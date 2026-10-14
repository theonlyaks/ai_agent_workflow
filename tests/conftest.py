"""Shared fixtures. Tests never call the real Claude API: they use offline mode or FakeLLM."""

from __future__ import annotations

from pathlib import Path

import pytest

from workflow_agent.core.config import PROJECT_ROOT, Settings
from workflow_agent.engine.agent import WorkflowAgent
from workflow_agent.llm.fake import FakeLLM
from workflow_agent.llm.prompts import PromptLibrary
from workflow_agent.tools import get_tool_registry
from workflow_agent.tools.registry import ToolContext


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,  # never read the developer's .env in tests
        anthropic_api_key=None,
        llm_enabled=False,
        log_dir=tmp_path / "logs",
        output_dir=tmp_path / "outputs",
        summary_enabled=False,
        log_level="WARNING",
    )


@pytest.fixture
def offline_agent(settings: Settings) -> WorkflowAgent:
    return WorkflowAgent(settings=settings, llm=None)


@pytest.fixture
def make_agent(settings: Settings):
    def factory(llm=None, **overrides) -> WorkflowAgent:
        custom = settings.model_copy(update=overrides) if overrides else settings
        return WorkflowAgent(settings=custom, llm=llm)

    return factory


@pytest.fixture
def tool_ctx(settings: Settings) -> ToolContext:
    return ToolContext(run_id="test-run", settings=settings, llm=FakeLLM(),
                       prompts=PromptLibrary(PROJECT_ROOT / "prompts"))


@pytest.fixture
def tools():
    return get_tool_registry()


def section(response, title_start: str) -> dict:
    return next(s for s in response.sections if s["title"].startswith(title_start))


def rows(response, title_start: str) -> list[dict]:
    return section(response, title_start)["data"]["rows"]
