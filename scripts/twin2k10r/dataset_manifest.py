# This file fingerprints the dataset: it computes a SHA-256 checksum for
# every dataset file the pipeline consumes, saves them into a
# dataset_manifest.json, and can later re-check that nothing changed.
# Functions:
#   build_manifest     — compute the checksum dictionary for the dataset.
#   write_manifest     — save that dictionary as dataset_manifest.json.
#   verify_manifest    — re-check every file against the saved manifest;
#                        raises DatasetHashMismatch on any change or
#                        missing file (including a missing manifest).
#   manifest_sha256    — one single checksum over the whole manifest, the
#                        number the pool provenance record stores.
import hashlib
import json
from pathlib import Path

# The files the persona pipeline actually reads, relative to the dataset
# root. Anything not listed here is never consumed, so it is never
# fingerprinted.
CONSUMED_FILES = [
    "question_catalog_and_human_response_csv/wave1_3_response.csv",
    "question_catalog_and_human_response_csv/wave1_3_response_label.csv",
    "question_catalog_and_human_response_csv/question_catalog.json",
    "raw_data/wave 1 scores.csv",
]

# The name of the manifest file saved inside the dataset root.
MANIFEST_FILENAME = "dataset_manifest.json"


def _sha256_of(path) -> str:
    """The lowercase hex SHA-256 of one file's bytes."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(dataset_root) -> dict:
    """Checksum every consumed dataset file.

    In: the dataset root path. Out: a dict mapping each consumed file's
    relative path to its SHA-256 hex digest. Raises FileNotFoundError
    when a consumed file is missing (the pipeline cannot run against a
    broken dataset).
    """
    root = Path(dataset_root)
    return {
        rel: _sha256_of(root / rel) for rel in CONSUMED_FILES
    }


def manifest_path(dataset_root):
    """Where the manifest file lives inside the dataset root."""
    return Path(dataset_root) / MANIFEST_FILENAME


def write_manifest(dataset_root, manifest_file=None) -> dict:
    """Save dataset_manifest.json and return the manifest dictionary.

    The dataset mirror itself is read-only, so the manifest file can be
    stored elsewhere (e.g. inside a run directory) via manifest_file.
    """
    manifest = build_manifest(dataset_root)
    path = Path(manifest_file) if manifest_file else manifest_path(dataset_root)
    path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def verify_manifest(dataset_root, manifest_file=None) -> None:
    """Re-check every consumed file against the saved manifest.

    Raises DatasetHashMismatch (naming the offending file) when the
    manifest file is absent, a consumed file is missing, or any file's
    checksum differs. Returns silently when everything matches.
    """
    path = Path(manifest_file) if manifest_file else manifest_path(dataset_root)
    if not path.exists():
        raise DatasetHashMismatch(
            f"no {MANIFEST_FILENAME} at {dataset_root} — the dataset was "
            "never fingerprinted, so it cannot be trusted as frozen"
        )
    stored = json.loads(path.read_text(encoding="utf-8"))
    try:
        rebuilt = build_manifest(dataset_root)
    except FileNotFoundError as exc:
        raise DatasetHashMismatch(
            f"consumed dataset file is missing: {exc.filename}"
        ) from exc
    for rel, expected in stored.items():
        if rel not in rebuilt:
            raise DatasetHashMismatch(
                f"{rel} is listed in the manifest but no longer readable"
            )
        if rebuilt[rel] != expected:
            raise DatasetHashMismatch(
                f"{rel} changed since the manifest was written "
                f"(was {expected}, now {rebuilt[rel]})"
            )
    for rel in rebuilt:
        if rel not in stored:
            raise DatasetHashMismatch(
                f"{rel} is new since the manifest was written"
            )


def manifest_sha256(dataset_root) -> str:
    """One checksum over the whole manifest — the provenance-chain number.

    Stable for the same dataset: the manifest dictionary is serialised
    with sorted keys before hashing.
    """
    manifest = build_manifest(dataset_root)
    serialised = json.dumps(manifest, sort_keys=True).encode("utf-8")
    return hashlib.sha256(serialised).hexdigest()


class DatasetHashMismatch(Exception):
    """A consumed dataset file changed, went missing, or was never
    fingerprinted. The run must stop, never read a moved dataset."""
