# corrected_pairs.py — canonical corrected paired dataset for the Stage 7/8
# reruns (reconciled_v1).
#
# What it does:
#   load_pairs — builds the same 553-pair contrast x model table (both
#     blinding legs, frozen human benchmark and human SE) that the frozen
#     stage7_common loader built from the stale Stage 5 dataset, but reads
#     CANONICAL_PAIRED_ANALYSIS.csv so the corrected model effects and
#     corrected bootstrap SEs flow through. Human-side columns are
#     unchanged by the reconciliation, and per-contrast pair coverage is
#     identical (C-13/C-14: 11, C-32: 10, C-33: 11), so the C-32 coverage
#     convention is preserved. The 6 `new_only` cells are single-leg and
#     never enter the paired table.
#   load_blinded_effects — one row per contrast x model, blinded leg only,
#     from CANONICAL_MODEL_EFFECTS.csv (for the Stage 8 regression).

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

UNBL = Path("/home/justin/Documents/ZJU work/fos/results/unblinding")
STAGE10 = UNBL / "_project_governance" / "stage10_data_reconciliation"
FROZEN7 = UNBL / "_project_governance" / "stage7_replication_evidence"

sys.path.insert(0, str(FROZEN7 / "scripts"))
sys.dont_write_bytecode = True
import stage7_common as sc  # noqa: E402  (conventions + native delta helper)


def load_pairs() -> pd.DataFrame:
    """553 corrected pairs with the frozen loader's derived columns."""
    df = pd.read_csv(STAGE10 / "data" / "CANONICAL_PAIRED_ANALYSIS.csv")
    assert len(df) == 553, f"expected 553 canonical pairs, got {len(df)}"
    assert df.contrast_id.nunique() == 38
    assert df.experiment_id.nunique() == 31
    wide = df.rename(columns={
        "y_std_blinded": "y_blinded",
        "y_std_disclosed": "y_disclosed",
        "human_effect_std": "d_human_std",
        "human_effect_se": "se_human",
    })
    arms = pd.read_csv(STAGE10 / "data" / "CANONICAL_ARM_OUTCOMES.csv")
    delta = arms.drop_duplicates("contrast_id").set_index(
        "contrast_id").delta_human_pp
    wide["delta_human_pp"] = wide.contrast_id.map(delta)
    assert wide.delta_human_pp.notna().all()
    assert wide.se_human.gt(0).all(), "human SE must be positive"
    wide["human_pr_pos"] = [float(norm.cdf(d / s)) for d, s in
                            zip(wide.d_human_std, wide.se_human)]
    wide["human_dir_confident"] = wide.human_pr_pos.map(
        sc.direction_confident)
    wide["human_sign"] = np.sign(wide.d_human_std).astype(int)
    wide["model_sign_blinded"] = np.sign(wide.y_blinded).astype(int)
    wide["model_sign_disclosed"] = np.sign(wide.y_disclosed).astype(int)
    wide["agree_blinded"] = wide.model_sign_blinded == wide.human_sign
    wide["agree_disclosed"] = wide.model_sign_disclosed == wide.human_sign
    counts = wide.groupby("contrast_id").size()
    for cid, n in [("C-13", 11), ("C-14", 11), ("C-32", 10), ("C-33", 11)]:
        assert counts[cid] == n, f"{cid} coverage changed: {counts[cid]} != {n}"
    return wide.reset_index(drop=True)


def load_blinded_effects() -> pd.DataFrame:
    """Blinded-leg corrected model effects (contrast, experiment, model,
    y_std), mirroring the frozen `stage5_dataset[blinding == 0]` input."""
    eff = pd.read_csv(STAGE10 / "data" / "CANONICAL_MODEL_EFFECTS.csv")
    df = eff[eff.blinding == 0][
        ["contrast_id", "experiment_id", "model", "model_effect_std"]
    ].rename(columns={"model_effect_std": "y_std"}).reset_index(drop=True)
    assert len(df) == 553 + 7, "blinded rows = 553 pairs + 7 unpaired legs"
    return df


def load_all_legs() -> pd.DataFrame:
    """Both legs in the frozen stage5_dataset layout (contrast, experiment,
    model, blinding, y_std), for the Stage 8 Part-5/6 analyses."""
    eff = pd.read_csv(STAGE10 / "data" / "CANONICAL_MODEL_EFFECTS.csv")
    df = eff[["contrast_id", "experiment_id", "model", "blinding",
              "model_effect_std"]].rename(
        columns={"model_effect_std": "y_std"}).reset_index(drop=True)
    assert len(df) == 1119
    return df
