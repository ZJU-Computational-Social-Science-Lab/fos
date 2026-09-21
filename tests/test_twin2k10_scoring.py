# Locked tests for the twin2k10 study's scoring module (TASK-2139 RED
# phase; tests ONLY — no implementation lives yet, so every test here
# errors at collection until scripts/twin2k10/scoring.py exists).
#
# WHAT THIS FILE CHECKS, in plain words:
#   - Choice scoring is exactly twin2k6's: a letter folds only its four
#     spellings ("A", " A", "a", " a"), punctuation/prose look-alikes
#     never fold, entries under the 1-in-a-million floor are noise, a
#     missing letter stays None (never a faked 0.0), the branch mass is
#     the sum over found letters, and the 0.80 low-mass flag matches.
#   - Numeric answers (the K=20 temperature samples) are parsed out of
#     messy model prose: "about 15,000 feet" -> 15000, "$5,000,000" ->
#     5000000, "3.5" -> 3.5; text with no number parses to None.
#   - Multi-row answers are parsed from numbered lines, one value per
#     line; a blank line stays None instead of a made-up 0.
#
# All offline: pure functions over synthetic strings and top-k lists.
import math
import sys
from pathlib import Path

import pytest

# The launch scripts live in scripts/ and are not on pytest's pythonpath.
_SCRIPTS = str(Path(__file__).resolve().parent.parent / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from twin2k10 import config, scoring  # noqa: E402


def _entry(token: str, prob: float) -> dict:
    """Build one top-k entry {token, logprob} from a probability (helper)."""
    return {"token": token, "logprob": math.log(prob)}


def test_letter_folding_is_identical_to_twin2k6() -> None:
    """Every letter A-G folds exactly twin2k6's four spellings."""
    from twin2k6 import scoring as k6_scoring

    for letter in "ABCDEFG":
        assert scoring.fold_label_tokens(letter) \
            == k6_scoring.fold_label_tokens(letter)
    assert scoring.fold_label_tokens("A") == frozenset(
        {"A", " A", "a", " a"}
    )


def test_lookalike_tokens_never_fold_into_a_letter() -> None:
    """Punctuation glue and prose must never count as an answer letter."""
    for impostor in ("(A", "A.", "Answer", "=A", "A)"):
        for letter in "ABCDEFG":
            assert impostor not in scoring.fold_label_tokens(letter)


def test_floor_and_threshold_equal_twin2k6s_choice_scoring() -> None:
    """The visibility floor (1e-6) and the 0.80 low-mass flag are shared."""
    from twin2k6 import config as k6_config

    assert config.PROBABILITY_FLOOR == k6_config.PROBABILITY_FLOOR == 1e-6
    assert config.LOW_BRANCH_MASS_THRESHOLD \
        == k6_config.LOW_BRANCH_MASS_THRESHOLD == 0.80


def test_allais_scoring_keeps_missing_letters_none_and_sums_the_mass() -> None:
    """A two-letter choice: found letter scored, missing letter None."""
    top_k = [
        _entry("A", 0.55),
        _entry(" a", 0.20),      # second spelling folds into A
        _entry("(B", 0.10),      # impostor — must NOT fold into B
        _entry("Answer", 0.05),  # prose — never folds
        _entry("B", 1e-9),       # below the floor — B stays missing
    ]
    record = scoring.score_labels(top_k, "allais", decision_position=1,
                                  skipped_prefix=[], skipped_len=0)
    assert record["p_raw"]["A"] == pytest.approx(0.75)
    assert record["p_raw"]["B"] is None
    assert record["branch_mass"] == pytest.approx(0.75)
    assert record["p_norm"]["A"] == pytest.approx(1.0)
    assert record["p_norm"]["B"] is None
    assert record["low_branch_mass"] is False
    assert record["top_logprobs"] == top_k
    assert record["decision_position"] == 1


def test_low_branch_mass_flags_below_080() -> None:
    """A combined letter mass under 0.80 is flagged, at 0.80 it is not."""
    at_threshold = scoring.score_labels(
        [_entry("A", 0.80)], "allais", decision_position=0,
        skipped_prefix=[], skipped_len=0,
    )
    below = scoring.score_labels(
        [_entry("A", 0.79)], "allais", decision_position=0,
        skipped_prefix=[], skipped_len=0,
    )
    assert at_threshold["low_branch_mass"] is False
    assert below["low_branch_mass"] is True


def test_parse_numeric_reads_numbers_out_of_messy_prose() -> None:
    """The three pinned formats: comma thousands, currency, decimal."""
    assert scoring.parse_numeric("about 15,000 feet") == 15000
    assert scoring.parse_numeric("$5,000,000") == 5000000
    assert scoring.parse_numeric("3.5") == 3.5


def test_parse_numeric_returns_none_when_there_is_no_number() -> None:
    """Text without any number parses to None — never an exception, never 0."""
    assert scoring.parse_numeric("I cannot say") is None
    assert scoring.parse_numeric("") is None


def test_parse_multi_numeric_reads_one_value_per_numbered_line() -> None:
    """Ten numbered lines become ten numbers, in order."""
    text = "\n".join(f"{i}. {i * 10}" for i in range(1, 11))
    values = scoring.parse_multi_numeric(text)
    assert values == [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]


def test_parse_multi_numeric_keeps_blanks_as_none() -> None:
    """A blank numbered line stays None instead of a made-up 0."""
    text = "\n".join([
        "1. 80", "2. 65", "3.", "4. 90", "5.", "6. 55",
        "7. 70", "8. 45", "9. 85", "10. 60",
    ])
    values = scoring.parse_multi_numeric(text)
    assert len(values) == 10
    assert values[0] == 80 and values[1] == 65
    assert values[2] is None and values[4] is None
    assert values[9] == 60
