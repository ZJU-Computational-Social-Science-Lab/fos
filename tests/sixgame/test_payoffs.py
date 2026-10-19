"""Tests that the game payoffs and rule texts match the frozen benchmarks.

Each test checks one plain fact about the games: the matrix numbers are
the published ones, the treatments differ in exactly one rule sentence,
and the die-roll variants each change exactly one thing.
"""

import games
import benchmarks


def test_pms_game1_matrix_matches_benchmark():
    assert games.PMS_MATRICES["G1"] == [
        [(10, 30), (30, 10), (10, 30)],
        [(30, 10), (10, 30), (10, 30)],
        [(10, 30), (10, 30), (30, 10)],
    ]


def test_pms_game4_matrix_matches_benchmark():
    assert games.PMS_MATRICES["G4"] == [
        [(20, 30), (30, 10), (10, 30)],
        [(30, 10), (10, 30), (10, 30)],
        [(10, 30), (10, 30), (30, 10)],
    ]


def test_pms_games_differ_only_in_top_left_row_payoff():
    g1 = games.PMS_MATRICES["G1"]
    g4 = games.PMS_MATRICES["G4"]
    assert g1[0][0][0] == 10 and g4[0][0][0] == 20
    for i in range(3):
        for j in range(3):
            if (i, j) != (0, 0):
                assert g1[i][j] == g4[i][j]
    # Column payoffs identical in every cell across the two games.
    for i in range(3):
        for j in range(3):
            assert g1[i][j][1] == g4[i][j][1]


def test_benchmark_frequencies_match_frozen_doc():
    assert benchmarks.FREQ_PMS["G1"]["Row"] == (0.273, 0.349, 0.378)
    assert benchmarks.FREQ_PMS["G4"]["Row"] == (0.473, 0.220, 0.307)
    assert benchmarks.FREQ_PMS["G4"]["Column"] == (0.487, 0.147, 0.366)
    assert benchmarks.EFFECT_PMS_PP["Row"] == (20.0, -12.9, -7.1)


def test_benchmark_1120_pmfs_match_frozen_doc():
    assert benchmarks.PMF_1120["basic"][6:10] == [32, 30, 12, 6]
    assert benchmarks.PMF_1120["costless"][8] == 40
    assert benchmarks.PMF_1120["cycle"][8] == 47
    assert benchmarks.EFFECTS_1120["basic_to_cycle"][19] == 35


def test_benchmark_die_pmfs_match_frozen_doc():
    assert benchmarks.PMF_DIE["private"][5] == 38.5
    assert benchmarks.PMF_DIE["public"][5] == 29.2
    assert benchmarks.EFFECT_DIE_SHARE6_PP == -9.2
    assert benchmarks.MEAN_DIE["private"] == 4.908


def test_die_public_variant_adds_only_the_announcement_sentence():
    private = games.die_roll_prompt("private", 4, "alice", None)
    public = games.die_roll_prompt("public", 4, "alice", None)
    # The public prompt is the private prompt plus one added sentence.
    assert public.replace(games._DIE_PUBLIC_SENTENCE, "") == private
    assert games._DIE_PUBLIC_SENTENCE in public


def test_die_neutral_variant_preserves_payoff_numbers():
    # Tier A: payoffs unchanged (10 per pip, 60 for a 6), only reworded.
    assert "10 units per pip" in games._DIE_NEUTRAL
    assert "60 units" in games._DIE_NEUTRAL
    # Tier B: stakes multiplied by ten (100 per pip, 600 for a 6).
    assert "100 units per pip" in games._DIE_STAKE10
    assert "600 units" in games._DIE_STAKE10


def test_1120_treatments_keep_same_number_line():
    for variant in ("basic", "costless", "cycle", "inverted"):
        prompt = games.eleven_twenty_prompt(variant, "alice", None)
        assert "between 11 and 20" in prompt
    # The inverted rule text is the verified mirror wording.
    assert "31 shekels minus the amount he requests" in games._RULE_INVERTED
    assert "exactly one shekel more" in games._RULE_INVERTED
    assert "exactly one shekel less" in games._RULE_BASIC


def test_range_rungs_are_pure_plus10_shifts():
    for rung, (lo, hi) in games.RANGE_RUNGS.items():
        assert hi - lo == 9
    prompt = games.eleven_twenty_prompt("r31-40", "alice", None)
    assert "between 31 and 40" in prompt


def test_persona_vs_no_persona_arm_differs_only_in_section_1():
    persona = games.eleven_twenty_prompt("basic", "alice", "I am cautious.")
    placebo = games.eleven_twenty_prompt("basic", "alice", None)
    assert "I am cautious." in persona
    assert "You are alice." in placebo
    # Sections 2-5 identical apart from the embedded persona block.
    tail = persona.split("=== SECTION 2", 1)[1]
    tail_placebo = placebo.split("=== SECTION 2", 1)[1]
    assert tail == tail_placebo
