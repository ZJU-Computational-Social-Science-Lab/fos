# Tests for twin2k10r/dataset_manifest.py — the file-fingerprint module.
# WHAT THESE TESTS CHECK, in plain words:
#   - Every dataset file the pipeline consumes gets a SHA-256 fingerprint
#     recorded in dataset_manifest.json.
#   - Building the manifest twice gives the exact same fingerprints (it is
#     stable, not random).
#   - If a dataset file goes missing or its bytes change later, checking
#     the manifest raises a specific error — the pipeline never silently
#     reads a different dataset than the one it was designed for.
import hashlib
import json

import pytest


# ---------- 1. SHA-256 is recorded per consumed file ----------

def test_manifest_records_sha256_for_every_consumed_file(fixture_dataset_root):
    """The manifest holds a sha256 entry for each file the pipeline reads."""
    from twin2k10r import dataset_manifest

    manifest = dataset_manifest.build_manifest(fixture_dataset_root)
    required = [
        "question_catalog_and_human_response_csv/wave1_3_response.csv",
        "question_catalog_and_human_response_csv/wave1_3_response_label.csv",
        "question_catalog_and_human_response_csv/question_catalog.json",
        "raw_data/wave 1 scores.csv",
    ]
    for rel in required:
        assert rel in manifest, f"manifest missing consumed file: {rel}"
        expected = hashlib.sha256(
            (fixture_dataset_root / rel).read_bytes()
        ).hexdigest()
        assert manifest[rel] == expected, f"wrong sha256 for {rel}"


def test_manifest_sha256_values_are_real_hash_strings(fixture_dataset_root):
    """Each fingerprint is a 64-character lowercase hex digest."""
    from twin2k10r import dataset_manifest

    manifest = dataset_manifest.build_manifest(fixture_dataset_root)
    for rel, digest in manifest.items():
        assert len(digest) == 64, f"{rel}: not a sha256 hex digest"
        assert digest == digest.lower(), f"{rel}: digest must be lowercase"
        int(digest, 16), f"{rel}: digest must be hexadecimal"


# ---------- 2. The manifest is stable ----------

def test_manifest_is_stable_across_rebuilds(fixture_dataset_root):
    """Building the manifest twice gives byte-identical fingerprints."""
    from twin2k10r import dataset_manifest

    first = dataset_manifest.build_manifest(fixture_dataset_root)
    second = dataset_manifest.build_manifest(fixture_dataset_root)
    assert first == second, "manifest fingerprints changed between rebuilds"
    # The JSON serialisation is stable too (sorted keys, no randomness).
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_written_manifest_file_matches_rebuilt_manifest(fixture_dataset_root):
    """write_manifest saves a dataset_manifest.json that verify accepts."""
    from twin2k10r import dataset_manifest

    dataset_manifest.write_manifest(fixture_dataset_root)
    manifest_path = fixture_dataset_root / dataset_manifest.MANIFEST_FILENAME
    assert manifest_path.exists(), "write_manifest wrote no dataset_manifest.json"
    stored = json.loads(manifest_path.read_text())
    rebuilt = dataset_manifest.build_manifest(fixture_dataset_root)
    assert stored == rebuilt


# ---------- 3. Missing or changed files raise ----------

def test_verify_passes_when_nothing_changed(fixture_dataset_root):
    """verify_manifest says nothing when the dataset matches its manifest."""
    from twin2k10r import dataset_manifest

    dataset_manifest.write_manifest(fixture_dataset_root)
    # No exception expected.
    dataset_manifest.verify_manifest(fixture_dataset_root)


def test_verify_raises_when_a_file_changed(fixture_dataset_root):
    """Editing one consumed dataset byte makes verify_manifest raise."""
    from twin2k10r import dataset_manifest

    dataset_manifest.write_manifest(fixture_dataset_root)
    target = fixture_dataset_root / "raw_data" / "wave 1 scores.csv"
    original = target.read_bytes()
    try:
        target.write_bytes(original + b"tamper\n")
        with pytest.raises(dataset_manifest.DatasetHashMismatch) as err:
            dataset_manifest.verify_manifest(fixture_dataset_root)
        assert "wave 1 scores.csv" in str(err.value), (
            "the error must name the file that changed"
        )
    finally:
        target.write_bytes(original)


def test_verify_raises_when_a_consumed_file_is_missing(fixture_dataset_root):
    """Deleting one consumed dataset file makes verify_manifest raise."""
    from twin2k10r import dataset_manifest

    dataset_manifest.write_manifest(fixture_dataset_root)
    target = fixture_dataset_root / "raw_data" / "wave 1 scores.csv"
    original = target.read_bytes()
    try:
        target.unlink()
        with pytest.raises(dataset_manifest.DatasetHashMismatch):
            dataset_manifest.verify_manifest(fixture_dataset_root)
    finally:
        target.write_bytes(original)


def test_verify_raises_when_manifest_file_is_absent(fixture_dataset_root):
    """No dataset_manifest.json at all is an error, not a silent pass."""
    from twin2k10r import dataset_manifest

    manifest_path = fixture_dataset_root / dataset_manifest.MANIFEST_FILENAME
    if manifest_path.exists():
        manifest_path.unlink()
    with pytest.raises(dataset_manifest.DatasetHashMismatch):
        dataset_manifest.verify_manifest(fixture_dataset_root)


# ---------- 4. The manifest hash goes into the provenance chain ----------

def test_manifest_of_manifest_is_available_for_provenance(fixture_dataset_root):
    """The module can compute a single sha256 over the whole manifest —
    the number POOL_PROVENANCE.json stores as dataset_manifest_sha256."""
    from twin2k10r import dataset_manifest

    digest = dataset_manifest.manifest_sha256(fixture_dataset_root)
    assert len(digest) == 64
    digest_again = dataset_manifest.manifest_sha256(fixture_dataset_root)
    assert digest == digest_again, "manifest-of-manifest must be stable"
