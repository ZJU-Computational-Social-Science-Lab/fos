# Regenerates every figure in this folder from the SAVED summary files
# only (CSV / NPZ / NetCDF). It never refits any model and never touches
# the raw run data, so a full re-run takes seconds and is fully
# deterministic (fixed matplotlib settings; SOURCE_DATE_EPOCH pins the
# PDF timestamps).
#
# What it draws, and the file each quantity comes from:
#   fig_gradient        — observed directional accuracy in |human effect|
#                         quartile bands + posterior predicted accuracy
#                         curve (gradient_data.csv, predicted_accuracy.csv,
#                         gradient_summary.csv).
#   fig_calibration     — predicted vs human effect scatter with the
#                         fitted pooled-per-condition known-SE slope line
#                         (final15_primary_effects.csv,
#                         posterior_calibration_summary.csv).
#   fig_tvd             — per-experiment model-human TVD per model with
#                         the human split-half floor line
#                         (final15_primary_twin_tvd.csv,
#                         final15_primary_t2kx_tvd.csv, floor_draws.csv).
#   fig_forest          — per-experiment and per-model posterior TVD
#                         forest (posterior_ratio_draws.csv,
#                         posterior_floor_draws.npz).
#   fig_ratio_posterior — posterior density of the TVD/floor ratio
#                         (posterior_ratio_draws.csv).
#   fig_disc_accuracy   — predicted accuracy by condition from the pooled
#                         interaction fit
#                         (disc_interaction_predicted_accuracy.csv).
#   fig_disc_errors     — paired magnitude MAE and TVD by model, both
#                         conditions (disc_mae_by_model.csv,
#                         disc_tvd_by_model.csv).
#
# Usage: python regenerate_figures.py [output_dir]
# Output defaults to ./regen_check so the original figures are never
# overwritten. Run it twice and compare (e.g. with cmp) to verify
# byte-identical output.

from __future__ import annotations

import os
import sys
from pathlib import Path

# Pin PDF metadata timestamps before matplotlib imports, so two runs
# produce byte-identical PDFs as well as PNGs.
os.environ.setdefault("SOURCE_DATE_EPOCH", "946684800")

import matplotlib  # noqa: E402

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "regen_check"

CONDITION_ORDER = ["uninformed", "disclosure"]
UN_COLOR = "#3556a5"
DIS_COLOR = "#a53c2e"
MODELS = [
    "gpt-oss-20b",
    "gemma-4-26b-a4b",
    "gemma-4-31b-it-qat",
    "gemma-4-12b-it-qat",
    "qwen3.8-27b",
    "qwen3.6-27b-dense",
    "qwen3.6-35b-a3b",
    "qwen3.6-35b-a3b-uncensored",
    "qwen3-32b",
    "qwen3-4b",
    "granite-4.1-8b",
    "granite-4.1-30b",
    "nemotron-cascade-2-30b-a3b",
    "muse-glimmer",
    "glm-4.7-flash",
]


def csv(name: str) -> pd.DataFrame:
    """Load one saved summary file from this folder."""
    return pd.read_csv(HERE / name)


def save(fig: plt.Figure, stem: str) -> None:
    """Write one figure as PNG and PDF into the output folder."""
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{stem}.png", dpi=200)
    fig.savefig(OUT / f"{stem}.pdf")
    plt.close(fig)


def quartile_bands(sub: pd.DataFrame) -> pd.DataFrame:
    """Four equal-count |human| bands with observed accuracy per band."""
    sub = sub.copy()
    sub["band"] = pd.qcut(sub.abs_human_sd, 4, duplicates="drop")
    grouped = sub.groupby("band", observed=True).agg(
        n_cells=("correct_direction", "size"),
        obs_accuracy=("correct_direction", "mean"),
        band_mid=("abs_human_sd", "median"),
    )
    grouped["band_hi"] = [iv.right for iv in grouped.index]
    grouped["band_lo"] = [iv.left for iv in grouped.index]
    return grouped.reset_index(drop=True)


def binom_ci(k: int, n: int) -> tuple[float, float]:
    """95% Wilson interval for k successes in n trials."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    z = 1.959963985
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, center - half), min(1.0, center + half))


def draw_gradient_panel(
    ax, sub: pd.DataFrame, pred: pd.DataFrame, title: str, max_supported: float
) -> None:
    """One condition's observed bands + posterior predicted curve."""
    bands = quartile_bands(sub)
    xs = (bands.band_lo + bands.band_hi) / 2
    cis = [binom_ci(round(a * n), n) for a, n in zip(bands.obs_accuracy, bands.n_cells)]
    ax.errorbar(
        xs,
        bands.obs_accuracy,
        yerr=[
            [a - lo for a, (lo, _) in zip(bands.obs_accuracy, cis)],
            [hi - a for a, (_, hi) in zip(bands.obs_accuracy, cis)],
        ],
        fmt="o",
        color="black",
        capsize=3,
        label="observed (quartile bands)",
    )
    ax.plot(pred.abs_human_sd, pred.acc_mean, color="#1f6fb4", label="posterior mean")
    ax.fill_between(
        pred.abs_human_sd,
        pred.acc_lo95,
        pred.acc_hi95,
        color="#1f6fb4",
        alpha=0.2,
        label="95% CrI",
    )
    ax.axvline(max_supported, color="grey", linestyle="--", linewidth=1)
    ax.set_xlabel("|human effect| (SD units)")
    ax.set_ylabel("directional accuracy")
    ax.set_ylim(0.4, 1.0)
    ax.set_title(title)
    ax.legend(loc="lower right", fontsize=8)


def fig_gradient() -> None:
    """Directional accuracy vs |human effect|, both conditions."""
    data = csv("gradient_data.csv")
    pred = csv("predicted_accuracy.csv")
    summary = csv("gradient_summary.csv")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharey=True)
    for ax, condition in zip(axes, CONDITION_ORDER):
        head = summary[summary.fit == condition].iloc[0]
        draw_gradient_panel(
            ax,
            data[data.condition == condition],
            pred[pred.condition == condition],
            f"{condition} (n={head.n_cells} cells)",
            float(head.max_abs_human_supported),
        )
    fig.suptitle(
        "Directional accuracy vs |human effect| — "
        "real-persona 15-model primary analysis"
    )
    fig.tight_layout()
    save(fig, "fig_gradient")


def fig_calibration() -> None:
    """Predicted vs human effect scatter with fitted slope lines."""
    table = csv("final15_primary_effects.csv").dropna(subset=["delta_std", "human_std"])
    fits = pd.read_csv(HERE / "posterior_calibration_summary.csv", index_col=0)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.6), sharex=True, sharey=True)
    for ax, cond in zip(axes, CONDITION_ORDER):
        sub = table[table.condition == cond]
        ax.scatter(
            sub.human_std,
            sub.delta_std,
            s=14,
            alpha=0.55,
            color="#3556a5",
            edgecolors="none",
        )
        lo = float(min(sub.human_std.min(), sub.delta_std.min()))
        hi = float(max(sub.human_std.max(), sub.delta_std.max()))
        pad = 0.1 * (hi - lo)
        grid = np.linspace(lo - pad, hi + pad, 50)
        row = fits.loc[f"{cond}_known_se"]
        b = float(row.slope_mean)
        a = float(row.a_mean)
        ax.plot(grid, a + b * grid, color="#a53c2e", lw=2, label=f"fitted slope {b:.2f}")
        ax.plot(grid, grid, color="0.4", lw=1, ls="--", label="slope 1")
        ax.set_title(f"{cond} (n={len(sub)} contrasts)")
        ax.set_xlabel("human effect (SD units)")
        ax.legend(fontsize=8, loc="upper left")
    axes[0].set_ylabel("model predicted effect (SD units)")
    fig.suptitle("Magnitude calibration — real-persona thirteen-model run")
    fig.tight_layout()
    save(fig, "fig_calibration")


def floor_mean_overall(floor_draws: pd.DataFrame) -> float:
    """Mean over experiments of each experiment's mean split-half TVD."""
    per_exp = floor_draws.groupby("experiment").tvd.mean()
    return float(per_exp.mean())


def fig_tvd() -> None:
    """Per-experiment model-human TVD per model + floor reference line."""
    twin = csv("final15_primary_twin_tvd.csv").dropna(subset=["tvd"]).assign(family="twin")
    t2kx = csv("final15_primary_t2kx_tvd.csv").dropna(subset=["tvd"]).assign(family="t2kx")
    floor = csv("floor_draws.csv")
    cells = pd.concat([twin, t2kx])
    per_cell = cells.groupby(["family", "experiment", "model"]).tvd.mean()
    order = cells.groupby("experiment").tvd.mean().sort_values().index
    fig, ax = plt.subplots(figsize=(11, 5.5))
    colors = {
        m: c
        for m, c in zip(
            MODELS,
            plt.get_cmap("tab20")(np.linspace(0, 0.95, max(len(MODELS), 1))),
        )
    }
    for model in MODELS:
        xs, ys = [], []
        for i, exp in enumerate(order):
            for family in ("twin", "t2kx"):
                v = per_cell.get((family, exp, model))
                if v is not None and v == v:
                    xs.append(i + 0.16 * MODELS.index(model) - 0.32)
                    ys.append(v)
        ax.scatter(xs, ys, s=16, label=model, alpha=0.75, color=colors[model], edgecolors="none")
    floor_line = floor_mean_overall(floor)
    ax.axhline(floor_line, color="0.2", ls="--", lw=1.5, label=f"human split-half floor ({floor_line:.3f})")
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels(order, rotation=60, ha="right", fontsize=8)
    ax.set_ylabel("model–human TVD (mean over cells)")
    ax.set_title("Distributional fidelity — real-persona thirteen-model run")
    ax.legend(fontsize=8, ncol=3)
    fig.tight_layout()
    save(fig, "fig_tvd")


def fig_forest() -> None:
    """Per-experiment and per-model posterior mean TVD forest."""
    draws = csv("posterior_ratio_draws.csv")
    floor_npz = np.load(HERE / "posterior_floor_draws.npz", allow_pickle=True)
    floor_mean = floor_npz["floor_mean"]
    experiments = [str(e) for e in floor_npz["experiments"]]
    models = sorted([c[4:] for c in draws.columns if c.startswith("num_")])
    rows = []
    for exp in experiments:
        q = np.quantile(draws[f"numexp_{exp}"], [0.025, 0.5, 0.975])
        rows.append(("experiment", exp, q))
    for model in models:
        q = np.quantile(draws[f"num_{model}"], [0.025, 0.5, 0.975])
        rows.append(("model", model, q))
    fig, ax = plt.subplots(figsize=(9, 7))
    n = len(rows)
    for i, (group, name, q) in enumerate(rows):
        y = n - 1 - i
        color = "#3556a5" if group == "experiment" else "#a53c2e"
        ax.plot([q[0], q[2]], [y, y], color=color, lw=2)
        ax.scatter([q[1]], [y], color=color, s=28, zorder=3)
    fq = np.quantile(floor_mean, [0.025, 0.5, 0.975])
    ax.axvline(fq[1], color="0.2", ls="--", lw=1.5, label=f"human split-half floor (median {fq[1]:.4f})")
    ax.set_yticks(range(n))
    ax.set_yticklabels([name for _, name, _ in reversed(rows)], fontsize=8)
    ax.set_xlabel("posterior mean TVD (95% CrI)")
    ax.set_title("Per-experiment (blue) and per-model (red) model-human TVD")
    ax.legend(fontsize=8)
    fig.tight_layout()
    save(fig, "fig_forest")


def fig_ratio_posterior() -> None:
    """Posterior density of the TVD / floor ratio with CrI markers."""
    draws = csv("posterior_ratio_draws.csv")
    ratio = draws.ratio.to_numpy()
    q = np.quantile(ratio, [0.025, 0.5, 0.975])
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.hist(ratio, bins=120, density=True, color="#3556a5", alpha=0.75)
    for ref in (1, 5, 10):
        ax.axvline(ref, color="0.4", ls=":", lw=1)
    ax.axvline(q[1], color="#a53c2e", lw=2, label=f"median {q[1]:.1f}")
    ax.axvline(q[0], color="#a53c2e", lw=1.5, ls="--", label=f"95% CrI [{q[0]:.1f}, {q[2]:.1f}]")
    ax.axvline(q[2], color="#a53c2e", lw=1.5, ls="--")
    ax.set_xlabel("posterior ratio  E[model-human TVD] / E[split-half floor]")
    ax.set_ylabel("posterior density")
    ax.set_title("Bayesian reanalysis — matched TVD ratio (all 15 real-persona models)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    save(fig, "fig_ratio_posterior")


def fig_disc_accuracy() -> None:
    """Predicted accuracy by |human effect| per condition, with bands."""
    preds = csv("disc_interaction_predicted_accuracy.csv")
    fig, ax = plt.subplots(figsize=(6.4, 4.4))
    for condition, color, dash in [
        ("uninformed", UN_COLOR, "-"),
        ("disclosure", DIS_COLOR, "--"),
    ]:
        sub = preds[preds.condition == condition].sort_values("abs_human_sd")
        ax.plot(sub.abs_human_sd, sub.acc_mean, dash, color=color, marker="o", label=condition)
        ax.fill_between(sub.abs_human_sd, sub.acc_lo95, sub.acc_hi95, color=color, alpha=0.15)
    ax.set_xlabel("|human effect| (SD)")
    ax.set_ylabel("predicted direction accuracy")
    ax.set_ylim(0.5, 1.0)
    ax.legend()
    ax.set_title("Predicted accuracy by condition\n(pooled interaction fit; bands = 95% CrI)")
    fig.tight_layout()
    save(fig, "fig_disc_accuracy")


def fig_disc_errors() -> None:
    """Paired MAE and TVD per model, both conditions side by side."""
    mae = csv("disc_mae_by_model.csv")
    tvd = csv("disc_tvd_by_model.csv")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    for ax, frame, cols, title in [
        (axes[0], mae, ("mae_uninformed", "mae_disclosure"), "Magnitude MAE by model (SD)"),
        (axes[1], tvd, ("tvd_uninformed", "tvd_disclosure"), "TVD by model (mean over cells)"),
    ]:
        x = range(len(frame))
        ax.bar([i - 0.2 for i in x], frame[cols[0]], width=0.4, color=UN_COLOR, label="uninformed")
        ax.bar([i + 0.2 for i in x], frame[cols[1]], width=0.4, color=DIS_COLOR, label="disclosure")
        ax.set_xticks(list(x))
        ax.set_xticklabels(frame.iloc[:, 0], rotation=30, ha="right", fontsize=8)
        ax.set_title(title)
        ax.legend(fontsize=8)
    fig.tight_layout()
    save(fig, "fig_disc_errors")


def main() -> None:
    """Regenerate all seven figures into the output folder."""
    fig_gradient()
    fig_calibration()
    fig_tvd()
    fig_forest()
    fig_ratio_posterior()
    fig_disc_accuracy()
    fig_disc_errors()
    print(f"figures written to {OUT}")


if __name__ == "__main__":
    main()
