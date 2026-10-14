"""Unit tests for the reusable tools (pure functions, no LLM)."""

import pandas as pd
import pytest

from workflow_agent.core.exceptions import ToolError
from workflow_agent.core.models import StepStatus
from workflow_agent.llm.fake import FakeLLM
from workflow_agent.llm.schema import compact_to_json_schema
from workflow_agent.tools.data_tools import (
    aggregate, assign_label, compare_to_threshold, compute_column, drop_duplicate_rows, join_tables,
    read_table, search_table,
)
from workflow_agent.tools.llm_tools import llm_classify
from workflow_agent.tools.ranking_tools import rank_rows, select_best, skill_match
from workflow_agent.tools.similarity_tools import find_similar_pairs
from workflow_agent.tools.validation_tools import detect_columns, validate_fields, validate_identifier, validate_rows


def test_read_table_errors_are_clear():
    with pytest.raises(ToolError, match="File not found"):
        read_table("data/samples/missing.csv")
    with pytest.raises(ToolError, match="Unsupported file format"):
        read_table("pyproject.toml")


def test_compare_to_threshold_is_strict_and_reports_bad_values():
    frame = pd.DataFrame({"sku": ["A", "B", "C"], "stock": [5, 10, None], "minimum": [10, 10, 10]})
    result = compare_to_threshold(frame, "stock", "<", threshold_column="minimum", flag_column="low")
    assert result.output["low"].tolist() == [True, False, False]  # equal is NOT below
    assert result.metrics["rows_flagged"] == 1
    assert "C" in result.warnings[0]


def test_compare_to_threshold_global_value_and_flag_status():
    frame = pd.DataFrame({"x": [5, 50]})
    result = compare_to_threshold(frame, "x", ">", threshold_value=10, mark_flagged=True)
    assert result.status == StepStatus.FLAGGED and result.output["flagged"].tolist() == [False, True]


def test_compute_column_with_variables():
    frame = pd.DataFrame({"a": [1, 2]})
    assert compute_column(frame, "b", "a * @m + 0.4", variables={"m": 3}, decimals=0).output["b"].tolist() == [3, 6]


def test_join_tables_reports_unmatched_keys():
    left = pd.DataFrame({"sku": ["a-1", "B-2"], "price": [1, 2]})
    right = pd.DataFrame({"sku": [" A-1 ", "C-3"], "vendor": [1, 3]})
    result = join_tables(left, right, key="sku", how="outer", indicator_column="match")
    assert sorted(result.output["match"]) == ["matched", "only_in_left", "only_in_right"]


def test_assign_label_first_matching_rule_wins():
    frame = pd.DataFrame({"v": [5, 50, 500]})
    rules = [{"when": "v > 100", "label": "high"}, {"when": "v > 10", "label": "medium"}]
    assert assign_label(frame, "level", rules, default="low").output["level"].tolist() == ["low", "medium", "high"]


def test_aggregate_and_dedupe():
    frame = pd.DataFrame({"k": ["x", "X ", "y"], "v": [1, 2, 3]})
    assert drop_duplicate_rows(frame, ["k"]).metrics["duplicates_removed"] == 1
    grouped = aggregate(pd.DataFrame({"g": ["a", "a", "b"], "v": [1, 3, 5]}), "g", {"avg": ["v", "mean"]}).output
    assert grouped.set_index("g")["avg"].to_dict() == {"a": 2, "b": 5}


def test_search_table_requires_all_query_words():
    frame = pd.DataFrame({"name": ["Wool Scarf", "Rain Jacket"], "tags": ["new collection", "core collection"]})
    assert search_table(frame, "the new collection", ["name", "tags"]).output["name"].tolist() == ["Wool Scarf"]


def test_validate_fields_asks_for_missing_required():
    result = validate_fields({"goal": "sales", "start": ""}, required=["goal", "start"], recommended=["audience"])
    assert result.status == StepStatus.NEEDS_INPUT and result.needs == ["start"]
    ok = validate_fields({"goal": "sales", "start": "2026-11-01"}, required=["goal", "start"], recommended=["audience"])
    assert ok.status == StepStatus.OK and ok.output["missing_recommended"] == ["audience"]


def test_validate_identifier():
    patterns = {"order_id": r"^ORD-\d{4,}$", "email": r"^[\w.+-]+@[\w-]+\.[\w.-]+$"}
    assert validate_identifier("ord-1001", patterns, normalize={"order_id": "upper"}).output == {"type": "order_id", "value": "ORD-1001"}
    assert validate_identifier("12345", patterns).status == StepStatus.NEEDS_INPUT
    assert validate_identifier(None, patterns).status == StepStatus.NEEDS_INPUT


def test_detect_columns_and_validate_rows():
    frame = pd.DataFrame({" Item Code ": ["A", None], "Product Title": ["x", "y"], "Colour": ["red", "blue"]})
    mapping = detect_columns(frame, {"sku": ["item code"], "product_name": ["product title"], "color": ["colour"]}).output
    assert mapping == {" Item Code ": "sku", "Product Title": "product_name", "Colour": "color"}
    validated = validate_rows(frame.rename(columns=mapping), ["sku", "product_name"]).output
    assert validated["is_valid"].tolist() == [True, False]
    assert validated["validation_errors"].tolist()[1] == "missing sku"


def test_similar_pairs_ignore_variants():
    frame = pd.DataFrame({
        "name": ["linen shirt", "linen shirt", "running sneakers", "running sneaker"],
        "color": ["white", "navy", "black", "black"], "size": ["m", "l", "42", "42"],
    })
    pairs = find_similar_pairs(frame, "name", ["color", "size"], min_name_score=85, min_attribute_match=0.75).output
    assert pairs[["row_a", "row_b"]].values.tolist() == [[2, 3]]  # the white/navy shirt variant is not a duplicate


def test_ranking_and_escalation():
    staff = pd.DataFrame({"name": ["a", "b"], "skills": ["python;sql", "react"], "free": [0.2, 0.9]})
    matched = skill_match(staff, ["python", "sql"]).output
    ranked = rank_rows(matched, {"skill_match": 0.5, "free": 0.5}).output
    assert ranked.iloc[0]["name"] == "a"
    assert select_best(ranked, where="skill_match >= 0.5").output["selected"]["name"] == "a"
    escalated = select_best(ranked, where="skill_match >= 0.5 and free > 0.5")
    assert escalated.status == StepStatus.ESCALATE


def test_llm_classify_enforces_label_set(tool_ctx):
    def responder(prompt, schema):
        return {"results": [{"id": 0, "label": "buy"}, {"id": 1, "label": "not-a-label"}]}

    tool_ctx.llm = FakeLLM(responses={"classify:intent": responder})
    frame = pd.DataFrame({"keyword": ["buy shoes", "what is wool"]})
    result = llm_classify(frame, "keyword", ["buy", "learn"], "intent", ctx=tool_ctx)
    assert result.output["intent"].tolist() == ["buy", "unclassified"]
    assert result.warnings


def test_compact_schema():
    schema = compact_to_json_schema({"title": "string | max 60 chars", "tags": ["string"], "kind": {"enum": ["a", "b"]}})
    assert schema["required"] == ["title", "tags", "kind"] and schema["additionalProperties"] is False
    assert schema["properties"]["title"] == {"type": "string", "description": "max 60 chars"}
    assert schema["properties"]["kind"]["enum"] == ["a", "b"]


def test_select_columns_custom_sort_order():
    from workflow_agent.tools.data_tools import select_columns

    frame = pd.DataFrame({"k": ["a", "b", "c", "d"], "priority": ["Low", "High", "Medium", "High"], "v": [1, 2, 3, 4]})
    result = select_columns(frame, sort_by=["priority", "v"], ascending=[True, False],
                            custom_order={"priority": ["High", "Medium", "Low"]}).output
    assert result["k"].tolist() == ["d", "b", "c", "a"]
