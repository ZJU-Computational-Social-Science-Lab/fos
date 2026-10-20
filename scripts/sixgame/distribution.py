"""Distributional equivalence checks for the sixgame transformations.

This module answers one question per transformation: does the
transformed play look like the canonical play with the rule's mapping
applied — as whole DISTRIBUTIONS, not draw-for-draw?

What each function does:

- ``paired_tvd_bootstrap``: the total variation distance between the
  mapped canonical distribution and the transformed distribution,
  together with a 90% bootstrap confidence interval.  Whole personas
  are resampled, and the SAME persona draw is used for both sides
  (the same five personas played canonical and transformed), so the
  pairing the experiment actually used is respected.  Also reports
  n_eff (how many effectively independent personas we have).
- ``equivalence_verdict``: the plain-language verdict.  If a margin
  was frozen in advance and the whole confidence interval sits inside
  it, the two are called EQUIVALENT; without a pre-agreed margin (or
  when the interval is too wide to tell) the row is labelled
  UNPOWERED-DESCRIPTIVE — a description, not a conclusion.
- ``distribution_equivalence_table``: the whole table, one row per
  transformation (and per player role for the PMS relabeling, which
  is never pooled across Row and Column players).
- ``independent_tvd_confirmation``: a second, deliberately separate
  tally of the 11-20 → 31-40 TVD, counted straight from the raw
  records with plain counters, so the headline numbers can be checked
  against the main pipeline by a different code path.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Sequence

try:  # works both as a package module and run from the scripts directory
    from sixgame import benchmarks
    from sixgame.games import variant_spec
    from sixgame.stats import (
        _kish_neff,
        finite_sample_tvd_slack,
        js_divergence_bits,
        tvd,
        tvd_of_outcomes,
    )
except ImportError:  # pragma: no cover - direct execution layout
    import benchmarks
    from games import variant_spec
    from stats import (
        _kish_neff,
        finite_sample_tvd_slack,
        js_divergence_bits,
        tvd,
        tvd_of_outcomes,
    )

#: Verdict for "the sample shows no difference, but the sample is too
#: small to establish equivalence at the frozen margin" (TASK-2760).
NO_DIFFERENCE_VERDICT = "NO_DIFFERENCE_OBSERVED_EQUIVALENCE_NOT_ESTABLISHED"

#: Distributional-equivalence checks: name -> (game, canonical variant,
#: transformed variant, roles to analyse separately, frozen margin in
#: percentage points or None when no margin was ever agreed).
#: Die-roll margins: Tier A small, Tier B wider (benchmarks.py).  PMS:
#: the frozen δ=25pp framework.  11-20 range shifts had no agreed margin.
DISTRIBUTION_CHECKS = {
    "1120_r31-40": ("1120", "basic", "r31-40", [None], None),
    "dieroll_neutral_tierA": (
        "dieroll", "private", "neutral", [None], benchmarks.DELTA_DIE_TIER_A_PP,
    ),
    "dieroll_stake10_tierB": (
        "dieroll", "private", "stake10", [None], benchmarks.DELTA_DIE_TIER_B_PP,
    ),
    "pms_relabel": ("pms", "G1", "relabel", ["Row", "Column"], benchmarks.DELTA_PMS_PP),
}


def paired_tvd_bootstrap(
    can_by_persona: dict[str, list],
    tra_by_persona: dict[str, list],
    n_boot: int = 10_000,
    seed: int = 0,
) -> dict:
    """TVD between mapped-canonical and transformed distributions with a
    90% paired cluster-bootstrap CI (personas resampled once per
    replicate, same indices on both sides) plus JS divergence (bits),
    n_eff and the per-persona cluster sizes."""
    import random

    personas = sorted(set(can_by_persona) & set(tra_by_persona))
    can_flat = [v for p in personas for v in can_by_persona[p]]
    tra_flat = [v for p in personas for v in tra_by_persona[p]]
    support = sorted(set(can_flat) | set(tra_flat), key=str)
    point = tvd_of_outcomes(can_flat, tra_flat, support=support)
    js = js_divergence_bits(
        _share(can_flat, support), _share(tra_flat, support)
    )
    rng = random.Random(seed)
    reps: list[float] = []
    for _ in range(n_boot):
        idx = [rng.randrange(len(personas)) for _ in range(len(personas))]
        c_rep = [v for i in idx for v in can_by_persona[personas[i]]]
        t_rep = [v for i in idx for v in tra_by_persona[personas[i]]]
        reps.append(tvd_of_outcomes(c_rep, t_rep, support=support))
    reps.sort()
    low, high = reps[int(0.05 * n_boot)], reps[min(n_boot - 1, int(0.95 * n_boot) - 1)]
    return {
        "tvd": round(point, 4),
        "tvd_ci90": [round(low, 4), round(high, 4)],
        "js_divergence_bits": round(js, 4),
        "n_eff": round(_kish_neff([len(can_by_persona[p]) for p in personas]), 2),
        "n_personas": len(personas),
    }


def _share(outcomes: list, support: Sequence) -> dict:
    """Empirical distribution of an outcome list over a support."""
    n = len(outcomes) or 1
    counts = Counter(outcomes)
    return {k: counts.get(k, 0) / n for k in support}


def finite_sample_tvd_bound(
    point: float, n_can: int, n_tra: int, n_categories: int,
    confidence: float = 0.90,
) -> float:
    """A defensible finite-sample upper bound on the true TVD: the point
    estimate plus the small-sample slack (TASK-2760), capped at 1."""
    slack = finite_sample_tvd_slack(n_can, n_tra, n_categories, confidence)
    return min(1.0, point + slack)


def equivalence_note_for(verdict: str, margin_pp: float | None) -> str:
    """The plain-language note attached to every distributional row, so
    a verdict is never a bare label (TASK-2760 wording, pre-agreed)."""
    if verdict == "EQUIVALENT":
        return (
            "equivalence established: a defensible finite-sample interval "
            "supports the frozen margin"
        )
    if verdict == NO_DIFFERENCE_VERDICT:
        return (
            "no difference observed in sample; equivalence NOT established "
            "— the sample is too small for any defensible finite-sample "
            "interval to support the frozen margin"
        )
    if margin_pp is None:
        return (
            "no margin was ever pre-agreed for this transformation — "
            "descriptive only, no equivalence claim possible"
        )
    return (
        "the observed difference exceeds the pre-agreed margin (or the "
        "interval is too wide to tell) — equivalence NOT established"
    )


def equivalence_verdict(
    margin_pp: float | None,
    tvd_ci90: list,
    n_can: int | None = None,
    n_tra: int | None = None,
    n_categories: int | None = None,
) -> str:
    """EQUIVALENT only when a pre-agreed margin exists AND the whole TVD
    CI sits below margin/100 AND a defensible finite-sample interval
    (point + small-sample slack) also supports the frozen margin
    (TASK-2760).  Without sample-size information the equivalence claim
    is refused outright — a degenerate interval from tiny cells (e.g.
    n=10 per cell) can never establish equivalence.  Everything else is
    UNPOWERED-DESCRIPTIVE or NO_DIFFERENCE_VERDICT — never a post-hoc
    threshold."""
    if margin_pp is None:
        return "UNPOWERED-DESCRIPTIVE"
    if tvd_ci90[1] >= margin_pp / 100.0:
        return "UNPOWERED-DESCRIPTIVE"
    # The CI is inside the margin — but equivalence additionally needs a
    # defensible finite-sample interval.  No sample info: refuse.
    if n_can is None or n_tra is None or n_categories is None:
        return NO_DIFFERENCE_VERDICT
    bound = finite_sample_tvd_bound(
        tvd_ci90[0], n_can, n_tra, n_categories
    )
    if bound < margin_pp / 100.0:
        return "EQUIVALENT"
    return NO_DIFFERENCE_VERDICT


def _records_for(cells: dict, game: str, variant: str, arm: str,
                 role: str | None) -> list:
    """Kept records for one (game, variant, arm), optionally one role.

    Cell keys are tuples whose first three entries are (game, variant,
    arm); anything after that (e.g. a role in the key) is ignored — the
    record's own `role` field decides.
    """
    out = []
    for key, recs in cells.items():
        if tuple(key)[:3] != (game, variant, arm):
            continue
        out.extend(r for r in recs if r.get("role") == role)
    return out


def distribution_equivalence_table(
    cell_records: dict, boot: int = 10_000, seed: int = 0
) -> list[dict]:
    """One row per transformation x arm (x role for PMS): TVD and JS with
    90% paired cluster-bootstrap CIs, n_eff, and the margin verdict."""
    rows = []
    for name, (game, can_v, tra_v, roles, margin) in DISTRIBUTION_CHECKS.items():
        spec = variant_spec(game, tra_v)
        for arm in ("persona", "no_persona"):
            for role in roles:
                can = _records_for(cell_records, game, can_v, arm, role)
                tra = _records_for(cell_records, game, tra_v, arm, role)
                if not can or not tra:
                    continue
                can_by = defaultdict(list)
                tra_by = defaultdict(list)
                for r in can:
                    can_by[r["persona_id"]].append(spec.mapping(r["choice"]))
                for r in tra:
                    tra_by[r["persona_id"]].append(r["choice"])
                stats = paired_tvd_bootstrap(can_by, tra_by, boot, seed)
                n_categories = len(spec.actions)
                n_can = sum(len(v) for v in can_by.values())
                n_tra = sum(len(v) for v in tra_by.values())
                verdict = equivalence_verdict(
                    margin, stats["tvd_ci90"],
                    n_can=n_can, n_tra=n_tra, n_categories=n_categories,
                )
                rows.append(
                    {
                        "transformation": name,
                        "arm": arm,
                        "role": role,
                        "margin_pp": margin,
                        "n_canonical": n_can,
                        "n_transformed": n_tra,
                        "finite_sample_tvd_bound": round(
                            finite_sample_tvd_bound(
                                stats["tvd"], n_can, n_tra, n_categories,
                            ),
                            4,
                        ),
                        **stats,
                        "verdict": verdict,
                        "equivalence_note": equivalence_note_for(verdict, margin),
                    }
                )
    return rows


def independent_tvd_confirmation(cell_records: dict) -> dict:
    """Recount the 11-20 -> 31-40 TVD per arm with plain counters (a
    separate code path from stats.tvd / the bootstrap machinery) and
    report whether it agrees with the pipeline value.  The frozen
    expectation is persona 0.30, no-persona 0.20."""
    result: dict = {}
    for arm in ("persona", "no_persona"):
        can = _records_for(cell_records, "1120", "basic", arm, None)
        tra = _records_for(cell_records, "1120", "r31-40", arm, None)
        if not can or not tra:
            continue
        # Independent path: shift each canonical choice by +20 and tally.
        can_counts: Counter = Counter(r["choice"] + 20 for r in can)
        tra_counts: Counter = Counter(r["choice"] for r in tra)
        keys = set(can_counts) | set(tra_counts)
        n_can, n_tra = sum(can_counts.values()), sum(tra_counts.values())
        independent = 0.5 * sum(
            abs(can_counts.get(k, 0) / n_can - tra_counts.get(k, 0) / n_tra)
            for k in keys
        )
        # Pipeline path: pmfs + stats.tvd over the union support.
        spec = variant_spec("1120", "r31-40")
        support = list(spec.actions)
        p_can = {k: can_counts.get(k, 0) / n_can for k in support}
        p_tra = {k: tra_counts.get(k, 0) / n_tra for k in support}
        pipeline = tvd(p_can, p_tra)
        result[arm] = {
            "independent": round(independent, 4),
            "pipeline": round(pipeline, 4),
            "agree": abs(independent - pipeline) < 1e-9,
            "expected_frozen": 0.30 if arm == "persona" else 0.20,
            "matches_frozen": abs(independent - (0.30 if arm == "persona" else 0.20))
            < 1e-9,
        }
    return result
