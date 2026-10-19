"""Repair the derived probe fields in the original engineering-pilot data.

What this file does: the first DeepSeek pilot run recorded every probe
answer with an empty choice and succeeded=False, even though the model's
answer was perfectly readable inside the raw text (bug A2 in
RESULT-2723).  This script re-reads each probe record's raw answer text,
rebuilds the missing fields (choice/answer, succeeded, recognition
coding, reason), and writes the fixed records to a NEW set of files in a
`repaired/` sub-folder.  The original files are never touched, so the
flawed run stays on record exactly as it happened.

Functions:
    repair_record(record): returns (fixed_record, changes_dict) for one
        probe record, rebuilding the derived fields from raw_content.
    repair_file(in_path, out_path): fixes every line of one probe file,
        writes the result to out_path, and returns a list of audit-trail
        entries (one per changed record).
    main(): finds all probe files in the pilot run directory, repairs
        them, prints the audit trail, and writes it to an audit file.

Run it as:  python scripts/sixgame/repair_probe_metadata.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from sixgame.probes import code_recognition  # noqa: E402
from sixgame.runner import parse_probe_answer  # noqa: E402

# Where the original (untouched) pilot run lives.
DATA_ROOT = Path("/home/justin/Documents/ZJU work/fos/results/sixgame")
PILOT_DIR = DATA_ROOT / "engineering_pilot"
REPAIRED_DIR = PILOT_DIR / "repaired"
AUDIT_PATH = REPAIRED_DIR / "repair_audit.jsonl"


def repair_record(record: dict) -> tuple[dict, dict]:
    """Rebuild one probe record's derived fields from its raw answer text.

    Returns the fixed record and a dictionary of the changes made, so
    the caller can show exactly what was repaired.
    """
    fixed = dict(record)
    answer, reason = parse_probe_answer(record.get("raw_content"))
    new_fields = {
        "choice": answer,
        "reason": reason,
        "succeeded": answer is not None,
        "recognition": code_recognition(record.get("raw_content")),
    }
    changes = {
        field: {"old": record.get(field), "new": value}
        for field, value in new_fields.items()
        if record.get(field) != value
    }
    fixed.update(new_fields)
    return fixed, changes


def record_key(record: dict) -> str:
    """A short human-readable name for one record (file + persona + draw)."""
    return (
        f"{record.get('game')}_{record.get('variant')}_{record.get('arm')}"
        f"/{record.get('persona_id')}#{record.get('draw_id')}"
    )


def repair_file(in_path: Path, out_path: Path) -> list[dict]:
    """Repair every record in one probe file and write the fixed copy.

    Returns one audit-trail entry per record whose fields changed.
    """
    entries: list[dict] = []
    lines = in_path.read_text(encoding="utf-8").splitlines()
    fixed_lines: list[str] = []
    for line in lines:
        if not line.strip():
            continue
        record = json.loads(line)
        fixed, changes = repair_record(record)
        if changes:
            entries.append(
                {
                    "file": in_path.name,
                    "record": record_key(record),
                    "changes": changes,
                }
            )
        fixed_lines.append(json.dumps(fixed, ensure_ascii=False))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        "\n".join(fixed_lines) + "\n", encoding="utf-8"
    )
    return entries


def main() -> int:
    """Repair all probe files in the pilot run and print the audit trail."""
    probe_files = sorted(PILOT_DIR.glob("probes_*.jsonl"))
    if not probe_files:
        print(f"No probe files found under {PILOT_DIR}", file=sys.stderr)
        return 1
    REPAIRED_DIR.mkdir(parents=True, exist_ok=True)
    all_entries: list[dict] = []
    for path in probe_files:
        out_path = REPAIRED_DIR / path.name
        entries = repair_file(path, out_path)
        all_entries.extend(entries)
        print(
            f"{path.name}: {len(entries)} record(s) repaired "
            f"-> {out_path.relative_to(DATA_ROOT)}"
        )
    with AUDIT_PATH.open("w", encoding="utf-8") as handle:
        for entry in all_entries:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(
        f"\nTotal records repaired: {len(all_entries)}; "
        f"audit trail written to {AUDIT_PATH}"
    )
    print("Original files were NOT modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
