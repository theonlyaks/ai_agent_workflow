"""Workflow selection (LLM tool calling + offline fallback) and graph-level condition handling."""

import pytest

from workflow_agent.core.exceptions import LLMError
from workflow_agent.core.models import RunStatus
from workflow_agent.llm.client import ToolCallReply
from workflow_agent.llm.fake import FakeLLM


def test_keyword_fallback_routes_every_excel_test_question(offline_agent):
    for question in offline_agent.registry.test_questions:
        decision = offline_agent.router.route(question.request)
        assert decision.workflow_id == question.workflow_id, question.request
        assert decision.method == "keyword_fallback"


@pytest.mark.parametrize("request_text", ["What's the weather in Paris tomorrow?", "hello"])
def test_out_of_scope_requests_get_a_clarifying_question(offline_agent, request_text):
    response = offline_agent.start(request_text)
    assert response.status == RunStatus.NEEDS_INPUT and response.workflow_id is None
    assert "I can help with" in response.question


def test_llm_router_tools_are_generated_from_excel(make_agent):
    agent = make_agent(llm=FakeLLM())
    tools = {t["name"]: t for t in agent.router.build_tools()}
    assert len(tools) == 11  # 10 workflows + ask_clarification
    wf005 = tools["run_wf005"]
    assert "Customer Order Status" in wf005["description"] and "If no order is found" in wf005["description"]
    assert "identifier" in wf005["input_schema"]["properties"]


def test_llm_tool_call_selects_workflow_and_extracts_inputs(make_agent):
    def router(messages, tools):
        return ToolCallReply("run_wf005", {"routing_reason": "Order lookup", "confidence": "high",
                                           "identifier": "ORD-1003"})

    response = make_agent(llm=FakeLLM(router=router)).start("hey, did my sneakers order ORD-1003 arrive?")
    assert response.routing["method"] == "llm_tool_call" and response.routing["confidence"] == "high"
    assert response.status == RunStatus.COMPLETED
    assert response.sections[0]["data"]["rows"][0]["shipment_status"] == "Delivered"


def test_llm_clarification_tool(make_agent):
    def router(messages, tools):
        return ToolCallReply("ask_clarification", {"question": "Prices or stock?", "reason": "ambiguous"})

    response = make_agent(llm=FakeLLM(router=router)).start("check the products")
    assert response.status == RunStatus.NEEDS_INPUT and response.question == "Prices or stock?"


def test_llm_outage_falls_back_to_keyword_routing(make_agent):
    def router(messages, tools):
        raise LLMError("Could not reach the Claude API")

    response = make_agent(llm=FakeLLM(router=router)).start("Which products need restocking?")
    assert response.workflow_id == "WF001" and response.status == RunStatus.COMPLETED
    assert response.routing["method"] == "keyword_fallback"
    assert "LLM unavailable" in response.routing["reasoning"]


def test_clarification_loop_is_bounded(make_agent):
    agent = make_agent(max_clarification_rounds=2)
    response = agent.start("Where is order ORD-9999?")
    for _ in range(3):
        if not response.waiting_for_input:
            break
        response = agent.resume(response.run_id, "ORD-8888")  # keeps giving unknown orders
    assert response.status == RunStatus.FAILED
    assert "still missing" in response.error


def test_completed_runs_are_written_to_the_execution_log(offline_agent):
    offline_agent.start("Which products need restocking?")
    records = offline_agent.execution_log.recent()
    assert records[0]["workflow_id"] == "WF001" and records[0]["status"] == "completed"
    assert len(records[0]["steps"]) == 5
