"""Reads workflow definitions (and test questions) from the Excel source of truth."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd

from workflow_agent.core.exceptions import ConfigError
from workflow_agent.core.models import TestQuestion, WorkflowDefinition

logger = logging.getLogger(__name__)

WORKFLOW_SHEET = "Workflows"
TEST_SHEET = "Test_Questions"
REQUIRED_COLUMNS = [
    "Workflow_ID",
    "Workflow_Name",
    "Trigger",
    "Inputs",
    "Steps",
    "Decision_Logic",
    "Tools_Required",
    "Expected_Output",
]
_STEP_SEPARATOR = re.compile(r"\s*(?:→|->|=>|\n)\s*")
_LIST_SEPARATOR = re.compile(r"\s*;\s*")


def _clean(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _split(text: str, pattern: re.Pattern[str]) -> list[str]:
    return [part.strip() for part in pattern.split(text) if part and part.strip()]


def _capitalize(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


def parse_steps(text: str) -> list[str]:
    """'Load inventory → compare stock' -> ['Load inventory', 'Compare stock']"""
    return [_capitalize(step) for step in _split(text, _STEP_SEPARATOR)]


def load_workflow_definitions(path: Path) -> list[WorkflowDefinition]:
    if not path.exists():
        raise ConfigError(f"Workflow Excel file not found: {path}")
    try:
        frame = pd.read_excel(path, sheet_name=WORKFLOW_SHEET, dtype=str)
    except ValueError as exc:  # missing sheet
        raise ConfigError(f"Excel file {path.name} has no '{WORKFLOW_SHEET}' sheet") from exc

    frame.columns = [str(c).strip() for c in frame.columns]
    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise ConfigError(f"Excel sheet '{WORKFLOW_SHEET}' is missing columns: {missing}")

    definitions: list[WorkflowDefinition] = []
    seen: set[str] = set()
    for row_number, row in enumerate(frame.to_dict(orient="records"), start=2):
        workflow_id = _clean(row["Workflow_ID"])
        if not workflow_id:
            continue  # blank line in the sheet
        if workflow_id in seen:
            raise ConfigError(f"Duplicate Workflow_ID '{workflow_id}' in Excel row {row_number}")
        seen.add(workflow_id)

        steps = parse_steps(_clean(row["Steps"]))
        if not steps:
            raise ConfigError(f"Workflow {workflow_id} (row {row_number}) has no steps")

        definitions.append(
            WorkflowDefinition(
                workflow_id=workflow_id,
                name=_clean(row["Workflow_Name"]),
                trigger=_clean(row["Trigger"]),
                inputs=_split(_clean(row["Inputs"]), _LIST_SEPARATOR),
                steps=steps,
                decision_logic=_clean(row["Decision_Logic"]),
                tools_required=_split(_clean(row["Tools_Required"]), _LIST_SEPARATOR),
                expected_output=_clean(row["Expected_Output"]),
            )
        )

    logger.info("Loaded %d workflow definitions from %s", len(definitions), path.name)
    return definitions


def load_test_questions(path: Path) -> list[TestQuestion]:
    """Optional sheet - returns [] when it does not exist."""
    try:
        frame = pd.read_excel(path, sheet_name=TEST_SHEET, dtype=str)
    except (ValueError, FileNotFoundError):
        return []
    frame.columns = [str(c).strip() for c in frame.columns]
    questions = []
    for row in frame.to_dict(orient="records"):
        workflow_id, request = _clean(row.get("Workflow_ID")), _clean(row.get("Test_Request"))
        if workflow_id and request:
            questions.append(
                TestQuestion(
                    workflow_id=workflow_id,
                    request=request,
                    what_to_check=_clean(row.get("What_To_Check")),
                )
            )
    return questions
