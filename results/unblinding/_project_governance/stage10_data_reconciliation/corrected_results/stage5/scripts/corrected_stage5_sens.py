# corrected_stage5_sens.py — rerun the Stage 5 registered sensitivity
# checks (priors, leave-one-experiment-out, pp tier, original/expansion
# split) on the corrected canonical data, reusing the frozen
# 03_sensitivity.py unchanged.
#
# What it does:
#   build_pp_table — the frozen pp-tier loader with one swap: the original
#                    18 contrasts come from the corrected signed table
#                    (corrected_results/stage3/corrected_signed_contrasts.csv)
#                    instead of the stale frozen one; the expansion share
#                    contrasts are unchanged and are loaded exactly as the
#                    frozen code loads them.
#   main           — patches the shared module (loader, BASE) and runs the
#                    frozen sensitivity script's main(); appends results to
#                    corrected_results/stage5/MODEL_VALIDATION.md.

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

UNBL = Path("/home/justin/Documents/ZJU work/fos/results/unblinding")
STAGE10 = UNBL / "_project_governance" / "stage10_data_reconciliation"
FROZEN5 = UNBL / "_project_governance" / "stage5_exploratory"
OUT = Path("/home/justin/work/worktrees/implement-3014/_project_governance/"
           "stage10_data_reconciliation/corrected_results/stage5")

sys.path.insert(0, str(FROZEN5 / "scripts"))
import stage5_common as sc  # noqa: E402

from corrected_stage5 import build_pair_table  # noqa: E402


def build_pp_table() -> pd.DataFrame:
    """Frozen pp tier with corrected original-contrast effects."""
    orig = pd.read_csv(OUT.parent / "stage3"
                       / "corrected_signed_contrasts.csv")
    orig = orig.rename(columns={"contrast": "contrast_id",
                                "experiment": "experiment_id"})
    # the corrected table stores oriented effects M = sign(d_h) * d_m;
    # the pp tier needs the raw signed contrasts back
    for leg in ("B", "U"):
        orig[f"d_m_{leg}"] = orig[f"M_{leg}"] / np.sign(orig["d_h"])
    orig["y0"], orig["y1"] = orig.d_m_B, orig.d_m_U
    hum = pd.read_csv(FROZEN5 / "data" / "human_se_bootstrap.csv")

    def boot_se(d_h):
        hit = hum[np.isclose(hum.frozen_d_h_pp, d_h, rtol=1e-9, atol=1e-9)]
        assert len(hit) == 1, f"d_h {d_h} matches {len(hit)} bootstrap rows"
        return hit.boot_se_pp.iloc[0]

    orig["se_human"] = orig.d_h.map(boot_se)
    orig["se0"] = orig["se1"] = 0.0
    orig = orig[["contrast_id", "experiment_id", "model", "y0", "y1",
                 "se0", "se1", "se_human"]]

    exp17 = pd.read_csv(
        UNBL / "_project_governance" / "stage3_results" /
        "expansion17" / "contrast_level_results.csv")
    reg = json.load(open(
        UNBL / "expansion" / "work" / "T2KX-20261022T222604" /
        "fingerprint.json"))["payload"]["register"]
    pp_ids = {"C-20", "C-21", "C-22"}
    sub = exp17[exp17.contrast_id.isin(pp_ids)].copy()
    piv = sub.pivot_table(index=["contrast_id", "experiment_id", "model",
                                 "delta_human", "sd_human_pooled"],
                          columns="blinding",
                          values=["delta_model", "ci95_low", "ci95_high"],
                          aggfunc="first").reset_index()
    piv.columns = ["_".join(str(x) for x in c if str(x) != "")
                   if isinstance(c, tuple) else c for c in piv.columns]
    piv["y0"] = piv["delta_model_blinded"] * 100.0
    piv["y1"] = piv["delta_model_disclosed"] * 100.0
    piv["se0"] = ((piv.ci95_high_blinded - piv.ci95_low_blinded) / 3.92) * 100.0
    piv["se1"] = ((piv.ci95_high_disclosed - piv.ci95_low_disclosed) / 3.92) * 100.0
    piv["se_human"] = np.nan
    for _, row in piv.iterrows():
        items = reg[row.experiment_id]
        for it in items:
            if np.isclose(it[2], row.delta_human):
                piv.loc[piv.contrast_id == row.contrast_id, "se_human"] = \
                    ((it[4] - it[3]) / 3.92) * 100.0
    piv = piv[["contrast_id", "experiment_id", "model", "y0", "y1",
               "se0", "se1", "se_human"]]
    out = pd.concat([orig, piv], ignore_index=True)
    bad = out.isna().sum()
    assert not bad.any(), f"pp tier has missing values: {bad[bad > 0].to_dict()}"
    return out


def main() -> None:
    _spec = importlib.util.spec_from_file_location(
        "sens", FROZEN5 / "scripts" / "03_sensitivity.py")
    sens = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(sens)
    sc.load_pair_table = build_pair_table
    sc.load_pp_table = build_pp_table
    sc.BASE = OUT
    sens.sc = sc
    sens.main()


if __name__ == "__main__":
    main()
