# This module ports the FROZEN historical scoring rules for the six
# restored experiments, copied rule-for-rule from the validated final
# audit code (blinding_effect_magnitude_analysis.py, record_outcome) —
# not reinvented. Each rule turns one archived record's answer
# distribution into the one raw-scale number the frozen pipeline used:
# rating scales become the mass-weighted expected answer code, the
# disease framing outcome is the probability mass on the "safe" answers,
# and the sunk-cost and virus-injection questions use the same expected-
# code rule on their 0–20 and 1–10 bracket lists. Parity with every
# archived run6 record is tested, so a silent drift is impossible.
from __future__ import annotations

from string import ascii_uppercase

# Letters-per-scale and starting code, exactly as the frozen audit
# registered them (a rating scale's first letter codes as `offset`).
_LETTER_RULES: dict[str, tuple[int, int]] = {
    "less_is_more": (5, 1),
    "fire_extinguisher": (5, 1),
    "seatbelt": (6, 1),
    "sunk_cost": (21, 0),
    "wta_wtp": (10, 1),
}


def letter_mean(p_norm: dict[str, float | None], n_letters: int,
                offset: int = 1) -> float | None:
    """The mass-weighted expected answer code over the first n letters.

    Letter A codes as `offset`, B as offset+1, and so on. Letters never
    seen (or carrying no mass) contribute nothing; an all-empty
    distribution returns None — never a quiet zero.
    """
    letters = ascii_uppercase[:n_letters]
    total = sum(p_norm.get(letter) or 0 for letter in letters)
    if total <= 0:
        return None
    return sum(
        (i + offset) * (p_norm.get(letter) or 0)
        for i, letter in enumerate(letters)
    ) / total


def p_safe(p_norm: dict[str, float | None]) -> float | None:
    """The disease framing outcome: mass on the three "safe" answers.

    The frozen rule scores the 6-point favor scale by the share of mass
    on answers 1-3 (strongly/slightly favor program A, the safe option).
    """
    total = sum(p_norm.get(letter) or 0 for letter in "ABC")
    if total <= 0:
        return None
    return total


def record_outcome(record: dict, experiment: str) -> float | None:
    """The one raw-scale number one record contributes (frozen rules).

    Dispatches on the experiment name; returns None for an experiment
    outside the restored six (loud, so a caller can never score an
    unknown experiment quietly).
    """
    p_norm = record.get("p_norm") or {}
    if experiment in _LETTER_RULES:
        n_letters, offset = _LETTER_RULES[experiment]
        return letter_mean(p_norm, n_letters, offset)
    if experiment == "disease":
        return p_safe(p_norm)
    raise ValueError(f"experiment {experiment!r} is not one of the restored six")
