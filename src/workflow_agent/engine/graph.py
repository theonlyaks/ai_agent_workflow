"""LangGraph orchestration.

    START -> route -> execute -> finalize -> END
               |        |
               v        v
             clarify (human-in-the-loop: interrupt() pauses the graph, the user's answer
                      resumes it from the checkpoint, inputs are merged, then we go back
                      to `route` or re-run `execute`)

Each node returns a partial state update; conditional edges implement the decisions.
State holds only JSON-serialisable data so any LangGraph checkpointer (memory, SQLite,
Postgres) can persist it.
"""

from __future__ import annotations

import functools
import logging
import operator
import time
from datetime import datetime, timezone
from typing import Annotated, Any, Callable, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.errors import GraphInterrupt
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from workflow_agent.core.config import Settings
from workflow_agent.core.logging import log_context
from workflow_agent.core.models import RunStatus
from workflow_agent.engine.execution_log import ExecutionLog
from workflow_agent.engine.executor import WorkflowExecutor
from workflow_agent.engine.input_extractor import InputExtractor
from workflow_agent.engine.router import WorkflowRouter
from workflow_agent.engine.summarizer import ResultSummarizer
from workflow_agent.llm.client import LLMClient
from workflow_agent.registry.workflow_registry import WorkflowRegistry

logger = logging.getLogger(__name__)

ROUTED = "routed"


class AgentState(TypedDict, total=False):
    run_id: str
    request: str
    transcript: list[dict[str, str]]
    started_at: float
    workflow_id: str | None
    workflow_name: str | None
    routing: dict[str, Any]
    inputs: dict[str, Any]
    effective_inputs: dict[str, Any]
    status: str
    steps: list[dict[str, Any]]
    sections: list[dict[str, Any]]
    flags: list[str]
    warnings: list[str]
    question: str | None
    needs: list[str]
    clarify_target: str | None
    clarification_rounds: int
    summary: str | None
    error: str | None
    duration_ms: float
    processing_ms: Annotated[float, operator.add]  # agent time only - excludes waiting for the user
    llm_usage: dict[str, Any]


def traced_node(name: str) -> Callable:
    """Bind log context, time the node, and turn unexpected crashes into a FAILED state."""

    def decorator(fn: Callable[[AgentState], dict[str, Any]]) -> Callable[[AgentState], dict[str, Any]]:
        @functools.wraps(fn)
        def wrapper(state: AgentState) -> dict[str, Any]:
            with log_context(state.get("run_id"), state.get("workflow_id") or "-"):
                started = time.perf_counter()
                try:
                    update = fn(state)
                except GraphInterrupt:
                    logger.info("Node '%s' paused - waiting for user input", name)
                    raise
                except Exception as exc:
                    logger.exception("Node '%s' crashed", name)
                    update = {"status": RunStatus.FAILED.value, "error": f"Internal error in '{name}': {exc}"}
                elapsed_ms = (time.perf_counter() - started) * 1000
                logger.info("Node '%s' -> %s (%.0f ms)", name, update.get("status", "-"), elapsed_ms)
                return {**update, "processing_ms": elapsed_ms}

        return wrapper

    return decorator


def build_graph(
    *,
    registry: WorkflowRegistry,
    router: WorkflowRouter,
    executor: WorkflowExecutor,
    extractor: InputExtractor,
    summarizer: ResultSummarizer,
    execution_log: ExecutionLog,
    llm: LLMClient | None,
    settings: Settings,
    checkpointer: BaseCheckpointSaver,
):
    @traced_node("route")
    def route(state: AgentState) -> dict[str, Any]:
        decision = router.route(state["request"])
        routing = decision.model_dump(exclude={"inputs"})
        if decision.action == "clarify":
            return {"status": RunStatus.NEEDS_INPUT.value, "question": decision.question, "needs": [],
                    "clarify_target": "route", "routing": routing}
        workflow = registry.get(decision.workflow_id)  # type: ignore[arg-type]
        return {
            "status": ROUTED,
            "workflow_id": workflow.id,
            "workflow_name": workflow.name,
            "routing": routing,
            "inputs": {**state.get("inputs", {}), **decision.inputs},
        }

    @traced_node("execute")
    def execute(state: AgentState) -> dict[str, Any]:
        workflow = registry.get(state["workflow_id"])  # type: ignore[arg-type]
        result = executor.run(workflow, state.get("inputs", {}), state["run_id"])
        update: dict[str, Any] = {
            "status": result.status.value,
            "steps": result.steps,
            "sections": result.sections,
            "flags": result.flags,
            "warnings": result.warnings,
            "effective_inputs": result.effective_inputs,
            "question": result.question,
            "needs": result.needs,
            "error": result.message if result.status == RunStatus.FAILED else None,
        }
        if result.status == RunStatus.NEEDS_INPUT:
            update["clarify_target"] = "execute"
        return update

    @traced_node("clarify")
    def clarify(state: AgentState) -> dict[str, Any]:
        rounds = state.get("clarification_rounds", 0)
        if rounds >= settings.max_clarification_rounds:
            return {"status": RunStatus.FAILED.value,
                    "error": f"Required information is still missing after {rounds} question(s). "
                             "Please start a new request including all the details."}
        question = state.get("question") or "Could you provide more details?"
        reply = str(interrupt({"question": question, "needs": state.get("needs", []),
                               "workflow_id": state.get("workflow_id")})).strip()
        transcript = [*state.get("transcript", []), {"role": "assistant", "content": question},
                      {"role": "user", "content": reply}]
        base = {"transcript": transcript, "clarification_rounds": rounds + 1, "question": None}
        if state.get("clarify_target") == "route":
            return {**base, "request": f"{state['request']}\n{reply}", "status": "clarified"}
        workflow = registry.get(state["workflow_id"])  # type: ignore[arg-type]
        new_inputs = extractor.extract(workflow, transcript, state.get("inputs", {}), state.get("needs", []))
        return {**base, "inputs": {**state.get("inputs", {}), **new_inputs}, "status": ROUTED}

    @traced_node("finalize")
    def finalize(state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        expected = registry.get(state["workflow_id"]).definition.expected_output if state.get("workflow_id") else ""
        summary = summarizer.summarize(dict(state), expected)
        # Agent processing time (excludes time spent waiting for the user's answers)
        duration_ms = round(state.get("processing_ms", 0.0) + (time.perf_counter() - started) * 1000, 1)
        wall_clock_ms = round((time.time() - state["started_at"]) * 1000, 1)
        usage = llm.usage_for(state["run_id"]) if llm is not None else {}
        execution_log.append({
            "run_id": state["run_id"],
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "request": state.get("request"),
            "workflow_id": state.get("workflow_id"),
            "workflow_name": state.get("workflow_name"),
            "routing_method": (state.get("routing") or {}).get("method"),
            "status": state.get("status"),
            "duration_ms": duration_ms,
            "wall_clock_ms": wall_clock_ms,
            "clarification_rounds": state.get("clarification_rounds", 0),
            "error": state.get("error"),
            "llm_usage": usage,
            "steps": [{k: s[k] for k in ("index", "name", "status", "duration_ms", "message")}
                      for s in state.get("steps", [])],
        })
        return {"summary": summary, "duration_ms": duration_ms, "llm_usage": usage}

    def after_route(state: AgentState) -> str:
        status = state.get("status")
        if status == ROUTED:
            return "execute"
        return "clarify" if status == RunStatus.NEEDS_INPUT.value else "finalize"

    def after_execute(state: AgentState) -> str:
        return "clarify" if state.get("status") == RunStatus.NEEDS_INPUT.value else "finalize"

    def after_clarify(state: AgentState) -> str:
        if state.get("status") == RunStatus.FAILED.value:
            return "finalize"
        return "route" if state.get("clarify_target") == "route" else "execute"

    graph = StateGraph(AgentState)
    graph.add_node("route", route)
    graph.add_node("execute", execute)
    graph.add_node("clarify", clarify)
    graph.add_node("finalize", finalize)
    graph.add_edge(START, "route")
    graph.add_conditional_edges("route", after_route, {"execute": "execute", "clarify": "clarify", "finalize": "finalize"})
    graph.add_conditional_edges("execute", after_execute, {"clarify": "clarify", "finalize": "finalize"})
    graph.add_conditional_edges("clarify", after_clarify, {"route": "route", "execute": "execute", "finalize": "finalize"})
    graph.add_edge("finalize", END)
    return graph.compile(checkpointer=checkpointer)
