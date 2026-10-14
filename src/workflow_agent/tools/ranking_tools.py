"""Ranking tools: skill matching, weighted scoring, best-candidate selection with escalation."""

from __future__ import annotations

from typing import Any

import pandas as pd

from workflow_agent.core.exceptions import ToolInputError
from workflow_agent.core.models import StepStatus, ToolResult
from workflow_agent.tools.data_tools import _as_bool_mask, _eval, as_frame, require_columns
from workflow_agent.tools.registry import tool


def _skill_set(value: Any, separator: str) -> set[str]:
    if isinstance(value, (list, tuple, set)):
        items = value
    else:
        items = str(value or "").split(separator)
    return {s.strip().lower() for s in items if str(s).strip()}


@tool(category="ranking")
def skill_match(
    table: Any, required_skills: list[str] | str | None, skills_column: str = "skills", separator: str = ";"
) -> ToolResult:
    """Share of required skills each row has (0-1), plus matched/missing skill lists."""
    frame = as_frame(table).copy()
    require_columns(frame, [skills_column], "skill_match")
    required = _skill_set(required_skills, separator if isinstance(required_skills, str) else ",")
    if not required:
        raise ToolInputError("No required skills were identified for the task")
    have = frame[skills_column].map(lambda v: _skill_set(v, separator))
    frame["matched_skills"] = have.map(lambda s: ", ".join(sorted(s & required)) or "-")
    frame["missing_skills"] = have.map(lambda s: ", ".join(sorted(required - s)) or "-")
    frame["skill_match"] = have.map(lambda s: round(len(s & required) / len(required), 2))
    full = int((frame["skill_match"] == 1).sum())
    return ToolResult(
        output=frame,
        message=f"Required: {', '.join(sorted(required))}. {full} of {len(frame)} have all skills",
        metrics={"required_skills": len(required), "full_matches": full},
    )


@tool(category="ranking")
def rank_rows(
    table: Any,
    weights: dict[str, float],
    score_column: str = "score",
    priority: str | None = None,
    weights_by_priority: dict[str, dict[str, float]] | None = None,
) -> ToolResult:
    """Weighted score over 0-1 columns, sorted best-first. Weights can depend on priority."""
    frame = as_frame(table).copy()
    chosen = weights
    if priority and weights_by_priority and str(priority).lower() in weights_by_priority:
        chosen = weights_by_priority[str(priority).lower()]
    require_columns(frame, list(chosen), "rank_rows")
    total = sum(chosen.values()) or 1
    frame[score_column] = sum(pd.to_numeric(frame[c], errors="coerce").fillna(0) * w for c, w in chosen.items()) / total
    frame[score_column] = frame[score_column].round(3)
    frame = frame.sort_values(score_column, ascending=False, kind="stable").reset_index(drop=True)
    frame.insert(0, "rank", range(1, len(frame) + 1))
    return ToolResult(output=frame, message="Weights: " + ", ".join(f"{c}={w}" for c, w in chosen.items()))


@tool(category="ranking")
def select_best(
    table: Any,
    where: str | None = None,
    variables: dict[str, Any] | None = None,
    top_n: int = 3,
    on_empty: str = "escalate",
    empty_message: str = "No candidate satisfies the selection criteria.",
) -> ToolResult:
    """Pick the top row that satisfies the criteria; escalate (or fail) when nobody qualifies."""
    frame = as_frame(table)
    eligible = frame[_as_bool_mask(_eval(frame, where, variables), frame)] if (where and len(frame)) else frame
    if eligible.empty:
        return ToolResult(
            output={"selected": None, "alternatives": []},
            status=StepStatus.ESCALATE if on_empty == "escalate" else StepStatus.FAILED,
            message=empty_message,
        )
    records = eligible.head(top_n).to_dict("records")
    return ToolResult(
        output={"selected": records[0], "alternatives": records[1:]},
        message=f"{len(eligible)} eligible candidate(s); selected rank #{records[0].get('rank', 1)}",
        metrics={"eligible": len(eligible)},
    )
