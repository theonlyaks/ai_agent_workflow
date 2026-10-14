"""Generic table tools (CSV/Excel reader, filters, calculator, joins, aggregations...).

These are deliberately workflow-agnostic: the same tool is reused by many workflows,
and workflow-specific behaviour comes from the arguments in config/workflows.yaml.
"""

from __future__ import annotations

import operator
import re
from pathlib import Path
from typing import Any

import pandas as pd
from rapidfuzz import fuzz

from workflow_agent.core.config import resolve_path
from workflow_agent.core.exceptions import ToolError, ToolInputError
from workflow_agent.core.models import StepStatus, ToolResult
from workflow_agent.tools.registry import ToolContext, tool

SUPPORTED_FORMATS = {".csv", ".xlsx", ".xls", ".json", ".jsonl"}
_ID_COLUMNS = ("sku", "id", "order_id", "employee_id", "task_id", "run_id", "keyword")
_STOPWORDS = {"the", "a", "an", "for", "of", "our", "this", "these", "my", "to", "and", "in", "on"}

OPERATORS = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "==": operator.eq,
    "!=": operator.ne,
}


# ---------------------------------------------------------------------------
# helpers (used by other tool modules too)
# ---------------------------------------------------------------------------
def load_frame(path: str | Path, sheet: str | int | None = None) -> pd.DataFrame:
    file_path = resolve_path(path)
    if not file_path.exists():
        raise ToolError(f"File not found: {path}")
    suffix = file_path.suffix.lower()
    if suffix not in SUPPORTED_FORMATS:
        raise ToolError(
            f"Unsupported file format '{suffix}'. Supported formats: CSV, XLSX, XLS, JSON"
        )
    try:
        if suffix == ".csv":
            return pd.read_csv(file_path)
        if suffix in (".xlsx", ".xls"):
            return pd.read_excel(file_path, sheet_name=sheet if sheet is not None else 0)
        return pd.read_json(file_path, lines=suffix == ".jsonl")
    except Exception as exc:  # corrupt / unreadable file
        raise ToolError(f"Could not read {file_path.name}: {exc}") from exc


def as_frame(table: Any) -> pd.DataFrame:
    """Accept a DataFrame, a file path, a list of records or a serialised table."""
    if isinstance(table, pd.DataFrame):
        return table
    if isinstance(table, (str, Path)):
        return load_frame(table)
    if isinstance(table, list):
        return pd.DataFrame(table)
    if isinstance(table, dict) and "rows" in table:
        return pd.DataFrame(table["rows"], columns=table.get("columns"))
    if table is None:
        raise ToolInputError("No table was provided to the tool")
    raise ToolInputError(f"Expected a table, got {type(table).__name__}")


def require_columns(frame: pd.DataFrame, columns: list[str], what: str) -> None:
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise ToolError(f"{what}: missing column(s) {missing}. Available: {list(frame.columns)}")


def row_labels(frame: pd.DataFrame, limit: int = 5) -> str:
    """Human-friendly identifiers for rows, used in warnings."""
    id_col = next((c for c in _ID_COLUMNS if c in frame.columns), None)
    labels = frame[id_col].astype(str).tolist() if id_col else [f"row {i + 1}" for i in frame.index]
    suffix = f" (+{len(labels) - limit} more)" if len(labels) > limit else ""
    return ", ".join(labels[:limit]) + suffix


def is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return str(value).strip() == ""


def _eval(frame: pd.DataFrame, expression: str, variables: dict | None) -> Any:
    try:
        return frame.eval(expression, engine="python", local_dict=dict(variables or {}))
    except Exception as exc:
        raise ToolError(f"Could not evaluate expression '{expression}': {exc}") from exc


def _as_bool_mask(result: Any, frame: pd.DataFrame) -> pd.Series:
    if isinstance(result, pd.Series):
        return result.fillna(False).astype(bool)
    return pd.Series(bool(result), index=frame.index)


def _search_tokens(text: str) -> str:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return " ".join(t for t in tokens if t not in _STOPWORDS)


# ---------------------------------------------------------------------------
# tools
# ---------------------------------------------------------------------------
@tool(category="data")
def read_table(path: str, sheet: str | None = None) -> ToolResult:
    """Read a CSV / Excel / JSON file into a table."""
    if is_blank(path):
        raise ToolInputError("No file path was provided")
    frame = load_frame(path, sheet)
    return ToolResult(
        output=frame,
        message=f"Loaded {len(frame)} rows x {len(frame.columns)} columns from {Path(path).name}",
        metrics={"rows": len(frame), "columns": len(frame.columns), "file": Path(path).name},
    )


@tool(category="data")
def compare_to_threshold(
    table: Any,
    value_column: str,
    operator: str,
    threshold_column: str | None = None,
    threshold_value: float | None = None,
    flag_column: str = "flagged",
    threshold_output_column: str | None = None,
    mark_flagged: bool = False,
    flag_message: str | None = None,
) -> ToolResult:
    """Flag rows where value_column <operator> threshold (per-row column or one global value)."""
    if operator not in OPERATORS:
        raise ToolInputError(f"Unsupported operator '{operator}'. Use one of {list(OPERATORS)}")
    frame = as_frame(table).copy()
    require_columns(frame, [value_column], "compare_to_threshold")
    values = pd.to_numeric(frame[value_column], errors="coerce")

    if not is_blank(threshold_value):
        threshold = pd.Series(float(threshold_value), index=frame.index)
        threshold_source = f"global threshold {threshold_value}"
    elif threshold_column:
        require_columns(frame, [threshold_column], "compare_to_threshold")
        threshold = pd.to_numeric(frame[threshold_column], errors="coerce")
        threshold_source = f"column '{threshold_column}'"
    else:
        raise ToolInputError("Provide threshold_column or threshold_value")

    comparable = values.notna() & threshold.notna()
    flags = OPERATORS[operator](values, threshold) & comparable
    frame[flag_column] = flags.astype(bool)
    if threshold_output_column:
        frame[threshold_output_column] = threshold

    warnings = []
    if (~comparable).any():
        warnings.append(
            f"{int((~comparable).sum())} row(s) skipped - '{value_column}' or its threshold is "
            f"missing / not a number: {row_labels(frame[~comparable])}"
        )
    count = int(flags.sum())
    message = (flag_message or "{count} row(s) where {column} {op} {source}").format(
        count=count, column=value_column, op=operator, source=threshold_source,
        threshold=f"{float(threshold_value):g}" if not is_blank(threshold_value) else threshold_column,
    )
    return ToolResult(
        output=frame,
        status=StepStatus.FLAGGED if (mark_flagged and count) else StepStatus.OK,
        message=message,
        metrics={"rows_checked": int(comparable.sum()), "rows_flagged": count},
        warnings=warnings,
    )


@tool(category="data")
def filter_rows(
    table: Any,
    where: str | None = None,
    contains: dict[str, Any] | None = None,
    equals: dict[str, Any] | None = None,
    variables: dict[str, Any] | None = None,
) -> ToolResult:
    """Keep rows matching a pandas expression and/or case-insensitive contains/equals filters."""
    frame = as_frame(table)
    result = frame
    if where:
        result = result[_as_bool_mask(_eval(result, where, variables), result)]
    for column, value in (contains or {}).items():
        if is_blank(value):
            continue
        require_columns(result, [column], "filter_rows")
        result = result[result[column].astype(str).str.contains(str(value), case=False, regex=False, na=False)]
    for column, value in (equals or {}).items():
        if is_blank(value):
            continue
        require_columns(result, [column], "filter_rows")
        result = result[result[column].astype(str).str.lower() == str(value).lower()]
    result = result.reset_index(drop=True)
    return ToolResult(
        output=result,
        message=f"{len(result)} of {len(frame)} rows match",
        metrics={"rows_in": len(frame), "rows_out": len(result)},
    )


@tool(category="data")
def compute_column(
    table: Any,
    column: str,
    expression: str,
    variables: dict[str, Any] | None = None,
    decimals: int | None = None,
    clip_min: float | None = None,
    clip_max: float | None = None,
) -> ToolResult:
    """Calculator: add/overwrite a column from an arithmetic expression over other columns."""
    frame = as_frame(table).copy()
    if frame.empty:
        frame[column] = pd.Series(dtype="float64")
        return ToolResult(output=frame, message="Table is empty - nothing to calculate")
    values = _eval(frame, expression, variables)
    if not isinstance(values, pd.Series):
        values = pd.Series(values, index=frame.index)
    if pd.api.types.is_numeric_dtype(values) and not pd.api.types.is_bool_dtype(values):
        if clip_min is not None or clip_max is not None:
            values = values.clip(lower=clip_min, upper=clip_max)
        if decimals is not None:
            values = values.round(decimals)
            if decimals == 0:
                values = values.astype("Int64")
    frame[column] = values
    return ToolResult(output=frame, message=f"Calculated '{column}' = {expression}")


@tool(category="data")
def select_columns(
    table: Any,
    columns: list[str] | None = None,
    drop: list[str] | None = None,
    rename: dict[str, str] | None = None,
    sort_by: str | list[str] | None = None,
    ascending: bool | list[bool] = True,
    limit: int | None = None,
    custom_order: dict[str, list[Any]] | None = None,
) -> ToolResult:
    """Pick, drop, rename, sort and limit columns/rows. custom_order sorts e.g. priority High > Medium > Low."""
    frame = as_frame(table).copy()
    warnings = []
    if sort_by:
        keys = [sort_by] if isinstance(sort_by, str) else list(sort_by)
        present = [k for k in keys if k in frame.columns]
        if present:
            order = ascending if isinstance(ascending, bool) else ascending[: len(present)]
            ranks = {c: {v: i for i, v in enumerate(values)} for c, values in (custom_order or {}).items()}

            def sort_key(column: pd.Series) -> pd.Series:
                if column.name in ranks:
                    return column.map(ranks[column.name]).fillna(len(ranks[column.name]))
                return column

            frame = frame.sort_values(present, ascending=order, kind="stable", key=sort_key)
    if columns:
        missing = [c for c in columns if c not in frame.columns]
        if missing:
            warnings.append(f"Columns not found and skipped: {missing}")
        frame = frame[[c for c in columns if c in frame.columns]]
    if drop:
        frame = frame.drop(columns=[c for c in drop if c in frame.columns])
    if rename:
        frame = frame.rename(columns=rename)
    if limit:
        frame = frame.head(int(limit))
    return ToolResult(output=frame.reset_index(drop=True), metrics={"rows": len(frame)}, warnings=warnings)


@tool(category="data")
def join_tables(
    left: Any,
    right: Any,
    key: str,
    how: str = "inner",
    indicator_column: str | None = None,
    left_only_label: str = "only_in_left",
    right_only_label: str = "only_in_right",
    normalize_keys: bool = True,
) -> ToolResult:
    """Join two tables on a key column (keys are trimmed/upper-cased for matching, originals kept)."""
    on = key
    lframe, rframe = as_frame(left).copy(), as_frame(right).copy()
    require_columns(lframe, [on], "join_tables (left)")
    require_columns(rframe, [on], "join_tables (right)")

    def normalized(series: pd.Series) -> pd.Series:
        text = series.astype("string").str.strip()
        return text.str.upper() if normalize_keys else text

    lframe["__key"], rframe["__key"] = normalized(lframe[on]), normalized(rframe[on])
    merged = lframe.merge(
        rframe, on="__key", how=how, suffixes=("", "__right"), indicator=bool(indicator_column)
    )
    if f"{on}__right" in merged.columns:
        merged[on] = merged[on].combine_first(merged[f"{on}__right"])
        merged = merged.drop(columns=[f"{on}__right"])
    merged = merged.drop(columns=["__key"])

    metrics: dict[str, Any] = {"rows": len(merged)}
    message = f"Joined {len(lframe)} + {len(rframe)} rows on '{on}' ({how})"
    if indicator_column:
        labels = {"both": "matched", "left_only": left_only_label, "right_only": right_only_label}
        merged[indicator_column] = merged.pop("_merge").astype(str).map(labels)
        counts = merged[indicator_column].value_counts().to_dict()
        metrics.update(counts)
        message += ": " + ", ".join(f"{v} {k}" for k, v in counts.items())
    return ToolResult(output=merged, metrics=metrics, message=message)


@tool(category="data")
def aggregate(
    table: Any,
    group_by: str | list[str],
    metrics: dict[str, list[str]],
    sort_by: str | None = None,
    ascending: bool = False,
    limit: int | None = None,
) -> ToolResult:
    """Group rows and compute metrics: {output_column: [source_column, count|sum|mean|min|max|nunique|first]}."""
    frame = as_frame(table)
    keys = [group_by] if isinstance(group_by, str) else list(group_by)
    require_columns(frame, keys + [spec[0] for spec in metrics.values()], "aggregate")
    if frame.empty:
        return ToolResult(output=pd.DataFrame(columns=keys + list(metrics)), message="No rows to aggregate")
    grouped = (
        frame.groupby(keys, dropna=False)
        .agg(**{out: (spec[0], spec[1]) for out, spec in metrics.items()})
        .reset_index()
    )
    for column in grouped.select_dtypes(include="float").columns:
        grouped[column] = grouped[column].round(4)
    if sort_by and sort_by in grouped.columns:
        grouped = grouped.sort_values(sort_by, ascending=ascending, kind="stable")
    if limit:
        grouped = grouped.head(int(limit))
    return ToolResult(output=grouped.reset_index(drop=True), metrics={"groups": len(grouped)})


@tool(category="data")
def assign_label(
    table: Any,
    column: str,
    rules: list[dict[str, Any]],
    default: Any = None,
    variables: dict[str, Any] | None = None,
    mark_flagged: bool = False,
    flag_message: str | None = None,
) -> ToolResult:
    """Decision rules: first matching `when` expression sets the label (a value or {column: name})."""
    frame = as_frame(table).copy()
    labels = pd.Series([None] * len(frame), index=frame.index, dtype="object")
    assigned = pd.Series(False, index=frame.index)

    def value_for(label: Any, mask: pd.Series) -> Any:
        if isinstance(label, dict) and "column" in label:
            require_columns(frame, [label["column"]], "assign_label")
            return frame.loc[mask, label["column"]]
        return label

    if not frame.empty:
        for rule in rules:
            mask = _as_bool_mask(_eval(frame, rule["when"], variables), frame) & ~assigned
            if mask.any():
                labels[mask] = value_for(rule["label"], mask)
                assigned |= mask
        rest = ~assigned
        if default is not None and rest.any():
            labels[rest] = value_for(default, rest)
    frame[column] = labels

    count = int(assigned.sum())
    message = (flag_message or "{count} row(s) matched a rule for '{column}'").format(
        count=count, column=column, **(variables or {})
    )
    return ToolResult(
        output=frame,
        status=StepStatus.FLAGGED if (mark_flagged and count) else StepStatus.OK,
        message=message,
        metrics={"rows_matched": count, **frame[column].astype(str).value_counts().to_dict()},
    )


@tool(category="data")
def search_table(
    table: Any,
    query: str | None,
    columns: list[str],
    min_score: float = 90,
    limit: int | None = None,
) -> ToolResult:
    """Fuzzy text search across columns (all query words present = score 100)."""
    frame = as_frame(table)
    require_columns(frame, columns, "search_table")
    if is_blank(query):
        return ToolResult(output=frame.iloc[0:0], warnings=["No search text was given - nothing matched"])
    needle = _search_tokens(str(query))
    haystack = frame[columns].fillna("").astype(str).agg(" ".join, axis=1).map(_search_tokens)
    scores = haystack.map(lambda text: fuzz.token_set_ratio(needle, text))
    result = frame.assign(match_score=scores.round(0))
    result = result[result["match_score"] >= min_score].sort_values("match_score", ascending=False)
    if limit:
        result = result.head(int(limit))
    warnings = [] if len(result) else [f"No rows matched '{query}'"]
    return ToolResult(
        output=result.reset_index(drop=True),
        message=f"{len(result)} row(s) match '{query}'",
        metrics={"matches": len(result)},
        warnings=warnings,
    )


@tool(category="data")
def summarize_table(
    table: Any,
    label_column: str | None = None,
    group_by: str | None = None,
    numeric_columns: list[str] | None = None,
) -> ToolResult:
    """Quick profile of a table: item count, counts per group, numeric ranges."""
    frame = as_frame(table)
    summary: dict[str, Any] = {"total_items": len(frame)}
    if label_column and label_column in frame.columns:
        summary["items"] = frame[label_column].astype(str).tolist()
    if group_by and group_by in frame.columns:
        summary[f"count_by_{group_by}"] = frame[group_by].astype(str).value_counts().to_dict()
    for column in numeric_columns or []:
        if column in frame.columns and len(frame):
            values = pd.to_numeric(frame[column], errors="coerce")
            summary[f"{column}_range"] = f"{values.min():.2f} - {values.max():.2f} (avg {values.mean():.2f})"
    return ToolResult(output=summary, message=f"Summarised {len(frame)} item(s)")


@tool(category="data")
def drop_duplicate_rows(table: Any, subset: list[str], normalize: bool = True) -> ToolResult:
    """Remove duplicate rows (optionally ignoring case and extra whitespace)."""
    frame = as_frame(table)
    require_columns(frame, subset, "drop_duplicate_rows")
    keys = frame[subset].astype(str)
    if normalize:
        keys = keys.apply(lambda col: col.str.lower().str.split().str.join(" "))
    duplicated = keys.duplicated(keep="first")
    removed = frame[duplicated]
    result = frame[~duplicated].reset_index(drop=True)
    warnings = [f"Removed {len(removed)} duplicate(s): {row_labels(removed)}"] if len(removed) else []
    return ToolResult(
        output=result,
        message=f"{len(removed)} duplicate row(s) removed, {len(result)} unique",
        metrics={"rows_in": len(frame), "duplicates_removed": len(removed), "rows_out": len(result)},
        warnings=warnings,
    )


@tool(category="data")
def normalize_text_columns(
    table: Any,
    text_columns: list[str] | None = None,
    identifier_columns: list[str] | None = None,
    suffix: str = "_norm",
) -> ToolResult:
    """Normalised copies of columns: text -> lowercase words; identifiers -> lowercase alphanumerics only."""
    frame = as_frame(table).copy()
    for column in text_columns or []:
        require_columns(frame, [column], "normalize_text_columns")
        frame[column + suffix] = (
            frame[column].fillna("").astype(str).str.lower()
            .str.replace(r"[^a-z0-9]+", " ", regex=True).str.strip()
        )
    for column in identifier_columns or []:
        require_columns(frame, [column], "normalize_text_columns")
        frame[column + suffix] = (
            frame[column].fillna("").astype(str).str.lower().str.replace(r"[^a-z0-9]", "", regex=True)
        )
    return ToolResult(output=frame, message="Normalised " + ", ".join((text_columns or []) + (identifier_columns or [])))


@tool(category="data")
def rename_columns(table: Any, mapping: dict[str, str], strip_values: bool = True) -> ToolResult:
    """Rename columns using a mapping; unmapped columns become snake_case. Optionally trim text cells."""
    frame = as_frame(table).copy()
    renamed = {}
    for column in frame.columns:
        target = mapping.get(column) or re.sub(r"[^a-z0-9]+", "_", str(column).strip().lower()).strip("_")
        renamed[column] = target
    frame = frame.rename(columns=renamed)
    if strip_values:
        for column in frame.select_dtypes(include=["object", "string"]).columns:
            frame[column] = frame[column].map(lambda v: v.strip() if isinstance(v, str) else v)
            frame[column] = frame[column].replace("", pd.NA)
    return ToolResult(output=frame, message=f"Columns: {list(frame.columns)}")


@tool(category="data")
def enrich_from_table(
    record: dict[str, Any] | None,
    table: Any,
    key_field: str,
    key_column: str,
    fields: dict[str, str],
    fuzzy_field: str | None = None,
    fuzzy_column: str | None = None,
    min_score: float = 90,
) -> ToolResult:
    """Fill missing record fields from a reference table row (matched by key, or fuzzy by name)."""
    record = dict(record or {})
    frame = as_frame(table)
    match = None
    key_value = record.get(key_field)
    if not is_blank(key_value):
        hits = frame[frame[key_column].astype(str).str.upper() == str(key_value).strip().upper()]
        if len(hits):
            match = hits.iloc[0]
        else:
            return ToolResult(output=record, warnings=[f"{key_field} '{key_value}' not found in reference data"])
    elif fuzzy_field and fuzzy_column and not is_blank(record.get(fuzzy_field)):
        needle = str(record[fuzzy_field]).lower()
        scores = frame[fuzzy_column].astype(str).str.lower().map(lambda v: fuzz.ratio(needle, v))
        if len(scores) and scores.max() >= min_score:
            match = frame.loc[scores.idxmax()]

    if match is None:
        return ToolResult(output=record, message="No reference record matched - using the details given by the user")

    filled = []
    for field, column in fields.items():
        if is_blank(record.get(field)) and column in match.index and not is_blank(match[column]):
            record[field] = match[column]
            filled.append(field)
    label = match.get(key_column, "")
    return ToolResult(
        output=record,
        message=f"Matched reference record {label}; filled: {', '.join(filled) or 'nothing (all provided)'}",
        metrics={"fields_filled": len(filled)},
    )


@tool(category="data")
def build_record(fields: dict[str, Any]) -> ToolResult:
    """Assemble a result record from values produced by earlier steps."""
    return ToolResult(output=dict(fields))


@tool(category="data")
def export_table(table: Any, filename: str, ctx: ToolContext) -> ToolResult:
    """Write a table to outputs/files/<run_id>_<filename> (CSV or XLSX by extension)."""
    frame = as_frame(table)
    out_dir = ctx.settings.output_dir / "files"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{ctx.run_id}_{filename}"
    if path.suffix.lower() == ".xlsx":
        frame.to_excel(path, index=False)
    else:
        frame.to_csv(path, index=False)
    try:
        shown = path.relative_to(ctx.settings.output_dir.parent).as_posix()
    except ValueError:
        shown = str(path)
    return ToolResult(output=shown, message=f"Exported {len(frame)} rows to {shown}", metrics={"rows": len(frame)})
