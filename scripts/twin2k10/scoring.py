# This file turns model answers into numbers, three ways. (1) Choice
# scoring is exactly twin2k6's: a letter answer folds only its four
# spellings ("A", " A", "a", " a"), punctuation/prose look-alikes never
# fold, entries under the one-in-a-million floor are sampler noise, a
# missing letter stays explicitly None (never a faked 0.0), the found
# letters' raw probabilities sum into the branch mass, and a mass under
# 0.80 is flagged. (2) parse_numeric pulls the number out of messy model
# prose ("about 15,000 feet" -> 15000, "$5,000,000" -> 5000000) and
# returns None — never an exception, never 0 — when there is no number.
# (3) parse_multi_numeric reads a numbered list ("1. 80", "2. 65", ...)
# into one value per line, keeping blank lines as None.

import math
import re

from logprob_scoring import _logprob_from_entry, _token_from_entry

from twin2k10 import config, experiments

# One number with optional thousands commas and optional decimals. The
# match is searched anywhere in the text, so "about 15,000 feet" works.
NUMBER_PATTERN = re.compile(r"\d[\d,]*(?:\.\d+)?")


def fold_label_tokens(letter: str) -> frozenset[str]:
    """The exact token spellings that count as one answer letter.

    Exactly four forms: bare, space-glued, lowercase, and space-glued
    lowercase ("A", " A", "a", " a"). Nothing else — not "A.", "(A",
    "Answer" — ever folds into a letter.
    """
    return frozenset({
        letter,
        f" {letter}",
        letter.lower(),
        f" {letter.lower()}",
    })


def _stripped_form_to_letter(letters) -> dict[str, str]:
    """Map each stripped fold spelling to its canonical uppercase letter.

    The fold forms compared after stripping are the bare letter and its
    lowercase twin, so the lookup has one entry per letter per case.
    """
    lookup: dict[str, str] = {}
    for letter in letters:
        lookup[letter] = letter
        lookup[letter.lower()] = letter
    return lookup


def _raw_letter_probabilities(top_logprobs, lookup: dict[str, str]
                              ) -> dict[str, float]:
    """Sum the raw probabilities each letter collects from one top-k list.

    Walks the entries with the proven R1 helpers (token text and logprob
    across the known key names), skips entries under the visibility floor,
    strips each token and adds its probability to the letter it folds to.
    Letters never seen stay absent from the returned dict.
    """
    raw: dict[str, float] = {}
    for entry in top_logprobs or []:
        token = _token_from_entry(entry)
        if token is None:
            continue
        logprob = _logprob_from_entry(entry, token)
        if logprob is None:
            continue
        probability = math.exp(logprob)
        if probability < config.PROBABILITY_FLOOR:
            continue  # numerically-zero top-k noise, never an answer form
        letter = lookup.get(token.strip())
        if letter is not None:
            raw[letter] = raw.get(letter, 0.0) + probability
    return raw


def _normalized(p_raw: dict[str, float | None], branch_mass: float, letters
                ) -> dict[str, float | None]:
    """Divide each found letter's raw probability by the branch mass.

    With zero mass (no letter appeared at all) every normalized probability
    stays None — there is no distribution to normalize.
    """
    if branch_mass == 0.0:
        return {letter: None for letter in letters}
    return {
        letter: (value / branch_mass if value is not None else None)
        for letter, value in p_raw.items()
    }


def score_labels(
    top_logprobs: list[dict],
    experiment: str,
    decision_position: int | None = None,
    skipped_prefix: list | None = None,
    skipped_len: int | None = None,
) -> dict:
    """Score one decision-position top-logprob list for one experiment.

    Returns the record's choice-scoring fields: p_raw / p_norm (every
    answer letter of the experiment, None when the letter never appeared),
    branch_mass (the found letters' summed raw probability), the
    low_branch_mass flag (mass strictly below 0.80), and the untouched
    audit fields (the full top_logprobs array, decision_position,
    skipped_prefix, skipped_len). Raises KeyError for an unknown
    experiment and ValueError when the experiment has no choice question.
    """
    letters = experiments.label_letters(experiment)
    lookup = _stripped_form_to_letter(letters)
    raw = _raw_letter_probabilities(top_logprobs, lookup)
    p_raw: dict[str, float | None] = {letter: raw.get(letter)
                                      for letter in letters}
    branch_mass = float(sum(raw.values()))
    return {
        "p_raw": p_raw,
        "p_norm": _normalized(p_raw, branch_mass, letters),
        "branch_mass": branch_mass,
        "low_branch_mass": branch_mass < config.LOW_BRANCH_MASS_THRESHOLD,
        "top_logprobs": top_logprobs,
        "decision_position": decision_position,
        "skipped_prefix": skipped_prefix,
        "skipped_len": skipped_len,
    }


def parse_numeric(text: str | None) -> float | int | None:
    """The first number in a model's prose, or None when there is none.

    Understands thousands commas ("15,000"), currency ("$5,000,000") and
    decimals ("3.5"); whole numbers come back as int. Unparseable text
    ("I cannot say", "") returns None — never an exception, never 0, so
    a missing number is always distinguishable from the answer zero.
    """
    if not text:
        return None
    match = NUMBER_PATTERN.search(text.replace("$", ""))
    if match is None:
        return None
    value = float(match.group().replace(",", ""))
    return int(value) if value.is_integer() else value


def parse_multi_numeric(text: str | None) -> list[float | int | None]:
    """One value per distinct row number of a multi-row answer, in order.

    Lines like "1. 80" or "2) 65" are read in line order; a line with no
    number after it ("3.") stays None instead of a made-up 0. The FIRST
    value seen for a row number wins and later repeats of that row number
    are ignored — a model that answers "1. 42 / 2. 42 / 3. 42" and then
    chats about its answer with another numbered list must not gain extra
    result slots. Lines without a leading row number are never parsed.
    """
    first_by_row: dict[int, float | int | None] = {}
    for line in (text or "").splitlines():
        match = re.match(r"^\s*(\d+)\s*[.)]\s*(.*)$", line)
        if match is None:
            continue
        row = int(match.group(1))
        if row in first_by_row:
            continue
        first_by_row[row] = parse_numeric(match.group(2))
    return [first_by_row[row] for row in sorted(first_by_row)]
