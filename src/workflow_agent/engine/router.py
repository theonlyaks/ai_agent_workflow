"""Workflow selection.

Primary: Claude tool calling. Every executable workflow becomes a tool whose description
comes from the Excel row (name, trigger, inputs, decision logic, expected output) and
whose parameters come from the YAML input specs. Claude picks the tool (= the workflow)
and fills its arguments (= extracts inputs) in one call, or calls `ask_clarification`.
A new Excel row + binding automatically becomes a new routable tool.

Fallback: deterministic keyword/fuzzy scoring over the same Excel text + YAML keywords,
used when no LLM is configured or the API is unreachable (graceful degradation).
"""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field
from rapidfuzz import fuzz

from workflow_agent.core.exceptions import LLMError
from workflow_agent.core.models import InputSpec, Workflow
from workflow_agent.llm.client import LLMClient
from workflow_agent.llm.prompts import PromptLibrary
from workflow_agent.registry.workflow_registry import WorkflowRegistry
from workflow_agent.tools.data_tools import is_blank

logger = logging.getLogger(__name__)

CLARIFY_TOOL = "ask_clarification"
_JSON_TYPES = {"string": "string", "number": "number", "integer": "integer", "boolean": "boolean"}


class RouteDecision(BaseModel):
    action: Literal["run", "clarify"]
    workflow_id: str | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    reasoning: str = ""
    confidence: str = ""
    method: str = ""
    question: str | None = None


def input_json_schema(spec: InputSpec) -> dict[str, Any]:
    if spec.type == "array":
        schema: dict[str, Any] = {"type": "array", "items": {"type": "string"}}
    else:
        schema = {"type": _JSON_TYPES[spec.type]}
    schema["description"] = spec.description
    return schema


def tool_name_for(workflow_id: str) -> str:
    return "run_" + re.sub(r"[^a-z0-9_]", "_", workflow_id.lower())


def extract_with_patterns(workflow: Workflow, text: str) -> dict[str, Any]:
    """Offline input extraction using each input's `extract_pattern` regex."""
    found: dict[str, Any] = {}
    for spec in workflow.binding.inputs if workflow.binding else []:
        if spec.extract_pattern:
            match = re.search(spec.extract_pattern, text, flags=re.IGNORECASE)
            if match:
                found[spec.name] = match.group(1) if match.groups() else match.group(0)
    return found


def _normalize(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9%@.\-]+", text.lower()))


class WorkflowRouter:
    def __init__(self, registry: WorkflowRegistry, llm: LLMClient | None, prompts: PromptLibrary) -> None:
        self.registry = registry
        self.llm = llm
        self.prompts = prompts

    # ------------------------------------------------------------------
    def build_tools(self) -> list[dict[str, Any]]:
        tools = []
        for workflow in self.registry.executable():
            d = workflow.definition
            properties: dict[str, Any] = {
                "routing_reason": {"type": "string", "description": "One sentence: why this workflow fits the request."},
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
            }
            for spec in workflow.binding.inputs:  # type: ignore[union-attr]
                properties[spec.name] = input_json_schema(spec)
            tools.append({
                "name": tool_name_for(d.workflow_id),
                "description": (
                    f"Run workflow {d.workflow_id} - {d.name}.\n"
                    f"Use when: {d.trigger}.\n"
                    f"Business inputs: {'; '.join(d.inputs)}.\n"
                    f"Decision logic: {d.decision_logic}\n"
                    f"Returns: {d.expected_output}.\n"
                    "Only fill an argument when the user explicitly stated its value; otherwise omit it."
                ),
                "input_schema": {"type": "object", "properties": properties, "required": ["routing_reason", "confidence"]},
            })
        tools.append({
            "name": CLARIFY_TOOL,
            "description": (
                "Ask the user a clarifying question when the request does not clearly match exactly one "
                "workflow, is ambiguous between workflows, or is outside what these workflows can do."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "Short question for the user, mention what you can help with."},
                    "reason": {"type": "string"},
                },
                "required": ["question", "reason"],
            },
        })
        return tools

    def route(self, request: str) -> RouteDecision:
        if self.llm is not None:
            try:
                return self._route_with_llm(request)
            except LLMError as exc:
                logger.warning("LLM routing failed (%s) - falling back to keyword routing", exc)
                decision = self._route_with_keywords(request)
                decision.reasoning = f"[LLM unavailable: {exc}] " + decision.reasoning
                return decision
        return self._route_with_keywords(request)

    # ------------------------------------------------------------------
    def _route_with_llm(self, request: str) -> RouteDecision:
        tools = self.build_tools()
        system = self.prompts.render(
            "router_system",
            {"today": date.today().isoformat(), "workflow_count": str(len(tools) - 1)},
        )
        reply = self.llm.call_tools(  # type: ignore[union-attr]
            system=system, messages=[{"role": "user", "content": request}], tools=tools, effort="low"
        )
        by_tool = {tool_name_for(w.id): w for w in self.registry.executable()}

        if reply.tool_name in by_tool:
            workflow = by_tool[reply.tool_name]
            args = dict(reply.tool_input)
            reasoning = str(args.pop("routing_reason", ""))
            confidence = str(args.pop("confidence", ""))
            names = {s.name for s in workflow.binding.inputs}  # type: ignore[union-attr]
            inputs = {k: v for k, v in args.items() if k in names and not is_blank(v)}
            logger.info("Claude selected %s (confidence=%s): %s | inputs=%s", workflow.id, confidence, reasoning, inputs)
            return RouteDecision(action="run", workflow_id=workflow.id, inputs=inputs, reasoning=reasoning,
                                 confidence=confidence, method="llm_tool_call")

        if reply.tool_name == CLARIFY_TOOL:
            question = str(reply.tool_input.get("question") or "Could you clarify what you need?")
            logger.info("Claude asked for clarification: %s", question)
            return RouteDecision(action="clarify", question=question, method="llm_tool_call",
                                 reasoning=str(reply.tool_input.get("reason", "")))

        logger.info("Claude answered without a tool call - treating as clarification")
        return RouteDecision(action="clarify", method="llm_tool_call",
                             question=reply.text or self._capabilities_question())

    def _route_with_keywords(self, request: str) -> RouteDecision:
        text = _normalize(request)
        scored: list[tuple[float, Workflow]] = []
        for workflow in self.registry.executable():
            keywords = workflow.binding.keywords  # type: ignore[union-attr]
            hits = sum(1 for k in keywords if _normalize(k) in text)
            fuzzy = fuzz.token_set_ratio(text, _normalize(f"{workflow.name} {workflow.definition.trigger}"))
            scored.append((hits * 25 + fuzzy * 0.5, workflow))
        scored.sort(key=lambda item: item[0], reverse=True)

        if not scored:
            return RouteDecision(action="clarify", method="keyword_fallback", question="No workflows are configured.")
        best_score, best = scored[0]
        runner_up = scored[1][0] if len(scored) > 1 else 0
        if best_score < 45 or best_score - runner_up < 5:
            return RouteDecision(
                action="clarify", method="keyword_fallback",
                reasoning=f"Best keyword score {best_score:.0f} ({best.id}) is too weak or ambiguous",
                question=self._capabilities_question(),
            )
        return RouteDecision(
            action="run", workflow_id=best.id, inputs=extract_with_patterns(best, request),
            reasoning=f"Keyword/fuzzy match score {best_score:.0f} (next best {runner_up:.0f})",
            confidence="high" if best_score - runner_up >= 20 else "medium", method="keyword_fallback",
        )

    def _capabilities_question(self) -> str:
        options = "\n".join(f"- {w.name} ({w.definition.trigger.lower()})" for w in self.registry.executable())
        return "I'm not sure which workflow you need. I can help with:\n" + options + "\n\nWhat would you like to do?"
