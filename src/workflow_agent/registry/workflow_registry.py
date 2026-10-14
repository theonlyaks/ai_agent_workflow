"""Workflow registry = Excel definitions (WHAT) joined with YAML bindings (HOW).

Everything is validated at startup ("fail fast"): step counts must match the Excel
steps, every tool must exist and accept the configured arguments, every `$reference`
must point at something defined earlier, and every prompt template must exist.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Iterator

import yaml
from pydantic import ValidationError

from workflow_agent.core.exceptions import ConfigError, WorkflowNotFoundError
from workflow_agent.core.models import TestQuestion, Workflow, WorkflowBinding, WorkflowDefinition
from workflow_agent.llm.prompts import PromptLibrary
from workflow_agent.llm.schema import compact_to_json_schema
from workflow_agent.registry.excel_loader import load_test_questions, load_workflow_definitions
from workflow_agent.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

RESERVED_ROOTS = {"inputs", "params", "metrics", "run"}


def iter_refs(value: Any) -> Iterator[str]:
    """Yield every `$reference` string inside a (nested) YAML value."""
    if isinstance(value, str) and value.startswith("$"):
        yield value[1:]
    elif isinstance(value, dict):
        for item in value.values():
            yield from iter_refs(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_refs(item)


def validate_binding(
    definition: WorkflowDefinition,
    binding: WorkflowBinding,
    tools: ToolRegistry,
    prompts: PromptLibrary | None,
) -> list[str]:
    wf = definition.workflow_id
    errors: list[str] = []
    if len(binding.steps) != len(definition.steps):
        errors.append(
            f"{wf}: YAML has {len(binding.steps)} steps but the Excel defines {len(definition.steps)} "
            f"({definition.steps})"
        )

    input_names = {i.name for i in binding.inputs}
    defined: set[str] = set()
    for step_number, step in enumerate(binding.steps, start=1):
        for call in step.calls:
            where = f"{wf} step {step_number} ({call.tool})"
            errors += [f"{where}: {e}" for e in tools.validate_args(call.tool, call.args)]
            for ref in iter_refs(call.args):
                root, _, rest = ref.partition(".")
                field = rest.split(".")[0]
                if root == "inputs" and field and field not in input_names:
                    errors.append(f"{where}: unknown input '${ref}'")
                elif root == "params" and field and field not in binding.params:
                    errors.append(f"{where}: unknown param '${ref}'")
                elif root == "metrics" and field not in defined:
                    errors.append(f"{where}: '${ref}' refers to a step result that is not defined yet")
                elif root not in RESERVED_ROOTS and root not in defined:
                    errors.append(f"{where}: '${ref}' is not defined by an earlier step")
            if call.tool == "llm_generate":
                prompt = call.args.get("prompt")
                if prompts is not None and isinstance(prompt, str) and not prompts.exists(prompt):
                    errors.append(f"{where}: prompt template prompts/{prompt}.md not found")
                try:
                    compact_to_json_schema(call.args.get("schema") or {"text": "string"})
                except ValueError as exc:
                    errors.append(f"{where}: invalid schema - {exc}")
            if call.save_as:
                defined.add(call.save_as)

    for section in binding.output:
        if section.source not in defined:
            errors.append(f"{wf}: output section '{section.title}' uses undefined source '{section.source}'")
    return errors


class WorkflowRegistry:
    def __init__(
        self,
        workflows: dict[str, Workflow],
        test_questions: list[TestQuestion],
        warnings: list[str],
        excel_path: Path,
        config_path: Path,
    ) -> None:
        self._workflows = workflows
        self.test_questions = test_questions
        self.warnings = warnings
        self.excel_path = excel_path
        self.config_path = config_path

    @classmethod
    def load(
        cls,
        excel_path: Path,
        config_path: Path,
        tools: ToolRegistry,
        prompts: PromptLibrary | None = None,
    ) -> "WorkflowRegistry":
        definitions = load_workflow_definitions(excel_path)
        if not config_path.exists():
            raise ConfigError(f"Workflow binding file not found: {config_path}")
        try:
            raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise ConfigError(f"{config_path.name} is not valid YAML: {exc}") from exc
        bindings_raw: dict[str, Any] = raw.get("workflows") or {}

        workflows: dict[str, Workflow] = {}
        errors: list[str] = []
        warnings: list[str] = []
        for definition in definitions:
            raw_binding = bindings_raw.get(definition.workflow_id)
            if raw_binding is None:
                warnings.append(
                    f"{definition.workflow_id} '{definition.name}' is defined in Excel but has no binding in "
                    f"{config_path.name} - it is listed but cannot be executed yet"
                )
                workflows[definition.workflow_id] = Workflow(definition=definition)
                continue
            try:
                binding = WorkflowBinding.model_validate(raw_binding)
            except ValidationError as exc:
                errors.append(f"{definition.workflow_id}: invalid binding - {exc}")
                continue
            errors += validate_binding(definition, binding, tools, prompts)
            workflows[definition.workflow_id] = Workflow(definition=definition, binding=binding)

        for orphan in sorted(set(bindings_raw) - {d.workflow_id for d in definitions}):
            warnings.append(f"Binding '{orphan}' in {config_path.name} has no matching Excel row - ignored")

        if errors:
            raise ConfigError("Workflow configuration is invalid:\n  - " + "\n  - ".join(errors))
        for warning in warnings:
            logger.warning(warning)
        logger.info(
            "Workflow registry ready: %d defined, %d executable",
            len(workflows), sum(w.executable for w in workflows.values()),
        )
        return cls(workflows, load_test_questions(excel_path), warnings, excel_path, config_path)

    def all(self) -> list[Workflow]:
        return list(self._workflows.values())

    def executable(self) -> list[Workflow]:
        return [w for w in self._workflows.values() if w.executable]

    def get(self, workflow_id: str) -> Workflow:
        try:
            return self._workflows[workflow_id]
        except KeyError as exc:
            raise WorkflowNotFoundError(f"Unknown workflow '{workflow_id}'") from exc

    def __len__(self) -> int:
        return len(self._workflows)
