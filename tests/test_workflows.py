"""End-to-end tests of all 10 workflows through the full agent (router -> graph -> executor -> tools).

Deterministic workflows run fully offline. LLM steps use FakeLLM with canned, schema-valid answers,
so the tests check the orchestration, decision logic and condition handling - not Claude's prose.
"""

import re
from pathlib import Path

from conftest import rows, section

from workflow_agent.core.models import RunStatus
from workflow_agent.llm.fake import FakeLLM


# --- WF001 Inventory Restock --------------------------------------------------
def test_wf001_restock_list(offline_agent):
    response = offline_agent.start("Which products need restocking?")
    assert response.workflow_id == "WF001" and response.status == RunStatus.COMPLETED
    restock = {r["sku"]: r for r in rows(response, "Products requiring restock")}
    assert set(restock) == {"SKU-1002", "SKU-1004", "SKU-1006", "SKU-1007", "SKU-1010", "SKU-1012", "SKU-1015"}
    assert "SKU-1008" not in restock  # stock == threshold is not "below"
    assert restock["SKU-1002"]["suggested_reorder_qty"] == 62  # 40 * 2 - 18
    assert any("SKU-1016" in w for w in response.warnings)  # missing stock value reported
    assert [s["status"] for s in response.steps] == ["ok"] * 5


def test_wf001_global_threshold_from_request(offline_agent):
    response = offline_agent.start("Which products have fewer than 10 units in stock?")
    assert response.workflow_id == "WF001" and response.inputs["min_stock_threshold"] == 10
    skus = {r["sku"] for r in rows(response, "Products requiring restock")}
    assert skus == {"SKU-1004", "SKU-1007", "SKU-1010", "SKU-1015"}


# --- WF002 Price Validation ---------------------------------------------------
def test_wf002_flags_price_exceptions(offline_agent):
    response = offline_agent.start("Find products where vendor price differs by more than 10%.")
    assert response.workflow_id == "WF002" and response.status == RunStatus.COMPLETED_WITH_FLAGS
    exceptions = {r["sku"] for r in rows(response, "Price exceptions")}
    assert exceptions == {"SKU-1010", "SKU-1003", "SKU-1007", "SKU-2003", "SKU-1013"}
    assert "SKU-1005" not in exceptions  # exactly 10% is not "more than"
    unmatched = {r["sku"]: r["match_status"] for r in rows(response, "SKUs that could not be matched")}
    assert unmatched == {"SKU-1016": "missing_from_vendor_list", "SKU-3001": "missing_from_internal_catalog"}


def test_wf002_threshold_override(offline_agent):
    response = offline_agent.start("Validate prices and flag vendor prices more than 20% off")
    assert {r["sku"] for r in rows(response, "Price exceptions")} == {"SKU-1010"}


# --- WF003 Vendor File Processing ---------------------------------------------
def test_wf003_cleans_vendor_file(offline_agent, settings):
    response = offline_agent.start("Process this vendor spreadsheet and show invalid rows.")
    assert response.workflow_id == "WF003" and response.status == RunStatus.COMPLETED
    summary = section(response, "Validation summary")["data"]
    assert (summary["total_rows"], summary["valid_rows"], summary["invalid_rows"]) == (12, 9, 3)
    assert summary["columns_detected"][" Item Code "] == "sku"
    assert (settings.output_dir.parent / summary["cleaned_file"]).exists()
    assert any("default" in w for w in response.warnings)  # tells the user the sample file was used


def test_wf003_missing_file_fails_gracefully(offline_agent):
    response = offline_agent.start("Process the vendor file [Attached file: data/uploads/nope.xlsx]")
    assert response.status == RunStatus.FAILED and "File not found" in response.error
    assert response.steps[0]["status"] == "failed" and response.steps[1]["status"] == "skipped"


# --- WF004 Product Description -------------------------------------------------
def test_wf004_asks_for_product_then_generates(make_agent):
    llm = FakeLLM(responses={
        "extract_inputs": {"product_name": "Merino Wool Turtleneck", "material": "merino wool"},
        "product_content": lambda prompt, schema: {k: "x" * 70 if k == "seo_title" else "Generated"
                                                    for k in schema["properties"]},
    })
    agent = make_agent(llm=llm)
    first = agent.start("Generate SEO content for this product.")
    assert first.workflow_id == "WF004" and first.status == RunStatus.NEEDS_INPUT
    assert "Which product" in first.question

    final = agent.resume(first.run_id, "The Merino Wool Turtleneck, merino wool")
    assert final.status == RunStatus.COMPLETED_WITH_FLAGS  # the 70-char SEO title breaks the 60-char limit
    content = section(final, "Generated product content")["data"]
    assert content["sku"] == "SKU-2001"  # enriched from the catalog by fuzzy name match
    assert "attributes" in content["missing_information"]  # missing info is marked, not invented
    assert any("seo title" in f for f in final.flags)


# --- WF005 Order Status ---------------------------------------------------------
def test_wf005_order_found(offline_agent):
    response = offline_agent.start("Where is order ORD-1001?")
    row = rows(response, "Order status")[0]
    assert (row["order_status"], row["shipment_status"], row["carrier"]) == ("Shipped", "In transit", "UPS")


def test_wf005_missing_order_asks_for_another_identifier(offline_agent):
    first = offline_agent.start("Where is order ORD-9999?")
    assert first.status == RunStatus.NEEDS_INPUT and "ORD-9999" in first.question
    final = offline_agent.resume(first.run_id, "try jane.doe@example.com")
    assert final.status == RunStatus.COMPLETED
    assert {r["order_id"] for r in rows(final, "Order status")} == {"ORD-1001", "ORD-1002"}


def test_wf005_transient_api_errors_are_retried_then_fail_cleanly(make_agent):
    agent = make_agent(mock_api_failure_rate=1.0)
    response = agent.start("Where is order ORD-1001?")
    assert response.status == RunStatus.FAILED
    assert "gave up after 3 attempts" in response.error
    assert response.steps[1]["calls"][0]["attempts"] == 3


# --- WF006 Duplicates -----------------------------------------------------------------
def test_wf006_duplicate_groups(offline_agent):
    response = offline_agent.start("Find likely duplicate products in the catalog.")
    groups = {r["sku"]: r["confidence"] for r in rows(response, "Duplicate groups")}
    assert groups["SKU-1001, sku-1001"].startswith("Definite")
    assert groups["SKU-1003, SKU-1203"] == "Possible duplicate - high confidence"
    assert groups["SKU-1007, SKU-1077"] == "Possible duplicate - medium confidence"
    assert not any("SKU-1112" in skus for skus in groups)  # colour/size variant is not a duplicate


# --- WF007 Campaign Brief ---------------------------------------------------------
def test_wf007_requires_goal_and_dates_before_generating(make_agent):
    llm = FakeLLM(responses={"extract_inputs": {
        "campaign_goal": "Grow online sales 25%", "start_date": "2026-11-01", "end_date": "2026-11-30",
        "products": "new collection", "target_audience": None, "promotion": None,
    }})
    agent = make_agent(llm=llm)
    first = agent.start("Create a campaign brief for the new collection.")
    assert first.workflow_id == "WF007" and first.status == RunStatus.NEEDS_INPUT
    assert "campaign goal, start date and end date" in first.question
    assert not any(c.startswith("campaign_") for c in llm.calls)  # nothing generated before validation passed

    final = agent.resume(first.run_id, "Goal: grow online sales 25%, from 1 to 30 November 2026")
    assert final.status == RunStatus.COMPLETED
    featured = {r["sku"] for r in rows(final, "Featured products")}
    assert featured == {"SKU-2001", "SKU-2002", "SKU-2003", "SKU-2004", "SKU-2005", "SKU-2006"}
    assert section(final, "Campaign brief")["data"]["start_date"] == "2026-11-01"


# --- WF008 Keywords ---------------------------------------------------------------------
def _keyword_classifier(prompt, schema):
    allowed = schema["properties"]["results"]["items"]["properties"]["label"]["enum"]
    ids = [int(i) for i in re.findall(r'"id": (\d+)', prompt)]
    return {"results": [{"id": i, "label": allowed[0]} for i in ids]}


def test_wf008_keyword_report(make_agent):
    agent = make_agent(llm=FakeLLM(responses={"classify:intent": _keyword_classifier,
                                              "classify:category": _keyword_classifier}))
    response = agent.start("Classify these keywords and map them to pages.")
    assert response.workflow_id == "WF008" and response.status == RunStatus.COMPLETED
    report = rows(response, "Keyword report")
    assert len(report) == 22  # 24 rows - 2 duplicates
    assert all(r["intent"] == "informational" for r in report)
    assert all(r["recommended_target_page"].startswith("/journal/") for r in report)  # informational -> guide page
    assert Path(section(response, "Exported file")["data"]).name.endswith("keyword_report.csv")


def test_wf008_without_llm_fails_with_clear_message(offline_agent):
    response = offline_agent.start("Classify these keywords and map them to pages.")
    assert response.status == RunStatus.FAILED and "ANTHROPIC_API_KEY" in response.error


# --- WF009 Task Assignment ------------------------------------------------------------
def _requirements(task_id, skills, hours):
    return {"task_id": task_id, "title": "Task", "required_skills": skills, "estimated_hours": hours,
            "priority": "urgent", "deadline": "2026-10-16"}


def test_wf009_asks_for_task_then_assigns(make_agent):
    llm = FakeLLM(responses={
        "extract_inputs": {"task": "T-201"},
        "task_requirements": _requirements("T-201", ["python", "fastapi", "postgresql"], 6),
    })
    agent = make_agent(llm=llm)
    first = agent.start("Assign this urgent task to the best available developer.")
    assert first.workflow_id == "WF009" and first.status == RunStatus.NEEDS_INPUT
    assert "T-201" in first.question  # backlog options are offered

    final = agent.resume(first.run_id, "T-201")
    assert final.status == RunStatus.COMPLETED
    assert section(final, "Recommended assignment")["data"]["recommended_employee"] == "Aarav Mehta"


def test_wf009_escalates_when_nobody_qualifies(make_agent):
    llm = FakeLLM(responses={"task_requirements": _requirements("T-204", ["swift"], 8)})
    response = make_agent(llm=llm).start("Urgent: assign task T-204 to the best available developer")
    assert response.status == RunStatus.ESCALATED
    assert response.sections[0]["title"] == "Escalation"
    assert response.steps[4]["status"] == "escalate" and response.steps[5]["status"] == "skipped"


# --- WF010 Performance Report ------------------------------------------------------------
def test_wf010_flags_failing_and_slow_workflows(offline_agent):
    response = offline_agent.start("Which workflows are failing most often?")
    assert response.workflow_id == "WF010" and response.status == RunStatus.COMPLETED_WITH_FLAGS
    performance = rows(response, "Workflow performance")
    health = {r["workflow_id"]: r["health"] for r in performance}
    rates = [r["failure_rate_pct"] for r in performance]
    assert rates == sorted(rates, reverse=True)  # "failing most often" first
    assert {performance[0]["workflow_id"], performance[1]["workflow_id"]} == {"WF003", "WF005"}
    assert health["WF005"].startswith("FLAG") and health["WF003"].startswith("FLAG")
    assert "slow" in health["WF008"]
    assert health["WF001"] == "Healthy"
    # the optional LLM recommendation step failed (offline) but the report still completed
    assert any("optional" in w for w in response.warnings)
