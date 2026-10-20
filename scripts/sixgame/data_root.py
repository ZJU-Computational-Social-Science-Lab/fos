"""The permanent home for sixgame experiment data, outside every worktree.

What this file does, in plain language:

- ``default_data_root`` says where experiment data permanently lives
  (``~/experiment-data/fos/sixgame``), unless the ``SIXGAME_DATA_ROOT``
  environment variable points somewhere else (tests use this).
- ``resolve_out_dir`` decides the folder a run writes to: by default a
  folder named after the run inside the data root, and it refuses
  paths outside the data root unless explicitly allowed.
- ``sha256_of`` computes a file's fingerprint.
- ``write_manifest`` records the fingerprint of every file in a folder.
- ``verify_manifest`` re-checks those fingerprints and lists problems.
- ``preserve_datasets`` copies the old result folders from the repo
  into the data root (leaving the originals untouched) and writes the
  fingerprint file ``PRESERVATION_MANIFEST.sha256``.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path


class DataRootError(RuntimeError):
    """Raised when an output path would break the data-root policy."""


#: The run currently being collected (frozen corrective run).
DEFAULT_RUN_ID = "engineering_pilot_corrective"

#: Run folders copied from the repo before the default output switched.
PRESERVED_RUN_IDS = ("engineering_pilot", "engineering_pilot_corrective")

#: Name of the fingerprint file for the preserved datasets.
PRESERVATION_MANIFEST = "PRESERVATION_MANIFEST.sha256"


def default_data_root() -> Path:
    """The permanent data folder, or the SIXGAME_DATA_ROOT override."""
    override = os.environ.get("SIXGAME_DATA_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    return (Path.home() / "experiment-data" / "fos" / "sixgame").resolve()


def resolve_out_dir(
    out_dir: Path | str | None,
    run_id: str,
    data_root: Path | None = None,
    allow_any: bool = False,
) -> Path:
    """The folder a run should write to, always inside the data root.

    With no ``--out-dir`` the run writes to ``<data_root>/<run_id>``.
    An explicit ``--out-dir`` is accepted only if it lives inside the
    data root, unless ``allow_any`` is True (tests only).
    """
    root = data_root if data_root is not None else default_data_root()
    if out_dir is None:
        return root / run_id
    chosen = Path(out_dir).expanduser().resolve()
    if allow_any:
        return chosen
    try:
        chosen.relative_to(root)
    except ValueError as exc:
        raise DataRootError(
            f"--out-dir {chosen} is outside the data root {root}; "
            "use --allow-any-outdir only in tests"
        ) from exc
    return chosen


def sha256_of(path: Path) -> str:
    """The file's sha256 fingerprint, read in chunks (large files OK)."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_lines(root: Path) -> list[str]:
    """One ``<sha256>  <relative-path>`` line per file under root.

    The fingerprint file itself is never listed (it cannot hash itself).
    """
    lines = []
    for path in sorted(root.rglob("*")):
        if (
            path.is_file()
            and not path.is_symlink()
            and path.name != PRESERVATION_MANIFEST
        ):
            rel = path.relative_to(root).as_posix()
            lines.append(f"{sha256_of(path)}  {rel}")
    return lines


def write_manifest(root: Path, manifest_path: Path) -> int:
    """Write the fingerprint file; returns how many files it covers."""
    lines = manifest_lines(root)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
    return len(lines)


def verify_manifest(root: Path, manifest_path: Path) -> list[str]:
    """Re-check every fingerprint; returns a list of problems (empty=OK)."""
    if not manifest_path.exists():
        return [f"manifest missing: {manifest_path}"]
    problems: list[str] = []
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, rel = line.split("  ", 1)
        if rel == PRESERVATION_MANIFEST:
            continue
        path = root / rel
        if not path.exists():
            problems.append(f"missing: {rel}")
        elif sha256_of(path) != expected:
            problems.append(f"hash mismatch: {rel}")
    return problems


def preserve_datasets(repo_results: Path, data_root: Path) -> dict[str, int]:
    """Copy the old run folders from the repo into the data root.

    Copies (never moves) each preserved run folder, leaves the repo
    originals untouched, writes the fingerprint file over both, and
    verifies every copy.  Returns ``{run_id: file_count}``.
    """
    if not repo_results.exists():
        raise DataRootError(f"repo results folder not found: {repo_results}")
    counts: dict[str, int] = {}
    for run_id in PRESERVED_RUN_IDS:
        source = repo_results / run_id
        if not source.exists():
            raise DataRootError(f"preserved dataset missing: {source}")
        destination = data_root / run_id
        destination.mkdir(parents=True, exist_ok=True)
        for path in sorted(source.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            target = destination / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists() or sha256_of(target) != sha256_of(path):
                shutil.copy2(path, target)
        counts[run_id] = sum(
            1 for p in destination.rglob("*") if p.is_file() and not p.is_symlink()
        )
    write_manifest(data_root, data_root / PRESERVATION_MANIFEST)
    problems = verify_manifest(data_root, data_root / PRESERVATION_MANIFEST)
    if problems:
        raise DataRootError("preservation verification failed: " + "; ".join(problems))
    return counts
