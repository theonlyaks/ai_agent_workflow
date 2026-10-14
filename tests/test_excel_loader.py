from pathlib import Path

import pandas as pd
import pytest

from workflow_agent.core.config import PROJECT_ROOT
from workflow_agent.core.exceptions import ConfigError
from workflow_agent.registry.excel_loader import load_test_questions, load_workflow_definitions, parse_steps

EXCEL = PROJECT_ROOT / "data" / "AI_Agent_Workflow_Assessment.xlsx"


def test_loads_all_ten_workflows():
    definitions = load_workflow_definitions(EXCEL)
    assert [d.workflow_id for d in definitions] == [f"WF{n:03d}" for n in range(1, 11)]
    step_counts = {d.workflow_id: len(d.steps) for d in definitions}
    assert step_counts == {"WF001": 5, "WF002": 5, "WF003": 6, "WF004": 5, "WF005": 5,
                           "WF006": 6, "WF007": 6, "WF008": 6, "WF009": 6, "WF010": 6}


def test_fields_are_parsed():
    wf001 = load_workflow_definitions(EXCEL)[0]
    assert wf001.name == "Inventory Restock Check"
    assert wf001.steps[0] == "Load inventory"
    assert wf001.inputs == ["Product inventory CSV", "minimum stock threshold"]
    assert wf001.tools_required == ["CSV reader", "calculator"]
    assert "current_stock < minimum_stock" in wf001.decision_logic


def test_parse_steps_supports_several_arrow_styles():
    assert parse_steps("load data → check it -> report => done") == ["Load data", "Check it", "Report", "Done"]


def test_loads_test_questions():
    questions = load_test_questions(EXCEL)
    assert len(questions) == 10
    assert questions[4].request == "Where is order ORD-1001?"


def test_missing_columns_raise_config_error(tmp_path: Path):
    bad = tmp_path / "bad.xlsx"
    pd.DataFrame({"Workflow_ID": ["WF001"], "Workflow_Name": ["x"]}).to_excel(bad, sheet_name="Workflows", index=False)
    with pytest.raises(ConfigError, match="missing columns"):
        load_workflow_definitions(bad)


def test_missing_file_raises_config_error(tmp_path: Path):
    with pytest.raises(ConfigError, match="not found"):
        load_workflow_definitions(tmp_path / "nope.xlsx")
