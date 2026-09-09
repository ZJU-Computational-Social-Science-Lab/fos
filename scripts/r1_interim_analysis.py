"""Strict + recovery parsing, cells, curves, and condition summaries.

This module is the numeric heart of the R1 interim report: it takes raw
sweep records (JSONL dicts as scripts/launch_sweep.py writes them) and
turns them into the numbers the report shows. Nothing here touches the
network, the run directory, or any dataset; it only reads the records it
is handed.

Plain-language map of what each function/class does:

    recover_purchase        - The re-parse pass for ONE raw answer: read the
                              first decision token (comma-field, or first
                              word) so trailing junk after a valid decision
                              does not lose the record. Never rescues prose.
    decide_records          - Add a "strict" (tooling parser) and a
                              "recovered" (strict + re-parse pass) decision
                              to every record.
    wilson95                - Wilson 95% confidence interval for a share.
    Cell                    - One little counter: how many records, how many
                              buys, the share, and its Wilson interval.
    buckets_by_level        - One Cell per price level, pooling all products
                              (the pooled p(buy) curve of a condition).
    matrix_by_product       - One row per product, one Cell per price level
                              (the per-product p(buy) matrix).
    condition_summary       - Everything numeric about one condition: parse
                              counts/rates and its curves and matrix.
    curve_mae / curve_value - Mean absolute difference between two per-level
                              curves (and one cell read helper).
    compare_condition       - Score one condition against the human benchmark
                              table: cell MAE (paper's way) plus the pooled
                              and mean-of-cells curve comparisons.
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from fos.experiments.sweep_kit import parse_purchase  # noqa: E402

_JUNK = " \t\"'$.,;:!?()[]{}"
_ANSWER_TOKENS = {"purchase": True, "yes": True, "not purchase": False, "no": False}
_Z = 1.959963984540054  # standard normal quantile for a 95% interval


def recover_purchase(text: str) -> bool | None:
    """Rescue one unparsed answer by reading its first decision token.

    Only the documented failure mode is rescued: the model answered a valid
    decision first and then kept echoing a comma list ("not purchase,not
    purchase,0.00,30,6,") or stray values ("not purchase 0.00 30 6"). The
    first comma-field is read when a comma is present, otherwise the first
    word (two words when they are "not purchase"). The word fallback only
    fires when nothing but numbers/punctuation follows the decision, so a
    prose sentence that merely starts with a decision word ("purchase is a
    personal choice") is NOT rescued. Anything else stays None.
    """
    if not isinstance(text, str):
        return None
    body = text.split("\n", 1)[0].strip().lower().lstrip(_JUNK)
    if not body:
        return None
    if "," in body:
        candidate = body.split(",", 1)[0].rstrip(_JUNK)
        return _ANSWER_TOKENS.get(candidate)
    words = body.split()
    if not words:
        return None
    candidate = " ".join(words[:2]) if words[0] == "not" else words[0]
    candidate = candidate.rstrip(_JUNK)
    if candidate not in _ANSWER_TOKENS:
        return None
    rest = body[len(candidate) :].strip()
    if any(char.isalpha() for char in rest):
        return None
    return _ANSWER_TOKENS[candidate]


def decide_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach a strict and a recovered decision to every record.

    The strict decision is the tooling parser run again on the stored raw
    answer (so old files recorded before a parser fix are judged by the
    current parser, not by the parser of the day). The recovered decision
    is the strict one, or the re-parse pass when strict found nothing. Each
    returned record gains "strict" and "recovered" (each bool or None).
    """
    decided: list[dict[str, Any]] = []
    for record in records:
        raw = record.get("raw_content", "")
        strict = parse_purchase(raw) if isinstance(raw, str) else None
        recovered = strict if strict is not None else recover_purchase(raw)
        decided.append({**record, "strict": strict, "recovered": recovered})
    return decided


def wilson95(k: int, n: int) -> tuple[float, float] | None:
    """Wilson 95% confidence interval for a share, or None when n is 0."""
    if n <= 0:
        return None
    share = k / n
    denom = 1 + _Z * _Z / n
    center = (share + _Z * _Z / (2 * n)) / denom
    half = _Z * math.sqrt((share * (1 - share) + _Z * _Z / (4 * n)) / n) / denom
    return (max(0.0, center - half), min(1.0, center + half))


@dataclass
class Cell:
    """One (n buys over n tries, p_buy, Wilson CI) summary."""

    n: int = 0
    buys: int = 0

    @property
    def p(self) -> float | None:
        """p_buy, or None when there are no parsed records."""
        return self.buys / self.n if self.n else None

    @property
    def ci(self) -> tuple[float, float] | None:
        """The Wilson 95% interval, or None when there are no records."""
        return wilson95(self.buys, self.n)

    def add(self, buys: bool) -> None:
        """Count one more record."""
        self.n += 1
        if buys:
            self.buys += 1


def _empty_cells(levels: list[float]) -> dict[float, dict[str, Cell]]:
    """A fresh {level: {strict: Cell, recovered: Cell}} map."""
    return {level: {"strict": Cell(), "recovered": Cell()} for level in levels}


def buckets_by_level(
    decided: list[dict[str, Any]], levels: list[float]
) -> list[dict[str, Any]]:
    """Per price level: strict and recovered cells, pooled over products.

    levels is the run's planned level list; any level with no records yet
    appears with empty cells (n=0), so an in-flight run shows its gaps
    instead of pretending the level was not planned.
    """
    strict: dict[float, Cell] = {level: Cell() for level in levels}
    recovered: dict[float, Cell] = {level: Cell() for level in levels}
    for record in decided:
        level = float(record.get("treatment_value", float("nan")))
        if not math.isfinite(level):
            continue
        if level not in strict:
            strict[level] = Cell()
            recovered[level] = Cell()
        if record["strict"] is not None:
            strict[level].add(record["strict"])
        if record["recovered"] is not None:
            recovered[level].add(record["recovered"])
    return [
        {"level": level, "strict": strict[level], "recovered": recovered[level]}
        for level in sorted(strict)
    ]


def matrix_by_product(
    decided: list[dict[str, Any]], levels: list[float]
) -> dict[str, dict[float, dict[str, Cell]]]:
    """Per product: per price level, strict and recovered cells."""
    matrix: dict[str, dict[float, dict[str, Cell]]] = {}
    for record in decided:
        product = str(record.get("product", ""))
        level = float(record.get("treatment_value", float("nan")))
        if not math.isfinite(level):
            continue
        row = matrix.setdefault(product, _empty_cells(levels))
        if level not in row:
            row[level] = {"strict": Cell(), "recovered": Cell()}
        if record["strict"] is not None:
            row[level]["strict"].add(record["strict"])
        if record["recovered"] is not None:
            row[level]["recovered"].add(record["recovered"])
    return {
        product: {level: row[level] for level in sorted(row)}
        for product, row in matrix.items()
    }


def condition_summary(
    decided: list[dict[str, Any]], levels: list[float]
) -> dict[str, Any]:
    """Everything the report needs about one (depth x blinding) condition."""
    total = len(decided)
    strict_parsed = sum(1 for r in decided if r["strict"] is not None)
    recovered_only = sum(
        1 for r in decided if r["strict"] is None and r["recovered"] is not None
    )
    recovered_parsed = strict_parsed + recovered_only
    return {
        "records": total,
        "strict_parsed": strict_parsed,
        "strict_rate": strict_parsed / total if total else 0.0,
        "recovered_parsed": recovered_parsed,
        "recovered_only": recovered_only,
        "recovered_rate": recovered_parsed / total if total else 0.0,
        "buckets": buckets_by_level(decided, levels),
        "matrix": matrix_by_product(decided, levels),
    }


def curve_mae(model: dict[float, Any], human: dict[float, Any]) -> float | None:
    """Mean over shared levels of |model - human| (None when nothing shares)."""
    diffs = [
        abs(curve_value(model[level]) - curve_value(human[level]))
        for level in sorted(set(model) & set(human))
    ]
    return sum(diffs) / len(diffs) if diffs else None


def curve_value(entry: Any) -> float:
    """Pull the p_buy out of either a Cell or a bare number."""
    if isinstance(entry, Cell):
        return entry.p if entry.p is not None else float("nan")
    return float(entry)


def _mean(values: list[float]) -> float:
    """The average of a list of numbers (nan when the list is empty)."""
    return sum(values) / len(values) if values else float("nan")


def _cell_curves(
    summary: dict[str, Any], human_cells: dict[str, dict[float, dict[str, int]]]
) -> tuple[
    list[float],
    list[float],
    dict[float, dict[str, list[float]]],
    dict[float, list[float]],
]:
    """Per-cell differences and per-level cell-mean curves vs the human table.

    Walks every (product, level) cell the condition has data for; when the
    human table also has that cell it records |p_model - p_human| under each
    parse label and appends both sides' p to the level's cell-mean lists.
    """
    diffs_strict: list[float] = []
    diffs_recovered: list[float] = []
    model_cells: dict[float, dict[str, list[float]]] = {}
    human_cells_at: dict[float, list[float]] = {}
    for product, rows in summary["matrix"].items():
        human_row = human_cells.get(product, {})
        for level, row in rows.items():
            human_cell = human_row.get(level, {})
            if not human_cell or human_cell.get("n", 0) <= 0:
                continue
            human_p = human_cell["buys"] / human_cell["n"]
            human_cells_at.setdefault(level, []).append(human_p)
            for label in ("strict", "recovered"):
                cell = row[label]
                if cell.n <= 0 or cell.p is None:
                    continue
                model_cells.setdefault(level, {"strict": [], "recovered": []})[
                    label
                ].append(cell.p)
                diff = abs(cell.p - human_p)
                (diffs_strict if label == "strict" else diffs_recovered).append(diff)
    return diffs_strict, diffs_recovered, model_cells, human_cells_at


def compare_condition(
    summary: dict[str, Any], human_table: dict[str, Any]
) -> dict[str, Any]:
    """Score one condition against the human benchmark.

    Cell MAE is the paper's way: the mean over product x level cells of
    |p_model - p_human|, counting only cells where both sides have data.
    The pooled comparisons then average curves two ways: the raw pooled
    proportion at each level and the mean of the per-product cells at each
    level.
    """
    human_cells = human_table["cells"]
    diffs_strict, diffs_recovered, model_cells, human_cells_at = _cell_curves(
        summary, human_cells
    )
    pooled_model_strict = {b["level"]: b["strict"] for b in summary["buckets"]}
    pooled_model_recovered = {b["level"]: b["recovered"] for b in summary["buckets"]}
    human_pooled: dict[float, Cell] = {}
    for product, rows in human_cells.items():
        for level, human_cell in rows.items():
            cell = human_pooled.setdefault(level, Cell())
            cell.n += human_cell["n"]
            cell.buys += human_cell["buys"]
    model_strict_curve = [
        {"level": level, "p": _mean(curves["strict"])}
        for level, curves in sorted(model_cells.items())
    ]
    model_recovered_curve = [
        {"level": level, "p": _mean(curves["recovered"])}
        for level, curves in sorted(model_cells.items())
    ]
    human_curve = [
        {"level": level, "p": _mean(values)}
        for level, values in sorted(human_cells_at.items())
    ]
    return {
        "cell_mae_strict": _mean(diffs_strict) if diffs_strict else None,
        "cell_mae_recovered": _mean(diffs_recovered) if diffs_recovered else None,
        "cells_used": len(diffs_strict),
        "pooled_mae_strict": curve_mae(pooled_model_strict, human_pooled),
        "pooled_mae_recovered": curve_mae(pooled_model_recovered, human_pooled),
        "mean_curve_mae_strict": curve_mae(
            {i["level"]: i["p"] for i in model_strict_curve},
            {i["level"]: i["p"] for i in human_curve},
        ),
        "mean_curve_mae_recovered": curve_mae(
            {i["level"]: i["p"] for i in model_recovered_curve},
            {i["level"]: i["p"] for i in human_curve},
        ),
        "model_curve_strict": model_strict_curve,
        "model_curve_recovered": model_recovered_curve,
        "human_curve": human_curve,
    }
