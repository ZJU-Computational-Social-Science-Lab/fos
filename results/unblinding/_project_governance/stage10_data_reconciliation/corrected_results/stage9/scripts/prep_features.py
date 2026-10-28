# Prepares the regression inputs: turns the analysis table into two model-ready
# datasets (one for the "how far off was the AI" model, one for the "did it point the
# same direction" model). Continuous measurements are rescaled to a common range so
# their effect sizes can be compared, with the original averages/spreads saved to a
# JSON file so any number can be translated back to real units later. Categorical
# labels become 0/1 indicator columns next to a named reference category. A few
# features are missing for one or two experiments; those are filled with the typical
# value plus an explicit "this was missing" flag column, and every such choice is
# reported. Writes MODEL_INPUTS_A.csv, MODEL_INPUTS_B.csv and FEATURE_SCALING.json.

import json
from pathlib import Path

import numpy as np
import pandas as pd

STAGE9 = Path(__file__).resolve().parents[1]
SEED = 20261028

CONTINUOUS = ["question_length", "wording_difference", "manipulation_location",
              "n_response_options", "human_abs_d_std", "log_se_y_std"]
BINARY = ["gain_loss_framing", "numerical_manipulation", "explicit_probability",
          "negation_change", "role_change", "question_order", "response_options_change"]
FORMAT_REF = "rating_mean"   # verified modal category (540/1106 rows); spec suggested
                             # binary_choice but required verifying modality first
SELF_OTHER_REF = "self"
DISCLOSURE_INTERACTIONS = ["role_change", "manipulation_location"]


def load_table() -> pd.DataFrame:
    df = pd.read_csv(STAGE9 / "ANALYSIS_TABLE.csv")
    df["log_se_y_std"] = np.log(df["se_y_std_used"].clip(lower=1e-6))
    return df


def impute_continuous(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    # Missing continuous features get the typical (median) value plus a flag column,
    # so the model can both use the filled value and see that it was filled.
    df = df.copy()
    imputed = {}
    for col, flag in [("manipulation_location", "manipulation_location_na"),
                      ("n_response_options", "n_response_options_na")]:
        df[flag] = df[col].isna().astype(int)
        med = float(df[col].median())
        n_missing = int(df[col].isna().sum())
        if n_missing:
            print(f"imputed {col}: {n_missing} missing values -> median {med:.4f} + flag")
        df[col] = df[col].fillna(med)
        imputed[col] = {"median": med, "n_imputed": n_missing}
    return df, imputed


def scaling_record(df: pd.DataFrame) -> dict:
    return {c: {"mean": float(df[c].mean()), "sd": float(df[c].std(ddof=0))}
            for c in CONTINUOUS}


def standardize(df: pd.DataFrame, scaling: dict) -> pd.DataFrame:
    df = df.copy()
    for c, s in scaling.items():
        df[c] = (df[c] - s["mean"]) / s["sd"]
    return df


def categorical_dummies(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    df = df.copy()
    df["self_other"] = df["self_other"].str.strip()
    fmt = pd.get_dummies(df["response_format"], prefix="fmt", dtype=int)
    ref_fmt = f"fmt_{FORMAT_REF}"
    fmt = fmt.drop(columns=[ref_fmt])
    selfo = pd.get_dummies(df["self_other"], prefix="selfother", dtype=int)
    ref_so = f"selfother_{SELF_OTHER_REF}"
    if ref_so in selfo:
        selfo = selfo.drop(columns=[ref_so])
    df = pd.concat([df, fmt, selfo], axis=1)
    return df, [ref_fmt, ref_so]


def design_columns(df: pd.DataFrame) -> list[str]:
    cols = list(BINARY) + list(CONTINUOUS)
    cols += [c for c in df.columns if c.startswith("fmt_") or c.startswith("selfother_")]
    cols += ["manipulation_location_na", "n_response_options_na"]
    cols += ["disclosure"]
    cols += ["disclosure_x_role_change", "disclosure_x_manipulation_location"]
    return cols


def add_interactions(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for feat in DISCLOSURE_INTERACTIONS:
        df[f"disclosure_x_{feat}"] = df["disclosure"] * df[feat]
    return df


def main() -> None:
    df = load_table()
    df, imputed = impute_continuous(df)
    scaling = scaling_record(df)
    df = standardize(df, scaling)
    df, refs = categorical_dummies(df)
    df = add_interactions(df)

    record = {
        "seed": SEED,
        "continuous_scaling": scaling,
        "imputation": imputed,
        "reference_categories": {"response_format": refs[0], "self_other": refs[1]},
        "note": "continuous predictors standardized (z-scores); binary features kept 0/1",
    }
    (STAGE9 / "FEATURE_SCALING.json").write_text(json.dumps(record, indent=2))

    cols = design_columns(df)
    meta = ["contrast_id", "experiment_id", "study_group", "model", "blinding",
            "model_contrast_pair", "absolute_error", "correct_direction",
            "human_direction_confident", "y_std", "se_y_std_used", "human_se_std",
            "human_direction", "response_format", "self_other", "d_human_std"]
    keep = [c for c in meta if c in df.columns] + cols

    a = df[keep]
    a.to_csv(STAGE9 / "MODEL_INPUTS_A.csv", index=False)

    b = df[df["human_direction_confident"] == True][keep]  # noqa: E712
    b.to_csv(STAGE9 / "MODEL_INPUTS_B.csv", index=False)
    print(f"Model A: {a.shape[0]} rows, {len(cols)} predictors")
    print(f"Model B: {b.shape[0]} rows, {b['contrast_id'].nunique()} contrasts, "
          f"{b['correct_direction'].mean():.3f} direction-correct")
    print(f"wrote FEATURE_SCALING.json, MODEL_INPUTS_A.csv, MODEL_INPUTS_B.csv")


if __name__ == "__main__":
    main()
