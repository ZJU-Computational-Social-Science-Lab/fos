# Locked tests for the twin2k10 study's preflight examiner (TASK-2139 RED
# phase; tests ONLY — no implementation lives yet, so every test here
# errors at collection until scripts/twin2k10/preflight.py exists).
#
# WHAT THIS FILE CHECKS, in plain words:
#   - The stop-or-proceed decision is one PURE function: it takes the
#     preflight records in memory and returns a verdict, touching no
#     files and no network.
#   - It says STOP exactly on the three technical failure criteria: a
#     record whose top-logprobs came back empty (the known GGUF failure
#     signature), a choice record where no answer letter could be read
#     (missing labels), and a numeric smoke record where a sample could
#     not be parsed into a number.
#   - Clean records mean PROCEED, and every stop verdict says why.
#
# All offline: pure functions over synthetic record dicts; no files.
import math
import sys
from pathlib import Path

import pytest

# The launch scripts live in scripts/ and are not on pytest's pythonpath.
_SCRIPTS = str(Path(__file__).resolve().parent.parent / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from twin2k10 import preflight, scoring  # noqa: E402


def _entry(token: str, prob: float) -> dict:
    """Build one top-k entry {token, logprob} from a probability (helper)."""
    return {"token": token, "logprob": math.log(prob)}


def _good_choice_record() -> dict:
    """A healthy choice preflight record: letters found, mass solid."""
    top_k = [_entry("A", 0.7), _entry("B", 0.2)]
    scored = scoring.score_labels(top_k, "allais", decision_position=1,
                                  skipped_prefix=[], skipped_len=0)
    return {"experiment": "allais", "arm": "form1", "model": "m",
            "persona_id": 0, "blind": "blinded",
            "top_logprobs": top_k, **scored}


def _good_numeric_record() -> dict:
    """A healthy numeric smoke record: every sample parses to a number."""
    return {"experiment": "base_rate", "arm": "30_engineers", "model": "m",
            "persona_id": 0, "blind": "blinded",
            "top_logprobs": [_entry("1", 0.5)],
            "numeric_samples": ["30", "about 35 percent", "40"]}


def test_clean_records_mean_proceed() -> None:
    """Healthy choice + numeric records produce stop=False."""
    verdict = preflight.decide(
        [_good_choice_record(), _good_numeric_record()]
    )
    assert verdict["stop"] is False
    assert verdict["reasons"] == []


def test_empty_top_logprobs_stops_the_model() -> None:
    """The known GGUF signature: no top-logprobs at the decision position."""
    broken = _good_choice_record()
    broken["top_logprobs"] = []
    verdict = preflight.decide([_good_choice_record(), broken])
    assert verdict["stop"] is True
    assert verdict["reasons"], "a stop verdict must say why"


def test_missing_labels_stop_the_run() -> None:
    """A choice record where no letter could be read is a failure."""
    letterless = _good_choice_record()
    letterless["p_raw"] = {"A": None, "B": None}
    verdict = preflight.decide([letterless])
    assert verdict["stop"] is True
    assert verdict["reasons"]


def test_numeric_sample_that_fails_to_parse_stops_the_run() -> None:
    """A numeric smoke sample with no parseable number is a failure."""
    unparseable = _good_numeric_record()
    unparseable["numeric_samples"] = ["30", "I refuse to answer"]
    assert scoring.parse_numeric("I refuse to answer") is None
    verdict = preflight.decide([unparseable])
    assert verdict["stop"] is True
    assert verdict["reasons"]


def test_the_decision_is_pure_and_stable() -> None:
    """Same records in, same verdict out; calling it changes nothing."""
    records = [_good_choice_record(), _good_numeric_record()]
    first = preflight.decide([dict(r) for r in records])
    second = preflight.decide([dict(r) for r in records])
    assert first == second
    assert preflight.decide([])["stop"] is False


# --------------------------------------------------------------------------
# TASK-2150 RED tests — review blocker B1 (RESULT-2146): a multi-row
# sample whose rows ALL parse but whose row count falls short of the
# record's expected_rows is the truncation signature (e.g. a 32-token
# window cutting a 10-row answer down to 8 rows) — the preflight must
# STOP on it and name the row deficit, and must still PROCEED on a full
# count.
# --------------------------------------------------------------------------


def _multi_record(expected_rows: int, filled_rows: int) -> dict:
    """A multi-row record with `filled_rows` of `expected_rows` parseable."""
    values = list(range(1, filled_rows + 1))
    return {"experiment": "false_consensus", "arm": "all", "model": "m",
            "persona_id": 0, "blind": "blinded",
            "top_logprobs": [_entry("1", 0.5)],
            "expected_rows": expected_rows,
            "multi_numeric_values": [values]}


def test_truncated_multi_sample_stops_even_when_every_row_parses() -> None:
    """8 parseable rows of an expected 10 is the truncation signature."""
    verdict = preflight.decide([_multi_record(expected_rows=10,
                                              filled_rows=8)])
    assert verdict["stop"] is True, (
        "a multi sample with 8 of 10 rows — every row parseable — must "
        "stop the run as truncated, not pass the preflight"
    )
    reasons = " ".join(verdict["reasons"])
    assert "8" in reasons and "10" in reasons, (
        f"the stop reason must name the row deficit (8 of 10): {reasons}"
    )


def test_full_ten_of_ten_multi_sample_proceeds() -> None:
    """A complete 10/10 multi sample is healthy — no truncation stop."""
    verdict = preflight.decide([_multi_record(expected_rows=10,
                                              filled_rows=10)])
    assert verdict["stop"] is False
    assert verdict["reasons"] == []
