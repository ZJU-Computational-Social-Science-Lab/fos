"""The three new games: Traveler's Dilemma, social allocation, Allais risk.

This file defines ten new experimental conditions as plain data plus
prompt builders, in the same style as games.py:

- Traveler's Dilemma (Capra et al. 1999): two players each claim a
  number; both are paid the lower claim, the lower claimant gets a
  bonus R and the higher claimant pays R.  The published amounts are in
  CENTS (R=5 means 5 cents), and this is disclosed in every prompt.
  Three conditions: R=5, R=80, and a range-shift version (claims
  180-300, R=5) whose claims map back to the R=5 range by subtracting
  100.
- Social allocation (Charness-Rabin 2002, Table I): choose between a
  generous option (400, 400) and a selfish option (750, 400), where
  payoffs are (you, other).  The prompt states what the other player
  did earlier (was generous or selfish).  The +1000 condition adds
  1000 to every payoff in both options — our own transformation.
- Allais-style risk (Erev et al. 2017, Table 1 phenomenon 1, from
  Kahneman-Tversky 1979): certain 3 vs 4 at 80%, and 3 at 25% vs 4 at
  20%; the x10 versions (30/40) are our own construction and are
  labeled as such in the prompt.

Every prompt uses the same five-section scaffolding as the existing
games; the persona text appears only in the persona arm.
"""

from __future__ import annotations

from games import build_five_section_prompt


# ------------------------------------------------------------------ #
# Game 1: Traveler's Dilemma (Capra et al. 1999)
# ------------------------------------------------------------------ #

#: Condition name -> (lowest claim, highest claim, reward/penalty R).
#: R is in CENTS, exactly as published (R=5 means 5 cents).
TRAVELER_CONDITIONS: dict[str, tuple[int, int, int]] = {
    "td_low": (80, 200, 5),
    "td_high": (80, 200, 80),
    "td_shift180_300": (180, 300, 5),
}


def traveler_payoff(own_claim: int, other_claim: int, r: int) -> int:
    """What one player earns in the Traveler's Dilemma.

    Both players are paid the lower of the two claims; the lower
    claimant also gets +R and the higher claimant pays -R.  The paper
    does not floor earnings, so a penalty below zero is capped at 0
    here and that cap is disclosed in the prompt.
    """
    lower = min(own_claim, other_claim)
    if own_claim < other_claim:
        return lower + r
    if own_claim > other_claim:
        return max(0, lower - r)
    return lower


def map_td_shift(x: int) -> int:
    """Map a shifted-range claim back to the R=5 range: x -> x - 100."""
    return x - 100


def _traveler_scenario(variant: str) -> str:
    lo, hi, r = TRAVELER_CONDITIONS[variant]
    return (
        "You and another player are playing a game. Each of you claims an "
        f"amount between {lo} and {hi} cents. If the claims are equal, each "
        "of you receives the amount claimed. If the claims are not equal, "
        "each of you receives the lower of the two claims; the player who "
        f"made the lower claim earns a reward of {r} cents, and the player "
        f"who made the higher claim pays a penalty of {r} cents. Earnings "
        "are never below zero. All amounts are in cents, exactly as in the "
        "original published experiment (a reward parameter of 5 means 5 "
        "cents).\n\n"
        "What amount do you claim?"
    )


# ------------------------------------------------------------------ #
# Game 2: Social allocation (Charness-Rabin 2002, Table I)
# ------------------------------------------------------------------ #

#: The published Table I choice set: generous (400, 400) vs selfish
#: (750, 400), payoffs (you, other).  Published generous shares:
#: .31 dictator (Berk29), .06 after a generous move by the other
#: (Barc7), .33 after the other imposed (550, 550) (Barc5).
SOCIAL_OPTIONS: dict[str, tuple[int, int]] = {
    "generous": (400, 400),
    "selfish": (750, 400),
}

#: What the prompt says the other player did earlier, per condition.
_SOCIAL_PRIOR: dict[str, str] = {
    "social_generous_prior": (
        "Earlier in the session, the other player was generous: they gave "
        "up money themselves so that you would earn more."
    ),
    "social_selfish_prior": (
        "Earlier in the session, the other player was selfish: they "
        "imposed an equal split (550, 550) on you both when they could "
        "have let you choose."
    ),
}

#: The +1000 condition is our constant-offset transformation of the
#: generous-prior context; ordering-neutral under expected utility.
SOCIAL_OFFSET_VARIANT = "social_plus1000"


def social_options_for(variant: str) -> dict[str, tuple[int, int]]:
    """The two options for one social condition, after any payoff offset."""
    if variant == SOCIAL_OFFSET_VARIANT:
        return {
            name: (self_pay + 1000, other_pay + 1000)
            for name, (self_pay, other_pay) in SOCIAL_OPTIONS.items()
        }
    return dict(SOCIAL_OPTIONS)


def _social_scenario(variant: str) -> str:
    options = social_options_for(variant)
    gen, sel = options["generous"], options["selfish"]
    prior = _SOCIAL_PRIOR.get(
        variant, _SOCIAL_PRIOR["social_generous_prior"]
    )
    return (
        "You are playing a game with another player. Earlier in the "
        "session, something happened between you:\n\n"
        f"{prior}\n\n"
        "Now you choose between two options. The payoffs are shown as "
        "(you, the other player):\n\n"
        f"Option A: ({gen[0]}, {gen[1]})\n"
        f"Option B: ({sel[0]}, {sel[1]})\n\n"
        "Which option do you choose?"
    )


# ------------------------------------------------------------------ #
# Game 3: Allais-style risk (Erev et al. 2017 Table 1, phenomenon 1)
# ------------------------------------------------------------------ #

#: Condition name -> option payoffs/probabilities.  Option A is the
#: (relatively) certain side, B the risky side; zero is paid otherwise.
#: Source: Erev et al. 2017 Table 1 phenomenon 1 (small-stakes version
#: of Kahneman & Tversky 1979).  The x10 prize variants are OUR
#: construction, scaled from the published pairs.
_ALLAIS_BASE: dict[str, dict[str, dict[str, float]]] = {
    "allais_base_1": {
        "A": {"payoff": 3, "probability": 1.0},
        "B": {"payoff": 4, "probability": 0.8},
    },
    "allais_base_2": {
        "A": {"payoff": 3, "probability": 0.25},
        "B": {"payoff": 4, "probability": 0.20},
    },
}

ALLAIS_SCALE = 10


def allais_options(variant: str) -> dict[str, dict[str, float]]:
    """The two gamble options for one Allais condition."""
    pair = variant[-1]  # the trailing 1 or 2 picks the published pair
    base = _ALLAIS_BASE[f"allais_base_{pair}"]
    if not variant.startswith("allais_x10"):
        return {k: dict(v) for k, v in base.items()}
    return {
        letter: {
            "payoff": opt["payoff"] * ALLAIS_SCALE,
            "probability": opt["probability"],
        }
        for letter, opt in base.items()
    }


def _allais_scenario(variant: str) -> str:
    options = allais_options(variant)
    lines = ["You choose between two options. You are paid for your choice:\n"]
    for letter in ("A", "B"):
        opt = options[letter]
        if opt["probability"] >= 1.0:
            lines.append(
                f"Option {letter}: {opt['payoff']:.0f} with certainty."
            )
        else:
            lines.append(
                f"Option {letter}: {opt['payoff']:.0f} with "
                f"{opt['probability'] * 100:.0f}% probability, 0 otherwise."
            )
    lines.append(
        "\nAll prizes are in the same currency units as the source "
        "experiments. The times-ten prize variant, if shown, is our own "
        "scaled construction of the published problem."
    )
    lines.append("\nWhich option do you choose?")
    return "\n".join(lines)


# ------------------------------------------------------------------ #
# Registry: prompts, legal choices, and mappings for the runner
# ------------------------------------------------------------------ #


def new_game_prompt(
    game: str, variant: str, username: str, persona_text: str | None
) -> str:
    """Build the full five-section prompt for one new-game condition."""
    if game == "traveler":
        if variant not in TRAVELER_CONDITIONS:
            raise ValueError(f"unknown traveler condition: {variant!r}")
        scenario = _traveler_scenario(variant)
        lo, hi, _ = TRAVELER_CONDITIONS[variant]
        action_line = f"Choose a value from {lo} to {hi}."
        json_fields = (
            "Respond with ONLY JSON containing two fields, in this order:\n"
            '{"reason": "explain why you chose this claim", '
            f'"claim": <number between {lo} and {hi}>}}'
        )
    elif game in ("social", "allais"):
        if game == "social":
            scenario = _social_scenario(variant)
        else:
            scenario = _allais_scenario(variant)
        action_line = "Choose one option: A or B."
        json_fields = (
            "Respond with ONLY JSON containing two fields, in this order:\n"
            '{"reason": "explain why you chose this option", '
            '"choice": <one of A, B>}'
        )
    else:
        raise ValueError(f"unknown new game: {game!r}")
    return build_five_section_prompt(
        username, persona_text, scenario, action_line, json_fields
    )


def variant_spec_new(game: str, variant: str):
    """The VariantSpec for one new-game condition (same fields as games.py).

    The shifted traveler range maps claims back by x -> x - 100, judged
    on the whole distribution (like the pure range shifts).
    """
    from games import VariantSpec, _int_actions

    if game == "traveler":
        lo, hi, _ = TRAVELER_CONDITIONS[variant]
        if variant == "td_shift180_300":
            return VariantSpec(
                game, variant, _int_actions(lo, hi), "claim", map_td_shift,
                mapping_kind="distributional",
            )
        return VariantSpec(
            game, variant, _int_actions(lo, hi), "claim", lambda x: x
        )
    if game in ("social", "allais"):
        return VariantSpec(game, variant, ("A", "B"), "choice", lambda x: x)
    raise ValueError(f"unknown new game: {game!r}")


#: The game names this module provides, for runner registration.
NEW_GAMES: dict[str, tuple[str, ...]] = {
    "traveler": ("td_low", "td_high", "td_shift180_300"),
    "social": ("social_generous_prior", "social_selfish_prior", "social_plus1000"),
    "allais": ("allais_base_1", "allais_base_2", "allais_x10_1", "allais_x10_2"),
}
