"""Convert tool outputs (DataFrames, numpy scalars, ...) into JSON-safe result sections."""

from __future__ import annotations

import json
import math
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd

MAX_TABLE_ROWS = 500


def to_jsonable(value: Any) -> Any:
    if isinstance(value, pd.DataFrame):
        frame = value.head(MAX_TABLE_ROWS)
        rows = json.loads(frame.to_json(orient="records", date_format="iso", force_ascii=False, default_handler=str))
        return {"columns": [str(c) for c in frame.columns], "rows": rows, "total_rows": len(value)}
    if isinstance(value, pd.Series):
        return to_jsonable(value.tolist())
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, np.generic):
        return to_jsonable(value.item())
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, bool)):
        return value
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)


def make_section(title: str, value: Any) -> dict[str, Any]:
    """A UI/report section: kind is table | record | list | text."""
    if isinstance(value, pd.DataFrame):
        return {"title": title, "kind": "table", "data": to_jsonable(value)}
    if isinstance(value, list) and value and all(isinstance(v, dict) for v in value):
        return {"title": title, "kind": "table", "data": to_jsonable(pd.DataFrame(value))}
    if isinstance(value, dict):
        return {"title": title, "kind": "record", "data": to_jsonable(value)}
    if isinstance(value, (list, tuple, set)):
        return {"title": title, "kind": "list", "data": to_jsonable(list(value))}
    return {"title": title, "kind": "text", "data": "" if value is None else str(to_jsonable(value))}
