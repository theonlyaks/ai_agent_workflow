"""Deterministic stand-in for Claude, used by the test-suite (no network, no cost)."""

from __future__ import annotations

from typing import Any, Callable

from workflow_agent.core.exceptions import LLMUnavailableError
from workflow_agent.llm.client import ToolCallReply


def sample_from_schema(schema: dict[str, Any]) -> Any:
    if "anyOf" in schema:
        return None  # nullable field -> "not mentioned"
    kind = schema.get("type")
    if "enum" in schema:
        return schema["enum"][0]
    if kind == "object":
        return {k: sample_from_schema(v) for k, v in schema.get("properties", {}).items()}
    if kind == "array":
        return [sample_from_schema(schema["items"])]
    return {"string": "Sample text", "integer": 1, "number": 1.0, "boolean": False}.get(kind)


class FakeLLM:
    model = "fake-llm"

    def __init__(
        self,
        responses: dict[str, Any] | None = None,
        router: Callable[[list[dict], list[dict]], ToolCallReply] | None = None,
    ) -> None:
        self.responses = responses or {}
        self.router = router
        self.calls: list[str] = []

    def call_tools(self, *, system: str, messages: list[dict], tools: list[dict], **_: Any) -> ToolCallReply:
        self.calls.append("router")
        if self.router is None:
            raise LLMUnavailableError("FakeLLM has no router - use the keyword fallback")
        return self.router(messages, tools)

    def structured(self, *, system: str, prompt: str, schema: dict[str, Any], tag: str = "", **_: Any) -> dict[str, Any]:
        self.calls.append(tag)
        response = self.responses.get(tag)
        if callable(response):
            return response(prompt, schema)
        if response is not None:
            return response
        return sample_from_schema(schema)

    def usage_for(self, run_id: str) -> dict[str, Any]:
        return {}
