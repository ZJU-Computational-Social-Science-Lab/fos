"""Tests for the PMS action relabeling permutation pi.

The frozen relabeling maps (A1, A2, J) to (J, A1, A2) and is applied to
both the presentation and the answer options, so the payoff structure
must be preserved exactly under the renaming.
"""

import games


def test_pi_maps_a1_to_j_a2_to_a1_j_to_a2():
    assert games.PMS_PI == {"A1": "J", "A2": "A1", "J": "A2"}


def test_pi_is_a_bijection():
    assert sorted(games.PMS_PI) == sorted(games.PMS_ACTIONS)
    assert len(set(games.PMS_PI.values())) == 3


def test_relabel_preserves_payoff_structure():
    # relabeled[i][j] must equal original at the inverse-permuted
    # indices: renaming actions cannot change any payoff cell.
    for game in ("G1", "G4"):
        matrix = games.PMS_MATRICES[game]
        relabeled = games.pms_relabel(matrix)
        inverse = {v: k for k, v in games.PMS_PI.items()}
        for i, row_action in enumerate(games.PMS_ACTIONS):
            for j, col_action in enumerate(games.PMS_ACTIONS):
                oi = games.PMS_ACTIONS.index(inverse[row_action])
                oj = games.PMS_ACTIONS.index(inverse[col_action])
                assert relabeled[i][j] == matrix[oi][oj]


def test_relabel_is_a_three_cycle():
    # pi is a 3-cycle (A1->J->A2->A1), so relabeling three times returns
    # the original matrix.
    for game in ("G1", "G4"):
        matrix = games.PMS_MATRICES[game]
        twice = games.pms_relabel(games.pms_relabel(matrix))
        thrice = games.pms_relabel(twice)
        assert thrice == matrix
        assert twice != matrix


def test_variant_spec_mapping_uses_pi_only_for_relabel():
    base = games.variant_spec("pms", "G1")
    relabel = games.variant_spec("pms", "relabel")
    assert base.mapping("A1") == "A1"
    assert relabel.mapping("A1") == "J"
    assert relabel.mapping("A2") == "A1"
    assert relabel.mapping("J") == "A2"


def test_matrix_prompt_applies_pi_to_presentation_and_options():
    base = games.matrix_prompt("G1", "base", "Row", "alice", None)
    relabel = games.matrix_prompt("G1", "relabel", "Row", "alice", None)
    # The relabeled top-left cell shows the J-row payoff of the J column
    # of the original (30, 10); the base shows (10, 30).
    assert "10,30" in base.split("\n")[7][:20] or "10,30" in base
    # Answer options list the same action names in both (the labels stay;
    # the payoffs beneath them move).
    for action in ("A1", "A2", "J"):
        assert action in relabel
    # The relabeled A1 row carries the old A2 row's payoffs, with the
    # columns carried along under the same permutation.
    first_data_row = None
    for line in relabel.split("\n"):
        if line.startswith("A1 "):
            first_data_row = line
            break
    cells = first_data_row.split()[1:]
    assert cells == [
        f"{cell[0]},{cell[1]}"
        for cell in games.pms_relabel(games.PMS_MATRICES["G1"])[0]
    ]
