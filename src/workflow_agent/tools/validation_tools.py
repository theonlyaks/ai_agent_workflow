"""Validation tools: required inputs, identifiers, file columns/rows, text limits."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd
from rapidfuzz import fuzz

from workflow_agent.core.exceptions import ToolError
from workflow_agent.core.models import StepStatus, ToolResult
from workflow_agent.tools.data_tools import as_frame, is_blank, row_labels
from workflow_agent.tools.registry import tool


def humanize(name: str) -> str:
    return name.replace("_", " ")


def human_join(items: list[str]) -> str:
    items = [humanize(i) for i in items]
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _normalize_header(name: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(name).lower()).strip()


@tool(category="validation")
def validate_fields(
    record: dict[str, Any] | None,
    required: list[str] | None = None,
    recommended: list[str] | None = None,
    question: str | None = None,
    suggestions: Any = None,
    suggestion_columns: list[str] | None = None,
) -> ToolResult:
    """Check that required fields are present; missing ones pause the workflow and ask the user."""
    record = record or {}
    provided = {k: v for k, v in record.items() if not is_blank(v)}
    missing_required = [f for f in (required or []) if f not in provided]
    missing_recommended = [f for f in (recommended or []) if f not in provided]
    output = {
        "provided": provided,
        "missing_required": missing_required,
        "missing_recommended": missing_recommended,
    }
    if missing_required:
        text = (question or "Please provide the {missing}.").format(missing=human_join(missing_required))
        if suggestions is not None:
            frame = as_frame(suggestions)
            columns = suggestion_columns or list(frame.columns[:3])
            options = [" | ".join(str(r[c]) for c in columns) for r in frame.head(10).to_dict("records")]
            if options:
                text += "\n\nAvailable options:\n" + "\n".join(f"- {o}" for o in options)
        return ToolResult(
            output=output,
            status=StepStatus.NEEDS_INPUT,
            needs=missing_required,
            question=text,
            message=f"Missing required information: {human_join(missing_required)}",
        )
    warnings = []
    if missing_recommended:
        warnings.append(
            f"Not provided (marked as missing, not invented): {human_join(missing_recommended)}"
        )
    return ToolResult(
        output=output,
        message=f"All required fields present ({len(provided)} provided)",
        metrics={"provided": len(provided), "missing_recommended": len(missing_recommended)},
        warnings=warnings,
    )


@tool(category="validation")
def validate_identifier(
    value: Any,
    patterns: dict[str, str],
    input_name: str = "identifier",
    normalize: dict[str, str] | None = None,
    question: str = "Please provide a valid identifier.",
) -> ToolResult:
    """Validate an identifier against named regex patterns (e.g. order_id / email)."""
    if is_blank(value):
        return ToolResult(
            status=StepStatus.NEEDS_INPUT, needs=[input_name], question=question,
            message=f"No {humanize(input_name)} provided",
        )
    text = str(value).strip()
    for kind, pattern in patterns.items():
        if re.fullmatch(pattern, text, flags=re.IGNORECASE):
            mode = (normalize or {}).get(kind)
            text = text.upper() if mode == "upper" else text.lower() if mode == "lower" else text
            return ToolResult(
                output={"type": kind, "value": text},
                message=f"Valid {humanize(kind)}: {text}",
            )
    return ToolResult(
        status=StepStatus.NEEDS_INPUT,
        needs=[input_name],
        question=f"'{text}' doesn't look like a valid {' or '.join(humanize(k) for k in patterns)}. {question}",
        message=f"Invalid {humanize(input_name)}: {text}",
    )


@tool(category="validation")
def detect_columns(table: Any, aliases: dict[str, list[str]], min_score: float = 90) -> ToolResult:
    """Map messy source headers to canonical names using an alias list (exact, then fuzzy)."""
    frame = as_frame(table)
    lookup = {_normalize_header(a): canonical for canonical, names in aliases.items() for a in [canonical, *names]}
    mapping: dict[str, str] = {}
    used: set[str] = set()
    warnings: list[str] = []
    for column in frame.columns:
        header = _normalize_header(column)
        canonical = lookup.get(header)
        if canonical is None and header:
            best = max(lookup, key=lambda alias: fuzz.ratio(header, alias))
            if fuzz.ratio(header, best) >= min_score:
                canonical = lookup[best]
        if canonical and canonical not in used:
            mapping[str(column)] = canonical
            used.add(canonical)
        elif canonical:
            warnings.append(f"Column '{column}' also looks like '{canonical}' - kept as-is")
    unmapped = [str(c) for c in frame.columns if str(c) not in mapping]
    if unmapped:
        warnings.append(f"Unrecognised columns kept with snake_case names: {unmapped}")
    return ToolResult(
        output=mapping,
        message=f"Detected {len(mapping)} of {len(frame.columns)} columns",
        metrics={"columns_detected": len(mapping), "columns_unmapped": len(unmapped)},
        warnings=warnings,
    )


@tool(category="validation")
def validate_rows(
    table: Any, required_columns: list[str], numeric_columns: list[str] | None = None
) -> ToolResult:
    """Row-level validation: rows missing a required field are invalid; bad numbers are warnings."""
    frame = as_frame(table).copy()
    missing = [c for c in required_columns if c not in frame.columns]
    if missing:
        raise ToolError(f"Required column(s) {missing} could not be found in the file. Columns: {list(frame.columns)}")

    errors: list[list[str]] = [[] for _ in range(len(frame))]
    notes: list[list[str]] = [[] for _ in range(len(frame))]
    for column in required_columns:
        for position, value in enumerate(frame[column].tolist()):
            if is_blank(value):
                errors[position].append(f"missing {column}")
    for column in numeric_columns or []:
        if column not in frame.columns:
            continue
        original = frame[column]
        converted = pd.to_numeric(original, errors="coerce")
        for position, (raw, num) in enumerate(zip(original.tolist(), converted.tolist())):
            if not is_blank(raw) and pd.isna(num):
                notes[position].append(f"{column} '{raw}' is not a number")
        frame[column] = converted

    frame["is_valid"] = [not e for e in errors]
    frame["validation_errors"] = ["; ".join(e) for e in errors]
    frame["validation_warnings"] = ["; ".join(n) for n in notes]
    invalid = int((~frame["is_valid"]).sum())
    warned = sum(1 for n in notes if n)
    warnings = [f"{warned} row(s) have non-numeric values (kept, value cleared)"] if warned else []
    return ToolResult(
        output=frame,
        message=f"{len(frame) - invalid} valid, {invalid} invalid row(s)",
        metrics={"total_rows": len(frame), "valid_rows": len(frame) - invalid, "invalid_rows": invalid,
                 "rows_with_warnings": warned},
        warnings=warnings,
    )


@tool(category="validation")
def validate_text(
    text: Any, field: str, max_chars: int | None = None, min_chars: int | None = None
) -> ToolResult:
    """Text validation for generated content (length limits for SEO fields etc.)."""
    if is_blank(text):
        return ToolResult(status=StepStatus.FAILED, message=f"{humanize(field)} is empty")
    value = str(text).strip()
    length = len(value)
    problems = []
    if max_chars and length > max_chars:
        problems.append(f"{length} chars exceeds the {max_chars}-char limit")
    if min_chars and length < min_chars:
        problems.append(f"{length} chars is below the {min_chars}-char minimum")
    return ToolResult(
        output=value,
        status=StepStatus.FLAGGED if problems else StepStatus.OK,
        message=f"{humanize(field)}: " + ("; ".join(problems) if problems else f"{length} chars - OK"),
        metrics={"length": length},
    )


__all__ = ["human_join", "humanize", "row_labels"]
