"""Game definitions for the three-game experiment.

This file describes the games we study as plain data, so anyone can read
exactly what the model is asked and what the rules are:

- ``ELEVEN_TWENTY`` builds prompts for the 11-20 money-request game: the
  three published treatments (basic, costless, cycle), the pure range
  shifts (21-30 ... 51-60), and the inverted-bonus game.  It also exposes
  the rule-implied mapping R(T): for a range shift a choice x becomes
  x + 10; for the inverted bonus a choice x becomes 31 - x (level-k
  answers correspond exactly, e.g. 19 <-> 12).
- ``DieRoll`` builds prompts for the die-roll honesty task.  All variants
  share one base prompt and differ in exactly one respect: private vs
  public reporting (public = the committed report will be announced; the
  roll itself is never revealed), a neutral cover-story rewording
  (Tier A), or stakes multiplied by ten (Tier B).
- ``MatrixGame`` builds prompts for the 3x3 PMS Joker matrix games 1 and
  4 (payoff matrices verbatim from HUMAN_BENCHMARKS section 3.1) plus the
  relabeled variant using the frozen permutation pi: (A1, A2, J) mapped
  to (J, A1, A2), applied to both the presentation and the answer
  options.  Each draw is assigned a role (Row or Column).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


# ------------------------------------------------------------------ #
# Shared prompt scaffolding (5 sections, mirrors the existing harness)
# ------------------------------------------------------------------ #


def persona_section(username: str, persona_text: str | None) -> str:
    """Section 1: full persona text (persona arm) or name only (no-persona)."""
    if persona_text is None:
        return f"=== EMBODY THIS PERSON ===\nYou are {username}."
    return f"=== EMBODY THIS PERSON ===\n{persona_text}"


def build_five_section_prompt(
    username: str,
    persona_text: str | None,
    scenario: str,
    action_line: str,
    json_fields: str,
) -> str:
    """Assemble the five prompt sections into one full prompt string.

    persona_text None means the no-persona (name-only placebo) arm.
    """
    return (
        f"{persona_section(username, persona_text)}\n"
        "=== SECTION 2: SCENARIO ===\n\n"
        f"## Scenario\n{scenario}\n"
        "=== SECTION 3: AVAILABLE ACTIONS ===\n\n"
        f"## Your Action\n{action_line}\n"
        "=== SECTION 4: CONTEXT ===\n\n"
        "## Context\nThis is the first round - no previous context.\n"
        "=== SECTION 5: JSON OUTPUT REQUIREMENT ===\n"
        f"## Your Response\n{json_fields}\n\n"
        "No markdown. No explanation. Only JSON."
    )


# ------------------------------------------------------------------ #
# Game 1: the 11-20 money-request game (all treatments and rungs)
# ------------------------------------------------------------------ #

# Rule texts per HUMAN_BENCHMARKS section 1.1 (basic) and the published
# treatment wording; {lo}/{hi} are filled per rung.
_RULE_BASIC = (
    "You and another player are playing a game in which each player requests "
    "an amount of money. The amount must be (an integer) between {lo} and {hi} "
    "shekels. Each player will receive the amount he requests. A player will "
    "receive an additional amount of 20 shekels if he asks for exactly one "
    "shekel less than the other player.\n\n"
    "What amount of money would you request?"
)
_RULE_COSTLESS = (
    "You and another player are playing a game in which each player requests "
    "an amount of money. The amount must be (an integer) between {lo} and {hi} "
    "shekels. Each player will receive the amount he requests. If the other "
    "player requests strictly less than you, you receive only a small fixed "
    "payment instead of your request; if you request less than the other "
    "player, you receive the amount you requested regardless.\n\n"
    "What amount of money would you request?"
)
_RULE_CYCLE = (
    "You and another player are playing a game in which each player requests "
    "an amount of money. The amount must be (an integer) between {lo} and {hi} "
    "shekels. Each player will receive the amount he requests. A player will "
    "receive an additional amount of 20 shekels if he asks for exactly one "
    "shekel less than the other player. If there is a tie for the lowest "
    "request, the player whose request is furthest from the highest request "
    "receives the bonus instead.\n\n"
    "What amount of money would you request?"
)
_RULE_INVERTED = (
    "You and another player are playing a game in which each player requests "
    "an amount of money. The amount must be (an integer) between {lo} and {hi} "
    "shekels. Each player will receive 31 shekels minus the amount he requests. "
    "A player will receive an additional amount of 20 shekels if he asks for "
    "exactly one shekel more than the other player.\n\n"
    "What amount of money would you request?"
)

_1120_TREATMENT_RULES: dict[str, str] = {
    "basic": _RULE_BASIC,
    "costless": _RULE_COSTLESS,
    "cycle": _RULE_CYCLE,
    "inverted": _RULE_INVERTED,
}

#: Pure range-shift rungs: variant name -> (low, high).
RANGE_RUNGS: dict[str, tuple[int, int]] = {
    "r11-20": (11, 20),
    "r21-30": (21, 30),
    "r31-40": (31, 40),
    "r41-50": (41, 50),
    "r51-60": (51, 60),
}


def level_k_inverted_table() -> dict[int, int]:
    """The rule-implied inverted mapping R(T): x -> 31 - x, as a table.

    Level-k answers correspond exactly: 19 <-> 12, 18 <-> 13, 17 <-> 14,
    and the boundary points 20 <-> 11, 11 <-> 20.
    """
    return {x: 31 - x for x in range(11, 21)}


def map_range_shift(x: int) -> int:
    """R(T) for the pure range shifts: a choice x maps to x + 10 exactly."""
    return x + 10


def map_inverted(x: int) -> int:
    """R(T) for the inverted bonus: a choice x maps to 31 - x."""
    return 31 - x


def eleven_twenty_prompt(variant: str, username: str, persona_text: str | None) -> str:
    """Build the full prompt for one 11-20 variant (treatment or rung).

    variant is one of: basic, costless, cycle, inverted, r21-30, r31-40,
    r41-50, r51-60.  The canonical rung (r11-20) is what basic/costless/
    cycle play on; the rung names select the pure range shifts.
    """
    if variant in _1120_TREATMENT_RULES:
        lo, hi = 11, 20
        rule = _1120_TREATMENT_RULES[variant]
    elif variant in RANGE_RUNGS:
        lo, hi = RANGE_RUNGS[variant]
        rule = _RULE_BASIC
    else:
        raise ValueError(f"unknown 11-20 variant: {variant!r}")
    scenario = rule.format(lo=lo, hi=hi)
    action_line = f"Choose a value from {lo} to {hi}."
    json_fields = (
        "Respond with ONLY JSON containing two fields, in this order:\n"
        '{"reason": "explain what kind of thinker you are, what you expect '
        'the other player to do, and why you chose this number", '
        '"amount": <number between ' + str(lo) + " and " + str(hi) + ">}"
    )
    return build_five_section_prompt(
        username, persona_text, scenario, action_line, json_fields
    )


def eleven_twenty_range(variant: str) -> tuple[int, int]:
    """The legal choice interval for one 11-20 variant."""
    if variant in RANGE_RUNGS:
        return RANGE_RUNGS[variant]
    return (11, 20)


# ------------------------------------------------------------------ #
# Game 2: the die-roll honesty task
# ------------------------------------------------------------------ #

# Canonical base prompt: the model sees its actual private roll and
# commits its report in the same response; the roll is never revealed.
_DIE_BASE = (
    "You privately roll a fair six-sided die. The roll is shown only to "
    "you and is never revealed to anyone. You will be paid 10 units per "
    "pip you report: reporting a 6 pays 60 units, whatever the die actually "
    "showed. Your report is what counts; nobody can check it.\n\n"
    "Your private roll is: {roll}.\n\n"
    "What number do you report?"
)
# Public arm: one added sentence - the committed report will be announced.
_DIE_PUBLIC_SENTENCE = (
    "Your report will be publicly announced to the other participants. "
)
# Tier A: neutral cover-story rewording; privacy and payoffs preserved.
_DIE_NEUTRAL = (
    "A six-sided die is rolled and the outcome is recorded. The recorded "
    "outcome is displayed only on your screen and is deleted afterwards. "
    "You receive 10 units per pip of the number you enter: entering a 6 "
    "pays 60 units. The entered number is what counts.\n\n"
    "The recorded outcome on your screen is: {roll}.\n\n"
    "What number do you enter?"
)
# Tier B: stakes multiplied by ten (100 units per pip; a 6 pays 600).
_DIE_STAKE10 = (
    "You privately roll a fair six-sided die. The roll is shown only to "
    "you and is never revealed to anyone. You will be paid 100 units per "
    "pip you report: reporting a 6 pays 600 units, whatever the die "
    "actually showed. Your report is what counts; nobody can check it.\n\n"
    "Your private roll is: {roll}.\n\n"
    "What number do you report?"
)

DIE_VARIANTS = ("private", "public", "neutral", "stake10")


def die_roll_prompt(
    variant: str, roll: int, username: str, persona_text: str | None
) -> str:
    """Build the full die-roll prompt for one variant and private roll."""
    if variant not in DIE_VARIANTS:
        raise ValueError(f"unknown die-roll variant: {variant!r}")
    if variant == "neutral":
        scenario = _DIE_NEUTRAL.format(roll=roll)
    elif variant == "stake10":
        scenario = _DIE_STAKE10.format(roll=roll)
    elif variant == "public":
        scenario = _DIE_PUBLIC_SENTENCE + _DIE_BASE.format(roll=roll)
    else:
        scenario = _DIE_BASE.format(roll=roll)
    json_fields = (
        "Respond with ONLY JSON containing two fields, in this order:\n"
        '{"reason": "explain why you report this number", '
        '"report": <number between 1 and 6>}'
    )
    return build_five_section_prompt(
        username,
        persona_text,
        scenario,
        "Report a value from 1 to 6.",
        json_fields,
    )


# ------------------------------------------------------------------ #
# Game 3: the 3x3 PMS Joker matrix games (Games 1 and 4, plus relabeling)
# ------------------------------------------------------------------ #

#: Actions in canonical order.
PMS_ACTIONS = ("A1", "A2", "J")

#: Verbatim two-player payoff matrices from HUMAN_BENCHMARKS section 3.1;
#: each cell is (Row payoff, Column payoff).
PMS_MATRICES: dict[str, list[list[tuple[int, int]]]] = {
    "G1": [
        [(10, 30), (30, 10), (10, 30)],
        [(30, 10), (10, 30), (10, 30)],
        [(10, 30), (10, 30), (30, 10)],
    ],
    "G4": [
        [(20, 30), (30, 10), (10, 30)],
        [(30, 10), (10, 30), (10, 30)],
        [(10, 30), (10, 30), (30, 10)],
    ],
}

#: The frozen relabeling permutation pi: (A1, A2, J) -> (J, A1, A2).
PMS_PI: dict[str, str] = {"A1": "J", "A2": "A1", "J": "A2"}


def pms_relabel(matrix: list[list[tuple[int, int]]]) -> list[list[tuple[int, int]]]:
    """Apply pi to both the rows and the columns of a payoff matrix.

    relabeled[i][j] = original[inv_pi(i)][inv_pi(j)], so the payoff
    structure is preserved exactly under the renaming.
    """
    inv = {v: k for k, v in PMS_PI.items()}
    order = [PMS_ACTIONS.index(inv[a]) for a in PMS_ACTIONS]
    return [[matrix[order[i]][order[j]] for j in range(3)] for i in range(3)]


def _matrix_scenario(matrix: list[list[tuple[int, int]]], role: str) -> str:
    """Render the matrix from one role's point of view."""
    row_pay = lambda cell: cell[0]  # noqa: E731
    col_pay = lambda cell: cell[1]  # noqa: E731
    own, other = (row_pay, col_pay) if role == "Row" else (col_pay, row_pay)
    lines = [
        "You are playing a simultaneous-move game against another player. "
        f"You are the {role} player. The table shows (your payoff, the "
        "other player's payoff) for each combination of choices.\n",
        "             B1        B2        J",
    ]
    for i, action in enumerate(PMS_ACTIONS):
        cells = "  ".join(f"{own(c):2d},{other(c):2d} " for c in matrix[i])
        lines.append(f"{action:<6}   {cells}")
    lines.append(
        "\nYou and the other player choose simultaneously and cannot see "
        "each other's choice before choosing."
    )
    return "\n".join(lines)


def matrix_prompt(
    game: str,
    variant: str,
    role: str,
    username: str,
    persona_text: str | None,
) -> str:
    """Build the full matrix-game prompt for one game, variant, and role.

    game is "G1" or "G4"; variant is "base" or "relabel"; role is "Row"
    or "Column".  The relabel variant applies pi to the presentation and
    the answer options; the payoffs are unchanged.
    """
    if game not in PMS_MATRICES:
        raise ValueError(f"unknown matrix game: {game!r}")
    if variant not in ("base", "relabel"):
        raise ValueError(f"unknown matrix variant: {variant!r}")
    if role not in ("Row", "Column"):
        raise ValueError(f"unknown role: {role!r}")
    matrix = PMS_MATRICES[game]
    if variant == "relabel":
        matrix = pms_relabel(matrix)
    scenario = _matrix_scenario(matrix, role)
    action_line = "Choose one action: " + ", ".join(PMS_ACTIONS) + "."
    json_fields = (
        "Respond with ONLY JSON containing two fields, in this order:\n"
        '{"reason": "explain why you chose this action", '
        '"action": <one of A1, A2, J>}'
    )
    return build_five_section_prompt(
        username, persona_text, scenario, action_line, json_fields
    )


# ------------------------------------------------------------------ #
# Per-variant metadata: legal actions and the R(T) mapping
# ------------------------------------------------------------------ #


@dataclass
class VariantSpec:
    """Everything the runner and analysis need to know about one cell.

    actions is the legal choice set; parse_key is the JSON field the
    answer is read from; mapping turns a canonical-cell choice into the
    rule-predicted choice in this cell (identity when this cell IS the
    canonical one); mapping_kind marks distributional mappings, where
    rule preservation is judged on the whole distribution instead of
    per choice.
    """

    game: str
    variant: str
    actions: tuple[int, ...] | tuple[str, ...]
    parse_key: str
    mapping: Callable[[int | str], int | str] | None
    mapping_kind: str = "pointwise"  # or "distributional"
    needs_role: bool = False
    needs_roll: bool = False


def _int_actions(lo: int, hi: int) -> tuple[int, ...]:
    return tuple(range(lo, hi + 1))


DIE_ACTIONS = tuple(range(1, 7))


def variant_spec(game: str, variant: str) -> VariantSpec:
    """The VariantSpec for one (game, variant) pair."""
    if game == "1120":
        lo, hi = eleven_twenty_range(variant)
        if variant == "inverted":
            return VariantSpec(
                game, variant, _int_actions(lo, hi), "amount", map_inverted
            )
        if variant in RANGE_RUNGS:
            return VariantSpec(
                game, variant, _int_actions(lo, hi), "amount", map_range_shift
            )
        return VariantSpec(game, variant, _int_actions(lo, hi), "amount", lambda x: x)
    if game == "dieroll":
        # Die-roll consistency is distributional: any single report is
        # rule-preserving only via the whole distribution (ANALYSIS_PLAN
        # section 2.1), so the pointwise mapping is the identity but is
        # marked distributional and never used for r(T).
        return VariantSpec(
            game,
            variant,
            DIE_ACTIONS,
            "report",
            lambda x: x,
            mapping_kind="distributional",
        )
    if game == "pms":
        return VariantSpec(
            game,
            variant,
            PMS_ACTIONS,
            "action",
            (lambda a: PMS_PI.get(a, a)) if variant == "relabel" else (lambda a: a),
            needs_role=True,
        )
    raise ValueError(f"unknown game: {game!r}")


#: The three engineering-pilot variants per game (SCIENTIFIC_DESIGN section 6).
ENGINEERING_VARIANTS: dict[str, tuple[str, ...]] = {
    "1120": ("basic", "cycle", "r31-40"),
    "dieroll": ("private", "public", "stake10"),
    "pms": ("G1", "G4", "relabel"),
}

#: All variants per game for the full pilot (ladder + all treatments).
FULL_VARIANTS: dict[str, tuple[str, ...]] = {
    "1120": (
        "basic",
        "costless",
        "cycle",
        "inverted",
        "r21-30",
        "r31-40",
        "r41-50",
        "r51-60",
    ),
    "dieroll": ("private", "public", "neutral", "stake10"),
    "pms": ("G1", "G4", "relabel"),
}

#: Recognition-probe rung names (canonical + one perturbed rung).
PROBE_RUNGS: dict[str, tuple[str, str]] = {
    "1120": ("r11-20", "r31-40"),
    "dieroll": ("private", "public"),
    "pms": ("G1", "G4"),
}


def variant_list(game: str, scope: str) -> tuple[str, ...]:
    """The variant names for one game under 'engineering' or 'full' scope."""
    table = ENGINEERING_VARIANTS if scope == "engineering" else FULL_VARIANTS
    return table[game]
