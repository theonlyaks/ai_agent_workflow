"""Compact output-schema syntax for YAML -> JSON Schema for Claude structured outputs.

    seo_title: "string | SEO title, max 60 characters"
    kpis: ["string"]
    intent: {enum: [informational, commercial]}
    channels:
      - channel: string
        rationale: string

Every object gets `additionalProperties: false` and all properties required, which is
what structured outputs expect. This lets a new LLM workflow define its output shape in
YAML without writing a Python model.
"""

from __future__ import annotations

from typing import Any

_SCALARS = {"string", "integer", "number", "boolean"}


def compact_to_json_schema(spec: Any) -> dict[str, Any]:
    if isinstance(spec, str):
        type_name, _, description = (part.strip() for part in spec.partition("|"))
        if type_name not in _SCALARS:
            raise ValueError(f"Unknown schema type '{type_name}' (use one of {sorted(_SCALARS)})")
        schema: dict[str, Any] = {"type": type_name}
        if description:
            schema["description"] = description
        return schema
    if isinstance(spec, list):
        if len(spec) != 1:
            raise ValueError("Array schema must contain exactly one item spec, e.g. ['string']")
        return {"type": "array", "items": compact_to_json_schema(spec[0])}
    if isinstance(spec, dict):
        if set(spec) == {"enum"}:
            return {"type": "string", "enum": [str(v) for v in spec["enum"]]}
        properties = {key: compact_to_json_schema(value) for key, value in spec.items()}
        return {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        }
    raise ValueError(f"Unsupported schema spec: {spec!r}")


def nullable(schema: dict[str, Any]) -> dict[str, Any]:
    return {"anyOf": [schema, {"type": "null"}]}
