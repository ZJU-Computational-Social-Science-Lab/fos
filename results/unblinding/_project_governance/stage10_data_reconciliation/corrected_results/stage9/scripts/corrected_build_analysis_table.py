# corrected_build_analysis_table.py — rebuild the Stage 9 analysis table from
# the corrected canonical data (reconciled_v1), keeping every other frozen
# convention (same EXPERIMENT_FEATURES.csv, same corrected Stage 7 audit,
# same row scope of 553 pairs / 1106 cells).
#
# What it does:
#   load_canonical_paired — melts CANONICAL_PAIRED_ANALYSIS.csv into one row
#     per contrast x model x blinding leg (1106 rows) with the corrected
#     model effects and corrected bootstrap SEs, plus the per-contrast human
#     benchmark columns (unchanged by the reconciliation) and native/pp
#     metadata from CANONICAL_ARM_OUTCOMES.csv. The frozen pipeline's
#     bootstrap-SE substitution step for the original experiments is not
#     needed: the canonical table already carries corrected SEs for every
#     cell (se_source = canonical_reconciled_v1).
#   main — joins the corrected Stage 7 audit human columns and the frozen
#     blind-coded experiment features, computes the two outcomes (absolute
#     error, direction-correct), writes ANALYSIS_TABLE.csv.

from pathlib import Path

import numpy as np
import pandas as pd

STAGE9 = Path(__file__).resolve().parents[1]
STAGE10 = Path(
    "/home/justin/Documents/ZJU work/fos/results/unblinding/_project_governance"
) / "stage10_data_reconciliation"
CORR7 = Path("/home/justin/work/worktrees/implement-3019/results/unblinding/"
             "_project_governance/stage10_data_reconciliation/"
             "corrected_results/stage7")
SEED = 20261028  # kept for provenance parity with the frozen run


def load_canonical_paired() -> pd.DataFrame:
    """1106 corrected paired cells (553 pairs x 2 legs) in the frozen
    analysis-table layout."""
    paired = pd.read_csv(STAGE10 / "data" / "CANONICAL_PAIRED_ANALYSIS.csv")
    assert len(paired) == 553 and paired.contrast_id.nunique() == 38
    long = paired.rename(columns={
        "y_std_blinded": "y_blinded", "y_std_disclosed": "y_disclosed",
        "se_y_std_blinded": "se_blinded", "se_y_std_disclosed": "se_disclosed",
        "human_effect_std": "d_human_std",
    })
    melted = long.melt(
        id_vars=["contrast_id", "experiment_id", "study_group", "model",
                 "d_human_std", "sd_human_pooled_pp", "response_format"],
        value_vars=["y_blinded", "y_disclosed"],
        var_name="leg", value_name="y_std",
    ).sort_values(["contrast_id", "model"], kind="stable").reset_index(drop=True)
    melted["blinding"] = (melted["leg"] == "y_disclosed").astype(int)
    melted["se_y_std"] = np.where(melted.blinding == 0,
                                  long.se_blinded.repeat(2).values,
                                  long.se_disclosed.repeat(2).values)
    assert len(melted) == 1106

    arms = pd.read_csv(STAGE10 / "data" / "CANONICAL_ARM_OUTCOMES.csv")
    per_con = arms.drop_duplicates("contrast_id").set_index("contrast_id")
    melted["delta_human_pp"] = melted.contrast_id.map(per_con.delta_human_pp)
    melted["n_options"] = melted.contrast_id.map(per_con.n_options)
    assert melted.delta_human_pp.notna().all()

    melted["dataset"] = np.where(melted.study_group == "original",
                                 "original14", "expansion17")
    melted["paired_cell"] = 1
    melted["human_effect_avail"] = 1
    # corrected bootstrap SEs for every cell; no substitution needed
    melted["se_y_std_used"] = melted["se_y_std"]
    melted["se_source"] = "canonical_reconciled_v1"
    return melted


def main() -> None:
    paired = load_canonical_paired()

    human_cols = [
        "contrast_id", "human_direction_confident", "human_direction",
        "human_abs_d_std", "human_se_std", "collective_disagreement_class",
    ]
    audit = pd.read_csv(CORR7 / "DISAGREEMENT_AUDIT.csv")
    df = paired.merge(audit[human_cols], on="contrast_id",
                      how="left", validate="many_to_one")
    feats = pd.read_csv(STAGE9 / "EXPERIMENT_FEATURES.csv")
    df = df.merge(
        feats.drop(columns=["experiment_id", "study_group", "response_format"]),
        on="contrast_id", how="left", validate="many_to_one",
    )
    assert len(df) == 1106, "joins must not change the row count"
    assert df["human_abs_d_std"].notna().all(), "every paired row needs a human benchmark"
    assert df.drop(columns=["collective_disagreement_class"]).isna().all().sum() == 0, \
        "unexpected missing values after joins"

    df["absolute_error"] = (df["y_std"] - df["d_human_std"]).abs()
    df["correct_direction"] = (np.sign(df["y_std"]) == df["human_direction"]).astype(int)
    df["disclosure"] = df["blinding"].astype(int)
    df["model_contrast_pair"] = df["contrast_id"] + "|" + df["model"]

    n_zero = int((df["absolute_error"] == 0).sum())
    print(f"exact zero absolute errors: {n_zero} (Gamma model needs a documented shift if > 0)")
    confident = df[df["human_direction_confident"] == True]  # noqa: E712
    print(f"direction subset: {confident['contrast_id'].nunique()} contrasts, "
          f"{len(confident)} rows")

    out = STAGE9 / "ANALYSIS_TABLE.csv"
    df.to_csv(out, index=False)
    print(f"wrote {out} ({df.shape[0]} rows, {df.shape[1]} cols)")


if __name__ == "__main__":
    main()
