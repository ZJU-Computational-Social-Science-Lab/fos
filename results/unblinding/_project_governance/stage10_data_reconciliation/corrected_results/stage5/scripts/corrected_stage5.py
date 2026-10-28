# corrected_stage5.py — rerun the Stage 5 Bayesian analyses (A1, A2, A3)
# on the corrected canonical paired data, with IDENTICAL priors, model
# specs, seeds, and outputs as the frozen run.
#
# What it does:
#   build_pair_table   — same layout as the frozen load_pair_table() output
#                        (553 complete pairs, both legs, human SE attached),
#                        built from CANONICAL_PAIRED_ANALYSIS.csv so the
#                        corrected model effects AND corrected per-model
#                        bootstrap SEs enter the likelihood. Design metadata
#                        (n_options) comes from the frozen dataset because
#                        it is experiment design, not an effect estimate.
#   main               — reuses the frozen 02_fit_models.py unchanged (it is
#                        imported and only its output base and data loader
#                        are swapped), so every estimator, prior, seed and
#                        table is identical; writes into
#                        corrected_results/stage5/.

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd

UNBL = Path("/home/justin/Documents/ZJU work/fos/results/unblinding")
STAGE10 = UNBL / "_project_governance" / "stage10_data_reconciliation"
FROZEN5 = UNBL / "_project_governance" / "stage5_exploratory"
OUT = Path("/home/justin/work/worktrees/implement-3014/_project_governance/"
           "stage10_data_reconciliation/corrected_results/stage5")

sys.path.insert(0, str(FROZEN5 / "scripts"))
import stage5_common as sc  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "fit_models", FROZEN5 / "scripts" / "02_fit_models.py")
fm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fm)


def build_pair_table() -> pd.DataFrame:
    """Frozen-shape pair table from canonical paired data."""
    cp = pd.read_csv(STAGE10 / "data" / "CANONICAL_PAIRED_ANALYSIS.csv")
    wide = pd.DataFrame({
        "contrast_id": cp.contrast_id, "experiment_id": cp.experiment_id,
        "study_group": cp.study_group, "model": cp.model,
        "y0": cp.y_std_blinded, "y1": cp.y_std_disclosed,
        "se0": cp.se_y_std_blinded, "se1": cp.se_y_std_disclosed,
        "d_human_std": cp["human_effect_std"], "se_human": cp.human_effect_se,
        "response_format": cp.response_format,
    })
    meta = (pd.read_csv(FROZEN5 / "data" / "stage5_dataset.csv")
            [["contrast_id", "n_options"]].drop_duplicates())
    wide = wide.merge(meta, on="contrast_id", how="left", validate="many_to_one")
    assert len(wide) == 553 and wide.contrast_id.nunique() == 38
    assert wide.experiment_id.nunique() == 31
    # n_options is NaN for 8 contrasts in the frozen data too; the A3
    # design handles that with an explicit missing-indicator column.
    assert wide[["y0", "y1", "se_human"]].notna().all().all()
    return wide.reset_index(drop=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sc.load_pair_table = build_pair_table      # corrected data, same shape
    fm.sc = sc
    fm.BASE = OUT                              # outputs to corrected_results
    fm.main()


if __name__ == "__main__":
    main()
