"""Move failed experiment records out of cell files so runs can refill them.

What this file does, in plain language:

- ``main`` scans the run folder for the given model's record files, moves
  every record that did NOT succeed into ``invalid_attempts/`` (kept for
  the audit trail, never deleted), and rewrites the cell files with only
  the good records.  The next runner pass then re-runs those samples,
  because idempotency keys only block samples whose record is still in
  the cell file.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path


def repair_model(run_dir: Path, model: str) -> int:
    """Move failed records for one model; return how many were moved."""
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out = run_dir / "invalid_attempts"
    out.mkdir(exist_ok=True)
    moved = 0
    suffix = model.replace("/", "_") + ".jsonl"
    for path in sorted(run_dir.glob("*_*.jsonl")):
        if not path.name.endswith(suffix) or path.parent.name == "invalid_attempts":
            continue
        keep, bad = [], []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            target = bad if (rec.get("succeeded") is False or rec.get("error")) else keep
            target.append(line)
        if bad:
            (out / f"{path.stem}.{stamp}.jsonl").write_text("\n".join(bad) + "\n")
            path.write_text("\n".join(keep) + ("\n" if keep else ""))
            moved += len(bad)
    return moved


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2:
        print("usage: repair_failed.py RUN_DIR MODEL", file=sys.stderr)
        return 2
    moved = repair_model(Path(argv[0]), argv[1])
    print(f"repair[{argv[1]}]: moved {moved} failed record(s)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
