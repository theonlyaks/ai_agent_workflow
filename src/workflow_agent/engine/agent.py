"""`WorkflowAgent` - the single entry point used by the Streamlit UI, the CLI and the tests."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from workflow_agent.core.config import Settings, get_settings
from workflow_agent.core.logging import log_context, setup_logging
from workflow_agent.core.models import AgentResponse, RunStatus
from workflow_agent.engine.execution_log import ExecutionLog
from workflow_agent.engine.executor import WorkflowExecutor
from workflow_agent.engine.graph import build_graph
from workflow_agent.engine.input_extractor import InputExtractor
from workflow_agent.engine.router import WorkflowRouter
from workflow_agent.engine.summarizer import ResultSummarizer
from workflow_agent.llm.client import LLMClient, build_llm
from workflow_agent.llm.prompts import PromptLibrary
from workflow_agent.registry.workflow_registry import WorkflowRegistry
from workflow_agent.tools import get_tool_registry

logger = logging.getLogger(__name__)

_AUTO: Any = object()


def new_run_id() -> str:
    return f"run-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"


class WorkflowAgent:
    def __init__(
        self,
        settings: Settings | None = None,
        llm: LLMClient | None = _AUTO,
        checkpointer: BaseCheckpointSaver | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        setup_logging(self.settings.log_level, self.settings.log_dir, self.settings.log_json_console)

        self.tools = get_tool_registry()
        self.prompts = PromptLibrary(self.settings.prompts_dir)
        self.registry = WorkflowRegistry.load(
            self.settings.workflow_excel_path, self.settings.workflow_config_path, self.tools, self.prompts
        )
        self.llm = build_llm(self.settings) if llm is _AUTO else llm
        self.router = WorkflowRouter(self.registry, self.llm, self.prompts)
        self.executor = WorkflowExecutor(self.tools, self.settings, self.llm, self.prompts)
        self.execution_log = ExecutionLog(self.settings.execution_log_path)
        self.graph = build_graph(
            registry=self.registry,
            router=self.router,
            executor=self.executor,
            extractor=InputExtractor(self.llm, self.prompts),
            summarizer=ResultSummarizer(self.llm, self.prompts, self.settings.summary_enabled),
            execution_log=self.execution_log,
            llm=self.llm,
            settings=self.settings,
            checkpointer=checkpointer or InMemorySaver(),
        )

    @property
    def offline(self) -> bool:
        return self.llm is None

    @property
    def model_name(self) -> str:
        return getattr(self.llm, "model", "offline (no LLM)")

    def start(self, request: str) -> AgentResponse:
        """Handle a new user request (new run / LangGraph thread)."""
        run_id = new_run_id()
        request = request.strip()
        with log_context(run_id):
            logger.info("New request: %s", request)
        payload = {
            "run_id": run_id,
            "request": request,
            "transcript": [{"role": "user", "content": request}],
            "started_at": time.time(),
            "inputs": {},
            "clarification_rounds": 0,
        }
        return self._invoke(run_id, payload, request)

    def resume(self, run_id: str, reply: str) -> AgentResponse:
        """Answer the question a paused run asked; the graph continues from its checkpoint."""
        with log_context(run_id):
            logger.info("User reply: %s", reply)
        return self._invoke(run_id, Command(resume=reply.strip()), None)

    def ask(self, request: str, replies: list[str] | None = None) -> AgentResponse:
        """Convenience for scripts/tests: start, then feed scripted replies while the agent asks."""
        response = self.start(request)
        for reply in replies or []:
            if not response.waiting_for_input:
                break
            response = self.resume(response.run_id, reply)
        return response

    # ------------------------------------------------------------------
    def _invoke(self, run_id: str, payload: Any, request: str | None) -> AgentResponse:
        config = {"configurable": {"thread_id": run_id}}
        try:
            result = self.graph.invoke(payload, config)
        except Exception as exc:  # last line of defence - the UI must never crash
            with log_context(run_id):
                logger.exception("Agent run failed")
            return AgentResponse(run_id=run_id, request=request or "", status=RunStatus.FAILED,
                                 error=f"Unexpected error: {exc}")
        return self._to_response(run_id, result)

    def _to_response(self, run_id: str, state: dict[str, Any]) -> AgentResponse:
        interrupts = state.get("__interrupt__") or []
        question = None
        status = RunStatus(state["status"]) if state.get("status") in RunStatus._value2member_map_ else RunStatus.FAILED
        if interrupts:
            status = RunStatus.NEEDS_INPUT
            value = interrupts[0].value
            question = value.get("question") if isinstance(value, dict) else str(value)
        return AgentResponse(
            run_id=run_id,
            request=state.get("request", ""),
            status=status,
            workflow_id=state.get("workflow_id"),
            workflow_name=state.get("workflow_name"),
            routing=state.get("routing", {}),
            inputs=state.get("effective_inputs") or state.get("inputs", {}),
            steps=state.get("steps", []),
            sections=state.get("sections", []) if not interrupts else [],
            summary=state.get("summary") if not interrupts else None,
            question=question,
            flags=state.get("flags", []),
            warnings=state.get("warnings", []),
            error=state.get("error"),
            duration_ms=state.get("duration_ms"),
            llm_usage=state.get("llm_usage", {}),
            transcript=state.get("transcript", []),
        )
