# This file is the twin2k10 study's preflight examiner. Its core is ONE
# pure function, decide(records), that takes the preflight records in
# memory and returns a stop-or-proceed verdict — touching no files and no
# network. It says STOP exactly on technical failure criteria: a record
# whose top-logprobs came back empty (the known GGUF failure signature), a
# choice record where no answer letter could be read, a numeric sample
# that cannot be parsed into a number, a multi-row sample with an
# unparseable row, or a multi-row sample TRUNCATED short of its item's
# row count even when every row it has parses (8 of 10 rows is a cut-off
# answer, not a model choice). It never judges whether an answer is
# sensible. The
# file also writes the preflight report and the skipped-models list the
# runner uses to leave broken models out of the full run.

import json
from datetime import datetime, timezone
from pathlib import Path

from twin2k10 import scoring


def _record_label(record: dict) -> str:
    """One record's short "who/what" tag for a stop reason line."""
    return (
        f"{record.get('model')}/{record.get('experiment')}/"
        f"{record.get('arm')}"
    )


def _choice_reasons(record: dict) -> list[str]:
    """The stop reasons a record's choice-scoring fields give (may be []).

    Empty top-logprobs is the known GGUF failure signature. A p_raw where
    EVERY letter is None means no answer letter could be read at all — a
    single missing letter next to found ones is normal, not a failure.
    """
    reasons: list[str] = []
    if not record.get("top_logprobs"):
        reasons.append(
            f"{_record_label(record)}: empty top_logprobs at the decision "
            "position (GGUF failure signature)"
        )
    p_raw = record.get("p_raw")
    if p_raw and all(value is None for value in p_raw.values()):
        reasons.append(
            f"{_record_label(record)}: no answer letter readable in p_raw"
        )
    return reasons


def _multi_row_reasons(record: dict) -> list[str]:
    """The stop reasons one record's multi-row samples give (may be []).

    multi_numeric_values holds one parsed value per row per K sample. A
    sample fails when a row is missing or unparseable — and it fails as
    TRUNCATED when every surviving row parses but the row count falls
    short of the record's expected_rows (the signature of a generation
    window cutting the answer short, e.g. 8 of 10 rows). The first
    failing sample decides the reason; the rest would say the same.
    """
    expected = record.get("expected_rows")
    for sample in (record.get("multi_numeric_values") or []):
        if not sample or any(value is None for value in sample):
            return [
                f"{_record_label(record)}: a multi-row sample has a "
                f"missing or unparseable row: {sample!r}"
            ]
        if expected is not None and len(sample) < expected:
            return [
                f"{_record_label(record)}: multi-row sample truncated — "
                f"{len(sample)} of {expected} rows, every row parseable "
                f"(deficit {expected - len(sample)}): {sample!r}"
            ]
    return []


def _numeric_reasons(record: dict) -> list[str]:
    """The stop reasons a record's numeric samples give (may be []).

    numeric_samples holds one raw sample string per K sample; every one
    must parse to a number. multi_numeric_values is checked separately
    (missing/unparseable rows, and truncation against expected_rows).
    """
    reasons: list[str] = []
    bad = [sample for sample in (record.get("numeric_samples") or [])
           if scoring.parse_numeric(sample) is None]
    if bad:
        reasons.append(
            f"{_record_label(record)}: {len(bad)} numeric sample(s) "
            f"unparseable, e.g. {bad[0]!r}"
        )
    reasons.extend(_multi_row_reasons(record))
    return reasons


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
        reasons.extend(_numeric_reasons(record))
    return {"stop": bool(reasons), "reasons": reasons}


def build_report(run_dir: Path, per_model: dict[str, list[dict]],
                 verdict: dict[str, list[str]]) -> str:
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
        lines.append(f"- {model}: {len(records)} records — "
                     + ("PROCEED" if not reasons else "STOP"))
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


def write_outputs(preflight_dir: Path, per_model: dict[str, list[dict]],
                  verdict: dict[str, list[str]]) -> dict:
    """Examine a finished preflight and write its report + skip list.

    Writes PREFLIGHT_REPORT.md always and skipped_models.json when any
    model is STOP-flagged, both into the run directory. Returns the
    verdict payload (also handy for logs). Records are read from the
    caller in memory — the leg files themselves were written by the
    runner's durable record loop.
    """
    preflight_dir = Path(preflight_dir)
    report = build_report(preflight_dir, per_model, verdict)
    (preflight_dir / "PREFLIGHT_REPORT.md").write_text(report,
                                                       encoding="utf-8")
    if verdict:
        (preflight_dir / "skipped_models.json").write_text(
            json.dumps({"skipped_models": sorted(verdict),
                        "reason": "preflight technical failure "
                                  "(see PREFLIGHT_REPORT.md)",
                        "written": datetime.now(timezone.utc).isoformat()},
                       indent=2) + "\n",
            encoding="utf-8",
        )
    return {"verdict": verdict}
