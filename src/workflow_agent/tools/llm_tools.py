"""LLM tools: structured content generation and batch classification (Claude)."""

from __future__ import annotations

from typing import Any

from workflow_agent.core.exceptions import LLMUnavailableError
from workflow_agent.core.models import ToolResult
from workflow_agent.llm.schema import compact_to_json_schema
from workflow_agent.tools.data_tools import as_frame, require_columns
from workflow_agent.tools.registry import ToolContext, tool

SYSTEM_PROMPT = (
    "You are a precise assistant inside a business workflow automation system. "
    "Complete only the task described. Use ONLY the facts provided in the task data - never invent "
    "product attributes, numbers, dates, names or prices. When information is missing, say it was not "
    "provided instead of guessing. Answer in the requested JSON format."
)


def _llm(ctx: ToolContext):
    if ctx.llm is None:
        raise LLMUnavailableError(
            "This step needs Claude, but no LLM is configured (set ANTHROPIC_API_KEY in .env)"
        )
    return ctx.llm


@tool(category="llm")
def llm_generate(
    prompt: str,
    ctx: ToolContext,
    schema: dict[str, Any] | None = None,
    variables: dict[str, Any] | None = None,
    effort: str = "low",
    max_tokens: int = 6000,
) -> ToolResult:
    """Generate structured content with Claude from a prompt template + compact output schema."""
    llm = _llm(ctx)
    text = ctx.prompts.render(prompt, variables)
    data = llm.structured(
        system=SYSTEM_PROMPT,
        prompt=text,
        schema=compact_to_json_schema(schema or {"text": "string"}),
        effort=effort,
        max_tokens=max_tokens,
        tag=prompt,
    )
    return ToolResult(output=data, message=f"Generated {', '.join(data)} ({llm.model})")


@tool(category="llm")
def llm_classify(
    table: Any,
    text_column: str,
    labels: Any,
    output_column: str,
    ctx: ToolContext,
    label_column: str | None = None,
    instructions: str = "",
    label_descriptions: dict[str, str] | None = None,
    batch_size: int = 40,
    effort: str = "low",
) -> ToolResult:
    """Classify every row's text into one of a fixed label set (batched, schema-enforced)."""
    llm = _llm(ctx)
    frame = as_frame(table).copy().reset_index(drop=True)
    require_columns(frame, [text_column], "llm_classify")
    if isinstance(labels, list):
        label_list = [str(label) for label in labels]
    else:
        label_frame = as_frame(labels)
        require_columns(label_frame, [label_column or ""], "llm_classify labels")
        label_list = label_frame[label_column].dropna().astype(str).unique().tolist()

    described = "\n".join(
        f"- {label}: {(label_descriptions or {}).get(label, '')}".rstrip(": ") for label in label_list
    )
    schema = {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"id": {"type": "integer"}, "label": {"type": "string", "enum": label_list}},
                    "required": ["id", "label"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["results"],
        "additionalProperties": False,
    }

    assigned: dict[int, str] = {}
    items = [{"id": i, "text": str(v)} for i, v in enumerate(frame[text_column].tolist())]
    for start in range(0, len(items), batch_size):
        batch = items[start : start + batch_size]
        prompt = ctx.prompts.render("classify", {"instructions": instructions, "labels": described, "items": batch})
        data = llm.structured(system=SYSTEM_PROMPT, prompt=prompt, schema=schema, effort=effort,
                              max_tokens=8000, tag=f"classify:{output_column}")
        valid_ids = {item["id"] for item in batch}
        for result in data.get("results", []):
            if result.get("id") in valid_ids and result.get("label") in label_list:
                assigned[int(result["id"])] = result["label"]

    frame[output_column] = [assigned.get(i, "unclassified") for i in range(len(frame))]
    missing = len(frame) - len(assigned)
    warnings = [f"{missing} row(s) could not be classified and were marked 'unclassified'"] if missing else []
    return ToolResult(
        output=frame,
        message=f"Classified {len(assigned)} of {len(frame)} rows into {len(label_list)} labels",
        metrics=frame[output_column].value_counts().to_dict(),
        warnings=warnings,
    )
