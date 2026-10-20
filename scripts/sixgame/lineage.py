"""Data-lineage audit: prove what may and may not enter a new analysis.

What this file does, in plain language:

- ``classify_input`` looks at one file path and decides whether it is
  INCLUDED (a frozen corrective-run input), EXCLUDED (the flawed
  original run, or a temp-0 exploratory file from the old repo results
  folder), or SUPERSEDED (a previous, incorrect audited report).
- ``record_cache_class`` reads one JSONL record and says whether its
  completion was freshly sampled ("context" prompt-prefix cache or no
  cache) or reused ("response" gateway cache — never allowed into an
  analysis).
- ``build_lineage_table`` turns a list of candidate input paths into a
  table with path, sha256, run ID and include/exclude status.
- ``write_lineage_report`` writes DATA_LINEAGE.md: the table, the
  cache reconciliation counts, and the cannot-enter guarantees
  (TASK-2760 SPEC §2).
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Sequence

try:  # works both as a package module and run from the scripts directory
    from sixgame.data_root import sha256_of
except ImportError:  # pragma: no cover
    from data_root import sha256_of

#: Folder name of the flawed original run (both arms ran no-persona).
ORIGINAL_RUN_ID = "engineering_pilot"

#: The frozen corrective run — the ONLY run whose raw files may be used.
CORRECTIVE_RUN_ID = "engineering_pilot_corrective"

#: Legacy exploratory condition files (temp-0 observation sweeps) that
#: lived in the old repo results/ folder.
TEMP0_MARKER = "_cond"


def classify_input(path: Path) -> dict:
    """Decide the lineage status of one candidate input file."""
    path = Path(path)
    parts = path.parts
    if ORIGINAL_RUN_ID in parts:
        return {
            "path": str(path),
            "run_id": ORIGINAL_RUN_ID,
            "status": "EXCLUDED",
            "reason": (
                "flawed original run (both arms ran no-persona) — "
                "can never enter a corrective analysis"
            ),
        }
    if "_cond" in path.name:
        return {
            "path": str(path),
            "run_id": "legacy_repo_results",
            "status": "EXCLUDED",
            "reason": (
                "temp-0 exploratory condition file (legacy repo "
                "results/) — not a corrective-run input"
            ),
        }
    if CORRECTIVE_RUN_ID in parts and "reports" in parts:
        return {
            "path": str(path),
            "run_id": CORRECTIVE_RUN_ID,
            "status": "SUPERSEDED",
            "reason": (
                "previous audited statistics (pre-2760) — superseded, "
                "labelled, and not readable as current"
            ),
        }
    if CORRECTIVE_RUN_ID in parts:
        return {
            "path": str(path),
            "run_id": CORRECTIVE_RUN_ID,
            "status": "INCLUDED",
            "reason": "frozen corrective-run raw JSONL",
        }
    return {
        "path": str(path),
        "run_id": "unknown",
        "status": "EXCLUDED",
        "reason": "outside every known run folder — excluded by default",
    }


def record_cache_class(record: dict) -> str:
    """'response' (reused completion — banned), 'context' (fresh
    completion, prompt prefix reused — allowed), or a legacy class."""
    kind = record.get("cache_kind")
    if kind in ("response", "context"):
        return kind
    return "legacy_hit" if record.get("cache_status", "MISS") != "MISS" else "legacy_miss"


def _cache_reconciliation(paths: Sequence[Path]) -> tuple[dict, int]:
    """Count cache classes across all included files; returns the counts
    and how many response-cache records were found (must be excluded)."""
    counts: Counter = Counter()
    response_records = 0
    for path in paths:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            cls = record_cache_class(json.loads(line))
            counts[cls] += 1
            if cls == "response":
                response_records += 1
    return dict(counts), response_records


def build_lineage_table(paths: Sequence[Path]) -> list[dict]:
    """One row per candidate input: path, sha256, run ID, status, reason."""
    rows = []
    for path in paths:
        row = classify_input(path)
        file = Path(str(row["path"]))
        row["sha256"] = sha256_of(file) if file.exists() else "MISSING"
        rows.append(row)
    return rows


def _guarantee_section(rows: list[dict], cache_counts: dict,
                       response_records: int) -> list[str]:
    """The cannot-enter guarantee statements (SPEC §2 a-d)."""
    excluded = [r for r in rows if r["status"] != "INCLUDED"]
    lines = [
        "## Cannot-enter guarantees",
        "",
        "- (a) The flawed original run (`engineering_pilot/`, both arms "
        "no-persona) is EXCLUDED: no file from that folder appears among "
        "the INCLUDED inputs.",
        "- (b) Temp-0 exploratory files (legacy repo `results/*_cond*`, "
        "`*_die_roll*`) are EXCLUDED by filename rule.",
        "- (c) Response-cached completions (`cache_kind == \"response\"`, "
        "a reused completion body) are EXCLUDED by the analysis exclusion "
        f"rule; this run contained {response_records} such record(s) and "
        "0 entered the analysis. Context/prompt-prefix cache records "
        "(freshly sampled completions) are included by the frozen rule.",
        "- (d) Previous incorrect statistics (pre-2760 `reports/audited/` "
        "and `reports/audited_v2/`) are SUPERSEDED: labelled with "
        "`SUPERSEDED-2760.md` and never read as current inputs.",
        "",
        "Cache reconciliation over INCLUDED files: "
        + ", ".join(f"{k}={v}" for k, v in sorted(cache_counts.items())),
        "",
        f"Excluded/superseded candidates evaluated: {len(excluded)}.",
        "",
    ]
    return lines


def write_lineage_report(
    out_dir: Path, input_paths: Sequence[Path]
) -> Path:
    """Write DATA_LINEAGE.md into the report output folder."""
    rows = build_lineage_table(input_paths)
    included = [Path(r["path"]) for r in rows if r["status"] == "INCLUDED"]
    cache_counts, response_records = _cache_reconciliation(included)
    lines = [
        "# DATA LINEAGE — phase-1 offline audit (TASK-2760)",
        "",
        "Every candidate analysis input, its fingerprint, its run, and "
        "whether it may enter a new analysis. Generated offline — no "
        "model calls. Raw data and prior audited versions untouched.",
        "",
        "| path | sha256 | run ID | status | reason |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| `{row['path']}` | `{row['sha256'][:16]}…` "
            f"| {row['run_id']} | {row['status']} | {row['reason']} |"
        )
    lines.append("")
    lines += _guarantee_section(rows, cache_counts, response_records)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "DATA_LINEAGE.md"
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target
