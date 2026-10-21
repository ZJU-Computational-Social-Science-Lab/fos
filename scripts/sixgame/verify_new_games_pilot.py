"""Verify the completed new-games pilot run and write a checksum manifest.

What this file does, in plain language:

- ``load_records`` reads every decisions JSONL in the run folder.
- ``check_cells`` makes sure each of the 60 cells (10 conditions x 2
  arms x 3 models) has exactly 10 records.
- ``check_duplicates`` makes sure no idempotency key appears twice.
- ``check_parse`` counts how many records parsed into a legal answer.
- ``check_call_fields`` makes sure temperature was 1.0, every call
  finished normally (finish_reason "stop"), and counts truncations.
- ``check_fingerprints`` matches each record to its captured request
  body (via the prompt hash) and checks that persona-arm prompts
  contain the full persona biography while no-persona prompts do not.
- ``check_metadata`` makes sure model and route are filled in.
- ``write_manifest`` writes a sha256 list of the 60 decision files.
- ``main`` runs all checks and writes VERIFICATION.md next to the data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_DATA_DIR = Path.home() / "experiment-data/fos/sixgame/new_games_pilot"
DEFAULT_PERSONAS_DIR = Path.home() / "work/fos-data/personas"
MANIFEST_NAME = "MANIFEST.sha256"
REPORT_NAME = "VERIFICATION.md"
EXPECTED_PER_CELL = 10
EXPECTED_CELLS = 60


def prompt_hash(prompt: str) -> str:
    """The short hash the runner logs on every record (first 16 hex of sha256)."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]


def load_records(data_dir: Path) -> list[dict[str, Any]]:
    """Read every decision record from the run folder's JSONL files."""
    records: list[dict[str, Any]] = []
    for path in sorted(data_dir.glob("decisions_*.jsonl")):
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    return records


def load_captured_prompts(data_dir: Path) -> list[str]:
    """The user-message text of every captured request body."""
    path = data_dir / "captured_requests.jsonl"
    prompts: list[str] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                body = json.loads(line)
                prompts.append(body["messages"][-1]["content"])
    return prompts


def cell_key(record: dict[str, Any]) -> tuple[str, str, str, str]:
    """Which cell a record belongs to: (game, variant, arm, model)."""
    return (
        record["game"],
        record["variant"],
        record["arm"],
        record["model"],
    )


def check_cells(records: list[dict[str, Any]]) -> tuple[int, list[str]]:
    """Count records per cell; return (cell count, problems)."""
    counts = Counter(cell_key(r) for r in records)
    problems = [
        f"cell {cell} has {count} records (expected {EXPECTED_PER_CELL})"
        for cell, count in sorted(counts.items())
        if count != EXPECTED_PER_CELL
    ]
    return len(counts), problems


def check_duplicates(records: list[dict[str, Any]]) -> list[str]:
    """No idempotency key may appear more than once."""
    counts = Counter(r["idempotency_key"] for r in records)
    return [
        f"idempotency key {key} appears {count} times"
        for key, count in counts.items()
        if count > 1
    ]


def check_parse(records: list[dict[str, Any]]) -> tuple[int, int]:
    """How many records succeeded and hold a legal answer."""
    ok = sum(
        1 for r in records if r.get("succeeded") and r.get("choice") is not None
    )
    return ok, len(records)


def check_call_fields(records: list[dict[str, Any]]) -> tuple[list[str], int]:
    """Temperature must be 1.0 and finish_reason "stop"; count truncations."""
    problems = [
        f"record {r['idempotency_key'][:8]} has temperature {r.get('temperature')}"
        for r in records
        if r.get("temperature") != 1.0
    ]
    problems += [
        f"record {r['idempotency_key'][:8]} has finish_reason {r.get('finish_reason')!r}"
        for r in records
        if r.get("finish_reason") != "stop"
    ]
    truncated = sum(1 for r in records if r.get("truncated"))
    return problems, truncated


def check_fingerprints(
    records: list[dict[str, Any]],
    captured_prompts: list[str],
    personas_dir: Path,
) -> list[str]:
    """Persona-arm prompts must contain the biography; no-persona must not.

    Records are matched to captured request bodies through the logged
    prompt hash (the same 16-hex sha256 prefix the runner writes).
    """
    prompts_by_hash: dict[str, list[str]] = {}
    for prompt in captured_prompts:
        prompts_by_hash.setdefault(prompt_hash(prompt), []).append(prompt)
    problems: list[str] = []
    checked = 0
    for record in records:
        candidates = prompts_by_hash.get(record["prompt_hash"], [])
        if not candidates:
            problems.append(
                f"no captured request matches prompt hash {record['prompt_hash']}"
            )
            continue
        name = record["persona_id"]
        if record["arm"] == "persona":
            bio_file = personas_dir / f"{name}.txt"
            if not bio_file.exists():
                problems.append(f"persona file missing: {bio_file}")
                continue
            bio = bio_file.read_text(encoding="utf-8")
            matched = any(bio in prompt for prompt in candidates)
        else:
            # no-persona arm: name-only placebo present, biography absent
            bio_file = personas_dir / f"{name}.txt"
            bio = (
                bio_file.read_text(encoding="utf-8")
                if bio_file.exists()
                else None
            )
            matched = any(
                name in prompt and (bio is None or bio not in prompt)
                for prompt in candidates
            )
        if not matched:
            problems.append(
                f"{record['game']}/{record['variant']}/{record['arm']} "
                f"{record['persona_id']}#{record['draw_id']}: fingerprint check failed"
            )
        checked += 1
    print(f"  fingerprint checks run: {checked}")
    return problems


def check_metadata(records: list[dict[str, Any]]) -> list[str]:
    """Model and route must be filled in on every record."""
    return [
        f"record {r['idempotency_key'][:8]} missing model/route"
        for r in records
        if not r.get("model") or not r.get("route")
    ]


def write_manifest(data_dir: Path) -> Path:
    """Write a sha256 manifest of the 60 decision files next to them."""
    lines = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
        for path in sorted(data_dir.glob("decisions_*.jsonl"))
    ]
    manifest_path = data_dir / MANIFEST_NAME
    manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest_path


def verify(data_dir: Path, personas_dir: Path) -> dict[str, Any]:
    """Run every check and return the summary used in VERIFICATION.md."""
    records = load_records(data_dir)
    captured = load_captured_prompts(data_dir)
    n_cells, cell_problems = check_cells(records)
    dup_problems = check_duplicates(records)
    parsed, total = check_parse(records)
    field_problems, truncated = check_call_fields(records)
    fingerprint_problems = check_fingerprints(records, captured, personas_dir)
    metadata_problems = check_metadata(records)
    return {
        "records": total,
        "cells": n_cells,
        "cell_problems": cell_problems,
        "duplicates": dup_problems,
        "parsed": parsed,
        "field_problems": field_problems,
        "truncated": truncated,
        "fingerprint_problems": fingerprint_problems,
        "metadata_problems": metadata_problems,
    }


def format_report(summary: dict[str, Any]) -> str:
    """Turn the verification summary into the VERIFICATION.md text."""
    all_problems = (
        summary["cell_problems"]
        + summary["duplicates"]
        + summary["field_problems"]
        + summary["fingerprint_problems"]
        + summary["metadata_problems"]
    )
    parse_rate = summary["parsed"] / summary["records"] * 100
    lines = [
        "# VERIFICATION — new_games_pilot (offline, no model calls)",
        "",
        f"- decision records: **{summary['records']}** "
        f"(expected {EXPECTED_CELLS * EXPECTED_PER_CELL})",
        f"- cells: **{summary['cells']}** (expected {EXPECTED_CELLS}), "
        f"all at {EXPECTED_PER_CELL} records: "
        f"{'YES' if not summary['cell_problems'] else 'NO'}",
        f"- duplicate idempotency keys: **{len(summary['duplicates'])}**",
        f"- parse success: **{summary['parsed']}/{summary['records']}** "
        f"({parse_rate:.1f}%)",
        "- temperature 1.0 on all: "
        f"{'YES' if not any('temperature' in p for p in summary['field_problems']) else 'NO'}",
        "- finish_reason=stop on all: "
        f"{'YES' if not any('finish_reason' in p for p in summary['field_problems']) else 'NO'}",
        f"- truncated records: **{summary['truncated']}**",
        "- persona biography fingerprints in persona-arm prompts "
        "(and absent in no-persona): "
        f"{'PASS' if not summary['fingerprint_problems'] else 'FAIL'}",
        "- model/route metadata populated on all: "
        f"{'YES' if not summary['metadata_problems'] else 'NO'}",
        "",
        f"**Result: {'ALL CHECKS PASS' if not all_problems else 'PROBLEMS FOUND'}**",
        "",
    ]
    if all_problems:
        lines += ["## Problems", ""] + [f"- {p}" for p in all_problems] + [""]
    return "\n".join(lines)


def main() -> None:
    """Command line: verify a run folder and write VERIFICATION.md + manifest."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--personas-dir", type=Path, default=DEFAULT_PERSONAS_DIR)
    args = parser.parse_args()
    summary = verify(args.data_dir, args.personas_dir)
    report_path = args.data_dir / REPORT_NAME
    report_path.write_text(format_report(summary), encoding="utf-8")
    manifest_path = write_manifest(args.data_dir)
    print(format_report(summary))
    print(f"wrote {report_path}")
    print(f"wrote {manifest_path} ({len(manifest_path.read_text().splitlines())} files)")


if __name__ == "__main__":
    main()
