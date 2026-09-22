# This file is the twin2k10 study's preflight examiner. Its core is ONE
# pure function, decide(records), that takes the preflight records in
# memory and returns a stop-or-proceed verdict — touching no files and no
# network. It says STOP exactly on technical failure criteria: a record
# whose top-logprobs came back empty (the known GGUF failure signature),
# a choice record where no answer letter could be read, or a digit item
# where no answer digit could be read (each digit item failing exactly
# like a choice record: empty top-k, or an all-None distribution). It
# never judges whether an answer is sensible, and sampling-era record
# fields are simply never inspected. The file also writes the preflight
# report and the skipped-models list the runner uses to leave broken
# models out of the full run.

import json
from datetime import datetime, timezone
from pathlib import Path

from twin2k10 import config


def _record_label(record: dict) -> str:
    """One record's short "who/what" tag for a stop reason line."""
    return f"{record.get('model')}/{record.get('experiment')}/{record.get('arm')}"


def _choice_reasons(record: dict) -> list[str]:
    """The stop reasons a record's choice-scoring fields give (may be []).

    Empty top-logprobs is the known GGUF failure signature. A p_raw where
    EVERY letter is None means no answer letter could be read at all — a
    single missing letter next to found ones is normal, not a failure.
    A digit-bearing record whose top_logprobs field is ABSENT (not empty)
    has no choice call of its own to judge — the digit items are judged
    on their own entries below.
    """
    reasons: list[str] = []
    has_digit_items = bool(record.get("digit_items"))
    if not record.get("top_logprobs") and not (
        has_digit_items and "top_logprobs" not in record
    ):
        reasons.append(
            f"{_record_label(record)}: empty top_logprobs at the decision "
            "position (GGUF failure signature)"
        )
    p_raw = record.get("p_raw")
    if p_raw and all(value is None for value in p_raw.values()):
        reasons.append(f"{_record_label(record)}: no answer letter readable in p_raw")
    return reasons


def _digit_reasons(record: dict) -> list[str]:
    """The stop reasons one record's digit items give (may be []).

    Every digit_items entry is judged exactly like a choice record: its
    top-logprobs must be non-empty (empty is the GGUF failure signature)
    and at least one label digit must be readable from its p_raw (an
    all-None distribution means no answer digit could be read at all — a
    single weak digit next to found ones is normal, not a failure).
    Sampling-era record fields are never looked at.
    """
    reasons: list[str] = []
    for item in record.get("digit_items") or []:
        where = _item_label(record, item)
        if "digit_mass" in item:
            reasons.extend(_digit_mass_reasons(item, where))
            continue
        if not item.get("top_logprobs"):
            reasons.append(
                f"{where}: empty top_logprobs at the decision position "
                "(GGUF failure signature)"
            )
        p_raw = item.get("p_raw")
        if p_raw and all(value is None for value in p_raw.values()):
            reasons.append(f"{where}: no answer digit readable in the item's p_raw")
    return reasons


def _digit_mass_reasons(item: dict, where: str) -> list[str]:
    """The stop reasons one scanned digit item gives (may be []).

    The multi-position scan stamps digit_mass (the best position's total
    digit probability) and decision_position (where it was found); the
    item passes only when that mass reaches the dominance gate. Below
    it, the model never wrote a dominant digit anywhere in the scan
    window — a technical failure the reason names with mass and position.
    Items without a digit_mass field (legacy shape) are never gated.
    """
    mass = item.get("digit_mass") or 0.0
    if mass >= config.DIGIT_MASS_PREFLIGHT_THRESHOLD:
        return []
    return [
        f"{where}: digit mass {mass:.2f} at best position "
        f"{item.get('decision_position')} is below the "
        f"{config.DIGIT_MASS_PREFLIGHT_THRESHOLD} dominance gate"
    ]


def _item_label(record: dict, item: dict) -> str:
    """One digit item's short "who/what" tag for a stop reason line."""
    row = item.get("row")
    at = f" row {row}" if row is not None else ""
    return f"{_record_label(record)}: digit item {item.get('qid')}{at}"


def decide(records: list[dict]) -> dict:
    """The pure stop-or-proceed verdict over a batch of preflight records.

    Returns {"stop": bool, "reasons": list[str]} — stop is True exactly
    when reasons is non-empty, and every reason names its record and what
    failed technically. Reads its arguments only: the same records always
    produce the same verdict, and calling it changes nothing.
    """
    reasons: list[str] = []
    for record in records:
        reasons.extend(_choice_reasons(record))
        reasons.extend(_digit_reasons(record))
    return {"stop": bool(reasons), "reasons": reasons}


def build_report(
    run_dir: Path, per_model: dict[str, list[dict]], verdict: dict[str, list[str]]
) -> str:
    """The PREFLIGHT_REPORT.md text: technical verdicts, no behaviour.

    per_model maps each model to its preflight records; verdict maps each
    STOP-flagged model to its reasons (a model absent from the verdict
    passed).
    """
    total = sum(len(records) for records in per_model.values())
    lines = [
        "# PREFLIGHT REPORT — twin2k10 (TECHNICAL CHECKS ONLY)",
        "",
        f"- run dir: `{run_dir}`",
        f"- finished: {datetime.now(timezone.utc).isoformat()}",
        f"- records: {total} (1 persona x 19 arms x 2 blind per model)",
        f"- models run: {len(per_model)}",
        "",
        "## Per-model verdicts",
        "",
    ]
    for model, records in per_model.items():
        reasons = verdict.get(model, [])
        lines.append(
            f"- {model}: {len(records)} records — "
            + ("PROCEED" if not reasons else "STOP")
        )
        for reason in reasons:
            lines.append(f"  - {reason}")
    lines += [
        "",
        "## Decision",
        "",
        (
            "- STOP — every model failed the technical preflight; the "
            "full run will not start."
        )
        if len(verdict) == len(per_model) and per_model
        else (
            "- PROCEED — full run starts without the STOP-flagged models "
            "listed in skipped_models.json."
        ),
        "- Preflight does NOT re-run its finished cells on resume; the "
        "full run skips every cell already durable in the leg files.",
        "",
    ]
    return "\n".join(lines)


def write_outputs(
    preflight_dir: Path, per_model: dict[str, list[dict]], verdict: dict[str, list[str]]
) -> dict:
    """Examine a finished preflight and write its report + skip list.

    Writes PREFLIGHT_REPORT.md always and skipped_models.json when any
    model is STOP-flagged, both into the run directory. Returns the
    verdict payload (also handy for logs). Records are read from the
    caller in memory — the leg files themselves were written by the
    runner's durable record loop.
    """
    preflight_dir = Path(preflight_dir)
    report = build_report(preflight_dir, per_model, verdict)
    (preflight_dir / "PREFLIGHT_REPORT.md").write_text(report, encoding="utf-8")
    if verdict:
        (preflight_dir / "skipped_models.json").write_text(
            json.dumps(
                {
                    "skipped_models": sorted(verdict),
                    "reason": "preflight technical failure (see PREFLIGHT_REPORT.md)",
                    "written": datetime.now(timezone.utc).isoformat(),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return {"verdict": verdict}
