"""Final natural-language answer, grounded strictly on the workflow's result sections."""

from __future__ import annotations

import logging
from typing import Any

from workflow_agent.core.exceptions import LLMError
from workflow_agent.core.models import RunStatus
from workflow_agent.llm.client import LLMClient
from workflow_agent.llm.prompts import PromptLibrary

logger = logging.getLogger(__name__)

SYSTEM = (
    "You write the final answer of a workflow automation agent. Base every statement strictly on the "
    "RESULT data provided - do not add facts, numbers or recommendations that are not in it."
)


def _compact_sections(sections: list[dict[str, Any]], max_rows: int = 25) -> list[dict[str, Any]]:
    compact = []
    for section in sections:
        data = section["data"]
        if section["kind"] == "table":
            data = {"columns": data["columns"], "rows": data["rows"][:max_rows], "total_rows": data["total_rows"]}
        compact.append({"title": section["title"], "kind": section["kind"], "data": data})
    return compact


def fallback_summary(state: dict[str, Any]) -> str:
    status = state.get("status")
    name = state.get("workflow_name") or "The workflow"
    if status == RunStatus.FAILED.value:
        return f"{name} could not be completed: {state.get('error') or 'unknown error'}"
    parts = []
    for section in state.get("sections", []):
        if section["kind"] == "table":
            parts.append(f"{section['data']['total_rows']} row(s) in '{section['title']}'")
        elif section["kind"] == "text":
            parts.append(section["data"])
    prefix = {
        RunStatus.ESCALATED.value: f"{name} escalated to a human",
        RunStatus.COMPLETED_WITH_FLAGS.value: f"{name} completed with {len(state.get('flags', []))} flag(s)",
    }.get(status, f"{name} completed")
    return prefix + (": " + "; ".join(parts) if parts else ".")


class ResultSummarizer:
    def __init__(self, llm: LLMClient | None, prompts: PromptLibrary, enabled: bool = True) -> None:
        self.llm = llm
        self.prompts = prompts
        self.enabled = enabled

    def summarize(self, state: dict[str, Any], workflow_expected_output: str = "") -> str:
        if state.get("status") == RunStatus.FAILED.value or not self.enabled or self.llm is None:
            return fallback_summary(state)
        conversation = "\n".join(
            f"{m['role'].upper()}: {m['content']}" for m in state.get("transcript", [])
        ) or str(state.get("request"))
        prompt = self.prompts.render("result_summary", {
            "conversation": conversation,
            "workflow": f"{state.get('workflow_id')} - {state.get('workflow_name')}",
            "expected_output": workflow_expected_output,
            "status": state.get("status"),
            "flags": state.get("flags", []),
            "warnings": state.get("warnings", []),
            "sections": _compact_sections(state.get("sections", [])),
        })
        try:
            data = self.llm.structured(system=SYSTEM, prompt=prompt, schema={
                "type": "object", "properties": {"answer": {"type": "string"}},
                "required": ["answer"], "additionalProperties": False,
            }, effort="low", max_tokens=3000, tag="result_summary")
            return str(data.get("answer") or fallback_summary(state))
        except LLMError as exc:
            logger.warning("Summary generation failed (%s) - using fallback summary", exc)
            return fallback_summary(state)
