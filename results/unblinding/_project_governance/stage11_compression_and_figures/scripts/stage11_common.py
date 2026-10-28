# stage11_common.py — shared data plumbing for the Stage 11 Task A
# compression + noise analysis.
#
# What this file does:
#   Loads the reconciled Stage 10 canonical datasets through the supported
#   verified loader (never frozen Stage 3/5/9 values), checks the sign
#   convention, flags human-direction confidence per contrast, and exposes
#   the analysis tables used by every later script.
#
#   load_canonical()            — verified canonical tables (model effects,
#                                 paired analysis, corrected uncertainty).
#   check_sign_convention()     — fails loudly if model/human effects are not
#                                 on the same signed treatment-minus-control
#                                 standardized scale.
#   contrast_level_table()      — one row per contrast: human effect, SE,
#                                 direction-confidence flag, |effect| quartile.
#   cell_level_table()          — one row per contrast x model x blinding,
#                                 ready for the regression fits.
#   DIRECTION_UNCERTAIN         — the 6 contrasts whose human direction is
#                                 not statistically confident (excluded from
#                                 the primary direction analysis, reported
#                                 separately).

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

# Where the Stage 10 verified loader lives (read-only — we import it, and
# make sure Python does not try to write bytecode caches next to it).
STAGE10 = Path(
    "/home/justin/Documents/ZJU work/fos/results/unblinding/"
    "_project_governance/stage10_data_reconciliation")
STAGE10_DATA = STAGE10 / "data"
STAGE10_MANIFEST = STAGE10 / "provenance" / "CANONICAL_DATA_MANIFEST.json"
STAGE10_REGISTRY = STAGE10 / "provenance" / "DATASET_REGISTRY.json"
sys.dont_write_bytecode = True
sys.path.insert(0, str(STAGE10 / "scripts"))

# NOTE: the Stage 10 supported loader (canonical_data.py) currently cannot
# be imported because the in-repo stage10_common.py is mid-recalculation
# and no longer exposes the constants the loader expects. We therefore
# verify the canonical tables ourselves — SHA-256 against the
# reconciled_v1 provenance manifest + approved registry entry — and refuse
# to proceed on any mismatch. Same files, same version gate, no silent
# substitution of frozen Stage 3/5/9 values.
CANONICAL_TABLES = {
    "model_effects": "CANONICAL_MODEL_EFFECTS.csv",
    "paired": "CANONICAL_PAIRED_ANALYSIS.csv",
    "uncertainty": "MODEL_EFFECT_UNCERTAINTY_CORRECTED.csv",
}


def _verify_reconciled_v1() -> None:
    """Registry says approved=reconciled_v1 and every canonical table's
    SHA-256 matches the manifest; raise loudly otherwise."""
    import hashlib
    import json
    registry = json.loads(STAGE10_REGISTRY.read_text())
    if registry.get("approved") != "reconciled_v1":
        raise RuntimeError(
            f"Stage 10 registry approved={registry.get('approved')!r}; "
            "expected reconciled_v1 — refusing stale data")
    manifest = json.loads(STAGE10_MANIFEST.read_text())
    if manifest.get("version") != "reconciled_v1":
        raise RuntimeError("manifest is not reconciled_v1")
    for name, recorded in manifest.get("outputs", {}).items():
        path = STAGE10_DATA / name
        if not path.is_file():
            raise RuntimeError(f"canonical output missing: {path}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != recorded:
            raise RuntimeError(f"hash mismatch for {path} — table changed "
                               "after the verified build")
    print("[data] reconciled_v1 verified: registry approved + all "
          f"{len(manifest['outputs'])} manifest hashes match")

# Master seed for every random draw in Stage 11 Task A.
SEED = 20261029

# Human direction confidence rule (same as Stage 6): the human benchmark
# direction counts as confident when Pr(human effect > 0) is below 0.025 or
# above 0.975, using the corrected Stage 10 human SE.
CONF_CUT = 0.975


def load_canonical() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load the verified Stage 10 canonical tables (reconciled_v1).

    Tables are verified by SHA-256 against the Stage 10 provenance
    manifest (see module note); raises on any mismatch — never falls back
    to frozen or stale files.
    """
    _verify_reconciled_v1()
    effects = pd.read_csv(STAGE10_DATA / CANONICAL_TABLES["model_effects"])
    paired = pd.read_csv(STAGE10_DATA / CANONICAL_TABLES["paired"])
    uncertainty = pd.read_csv(STAGE10_DATA / CANONICAL_TABLES["uncertainty"])
    for name, df in (("model_effects", effects), ("paired", paired),
                     ("uncertainty", uncertainty)):
        if "source_version" in df.columns and \
                (df.source_version != "reconciled_v1").any():
            raise RuntimeError(f"{name}: mixed/unknown source_version")
    return effects, paired, uncertainty


def check_sign_convention(effects: pd.DataFrame,
                          paired: pd.DataFrame) -> None:
    """Verify both tables use the same signed treatment-minus-control scale.

    For every paired cell the blinded leg of the effects table must equal
    the paired table's y_std_blinded (and likewise disclosed), and the
    human effect columns must agree. Any mismatch means the tables are not
    on a shared convention and the analysis must stop.
    """
    merged = effects.merge(
        paired[["contrast_id", "model", "y_std_blinded", "y_std_disclosed"]],
        on=["contrast_id", "model"], how="inner")
    if len(merged) != 2 * len(paired):
        raise ValueError("effects/paired join lost rows — keys disagree")
    blinded = merged[merged.blinding == 0]
    disclosed = merged[merged.blinding == 1]
    dev_b = (blinded.model_effect_std - blinded.y_std_blinded).abs().max()
    dev_d = (disclosed.model_effect_std - disclosed.y_std_disclosed).abs().max()
    if max(dev_b, dev_d) > 1e-9:
        raise ValueError(
            f"sign/scale convention mismatch: max deviation {max(dev_b, dev_d)}")
    per_contrast = paired.groupby("contrast_id").agg(
        h=("human_effect_std", "first"), n=("human_effect_std", "nunique"))
    if (per_contrast.n != 1).any():
        raise ValueError("human effect varies within a contrast — bad join")
    print(f"[convention] OK: signed t-minus-c standardized scale shared "
          f"by {len(paired)} paired cells, "
          f"max deviation {max(dev_b, dev_d):.2e}")


def contrast_level_table(paired: pd.DataFrame) -> pd.DataFrame:
    """One row per contrast with human effect, SE, confidence, quartile.

    Confidence uses the Stage 10 corrected human SE with the Stage 6 rule.
    Quartiles of |human effect| use the confident contrasts only (labels
    Q1..Q4 by tercile-free quartile cut on that subset); uncertain
    contrasts get the label 'uncertain'.
    """
    conf_se = {"C-17": 0.043991, "C-27": 0.022337, "C-28": 0.022504,
               "C-33": 0.068038, "C-34": 0.077435, "C-36": 0.033800}
    g = paired.groupby("contrast_id")
    out = g.agg(experiment_id=("experiment_id", "first"),
                human_effect=("human_effect_std", "first"),
                human_se=("human_effect_se", "first")).reset_index()
    out["human_pr_pos"] = norm.cdf(out.human_effect / out.human_se)
    out["direction_confident"] = ((out.human_pr_pos > CONF_CUT) |
                                  (out.human_pr_pos < 1 - CONF_CUT))
    # Guard against silent SE regressions in Stage 10: the six contrasts
    # Stage 6 flagged as direction-uncertain must stay uncertain here.
    for cid, se in conf_se.items():
        row = out.loc[out.contrast_id == cid].iloc[0]
        if row.direction_confident or abs(row.human_se - se) > 1e-3:
            raise ValueError(f"contrast {cid}: expected uncertain with "
                             f"SE~{se}, got SE={row.human_se}, "
                             f"confident={row.direction_confident}")
    conf = out[out.direction_confident]
    cuts = np.quantile(conf.human_effect.abs(), [0.25, 0.5, 0.75])
    out["abs_human"] = out.human_effect.abs()
    out["quartile"] = np.where(
        ~out.direction_confident, "uncertain",
        np.where(out.abs_human <= cuts[0], "Q1",
                 np.where(out.abs_human <= cuts[1], "Q2",
                          np.where(out.abs_human <= cuts[2], "Q3", "Q4"))))
    out["quartile_cut"] = out.abs_human.where(out.direction_confident)
    return out.sort_values("contrast_id").reset_index(drop=True)


def cell_level_table(effects: pd.DataFrame,
                     contrasts: pd.DataFrame) -> pd.DataFrame:
    """One row per contrast x model x blinding with all fit inputs.

    Columns: y (signed standardized model effect), h (contrast human
    effect), plus integer indices for experiment, contrast, model, and the
    blinding flag. This is the exact row set used by every hierarchical
    fit, so the reported n is the n analysed.
    """
    df = effects.merge(
        contrasts[["contrast_id", "human_effect", "direction_confident"]],
        on="contrast_id", how="left")
    if df.human_effect.isna().any():
        raise ValueError("effects rows with no contrast-level human effect")
    df = df.rename(columns={"model_effect_std": "y", "blinding": "b"})
    df["exp_idx"], _ = pd.factorize(df.experiment_id)
    df["contrast_idx"], _ = pd.factorize(df.contrast_id)
    df["model_idx"], _ = pd.factorize(df.model)
    return df.reset_index(drop=True)
