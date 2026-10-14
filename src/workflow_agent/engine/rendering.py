"""Markdown rendering of an AgentResponse (CLI output, saved results, Streamlit records)."""

from __future__ import annotations

from typing import Any

from workflow_agent.core.models import AgentResponse

STATUS_ICON = {
    "ok": "✅", "flagged": "⚠️", "needs_input": "❓", "escalate": "🔺", "failed": "❌", "skipped": "⏭️",
}
RUN_LABEL = {
    "completed": "✅ Completed",
    "completed_with_flags": "⚠️ Completed with flags",
    "needs_input": "❓ Waiting for your input",
    "escalated": "🔺 Escalated",
    "failed": "❌ Failed",
}
METHOD_LABEL = {"llm_tool_call": "Claude tool calling", "keyword_fallback": "keyword fallback (offline)"}


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        value = f"{value:g}"
    elif isinstance(value, (list, tuple)):
        value = "; ".join(_cell(v) for v in value)
    elif isinstance(value, dict):
        value = ", ".join(f"{k}: {_cell(v)}" for k, v in value.items())
    return str(value).replace("|", "\\|").replace("\n", " ")


def table_markdown(data: dict[str, Any], max_rows: int = 50) -> str:
    columns, rows = data["columns"], data["rows"]
    if not rows:
        return "_No rows._"
    lines = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    lines += ["| " + " | ".join(_cell(row.get(c)) for c in columns) + " |" for row in rows[:max_rows]]
    if data.get("total_rows", len(rows)) > max_rows:
        lines.append(f"\n_Showing {max_rows} of {data['total_rows']} rows._")
    return "\n".join(lines)


def value_markdown(value: Any, indent: int = 0) -> str:
    pad = "  " * indent
    if isinstance(value, dict):
        lines = []
        for key, item in value.items():
            label = key.replace("_", " ").capitalize()
            if isinstance(item, list) and item and all(isinstance(v, dict) for v in item):
                # Markdown tables cannot be nested inside list items -> render as its own block
                lines.append(f"{pad}- **{label}:**\n\n{value_markdown(item)}\n")
            elif isinstance(item, (dict, list)) and item:
                lines.append(f"{pad}- **{label}:**\n{value_markdown(item, indent + 1)}")
            elif isinstance(item, (dict, list)):
                lines.append(f"{pad}- **{label}:** _none_")
            else:
                lines.append(f"{pad}- **{label}:** {_cell(item) if item not in (None, '') else '_not provided_'}")
        return "\n".join(lines)
    if isinstance(value, list):
        if value and all(isinstance(v, dict) for v in value):
            columns = list(dict.fromkeys(k for v in value for k in v))
            return table_markdown({"columns": columns, "rows": value, "total_rows": len(value)})
        return "\n".join(f"{pad}- {_cell(v)}" for v in value)
    return f"{pad}{_cell(value)}"


def section_markdown(section: dict[str, Any]) -> str:
    kind, data = section["kind"], section["data"]
    if kind == "table":
        body = table_markdown(data)
    elif kind in ("record", "list"):
        body = value_markdown(data)
    else:
        body = str(data)
    return f"#### {section['title']}\n\n{body}"


def response_markdown(response: AgentResponse) -> str:
    out = [f"**Request:** {response.request.splitlines()[0] if response.request else ''}", ""]
    if response.workflow_id:
        method = METHOD_LABEL.get(response.routing.get("method", ""), response.routing.get("method", ""))
        out.append(f"**Selected Workflow:** {response.workflow_id} - {response.workflow_name}")
        out.append(f"**Routing:** {method}"
                   + (f" (confidence: {response.routing.get('confidence')})" if response.routing.get("confidence") else "")
                   + (f" - {response.routing.get('reasoning')}" if response.routing.get("reasoning") else ""))
    out.append(f"**Status:** {RUN_LABEL.get(response.status.value, response.status.value)}")

    if len(response.transcript) > 1:
        out += ["", "**Conversation:**"]
        out += [f"> **{m['role'].capitalize()}:** {m['content']}".replace("\n", "\n> ") for m in response.transcript]

    if response.steps:
        out += ["", "### Steps Executed"]
        for step in response.steps:
            tools = ", ".join(f"`{c['tool']}`" for c in step["calls"]) or "-"
            message = f" - {step['message']}" if step.get("message") else ""
            out.append(f"{step['index']}. {STATUS_ICON.get(step['status'], '')} **{step['name']}** [{tools}]{message}")

    if response.question:
        out += ["", "### Question", response.question]
    if response.error:
        out += ["", f"**Error:** {response.error}"]
    if response.summary or response.sections:
        out += ["", "### Result"]
        if response.summary:
            out += [response.summary, ""]
        out += [section_markdown(s) + "\n" for s in response.sections]
    if response.flags:
        out += ["**Flags:**"] + [f"- {f}" for f in response.flags] + [""]
    if response.warnings:
        out += ["**Warnings:**"] + [f"- {w}" for w in response.warnings] + [""]
    if response.duration_ms is not None:
        usage = response.llm_usage or {}
        tokens = f", LLM calls: {usage.get('calls', 0)}, tokens: {usage.get('input_tokens', 0)} in / {usage.get('output_tokens', 0)} out" if usage else ""
        out.append(f"_Run {response.run_id} - {response.duration_ms / 1000:.1f}s{tokens}_")
    return "\n".join(out).strip() + "\n"
