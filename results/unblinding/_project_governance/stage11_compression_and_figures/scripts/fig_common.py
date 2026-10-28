# fig_common.py — shared setup for the Stage 11 exploratory figures.
#
# What this file does: it points every figure script at the corrected Stage 10
# data (read-only), loads the tables, decides which human effect directions are
# trustworthy (the same two-sided 95% rule Stage 6 used), and saves figures in
# the required formats (PNG at 300 dpi, vector PDF, plus a small CSV of the
# exact plotted numbers written by each figure script).
#
# Functions:
#   load_effects()     -> corrected per-model effect table (reconciled_v1)
#   load_paired()      -> corrected blinded-vs-disclosed paired table
#   contrast_table()   -> one row per contrast: readable name, human effect,
#                         and whether the human direction is confident
#   cell_directions()  -> per model x contrast: is the LLM direction right?
#   stage10_slope_ci() -> the prespecified Stage 10 corrected magnitude-
#                         recovery estimator (WLS through origin on
#                         model-means within contrast, experiment-equal
#                         weights) with its frozen family-bootstrap CI,
#                         read from the Stage 10 corrected outputs
#   pooled_slope_ci()  -> (legacy exploratory slope; kept for reference,
#                         no longer used by the final figures)
#   boot_mean_ci()     -> mean of per-group values with a bootstrap CI
#   save_figure()      -> writes PNG (300 dpi) + PDF, then closes the figure

import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import norm

os.environ.setdefault("MPLCONFIGDIR", "/tmp/mplcache-stage11")

UNBLINDING = Path("/home/justin/Documents/ZJU work/fos/results/unblinding")
STAGE10_DATA = UNBLINDING / "_project_governance/stage10_data_reconciliation/data"
STAGE11_DIR = Path(__file__).resolve().parent.parent
FIG_DIR = STAGE11_DIR / "figures"
STAGE3_CORRECTED = (UNBLINDING / "_project_governance/"
                    "stage10_data_reconciliation/corrected_results/stage3")

# One seed for every resampling procedure, so every figure is reproducible.
SEED = 20261028
N_BOOT = 2000

# Accessible, colour-blind-safe palette.
C_HUMAN = "#2166ac"     # blue: human data
C_LLM = "#e08214"       # orange: LLM data
C_BLINDED = "#4393c3"
C_BLINDED_DARK = "#2166ac"  # darker blue: blinded fitted lines/bands
C_DISCLOSED = "#d6604d"
C_CORRECT = "#2166ac"
C_WRONG = "#b2182b"
C_MISSING = "#d9d9d9"

BLINDING_NAME = {0: "blinded", 1: "disclosed"}


def load_effects() -> pd.DataFrame:
    """The corrected Stage 10 model-effects table (never the frozen Stage 5/9 numbers)."""
    df = pd.read_csv(STAGE10_DATA / "CANONICAL_MODEL_EFFECTS.csv")
    df = df.loc[:, ~df.columns.str.startswith("human_effect_std.")]
    df["condition"] = df["blinding"].map(BLINDING_NAME)
    return df


def load_paired() -> pd.DataFrame:
    """The corrected paired blinded/disclosed table with the new uncertainties."""
    df = pd.read_csv(STAGE10_DATA / "CANONICAL_PAIRED_ANALYSIS.csv")
    df = df.loc[:, ~df.columns.str.startswith("human_effect_std.")]
    return df


def _readable_name(row) -> str:
    """Turn experiment id + arm conditions into a short readable label."""
    exp = str(row["experiment_id"])
    t = str(row.get("treatment_condition", ""))
    c = str(row.get("control_condition", ""))
    if t and c and t != "nan" and c != "nan":
        return f"{exp}\n({t} \u2212 {c})"
    return exp


def contrast_table() -> pd.DataFrame:
    """One row per contrast with the human effect and direction confidence.

    A human direction counts as confident when the two-sided 95% interval
    excludes zero (pr < 0.025 or pr > 0.975) — the same rule that produced
    the 32 confident contrasts reported in Stage 6.
    """
    pa = load_paired()
    first = pa.groupby("contrast_id", as_index=False).first()
    pr_pos = norm.cdf(first["human_effect_std"] / first["human_effect_se"])
    first["human_pr_pos"] = pr_pos
    first["direction_confident"] = (pr_pos < 0.025) | (pr_pos > 0.975)
    first["abs_human_effect"] = first["human_effect_std"].abs()
    first["label"] = first.apply(_readable_name, axis=1)
    return first


def load_direction_results() -> pd.DataFrame:
    """Stage 6 per-cell direction calls, kept only as a cross-check reference."""
    path = UNBLINDING / "_project_governance/stage6_direction_and_disclosure/DIRECTION_RESULTS.csv"
    return pd.read_csv(path)


def cell_directions(effects: pd.DataFrame, contrasts: pd.DataFrame) -> pd.DataFrame:
    """Merge model cells with contrast info and score direction correctness.

    A cell is 'correct' when the LLM effect has the same sign as the (confident)
    human effect. Cells with no data stay missing and are never counted wrong.
    """
    df = effects.merge(
        contrasts[["contrast_id", "human_effect_std", "direction_confident",
                   "abs_human_effect", "label", "experiment_id"]],
        on="contrast_id", suffixes=("", "_c"))
    df["llm_sign"] = np.sign(df["model_effect_std"])
    df["human_sign"] = np.sign(df["human_effect_std"])
    df["direction_correct"] = (df["llm_sign"] == df["human_sign"]) & (df["llm_sign"] != 0)
    df["abs_error"] = (df["model_effect_std"] - df["human_effect_std"]).abs()
    return df


def stage10_slope_ci() -> dict[str, tuple[float, float, float]]:
    """The prespecified Stage 10 corrected recovery slopes with their CIs.

    Estimator (frozen Stage 3 method, rerun on reconciled_v1 data in
    Stage 10): collapse to model-means within experiment x contrast,
    weight 1/k_e per experiment, WLS slope of model effect on human effect
    forced through the origin. CI: family-cluster bootstrap (resampling
    paradigm families), frozen seeds 20261010 + per-statistic offsets —
    deterministic, no refitting here. The point estimate is recomputed
    from the corrected signed table and must match the recorded value
    exactly, otherwise something moved and we refuse to plot.
    """
    signed = pd.read_csv(STAGE3_CORRECTED / "corrected_signed_contrasts.csv")
    g = signed.groupby(["experiment", "contrast"], as_index=False).agg(
        H=("H", "mean"), M_B=("M_B", "mean"), M_U=("M_U", "mean"))
    k_e = signed.groupby("experiment")["contrast"].nunique()
    g["w"] = g["experiment"].map(1.0 / k_e)
    point = {}
    for cond, col in (("blinded", "M_B"), ("disclosed", "M_U")):
        point[cond] = float((g.w * g.H * g[col]).sum()
                            / (g.w * g.H * g.H).sum())
    recorded = pd.read_csv(
        STAGE3_CORRECTED / "recovery_slopes_signed_bias_figure3.csv"
    ).set_index("statistic")["value"]
    for cond, key in (("blinded", "recovery_blinded"),
                      ("disclosed", "recovery_disclosed")):
        if abs(point[cond] - float(recorded[key])) > 1e-9:
            raise RuntimeError(
                f"Stage 10 corrected slope {key} changed: computed "
                f"{point[cond]} vs recorded {recorded[key]} — refusing "
                "to plot unverified estimates")
    cis = pd.read_csv(STAGE3_CORRECTED / "bootstrap_cis_frozen_method.csv"
                      ).set_index("quantity")
    out = {}
    for cond, key in (("blinded", "recovery_blinded"),
                      ("disclosed", "recovery_unblinded")):
        row = cis.loc[key]
        out[cond] = (point[cond], float(row.ci95_low), float(row.ci95_high))
    return out


def pooled_slope_ci(df: pd.DataFrame, value_col: str = "model_effect_std",
                    seed: int = SEED, n_boot: int = N_BOOT):
    """Slope of LLM effect on human effect across all cells, with contrast
    fixed effects accounted for through the uncertainty: the confidence
    interval comes from resampling whole contrasts (a contrast-level cluster
    bootstrap), so cells within one contrast never count as independent.
    """
    x = df["human_effect_std"].to_numpy(float)
    y = df[value_col].to_numpy(float)
    cid = df["contrast_id"].to_numpy()

    def slope_of(xv, yv):
        if len(xv) < 2 or np.ptp(xv) == 0:
            return np.nan
        b, _ = np.polyfit(xv, yv, 1)
        return float(b)

    point = slope_of(x, y)
    rng = np.random.default_rng(seed)
    levels = np.unique(cid)
    index_of = {c: np.where(cid == c)[0] for c in levels}
    boots = []
    for _ in range(n_boot):
        pick = rng.choice(levels, size=len(levels), replace=True)
        idx = np.concatenate([index_of[c] for c in pick])
        boots.append(slope_of(x[idx], y[idx]))
    boots = np.asarray(boots, float)
    boots = boots[~np.isnan(boots)]
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return float(point), float(lo), float(hi), boots


def boot_mean_ci(values: pd.Series, groups: pd.Series, seed: int = SEED,
                 n_boot: int = N_BOOT):
    """Mean of per-group values with a bootstrap CI that resamples the groups.

    Used for experiment-equal-weighted estimates: `values` holds one number
    per experiment and `groups` just labels them, so each experiment counts
    once no matter how many contrasts or models it contains.
    """
    v = np.asarray(values, float)
    v = v[~np.isnan(v)]
    point = float(v.mean())
    rng = np.random.default_rng(seed)
    boots = [float(np.mean(rng.choice(v, size=len(v), replace=True)))
             for _ in range(n_boot)]
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return point, float(lo), float(hi)


def save_figure(fig: plt.Figure, name: str,
                out_dir: Path | None = None) -> None:
    """Write the figure as PNG (300 dpi) and vector PDF into figures/.

    out_dir overrides the default (used by the worktree-relative Figure 02
    pipeline so runs write next to the code that produced them).
    """
    target = out_dir or FIG_DIR
    if not os.access(target, os.W_OK):
        # read-only live tree (sandboxed run): write next to this code
        target = Path(__file__).resolve().parent.parent / "figures"
    target.mkdir(parents=True, exist_ok=True)
    fig.savefig(target / f"{name}.png", dpi=300, bbox_inches="tight")
    fig.savefig(target / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)
    print(f"saved: figures/{name}.png + .pdf")
