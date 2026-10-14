"""Thin, provider-specific LLM adapter.

The rest of the app depends only on the `LLMClient` protocol (two operations:
`call_tools` for agent tool calling and `structured` for schema-constrained JSON), so the
provider/model can be swapped without touching workflows. `ClaudeClient` implements it
with the official Anthropic SDK.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import anthropic

from workflow_agent.core.config import Settings
from workflow_agent.core.exceptions import LLMError, LLMRefusalError
from workflow_agent.core.logging import run_id_var

logger = logging.getLogger(__name__)

FALLBACK_BETA = "server-side-fallback-2026-07-01"


@dataclass
class ToolCallReply:
    tool_name: str | None
    tool_input: dict[str, Any] = field(default_factory=dict)
    text: str = ""


class LLMClient(Protocol):
    model: str

    def call_tools(
        self, *, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]],
        effort: str = "low", max_tokens: int = 4096,
    ) -> ToolCallReply: ...

    def structured(
        self, *, system: str, prompt: str, schema: dict[str, Any], effort: str = "low",
        max_tokens: int = 8000, tag: str = "",
    ) -> dict[str, Any]: ...

    def usage_for(self, run_id: str) -> dict[str, Any]: ...


class UsageTracker:
    """Thread-safe token/latency accounting per run (shown in the UI, written to the run log)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._runs: dict[str, dict[str, Any]] = {}

    def record(self, run_id: str, input_tokens: int, output_tokens: int, latency_ms: float) -> None:
        with self._lock:
            usage = self._runs.setdefault(run_id, {"calls": 0, "input_tokens": 0, "output_tokens": 0, "latency_ms": 0.0})
            usage["calls"] += 1
            usage["input_tokens"] += input_tokens
            usage["output_tokens"] += output_tokens
            usage["latency_ms"] = round(usage["latency_ms"] + latency_ms, 1)

    def get(self, run_id: str) -> dict[str, Any]:
        with self._lock:
            return dict(self._runs.get(run_id, {}))


class ClaudeClient:
    def __init__(self, settings: Settings) -> None:
        if not settings.llm_available:
            raise LLMError("ClaudeClient needs ANTHROPIC_API_KEY")
        self._client = anthropic.Anthropic(
            api_key=settings.anthropic_api_key.get_secret_value(),  # type: ignore[union-attr]
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,  # SDK retries 408/409/429/5xx with backoff
        )
        self.model = settings.claude_model
        self._fallback_enabled = settings.claude_refusal_fallback
        self.usage = UsageTracker()

    # -- public API ---------------------------------------------------------
    def call_tools(
        self, *, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]],
        effort: str = "low", max_tokens: int = 4096,
    ) -> ToolCallReply:
        response = self._request(
            system=system, messages=messages, tools=tools, max_tokens=max_tokens,
            output_config={"effort": effort}, tag="router",
        )
        tool_use = next((b for b in response.content if b.type == "tool_use"), None)
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        return ToolCallReply(
            tool_name=tool_use.name if tool_use else None,
            tool_input=dict(tool_use.input) if tool_use else {},
            text=text,
        )

    def structured(
        self, *, system: str, prompt: str, schema: dict[str, Any], effort: str = "low",
        max_tokens: int = 8000, tag: str = "",
    ) -> dict[str, Any]:
        response = self._request(
            system=system,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
            tag=tag,
        )
        text = next((b.text for b in response.content if b.type == "text"), None)
        if not text:
            raise LLMError("Claude returned no JSON content")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError(f"Claude returned invalid JSON: {exc}") from exc

    def usage_for(self, run_id: str) -> dict[str, Any]:
        return self.usage.get(run_id)

    # -- internals ------------------------------------------------------------
    def _request(self, *, tag: str, **kwargs: Any) -> Any:
        extra: dict[str, Any] = {}
        if self._fallback_enabled:
            # Server-side refusal fallback: if the model declines, the API retries on a
            # fallback model inside the same call.
            extra = {"betas": [FALLBACK_BETA], "fallbacks": "default"}
        started = time.perf_counter()
        try:
            response = self._client.beta.messages.create(model=self.model, **extra, **kwargs)
        except anthropic.BadRequestError as exc:
            if self._fallback_enabled and "fallback" in str(exc).lower():
                logger.warning("Refusal fallback rejected by the API, disabling it: %s", exc.message)
                self._fallback_enabled = False
                return self._request(tag=tag, **kwargs)
            raise LLMError(f"Claude rejected the request: {exc.message}") from exc
        except anthropic.AuthenticationError as exc:
            raise LLMError("The Anthropic API key is invalid (401). Check ANTHROPIC_API_KEY in .env") from exc
        except anthropic.PermissionDeniedError as exc:
            raise LLMError(f"The API key cannot use model '{self.model}' (403)") from exc
        except anthropic.NotFoundError as exc:
            raise LLMError(f"Model '{self.model}' was not found (404). Check CLAUDE_MODEL") from exc
        except anthropic.RateLimitError as exc:
            raise LLMError("Rate limited by the Claude API (429) after retries - try again shortly") from exc
        except anthropic.APIStatusError as exc:
            raise LLMError(f"Claude API error {exc.status_code}: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:  # includes timeouts
            raise LLMError("Could not reach the Claude API (network error or timeout)") from exc

        latency_ms = (time.perf_counter() - started) * 1000
        usage = response.usage
        self.usage.record(run_id_var.get(), usage.input_tokens, usage.output_tokens, latency_ms)
        logger.info(
            "LLM call %s: %d in / %d out tokens, %.0f ms, stop=%s",
            tag, usage.input_tokens, usage.output_tokens, latency_ms, response.stop_reason,
            extra={"model": response.model, "request_id": getattr(response, "_request_id", None)},
        )
        if response.stop_reason == "refusal":
            raise LLMRefusalError("Claude declined this request")
        if response.stop_reason == "max_tokens":
            raise LLMError("Claude's response was cut off (max_tokens reached)")
        return response


def build_llm(settings: Settings) -> LLMClient | None:
    """Claude when a key is configured, otherwise None (offline mode)."""
    if not settings.llm_available:
        logger.warning("No ANTHROPIC_API_KEY configured - running in OFFLINE mode (keyword routing, no LLM steps)")
        return None
    return ClaudeClient(settings)
