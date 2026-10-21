"""Tests for the three new games (offline, no model calls).

Each test checks one plain fact about the new games: the traveler's
dilemma bonus/penalty arithmetic, the social-allocation payoff numbers
(including the +1000 offset variant), the Allais-style gamble
probabilities shown in the prompt text, which arm sees the persona
text, the legal choices per condition, and that the pilot config plans
exactly 600 decisions with no probes.
"""

import yaml
from pathlib import Path

import new_games
import runner

CONFIGS = Path(__file__).resolve().parents[2] / "scripts" / "sixgame" / "configs"


# ------------------------------------------------------------------ #
# Traveler's Dilemma payoffs
# ------------------------------------------------------------------ #


def test_traveler_equal_claims_pay_both_their_claim():
    assert new_games.traveler_payoff(150, 150, 5) == 150
    assert new_games.traveler_payoff(200, 200, 80) == 200


def test_traveler_lower_claimer_gets_bonus_higher_gets_penalty():
    # I claim 100, other claims 150, R=5: I get 100+5, they get 100-5.
    assert new_games.traveler_payoff(100, 150, 5) == 105
    assert new_games.traveler_payoff(150, 100, 5) == 95


def test_traveler_penalty_never_goes_below_zero():
    # Lower claim 3 would mean a negative payoff (3 - 5); it is floored at 0.
    assert new_games.traveler_payoff(80, 80, 80) == 80
    assert new_games.traveler_payoff(80, 81, 80) >= 0
    assert new_games.traveler_payoff(81, 80, 80) == 0


def test_traveler_td_shift_maps_claims_back_by_minus_100():
    assert new_games.map_td_shift(280) == 180
    assert new_games.map_td_shift(100) == 0


def test_traveler_prompt_discloses_cents_units_and_range():
    prompt = new_games.new_game_prompt(
        "traveler", "td_low", "person1", None
    )
    assert "cents" in prompt
    assert "80" in prompt and "200" in prompt
    assert "5" in prompt  # the reward/penalty parameter
    high = new_games.new_game_prompt("traveler", "td_high", "person1", None)
    assert "80" in high


# ------------------------------------------------------------------ #
# Social allocation (Charness-Rabin 2002 Table I)
# ------------------------------------------------------------------ #


def test_social_generous_option_pays_400_400_and_selfish_750_400():
    options = new_games.SOCIAL_OPTIONS
    assert options["generous"] == (400, 400)
    assert options["selfish"] == (750, 400)


def test_social_plus1000_adds_1000_to_every_payoff():
    options = new_games.social_options_for("social_plus1000")
    assert options["generous"] == (1400, 1400)
    assert options["selfish"] == (1750, 1400)


def test_social_base_conditions_use_unshifted_payoffs():
    for variant in ("social_generous_prior", "social_selfish_prior"):
        assert new_games.social_options_for(variant) == new_games.SOCIAL_OPTIONS


def test_social_prompt_states_the_other_player_prior_behavior():
    generous = new_games.new_game_prompt(
        "social", "social_generous_prior", "person1", None
    )
    selfish = new_games.new_game_prompt(
        "social", "social_selfish_prior", "person1", None
    )
    assert "generous" in generous.lower()
    assert "selfish" in selfish.lower()


# ------------------------------------------------------------------ #
# Allais-style risk (Erev et al. 2017 Table 1 phenomenon 1)
# ------------------------------------------------------------------ #


def test_allais_base_options_are_3_vs_4_at_80_percent():
    assert new_games.allais_options("allais_base_1") == {
        "A": {"payoff": 3, "probability": 1.0},
        "B": {"payoff": 4, "probability": 0.8},
    }
    assert new_games.allais_options("allais_base_2") == {
        "A": {"payoff": 3, "probability": 0.25},
        "B": {"payoff": 4, "probability": 0.20},
    }


def test_allais_x10_options_are_the_same_gambles_with_prizes_times_ten():
    assert new_games.allais_options("allais_x10_1") == {
        "A": {"payoff": 30, "probability": 1.0},
        "B": {"payoff": 40, "probability": 0.8},
    }
    assert new_games.allais_options("allais_x10_2") == {
        "A": {"payoff": 30, "probability": 0.25},
        "B": {"payoff": 40, "probability": 0.20},
    }


def test_allais_prompt_shows_probabilities_and_zero_outcome():
    prompt = new_games.new_game_prompt("allais", "allais_base_2", "person1", None)
    assert "25%" in prompt
    assert "20%" in prompt
    assert "0" in prompt  # zero payoff otherwise


# ------------------------------------------------------------------ #
# Prompt structure: 5 sections, persona text only in the persona arm
# ------------------------------------------------------------------ #


ALL_CONDITIONS = (
    ("traveler", "td_low"),
    ("traveler", "td_high"),
    ("traveler", "td_shift180_300"),
    ("social", "social_generous_prior"),
    ("social", "social_selfish_prior"),
    ("social", "social_plus1000"),
    ("allais", "allais_base_1"),
    ("allais", "allais_base_2"),
    ("allais", "allais_x10_1"),
    ("allais", "allais_x10_2"),
)


def test_all_ten_conditions_exist_and_build_prompts():
    for game, variant in ALL_CONDITIONS:
        prompt = new_games.new_game_prompt(game, variant, "person1", None)
        assert "EMBODY THIS PERSON" in prompt
        assert "JSON" in prompt


def test_persona_text_only_appears_in_persona_arm():
    for game, variant in ALL_CONDITIONS:
        with_persona = new_games.new_game_prompt(
            game, variant, "person1", "You are a cautious accountant."
        )
        no_persona = new_games.new_game_prompt(game, variant, "person1", None)
        assert "cautious accountant" in with_persona
        assert "cautious accountant" not in no_persona
        assert "You are person1." in no_persona


# ------------------------------------------------------------------ #
# Legal choices and specs per condition
# ------------------------------------------------------------------ #


def test_traveler_legal_claims_are_80_to_200_or_180_to_300():
    spec = new_games.variant_spec_new("traveler", "td_low")
    assert spec.actions[0] == 80 and spec.actions[-1] == 200
    shift = new_games.variant_spec_new("traveler", "td_shift180_300")
    assert shift.actions[0] == 180 and shift.actions[-1] == 300


def test_social_and_allais_legal_choices_are_a_or_b():
    assert new_games.variant_spec_new("social", "social_plus1000").actions == ("A", "B")
    assert new_games.variant_spec_new("allais", "allais_base_1").actions == ("A", "B")


def test_variant_spec_registry_covers_new_games():
    for game, variant in ALL_CONDITIONS:
        spec = runner.variant_spec(game, variant)  # re-exported via plan/games
        assert spec.actions


# ------------------------------------------------------------------ #
# Plan counts: 10 conditions x 2 arms x 3 models x 10 draws = 600
# ------------------------------------------------------------------ #


def _load_config():
    with (CONFIGS / "new_games_pilot.yaml").open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def test_pilot_config_has_exactly_ten_conditions():
    config = _load_config()
    n_variants = sum(len(g["variants"]) for g in config["games"].values())
    assert n_variants == 10


def test_pilot_config_plans_600_decisions_and_no_probes():
    config = _load_config()
    decision_cells = runner.cells(config)
    assert len(decision_cells) == 10 * 2 * 3
    decisions = len(decision_cells) * config["draws_per_cell"]
    assert decisions == 600
    assert config["probes"]["enabled"] is False
    text = runner.print_counts(config)
    assert "decisions: 600" in text
    assert "probes: 0" in text
    assert "TOTAL: 600" in text


def test_print_counts_cli_matches_pilot_config(capsys):
    code = runner.main(
        ["--config", str(CONFIGS / "new_games_pilot.yaml"), "--print-counts"]
    )
    assert code == 0
    assert "TOTAL: 600" in capsys.readouterr().out


def test_existing_games_and_configs_are_untouched():
    # The registry only ADDS the three new games; old games unchanged.
    import games

    assert set(games.ENGINEERING_VARIANTS) == {"1120", "dieroll", "pms"}
    with (CONFIGS / "engineering_pilot.yaml").open("r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)
    assert set(config["games"]) == {"1120", "dieroll", "pms"}
