# figures_distributions.py — final journal Figure 02 (overlaid histogram
# of distributional distances, all 31 experiments).
#
# What this file does: one panel with three overlaid histograms comparing
# blinded LLM-human, disclosed LLM-human, and the human split-half
# reference distributional distances across all 31 experiments. Distances are normalized 1-D Wasserstein
# distances on each experiment's registered outcome space (equal to TVD
# for two-point/binary spaces), computed by run_fig02_all31 (seeded,
# deterministic); aggregation weights every experiment equally. The
# human split-half curve is the full reference DISTRIBUTION (500 seeded
# splits per experiment), not a percentile point.
#
# Functions:
#   fig02_distributional_distance() -> builds the Figure 02 histogram

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fig_common import C_BLINDED, C_DISCLOSED, save_figure  # noqa: E402
import run_fig02_all31 as ra  # noqa: E402

# the worktree stage11 figures directory (script-relative, so runs write
# next to this code and get synced, never into the read-only live tree)
FIG_DIR_WT = Path(__file__).resolve().parent.parent / "figures"


BIN_EDGES = np.arange(0.0, 1.0001, 0.01)  # x 0-1, bin width exactly 0.01


def fig02_distributional_distance():
    """Overlaid weighted histogram of distances, all 31 experiments."""
    units = ra.canonical_experiments()
    by_arm = ra.compute_arm_dists(units)
    splits = ra.split_half_reference(units)
    ra.write_tables(units, by_arm, splits)

    agg = by_arm.groupby(["experiment", "model", "blinding"],
                         as_index=False)["distance"].mean()
    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    n_exp = len(units)
    bin_rows = []
    series = []
    for cond, color, label in (("blinded", C_BLINDED, "LLM–human, blinded"),
                               ("disclosed", C_DISCLOSED,
                                "LLM–human, disclosed")):
        sub = agg[agg.blinding == cond]
        w = np.array([1.0 / (n_exp * len(sub[sub.experiment == e]))
                      for e in sub.experiment])
        series.append((label, color, sub.distance.to_numpy(), w))
    w_sh = np.full(len(splits), 1.0 / (n_exp * ra.N_SPLITS))
    series.append(("human split-half", "0.45",
                   splits.distance.to_numpy(), w_sh))
    for label, color, values, w in series:
        heights, _edges = np.histogram(values, bins=BIN_EDGES, weights=w)
        ax.stairs(heights, BIN_EDGES, color=color, linewidth=1.4,
                  label=label)
        for left, h in zip(BIN_EDGES[:-1], heights):
            if h > 0:
                bin_rows.append({"series": label, "bin_left": round(left, 2),
                                 "bin_right": round(left + 0.01, 2),
                                 "proportion": h})
    ax.set_xlim(0, 1)
    ax.set_xlabel("distributional distance (0 = identical)")
    ax.set_ylabel("proportion (experiment-equal weighted)")
    ax.legend(frameon=False, fontsize=8.5, loc="upper center",
              bbox_to_anchor=(0.5, -0.16), ncol=3)
    fig.tight_layout()
    # plotted values: the exact per-bin histogram heights; the raw weighted
    # points behind each histogram are kept alongside for provenance
    pd.DataFrame(bin_rows).sort_values(["series", "bin_left"]).to_csv(
        FIG_DIR_WT / "fig02_distributional_distance.csv", index=False)
    keep = agg.rename(columns={"distance": "dist"})
    keep["weight"] = [1.0 / (n_exp * len(agg[agg.experiment == e]))
                      for e in keep.experiment]
    sh = splits.assign(model="human split-half", blinding="human split-half",
                       weight=1.0 / (n_exp * ra.N_SPLITS)
                       ).rename(columns={"distance": "dist"})
    keep[["experiment", "model", "blinding", "dist", "weight"]].to_csv(
        FIG_DIR_WT / "fig02_hist_points.csv", index=False)
    sh[["experiment", "model", "blinding", "dist", "weight"]].to_csv(
        FIG_DIR_WT / "fig02_hist_splithalf_points.csv", index=False)
    save_figure(fig, "fig02_distributional_distance", out_dir=FIG_DIR_WT)


if __name__ == "__main__":
    fig02_distributional_distance()
