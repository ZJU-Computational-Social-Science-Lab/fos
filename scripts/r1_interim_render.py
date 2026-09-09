"""Markdown and JSON rendering of the R1 interim report.

Takes the report's numbers (condition summaries, benchmark comparisons and
the header context) and turns them into two files with identical content:
a human-readable interim-report.md and, on request, a machine-readable
interim-report.json twin. Pure text work - no I/O here, the caller writes
the files.

Plain-language map:

    fmt_p / fmt_ci          - One p_buy / Wilson interval as text.
    parse_lines             - The parse-rate lines of one condition.
    bucket_table            - The pooled p(buy)-per-level table as text.
    matrix_table            - One per-product p(buy) matrix as text.
    mae_block               - The benchmark MAE block of one condition.
    condition_markdown      - The whole markdown section of one condition.
    render_markdown         - Join the header and all sections into one text.
    summary_json            - One condition's numbers as JSON-able dicts.
    comparison_json         - One condition's benchmark numbers as dicts.
    analysis_json           - One condition's full JSON twin entry.
    render_json             - The whole report as JSON-able dicts.
"""

from __future__ import annotations

from typing import Any

from r1_interim_analysis import Cell  # noqa: E402


def fmt_p(value: float | None) -> str:
    """One p_buy as text: three decimals, or a dot when there is no data."""
    return f"{value:.3f}" if value is not None else "."


def fmt_ci(ci: tuple[float, float] | None) -> str:
    """One Wilson interval as '[lo, hi]' text, or a dot."""
    return f"[{ci[0]:.3f}, {ci[1]:.3f}]" if ci is not None else "."


def _fmt_level(level: float) -> str:
    """One price level as compact text ('0', '40', '200')."""
    return f"{level:g}"


def _cell(text: str) -> str:
    """Make one table-cell string safe (escape any pipes)."""
    return text.replace("|", "\\|")


def parse_lines(summary: dict[str, Any]) -> list[str]:
    """The parse-rate block of one condition, as text lines."""
    total = summary["records"]
    return [
        f"strict   parse rate {summary['strict_rate']:.1%} "
        f"({summary['strict_parsed']}/{total})",
        f"recovered parse rate {summary['recovered_rate']:.1%} "
        f"({summary['recovered_parsed']}/{total}; recovery added "
        f"{summary['recovered_only']} of the {total} records)",
    ]


def bucket_table(buckets: list[dict[str, Any]], title: str) -> list[str]:
    """One pooled p(buy)-per-level table as text lines."""
    lines = [
        f"**{title}** (pooled over products, per price level)",
        "",
        "| level | n | p(buy) | Wilson95 | n (rec.) | p(buy) (rec.) | "
        "Wilson95 (rec.) |",
        "|---|---|---|---|---|---|---|",
    ]
    for bucket in buckets:
        strict = bucket["strict"]
        recovered = bucket["recovered"]
        lines.append(
            f"| {_fmt_level(bucket['level'])} | {strict.n} | {fmt_p(strict.p)} | "
            f"{fmt_ci(strict.ci)} | {recovered.n} | {fmt_p(recovered.p)} | "
            f"{fmt_ci(recovered.ci)} |"
        )
    return lines


def matrix_table(
    matrix: dict[str, dict[float, dict[str, Cell]]],
    levels: list[float],
    label: str,
) -> list[str]:
    """One per-product p(buy) matrix as text lines (one row per product)."""
    level_heads = " | ".join(_fmt_level(level) for level in levels)
    lines = [
        f"**Per-product p(buy) matrix ({label})**",
        "",
        f"| product | {level_heads} |",
        "|---|" + "---|" * len(levels),
    ]
    for product in sorted(matrix):
        row = matrix[product]
        text = " | ".join(
            fmt_p(row[level][label].p) if level in row else "." for level in levels
        )
        lines.append(f"| {_cell(product)} | {text} |")
    return lines


def _curves_levels(comparison: dict[str, Any]) -> list[float]:
    """The sorted union of levels across the comparison's curves."""
    levels: set[float] = set()
    for key in ("model_curve_strict", "model_curve_recovered", "human_curve"):
        for item in comparison[key]:
            levels.add(float(item["level"]))
    return sorted(levels)


def _curve_dict(items: list[dict[str, Any]]) -> dict[float, float | None]:
    """One list of {level, p} entries as a {level: p} lookup."""
    return {float(item["level"]): item["p"] for item in items}


def mae_block(comparison: dict[str, Any] | None) -> list[str]:
    """The benchmark MAE block of one condition, or a clear no-data note."""
    if comparison is None:
        return ["_No benchmark comparison yet: see the benchmark section._"]
    lines = [
        "**MAE vs the Twin-2K-500 human benchmark (wave 4)**",
        "",
        "| comparison | strict | recovered |",
        "|---|---|---|",
        "| "
        + _cell(
            "cell MAE (mean over product x price cells of "
            f"|p_model - p_human|, {comparison['cells_used']} cells)"
        )
        + " | "
        f"{fmt_p(comparison['cell_mae_strict'])} | "
        f"{fmt_p(comparison['cell_mae_recovered'])} |",
        "| "
        + _cell(
            "pooled-curve MAE (model pooled p(buy) vs human pooled p(buy), per level)"
        )
        + " | "
        f"{fmt_p(comparison['pooled_mae_strict'])} | "
        f"{fmt_p(comparison['pooled_mae_recovered'])} |",
        "| "
        + _cell(
            "mean-of-cells-curve MAE (average over products of "
            "per-cell p(buy), per level)"
        )
        + " | "
        f"{fmt_p(comparison['mean_curve_mae_strict'])} | "
        f"{fmt_p(comparison['mean_curve_mae_recovered'])} |",
        "",
        "Per-level averages (mean over product cells; strict / recovered / human):",
        "",
        "| level | model (strict) | model (recovered) | human |",
        "|---|---|---|---|",
    ]
    model_strict = _curve_dict(comparison["model_curve_strict"])
    model_recovered = _curve_dict(comparison["model_curve_recovered"])
    human = _curve_dict(comparison["human_curve"])
    for level in _curves_levels(comparison):
        lines.append(
            f"| {_fmt_level(level)} | {fmt_p(model_strict.get(level))} | "
            f"{fmt_p(model_recovered.get(level))} | {fmt_p(human.get(level))} |"
        )
    return lines


def condition_markdown(
    leg: dict[str, Any],
    summary: dict[str, Any] | None,
    levels: list[float],
    comparison: dict[str, Any] | None,
) -> list[str]:
    """The whole markdown section of one condition."""
    heading = f"### {leg['depth']} / {leg['blinding']}"
    if not leg["records"]:
        return [
            heading,
            "",
            f"No sweep records yet in {leg['dir'].name}/ "
            f"({len(leg['files'])} jsonl file(s) on disk); the leg is in "
            "flight or has not started. Nothing to score yet.",
            "",
        ]
    assert summary is not None
    lines = [heading, "", f"{summary['records']:,} records"]
    lines += parse_lines(summary)
    lines += [""] + bucket_table(summary["buckets"], "p(buy) per price level")
    lines += [""] + matrix_table(summary["matrix"], levels, "strict")
    lines += [""] + matrix_table(summary["matrix"], levels, "recovered")
    lines += [""] + mae_block(comparison)
    return lines


def render_markdown(header: dict[str, Any], sections: list[list[str]]) -> str:
    """Join the header and every condition section into one report text."""
    lines = [
        f"# Interim report — {header['run_name']}",
        "",
        f"_Generated {header['generated_at']} by scripts/r1_interim_report.py "
        f"(read-only; the run directory was not modified). Run state: "
        f"{header['run_state']}._",
        "",
        "## Provenance",
        "",
        "| item | value |",
        "|---|---|",
        f"| run dir | `{header['run_dir']}` |",
        f"| model | {header['model']} |",
        f"| commit | {header['commit_sha'] or 'unknown'} |",
        f"| profile / seed / pool seed | {header.get('profile') or '-'} / "
        f"{header.get('seed') or '-'} / {header.get('pool_seed') or '-'} |",
        "| levels | "
        + ", ".join(_fmt_level(level) for level in header["levels"])
        + " |",
        f"| draws / K | {header['draws']} / {header['k']} |",
        f"| records on disk | {header['records']:,} ({header['torn']} torn line(s)) |",
        f"| strict-parsed records | {header['strict_parsed']:,} "
        f"({header['strict_rate']:.1%}) |",
        f"| recovered-parsed records | {header['recovered_parsed']:,} "
        f"({header['recovered_rate']:.1%}; recovery added "
        f"{header['recovered_only']}) |",
        f"| persona pools | {header['pools']} |",
        f"| benchmark | {header['benchmark_note']} |",
        "",
        "Strict = the tooling parser `parse_purchase` run on each raw "
        "answer. Recovered = strict plus the first-decision re-parse pass "
        "for the trailing comma-list echo failure mode.",
        "",
    ]
    for section in sections:
        lines += section
        lines += [""]
    return "\n".join(lines)


def _cell_json(cell: Cell) -> dict[str, Any]:
    """One Cell as JSON-able dict."""
    return {"n": cell.n, "buys": cell.buys, "p_buy": cell.p, "wilson95": cell.ci}


def summary_json(summary: dict[str, Any]) -> dict[str, Any]:
    """One condition's numbers as JSON-able dicts."""
    return {
        "records": summary["records"],
        "strict_parsed": summary["strict_parsed"],
        "strict_rate": summary["strict_rate"],
        "recovered_parsed": summary["recovered_parsed"],
        "recovered_only": summary["recovered_only"],
        "recovered_rate": summary["recovered_rate"],
        "buckets": [
            {
                "level": bucket["level"],
                "strict": _cell_json(bucket["strict"]),
                "recovered": _cell_json(bucket["recovered"]),
            }
            for bucket in summary["buckets"]
        ],
        "matrix": {
            product: {
                str(level): {
                    "strict": _cell_json(row["strict"]),
                    "recovered": _cell_json(row["recovered"]),
                }
                for level, row in rows.items()
            }
            for product, rows in summary["matrix"].items()
        },
    }


def comparison_json(comparison: dict[str, Any] | None) -> dict[str, Any] | None:
    """One condition's benchmark numbers as JSON-able dicts, or None."""
    if comparison is None:
        return None
    keys = (
        "cell_mae_strict",
        "cell_mae_recovered",
        "cells_used",
        "pooled_mae_strict",
        "pooled_mae_recovered",
        "mean_curve_mae_strict",
        "mean_curve_mae_recovered",
        "model_curve_strict",
        "model_curve_recovered",
        "human_curve",
    )
    return {key: comparison[key] for key in keys}


def analysis_json(
    leg: dict[str, Any],
    summary: dict[str, Any] | None,
    comparison: dict[str, Any] | None,
) -> dict[str, Any]:
    """One condition's full JSON twin entry."""
    return {
        "depth": leg["depth"],
        "blinding": leg["blinding"],
        "records": len(leg["records"]),
        "torn": leg["torn"],
        "files": leg["files"],
        "summary": summary_json(summary) if summary is not None else None,
        "comparison": comparison_json(comparison),
    }


def render_json(
    header: dict[str, Any], sections: list[dict[str, Any]]
) -> dict[str, Any]:
    """The machine-readable twin: the whole report as JSON-able dicts."""
    return {"header": header, "conditions": sections}
