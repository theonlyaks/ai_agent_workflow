"""Tool registry: every reusable tool registers itself with the @tool decorator.

Workflows never import tools directly - the YAML binding refers to tools by name and
the executor looks them up here. Adding a tool = writing one decorated function.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from workflow_agent.core.exceptions import ConfigError
from workflow_agent.core.models import ToolResult

if TYPE_CHECKING:
    from workflow_agent.core.config import Settings
    from workflow_agent.llm.client import LLMClient
    from workflow_agent.llm.prompts import PromptLibrary


@dataclass
class ToolContext:
    """Runtime services a tool may ask for by declaring a `ctx` parameter."""

    run_id: str
    settings: "Settings"
    llm: "LLMClient | None"
    prompts: "PromptLibrary"


@dataclass(frozen=True)
class ToolSpec:
    name: str
    func: Callable[..., Any]
    description: str
    category: str
    parameters: tuple[str, ...]
    required: tuple[str, ...]
    accepts_ctx: bool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(
        self, name: str | None = None, *, category: str = "general", description: str | None = None
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            signature = inspect.signature(func)
            params = [p for p in signature.parameters.values() if p.name != "ctx"]
            spec = ToolSpec(
                name=name or func.__name__,
                func=func,
                description=(description or inspect.getdoc(func) or "").strip().split("\n")[0],
                category=category,
                parameters=tuple(p.name for p in params),
                required=tuple(p.name for p in params if p.default is inspect.Parameter.empty),
                accepts_ctx="ctx" in signature.parameters,
            )
            if spec.name in self._tools:
                raise ConfigError(f"Tool '{spec.name}' is registered twice")
            self._tools[spec.name] = spec
            return func

        return decorator

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def get(self, name: str) -> ToolSpec:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ConfigError(f"Unknown tool '{name}'. Registered tools: {sorted(self._tools)}") from exc

    def specs(self) -> list[ToolSpec]:
        return sorted(self._tools.values(), key=lambda s: (s.category, s.name))

    def validate_args(self, name: str, args: dict[str, Any]) -> list[str]:
        """Static check of a YAML call against the tool signature (run at startup)."""
        if name not in self._tools:
            return [f"unknown tool '{name}'"]
        spec = self._tools[name]
        errors = [f"tool '{name}' has no argument '{a}'" for a in args if a not in spec.parameters]
        errors += [f"tool '{name}' requires argument '{r}'" for r in spec.required if r not in args]
        return errors

    def invoke(self, name: str, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        spec = self.get(name)
        kwargs = dict(args)
        if spec.accepts_ctx:
            kwargs["ctx"] = ctx
        result = spec.func(**kwargs)
        return result if isinstance(result, ToolResult) else ToolResult(output=result)


registry = ToolRegistry()
tool = registry.register
