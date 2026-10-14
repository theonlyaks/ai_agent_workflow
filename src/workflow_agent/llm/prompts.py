"""Prompt templates live in prompts/*.md (editable without touching code).

Placeholders use `$name` (string.Template) so JSON braces inside prompts are safe.
Values are rendered to text: tables -> JSON records, dicts/lists -> JSON, None -> "(not provided)".
"""

from __future__ import annotations

import json
from pathlib import Path
from string import Template
from typing import Any

import pandas as pd

from workflow_agent.core.exceptions import ConfigError

MAX_ROWS_IN_PROMPT = 60


def to_prompt_text(value: Any) -> str:
    if value is None:
        return "(not provided)"
    if isinstance(value, str):
        return value
    if isinstance(value, pd.DataFrame):
        frame = value.head(MAX_ROWS_IN_PROMPT)
        text = frame.to_json(orient="records", date_format="iso", force_ascii=False)
        records = json.loads(text)
        note = f"\n(showing {len(frame)} of {len(value)} rows)" if len(value) > len(frame) else ""
        return json.dumps(records, indent=1, ensure_ascii=False) + note
    try:
        return json.dumps(value, indent=1, default=str, ensure_ascii=False)
    except TypeError:
        return str(value)


class PromptLibrary:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self._cache: dict[str, Template] = {}

    def exists(self, name: str) -> bool:
        return (self.directory / f"{name}.md").exists()

    def template(self, name: str) -> Template:
        if name not in self._cache:
            path = self.directory / f"{name}.md"
            if not path.exists():
                raise ConfigError(f"Prompt template not found: {path}")
            self._cache[name] = Template(path.read_text(encoding="utf-8"))
        return self._cache[name]

    def render(self, name: str, variables: dict[str, Any] | None = None) -> str:
        template = self.template(name)
        values = dict(variables or {})
        # Placeholders the caller did not supply render as "(not provided)" instead of "$name"
        for identifier in template.get_identifiers():
            values.setdefault(identifier, None)
        return template.safe_substitute({k: to_prompt_text(v) for k, v in values.items()})
