"""Backup and restore checks for the sixgame data root.

What this file does, in plain language:

- ``backup`` copies the whole data root to a backup folder and writes
  a checksum list (``MANIFEST.sha256``) of everything it copied.
- ``verify`` re-checks a backup folder against its checksum list and
  reports anything missing or changed.
- ``main`` is the command line: ``backup_data.py`` makes a timestamped
  backup, ``--verify <dir>`` checks one, ``--preserve`` copies the old
  repo result folders into the data root first.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

try:
    from sixgame import data_root
except ImportError:  # pragma: no cover - direct execution layout
    import data_root

MANIFEST_NAME = "MANIFEST.sha256"
DEFAULT_BACKUP_PARENT = Path.home() / "experiment-data" / "fos" / "sixgame-backups"


def backup(source: Path, destination: Path) -> dict[str, int]:
    """Copy every file from source to destination and write checksums."""
    if not source.exists():
        raise data_root.DataRootError(f"data root not found: {source}")
    destination.mkdir(parents=True, exist_ok=True)
    copied = 0
    for path in sorted(source.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        # skip the backup's own top-level manifest (it cannot hash itself),
        # but DO copy per-run manifests written next to the data
        if path.name == MANIFEST_NAME and path.parent == source:
            continue
        rel = path.relative_to(source)
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or data_root.sha256_of(target) != data_root.sha256_of(
            path
        ):
            shutil.copy2(path, target)
        copied += 1
    count = data_root.write_manifest(source, destination / MANIFEST_NAME)
    return {"copied": copied, "manifest_entries": count}


def verify(backup_dir: Path) -> list[str]:
    """Check every checksum in the backup; returns problems (empty=OK)."""
    return data_root.verify_manifest(backup_dir, backup_dir / MANIFEST_NAME)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="sixgame data-root backup")
    parser.add_argument(
        "--verify",
        metavar="DIR",
        help="verify an existing backup folder instead of making one",
    )
    parser.add_argument(
        "--preserve",
        action="store_true",
        help="copy the old repo result datasets into the data root first",
    )
    parser.add_argument(
        "--repo-results",
        type=Path,
        default=None,
        help="repo results/sixgame folder (default: sibling 'fos' repo)",
    )
    parser.add_argument("--dest", type=Path, default=None, help="backup folder")
    args = parser.parse_args(argv)

    root = data_root.default_data_root()
    if args.preserve:
        repo_results = args.repo_results
        if repo_results is None:
            repo_results = (
                Path.home() / "Documents" / "ZJU work" / "fos" / "results" / "sixgame"
            )
        counts = data_root.preserve_datasets(repo_results, root)
        for run_id, count in counts.items():
            print(f"preserved {run_id}: {count} files")
    if args.verify:
        problems = verify(Path(args.verify))
        if problems:
            for problem in problems:
                print(f"VERIFY FAIL: {problem}", file=sys.stderr)
            return 1
        print(f"verify OK: {args.verify}")
        return 0
    destination = args.dest
    if destination is None:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        destination = DEFAULT_BACKUP_PARENT / stamp
    stats = backup(root, destination)
    print(
        f"backup {root} -> {destination}: {stats['copied']} files, "
        f"{stats['manifest_entries']} manifest entries"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
