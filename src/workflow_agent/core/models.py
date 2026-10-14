"""Domain models shared by the registry, executor, graph and UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StepStatus(str, Enum):
    OK = "ok"
    FLAGGED = "flagged"  # business exception found (e.g. price diff > 10%) - workflow continues
    NEEDS_INPUT = "needs_input"  # workflow pauses and asks the user
    ESCALATE = "escalate"  # workflow stops, hand-off to a human
    FAILED = "failed"  # error - workflow stops
    SKIPPED = "skipped"


# Higher number wins when several calls/steps report different statuses
STATUS_SEVERITY = {
    StepStatus.SKIPPED: 0,
    StepStatus.OK: 1,
    StepStatus.FLAGGED: 2,
    StepStatus.ESCALATE: 3,
    StepStatus.NEEDS_INPUT: 4,
    StepStatus.FAILED: 5,
}
TERMINAL_STATUSES = {StepStatus.NEEDS_INPUT, StepStatus.ESCALATE, StepStatus.FAILED}


class RunStatus(str, Enum):
    COMPLETED = "completed"
    COMPLETED_WITH_FLAGS = "completed_with_flags"
    NEEDS_INPUT = "needs_input"
    ESCALATED = "escalated"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Excel side: WHAT a workflow is
# ---------------------------------------------------------------------------
class WorkflowDefinition(BaseModel):
    """One row of the `Workflows` sheet in the Excel file."""

    workflow_id: str
    name: str
    trigger: str
    inputs: list[str]
    steps: list[str]
    decision_logic: str
    tools_required: list[str]
    expected_output: str


class TestQuestion(BaseModel):
    """One row of the `Test_Questions` sheet."""

    workflow_id: str
    request: str
    what_to_check: str = ""


# ---------------------------------------------------------------------------
# YAML side: HOW a workflow is executed
# ---------------------------------------------------------------------------
class InputSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    type: Literal["string", "number", "integer", "boolean", "array"] = "string"
    description: str = ""
    required: bool = False
    default: Any = None
    announce_default: bool = False  # tell the user when the default value is used
    extract_pattern: str | None = None  # regex used by the offline (no-LLM) extractor


class RetryPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempts: int = Field(default=1, ge=1, le=10)
    backoff_seconds: float = Field(default=0.5, ge=0)


class CallSpec(BaseModel):
    """One tool invocation inside a step."""

    model_config = ConfigDict(extra="forbid")

    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    save_as: str | None = None
    retry: RetryPolicy = Field(default_factory=RetryPolicy)
    continue_on_error: bool = False


class StepBinding(BaseModel):
    """Binding for one Excel step: a single tool call (shorthand) or a list of calls."""

    model_config = ConfigDict(extra="forbid")

    calls: list[CallSpec]

    @model_validator(mode="before")
    @classmethod
    def _shorthand(cls, data: Any) -> Any:
        if isinstance(data, dict) and "tool" in data:
            return {"calls": [data]}
        return data


class OutputSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    source: str


class WorkflowBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keywords: list[str] = Field(default_factory=list)
    inputs: list[InputSpec] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    steps: list[StepBinding]
    output: list[OutputSection] = Field(default_factory=list)


class Workflow(BaseModel):
    """Excel definition + YAML binding = an executable workflow."""

    definition: WorkflowDefinition
    binding: WorkflowBinding | None = None

    @property
    def id(self) -> str:
        return self.definition.workflow_id

    @property
    def name(self) -> str:
        return self.definition.name

    @property
    def executable(self) -> bool:
        return self.binding is not None


# ---------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------
@dataclass
class ToolResult:
    """What every tool returns. Tools may also return a plain value (wrapped as OK)."""

    output: Any = None
    status: StepStatus = StepStatus.OK
    message: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    needs: list[str] = field(default_factory=list)  # input names the user must provide
    question: str | None = None  # question to ask when status == NEEDS_INPUT


class AgentResponse(BaseModel):
    """Final, JSON-serialisable result of one agent turn (shown in UI / CLI / outputs)."""

    run_id: str
    request: str
    status: RunStatus
    workflow_id: str | None = None
    workflow_name: str | None = None
    routing: dict[str, Any] = Field(default_factory=dict)
    inputs: dict[str, Any] = Field(default_factory=dict)
    steps: list[dict[str, Any]] = Field(default_factory=list)
    sections: list[dict[str, Any]] = Field(default_factory=list)
    summary: str | None = None
    question: str | None = None
    flags: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
    duration_ms: float | None = None
    llm_usage: dict[str, Any] = Field(default_factory=dict)
    transcript: list[dict[str, str]] = Field(default_factory=list)

    @property
    def waiting_for_input(self) -> bool:
        return self.status == RunStatus.NEEDS_INPUT
