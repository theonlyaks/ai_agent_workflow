"""Reporting tools: execution-log loading (historical sample + this app's own live runs)."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from workflow_agent.core.config import resolve_path
from workflow_agent.core.models import ToolResult
from workflow_agent.tools.data_tools import load_frame
from workflow_agent.tools.registry import ToolContext, tool

LOG_COLUMNS = ["run_id", "timestamp", "workflow_id", "workflow_name", "step", "status", "duration_ms", "error"]


def flatten_live_runs(path) -> pd.DataFrame:
    """logs/executions.jsonl (one run per line, nested steps) -> step-level rows."""
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return pd.DataFrame(columns=LOG_COLUMNS)
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            run = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not run.get("workflow_id"):
            continue
        for step in run.get("steps", []):
            failed = step.get("status") == "failed"
            rows.append({
                "run_id": run["run_id"],
                "timestamp": run.get("finished_at"),
                "workflow_id": run["workflow_id"],
                "workflow_name": run.get("workflow_name"),
                "step": step.get("name"),
                "status": "failed" if failed else "success",
                "duration_ms": step.get("duration_ms", 0),
                "error": step.get("message") if failed else None,
            })
    return pd.DataFrame(rows, columns=LOG_COLUMNS)


@tool(category="reporting")
def load_execution_logs(path: str, ctx: ToolContext, include_live_runs: bool = True) -> ToolResult:
    """Load step-level workflow execution logs (CSV history + this app's own run log)."""
    history = load_frame(resolve_path(path))
    history["source"] = "history"
    frames = [history]
    live_count = 0
    if include_live_runs:
        live = flatten_live_runs(ctx.settings.execution_log_path)
        live_count = live["run_id"].nunique() if len(live) else 0
        if len(live):
            live["source"] = "live"
            frames.append(live)
    logs = pd.concat(frames, ignore_index=True)
    logs["duration_ms"] = pd.to_numeric(logs["duration_ms"], errors="coerce").fillna(0)
    return ToolResult(
        output=logs,
        message=f"{logs['run_id'].nunique()} runs / {len(logs)} step records ({live_count} live runs from this app)",
        metrics={"runs": int(logs["run_id"].nunique()), "step_records": len(logs), "live_runs": int(live_count)},
    )
