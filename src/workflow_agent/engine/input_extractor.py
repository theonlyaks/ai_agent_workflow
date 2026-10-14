"""Turns a user's follow-up answer into workflow inputs (after the agent asked a question)."""

from __future__ import annotations

import logging
from typing import Any

from workflow_agent.core.exceptions import LLMError
from workflow_agent.core.models import Workflow
from workflow_agent.engine.router import extract_with_patterns, input_json_schema
from workflow_agent.llm.client import LLMClient
from workflow_agent.llm.prompts import PromptLibrary
from workflow_agent.llm.schema import nullable
from workflow_agent.tools.data_tools import is_blank

logger = logging.getLogger(__name__)

SYSTEM = (
    "You extract structured workflow inputs from a conversation. Only use values the user actually "
    "stated. Use null for anything not mentioned. Never invent values."
)


class InputExtractor:
    def __init__(self, llm: LLMClient | None, prompts: PromptLibrary) -> None:
        self.llm = llm
        self.prompts = prompts

    def extract(
        self,
        workflow: Workflow,
        transcript: list[dict[str, str]],
        current_inputs: dict[str, Any],
        needs: list[str],
    ) -> dict[str, Any]:
        latest_reply = transcript[-1]["content"] if transcript else ""
        if self.llm is not None:
            try:
                return self._extract_with_llm(workflow, transcript, current_inputs, needs)
            except LLMError as exc:
                logger.warning("LLM input extraction failed (%s) - using pattern extraction", exc)
        return self._extract_offline(workflow, latest_reply, needs)

    def _extract_with_llm(self, workflow, transcript, current_inputs, needs) -> dict[str, Any]:
        specs = workflow.binding.inputs
        schema = {
            "type": "object",
            "properties": {s.name: nullable(input_json_schema(s)) for s in specs},
            "required": [s.name for s in specs],
            "additionalProperties": False,
        }
        prompt = self.prompts.render("extract_inputs", {
            "workflow": f"{workflow.id} - {workflow.name}: {workflow.definition.trigger}",
            "inputs": [{"name": s.name, "type": s.type, "description": s.description} for s in specs],
            "current_inputs": {k: v for k, v in current_inputs.items() if not is_blank(v)},
            "needs": needs,
            "transcript": "\n".join(f"{m['role'].upper()}: {m['content']}" for m in transcript),
        })
        data = self.llm.structured(system=SYSTEM, prompt=prompt, schema=schema, effort="low",  # type: ignore[union-attr]
                                   max_tokens=4000, tag="extract_inputs")
        extracted = {k: v for k, v in data.items() if not is_blank(v)}
        logger.info("Extracted inputs from reply: %s", extracted)
        return extracted

    @staticmethod
    def _extract_offline(workflow: Workflow, reply: str, needs: list[str]) -> dict[str, Any]:
        found = extract_with_patterns(workflow, reply)
        missing = [n for n in needs if n not in found]
        if len(missing) == 1 and reply.strip():
            # One thing was asked for -> the whole answer is that value
            found[missing[0]] = reply.strip()
        return found
