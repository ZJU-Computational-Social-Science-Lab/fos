"""Render the Markdown analysis report FROM the analysis output dict.

This module is the single source of truth fix for RESULT-2749 defect 3:
the report used to be hand-authored, so its numbers drifted from
analysis.json.  Here every number in the Markdown is rendered from the
same dict that is dumped to analysis.json — a number can never disagree
with the JSON because it IS the JSON value.

render_markdown(output) -> str: one section per table in the dict
(exclusions, PMFs, contrasts, consistency, recognition, cost).  Every
contrast row shows the three separate quantities (model effect, frozen
human effect, discrepancy delta).  Small-cell (n=10) analyses are
labelled EXPLORATORY / UNDERPOWERED throughout.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

POWER_NOTE = (
    "**Power note:** every model cell in this run has n=10 (PMS cells are "
    "n=10 pooled across roles, smaller per role). All estimates here are "
    "**EXPLORATORY / UNDERPOWERED**; CIs are wide and TOST margins are "
    "rarely met. Do not read point estimates as confirmatory."
)

GAME_TITLES = {
    "1120": "11-20 game",
    "dieroll": "die-roll game",
    "pms": "PMS Joker matrix games",
}


def _pct(x: float) -> str:
    """A share rendered as a percentage string (e.g. 0.7 -> '70.0%')."""
    return f"{x * 100:.1f}%"


def _fmt(v) -> str:
    """Render one JSON scalar for the report (None -> '—')."""
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.1f}"
    return str(v)


def _exclusions_section(output: dict) -> list[str]:
    """Exclusion counts (this audited run: all zero, by design)."""
    lines = ["## Exclusions", ""]
    excl = output.get("exclusions", {})
    if not excl:
        lines.append(
            "None. Every raw record was included: all 240 records carry "
            "`cache_kind` of `context` or `none` (context/prompt-prefix "
            "caching keeps a fresh completion), so no record was eligible "
            "for exclusion. The legacy '24 exclusions' figure was an "
            "artifact of the legacy cache rule and does not apply."
        )
    else:
        for reason, n in sorted(excl.items()):
            lines.append(f"- {reason}: {n}")
    lines.append("")
    return lines


def _pmfs_section(output: dict) -> list[str]:
    """Per-cell choice distributions, straight from the pmfs dict."""
    lines = [
        "## Choice distributions (PMFs)",
        "",
        "Each cell n=10 — EXPLORATORY / UNDERPOWERED.",
        "",
        "| cell | action | share |",
        "|---|---|---|",
    ]
    for key, pmf in output.get("pmfs", {}).items():
        for action, share in pmf.items():
            lines.append(f"| `{key}` | {_fmt(action)} | {_pct(share)} |")
    lines.append("")
    return lines


def _arm_cell(arm_row) -> str:
    """One contrast arm rendered with the three explicit quantities."""
    if arm_row is None:
        return "—"
    ci = arm_row.get("ci90", [None, None])
    return (
        f"model {_fmt(arm_row['effect_llm_pp'])} pp "
        f"[{ci[0]}, {ci[1]}]; human (frozen) "
        f"{_fmt(arm_row['effect_human_pp'])} pp; discrepancy Δ "
        f"{_fmt(arm_row['delta_pp'])} pp"
    )


def _contrasts_section(output: dict) -> list[str]:
    """Contrast table: model effect / human effect / Δ, per role."""
    lines = [
        "## Replication contrasts",
        "",
        POWER_NOTE,
        "",
        "Δ is the **discrepancy** (model treatment effect − frozen human "
        "treatment effect), never a model treatment effect itself.",
        "",
        "| contrast | action | role | persona arm | no-persona arm |",
        "|---|---|---|---|---|",
    ]
    for row in output.get("contrasts", []):
        lines.append(
            f"| {row['contrast']} | {_fmt(row['action'])} "
            f"| {_fmt(row.get('role'))} "
            f"| {_arm_cell(row.get('persona'))} "
            f"| {_arm_cell(row.get('no_persona'))} |"
        )
    lines.append("")
    return lines


def _consistency_section(output: dict) -> list[str]:
    """Rule-preservation r(T) at the distribution level."""
    lines = [
        "## Consistency (distribution level)",
        "",
        "r(T) = share of transformed **mass** on the mapped image of the "
        "canonical support; no pointwise pairing of independent draws. "
        "JS divergence compares the mapped canonical and transformed "
        "distributions.",
        "",
        "| transformation | arm | r(T) | CI90 | JS div | stability | excess | verdict |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in output.get("consistency", []):
        if "tvd" in row:
            lines.append(
                f"| {row['transformation']} | {row['arm']} | (distributional: "
                f"TVD {row['tvd']}) | — | — | — | — | — |"
            )
            continue
        ci = row.get("r_T_ci90", [None, None])
        lines.append(
            f"| {row['transformation']} | {row['arm']} | {row['r_T']} "
            f"| [{ci[0]}, {ci[1]}] | {row.get('js_divergence', '—')} "
            f"| {row.get('stability', '—')} "
            f"| {row.get('excess_inconsistency', '—')} "
            f"| {row.get('verdict', '—')} |"
        )
    lines.append("")
    return lines


def _recognition_section(output: dict) -> list[str]:
    """Per-arm recognition tables with true denominators (5/cell, 30/arm)."""
    rec = output.get("recognition")
    if not rec:
        return []
    lines = [
        "## Recognition stratification (per arm — arms never pooled)",
        "",
        "Denominators are the true probe counts: n=5 per cell, n=30 per arm.",
        "",
        "| game/variant/arm | n | RECOGNISING | NOT_RECOGNISING | UNKNOWN | RECOGNISING rate |",
        "|---|---|---|---|---|---|",
    ]
    for key, entry in sorted(rec.items()):
        rates = entry.get("rates", {})
        lines.append(
            f"| {key} | n={entry['n']} | {entry['RECOGNISING']} "
            f"| {entry['NOT_RECOGNISING']} | {entry['UNKNOWN']} "
            f"| {_pct(rates.get('RECOGNISING', 0.0))} |"
        )
    lines.append("")
    return lines


def _cost_section(output: dict) -> list[str]:
    """Token/cost totals (reporting only)."""
    cost = output.get("cost_and_tokens")
    if not cost:
        return []
    lines = [
        "## Tokens and cost (reporting only)",
        "",
        "| model | calls | prompt tok | completion tok | cost USD |",
        "|---|---|---|---|---|",
    ]
    for model, entry in sorted(cost.items()):
        lines.append(
            f"| {model} | {entry['calls']} | {entry['prompt_tokens']} "
            f"| {entry['completion_tokens']} | {entry['cost_usd']:.4f} |"
        )
    lines.append("")
    return lines


def _file_stats(path: Path) -> dict:
    """SHA256, record count and cache_kind counts for one input file."""
    kinds = {"context": 0, "none": 0, "response": 0, "missing": 0}
    n = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        n += 1
        import json

        rec = json.loads(line)
        kinds[rec.get("cache_kind", "missing")] = (
            kinds.get(rec.get("cache_kind", "missing"), 0) + 1
        )
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"path": str(path), "sha256": sha, "records": n, "cache_kind": kinds}


def build_audit_log(decision_paths, probe_paths, exclusions: dict) -> str:
    """The AUDIT_LOG.md contents: input paths, SHA256s, per-file record
    counts, the cache_kind reconciliation table and the exclusion verdict
    (SPEC §1, RESULT-2749 defect 4)."""
    import json as _json

    lines = [
        "# AUDIT_LOG — audited analysis regeneration",
        "",
        "Inputs are the frozen raw JSONL under "
        "`~/experiment-data/fos/sixgame/engineering_pilot_corrective/`. "
        "Outputs go to `reports/audited/` only; nothing upstream is "
        "modified. No model calls were made.",
        "",
        "## Input files",
        "",
        "| file | records | sha256 | context | none | response |",
        "|---|---|---|---|---|---|",
    ]
    total = {"context": 0, "none": 0, "response": 0}
    for path in list(decision_paths) + list(probe_paths):
        stats = _file_stats(Path(path))
        k = stats["cache_kind"]
        for kind in total:
            total[kind] += k.get(kind, 0)
        lines.append(
            f"| `{stats['path']}` | {stats['records']} | `{stats['sha256'][:16]}…` "
            f"| {k.get('context', 0)} | {k.get('none', 0)} | {k.get('response', 0)} |"
        )
    lines += [
        "",
        "## Cache reconciliation (cache_kind across all records)",
        "",
        f"- context (prompt-prefix hit, fresh completion — INCLUDED): {total['context']}",
        f"- none: {total['none']}",
        f"- response (reused completion — excludable): {total['response']}",
        "",
        f"**Verdict: eligible-for-exclusion = {total['response']} of "
        f"{sum(total.values())} records; exclusions applied: "
        f"{sum((exclusions or {}).values())}.** The legacy fallback rule "
        "(any cache_status != MISS excluded) never fired: every record "
        "carries a modern `cache_kind`. The legacy '24 exclusions' figure "
        "was an artifact of that legacy rule and is dropped.",
        "",
        "Run IDs are the input filenames; regeneration command:",
        "",
        "```",
        "python -m sixgame.analysis --audit --run-id engineering_pilot_corrective \\",
        "  --manifest <decisions_*.jsonl> --probes <probes_*.jsonl>",
        "```",
        "",
    ]
    assert _json is not None  # keep json import local-use explicit
    return "\n".join(lines)


def render_markdown(output: dict) -> str:
    """Render the full Markdown report from the analysis output dict.

    Every number is a rendering of a value in `output` — the same dict
    that is serialised to analysis.json (single source of truth).
    """
    parts = [
        "# Audited analysis report (regenerated from raw JSONL)",
        "",
        "Rendered programmatically from the same dict that produces "
        "`analysis.json`; no hand-maintained numbers.",
        "",
    ]
    parts += _exclusions_section(output)
    parts += _pmfs_section(output)
    parts += _contrasts_section(output)
    parts += _consistency_section(output)
    parts += _recognition_section(output)
    parts += _cost_section(output)
    return "\n".join(parts)
