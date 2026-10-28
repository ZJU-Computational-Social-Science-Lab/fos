# canonical_tables.py — assembles and validates the Stage 10 canonical
# output tables from the rebuilt effects frame: the arm-outcomes table, the
# model-effects table, the uncertainty table, and the Stage 5-equivalent
# paired analysis table, plus the expected-coverage report.
#
# What each function does:
#   build_tables               — four canonical data frames from one
#                                effects frame (native + std, both legs).
#   validate_tables            — fail-fast checks before promotion.
#   coverage_report            — expected-vs-actual coverage with reasons.
#   human_effect_se_by_contrast — frozen human benchmark SE per contrast.


from __future__ import annotations

import json

import numpy as np

import pandas as pd

from stage10_common import COVERAGE, EXPANSION17, UNBL, VERSION, load_register

RESPONSE_FORMAT = {
    "disease": ("share", 6), "less_is_more": ("rating_mean", 5),
    "fire_extinguisher": ("rating_mean", 5), "seatbelt": ("rating_mean", 6),
    "sunk_cost": ("numeric_open", None), "wta_wtp": ("bracket_mean", 10),
    "allais": ("binary_choice", 2), "linda": ("rating_mean", 6),
    "anchoring_redwood": ("numeric_estimate", None),
    "anchoring_african": ("numeric_estimate", None),
    "outcome_bias": ("rating_mean", 7), "myside": ("rating_mean", 6),
    "prob_matching": ("share", 2), "abs_relative": ("binary_choice", 2),
    "T2KX-ml1_gamblers_fallacy": ("share", None),
    "T2KX-ml1_category_scales": ("share", None),
    "T2KX-ml1_reciprocity": ("share", 2),
    "T2KX-ml1_allowed_forbidden": ("share", 2),
    "T2KX-ml1_quote_attribution": ("rating_mean", None),
    "T2KX-ml1_imagined_contact": ("rating_mean", 9),
    "T2KX-ml2_hauser_s1": ("binary_choice", 2),
    "T2KX-ml2_risen_tempt_fate": ("rating_mean", 10),
    "T2KX-ml2_schwarz_order": ("rating_mean", 11),
    "T2KX-ml2_shafir_choose_reject": ("binary_choice", 2),
    "T2KX-ml2_miyamoto_correspondence": ("rating_mean", 15),
    "T2KX-ml2_rottenstreich_affect": ("binary_choice", 2),
    "T2KX-ml2_bauer_materialism": ("rating_mean", 7),
    "T2KX-howard823": ("numeric_estimate", None),
    "T2KX-budescu779": ("bracket_mean", 10),
    "T2KX-keusch433": ("rating_mean", 5),
    "T2KX-reedBR32": ("rating_mean", 7),
}
FAMILY = {"disease": "disease", "less_is_more": "valuation_reference",
          "fire_extinguisher": "proportion_dominance",
          "seatbelt": "proportion_dominance",
          "wta_wtp": "valuation_reference", "sunk_cost": "valuation_reference",
          "abs_relative": "valuation_reference", "allais": "probability_risk",
          "prob_matching": "probability_risk", "linda": "judgment_inference",
          "outcome_bias": "judgment_inference", "myside": "judgment_inference",
          "anchoring_redwood": "anchoring", "anchoring_african": "anchoring"}


def human_effect_se_by_contrast() -> pd.DataFrame:
    """Frozen human benchmark SE per contrast (std scale).

    Originals: the stage 5 Phase-1 respondent bootstrap. Expansion: the
    fingerprint register 95% CI half-width over the frozen pooled SD.
    """
    s5 = pd.read_csv(UNBL / "_project_governance/stage5_exploratory/data/"
                     "human_se_bootstrap.csv")
    reg = json.load(open(UNBL / "expansion/work/T2KX-20261022T222604/"
                         "fingerprint.json"))["payload"]["register"]
    exp17 = pd.read_csv(EXPANSION17)
    sd_by_contrast = exp17.groupby("contrast_id").sd_human_pooled.first()
    out = dict(zip(s5.contrast_id, s5.boot_se_std))
    for exp_id, items in reg.items():
        sub = exp17[exp17.experiment_id == exp_id]
        for it in items:
            hit = sub[np.isclose(sub.delta_human, it[2])]
            cid = hit.contrast_id.iloc[0]
            out[cid] = ((it[4] - it[3]) / (2 * 1.96)) / sd_by_contrast[cid]
    return pd.DataFrame({"contrast_id": list(out),
                         "human_effect_se": list(out.values())})


def build_tables(effects: pd.DataFrame) -> tuple[pd.DataFrame, ...]:
    """Assemble the canonical output tables from the effects frame."""
    register = {r["contrast_id"]: r for r in load_register()}
    arm = effects.rename(columns={
        "model_effect_native": "model_effect_pp",
        "model_effect_se": "model_effect_se_pp",
        "n_t": "n_treatment", "n_c": "n_control"}).copy()
    arm["treatment_condition"] = arm.contrast_id.map(
        lambda c: register[c]["treatment_condition"])
    arm["control_condition"] = arm.contrast_id.map(
        lambda c: register[c]["control_condition"])
    arm["response_format"] = arm.experiment_id.map(
        lambda e: RESPONSE_FORMAT[e][0])
    arm["n_options"] = arm.experiment_id.map(lambda e: RESPONSE_FORMAT[e][1])
    arm["source_version"] = VERSION
    keep = ["contrast_id", "experiment_id", "study_group", "model",
            "blinding", "treatment_condition", "control_condition",
            "model_effect_pp", "model_effect_std", "human_effect_std",
            "sd_human_pooled_pp", "model_effect_se_pp", "model_effect_se_std",
            "human_effect_std", "delta_human_pp", "n_treatment", "n_control",
            "boot_seed", "boot_draws", "degenerate_share", "zero_prob_note",
            "response_format", "n_options", "source_version"]
    arm_out = arm[keep]

    unc = arm_out[["contrast_id", "model", "blinding", "model_effect_pp",
                   "model_effect_se_pp", "model_effect_std",
                   "model_effect_se_std", "boot_seed", "boot_draws",
                   "degenerate_share", "zero_prob_note"]].rename(columns={
                       "model_effect_se_pp": "se_native",
                       "model_effect_se_std": "se_std"})
    model_fx = arm_out[["contrast_id", "experiment_id", "study_group", "model",
                        "blinding", "treatment_condition", "control_condition",
                        "model_effect_pp", "model_effect_std",
                        "human_effect_std", "sd_human_pooled_pp",
                        "model_effect_se_pp", "model_effect_se_std",
                        "response_format", "n_options", "source_version"]]

    piv = arm_out.pivot_table(
        index=["contrast_id", "model"],
        columns="blinding",
        values=["model_effect_std", "model_effect_se_std"],
        aggfunc="first").reset_index()
    piv.columns = [f"{c}_{b}" if isinstance(b, int) else c
                   for c, b in piv.columns]
    piv = piv.rename(columns={"model_effect_std_0": "y_std_blinded",
                              "model_effect_std_1": "y_std_disclosed",
                              "model_effect_se_std_0": "se_y_std_blinded",
                              "model_effect_se_std_1": "se_y_std_disclosed"})
    paired = piv.dropna(subset=["y_std_blinded", "y_std_disclosed"]).copy()
    paired["paired_cell"] = 1
    meta_cols = ["contrast_id", "experiment_id", "study_group",
                 "human_effect_std", "sd_human_pooled_pp"]
    meta = arm_out[meta_cols].drop_duplicates("contrast_id")
    paired = paired.merge(meta, on="contrast_id", validate="many_to_one")
    paired = paired.merge(human_effect_se_by_contrast(), on="contrast_id",
                          validate="many_to_one")
    paired["response_format"] = paired.experiment_id.map(
        lambda e: RESPONSE_FORMAT[e][0])
    paired["source_version"] = VERSION
    return arm_out, model_fx, unc, paired


def validate_tables(tables: tuple[pd.DataFrame, ...]) -> None:
    """Fail-fast checks; a failed run must never promote partial tables."""
    arm, model_fx, unc, paired = tables
    keys = ["contrast_id", "model", "blinding"]
    if arm.duplicated(keys).any():
        raise ValueError("duplicate canonical keys")
    if model_fx[keys].duplicated().any() or unc[keys].duplicated().any():
        raise ValueError("duplicate keys in effects/uncertainty")
    if arm.contrast_id.nunique() < 38:
        raise ValueError(f"coverage: only {arm.contrast_id.nunique()} of 38 "
                         "contrasts present")
    zero_se = arm[arm.model_effect_se_std < 0]
    if len(zero_se):
        raise ValueError("negative SE present")
    # SE exactly 0 is honest ONLY when the bootstrap resampled fine and
    # every retained response was identical (constant-response cells).
    constant = arm[(arm.model_effect_se_pp == 0)
                   & (arm.degenerate_share == 0)]
    if len(arm[(arm.model_effect_se_pp == 0)
               & (arm.degenerate_share > 0)]):
        raise ValueError("SE == 0 from failed bootstrap draws")
    if paired.y_std_blinded.isna().any() or paired.y_std_disclosed.isna().any():
        raise ValueError("incomplete paired cells")
    if arm.contrast_id.nunique() != model_fx.contrast_id.nunique():
        raise ValueError("arm/effect coverage disagree")
    if len(constant):
        print(f"note: {len(constant)} constant-response cells with honest "
              "bootstrap SE = 0 "
              f"({sorted(set(constant.contrast_id))})")


def coverage_report(arm: pd.DataFrame) -> dict:
    """Expected-vs-actual coverage with explicit reasons."""
    expected = {"original_cells": 524, "expansion_kept": None}
    cov = pd.read_csv(COVERAGE)
    by_group = arm.groupby("study_group").size().to_dict()
    return {"rows_total": int(len(arm)),
            "rows_by_group": {k: int(v) for k, v in by_group.items()},
            "expected_original_rows": expected["original_cells"],
            "frozen_coverage_rows": int(len(cov)),
            "note": ("originals: frozen 262-row grid x 2 legs; anchoring "
                     "C-13/C-14 have an 11-model structure; expansion: "
                     "unestimable cells (howard823 C-32/C-33) are absent, "
                     "never imputed")}


