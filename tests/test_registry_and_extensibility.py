"""Registry validation + the key architecture claim: an 11th workflow needs no Python code."""

from pathlib import Path

import pandas as pd
import pytest
import yaml

from workflow_agent.core.config import PROJECT_ROOT
from workflow_agent.core.exceptions import ConfigError
from workflow_agent.core.models import RunStatus
from workflow_agent.engine.agent import WorkflowAgent
from workflow_agent.llm.prompts import PromptLibrary
from workflow_agent.registry.workflow_registry import WorkflowRegistry

EXCEL = PROJECT_ROOT / "data" / "AI_Agent_Workflow_Assessment.xlsx"
CONFIG = PROJECT_ROOT / "config" / "workflows.yaml"
PROMPTS = PromptLibrary(PROJECT_ROOT / "prompts")
EXAMPLE = PROJECT_ROOT / "examples" / "wf011_low_margin"


def _copy_config(tmp_path: Path, mutate) -> Path:
    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    mutate(data["workflows"])
    path = tmp_path / "workflows.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def test_all_ten_workflows_are_executable(tools):
    registry = WorkflowRegistry.load(EXCEL, CONFIG, tools, PROMPTS)
    assert len(registry.executable()) == 10
    assert registry.warnings == []
    for wf in registry.executable():
        assert len(wf.binding.steps) == len(wf.definition.steps)


def test_tools_are_reused_across_workflows(tools):
    registry = WorkflowRegistry.load(EXCEL, CONFIG, tools, PROMPTS)
    users: dict[str, set] = {}
    for wf in registry.executable():
        for step in wf.binding.steps:
            for call in step.calls:
                users.setdefault(call.tool, set()).add(wf.id)
    assert len(users["read_table"]) >= 7
    assert len(users["llm_generate"]) >= 4
    assert len(users["filter_rows"]) >= 5


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda w: w["WF001"]["steps"].pop(), "YAML has 4 steps but the Excel defines 5"),
        (lambda w: w["WF001"]["steps"][0].update(tool="does_not_exist"), "unknown tool 'does_not_exist'"),
        (lambda w: w["WF001"]["steps"][0]["args"].update(bogus=1), "has no argument 'bogus'"),
        (lambda w: w["WF001"]["steps"][2]["args"].update(table="$nope"), "'$nope' is not defined"),
        (lambda w: w["WF001"]["steps"][0]["args"].update(path="$inputs.missing"), "unknown input"),
    ],
)
def test_invalid_bindings_fail_fast(tmp_path, tools, mutate, message):
    config = _copy_config(tmp_path, mutate)
    with pytest.raises(ConfigError, match=message.replace("$", r"\$").replace("(", r"\(")):
        WorkflowRegistry.load(EXCEL, config, tools, PROMPTS)


def test_excel_row_without_binding_is_listed_but_not_executable(tmp_path, tools):
    config = _copy_config(tmp_path, lambda w: w.pop("WF010"))
    registry = WorkflowRegistry.load(EXCEL, config, tools, PROMPTS)
    assert len(registry) == 10 and len(registry.executable()) == 9
    assert any("WF010" in w for w in registry.warnings)


def test_eleventh_workflow_needs_only_an_excel_row_and_yaml(tmp_path, settings):
    """Add WF011 exactly as documented in examples/wf011_low_margin - no Python changes."""
    row = yaml.safe_load((EXAMPLE / "excel_row.yaml").read_text(encoding="utf-8"))
    workflows = pd.read_excel(EXCEL, sheet_name="Workflows")
    tests = pd.read_excel(EXCEL, sheet_name="Test_Questions")
    excel = tmp_path / "workflows.xlsx"
    with pd.ExcelWriter(excel) as writer:
        pd.concat([workflows, pd.DataFrame([row])], ignore_index=True).to_excel(writer, sheet_name="Workflows", index=False)
        tests.to_excel(writer, sheet_name="Test_Questions", index=False)

    binding = yaml.safe_load((EXAMPLE / "binding.yaml").read_text(encoding="utf-8"))
    config = _copy_config(tmp_path, lambda w: w.update(binding))

    agent = WorkflowAgent(settings=settings.model_copy(update={"workflow_excel_path": excel,
                                                                "workflow_config_path": config}), llm=None)
    assert len(agent.registry.executable()) == 11

    response = agent.start("Which products have a low profit margin?")
    assert response.workflow_id == "WF011"
    assert response.status == RunStatus.COMPLETED_WITH_FLAGS
    flagged = {r["sku"] for r in response.sections[0]["data"]["rows"]}
    assert flagged == {"SKU-1007", "SKU-1010"}  # margins 53.9% and 36.4%; everything else >= 55%
