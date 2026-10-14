"""Command line interface.

    workflow-agent list                         # workflows loaded from Excel + their tool bindings
    workflow-agent ask "Which products need restocking?"   # interactive: answers follow-up questions
    workflow-agent test-questions               # run every Excel test question (+ edge cases) -> outputs/
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import yaml

from workflow_agent.core.config import PROJECT_ROOT, get_settings
from workflow_agent.core.exceptions import ConfigError
from workflow_agent.core.models import AgentResponse
from workflow_agent.engine.agent import WorkflowAgent
from workflow_agent.engine.rendering import RUN_LABEL, response_markdown

SCENARIO_FILE = PROJECT_ROOT / "examples" / "test_scenarios.yaml"


def _agent() -> WorkflowAgent:
    try:
        return WorkflowAgent()
    except ConfigError as exc:
        print(f"Configuration error:\n{exc}", file=sys.stderr)
        raise SystemExit(2) from exc


def cmd_list(_: argparse.Namespace) -> None:
    agent = _agent()
    print(f"Excel: {agent.registry.excel_path}\nBindings: {agent.registry.config_path}\nLLM: {agent.model_name}\n")
    for wf in agent.registry.all():
        print(f"{wf.id}  {wf.name}  {'[executable]' if wf.executable else '[NOT CONFIGURED]'}")
        for number, step in enumerate(wf.definition.steps, start=1):
            tools = ", ".join(c.tool for c in wf.binding.steps[number - 1].calls) if wf.binding else "-"
            print(f"    {number}. {step:<45} -> {tools}")
    for warning in agent.registry.warnings:
        print(f"WARNING: {warning}")


def cmd_ask(args: argparse.Namespace) -> None:
    agent = _agent()
    response = agent.start(" ".join(args.request))
    while True:
        print("\n" + response_markdown(response))
        if not response.waiting_for_input:
            break
        reply = input("\nYour answer (empty to stop) > ").strip()
        if not reply:
            break
        response = agent.resume(response.run_id, reply)
    if args.json:
        print(response.model_dump_json(indent=2))


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in text.lower()).strip("_")[:50]


def cmd_test_questions(args: argparse.Namespace) -> None:
    """Runs the Excel Test_Questions (with scripted follow-up answers) and extra edge cases."""
    agent = _agent()
    scenarios_cfg = yaml.safe_load(SCENARIO_FILE.read_text(encoding="utf-8")) if SCENARIO_FILE.exists() else {}
    follow_ups = scenarios_cfg.get("follow_ups", {})
    scenarios = [
        {"id": f"{q.workflow_id}_excel_test", "workflow_id": q.workflow_id, "request": q.request,
         "replies": follow_ups.get(q.workflow_id, []), "check": q.what_to_check}
        for q in agent.registry.test_questions
    ]
    if not args.excel_only:
        scenarios += scenarios_cfg.get("edge_cases", [])

    out_dir = Path(args.output_dir) if args.output_dir else get_settings().output_dir / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_rows, results = [], []
    for scenario in scenarios:
        print(f"> {scenario['id']}: {scenario['request']}")
        response: AgentResponse = agent.ask(scenario["request"], scenario.get("replies", []))
        expected = scenario.get("workflow_id")
        routed_ok = expected is None or response.workflow_id == expected
        print(f"  -> {response.workflow_id} | {response.status.value} | routing {'OK' if routed_ok else 'MISMATCH'}")
        (out_dir / f"{scenario['id']}.md").write_text(
            f"# {scenario['id']}\n\n_What this checks: {scenario.get('check', '')}_\n\n" + response_markdown(response),
            encoding="utf-8",
        )
        results.append({"scenario": scenario, "response": response.model_dump(mode="json")})
        summary_rows.append(
            f"| [{scenario['id']}]({scenario['id']}.md) | {scenario['request'].splitlines()[0]} | "
            f"{expected or '-'} | {response.workflow_id or '-'} | {RUN_LABEL.get(response.status.value)} | "
            f"{len(response.transcript) // 2} | {(response.duration_ms or 0) / 1000:.1f}s |"
        )

    (out_dir / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    index = [
        "# Test run results", "",
        f"_Generated {datetime.now():%Y-%m-%d %H:%M} - LLM: {agent.model_name}_", "",
        "| Scenario | Request | Expected workflow | Selected workflow | Status | Follow-up answers | Time |",
        "|---|---|---|---|---|---|---|",
        *summary_rows,
    ]
    (out_dir / "README.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    print(f"\nWrote {len(results)} results to {out_dir}")


def main(argv: list[str] | None = None) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="workflow-agent", description="Excel-driven AI workflow agent")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="show workflows loaded from Excel and their tool bindings").set_defaults(func=cmd_list)

    ask = sub.add_parser("ask", help="send a request to the agent (interactive follow-ups)")
    ask.add_argument("request", nargs="+")
    ask.add_argument("--json", action="store_true", help="also print the raw JSON response")
    ask.set_defaults(func=cmd_ask)

    tests = sub.add_parser("test-questions", help="run Excel test questions + edge cases, save outputs")
    tests.add_argument("--excel-only", action="store_true", help="skip the extra edge-case scenarios")
    tests.add_argument("--output-dir", help="default: outputs/results")
    tests.set_defaults(func=cmd_test_questions)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
