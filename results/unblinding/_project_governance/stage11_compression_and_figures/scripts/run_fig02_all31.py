# run_fig02_all31.py — computes the Figure 02 distributional distances
# for ALL 31 experiments and writes the analysis tables.
#
# What this file does:
#   1. loads every experiment's human + LLM response distributions
#      (fig02_original14 + fig02_expansion, incl. the TESS studies);
#   2. scores the normalized Wasserstein distance human-vs-LLM per
#      experiment x arm x model x blinding condition;
#   3. draws >=200 seeded human split-halves per arm for the noise
#      reference distribution (same metric, not a percentile point);
#   4. aggregates with equal weight per experiment and writes the
#      coverage table, the per-arm table, and the plotting table.
#
# Functions:
#   canonical_experiments -> the 31 canonical experiment units
#   canonical_exp_id      -> maps the split TESS pseudo-units back
#   compute_arm_dists     -> per-arm human-vs-LLM distances
#   split_half_reference  -> per-experiment split-half distance draws
#   write_tables          -> coverage / by-arm / plotting CSVs
#   main                  -> runs everything

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fig02_common import weighted_dist, split_half_dist  # noqa: E402
import fig02_original14 as o14  # noqa: E402
import fig02_expansion as fx  # noqa: E402

ANALYSIS_DIR = Path(__file__).resolve().parent.parent / "analysis"
SEED = 20261028
N_SPLITS = 500  # split-half draws per experiment (>= 200 per spec)

BLINDING_LABEL = {"blinded": "blinded", "unblinded": "disclosed"}


def canonical_exp_id(exp_id: str) -> str:
    """TESS item/outcome contrasts live in ONE experiment each."""
    return exp_id.split("#")[0]


def canonical_experiments() -> list:
    """The 31 canonical units: 14 original + 13 ML1/ML2 + 4 TESS.

    TESS item-subset pseudo-units (budescu item contrasts, reed outcome
    contrasts) merge back into their one canonical experiment each; their
    arms keep the '#subset' suffix so every contrast arm stays distinct.
    """
    merged: dict = {}
    order = []
    for name, exp in o14.load_original14().items():
        merged[name] = exp
        order.append(name)
    for exp_id, exp in fx.load_expansion().items():
        cid = canonical_exp_id(exp_id)
        if cid not in merged:
            merged[cid] = exp
            merged[cid].exp_id = cid
            order.append(cid)
            continue
        prev = merged[cid]
        prev.contrasts = list(prev.contrasts) + list(exp.contrasts)
        prev.arms.update(exp.arms)
    return [(name, merged[name], merged[name].group) for name in order]


def arm_distance(exp, arm_name: str, model: str, cond: str) -> float:
    """Human-vs-LLM distance for one arm (metric per registered space)."""
    arm = exp.arms[arm_name]
    key = f"{model}|{cond}"
    lo, hi = arm.space
    return weighted_dist(arm.human_values, arm.llm_values[key], lo, hi,
                         llm_weights=arm.llm_weights.get(key))


def compute_arm_dists(units: list) -> pd.DataFrame:
    """One row per canonical experiment x contrast x arm x model x cond."""
    rows = []
    for exp_id, exp, group in units:
        for contrast, control, treatment in exp.contrasts:
            for arm_name in (control, treatment):
                for model in exp.models:
                    for cond in ("blinded", "unblinded"):
                        rows.append({
                            "experiment": exp_id, "group": group,
                            "contrast": contrast, "arm": arm_name,
                            "model": model,
                            "blinding": BLINDING_LABEL[cond],
                            "distance": arm_distance(exp, arm_name, model,
                                                     cond)})
    return pd.DataFrame(rows)


def split_half_reference(units: list) -> pd.DataFrame:
    """Per-experiment split-half draws: one aggregated distance per draw.

    Each draw splits every arm's human respondents into halves and scores
    the same metric; the per-draw experiment value is the equal-arm mean
    (the same aggregation the LLM distances get).
    """
    rows = []
    for i, (exp_id, exp, group) in enumerate(units):
        rng = np.random.default_rng(SEED + i)
        arms = sorted({a for _c, ctl, trt in exp.contrasts
                       for a in (ctl, trt)})
        for draw in range(N_SPLITS):
            vals = [split_half_dist(exp.arms[a].human_values,
                                    *exp.arms[a].space, rng)
                    for a in arms]
            rows.append({"experiment": exp_id, "group": group,
                         "draw": draw, "distance": float(np.mean(vals))})
    return pd.DataFrame(rows)


def aggregate(by_arm: pd.DataFrame, units: list) -> pd.DataFrame:
    """Equal-weight-per-experiment aggregation for the pooled ECDF.

    Unit = experiment x model x blinding; arms enter with equal weight
    (a shared control arm once). Each experiment gets total weight 1/31,
    split equally over its model-level points inside one blinding curve.
    """
    agg = by_arm.groupby(["experiment", "model", "blinding"],
                         as_index=False)["distance"].mean()
    n_exp = len(units)
    n_models = {exp_id: len(exp.models) for exp_id, exp, _g in units}
    agg["weight"] = [
        1.0 / (n_exp * n_models[r.experiment]) for r in agg.itertuples()]
    return agg


def write_tables(units: list, by_arm: pd.DataFrame,
                 splits: pd.DataFrame) -> None:
    """Coverage table + per-arm table + plotting table."""
    ANALYSIS_DIR.mkdir(exist_ok=True)
    cov_rows = []
    for exp_id, exp, group in units:
        arms = sorted({a for _c, ctl, trt in exp.contrasts
                       for a in (ctl, trt)})
        cov_rows.append({
            "experiment": exp_id, "group": group,
            "n_contrasts": len(exp.contrasts),
            "contrasts": "; ".join(c for c, _t, _ctl in exp.contrasts),
            "arms": "; ".join(arms),
            "outcome_type": exp.outcome_type,
            "n_models": len(exp.models),
            "human_n_per_arm": "; ".join(
                f"{a}:{len(exp.arms[a].human_values)}" for a in arms),
            "registered_space": ";".join(
                f"{exp.arms[a].space[0]:g}-{exp.arms[a].space[1]:g}"
                for a in arms),
            "human_source": (
                "wave1_3_response.csv (registered coding)"
                if group == "original" else
                "expansion cleaned CSVs / TESS .sav (registered coding)"),
            "llm_source": (
                "TWIN2K/T2K10 unblinding logprob records (complete "
                "canonical tree)" if group == "original" else
                "expansion work T2KX-20261022T222604 production records"),
            "included": "yes",
        })
    cov = pd.DataFrame(cov_rows)
    cov.to_csv(ANALYSIS_DIR / "fig02_coverage_table.csv", index=False)
    by_arm.to_csv(ANALYSIS_DIR / "fig02_dist_by_arm.csv", index=False)
    splits.to_csv(ANALYSIS_DIR / "fig02_split_half_draws.csv", index=False)
    agg = aggregate(by_arm, units)
    # plotting table: LLM points + the experiment-equal split-half pool
    sh = splits.copy()
    sh["weight"] = 1.0 / (len(units) * N_SPLITS)
    sh["model"] = "human split-half"
    sh["blinding"] = "human split-half"
    keep = ["experiment", "model", "blinding", "distance", "weight"]
    pd.concat([agg[keep], sh[keep]]).to_csv(
        ANALYSIS_DIR / "fig02_dist_ecdf.csv", index=False)


def main() -> None:
    units = canonical_experiments()
    print(f"experiments: {len(units)}")
    by_arm = compute_arm_dists(units)
    print(f"arm-level rows: {len(by_arm)}; "
          f"mean distance {by_arm.distance.mean():.4f}")
    splits = split_half_reference(units)
    print(f"split-half draws: {len(splits)}; "
          f"mean {splits.distance.mean():.4f}")
    write_tables(units, by_arm, splits)
    print("tables written to", ANALYSIS_DIR)


if __name__ == "__main__":
    main()
