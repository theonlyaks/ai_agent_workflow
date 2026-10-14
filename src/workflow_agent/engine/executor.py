"""Generic workflow executor.

Runs the Excel steps of ANY workflow, in order, by invoking the tools its YAML binding
names. It knows nothing about inventory, orders or keywords - that is the whole point:
one engine, many workflows.

Per call it: resolves `$references`, invokes the tool, retries transient failures,
captures errors, times everything and records a trace. Tool statuses drive the
condition handling (flag / ask the user / escalate / fail).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from workflow_agent.core.config import Settings
from workflow_agent.core.exceptions import LLMError, ToolError, TransientToolError, WorkflowAgentError
from workflow_agent.core.models import (
    STATUS_SEVERITY,
    TERMINAL_STATUSES,
    CallSpec,
    InputSpec,
    RunStatus,
    StepStatus,
    ToolResult,
    Workflow,
)
from workflow_agent.engine.serialization import make_section, to_jsonable
from workflow_agent.llm.client import LLMClient
from workflow_agent.llm.prompts import PromptLibrary
from workflow_agent.tools.data_tools import is_blank
from workflow_agent.tools.registry import ToolContext, ToolRegistry
from workflow_agent.tools.validation_tools import humanize

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    status: RunStatus
    steps: list[dict[str, Any]]
    sections: list[dict[str, Any]] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    question: str | None = None
    needs: list[str] = field(default_factory=list)
    message: str | None = None
    effective_inputs: dict[str, Any] = field(default_factory=dict)


def lookup(path: str, values: dict[str, Any]) -> Any:
    """'restock.items' -> values['restock']['items'] (dicts, DataFrame columns, attributes)."""
    root, *parts = path.split(".")
    current = values.get(root)
    for part in parts:
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, pd.DataFrame) and part in current.columns:
            current = current[part].tolist()
        else:
            current = getattr(current, part, None)
    return current


def resolve(value: Any, values: dict[str, Any]) -> Any:
    if isinstance(value, str) and value.startswith("$"):
        return lookup(value[1:], values)
    if isinstance(value, dict):
        return {k: resolve(v, values) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve(v, values) for v in value]
    return value


def coerce_input(spec: InputSpec, value: Any) -> Any:
    if is_blank(value):
        return None
    if spec.type == "number":
        return float(str(value).replace("%", "").strip())
    if spec.type == "integer":
        return int(float(str(value).strip()))
    if spec.type == "boolean":
        return value if isinstance(value, bool) else str(value).strip().lower() in {"true", "yes", "1", "y"}
    if spec.type == "array":
        return value if isinstance(value, list) else [v.strip() for v in str(value).split(",") if v.strip()]
    return value if isinstance(value, str) else str(value)


def _worst(statuses: list[StepStatus]) -> StepStatus:
    return max(statuses, key=lambda s: STATUS_SEVERITY[s]) if statuses else StepStatus.OK


class WorkflowExecutor:
    def __init__(self, tools: ToolRegistry, settings: Settings, llm: LLMClient | None, prompts: PromptLibrary) -> None:
        self.tools = tools
        self.settings = settings
        self.llm = llm
        self.prompts = prompts

    def effective_inputs(self, workflow: Workflow, inputs: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        """User inputs + defaults, type-coerced. Unknown keys are dropped."""
        assert workflow.binding is not None
        resolved: dict[str, Any] = {}
        warnings: list[str] = []
        for spec in workflow.binding.inputs:
            value = inputs.get(spec.name)
            try:
                value = coerce_input(spec, value)
            except (TypeError, ValueError):
                warnings.append(f"Ignored invalid value for {humanize(spec.name)}: {value!r}")
                value = None
            if value is None and spec.default is not None:
                value = spec.default
                if spec.announce_default:
                    warnings.append(f"No {humanize(spec.name)} was given - using the default: {spec.default}")
            resolved[spec.name] = value
        return resolved, warnings

    def run(self, workflow: Workflow, inputs: dict[str, Any], run_id: str) -> ExecutionResult:
        if workflow.binding is None:
            return ExecutionResult(
                status=RunStatus.FAILED, steps=[],
                message=f"Workflow {workflow.id} has no execution binding in {self.settings.workflow_config_path.name}",
            )
        binding = workflow.binding
        effective, warnings = self.effective_inputs(workflow, inputs)
        values: dict[str, Any] = {"inputs": effective, "params": binding.params, "run": {"id": run_id}, "metrics": {}}
        ctx = ToolContext(run_id=run_id, settings=self.settings, llm=self.llm, prompts=self.prompts)

        steps: list[dict[str, Any]] = []
        flags: list[str] = []
        stop: ToolResult | None = None

        for index, (step_name, step) in enumerate(zip(workflow.definition.steps, binding.steps), start=1):
            step_started = time.perf_counter()
            call_traces, call_statuses = [], []
            logger.info("Step %d/%d: %s", index, len(binding.steps), step_name)
            for call in step.calls:
                result, attempts, call_ms = self._invoke(call, resolve(call.args, values), ctx)
                effective_status = result.status
                if result.status == StepStatus.FAILED and call.continue_on_error:
                    warnings.append(f"Step '{step_name}': {call.tool} failed but is optional - {result.message}")
                    effective_status = StepStatus.OK
                call_statuses.append(effective_status)
                warnings.extend(result.warnings)
                if result.status == StepStatus.FLAGGED and result.message:
                    flags.append(result.message)
                call_traces.append({
                    "tool": call.tool,
                    "status": result.status.value,
                    "duration_ms": round(call_ms, 1),
                    "attempts": attempts,
                    "message": result.message,
                    "metrics": to_jsonable(result.metrics),
                    "warnings": result.warnings,
                })
                if call.save_as:
                    values[call.save_as] = result.output
                    values["metrics"][call.save_as] = result.metrics
                if effective_status in TERMINAL_STATUSES:
                    stop = result
                    break

            step_status = _worst(call_statuses)
            messages = [c["message"] for c in call_traces if c["message"]]
            steps.append({
                "index": index,
                "name": step_name,
                "status": step_status.value,
                "duration_ms": round((time.perf_counter() - step_started) * 1000, 1),
                "message": " → ".join(dict.fromkeys(messages)) if messages else None,
                "calls": call_traces,
            })
            if stop is not None:
                break

        # Steps never reached are shown as skipped so the trace always mirrors the Excel steps
        for index in range(len(steps) + 1, len(workflow.definition.steps) + 1):
            steps.append({"index": index, "name": workflow.definition.steps[index - 1], "status": StepStatus.SKIPPED.value,
                          "duration_ms": 0, "message": None, "calls": []})

        return self._result(binding, values, steps, flags, warnings, stop, effective)

    # ------------------------------------------------------------------
    def _invoke(self, call: CallSpec, args: dict[str, Any], ctx: ToolContext) -> tuple[ToolResult, int, float]:
        started = time.perf_counter()
        attempts = call.retry.attempts
        for attempt in range(1, attempts + 1):
            try:
                result = self.tools.invoke(call.tool, args, ctx)
                return result, attempt, (time.perf_counter() - started) * 1000
            except TransientToolError as exc:
                if attempt == attempts:
                    message = f"{exc} (gave up after {attempt} attempt{'s' if attempt > 1 else ''})"
                    logger.error("Tool %s failed: %s", call.tool, message)
                    return ToolResult(status=StepStatus.FAILED, message=message), attempt, (time.perf_counter() - started) * 1000
                delay = call.retry.backoff_seconds * (2 ** (attempt - 1))
                logger.warning("Tool %s transient error (%s) - retry %d/%d in %.1fs", call.tool, exc, attempt, attempts - 1, delay)
                time.sleep(delay)
            except (ToolError, LLMError) as exc:
                logger.warning("Tool %s failed: %s", call.tool, exc)
                return ToolResult(status=StepStatus.FAILED, message=str(exc)), attempt, (time.perf_counter() - started) * 1000
            except WorkflowAgentError as exc:
                logger.error("Tool %s error: %s", call.tool, exc)
                return ToolResult(status=StepStatus.FAILED, message=str(exc)), attempt, (time.perf_counter() - started) * 1000
            except Exception as exc:  # a bug in a tool must not crash the agent
                logger.exception("Unexpected error in tool %s", call.tool)
                return (
                    ToolResult(status=StepStatus.FAILED, message=f"Unexpected error in {call.tool}: {exc}"),
                    attempt,
                    (time.perf_counter() - started) * 1000,
                )
        raise AssertionError("unreachable")

    @staticmethod
    def _result(binding, values, steps, flags, warnings, stop, effective) -> ExecutionResult:
        if stop is not None and stop.status == StepStatus.FAILED:
            return ExecutionResult(status=RunStatus.FAILED, steps=steps, flags=flags, warnings=warnings,
                                   message=stop.message, effective_inputs=to_jsonable(effective))
        if stop is not None and stop.status == StepStatus.NEEDS_INPUT:
            return ExecutionResult(status=RunStatus.NEEDS_INPUT, steps=steps, flags=flags, warnings=warnings,
                                   question=stop.question or stop.message, needs=stop.needs,
                                   message=stop.message, effective_inputs=to_jsonable(effective))

        sections = [make_section(s.title, values[s.source]) for s in binding.output if values.get(s.source) is not None]
        if stop is not None and stop.status == StepStatus.ESCALATE:
            sections.insert(0, make_section("Escalation", stop.message))
            status = RunStatus.ESCALATED
        else:
            status = RunStatus.COMPLETED_WITH_FLAGS if flags else RunStatus.COMPLETED
        return ExecutionResult(status=status, steps=steps, sections=sections, flags=flags,
                               warnings=list(dict.fromkeys(warnings)),
                               message=stop.message if stop else None, effective_inputs=to_jsonable(effective))
