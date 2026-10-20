"""Analysis for the three-game experiment: tables from raw JSONL alone.

Entry point: ``python -m sixgame.analysis --manifest <run.jsonl ...>``
(or ``--exploratory`` to ingest the legacy condition files).  Everything
regenerates from the raw per-cell JSONL records — nothing is cached.

What it produces (each a printed section and, with --out-dir, a file):

- per-cell choice distributions (PMFs) with exclusion counts;
- replication contrasts: for each prespecified treatment pair the LLM
  effect minus the frozen human effect (delta) with 90% cluster-bootstrap
  CIs (clusters = personas), plus TOST at the contrast's frozen margin;
- consistency: the rule-preservation rate r(T) (share of draws whose
  choice equals the rule-implied mapping of the canonical play) with
  CIs, and excess inconsistency against the model's own identical-prompt
  stability; die-roll tiers are judged distributionally (TVD);
- recognition stratification: replication cells split by whether the
  model coded as RECOGNISING on the probe;
- exclusions and token/cost report (reporting only — no stopping rule).

Exclusions (ANALYSIS_PLAN section 0, exhaustive): parse failure, choice
outside the legal set, refusal/empty completion, truncated completion
(finish_reason = length), and gateway RESPONSE caches only.

Rule change (task 2726, per ANALYSIS_PLAN): provider context/prompt-
prefix caching (DeepSeek automatic context caching — records with
``cache_kind == "context"``) is NOT an exclusion: the completion is
still freshly sampled; only the prompt prefix is reused.  Only a
gateway response cache (``cache_kind == "response"`` — a reused
completion body) is excluded.  Legacy records without a ``cache_kind``
field keep the old rule (any cache_status other than MISS is excluded).
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Sequence

try:  # works both as a package module and run from the scripts directory
    from sixgame import benchmarks
    from sixgame.games import (
        level_k_inverted_table,
        variant_spec,
    )
    from sixgame.probes import code_recognition
    from sixgame.stats import (
        bootstrap_ci,
        tost_equivalent,
        tvd,
    )
    from sixgame.report import build_audit_log, render_markdown
except ImportError:  # pragma: no cover - direct execution layout
    import benchmarks
    from games import (
        level_k_inverted_table,
        variant_spec,
    )
    from probes import code_recognition
    from report import build_audit_log, render_markdown
    from stats import (
        bootstrap_ci,
        tost_equivalent,
        tvd,
    )

ACTIONS_1120 = tuple(range(11, 21))

#: Prespecified replication contrasts: name -> (game, control, treatment,
#: actions, benchmark effect dict, delta margin pp, human SE pp, role).
#: role is the record-key role the contrast is computed within (H3 must
#: never pool Row and Column players — RESULT-2749 defect 1); None pools
#: all roles for the non-role games, whose records carry role=None.
CONTRASTS = {
    "H1_basic_to_costless": (
        "1120",
        "basic",
        "costless",
        (17, 18, 19, 20),
        benchmarks.EFFECTS_1120["basic_to_costless"],
        benchmarks.DELTA_1120_PP,
        benchmarks.SE_HUMAN_1120_PP,
    ),
    "H1_basic_to_cycle": (
        "1120",
        "basic",
        "cycle",
        (17, 18, 19, 20),
        benchmarks.EFFECTS_1120["basic_to_cycle"],
        benchmarks.DELTA_1120_PP,
        benchmarks.SE_HUMAN_1120_PP,
    ),
    "H2_private_to_public": (
        "dieroll",
        "private",
        "public",
        (6,),
        {6: benchmarks.EFFECT_DIE_SHARE6_PP},
        benchmarks.DELTA_DIE_PP,
        benchmarks.SE_HUMAN_DIE_PP,
    ),
    # PMS actions are the string labels "A1" | "A2" | "J" (games.PMS_ACTIONS),
    # matching the `choice` key of the raw records. Integer indices silently
    # matched nothing, zeroing every H3 effect (RESULT-2749 defect 1).
    "H3_pms_G1_to_G4_row": (
        "pms",
        "G1",
        "G4",
        ("A1", "A2", "J"),
        {a: v for a, v in zip(("A1", "A2", "J"), benchmarks.EFFECT_PMS_PP["Row"])},
        benchmarks.DELTA_PMS_PP,
        benchmarks.SE_HUMAN_PMS_PP,
        "Row",
    ),
    "H3_pms_G1_to_G4_column": (
        "pms",
        "G1",
        "G4",
        ("A1", "A2", "J"),
        {a: v for a, v in zip(("A1", "A2", "J"), benchmarks.EFFECT_PMS_PP["Column"])},
        benchmarks.DELTA_PMS_PP,
        benchmarks.SE_HUMAN_PMS_PP,
        "Column",
    ),
}

# Non-role contrasts carry role=None: their records have role=None anyway
# and pooling is the prespecified estimand for the 11-20 and die-roll games.
CONTRASTS["H1_basic_to_costless"] = (
    "1120",
    "basic",
    "costless",
    (17, 18, 19, 20),
    benchmarks.EFFECTS_1120["basic_to_costless"],
    benchmarks.DELTA_1120_PP,
    benchmarks.SE_HUMAN_1120_PP,
    None,
)
CONTRASTS["H1_basic_to_cycle"] = (
    "1120",
    "basic",
    "cycle",
    (17, 18, 19, 20),
    benchmarks.EFFECTS_1120["basic_to_cycle"],
    benchmarks.DELTA_1120_PP,
    benchmarks.SE_HUMAN_1120_PP,
    None,
)
CONTRASTS["H2_private_to_public"] = (
    "dieroll",
    "private",
    "public",
    (6,),
    {6: benchmarks.EFFECT_DIE_SHARE6_PP},
    benchmarks.DELTA_DIE_PP,
    benchmarks.SE_HUMAN_DIE_PP,
    None,
)

#: Frozen consistency transformations: name -> (game, canonical, transformed,
#: mapping kind).  Pointwise mappings come from games.variant_spec.
TRANSFORMATIONS = {
    "1120_r31-40": ("1120", "basic", "r31-40", "pointwise"),
    "1120_r21-30": ("1120", "basic", "r21-30", "pointwise"),
    "1120_r41-50": ("1120", "basic", "r41-50", "pointwise"),
    "1120_r51-60": ("1120", "basic", "r51-60", "pointwise"),
    "1120_inverted": ("1120", "basic", "inverted", "pointwise"),
    "dieroll_neutral_tierA": ("dieroll", "private", "neutral", "distributional"),
    "dieroll_stake10_tierB": ("dieroll", "private", "stake10", "distributional"),
    "pms_relabel": ("pms", "G1", "relabel", "pointwise"),
}


def load_records(paths: Sequence[Path]) -> list[dict]:
    """Read all JSONL records from the given files (bad lines skipped and
    counted — never silent: the count is reported)."""
    records = []
    bad = 0
    for path in paths:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                bad += 1
    if bad:
        print(f"WARNING: skipped {bad} unparseable JSONL lines")
    return records


def apply_exclusions(records: list[dict]) -> tuple[list[dict], dict]:
    """Apply the exhaustive exclusion list; return (kept, exclusion_counts)."""
    kept, counts = [], Counter()
    for r in records:
        if r.get("error"):
            counts["error"] += 1
        elif r.get("choice") is None:
            counts["parse_failure"] += 1
        elif r.get("truncated") or r.get("finish_reason") == "length":
            counts["truncated"] += 1
        elif _is_response_cache(r):
            counts["cache_hit"] += 1
        else:
            kept.append(r)
    return kept, dict(counts)


def _is_response_cache(r: dict) -> bool:
    """True only for gateway response caches (see module docstring).

    Context/prompt-prefix caching keeps the record.  Legacy records
    with no cache_kind fall back to the old exclusion rule (see the
    module docstring).
    """
    kind = r.get("cache_kind")
    if kind is not None:
        return kind == "response"
    # Legacy records (no cache_kind): fall back to the old rule — any
    # cache_status other than MISS counts as a cache hit and is excluded.
    return r.get("cache_status", "MISS") != "MISS"


def cell_key(r: dict) -> tuple:
    """The (game, variant, arm, model) a record belongs to."""
    return (r["game"], r["variant"], r["arm"], r["model"])


def pmf_for(records: list[dict], actions: Sequence) -> dict:
    """The choice distribution of one cell as {choice: share}."""
    counts = Counter(r["choice"] for r in records)
    total = sum(counts.values())
    if total == 0:
        return {}
    return {a: counts.get(a, 0) / total for a in actions}


def persona_clusters(records: list[dict], target) -> list[list[float]]:
    """Group 1/0 target-hit indicators by persona (bootstrap clusters)."""
    groups: dict[str, list[float]] = defaultdict(list)
    for r in records:
        groups[r["persona_id"]].append(1.0 if r["choice"] == target else 0.0)
    return list(groups.values())


def llm_effect(
    clusters_c: list[list[float]],
    clusters_t: list[list[float]],
    target,
    boot: int,
    seed: int,
) -> tuple[float, float, float]:
    """The LLM treatment effect on a target action's share, with its 90%
    cluster-bootstrap CI (treatment minus control)."""

    def stat(cs: list[list[list[float]]]) -> float:
        control, treatment = cs
        n_c = sum(len(c) for c in control) or 1
        n_t = sum(len(c) for c in treatment) or 1
        return (
            sum(v for c in treatment for v in c) / n_t
            - sum(v for c in control for v in c) / n_c
        )

    return bootstrap_ci([clusters_c, clusters_t], stat, n_boot=boot, seed=seed)


def cell_records_for_arm(
    cell_records: dict, game: str, variant: str, arm: str, role: str | None = None
) -> list:
    """All kept records for a (game, variant, arm) across every model.

    With role given, only records whose `role` key matches are returned
    (H3 contrasts must never pool Row and Column players).

    Bug B1 in RESULT-2723: cells are keyed by the 4-tuple
    (game, variant, arm, model) but the tables looked up 3-tuples, so
    every lookup missed.  Pooling across models matches how the
    contrast/consistency benchmarks are prespecified (per design, not
    per model).
    """
    pooled: list = []
    for key, recs in cell_records.items():
        if tuple(key)[:3] != (game, variant, arm):
            continue
        if role is not None:
            recs = [r for r in recs if r.get("role") == role]
        pooled.extend(recs)
    return pooled


def contrast_table(cell_records: dict, boot: int, seed: int) -> list[dict]:
    """All prespecified replication contrasts with delta, CI, TOST."""
    rows = []
    for name, (
        game,
        control,
        treatment,
        actions,
        human,
        delta,
        se_h,
        role,
    ) in CONTRASTS.items():
        for action in actions:
            row: dict = {
                "contrast": name,
                "action": action,
                "role": role,
                "delta_margin_pp": delta,
            }
            for arm in ("persona", "no_persona"):
                rec_c = cell_records_for_arm(cell_records, game, control, arm, role)
                rec_t = cell_records_for_arm(cell_records, game, treatment, arm, role)
                if not rec_c or not rec_t:
                    row[arm] = None
                    continue
                effect, lo, hi = llm_effect(
                    persona_clusters(rec_c, action),
                    persona_clusters(rec_t, action),
                    action,
                    boot,
                    seed,
                )
                delta_hat = (effect * 100.0) - human[action]
                # propagate: widen the CI half-width by the human SE (pp)
                half = (hi - lo) / 2 * 100.0
                total_half = (half**2 + (1.645 * se_h) ** 2) ** 0.5
                row[arm] = {
                    "effect_llm_pp": round(effect * 100.0, 2),
                    "effect_human_pp": human[action],
                    "delta_pp": round(delta_hat, 2),
                    "ci90": [
                        round(delta_hat - total_half, 2),
                        round(delta_hat + total_half, 2),
                    ],
                    "tost_within_delta": tost_equivalent(
                        delta_hat - total_half, delta_hat + total_half, delta
                    ),
                }
            rows.append(row)
    return rows


def _human_n(game: str, cell: str) -> int:
    """The benchmark human sample size for one control cell."""
    if game == "1120":
        return benchmarks.N_HUMAN_1120[cell]
    if game == "dieroll":
        return benchmarks.N_HUMAN_DIE[cell]
    return 96


def consistency_table(cell_records: dict, boot: int, seed: int) -> list[dict]:
    """Rule-preservation rates r(T) and excess inconsistency per transform."""
    rows = []
    inv_table = level_k_inverted_table()
    for name, (game, canonical, transformed, kind) in TRANSFORMATIONS.items():
        for arm in ("persona", "no_persona"):
            can = cell_records_for_arm(cell_records, game, canonical, arm)
            tra = cell_records_for_arm(cell_records, game, transformed, arm)
            if not can or not tra:
                continue
            row = {"transformation": name, "arm": arm, "kind": kind}
            if kind == "distributional":
                # Die-roll tiers: compare full report distributions (TVD);
                # r(T) is not per-choice (ANALYSIS_PLAN section 2.1).
                spec = variant_spec(game, canonical)
                pmf_c = pmf_for(can, spec.actions)
                pmf_t = pmf_for(tra, spec.actions)
                row["tvd"] = round(tvd(pmf_c, pmf_t), 4)
                row["tier_margin_pp"] = (
                    benchmarks.DELTA_DIE_TIER_A_PP
                    if "tierA" in name
                    else benchmarks.DELTA_DIE_TIER_B_PP
                )
                rows.append(row)
                continue
            # r(T), distribution level (RESULT-2749 defect 2 / SPEC §4):
            # the share of transformed MASS on the image of the canonical
            # support under the frozen mapping — never pointwise pairing
            # of independent draws.  The JS divergence between the mapped
            # canonical distribution and the transformed distribution is
            # reported alongside.
            image = _rule_preserving_set(game, can, transformed, inv_table)
            pres = [1.0 if r["choice"] in image else 0.0 for r in tra]
            clusters = defaultdict(list)
            for r, hit in zip(tra, pres):
                clusters[r["persona_id"]].append(hit)
            point, lo, hi = bootstrap_ci(
                list(clusters.values()),
                lambda cs: (
                    sum(v for c in cs for v in c) / (sum(len(c) for c in cs) or 1)
                ),
                n_boot=boot,
                seed=seed,
            )
            stability = _stability(can, boot, seed)
            one_minus_r = 1.0 - point
            excess = one_minus_r - (1.0 - stability)
            row.update(
                {
                    "image_set": sorted(image),
                    "js_divergence": round(
                        _js_divergence(game, can, tra, transformed), 4
                    ),
                    "r_T": round(point, 4),
                    "r_T_ci90": [round(lo, 4), round(hi, 4)],
                    "stability": round(stability, 4),
                    "excess_inconsistency": round(excess, 4),
                    "verdict": (
                        "CONSISTENCY-SUCCESS"
                        if lo > 0.5 and excess <= 0
                        else "CONSISTENCY-FAIL"
                        if hi < 0.5 or excess > 0
                        else "INCONCLUSIVE"
                    ),
                }
            )
            rows.append(row)
    return rows


def _mapping_for(game: str, transformed: str, inv_table: dict):
    """The frozen pointwise mapping for a transformation (game-specific)."""
    spec = variant_spec(game, transformed)
    return spec.mapping


def _rule_preserving_set(
    game: str, can: list[dict], transformed: str, inv_table: dict
) -> set:
    """The set of transformed choices counted as rule-preserving.

    For range shifts: the image of the canonical support under x -> x+10.
    For the inverted game: the image of the canonical support under
    x -> 31 - x (the level-k table).  For PMS relabel: the pi images of
    the canonical actions.
    """
    spec_t = variant_spec(game, transformed)
    mapping = spec_t.mapping
    return {mapping(r["choice"]) for r in can}


def _stability(can: list[dict], boot: int, seed: int) -> float:
    """Identical-prompt stability: share of persona pairs of draws that
    agree on the canonical cell (the model's own retest noise)."""
    by_persona: dict[str, list] = defaultdict(list)
    for r in can:
        by_persona[r["persona_id"]].append(r["choice"])
    agree = total = 0
    for choices in by_persona.values():
        for i in range(len(choices)):
            for j in range(i + 1, len(choices)):
                total += 1
                agree += 1 if choices[i] == choices[j] else 0
    return agree / total if total else 0.0


def recognition_stratification(probe_records: list[dict]) -> dict:
    """Recognition coding per (game, variant, ARM) — arms are never pooled
    (RESULT-2749 defect 5).  Each cell reports the true denominator n
    (5 probes per cell, 30 per arm) with counts and rates."""
    out: dict[str, dict] = defaultdict(
        lambda: {"n": 0, "RECOGNISING": 0, "NOT_RECOGNISING": 0, "UNKNOWN": 0}
    )
    for r in probe_records:
        key = f"{r['game']}/{r['variant']}/{r['arm']}"
        code = code_recognition(r.get("raw_content"))
        out[key]["n"] += 1
        out[key][code] += 1
    for entry in out.values():
        n = entry["n"] or 1
        entry["rates"] = {
            code: round(entry[code] / n, 4)
            for code in ("RECOGNISING", "NOT_RECOGNISING", "UNKNOWN")
        }
    return dict(out)


def _js_divergence(
    game: str, can: list[dict], tra: list[dict], transformed: str
) -> float:
    """JS divergence (base e) between the mapped canonical distribution and
    the transformed distribution over the transformed action set."""
    import math

    spec_t = variant_spec(game, transformed)
    actions = list(spec_t.actions)
    mapping = spec_t.mapping
    p = {a: 0.0 for a in actions}
    q = {a: 0.0 for a in actions}
    for r in can:
        image = mapping(r["choice"])
        p[image if image in p else "_off_set"] = (
            p.get(image if image in p else "_off_set", 0.0) + 1.0
        )
    for r in tra:
        c = r["choice"]
        q[c if c in q else "_off_set"] = q.get(c if c in q else "_off_set", 0.0) + 1.0

    def normalise(d):
        t = sum(d.values()) or 1.0
        return {k: v / t for k, v in d.items()}

    p, q = normalise(p), normalise(q)
    js = 0.0
    for a in set(p) | set(q):
        m = (p[a] + q[a]) / 2.0
        for px in (p[a], q[a]):
            if px > 0 and m > 0:
                js += 0.5 * px * math.log(px / m)
    return js


def cost_report(records: list[dict]) -> dict:
    """Token and cost totals per model (reporting only, never a control)."""
    totals: dict[str, dict] = defaultdict(
        lambda: {
            "calls": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "cost_usd": 0.0,
        }
    )
    for r in records:
        entry = totals[r["model"]]
        entry["calls"] += 1
        entry["prompt_tokens"] += r.get("prompt_tokens") or 0
        entry["completion_tokens"] += r.get("completion_tokens") or 0
        entry["cost_usd"] += r.get("cost_usd") or 0.0
    return dict(totals)


def load_exploratory(paths: Sequence[Path]) -> list[dict]:
    """Ingest legacy condition JSONL into the standard record shape.

    cond2 files are the name-only (no-persona) arm; cond3 files are the
    full-persona arm; each row carries chosen_number on the 11-20 game.
    """
    records = []
    for path in paths:
        name = Path(path).name
        model = _model_from_filename(name)
        cond = name.rsplit("_cond", 1)[1].split("_")[0]
        arm = "no_persona" if cond == "2" else "persona"
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("chosen_number") is None:
                continue
            records.append(
                {
                    "game": "1120",
                    "variant": "basic",
                    "arm": arm,
                    "model": model,
                    "persona_id": row["username"],
                    "draw_id": 0,
                    "role": None,
                    "choice": row["chosen_number"],
                    "succeeded": True,
                    "cache_status": "MISS",
                    "truncated": False,
                }
            )
    return records


def _model_from_filename(name: str) -> str:
    """Recover the model id from a legacy results filename."""
    for known in (
        "anthropic_claude-sonnet-5",
        "deepseek-v4-flash",
        "openai_gpt-5.6-luna",
    ):
        if name.startswith(known):
            return known.replace("anthropic_claude", "anthropic/claude").replace(
                "openai_gpt", "openai/gpt"
            )
    return name.rsplit("_cond", 1)[0]


def run_analysis(
    decision_paths: Sequence[Path] = (),
    probe_paths: Sequence[Path] = (),
    exploratory_paths: Sequence[Path] = (),
    boot: int = 10_000,
    seed: int = 0,
) -> dict:
    """Regenerate every output table from raw JSONL alone."""
    records = load_records(decision_paths)
    kept, exclusions = apply_exclusions(records)
    cell_records: dict[tuple, list[dict]] = defaultdict(list)
    for r in kept:
        cell_records[cell_key(r)].append(r)
    output = {
        "exclusions": exclusions,
        "pmfs": {
            str(key): pmf_for(recs, variant_spec(key[0], key[1]).actions)
            for key, recs in sorted(cell_records.items())
        },
        "contrasts": contrast_table(cell_records, boot, seed),
        "consistency": consistency_table(cell_records, boot, seed),
        "cost_and_tokens": cost_report(records),
    }
    probe_records = load_records(probe_paths)
    if probe_records:
        output["recognition"] = recognition_stratification(probe_records)
    if exploratory_paths:
        exp = load_exploratory(exploratory_paths)
        exp_kept, exp_excl = apply_exclusions(exp)
        exp_cells: dict[tuple, list[dict]] = defaultdict(list)
        for r in exp_kept:
            exp_cells[cell_key(r)].append(r)
        output["exploratory_choice_counts"] = {
            str(key): dict(Counter(r["choice"] for r in recs))
            for key, recs in sorted(exp_cells.items())
        }
    return output


def main(argv: list[str] | None = None) -> int:
    """CLI: regenerate all tables from raw JSONL (--manifest/--exploratory)."""
    parser = argparse.ArgumentParser(description="sixgame analysis")
    parser.add_argument(
        "--manifest", nargs="*", default=[], help="decision JSONL files"
    )
    parser.add_argument("--probes", nargs="*", default=[], help="probe JSONL files")
    parser.add_argument(
        "--exploratory", nargs="*", default=[], help="legacy condition JSONL files"
    )
    parser.add_argument("--boot", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out-dir", default=None)
    parser.add_argument(
        "--run-id",
        default=None,
        help="write analysis.json to <data-root>/<run-id>/ when --out-dir is absent",
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="also write AUDIT_LOG.md (input hashes, cache reconciliation)",
    )
    args = parser.parse_args(argv)
    output = run_analysis(
        [Path(p) for p in args.manifest],
        [Path(p) for p in args.probes],
        [Path(p) for p in args.exploratory],
        args.boot,
        args.seed,
    )
    text = json.dumps(output, indent=2, ensure_ascii=False)
    print(text)
    if args.out_dir:
        out = Path(args.out_dir)
    elif args.run_id:
        try:
            from sixgame.data_root import default_data_root
        except ImportError:  # pragma: no cover
            from data_root import default_data_root
        out = default_data_root() / args.run_id
    else:
        out = None
    if out is not None:
        out.mkdir(parents=True, exist_ok=True)
        (out / "analysis.json").write_text(text + "\n", encoding="utf-8")
        # Single source of truth (RESULT-2749 defect 3): the Markdown is
        # rendered from the SAME dict that was just dumped to JSON.
        (out / "report.md").write_text(render_markdown(output) + "\n", encoding="utf-8")
        if args.audit:
            (out / "AUDIT_LOG.md").write_text(
                build_audit_log(args.manifest, args.probes, output["exclusions"])
                + "\n",
                encoding="utf-8",
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
