# Builds the Stage 9 analysis table: takes the frozen Stage 5 dataset, keeps only
# paired model-vs-human cells, joins the human side of each contrast (from the Stage 7
# audit) and the blind-coded experiment features, and computes the two outcomes we
# want to explain (how far the AI was from the human result, and whether the AI pointed
# the same way as humans). Also fixes the known missing/zero uncertainty values for the
# original experiments by substituting bootstrap uncertainty estimates, keeping a clear
# record of every substitution. Writes ANALYSIS_TABLE.csv into the stage 9 folder.

from pathlib import Path

import numpy as np
import pandas as pd

STAGE9 = Path(__file__).resolve().parents[1]
# Frozen inputs live in the read-only project tree; only stage 9 outputs are written here.
GOV = Path("/home/justin/Documents/ZJU work/fos/results/unblinding/_project_governance")
SEED = 20261028


def assert_stage5_shape(d: pd.DataFrame) -> None:
    # The frozen Stage 5 dataset must match what earlier stages recorded.
    assert d.shape[0] == 1113, f"expected 1113 rows, got {d.shape[0]}"
    assert d["experiment_id"].nunique() == 31, "expected 31 experiments"
    assert d["contrast_id"].nunique() == 38, "expected 38 contrasts"
    assert d["model"].nunique() == 15, "expected 15 models"


def load_inputs():
    stage5 = pd.read_csv(GOV / "stage5_exploratory" / "data" / "stage5_dataset.csv")
    audit = pd.read_csv(GOV / "stage7_replication_evidence" / "DISAGREEMENT_AUDIT.csv")
    feats = pd.read_csv(STAGE9 / "EXPERIMENT_FEATURES.csv")
    boot = pd.read_csv(STAGE9 / "MODEL_SE_BOOTSTRAP_DRAFT.csv")
    return stage5, audit, feats, boot


def fix_standard_errors(paired: pd.DataFrame, boot: pd.DataFrame) -> pd.DataFrame:
    # Stage 5 left the uncertainty column empty (missing-value sentinel) for the
    # original experiments; expansion experiments carry real values, except three
    # cells where every response in an arm was identical (true zero variation).
    paired = paired.copy()
    paired["se_y_std_used"] = paired["se_y_std"]
    paired["se_source"] = "stage5"
    paired.loc[paired["study_group"] == "original", "se_source"] = "stage5_missing"

    boot2 = boot.rename(columns={"experiment": "experiment_id"})[
        ["contrast_id", "model", "blinding", "se_model_effect", "reliable_flag"]
    ].copy()
    boot2["blinding"] = boot2["blinding"].map({"blinded": 0, "unblinded": 1}).astype(int)
    is_orig = paired["study_group"] == "original"
    merged = paired.loc[is_orig].drop(columns=["se_y_std_used", "se_source"]).merge(
        boot2, on=["contrast_id", "model", "blinding"], how="left", validate="many_to_one"
    )
    merged["se_y_std_used"] = merged["se_model_effect"]
    merged["se_source"] = np.where(
        merged["se_model_effect"].notna(), "bootstrap", "bootstrap_unavailable"
    )
    merged["se_bootstrap_reliable"] = merged["reliable_flag"]
    paired = pd.concat([paired.loc[~is_orig], merged], ignore_index=True)
    return paired


def main() -> None:
    stage5, audit, feats, boot = load_inputs()
    assert_stage5_shape(stage5)

    paired = stage5[stage5["paired_cell"] == 1].copy()
    assert len(paired) == 1106 and len(paired) // 2 == 553, "expected 553 pairs / 1106 rows"

    paired = fix_standard_errors(paired, boot)
    n_fixed = (paired["se_source"] == "bootstrap").sum()
    n_unrel = (paired["se_source"] == "bootstrap") & (~paired["se_bootstrap_reliable"].astype(bool))
    print(f"SE replacements from bootstrap: {n_fixed} rows ({n_unrel.sum()} unreliable lineage)")

    # Human side of each contrast + blind-coded features.
    human_cols = [
        "contrast_id", "human_direction_confident", "human_direction",
        "human_abs_d_std", "human_se_std", "collective_disagreement_class",
    ]
    df = paired.merge(audit[human_cols], on="contrast_id", how="left", validate="many_to_one")
    df = df.merge(
        feats.drop(columns=["experiment_id", "study_group", "response_format"]),
        on="contrast_id", how="left", validate="many_to_one",
    )
    assert len(df) == 1106, "joins must not change the row count"
    assert df["human_abs_d_std"].notna().all(), "every paired row needs a human benchmark"
    assert df.drop(columns=["collective_disagreement_class"]).isna().all().sum() == 0, \
        "unexpected missing values after joins"

    # Outcomes: absolute distance from the human effect, and same-sign agreement.
    df["absolute_error"] = (df["y_std"] - df["d_human_std"]).abs()
    df["correct_direction"] = (np.sign(df["y_std"]) == df["human_direction"]).astype(int)
    df["disclosure"] = df["blinding"].astype(int)  # 0 = blinded, 1 = disclosed
    df["model_contrast_pair"] = df["contrast_id"] + "|" + df["model"]

    n_zero = int((df["absolute_error"] == 0).sum())
    print(f"exact zero absolute errors: {n_zero} (Gamma model needs a documented shift if > 0)")
    confident = df[df["human_direction_confident"] == True]  # noqa: E712
    print(f"direction subset: {confident['contrast_id'].nunique()} contrasts, {len(confident)} rows")

    out = STAGE9 / "ANALYSIS_TABLE.csv"
    df.to_csv(out, index=False)
    print(f"wrote {out} ({df.shape[0]} rows, {df.shape[1]} cols)")


if __name__ == "__main__":
    main()
