# figures_distributions.py — final journal Figure 02 (TVD mismatch).
#
# What this file does:
#   Only Figure 02 remains in this module: the validated total-variation
#   distance (TVD) results for the 7 eligible experiments — how far each
#   LLM's answer distribution sits from the human one, blinded and
#   disclosed. The TVD numbers themselves are read from the
#   already-validated table (T1_tvd.csv, seeded 20261010) and only
#   re-plotted. Provenance: that table was built from the complete
#   canonical records tree (Documents/ZJU work/fos/...), NOT the stale
#   fos-data mid-run mirror (see FIGURE_GUIDE.md, TVD provenance note).
#
#   The exploratory fig01 distribution-example figures were removed from
#   the pipeline; the git/project history holds the old code.
#
# Functions:
#   fig02_tvd_mismatch() -> builds the TVD journal figure

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fig_common import (C_BLINDED, C_DISCLOSED, FIG_DIR, UNBLINDING,
                        save_figure)

# The validated distributional analysis (Task 2724/2732, seeded 20261010).
DIST_RESULTS = UNBLINDING / ("publication_audit/"
                             "distributional_error_explanation_20261019")


# The 7 eligible experiments of the final journal set, with readable
# names. The two anchoring units share ONE "Anchoring" category on the x
# axis (their points and reference line are pooled there).
JOURNAL_EXPERIMENTS = [
    ("disease", "Disease framing"),
    ("sunk_cost", "Sunk cost"),
    ("wta_wtp", "WTA/WTP"),
    ("outcome_bias", "Outcome bias"),
    ("myside", "Myside bias"),
    ("anchoring_african", "Anchoring"),
    ("anchoring_redwood", "Anchoring"),
    ("prob_matching", "Probability matching"),
]


def fig02_tvd_mismatch():
    """Plot the validated TVD values for the 7 eligible experiments.

    One jittered point per model x arm; blinded/disclosed differ in both
    colour and marker shape; per-experiment human split-half reference
    (95th percentile of split-half TVD, averaged over arms and contrasts)
    as a short grey horizontal line. Journal rules: no title, no notes.
    """
    tvd = pd.read_csv(DIST_RESULTS / "T1_tvd.csv")
    # keep first-appearance order, so the two anchoring units collapse
    # into one category automatically
    exp_order = list(dict.fromkeys(label for _, label in JOURNAL_EXPERIMENTS))
    labels = dict(JOURNAL_EXPERIMENTS)
    missing = {name for name, _ in JOURNAL_EXPERIMENTS}
    missing -= set(tvd.experiment.unique())
    if missing:
        raise ValueError(f"TVD table missing eligible experiments: {missing}")
    long = tvd.melt(
        id_vars=["experiment", "contrast", "model", "condition",
                 "ref_tvd_control_p95", "ref_tvd_treat_p95"],
        value_vars=["TVD_control", "TVD_treat"],
        var_name="arm", value_name="TVD")
    long["arm"] = long["arm"].map({"TVD_control": "control",
                                   "TVD_treat": "treatment"})
    long["category"] = long.experiment.map(labels)
    fig, ax = plt.subplots(figsize=(8.6, 4.4))
    rng = np.random.default_rng(20261028)
    for x_i, cat in enumerate(exp_order):
        sub = long[long.category == cat]
        for cond, color, marker in (("blinded", C_BLINDED, "o"),
                                    ("unblinded", C_DISCLOSED, "^")):
            vals = sub[sub.condition == cond].TVD.to_numpy()
            jitter = rng.uniform(-0.18, 0.18, size=len(vals))
            ax.plot(x_i + jitter, vals, marker, color=color, markersize=3.5,
                    alpha=0.55, linestyle="none",
                    label=("blinded" if x_i == 0 and cond == "blinded"
                           else ("disclosed" if x_i == 0 else None)))
        # human split-half noise reference (95th percentile), this
        # experiment only — averaged over its contrasts, units and arms
        ref = sub[["ref_tvd_control_p95", "ref_tvd_treat_p95"]].mean(axis=1)
        ax.plot([x_i - 0.28, x_i + 0.28], [ref.mean()] * 2, "-", color="0.45",
                linewidth=1.4,
                label=("human split-half noise (95th pct)" if x_i == 0
                       else None))
    ax.set_xticks(range(len(exp_order)))
    ax.set_xticklabels(exp_order, rotation=40, ha="right", fontsize=8.5)
    ax.set_ylabel("total variation distance")
    ax.set_ylim(0.0, 1.0)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    keep = long[["experiment", "contrast", "model", "condition", "arm",
                 "TVD", "ref_tvd_control_p95", "ref_tvd_treat_p95"]]
    keep.to_csv(FIG_DIR / "fig02_tvd_mismatch.csv", index=False)
    save_figure(fig, "fig02_tvd_mismatch")


if __name__ == "__main__":
    fig02_tvd_mismatch()
