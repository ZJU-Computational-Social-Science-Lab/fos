# test_loader_and_integrity.py — the canonical loader must resolve the
# approved version, verify the manifest, reject stale or tampered data,
# and never fall back silently; plus manifest consistency checks and a
# direct raw-record recomputation of one canonical cell.

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

import canonical_data
import stage10_common as sc
from canonical_data import CanonicalDataError


def test_loader_returns_verified_effects():
    """The supported entry point returns the canonical effects table."""
    df = canonical_data.load_model_effects()
    assert len(df) > 0
    assert set(df.blinding.unique()) == {0, 1}


def test_loader_rejects_unknown_version():
    """An unregistered version is refused, never silently served."""
    with pytest.raises(CanonicalDataError, match="not in the dataset"):
        canonical_data.load_model_effects(version="reconciled_v0")


def test_loader_rejects_tampered_output(tmp_path, monkeypatch):
    """A changed table must fail the manifest hash check."""
    real_dir = canonical_data.DATA_DIR
    import shutil
    tmp_data = tmp_path / "data"
    shutil.copytree(real_dir, tmp_data)
    victim = tmp_data / "CANONICAL_MODEL_EFFECTS.csv"
    df = pd.read_csv(victim)
    df.loc[0, "model_effect_pp"] = 42.0
    df.to_csv(victim, index=False)
    monkeypatch.setattr(canonical_data, "DATA_DIR", tmp_data)
    with pytest.raises(CanonicalDataError, match="hash mismatch"):
        canonical_data.load_model_effects()


def test_loader_rejects_stale_registry(tmp_path, monkeypatch):
    """If the registry points elsewhere, verified loads must fail."""
    stale = tmp_path / "DATASET_REGISTRY.json"
    stale.write_text(json.dumps({"approved": "some_other_version",
                                 "versions": {}}))
    monkeypatch.setattr(canonical_data, "REGISTRY_JSON", stale)
    with pytest.raises(CanonicalDataError, match="not in the dataset"):
        canonical_data.load_model_effects()


def test_loader_rejects_missing_table(tmp_path, monkeypatch):
    """A missing canonical file is a loud error, not an empty frame."""
    real_dir = canonical_data.DATA_DIR
    monkeypatch.setattr(canonical_data, "DATA_DIR",
                        tmp_path)  # empty dir: tables 'missing'
    with pytest.raises(CanonicalDataError, match="missing canonical table"):
        canonical_data.load_table("model_effects", require_verified=False)
    assert real_dir.is_dir()


def test_manifest_input_hashes_match_current_files():
    """Every manifest input hash matches the current read-only source."""
    manifest = json.loads(sc.MANIFEST.read_text())
    for rel, recorded in manifest["inputs"].items():
        assert sc.sha256_file(sc.UNBL / rel) == recorded


def test_integrity_verifier_passes():
    """The standalone verifier reports every check green."""
    import verify_integrity
    results = verify_integrity.verify()
    failed = [name for name, ok, _ in results if not ok]
    assert not failed, f"failing checks: {failed}"


def test_canonical_cell_recomputed_from_raw_records(arm):
    """One canonical cell is recomputed straight from records.jsonl."""
    row = arm[(arm.contrast_id == "C-01") & (arm.model == "gemma-4-12b-it-qat")
              & (arm.blinding == 0)]
    reg = sc.register_for("C-01")
    values = {"gain": [], "loss": []}
    path = (sc.RUN6 / "gemma-4-12b-it-qat" / "disease_blinded"
            / "records.jsonl")
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            if rec.get("succeeded") and rec.get("p_safe_norm") is not None:
                values[rec["arm"]].append(float(rec["p_safe_norm"]))
    delta = (np.mean(values[reg["treatment_condition"]])
             - np.mean(values[reg["control_condition"]])) * 100.0
    assert np.isclose(delta, row.model_effect_pp.iloc[0], rtol=0, atol=1e-9)


def test_record_keys_unique_in_one_raw_file():
    """Raw records identify themselves uniquely by (qid, arm, persona)."""
    path = (sc.RUN6 / "gemma-4-12b-it-qat" / "disease_blinded"
            / "records.jsonl")
    seen = set()
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            key = (rec["qid"], rec["arm"], rec["persona_id"])
            assert key not in seen, f"duplicate record key {key}"
            seen.add(key)
    assert seen
