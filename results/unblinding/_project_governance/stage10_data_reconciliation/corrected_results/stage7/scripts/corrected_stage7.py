# corrected_stage7.py — rerun the Stage 7 replication-evidence audit on the
# corrected canonical paired data, reusing the frozen Stage 7 scripts
# unchanged except for the data loader and output directory.
#
# What it does:
#   load_pairs_canonical — the same 553-pair, 38-contrast table the frozen
#                 loader builds (both blinding legs, frozen human benchmark
#                 and human SE), but with model effects and human SE taken
#                 from CANONICAL_PAIRED_ANALYSIS.csv so the corrected model
#                 effects flow in. Human-side columns are unchanged by the
#                 reconciliation; per-contrast pair counts (C-13/C-14: 11,
#                 C-32: 10, C-33: 11) are identical to the frozen run, so
#                 the C-32 coverage convention is preserved exactly. The 6
#                 `new_only` cells are single-leg (no pair) and therefore
#                 never enter the paired table.
#   main        — patches stage7_common's loader and STAGE7 output dir,
#                 then runs the frozen 30_contrast_audit and 40_screening
#                 mains and copies the frozen 50_qa_counts checks over the
#                 corrected CSVs; writes into corrected_results/stage7/.

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

UNBL = Path("/home/justin/Documents/ZJU work/fos/results/unblinding")
STAGE10 = UNBL / "_project_governance" / "stage10_data_reconciliation"
FROZEN7 = UNBL / "_project_governance" / "stage7_replication_evidence"
OUT = Path("/home/justin/work/worktrees/implement-3019/results/unblinding/"
           "_project_governance/stage10_data_reconciliation/"
           "corrected_results/stage7")

sys.path.insert(0, str(FROZEN7 / "scripts"))
sys.dont_write_bytecode = True
import stage7_common as sc  # noqa: E402


def load_pairs_canonical() -> pd.DataFrame:
    """One row per contrast x model with both blinding legs (553 pairs),
    built from the corrected canonical paired table. Column semantics and
    derived columns match the frozen loader exactly."""
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
    # native-scale human effect per contrast (sign/orientation checks)
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
    # frozen coverage convention preserved: same per-contrast pair counts
    counts = wide.groupby("contrast_id").size()
    for cid, n in [("C-13", 11), ("C-14", 11), ("C-32", 10), ("C-33", 11)]:
        assert counts[cid] == n, f"{cid} coverage changed: {counts[cid]} != {n}"
    return wide.reset_index(drop=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sc.STAGE7 = OUT
    sc.load_pairs = load_pairs_canonical

    spec = importlib.util.spec_from_file_location(
        "audit30", FROZEN7 / "scripts" / "30_contrast_audit.py")
    audit30 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit30)
    audit30.main()

    spec = importlib.util.spec_from_file_location(
        "screen40", FROZEN7 / "scripts" / "40_screening.py")
    screen40 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(screen40)
    screen40.main()

    # 50_qa_counts re-derives headline counts from the CSVs in its own
    # parent dir (DIR = parents[1] of its file), so a byte-identical copy
    # in the corrected scripts dir reads the corrected CSVs.
    import shutil
    shutil.copyfile(FROZEN7 / "scripts" / "50_qa_counts.py",
                    OUT / "scripts" / "50_qa_counts.py")
    spec = importlib.util.spec_from_file_location(
        "qa50", OUT / "scripts" / "50_qa_counts.py")
    qa50 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(qa50)


if __name__ == "__main__":
    main()
