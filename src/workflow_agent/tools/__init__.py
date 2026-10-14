"""Importing this package registers every built-in tool."""

from workflow_agent.tools import (  # noqa: F401  (imported for their @tool side effects)
    api_tools,
    data_tools,
    llm_tools,
    ranking_tools,
    reporting_tools,
    similarity_tools,
    validation_tools,
)
from workflow_agent.tools.registry import ToolContext, ToolRegistry, registry


def get_tool_registry() -> ToolRegistry:
    return registry


__all__ = ["ToolContext", "ToolRegistry", "get_tool_registry", "registry"]
