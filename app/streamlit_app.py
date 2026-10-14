"""Streamlit chat UI for the workflow agent.

    streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pandas as pd
import streamlit as st

from workflow_agent.core.config import PROJECT_ROOT, get_settings
from workflow_agent.core.exceptions import ConfigError
from workflow_agent.core.models import AgentResponse
from workflow_agent.engine.agent import WorkflowAgent
from workflow_agent.engine.rendering import METHOD_LABEL, RUN_LABEL, STATUS_ICON, value_markdown

st.set_page_config(page_title="AI Workflow Agent", page_icon="🤖", layout="wide")


@st.cache_resource(show_spinner="Loading workflows from Excel...")
def load_agent() -> WorkflowAgent:
    return WorkflowAgent()


def init_state() -> None:
    st.session_state.setdefault("messages", [])  # [{"role": "user"|"assistant", "content": str, "response": dict}]
    st.session_state.setdefault("pending_run", None)  # run id of a paused run waiting for the user's answer
    st.session_state.setdefault("queued_prompt", None)


def save_upload(uploaded) -> str:
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    target = settings.upload_dir / f"{uuid.uuid4().hex[:8]}_{Path(uploaded.name).name}"
    target.write_bytes(uploaded.getvalue())
    return target.relative_to(PROJECT_ROOT).as_posix()


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------
def render_section(section: dict) -> None:
    st.markdown(f"##### {section['title']}")
    data = section["data"]
    if section["kind"] == "table":
        if data["rows"]:
            st.dataframe(pd.DataFrame(data["rows"], columns=data["columns"]), hide_index=True)
            if data["total_rows"] > len(data["rows"]):
                st.caption(f"Showing {len(data['rows'])} of {data['total_rows']} rows")
        else:
            st.caption("No rows.")
    elif section["kind"] in ("record", "list"):
        st.markdown(value_markdown(data))
    else:
        st.markdown(str(data))


def render_steps(response: AgentResponse, expanded: bool) -> None:
    done = sum(1 for s in response.steps if s["status"] not in ("skipped",))
    with st.expander(f"Steps executed ({done}/{len(response.steps)})", expanded=expanded):
        for step in response.steps:
            icon = STATUS_ICON.get(step["status"], "")
            message = f" — {step['message']}" if step.get("message") else ""
            st.markdown(f"{icon} **{step['index']}. {step['name']}**{message}")
            for call in step["calls"]:
                metrics = ", ".join(f"{k}={v}" for k, v in list(call["metrics"].items())[:4])
                retries = f" · {call['attempts']} attempts" if call["attempts"] > 1 else ""
                st.caption(f"↳ `{call['tool']}` · {call['status']} · {call['duration_ms']:.0f} ms{retries}"
                           + (f" · {metrics}" if metrics else ""))


def render_response(response: AgentResponse, latest: bool, key: str) -> None:
    if response.workflow_id:
        st.markdown(f"**Selected workflow:** `{response.workflow_id}` — {response.workflow_name}")
        routing = response.routing
        details = [METHOD_LABEL.get(routing.get("method", ""), routing.get("method", ""))]
        if routing.get("confidence"):
            details.append(f"confidence: {routing['confidence']}")
        if routing.get("reasoning"):
            details.append(routing["reasoning"])
        st.caption("Routing: " + " · ".join(d for d in details if d))
    st.markdown(f"**Status:** {RUN_LABEL.get(response.status.value, response.status.value)}")

    if response.steps:
        render_steps(response, expanded=latest)
    if response.question:
        st.info(response.question)
    if response.error:
        st.error(response.error)
    if response.summary:
        st.markdown(response.summary)
    for section in response.sections:
        render_section(section)
    if response.flags:
        st.warning("**Flags**\n\n" + "\n".join(f"- {f}" for f in response.flags))
    if response.warnings:
        with st.expander(f"Warnings ({len(response.warnings)})", expanded=False):
            for warning in response.warnings:
                st.markdown(f"- {warning}")
    if response.duration_ms is not None:
        usage = response.llm_usage or {}
        tokens = (f" · LLM calls {usage.get('calls', 0)} · tokens {usage.get('input_tokens', 0)} in / "
                  f"{usage.get('output_tokens', 0)} out") if usage else ""
        st.caption(f"Run `{response.run_id}` · {response.duration_ms / 1000:.1f}s{tokens}")
        st.download_button("Download result (JSON)", response.model_dump_json(indent=2),
                           file_name=f"{response.run_id}.json", mime="application/json", key=f"dl-{key}")


def render_history() -> None:
    messages = st.session_state.messages
    last_assistant = max((i for i, m in enumerate(messages) if m["role"] == "assistant"), default=-1)
    for index, message in enumerate(messages):
        with st.chat_message(message["role"]):
            if message["role"] == "user":
                st.markdown(message["content"])
            else:
                render_response(AgentResponse.model_validate(message["response"]), index == last_assistant, str(index))


# ---------------------------------------------------------------------------
# pages
# ---------------------------------------------------------------------------
def sidebar(agent: WorkflowAgent) -> None:
    with st.sidebar:
        st.header("🤖 Workflow Agent")
        if agent.offline:
            st.warning("**Offline mode** - no ANTHROPIC_API_KEY. Keyword routing; LLM steps are unavailable.")
        else:
            st.success(f"LLM: **{agent.model_name}**")
        st.caption(f"{len(agent.registry.executable())}/{len(agent.registry)} workflows loaded from "
                   f"`{agent.registry.excel_path.name}` + `{agent.registry.config_path.name}`")
        for warning in agent.registry.warnings:
            st.caption(f"⚠️ {warning}")
        col1, col2 = st.columns(2)
        if col1.button("🔄 Reload Excel", help="Re-read the Excel file, YAML bindings and .env"):
            get_settings.cache_clear()
            load_agent.clear()
            st.rerun()
        if col2.button("🧹 New chat"):
            st.session_state.messages = []
            st.session_state.pending_run = None
            st.rerun()

        st.subheader("Excel test questions")
        for question in agent.registry.test_questions:
            if st.button(f"{question.workflow_id}: {question.request}", key=f"tq-{question.workflow_id}",
                         help=question.what_to_check, width="stretch"):
                st.session_state.queued_prompt = question.request
        st.caption("Tip: attach a CSV/XLSX with the 📎 in the chat box for vendor-file or keyword workflows.")


def workflows_page(agent: WorkflowAgent) -> None:
    st.subheader("Workflows loaded from Excel")
    st.caption("Excel = WHAT (definition). YAML binding = HOW (each Excel step -> reusable tools).")
    usage: dict[str, set[str]] = {}
    for wf in agent.registry.all():
        with st.expander(f"{wf.id} — {wf.name}" + ("" if wf.executable else "  (not configured)")):
            d = wf.definition
            st.markdown(f"**Trigger:** {d.trigger}  \n**Inputs:** {'; '.join(d.inputs)}  \n"
                        f"**Decision logic:** {d.decision_logic}  \n**Tools required:** {'; '.join(d.tools_required)}  \n"
                        f"**Expected output:** {d.expected_output}")
            rows = []
            for number, step in enumerate(d.steps, start=1):
                tools = [c.tool for c in wf.binding.steps[number - 1].calls] if wf.binding else []
                for tool_name in tools:
                    usage.setdefault(tool_name, set()).add(wf.id)
                rows.append({"#": number, "Excel step": step, "Tools (from YAML)": ", ".join(tools) or "-"})
            st.dataframe(pd.DataFrame(rows), hide_index=True)
            if wf.binding and wf.binding.params:
                st.markdown("**Business parameters:**")
                st.json(wf.binding.params, expanded=False)

    st.subheader("Tool registry")
    st.dataframe(pd.DataFrame([
        {"tool": s.name, "category": s.category, "description": s.description,
         "used by": ", ".join(sorted(usage.get(s.name, []))) or "-", "reuse": len(usage.get(s.name, []))}
        for s in agent.tools.specs()
    ]), hide_index=True)


def run_log_page(agent: WorkflowAgent) -> None:
    st.subheader("Execution log")
    st.caption(f"Every finished run is appended to `{agent.settings.execution_log_path.name}` "
               "(also the data source for WF010 - Workflow Performance Report).")
    runs = agent.execution_log.recent(100)
    if not runs:
        st.info("No runs yet.")
        return
    st.dataframe(pd.DataFrame([{
        "finished_at": r.get("finished_at", "")[:19], "run_id": r["run_id"], "workflow": r.get("workflow_id"),
        "status": r.get("status"), "duration_s": round((r.get("duration_ms") or 0) / 1000, 2),
        "routing": r.get("routing_method"), "questions_asked": r.get("clarification_rounds"),
        "llm_calls": (r.get("llm_usage") or {}).get("calls", 0), "request": r.get("request"),
    } for r in runs]), hide_index=True)


def handle_prompt(agent: WorkflowAgent, text: str, files: list) -> None:
    attachments = [save_upload(f) for f in files]
    request = text + "".join(f"\n[Attached file: {path}]" for path in attachments)
    shown = text + "".join(f"\n\n📎 `{Path(p).name}`" for p in attachments)
    st.session_state.messages.append({"role": "user", "content": shown})
    with st.spinner("Agent is working..."):
        if st.session_state.pending_run:
            response = agent.resume(st.session_state.pending_run, request)
        else:
            response = agent.start(request)
    st.session_state.pending_run = response.run_id if response.waiting_for_input else None
    st.session_state.messages.append({"role": "assistant", "response": json.loads(response.model_dump_json())})


def main() -> None:
    init_state()
    try:
        agent = load_agent()
    except ConfigError as exc:
        st.error(f"**Workflow configuration error**\n\n```\n{exc}\n```")
        st.stop()

    sidebar(agent)
    chat_tab, workflows_tab, log_tab = st.tabs(["💬 Agent", "📋 Workflows (Excel)", "📈 Run log"])

    prompt = st.chat_input(
        "Answer the question above..." if st.session_state.pending_run else "Ask e.g. 'Which products need restocking?'",
        accept_file="multiple", file_type=["csv", "xlsx", "xls", "json"],
    )
    with chat_tab:
        st.title("AI Workflow Agent")
        st.caption("Describe what you need. The agent picks the matching Excel workflow, runs its steps with "
                   "tools, handles conditions, and shows every step it executed.")
        if prompt or st.session_state.queued_prompt:
            if prompt:
                text, files = prompt.text or "", list(prompt.files or [])
            else:
                text, files = st.session_state.queued_prompt, []
                st.session_state.queued_prompt = None
            if text.strip() or files:
                handle_prompt(agent, text.strip(), files)
                st.rerun()  # re-render so the chat box placeholder reflects the new state
        render_history()
        if st.session_state.pending_run:
            st.info("⏸️ The agent paused and is waiting for your answer (type it below).")
            if st.button("Cancel this request"):
                st.session_state.pending_run = None
                st.rerun()
    with workflows_tab:
        workflows_page(agent)
    with log_tab:
        run_log_page(agent)


main()
