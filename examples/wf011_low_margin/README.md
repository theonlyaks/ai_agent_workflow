# Adding an 11th workflow: "Low Margin Product Alert"

This example shows that a new business workflow needs **no Python code** when it can reuse
existing tools. Only two files change:

| What | Where | Content |
|---|---|---|
| WHAT the workflow is | `data/AI_Agent_Workflow_Assessment.xlsx` → `Workflows` sheet | one new row: [`excel_row.yaml`](excel_row.yaml) |
| HOW it is executed | `config/workflows.yaml` | one new binding: [`binding.yaml`](binding.yaml) |

## Option A: by hand (best for the demo)

1. Open the Excel file and add a row with the values from `excel_row.yaml`.
2. Paste `binding.yaml` under `workflows:` in `config/workflows.yaml`.
3. In the Streamlit sidebar click **Reload Excel** (or restart the CLI).
4. Ask: *"Which products have a low profit margin?"* (or *"...margin below 60%?"*).

## Option B: script

```bash
python scripts/add_wf011_demo.py            # adds the row + binding
python scripts/add_wf011_demo.py --remove   # reverts both
```

## What happens automatically

* The Excel loader picks up the row, and the registry validates the binding at startup: the step
  count matches the 4 Excel steps, the tools exist, the arguments are valid and every `$reference` is defined.
* The router turns WF011 into a new Claude tool (`run_wf011`) using the Excel name, trigger, decision
  logic and expected output. No prompt changes are needed.
* The executor runs it like every other workflow, with the same tracing, retries, error handling,
  logging and UI.

If a workflow needs a capability no tool has yet (for example a real ERP API), the only code to
write is one function decorated with `@tool(...)` in `src/workflow_agent/tools/`.
