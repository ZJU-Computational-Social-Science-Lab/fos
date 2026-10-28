# figures_effects.py — final journal figures 03 to 07 (effect-level).
#
# What this file does: builds the retained journal figures only from the
# corrected Stage 10 tables (reconciled_v1). Direction figures use only the
# 32 contrasts whose human direction is confident at the two-sided 95%
# level; the 6 uncertain contrasts are left out of direction scoring
# entirely and are never counted as failures.
#
# Journal visual rules: no titles, no annotations, no printed estimates —
# axis labels, ticks, data, minimal legends and reference lines only.
#
# Figures:
#   03/04: human vs LLM standardized effects scatter, blinded / disclosed,
#          identical axes, 45-degree line, fitted recovery line using the
#          prespecified Stage 10 corrected estimator (same as fig05).
#   05:    the two recovery slopes side by side with their Stage 10 CIs
#          and a reference at 1.
#   06:    mean absolute standardized error, blinded vs disclosed, each
#          experiment counted once, plus the paired difference (visually
#          separated). CIs are bootstrap CIs over experiments.
#   07:    direction accuracy vs |human effect| per confident contrast,
#          blinded and disclosed as separate files with identical axes.
#
# Functions: one figNN_*() function per figure, plus main().

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fig_common import (C_BLINDED, C_BLINDED_DARK, C_DISCLOSED, C_LLM,
                        C_WRONG, FIG_DIR, N_BOOT, SEED, boot_mean_ci,
                        cell_directions, contrast_table, load_effects,
                        save_figure, stage10_slope_ci)

# The exploratory effect figures fig08 (abs error trend), fig09 (agreement
# by experiment) and fig10/fig11 (heatmaps) were removed from the pipeline
# along with their helpers; the git/project history holds the old code.


def _recovery_scatter(cells, condition, name, lims, slope, lo, hi):
    """Shared body of figures 03 and 04 (identical axes and encoding)."""
    # blinded = blue throughout; disclosed = orange points, muted-red line
    point_color, line_color = ((C_BLINDED, C_BLINDED_DARK)
                               if condition == "blinded" else (C_LLM, C_WRONG))
    sub = cells[cells.condition == condition]
    fig, ax = plt.subplots(figsize=(5.4, 5.4))
    ax.axhline(0, color="0.75", linewidth=0.8, zorder=1)
    ax.axvline(0, color="0.55", linewidth=1.0, linestyle="--", zorder=1)
    ax.plot(lims, lims, color="0.3", linewidth=1.0, linestyle=":",
            label="perfect recovery (45\u00b0)", zorder=2)
    ax.scatter(sub.human_effect_std, sub.model_effect_std, s=10, alpha=0.30,
               color=point_color, edgecolor="none", zorder=3,
               label="model\u00d7contrast cells")
    xs = np.array(lims)
    ax.plot(xs, slope * xs, color=line_color, linewidth=1.8, zorder=4,
            label="fitted recovery line")
    ax.set_xlim(lims)
    ax.set_ylim(lims)
    ax.set_aspect("equal")
    ax.set_xlabel("human effect (std units)")
    ax.set_ylabel("LLM effect (std units)")
    ax.legend(frameon=False, fontsize=7.5, loc="lower right")
    fig.tight_layout()
    out = sub[["contrast_id", "experiment_id", "model", "condition",
               "human_effect_std", "model_effect_std", "model_effect_se_std",
               "direction_confident"]]
    out.to_csv(FIG_DIR / f"{name}.csv", index=False)
    save_figure(fig, name)


def fig03_04_recovery_scatter(cells):
    lims = (-1.45, 1.45)
    slopes = stage10_slope_ci()
    _recovery_scatter(cells, "blinded", "fig03_recovery_blinded", lims,
                      *slopes["blinded"])
    _recovery_scatter(cells, "disclosed", "fig04_recovery_disclosed", lims,
                      *slopes["disclosed"])
    return slopes


def fig05_slopes(slopes):
    fig, ax = plt.subplots(figsize=(4.6, 3.8))
    conds = ["blinded", "disclosed"]
    for x_i, cond in enumerate(conds):
        s, lo, hi = slopes[cond]
        color = C_BLINDED if cond == "blinded" else C_DISCLOSED
        ax.errorbar([x_i], [s], yerr=[[s - lo], [hi - s]], fmt="o",
                    color=color, markersize=7, capsize=5, linewidth=1.6)
    ax.axhline(1.0, color="0.3", linestyle=":", linewidth=1.2)
    ax.axhline(0.0, color="0.75", linewidth=0.8)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(conds)
    ax.set_ylabel("fitted recovery slope (std units per std unit)")
    fig.tight_layout()
    pd.DataFrame([{"condition": c, "slope": slopes[c][0],
                   "ci_low": slopes[c][1], "ci_high": slopes[c][2]}
                  for c in conds]).to_csv(FIG_DIR / "fig05_slopes.csv",
                                          index=False)
    save_figure(fig, "fig05_recovery_slopes")


def fig06_abs_error(cells):
    """Mean absolute standardized error, experiment-equal-weighted."""
    per_exp = (cells.groupby(["condition", "experiment_id"]).abs_error.mean()
               .unstack(0))
    per_exp = per_exp.dropna()
    res = {}
    for cond in ("blinded", "disclosed"):
        res[cond] = boot_mean_ci(per_exp[cond], per_exp.index)
    diff = per_exp["disclosed"] - per_exp["blinded"]
    res["difference"] = boot_mean_ci(diff, diff.index)
    fig, ax = plt.subplots(figsize=(5.2, 4.0))
    labels = ["blinded", "disclosed", "difference\n(disclosed \u2212 blinded)"]
    # the difference sits on its own side of a visual separator
    x_pos = {"blinded": 0.0, "disclosed": 1.0, "difference": 2.6}
    for key in ("blinded", "disclosed", "difference"):
        pt, lo, hi = res[key]
        color = {"blinded": C_BLINDED, "disclosed": C_DISCLOSED,
                 "difference": "0.3"}[key]
        ax.errorbar([x_pos[key]], [pt], yerr=[[pt - lo], [hi - pt]], fmt="o",
                    color=color, markersize=7, capsize=5, linewidth=1.6)
    ax.axhline(0, color="0.75", linewidth=0.8)
    ax.axvline(1.8, color="0.7", linewidth=0.8, linestyle="--")
    ax.set_xticks([x_pos[k] for k in ("blinded", "disclosed", "difference")])
    ax.set_xticklabels(labels)
    ax.set_ylabel("mean absolute error (std units)")
    fig.tight_layout()
    per_exp.assign(difference=diff).rename(
        columns={"blinded": "mean_abs_err_blinded",
                 "disclosed": "mean_abs_err_disclosed"})
    per_exp.assign(difference=diff).to_csv(
        FIG_DIR / "fig06_abs_error_by_experiment.csv",
        index_label="experiment_id")
    save_figure(fig, "fig06_abs_error_by_disclosure")


def _accuracy_trend_fig(cells, condition, name):
    """Figure 07: direction accuracy vs |human effect|, one file per condition."""
    conf = cells[(cells.condition == condition)
                 & (cells.direction_confident)]
    acc = (conf.groupby(["contrast_id", "abs_human_effect", "label"])
           .direction_correct.mean().reset_index()
           .rename(columns={"direction_correct": "accuracy"}))
    n_models = conf.groupby("contrast_id").direction_correct.count()
    acc["n_models"] = acc.contrast_id.map(n_models)

    # linear fit with a bootstrap CI that resamples experiments (clustering)
    x = acc.abs_human_effect.to_numpy(float)
    y = acc.accuracy.to_numpy(float)
    exp_of = acc.contrast_id.map(
        conf.groupby("contrast_id").experiment_id.first()).to_numpy()

    def fit_line(xs, ys):
        b, a = np.polyfit(xs, ys, 1)
        return a, b

    a0, b0 = fit_line(x, y)
    rng = np.random.default_rng(SEED)
    levels = np.unique(exp_of)
    boots = []
    for _ in range(N_BOOT):
        pick = rng.choice(levels, size=len(levels), replace=True)
        xs = np.concatenate([x[exp_of == c] for c in pick])
        ys = np.concatenate([y[exp_of == c] for c in pick])
        boots.append(fit_line(xs, ys))
    boots = np.asarray(boots)
    xs_line = np.linspace(x.min(), x.max(), 100)
    preds = boots[:, 0][:, None] + boots[:, 1][:, None] * xs_line[None, :]
    lo, hi = np.percentile(preds, [2.5, 97.5], axis=0)

    fig, ax = plt.subplots(figsize=(5.6, 4.2))
    color = C_BLINDED if condition == "blinded" else C_DISCLOSED
    if condition == "blinded":
        ax.scatter(x, y, s=26, alpha=0.7, color=color, edgecolor="none",
                   label="contrast")
    else:
        ax.scatter(x, y, s=26, alpha=0.7, color=color, edgecolor="white",
                   linewidth=0.4, label="contrast")
    ax.plot(xs_line, a0 + b0 * xs_line, color=color, linewidth=1.6,
            label="fitted trend")
    ax.fill_between(xs_line, lo, hi, color=color, alpha=0.15,
                    label="95% CI (bootstrap over experiments)")
    ax.set_xlabel("|human effect| (std units)")
    ax.set_ylabel("share of eligible LLMs with correct direction")
    # identical axes across the blinded/disclosed pair; band visually
    # clipped to 0-1 by the y-limits (documented in FIGURE_GUIDE.md)
    ax.set_xlim(0.0, 1.5)
    ax.set_ylim(0.0, 1.0)
    ax.legend(frameon=False, fontsize=7.5, loc="lower right")
    fig.tight_layout()
    acc.to_csv(FIG_DIR / f"{name}.csv", index=False)
    save_figure(fig, name)


def fig07_direction_accuracy(cells):
    _accuracy_trend_fig(cells, "blinded", "fig07_direction_accuracy_blinded")
    _accuracy_trend_fig(cells, "disclosed",
                        "fig07_direction_accuracy_disclosed")


def main():
    effects = load_effects()
    contrasts = contrast_table()
    n_conf = contrasts.direction_confident.sum()
    print(f"contrasts: {len(contrasts)} ({n_conf} direction-confident)")
    if n_conf != 32:
        raise ValueError(f"expected 32 confident contrasts, got {n_conf}")
    cells = cell_directions(effects, contrasts)
    slopes = fig03_04_recovery_scatter(cells)
    fig05_slopes(slopes)
    fig06_abs_error(cells)
    fig07_direction_accuracy(cells)
    print("effect figures 03-07 done")


if __name__ == "__main__":
    main()
