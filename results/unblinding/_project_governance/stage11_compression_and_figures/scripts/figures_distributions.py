# figures_distributions.py — final journal Figure 02 (distributional
# distance ECDF, all 31 experiments).
#
# What this file does: one ECDF comparing blinded LLM-human, disclosed
# LLM-human, and the human split-half reference distributional distances
# across all 31 experiments. Distances are normalized 1-D Wasserstein
# distances on each experiment's registered outcome space (equal to TVD
# for two-point/binary spaces), computed by run_fig02_all31 (seeded,
# deterministic); aggregation weights every experiment equally. The
# human split-half curve is the full reference DISTRIBUTION (500 seeded
# splits per experiment), not a percentile point.
#
# Functions:
#   fig02_distributional_distance() -> builds the Figure 02 ECDF

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fig_common import C_BLINDED, C_DISCLOSED, save_figure  # noqa: E402
from fig02_common import ecdf_points as _ecdf_impl  # noqa: E402
import run_fig02_all31 as ra  # noqa: E402

# the worktree stage11 figures directory (script-relative, so runs write
# next to this code and get synced, never into the read-only live tree)
FIG_DIR_WT = Path(__file__).resolve().parent.parent / "figures"


def fig02_distributional_distance():
    """Pooled weighted ECDF of distributional distances, all 31 exps."""
    units = ra.canonical_experiments()
    by_arm = ra.compute_arm_dists(units)
    splits = ra.split_half_reference(units)
    ra.write_tables(units, by_arm, splits)

    agg = by_arm.groupby(["experiment", "model", "blinding"],
                         as_index=False)["distance"].mean()
    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    n_exp = len(units)
    for cond, color, label in ((("blinded"), C_BLINDED, "LLM–human, blinded"),
                               (("disclosed"), C_DISCLOSED,
                                "LLM–human, disclosed")):
        sub = agg[agg.blinding == cond]
        w = [1.0 / (n_exp * len(sub[sub.experiment == e]))
             for e in sub.experiment]
        x, y = _ecdf(sub.distance.to_numpy(), w)
        ax.step(x, y, where="post", color=color, linewidth=1.6, label=label)
    w_sh = [1.0 / (n_exp * ra.N_SPLITS)] * len(splits)
    x, y = _ecdf(splits.distance.to_numpy(), w_sh)
    ax.step(x, y, where="post", color="0.45", linewidth=1.6,
            label="human split-half")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("distributional distance (0 = identical)")
    ax.set_ylabel("cumulative proportion")
    ax.legend(frameon=False, fontsize=8.5, loc="lower right")
    fig.tight_layout()
    keep = agg.rename(columns={"distance": "dist"})
    keep["weight"] = [1.0 / (n_exp * len(agg[agg.experiment == e]))
                      for e in keep.experiment]
    sh = splits.assign(model="human split-half", blinding="human split-half",
                       weight=1.0 / (n_exp * ra.N_SPLITS)
                       ).rename(columns={"distance": "dist"})
    plot_table = keep[["experiment", "model", "blinding", "dist",
                       "weight"]]
    plot_table = pd.concat([
        plot_table,
        sh[["experiment", "model", "blinding", "dist", "weight"]]])
    plot_table.to_csv(
        FIG_DIR_WT / "fig02_distributional_distance.csv", index=False)
    save_figure(fig, "fig02_distributional_distance", out_dir=FIG_DIR_WT)


def _ecdf(samples, weights):
    """Sorted x / cumulative-share y for one blinding curve."""
    return _ecdf_impl(list(samples), list(weights))


if __name__ == "__main__":
    fig02_distributional_distance()
