"""Tests for arm, role, and persona assignment: balance and determinism.

Role assignment (Row/Column) must be balanced within each matrix cell
and fully determined by the seed, so a rerun reproduces it exactly.
"""

import runner


def test_role_assignment_is_deterministic_for_same_seed():
    kwargs = dict(
        game="pms",
        variant="relabel",
        arm="persona",
        model="deepseek-v4-flash",
        persona_id="alice",
    )
    first = [runner.assign_role(7, draw_id=d, **kwargs) for d in range(10)]
    again = [runner.assign_role(7, draw_id=d, **kwargs) for d in range(10)]
    assert first == again


def test_role_assignment_is_balanced_across_draws():
    roles = [
        runner.assign_role(11, "pms", "G1", "persona", "deepseek-v4-flash", f"p{i}", d)
        for i in range(20)
        for d in range(10)
    ]
    counts = {role: roles.count(role) for role in ("Row", "Column")}
    # Balanced: neither side may hold more than 55% of assignments.
    assert abs(counts["Row"] - counts["Column"]) <= 0.1 * len(roles)


def test_non_matrix_games_get_no_role():
    assert (
        runner.assign_role(
            3, "1120", "basic", "persona", "deepseek-v4-flash", "alice", 0
        )
        is None
    )
    assert (
        runner.draw_true_roll(
            3, "1120", "basic", "persona", "deepseek-v4-flash", "alice", 0
        )
        is None
    )


def test_die_rolls_deterministic_and_cover_one_to_six():
    rolls = [
        runner.draw_true_roll(
            5, "dieroll", "private", "persona", "deepseek-v4-flash", f"p{i}", d
        )
        for i in range(30)
        for d in range(10)
    ]
    assert all(1 <= r <= 6 for r in rolls)
    assert set(rolls) == set(range(1, 7))
    again = [
        runner.draw_true_roll(
            5, "dieroll", "private", "persona", "deepseek-v4-flash", f"p{i}", d
        )
        for i in range(30)
        for d in range(10)
    ]
    assert rolls == again


def test_draws_distributed_round_robin_over_personas():
    names = ["p1", "p2", "p3", "p4", "p5"]
    assigned = runner.personas_for_cell(names, 10, 5)
    assert assigned == ["p1", "p2", "p3", "p4", "p5"] * 2


def test_plan_has_equal_cells_across_arms_and_models():
    config = runner.default_config("engineering")
    plan = runner.build_plan(config, [f"p{i}" for i in range(5)], seed=1)
    per_cell = {}
    for sample in plan:
        key = (sample.game, sample.variant, sample.arm, sample.model)
        per_cell[key] = per_cell.get(key, 0) + 1
    assert set(per_cell.values()) == {10}
    assert len(per_cell) == 3 * 3 * 2 * 3  # games x variants x arms x models


def test_same_seed_same_plan():
    config = runner.default_config("engineering")
    names = [f"p{i}" for i in range(5)]
    one = runner.build_plan(config, names, seed=42)
    two = runner.build_plan(config, names, seed=42)
    assert one == two
    other = runner.build_plan(config, names, seed=43)
    assert one != other
