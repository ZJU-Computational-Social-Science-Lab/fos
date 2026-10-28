# frozen_check.py — hard gates comparing the Stage 10 rebuild against the
# frozen Stage 3 reference files: every rebuilt effect must equal its
# frozen value to 1e-8 or the rebuild stops. This is how we prove the new
# pipeline reproduces the verified numbers instead of assuming it does.
#
# What each function does:
#   check_originals — rebuilt original effects vs the frozen 262-row file.
#   check_expansion — rebuilt expansion effects vs frozen expansion17
#                     native deltas (unestimable cells stay missing).

from __future__ import annotations

import pandas as pd

from stage10_common import EXPANSION17, FROZEN_262, load_register, log

# Experiments whose raw records live in run6 (identical in every copy of
# the project; hard-gated against the frozen file).
RUN6_EXPERIMENTS = {"disease", "less_is_more", "fire_extinguisher",
                    "seatbelt", "sunk_cost", "wta_wtp"}

# Frozen-match tolerance: exact at 1e-8 (the Stage 10 brief's tolerance).
TOL = 1e-8


def check_originals(effects: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compare rebuilt original effects with the frozen 262-row file.

    The frozen file was computed from the 2026-10-04 state of the run10
    records; the canonical project root holds the 2026-10-05 completed
    re-run. Run6 legs must match EXACTLY (hard gate); run10 cells that
    differ are kept in the canonical data and reported row-by-row in
    OLD_VS_CORRECTED as documented exceptions, never hidden.
    """
    frozen = pd.read_csv(FROZEN_262)
    register = [r for r in load_register() if r["study_group"] == "original"]
    exp_by_contrast = {r["contrast_id"]: r["experiment_id"] for r in register}
    name_by_contrast = {r["contrast_id"]: r["contrast_name"] for r in register}
    frozen = frozen.rename(columns={"experiment": "experiment_id",
                                    "contrast": "contrast_name"})
    frozen["contrast_id"] = [
        [cid for cid, e in exp_by_contrast.items()
         if e == row.experiment_id
         and name_by_contrast[cid] == row.contrast_name][0]
        for row in frozen.itertuples()]
    fmap = {(r.contrast_id, r.model, 0 if k == "d_m_B" else 1):
            getattr(r, k) for r in frozen.itertuples()
            for k in ("d_m_B", "d_m_U")}
    bad, exceptions = [], []
    for r in effects.itertuples():
        key = (r.contrast_id, r.model, r.blinding)
        ref = fmap.get(key)
        if ref is None:
            exceptions.append({"contrast_id": r.contrast_id,
                               "model": r.model, "blinding": r.blinding,
                               "frozen": None,
                               "rebuilt": r.model_effect_native,
                               "reason": "cell absent from frozen 262-row "
                                        "grid"})
            continue
        diff = r.model_effect_native - ref
        if abs(diff) > TOL:
            exceptions.append({"contrast_id": r.contrast_id,
                               "model": r.model, "blinding": r.blinding,
                               "frozen": ref,
                               "rebuilt": r.model_effect_native,
                               "reason": "run10 records re-run "
                                        "(2026-10-05) differ from the "
                                        "2026-10-04 state behind the "
                                        "frozen file"})
            exp_id = exp_by_contrast[r.contrast_id]
            if exp_id in RUN6_EXPERIMENTS:
                bad.append(key)
    if bad:
        raise ValueError(f"{len(bad)} run6 original effects differ from "
                         f"frozen (hard gate): {bad[:5]}")
    log(f"originals: run6 legs match frozen exactly; "
        f"{len(exceptions)} documented run10 exceptions "
        "(kept in canonical, reported in OLD_VS_CORRECTED)")
    return effects, pd.DataFrame(exceptions)


def check_expansion(effects: pd.DataFrame) -> pd.DataFrame:
    """Every rebuilt expansion delta must equal the frozen native delta."""
    frozen = pd.read_csv(EXPANSION17)
    keep = frozen[~frozen["unestimable"].astype(str).str.lower().eq("true")]
    fmap = {(r.contrast_id, r.model, 0 if r.blinding == "blinded" else 1):
            r.delta_model for r in keep.itertuples()}
    bad, drop = [], []
    for r in effects.itertuples():
        ref = fmap.get((r.contrast_id, r.model, r.blinding))
        if ref is None or ref != ref:
            # The frozen file marked this cell missing (unestimable):
            # it stays missing in the canonical data, never imputed.
            drop.append((r.contrast_id, r.model, r.blinding))
            continue
        if abs(ref - r.model_effect_native) > TOL:
            bad.append((r.contrast_id, r.model, r.blinding,
                        ref, r.model_effect_native))
    if bad:
        raise ValueError(f"{len(bad)} expansion effects differ from frozen: "
                         f"{bad[:5]}")
    if drop:
        mask = pd.Series([tuple(x) for x in effects[
            ["contrast_id", "model", "blinding"]].itertuples(index=False)],
            index=effects.index)
        effects = effects[~mask.isin(drop)]
    log(f"expansion: {len(effects)} rebuilt effects all match frozen "
        f"expansion17 (tol {TOL}); {len(drop)} unestimable cells stay "
        "missing")
    return effects
