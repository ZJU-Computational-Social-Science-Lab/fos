# Prepares the tidy datasets the hierarchical Bayesian models consume.
#
# What this file does: it reads the Phase 2 output CSVs (per-contrast
# effects and per-cell TVD distances for the five models, original vs
# redesigned persona pools) and builds three tidy tables, one per
# scientific outcome:
#   1. direction  — one row per model × era × experiment × contrast ×
#                   condition, saying whether the model effect agreed with
#                   the human effect's sign (near-zero human effects
#                   excluded, as in the Phase 2 headline).
#   2. magnitude  — same rows, carrying the model effect and the human
#                   effect in human-SD units.
#   3. tvd        — one row per model × era × experiment × condition, the
#                   total-variation distance from the human answer
#                   distribution (per-arm values averaged within each
#                   disclosure condition, as in the historically validated
#                   procedure).
# Each row also gets integer group indexes (model, experiment, contrast
# cell) that the Bayesian models need.
#
# What each function does:
#   load_effects    — reads the unified effect CSV and keeps non-near-zero rows.
#   load_tvd        — reads the twin + expansion TVD CSVs and averages arm
#                     values within each disclosure condition.
#   add_group_codes — turns model/experiment/contrast labels into integer codes.
#   build_direction_magnitude — assembles tables 1 and 2 (same rows).
#   main            — builds all three tables and prints a row-count summary.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from config import MODELS, OUT


@dataclass
class BayesDatasets:
    """The three tidy tables plus the string→code lookup tables."""

    direction: pd.DataFrame
    magnitude: pd.DataFrame
    tvd: pd.DataFrame


def load_effects() -> pd.DataFrame:
    """Read the unified effect table; drop near-zero human effects."""
    effects = pd.read_csv(OUT / "five_model_all_effects.csv")
    effects = effects[effects.model.isin(MODELS)]
    return effects[~effects.near_zero_human.astype(bool)].copy()


def load_tvd() -> pd.DataFrame:
    """Average per-arm TVD values within each disclosure condition."""
    twin = pd.read_csv(OUT / "five_model_twin_tvd.csv")
    twin = twin.rename(columns={"blinding": "condition"})
    t2kx = pd.read_csv(OUT / "five_model_t2kx_tvd.csv")
    cells = pd.concat([twin[["model", "era", "experiment", "condition", "tvd"]],
                       t2kx[["model", "era", "experiment", "condition", "tvd"]]])
    cells = cells[cells.model.isin(MODELS)]
    cells = cells.dropna(subset=["tvd"])
    grouped = (cells.groupby(["model", "era", "experiment", "condition"],
                             as_index=False)
               .agg(tvd=("tvd", "mean"), n_arms=("tvd", "size")))
    return grouped


def add_group_codes(table: pd.DataFrame) -> pd.DataFrame:
    """Add integer codes for model, experiment, and contrast cell."""
    out = table.copy()
    out["model_code"] = out.model.astype("category").cat.codes
    out["experiment_code"] = out.experiment.astype("category").cat.codes
    # A contrast cell is (experiment, contrast_id): the nesting level.
    # Tables without a contrast id (the TVD cells) get a dummy code.
    cell_labels = (out.experiment + "|" + out.contrast_id
                   if "contrast_id" in out.columns else out.experiment)
    out["cell_code"] = cell_labels.astype("category").cat.codes
    return out


def build_direction_magnitude(effects: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Both effect tables share rows; direction keeps the sign-agreement flag."""
    coded = add_group_codes(effects)
    direction = coded[["model", "model_code", "era", "family", "experiment",
                       "experiment_code", "contrast_id", "cell_code",
                       "condition", "human_std", "sign_agrees"]].copy()
    direction["sign_agrees"] = direction.sign_agrees.astype(int)
    magnitude = coded[["model", "model_code", "era", "family", "experiment",
                       "experiment_code", "contrast_id", "cell_code",
                       "condition", "delta_std", "human_std"]].copy()
    return direction, magnitude


def main() -> None:
    """Build all three tables and print a summary."""
    effects = load_effects()
    direction, magnitude = build_direction_magnitude(effects)
    tvd = load_tvd()
    print(f"direction/magnitude rows: {len(direction)} "
          f"(models={direction.model.nunique()}, "
          f"experiments={direction.experiment.nunique()}, "
          f"cells={direction.cell_code.nunique()})")
    print(f"tvd rows: {len(tvd)} "
          f"(experiments={tvd.experiment.nunique()})")
    print(direction.groupby(['era', 'condition']).sign_agrees.agg(['size', 'mean']).to_string())


if __name__ == "__main__":
    main()
