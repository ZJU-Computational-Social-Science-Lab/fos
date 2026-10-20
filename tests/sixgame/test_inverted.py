"""Tests for the inverted-game and range-shift rule-implied mappings R(T).

The inverted bonus mirrors the basic game: a choice x in the inverted
game must map to 31 - x, so level-k answers correspond exactly
(19<->12, 18<->13, 17<->14, and the boundaries 20<->11).
"""

import games


def test_inverted_mapping_is_31_minus_x():
    for x in range(11, 21):
        assert games.map_inverted(x) == 31 - x


def test_inverted_level_k_table_matches_spec():
    table = games.level_k_inverted_table()
    assert table[19] == 12
    assert table[18] == 13
    assert table[17] == 14
    assert table[20] == 11
    assert table[11] == 20


def test_inverted_mapping_is_involutive():
    # Mirroring twice returns the original choice.
    for x in range(11, 21):
        assert games.map_inverted(games.map_inverted(x)) == x


def test_range_shift_mapping_is_x_plus_10():
    for x in range(11, 21):
        assert games.map_range_shift(x) == x + 10


def _basic_payoff(x: int, other: int) -> int:
    """Payoff in the basic game for requesting x against other."""
    bonus = 20 if x == other - 1 else 0
    return x + bonus


def _inverted_payoff(x: int, other: int) -> int:
    """Payoff in the inverted game for requesting x against other."""
    bonus = 20 if x == other + 1 else 0
    return (31 - x) + bonus


def test_inverted_game_best_response_mirrors_basic():
    # In the basic game the best reply to y is y-1; in the inverted game
    # it is y+1 (clamped to the 11..20 line) — the strategic mirror.
    for y in range(12, 21):
        basic_best = max(range(11, 21), key=lambda x: _basic_payoff(x, y))
        assert basic_best == y - 1
    for y in range(11, 20):
        inv_best = max(range(11, 21), key=lambda x: _inverted_payoff(x, y))
        assert inv_best == y + 1


def test_inverted_payoff_through_mapping_equals_basic_payoff():
    # Structure preservation: playing the mirrored choice in the
    # inverted game earns exactly what the original choice earns in the
    # basic game against the mirrored opponent.
    for x in range(11, 21):
        for y in range(11, 21):
            assert _inverted_payoff(31 - x, 31 - y) == _basic_payoff(x, y)


def test_variant_spec_exposes_correct_mappings():
    assert games.variant_spec("1120", "inverted").mapping(19) == 12
    # Audited rule: r31-40 rung maps x ↦ x+20 (11–20 → 31–40).
    assert games.variant_spec("1120", "r31-40").mapping(17) == 37
    assert games.variant_spec("1120", "basic").mapping(17) == 17
    die = games.variant_spec("dieroll", "public")
    assert die.mapping_kind == "distributional"
