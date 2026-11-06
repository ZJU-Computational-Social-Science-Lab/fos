# Builds the comparison table and figures from the two outcome CSVs.
#
# What this file does: it reads the twin and T2KX effect-level CSVs and
# the two TVD CSVs produced by twin_analysis.py and t2kx_analysis.py, and
# writes:
#   - five_model_all_effects.csv  — one unified effect-level table (both
#     families, both eras, SD units, with per-cell sign agreement and a
#     "near-zero human effect" flag);
#   - MODEL_COMPARISON.csv — the headline table: per model (and pooled
#     over the five models) × outcome (direction agreement, magnitude
#     error, TVD) × disclosure condition, original vs redesigned side by
#     side in long format;
#   - three figures (PNG + PDF): direction agreement, magnitude error,
#     and TVD, original vs redesigned per model and condition.
# Direction is measured on cells whose human effect is not near zero
# (|human effect| >= 0.10 SD); near-zero cells get their own row so they
# are analyzed separately, never silently mixed in.
#
# What each function does:
#   load_effects    — reads both effect CSVs, unifies columns, adds the
#                     family (twin/expansion), sign agreement, and
#                     near-zero flags; writes the unified CSV.
#   direction_rows  — per model/condition/era: agreement with the human
#                     sign over non-near-zero cells, plus the near-zero
#                     subset separately.
#   magnitude_rows  — per model/condition/era: mean absolute error of the
#                     effect in SD units over non-near-zero cells.
#   tvd_rows        — per model/condition/era: mean TVD over the
#                     comparable experiments (twin registry supports, and
#                     the support-matched expansion experiments).
#   build_table     — assembles the long-format MODEL_COMPARISON.csv with
#                     a POOLED-5 row per outcome/condition/era.
#   make_figures    — renders the three comparison figures.
#   main            — runs the above and prints the headline numbers.

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/mplconfig-five-model")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import CONDITION_LABELS, MODELS, NEAR_ZERO_SD, OUT

ERAS = ["original", "redesigned"]
OUTCOMES = ["direction_agreement", "direction_agreement_near_zero_only",
            "magnitude_mae_sd", "mean_tvd"]


def load_effects() -> pd.DataFrame:
    """Unified effect-level table in SD units with flags, written out."""
    twin = pd.read_csv(OUT / "five_model_twin_effects.csv")
    t2kx = pd.read_csv(OUT / "five_model_t2kx_effects.csv")
    twin["family"] = "twin"
    t2kx["family"] = "expansion"
    keep = ["model", "era", "family", "experiment", "contrast_id",
            "blinding", "delta_std", "human_std"]
    frame = pd.concat([twin[keep], t2kx[keep]], ignore_index=True)
    frame = frame.rename(columns={"blinding": "condition"})
    frame["condition"] = frame.condition.map(CONDITION_LABELS)
    frame = frame[frame.delta_std.notna() & frame.human_std.notna()]
    frame["sign_agrees"] = np.sign(frame.delta_std) == np.sign(frame.human_std)
    frame["near_zero_human"] = frame.human_std.abs() < NEAR_ZERO_SD
    frame["abs_error_sd"] = (frame.delta_std - frame.human_std).abs()
    frame.to_csv(OUT / "five_model_all_effects.csv", index=False)
    return frame


def load_tvd() -> pd.DataFrame:
    """Unified TVD table with the report's condition labels."""
    twin = pd.read_csv(OUT / "five_model_twin_tvd.csv")
    t2kx = pd.read_csv(OUT / "five_model_t2kx_tvd.csv")
    twin["family"] = "twin"
    t2kx["family"] = "expansion"
    keep = ["model", "era", "family", "experiment", "blinding", "tvd"]
    frame = pd.concat([twin[keep], t2kx[keep]], ignore_index=True)
    frame = frame.rename(columns={"blinding": "condition"})
    frame["condition"] = frame.condition.map(CONDITION_LABELS)
    return frame[frame.tvd.notna()]


def _rate(sub: pd.DataFrame) -> tuple[float, int]:
    """Sign-agreement rate and cell count of one subset."""
    return float(sub.sign_agrees.mean()), int(len(sub))


def direction_rows(effects: pd.DataFrame) -> list[dict]:
    """Direction-agreement rows, near-zero human effects kept separate."""
    rows: list[dict] = []
    main = effects[~effects.near_zero_human]
    near = effects[effects.near_zero_human]
    def emit(frame: pd.DataFrame, model: str, outcome: str) -> None:
        pool = frame if model == "POOLED-5" else \
            frame[frame.model == model]
        for condition in ("uninformed", "disclosure"):
            for era in ERAS:
                sub = pool[(pool.condition == condition)
                           & (pool.era == era)]
                value, n = _rate(sub)
                rows.append({"model": model, "outcome": outcome,
                             "condition": condition, "era": era,
                             "value": value, "n_cells": n})
    for model in MODELS + ["POOLED-5"]:
        emit(main, model, "direction_agreement")
        emit(near, model, "direction_agreement_near_zero_only")
    return rows


def magnitude_rows(effects: pd.DataFrame) -> list[dict]:
    """Mean absolute error (SD units) over non-near-zero cells."""
    rows: list[dict] = []
    main = effects[~effects.near_zero_human]
    for model in MODELS + ["POOLED-5"]:
        pool = main if model == "POOLED-5" else main[main.model == model]
        for condition in ("uninformed", "disclosure"):
            for era in ERAS:
                sub = pool[(pool.condition == condition)
                           & (pool.era == era)]
                rows.append({"model": model,
                             "outcome": "magnitude_mae_sd",
                             "condition": condition, "era": era,
                             "value": float(sub.abs_error_sd.mean()),
                             "n_cells": int(len(sub))})
    return rows


def tvd_mean_rows(tvd: pd.DataFrame) -> list[dict]:
    """Mean TVD per model/condition/era over comparable experiments."""
    rows: list[dict] = []
    for model in MODELS + ["POOLED-5"]:
        pool = tvd if model == "POOLED-5" else tvd[tvd.model == model]
        for condition in ("uninformed", "disclosure"):
            for era in ERAS:
                sub = pool[(pool.condition == condition)
                           & (pool.era == era)]
                rows.append({"model": model, "outcome": "mean_tvd",
                             "condition": condition, "era": era,
                             "value": float(sub.tvd.mean()),
                             "n_cells": int(len(sub))})
    return rows


def build_table(effects: pd.DataFrame, tvd: pd.DataFrame) -> pd.DataFrame:
    """Long-format comparison table, one row per outcome×cond×era."""
    rows = direction_rows(effects) + magnitude_rows(effects) + \
        tvd_mean_rows(tvd)
    table = pd.DataFrame(rows)
    table.to_csv(OUT / "MODEL_COMPARISON.csv", index=False)
    return table


def _era_values(table: pd.DataFrame, model: str, outcome: str,
                condition: str) -> tuple[float, float]:
    """(original, redesigned) values for one bar group."""
    sub = table[(table.model == model) & (table.outcome == outcome)
                & (table.condition == condition)]
    get = lambda era: float(sub[sub.era == era].value.iloc[0])
    return get("original"), get("redesigned")


def make_figures(table: pd.DataFrame) -> None:
    """Three figures: direction agreement, magnitude error, TVD."""
    specs = [
        ("direction_agreement", "fig_direction",
         "Direction agreement with human effect sign (non-near-zero cells)",
         "Share of contrasts agreeing with human direction", 100, "%"),
        ("magnitude_mae_sd", "fig_magnitude",
         "Mean absolute effect error (human-SD units, non-near-zero cells)",
         "Mean |model effect − human effect| (SD)", 1, ""),
        ("mean_tvd", "fig_tvd",
         "Distributional fidelity: mean TVD vs human distribution",
         "Mean total-variation distance (lower is better)", 1, ""),
    ]
    for outcome, stem, title, ylabel, scale, unit in specs:
        fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
        for ax, condition in zip(axes, ("uninformed", "disclosure")):
            x = np.arange(len(MODELS))
            width = 0.38
            for k, (era, color) in enumerate(
                    (("original", "tab:gray"), ("redesigned", "tab:blue"))):
                vals = [scale * _era_values(table, m, outcome, condition)[
                    0 if era == "original" else 1] for m in MODELS]
                ax.bar(x + (k - 0.5) * width, vals, width, label=era,
                       color=color)
            ax.set_xticks(x)
            ax.set_xticklabels(MODELS, rotation=30, ha="right",
                               fontsize=8)
            ax.set_title(f"{condition} condition", fontsize=10)
            ax.set_ylabel(ylabel + ("" if not unit else ""), fontsize=9)
            ax.grid(axis="y", alpha=0.3)
        axes[0].legend(fontsize=8)
        fig.suptitle(title, fontsize=11)
        fig.tight_layout(rect=[0, 0, 1, 0.94])
        for ext in ("png", "pdf"):
            fig.savefig(OUT / f"{stem}.{ext}", dpi=200)
        plt.close(fig)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    effects = load_effects()
    tvd = load_tvd()
    table = build_table(effects, tvd)
    make_figures(table)
    head = table[table.model.isin(("POOLED-5",)) & ~
                 (table.outcome == "direction_agreement_near_zero_only")]
    print(head.pivot_table(index=["outcome", "condition"],
                           columns="era", values="value").to_string())
    print(f"wrote MODEL_COMPARISON.csv with {len(table)} rows; "
          f"{len(effects)} unified effect cells; {len(tvd)} TVD cells")


if __name__ == "__main__":
    main()
