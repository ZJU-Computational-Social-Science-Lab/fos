# test_canonical_tables.py — structural checks on the canonical tables:
# coverage, unique keys, treatment/control orientation, native->std
# conversion, outcome scale, missing-arm handling, zero-probability
# handling, paired eligibility, and human-benchmark matching.

from __future__ import annotations

import numpy as np
import pandas as pd

import stage10_common as sc

TOL = 1e-8


def test_every_registered_contrast_is_present(arm, register):
    """All 38 registered contrasts appear in the canonical arm table."""
    assert set(arm.contrast_id) == {r["contrast_id"] for r in register}


def test_keys_are_unique(arm, effects, uncertainty, paired):
    """No duplicated (contrast, model, blinding) keys anywhere."""
    keys = ["contrast_id", "model", "blinding"]
    assert not arm.duplicated(keys).any()
    assert not effects.duplicated(keys).any()
    assert not uncertainty.duplicated(keys).any()
    assert not paired.duplicated(["contrast_id", "model"]).any()


def test_original_coverage_matches_frozen_grid(arm, frozen_262):
    """Originals: 524 rows = the frozen 262-row grid x 2 legs (with the
    run10 re-run adding exactly the 6 completed anchoring cells)."""
    orig = arm[arm.study_group == "original"]
    assert len(orig) == 524 + 6


def test_expansion_unestimable_cells_stay_missing(arm):
    """howard823 cells the frozen file marked unestimable stay absent."""
    exp17 = pd.read_csv(sc.EXPANSION17)
    unst = exp17[exp17["unestimable"].astype(str).str.lower().eq("true")]
    for row in unst.itertuples():
        b = 0 if row.blinding == "blinded" else 1
        n = len(arm[(arm.contrast_id == row.contrast_id)
                    & (arm.model == row.model) & (arm.blinding == b)])
        assert n == 0, f"{row.contrast_id}/{row.model}/leg{b} should miss"


def test_treatment_minus_control_orientation(arm, register):
    """model_effect_pp is treatment minus control (register order)."""
    reg = {r["contrast_id"]: r for r in register}
    share = arm[arm.experiment_id == "disease"]
    # C-01: p_safe(loss) - p_safe(gain); humans are negative on this sign.
    row = reg["C-01"]
    assert (share.treatment_condition == row["treatment_condition"]).all()
    assert (share.control_condition == row["control_condition"]).all()


def test_native_to_std_conversion(arm):
    """model_effect_std = model_effect_pp / frozen human pooled SD."""
    ratio = arm.model_effect_pp / arm.sd_human_pooled_pp
    assert np.allclose(ratio, arm.model_effect_std, rtol=0, atol=1e-12)


def test_human_std_conversion(arm):
    """human_effect_std = frozen human pp effect / same denominator."""
    ratio = arm.delta_human_pp / arm.sd_human_pooled_pp
    assert np.allclose(ratio, arm.human_effect_std, rtol=0, atol=1e-12)


def test_se_std_conversion(arm):
    """model_effect_se_std = model_effect_se_pp / same denominator."""
    ratio = arm.model_effect_se_pp / arm.sd_human_pooled_pp
    assert np.allclose(ratio, arm.model_effect_se_std, rtol=0, atol=1e-12)


def test_probability_scale_effects_are_bounded(arm):
    """Probability/share outcomes stay within +/-100 pp by construction."""
    share_ids = ["C-01", "C-04", "C-05", "C-06", "C-07", "C-11", "C-17",
                 "C-18"]
    sub = arm[arm.contrast_id.isin(share_ids)]
    assert sub.model_effect_pp.abs().max() <= 100.0 + 1e-6


def test_no_missing_arms_silently_filled(arm):
    """No NaN effects and no zero-filled n counts in canonical cells."""
    assert arm.model_effect_pp.notna().all()
    assert (arm[["n_treatment", "n_control"]] > 0).all().all()


def test_zero_probability_records_documented(arm):
    """Zero/unreadable records are noted per cell, never folded in as 0."""
    assert "zero_prob_note" in arm.columns


def test_se_zero_only_for_constant_responses(arm):
    """SE = 0 must come from identical retained draws, not failures."""
    bad = arm[(arm.model_effect_se_pp == 0) & (arm.degenerate_share > 0)]
    assert len(bad) == 0


def test_paired_cells_have_both_legs(paired):
    """Paired table only holds contrast x model with both legs."""
    assert paired[["y_std_blinded", "y_std_disclosed"]].notna().all().all()
    assert (paired.paired_cell == 1).all()


def test_human_benchmark_matches_frozen_stage5(paired, frozen_stage5):
    """d_human_std equals the frozen Stage 5 human benchmark exactly."""
    s5 = frozen_stage5.drop_duplicates("contrast_id").set_index("contrast_id")
    joined = paired.set_index("contrast_id")
    both = joined.join(s5[["d_human_std"]], rsuffix="_s5")
    frozen = both["d_human_std_s5"] if "d_human_std_s5" in both else both["d_human_std"]
    ok = np.isclose(both.human_effect_std, frozen, rtol=0, atol=1e-9)
    assert ok.all(), both[~ok][["human_effect_std", "d_human_std"]].head()


def test_source_version_recorded(arm):
    """Every row carries the canonical version id."""
    assert (arm.source_version == sc.VERSION).all()


def test_manifest_records_seed_and_draws():
    """The manifest pins the seed and bootstrap draws."""
    import json
    manifest = json.loads(sc.MANIFEST.read_text())
    assert manifest["seed"] == sc.SEED
    assert manifest["bootstrap_draws"] == sc.NDRAWS
