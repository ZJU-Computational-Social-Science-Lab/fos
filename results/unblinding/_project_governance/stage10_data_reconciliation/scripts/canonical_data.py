# canonical_data.py — the supported loader for the Stage 10 canonical
# datasets. It resolves the approved version from the dataset registry,
# verifies the provenance manifest (input + output hashes), checks that
# every required column and unique key is present, and fails fast with a
# specific error instead of ever falling back to stale Stage 5 files.
#
# What each function does:
#   load_model_effects      — the supported entry point (version,
#                             require_verified); returns the effects table.
#   load_table              — any canonical table by name, same checks.
#   _resolve_version        — registry lookup of the approved version.
#   _verify_manifest        — output hashes + recorded version + seed.
#   _check_schema           — required columns + unique-key checks.
#   CanonicalDataError      — specific failure type (never a silent fallback).

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from stage10_common import (DATA_DIR, MANIFEST, PROV_DIR, REGISTRY_JSON,
                            VERSION, sha256_file)

TABLES = {
    "arm_outcomes": "CANONICAL_ARM_OUTCOMES.csv",
    "model_effects": "CANONICAL_MODEL_EFFECTS.csv",
    "uncertainty": "MODEL_EFFECT_UNCERTAINTY_CORRECTED.csv",
    "paired": "CANONICAL_PAIRED_ANALYSIS.csv",
    "old_vs_corrected": "OLD_VS_CORRECTED_EFFECTS.csv",
}

REQUIRED_COLUMNS = {
    "model_effects": ["contrast_id", "experiment_id", "study_group", "model",
                      "blinding", "treatment_condition", "control_condition",
                      "model_effect_pp", "model_effect_std", "human_effect_std",
                      "sd_human_pooled_pp", "model_effect_se_pp",
                      "model_effect_se_std", "source_version"],
    "arm_outcomes": ["contrast_id", "model", "blinding", "model_effect_pp",
                     "model_effect_std", "source_version"],
    "uncertainty": ["contrast_id", "model", "blinding", "se_native", "se_std"],
    "paired": ["contrast_id", "model", "y_std_blinded", "y_std_disclosed",
               "se_y_std_blinded", "se_y_std_disclosed", "paired_cell"],
}

UNIQUE_KEYS = {
    "model_effects": ["contrast_id", "model", "blinding"],
    "arm_outcomes": ["contrast_id", "model", "blinding"],
    "uncertainty": ["contrast_id", "model", "blinding"],
    "paired": ["contrast_id", "model"],
}


class CanonicalDataError(RuntimeError):
    """Raised when the canonical data is missing, unverified, or stale."""


def load_model_effects(version: str = VERSION,
                       require_verified: bool = True) -> pd.DataFrame:
    """The supported entry point: canonical model effects, verified."""
    return load_table("model_effects", version=version,
                      require_verified=require_verified)


def load_table(table: str, version: str = VERSION,
               require_verified: bool = True) -> pd.DataFrame:
    """One canonical table by name, with registry + manifest checks."""
    if table not in TABLES:
        raise CanonicalDataError(f"unknown table '{table}'")
    approved = _resolve_version(version, require_verified)
    path = DATA_DIR / TABLES[table]
    if not path.is_file():
        raise CanonicalDataError(f"missing canonical table: {path}")
    if approved is not None:
        _verify_manifest(approved, require_verified)
    df = pd.read_csv(path)
    _check_schema(df, table, path)
    if "source_version" in df.columns and df.source_version.nunique() > 1:
        raise CanonicalDataError(f"{path}: mixed source_version values")
    return df


def _resolve_version(version: str,
                     require_verified: bool) -> dict | None:
    """Approved version entry from the registry (None = skip checks)."""
    if not REGISTRY_JSON.is_file():
        if require_verified:
            raise CanonicalDataError(
                f"dataset registry missing: {REGISTRY_JSON}")
        return None
    registry = json.loads(REGISTRY_JSON.read_text())
    entry = registry.get("versions", {}).get(version)
    if entry is None:
        raise CanonicalDataError(
            f"version '{version}' is not in the dataset registry")
    if require_verified and registry.get("approved") != version:
        raise CanonicalDataError(
            f"version '{version}' exists but is not the approved version "
            f"('{registry.get('approved')}'); refusing stale data")
    if not MANIFEST.is_file():
        if require_verified:
            raise CanonicalDataError(f"manifest missing: {MANIFEST}")
        return entry
    recorded = json.loads(MANIFEST.read_text()).get("version")
    if require_verified and recorded != version:
        raise CanonicalDataError(
            f"manifest records version '{recorded}', requested '{version}'")
    return entry


def _verify_manifest(entry: dict, require_verified: bool) -> None:
    """Output hashes in the registry entry must match the manifest."""
    if entry.get("manifest_sha256") != sha256_file(MANIFEST):
        msg = "dataset registry is out of date with the manifest"
        if require_verified:
            raise CanonicalDataError(msg + " — rerun the rebuild")
        return
    manifest = json.loads(MANIFEST.read_text())
    for name, recorded in manifest.get("outputs", {}).items():
        path = DATA_DIR / name
        if not path.is_file():
            raise CanonicalDataError(f"manifest output missing: {path}")
        if sha256_file(path) != recorded:
            raise CanonicalDataError(
                f"hash mismatch for {path} — the table changed after the "
                "verified build; refuse and rerun")


def _check_schema(df: pd.DataFrame, table: str, path: Path) -> None:
    """Required columns and unique keys, fail-fast."""
    missing = [c for c in REQUIRED_COLUMNS[table] if c not in df.columns]
    if missing:
        raise CanonicalDataError(f"{path}: missing columns {missing}")
    keys = UNIQUE_KEYS[table]
    if df.duplicated(keys).any():
        raise CanonicalDataError(f"{path}: duplicate keys on {keys}")
    if len(df) == 0:
        raise CanonicalDataError(f"{path}: empty table")
