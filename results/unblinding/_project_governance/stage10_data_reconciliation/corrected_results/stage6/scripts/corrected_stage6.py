# corrected_stage6.py — rerun the Stage 6 direction & disclosure analyses
# on the corrected canonical paired data, reusing the frozen scripts
# unchanged except for the data loader and output directory.
#
# What it does:
#   build_pairs — the same 553-pair table the frozen loader produces
#                 (y0/y1 blinded+disclosed standardized effects, frozen
#                 human benchmark and its SE), built from
#                 CANONICAL_PAIRED_ANALYSIS.csv so corrected model effects
#                 and corrected model SEs flow in. Human-side columns are
#                 unchanged by the correction. The 7 historical unpaired
#                 rows never entered the direction analysis (pairs only),
#                 so the corrected scope matches the frozen one.
#   main        — patches stage6_common's loader and STAGE6 output dir,
#                 then runs the frozen 10_direction_analysis.py and
#                 20_accuracy_refit.py mains; writes into
#                 corrected_results/stage6/.

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd

UNBL = Path("/home/justin/Documents/ZJU work/fos/results/unblinding")
STAGE10 = UNBL / "_project_governance" / "stage10_data_reconciliation"
FROZEN6 = UNBL / "_project_governance" / "stage6_direction_and_disclosure"
FROZEN5 = UNBL / "_project_governance" / "stage5_exploratory"
OUT = Path("/home/justin/work/worktrees/implement-3014/_project_governance/"
           "stage10_data_reconciliation/corrected_results/stage6")

sys.path.insert(0, str(FROZEN6 / "scripts"))
sys.path.insert(0, str(FROZEN5 / "scripts"))
sys.dont_write_bytecode = True
import stage6_common as s6  # noqa: E402
import stage5_common as s5  # noqa: E402  (used by 20_accuracy_refit)


def build_pairs() -> pd.DataFrame:
    """553-pair table from canonical paired data (frozen layout)."""
    cp = pd.read_csv(STAGE10 / "data" / "CANONICAL_PAIRED_ANALYSIS.csv")
    wide = pd.DataFrame({
        "contrast_id": cp.contrast_id, "experiment_id": cp.experiment_id,
        "study_group": cp.study_group, "model": cp.model,
        "y0": cp.y_std_blinded, "y1": cp.y_std_disclosed,
        "d_human_std": cp["human_effect_std"], "se_human": cp.human_effect_se,
    })
    assert len(wide) == 553 and wide.contrast_id.nunique() == 38
    assert wide.experiment_id.nunique() == 31
    assert wide[["y0", "y1", "se_human"]].notna().all().all()
    return wide.reset_index(drop=True)


def _run(script_name: str) -> None:
    spec = importlib.util.spec_from_file_location(
        script_name.replace(".py", ""), FROZEN6 / "scripts" / script_name)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.main()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    s6.load_pairs = build_pairs
    s6.STAGE6 = OUT
    s5.load_pair_table = build_pairs   # accuracy refit loads via stage5_common
    _run("10_direction_analysis.py")
    _run("20_accuracy_refit.py")


if __name__ == "__main__":
    main()
