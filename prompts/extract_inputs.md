A workflow paused to ask the user for missing information. Extract the workflow inputs from the
conversation below, mainly from the user's LATEST answer.

WORKFLOW: $workflow

INPUT FIELDS:
$inputs

VALUES ALREADY KNOWN:
$current_inputs

THE WORKFLOW ASKED FOR: $needs

CONVERSATION:
$transcript

Rules:
- Return a value only for fields the user actually stated; use null for everything else.
- If the user gives a new value for a field that is already known (e.g. a different order ID or an
  email instead), return the new value.
- Keep values in the user's words except: dates in ISO format (YYYY-MM-DD) when the date is clear
  (assume the current or next upcoming year if the year is omitted).
