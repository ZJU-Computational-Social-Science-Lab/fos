# corrected_stage3_original14.py — recalculate the Stage 3 original
# 14-experiment statistics using the corrected canonical model effects
# (reconciled_v1) instead of the stale frozen 262-row table.
#
# What it does:
#   build_signed_table  — rebuilds the 262-row signed-contrast table
#                         (same layout as the frozen
#                         blinding_signed_contrasts.csv) from
#                         CANONICAL_MODEL_EFFECTS.csv. Human effects are
#                         identical to frozen (corrections touch model
#                         effects only); the 6 new-only coverage cells are
#                         excluded so the analysis stays comparable to the
#                         frozen 262-row structure.
#   main                — feeds that table through the UNCHANGED frozen
#                         method library (collapse, headline stats, per-model
#                         / per-experiment tables, family bootstrap seed
#                         20261010 + offsets, spec A.2 bootstrap seed
#                         20261013) and writes the corrected tables plus a
#                         before/after comparison into corrected_results/stage3/.

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

UNBL = Path("/home/justin/Documents/ZJU work/fos/results/unblinding")
GOV = UNBL / "_project_governance"
STAGE10 = GOV / "stage10_data_reconciliation"
OUT = Path("/home/justin/work/worktrees/implement-3014/_project_governance/"
           "stage10_data_reconciliation/corrected_results/stage3")

sys.path.insert(0, str(GOV / "stage3_results" / "scripts"))
from frozen_methods import (  # noqa: E402  (frozen library, reused unchanged)
    collapse, frozen_primary, group_table, headline_stats, spec_a2_bootstrap)

FAMILIES = {
    "anchoring_redwood": "anchoring", "anchoring_african": "anchoring",
    "fire_extinguisher": "proportion_dominance",
    "seatbelt": "proportion_dominance",
    "wta_wtp": "valuation_reference", "sunk_cost": "valuation_reference",
    "abs_relative": "valuation_reference",
    "less_is_more": "valuation_reference",
    "allais": "probability_risk", "prob_matching": "probability_risk",
    "linda": "judgment_inference", "outcome_bias": "judgment_inference",
    "myside": "judgment_inference", "disease": "disease",
}

FROZEN_SIGNED = (UNBL / "agreed_figure_code_package" / "data"
                 / "blinding_signed_contrasts.csv")


def build_signed_table() -> pd.DataFrame:
    """262-row signed table from canonical effects (model effects corrected,
    human effects unchanged; new-only cells excluded)."""
    canon = pd.read_csv(STAGE10 / "data" / "CANONICAL_MODEL_EFFECTS.csv")
    orig = canon[canon["study_group"] == "original"].copy()
    orig["leg"] = orig["blinding"].map({0: "B", 1: "U"})
    # pp-scale human effect, exactly as the canonical std x pooled-SD defines
    orig["d_h"] = orig["human_effect_std"] * orig["sd_human_pooled_pp"]

    wide = orig.pivot_table(index=["contrast_id", "model"], columns="leg",
                            values=["model_effect_pp", "d_h"], aggfunc="first")
    wide.columns = [f"{a}_{b}" for a, b in wide.columns]
    wide = wide.reset_index()

    reg = pd.read_csv(GOV / "stage3_methodology" / "CONTRAST_REGISTER.csv")
    ov = pd.read_csv(STAGE10 / "data" / "OLD_VS_CORRECTED_EFFECTS.csv")
    # keep exactly the cells present in the frozen 262-row structure
    keep = ov[(ov["coverage_status"] == "both")
              & ov["experiment_id"].isin(FAMILIES)][["contrast_id", "model"]]
    keep = keep.drop_duplicates()
    wide = wide.merge(keep, on=["contrast_id", "model"], how="inner")
    assert len(wide) == 262, f"expected 262 rows, got {len(wide)}"

    t = wide.merge(reg[["contrast_id", "contrast_name", "experiment_id"]],
                   on="contrast_id")
    t = t.rename(columns={"experiment_id": "experiment",
                          "contrast_name": "contrast"})
    t["paradigm_family"] = t["experiment"].map(FAMILIES)
    assert t["paradigm_family"].notna().all()

    t["H"] = t["d_h_B"].abs()
    for leg in ("B", "U"):
        t[f"M_{leg}"] = np.sign(t["d_h_B"]) * t[f"model_effect_pp_{leg}"]
        t[f"A_{leg}"] = t["H"] - t[f"M_{leg}"]
        t[f"E_{leg}"] = t[f"M_{leg}"].sub(t["H"]).abs()
    cols = ["model", "experiment", "contrast", "paradigm_family", "d_h_B",
            "H"] + [f"{p}_{leg}" for leg in "BU"
                    for p in ("M", "A", "E")]
    return t[cols].rename(columns={"d_h_B": "d_h"})


def before_after(head_new: dict[str, float], per_model_new: pd.DataFrame,
                 d_new: pd.DataFrame, d_old: pd.DataFrame) -> pd.DataFrame:
    """Old vs corrected headline numbers, side by side."""
    frozen = pd.read_csv(FROZEN_SIGNED)
    d_old = collapse(frozen)
    head_old = headline_stats(d_old)
    rows = []
    for k in head_new:
        rows.append({"statistic": k, "frozen": head_old[k],
                     "corrected": head_new[k],
                     "difference": head_new[k] - head_old[k]})
    return pd.DataFrame(rows), head_old


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    signed = build_signed_table()
    paired = signed.copy()
    paired["R_B"] = paired["M_B"] - paired["H"]
    paired["R_U"] = paired["M_U"] - paired["H"]
    paired["dE"] = paired["E_U"] - paired["E_B"]
    d = collapse(paired)
    assert len(d) == 18

    head = headline_stats(d)
    per_model = group_table(paired, "model")
    per_exp = group_table(paired, "experiment")

    prim = frozen_primary(d)
    ci_rows = [{"quantity": k, "estimate": est, "ci95_low": lo,
                "ci95_high": hi} for k, (est, lo, hi) in prim.items()]
    spec_ci = spec_a2_bootstrap(d)

    ba, head_old = before_after(head, per_model, d, None)

    signed.to_csv(OUT / "corrected_signed_contrasts.csv", index=False)
    pd.DataFrame([{"statistic": k, "value": v} for k, v in
                  head.items()]).to_csv(
        OUT / "recovery_slopes_signed_bias_figure3.csv", index=False)
    per_model.sort_values("model").to_csv(
        OUT / "per_model_statistics.csv", index=False)
    per_exp.sort_values("experiment").to_csv(
        OUT / "per_experiment_statistics.csv", index=False)
    pd.DataFrame(ci_rows).to_csv(
        OUT / "bootstrap_cis_frozen_method.csv", index=False)
    spec_ci.to_csv(
        OUT / "bootstrap_cis_spec_A2_experiment_cluster.csv", index=False)
    ba.to_csv(OUT / "headline_before_after.csv", index=False)

    print(ba.to_string(index=False))
    print(f"\noutputs in {OUT}")


if __name__ == "__main__":
    main()
