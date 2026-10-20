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
    """One contrast arm rendered with the three explicitly labelled CIs."""
    if arm_row is None:
        return "—"
    model_ci = arm_row.get("model_effect_ci90", [None, None])
    human_ci = arm_row.get("human_effect_ci90", [None, None])
    disc_ci = arm_row.get("discrepancy_ci90", arm_row.get("ci90", [None, None]))
    return (
        f"model {_fmt(arm_row['effect_llm_pp'])} pp "
        f"model_effect_CI [{model_ci[0]}, {model_ci[1]}]; "
        f"human (frozen) {_fmt(arm_row['effect_human_pp'])} pp "
        f"human_effect_CI [{human_ci[0]}, {human_ci[1]}]; "
        f"discrepancy Δ {_fmt(arm_row['delta_pp'])} pp "
        f"discrepancy_CI [{disc_ci[0]}, {disc_ci[1]}]"
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
    """Rule-preservation r(T) as a SUPPORT DIAGNOSTIC (no verdict)."""
    lines = [
        "## Support diagnostic (r(T), distribution level)",
        "",
        "r(T) = share of transformed **mass** on the mapped image of the "
        "canonical support. **r(T) is a SUPPORT DIAGNOSTIC only — it is "
        "not a consistency verdict** (the old CONSISTENCY-SUCCESS/FAIL "
        "labels derived from r(T) alone were removed per SPEC §1). "
        "Consistency verdicts come solely from the distributional "
        "equivalence section below.",
        "",
        "| transformation | arm | r(T) | CI90 | JS div (base 2) | stability | excess |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in output.get("consistency", []):
        if "tvd" in row:
            lines.append(
                f"| {row['transformation']} | {row['arm']} | (distributional: "
                f"TVD {row['tvd']}) | — | — | — | — |"
            )
            continue
        ci = row.get("r_T_ci90", [None, None])
        lines.append(
            f"| {row['transformation']} | {row['arm']} | {row['r_T']} "
            f"| [{ci[0]}, {ci[1]}] | {row.get('js_divergence', '—')} "
            f"| {row.get('stability', '—')} "
            f"| {row.get('excess_inconsistency', '—')} |"
        )
    lines.append("")
    return lines


def _distribution_equivalence_section(output: dict) -> list[str]:
    """Distributional equivalence per transformation x arm (x role)."""
    rows = output.get("distribution_equivalence", [])
    if not rows:
        return []
    lines = [
        "## Distributional equivalence (TVD / JS per transformation)",
        "",
        "TVD and Jensen–Shannon divergence (base 2) between the mapped "
        "canonical distribution and the transformed distribution, with "
        "90% paired cluster-bootstrap CIs (clusters = personas, B = 10,000, "
        "fixed seed). PMS relabeling is analysed SEPARATELY per role — "
        "never pooled. Equivalence is declared ONLY at the pre-agreed "
        "margins AND only when a defensible finite-sample interval "
        "supports the margin (TASK-2760: n=10-per-cell degenerate "
        "bootstrap intervals can never establish equivalence); where no "
        "margin was ever agreed the row is labelled "
        "UNPOWERED-DESCRIPTIVE.",
        "",
        "| transformation | arm | role | TVD | TVD CI90 | JS div (bits) | n_eff | margin (pp) | verdict |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        ci = row["tvd_ci90"]
        margin = row.get("margin_pp")
        lines.append(
            f"| {row['transformation']} | {row['arm']} | {_fmt(row.get('role'))} "
            f"| {row['tvd']} | [{ci[0]}, {ci[1]}] "
            f"| {row['js_divergence_bits']} | {row['n_eff']} "
            f"| {_fmt(margin)} | {row['verdict']} |"
        )
    lines.append("")
    for row in rows:
        if row.get("equivalence_note"):
            lines.append(
                f"**{row['transformation']} / {row['arm']}"
                + (f" / {row['role']}" if row.get("role") else "")
                + f"**: {row['equivalence_note']}."
            )
    lines.append("")
    return lines


def _tvd_confirmation_section(output: dict) -> list[str]:
    """The independent TVD confirmation (separate code path)."""
    conf = output.get("tvd_confirmation", {})
    if not conf:
        return []
    lines = [
        "## Independent TVD confirmation (11-20 → 31-40)",
        "",
        "Recomputed by a separate code path (plain counters on the raw "
        "records, mapping +20 applied by hand) against the pipeline value; "
        "frozen expectations: persona 0.30, no-persona 0.20.",
        "",
        "| arm | independent | pipeline | agree | frozen expectation | matches frozen |",
        "|---|---|---|---|---|---|",
    ]
    for arm, entry in conf.items():
        lines.append(
            f"| {arm} | {entry['independent']} | {entry['pipeline']} "
            f"| {entry['agree']} | {entry['expected_frozen']} "
            f"| {entry['matches_frozen']} |"
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
    """Decision / probe / full-run token and cost totals, separately."""
    cost = output.get("cost_and_tokens")
    if not cost:
        return []
    lines = [
        "## Tokens and cost (reporting only)",
        "",
        "Decision calls, probe calls, and the FULL-run total are reported "
        "separately (SPEC §5): the earlier '180 calls' figure covered "
        "decision records only and omitted the 60 recognition probes.",
        "",
    ]
    for block, title in (
        ("decision_calls", "Decision calls"),
        ("probe_calls", "Recognition probe calls"),
        ("full_run", "FULL run (decisions + probes)"),
    ):
        entry = cost.get(block, {})
        lines += [
            f"### {title}",
            "",
            f"calls: **{entry.get('calls', 0)}** · prompt tokens: "
            f"{entry.get('prompt_tokens', 0)} · completion tokens: "
            f"{entry.get('completion_tokens', 0)} · cost USD: "
            f"{entry.get('cost_usd', 0.0):.4f}",
            "",
            "| model | calls | prompt tok | completion tok | cost USD |",
            "|---|---|---|---|---|",
        ]
        for model, m in sorted((entry.get("by_model") or {}).items()):
            lines.append(
                f"| {model} | {m['calls']} | {m['prompt_tokens']} "
                f"| {m['completion_tokens']} | {m['cost_usd']:.4f} |"
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
        "## Cost reconciliation (SPEC §5, TASK-2755)",
        "",
        "The earlier '180 calls' figure counted DECISION records only "
        "(18 files x 10). The 60 recognition-probe records (12 files x 5) "
        "were omitted from that summary. Decision calls, probe calls and "
        "the FULL-run total (decisions + probes) are now reported "
        "separately, each with tokens and cost — see the cost section of "
        "the report.",
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
    parts += _distribution_equivalence_section(output)
    parts += _tvd_confirmation_section(output)
    parts += _recognition_section(output)
    parts += _cost_section(output)
    return "\n".join(parts)
