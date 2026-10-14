"""Similarity tools: exact identifier matches, fuzzy name + attribute matches, grouping."""

from __future__ import annotations

from itertools import combinations
from typing import Any

import pandas as pd
from rapidfuzz import fuzz

from workflow_agent.core.models import ToolResult
from workflow_agent.tools.data_tools import as_frame, is_blank, require_columns
from workflow_agent.tools.registry import tool

PAIR_COLUMNS = ["row_a", "row_b", "match_type", "name_score", "attribute_match", "matched_fields", "mismatched_fields"]


def _norm(value: Any) -> str:
    return "" if is_blank(value) else " ".join(str(value).lower().split())


def _compare_attributes(row_a: pd.Series, row_b: pd.Series, columns: list[str]) -> tuple[float | None, list[str], list[str]]:
    matched, mismatched = [], []
    for column in columns:
        a, b = _norm(row_a.get(column)), _norm(row_b.get(column))
        if not a and not b:
            continue  # nothing to compare
        (matched if a == b else mismatched).append(column)
    compared = len(matched) + len(mismatched)
    return (round(len(matched) / compared, 2) if compared else None), matched, mismatched


def _pairs_frame(pairs: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(pairs, columns=PAIR_COLUMNS)


@tool(category="similarity")
def find_exact_matches(
    table: Any,
    key_column: str,
    text_column: str | None = None,
    attribute_columns: list[str] | None = None,
) -> ToolResult:
    """Pairs of rows sharing the same (normalised) identifier -> definite duplicates."""
    frame = as_frame(table).reset_index(drop=True)
    require_columns(frame, [key_column], "find_exact_matches")
    pairs = []
    for key, index in frame.groupby(key_column).indices.items():
        if is_blank(key) or len(index) < 2:
            continue
        for a, b in combinations(sorted(index), 2):
            score = fuzz.token_set_ratio(frame.at[a, text_column], frame.at[b, text_column]) if text_column else None
            attr, matched, mismatched = _compare_attributes(frame.loc[a], frame.loc[b], attribute_columns or [])
            pairs.append({
                "row_a": int(a), "row_b": int(b), "match_type": "exact_id",
                "name_score": round(score, 1) if score is not None else None, "attribute_match": attr,
                "matched_fields": [key_column, *matched], "mismatched_fields": mismatched,
            })
    return ToolResult(output=_pairs_frame(pairs), message=f"{len(pairs)} pair(s) share the same {key_column}",
                      metrics={"exact_pairs": len(pairs)})


@tool(category="similarity")
def find_similar_pairs(
    table: Any,
    text_column: str,
    attribute_columns: list[str],
    min_name_score: float = 85,
    min_attribute_match: float = 0.75,
    block_by: str | None = None,
    exclude_pairs: Any = None,
) -> ToolResult:
    """Pairs with similar names AND similar attributes -> possible duplicates.

    `block_by` only compares rows within the same group (e.g. category) to keep the
    O(n^2) comparison cheap on large catalogs.
    """
    frame = as_frame(table).reset_index(drop=True)
    require_columns(frame, [text_column], "find_similar_pairs")
    skip: set[tuple[int, int]] = set()
    if exclude_pairs is not None and len(as_frame(exclude_pairs)):
        skip = {(int(r["row_a"]), int(r["row_b"])) for r in as_frame(exclude_pairs).to_dict("records")}

    blocks = frame.groupby(block_by).indices.values() if block_by and block_by in frame.columns else [frame.index]
    pairs, compared = [], 0
    for index in blocks:
        for a, b in combinations(sorted(index), 2):
            if (a, b) in skip:
                continue
            compared += 1
            score = fuzz.token_set_ratio(frame.at[a, text_column], frame.at[b, text_column])
            if score < min_name_score:
                continue
            attr, matched, mismatched = _compare_attributes(frame.loc[a], frame.loc[b], attribute_columns)
            if attr is not None and attr < min_attribute_match:
                continue
            pairs.append({
                "row_a": int(a), "row_b": int(b), "match_type": "similar",
                "name_score": round(score, 1), "attribute_match": attr,
                "matched_fields": ["name", *matched], "mismatched_fields": mismatched,
            })
    return ToolResult(
        output=_pairs_frame(pairs),
        message=f"{len(pairs)} similar pair(s) out of {compared} comparisons",
        metrics={"comparisons": compared, "similar_pairs": len(pairs)},
    )


@tool(category="similarity")
def group_pairs(table: Any, pairs: list[Any], id_column: str, label_column: str) -> ToolResult:
    """Union-find over matched pairs -> duplicate groups with the evidence for each group."""
    frame = as_frame(table).reset_index(drop=True)
    all_pairs = pd.concat([as_frame(p) for p in pairs if p is not None], ignore_index=True) if pairs else _pairs_frame([])

    parent: dict[int, int] = {}

    def find(x: int) -> int:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for row in all_pairs.to_dict("records"):
        parent[find(int(row["row_a"]))] = find(int(row["row_b"]))

    members: dict[int, set[int]] = {}
    for node in list(parent):
        members.setdefault(find(node), set()).add(node)

    groups = []
    for number, rows in enumerate(sorted((sorted(m) for m in members.values()), key=lambda m: m[0]), start=1):
        evidence = all_pairs[all_pairs["row_a"].isin(rows) & all_pairs["row_b"].isin(rows)]
        name_scores = evidence["name_score"].dropna()
        attr_scores = evidence["attribute_match"].dropna()
        matched = sorted({f for fields in evidence["matched_fields"] for f in fields})
        mismatched = sorted({f for fields in evidence["mismatched_fields"] for f in fields})
        groups.append({
            "group_id": f"G{number}",
            "size": len(rows),
            id_column: ", ".join(frame.loc[rows, id_column].astype(str).str.strip()),
            label_column: " | ".join(frame.loc[rows, label_column].astype(str)),
            "has_exact_id_match": bool((evidence["match_type"] == "exact_id").any()),
            "name_similarity": float(name_scores.min()) if len(name_scores) else None,
            "attribute_match": float(attr_scores.min()) if len(attr_scores) else None,
            "matching_fields": ", ".join(matched),
            "differing_fields": ", ".join(mismatched) or "-",
        })
    result = pd.DataFrame(groups, columns=[
        "group_id", "size", id_column, label_column, "has_exact_id_match", "name_similarity",
        "attribute_match", "matching_fields", "differing_fields",
    ])
    return ToolResult(output=result, message=f"{len(result)} duplicate group(s) found",
                      metrics={"groups": len(result), "products_involved": int(result["size"].sum()) if len(result) else 0})
