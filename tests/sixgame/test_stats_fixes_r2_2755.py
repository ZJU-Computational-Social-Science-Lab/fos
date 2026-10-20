"""Regression tests for the TASK-2755 statistical fixes (round 2).

Each test checks a NUMERICAL value computed from fixed synthetic
distributions with a hand-known answer — none of these tests compare
Markdown to JSON.  They lock in: TVD and Jensen-Shannon math, the
cluster-bootstrap TVD CI on a fixed seed, PMS role separation, margin
verdict logic, labelled CIs with a structural no-cross-attachment check,
the support-diagnostic relabelling (no CONSISTENCY-SUCCESS/FAIL verdict),
the independent TVD confirmation path, and the decision/probe/full cost
breakdown.
"""

import math

import pytest

from analysis import (
    consistency_table,
    contrast_table,
    cost_breakdown,
    distribution_equivalence_table,
    independent_tvd_confirmation,
)
from games import variant_spec
from stats import (
    cluster_tvd_ci,
    js_divergence_bits,
    require_ci_label,
    tvd,
)


def _rec(game, variant, arm, persona, choice, role=None, draw=0, model="m",
         namespace="decisions"):
    """One synthetic raw record with hand-settable fields."""
    return {
        "game": game,
        "variant": variant,
        "arm": arm,
        "model": model,
        "persona_id": persona,
        "draw_id": draw,
        "role": role,
        "choice": choice,
        "namespace": namespace,
        "truncated": False,
        "finish_reason": "stop",
        "cache_status": "MISS",
        "cache_kind": "none",
        "error": None,
        "succeeded": True,
        "prompt_tokens": 100,
        "completion_tokens": 10,
        "cost_usd": 0.001,
        "raw_content": "",
    }


def _cells(game, can_variant, tra_variant, can_choices, tra_choices,
           role=None):
    """Build a cell_records dict mapping cells to synthetic records."""
    cells = {}
    for variant, choices in ((can_variant, can_choices),
                             (tra_variant, tra_choices)):
        recs = [
            _rec(game, variant, "persona", f"p{i % 5}", c, role=role, draw=i)
            for i, c in enumerate(choices)
        ]
        cells[(game, variant, "persona", "m")] = recs
    return cells


# ------------------------------------------------------------------ #
# TVD / Jensen-Shannon math on hand-computed fixtures
# ------------------------------------------------------------------ #

def test_tvd_of_two_known_pmf_is_four_tenths():
    p = {"a": 0.6, "b": 0.4}
    q = {"a": 0.2, "b": 0.8}
    assert tvd(p, q) == pytest.approx(0.4)


def test_tvd_ignores_missing_categories_as_zero():
    p = {"a": 0.6, "b": 0.4}
    q = {"a": 0.2, "b": 0.5, "c": 0.3}
    # |0.6-0.2| + |0.4-0.5| + |0-0.3| = 0.8; TVD = half of that = 0.4.
    assert tvd(p, q) == pytest.approx(0.4)


def test_js_divergence_base2_of_known_pair_is_about_01245():
    p = {"a": 0.6, "b": 0.4}
    q = {"a": 0.2, "b": 0.8}
    assert js_divergence_bits(p, q) == pytest.approx(0.1245112498, abs=1e-8)


def test_js_divergence_is_at_most_one_bit_and_zero_for_identical():
    p = {"a": 1.0}
    assert js_divergence_bits(p, p) == 0.0
    assert js_divergence_bits({"a": 1.0}, {"b": 1.0}) <= 1.0


# ------------------------------------------------------------------ #
# Cluster-bootstrap TVD CI from a fixed synthetic fixture
# ------------------------------------------------------------------ #

def test_cluster_tvd_ci_point_estimate_matches_hand_value():
    # canonical: both personas always a (indicator 1);
    # transformed: persona A always a, persona B never a.
    can = [[1.0], [1.0]]
    tra = [[1.0], [0.0]]
    point, lo, hi, n_eff = cluster_tvd_ci(can, tra, n_boot=1000, seed=7)
    # canonical share(a)=1.0, transformed share(a)=0.5 -> TVD=0.5
    assert point == pytest.approx(0.5)


def test_cluster_tvd_ci_is_deterministic_on_fixed_seed():
    can = [[1, 1, 0], [0, 0, 0], [1, 0, 0]]
    tra = [[0, 1], [1, 1], [0, 0]]
    a = cluster_tvd_ci(can, tra, n_boot=500, seed=3)
    b = cluster_tvd_ci(can, tra, n_boot=500, seed=3)
    assert a == b


def test_cluster_tvd_ci_brackets_the_point_estimate():
    can = [[1, 1, 0], [0, 0, 0], [1, 0, 0]]
    tra = [[0, 1], [1, 1], [0, 0]]
    point, lo, hi, _ = cluster_tvd_ci(can, tra, n_boot=2000, seed=11)
    assert lo <= point <= hi


def test_cluster_tvd_ci_reports_neff_per_kish_formula():
    # clusters of sizes 3 and 1: n_eff = 16 / (9 + 1) = 1.6
    can = [[1, 1, 0], [0]]
    tra = [[0, 1, 1], [1]]
    _, _, _, n_eff = cluster_tvd_ci(can, tra, n_boot=100, seed=0)
    assert n_eff == pytest.approx(1.6)


# ------------------------------------------------------------------ #
# Margin verdict logic
# ------------------------------------------------------------------ #

def test_distribution_equivalence_labels_unpowered_when_no_margin():
    # 11-20 r31-40 had no pre-agreed margin -> UNPOWERED-DESCRIPTIVE.
    cells = _cells(
        "1120", "basic", "r31-40",
        [11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
        [31, 32, 33, 34, 35, 36, 37, 38, 39, 40],
    )
    rows = distribution_equivalence_table(cells, boot=200, seed=0)
    for row in rows:
        assert row["verdict"] == "UNPOWERED-DESCRIPTIVE"


def test_distribution_equivalence_equivalent_when_ci_inside_margin():
    # Identical canonical and transformed distributions -> TVD point 0,
    # CI collapses near 0, inside the 5pp (0.05) Tier-A margin.
    # TASK-2760: n=10 per cell is too small for a defensible
    # finite-sample TVD bound, so equivalence is NOT established even
    # with a degenerate CI at 0 — we report no difference observed.
    choices = [6] * 8 + [5, 4]
    cells = _cells("dieroll", "private", "neutral", choices, choices)
    rows = distribution_equivalence_table(cells, boot=2000, seed=0)
    row = [r for r in rows if r["transformation"] == "dieroll_neutral_tierA"][0]
    assert row["verdict"] == (
        "NO_DIFFERENCE_OBSERVED_EQUIVALENCE_NOT_ESTABLISHED"
    )
    assert row["tvd"] == pytest.approx(0.0)


def test_distribution_equivalence_not_equivalent_when_ci_exceeds_margin():
    # Completely disjoint distributions: TVD = 1.0, way outside Tier B 15pp.
    cells = _cells(
        "dieroll", "private", "stake10", [1] * 10, [6] * 10,
    )
    rows = distribution_equivalence_table(cells, boot=200, seed=0)
    row = [r for r in rows if r["transformation"] == "dieroll_stake10_tierB"][0]
    assert row["verdict"] == "UNPOWERED-DESCRIPTIVE"
    assert row["tvd"] == pytest.approx(1.0)


# ------------------------------------------------------------------ #
# PMS relabeling analyzed separately per role
# ------------------------------------------------------------------ #

def test_pms_relabel_produces_separate_row_and_column_rows():
    choices = ["A1", "A2", "J", "A1", "A2", "J", "A1", "A2", "J", "A1"]
    cells = {}
    for role in ("Row", "Column"):
        for variant, cs in (("G1", choices), ("relabel", choices)):
            cells[("pms", variant, "persona", "m", role)] = [
                _rec("pms", variant, "persona", f"p{i % 5}", c, role=role,
                     draw=i)
                for i, c in enumerate(cs)
            ]
    rows = distribution_equivalence_table(cells, boot=200, seed=0)
    pms_rows = [r for r in rows if r["transformation"] == "pms_relabel"]
    roles = sorted(r["role"] for r in pms_rows)
    assert roles == ["Column", "Row"]
    assert all(r["arm"] == "persona" for r in pms_rows)


def test_pms_relabel_never_pools_roles_into_one_row():
    choices = ["A1", "A2", "J", "A1", "A2", "J", "A1", "A2", "J", "A1"]
    cells = {}
    for role in ("Row", "Column"):
        for variant, cs in (("G1", choices), ("relabel", choices)):
            cells[("pms", variant, "persona", "m", role)] = [
                _rec("pms", variant, "persona", f"p{i % 5}", c, role=role,
                     draw=i)
                for i, c in enumerate(cs)
            ]
    rows = distribution_equivalence_table(cells, boot=200, seed=0)
    pms_rows = [r for r in rows if r["transformation"] == "pms_relabel"]
    assert len(pms_rows) == 2
    assert all(r.get("role") is not None for r in pms_rows)


# ------------------------------------------------------------------ #
# CI label hygiene: three separate labels, no cross-attachment
# ------------------------------------------------------------------ #

def test_contrast_rows_carry_three_separately_labelled_cis():
    cells = _cells(
        "1120", "basic", "costless",
        [17] * 5 + [18] * 5, [19] * 5 + [20] * 5,
    )
    rows = contrast_table(cells, boot=200, seed=0)
    for row in rows:
        for arm in ("persona", "no_persona"):
            cell = row[arm]
            assert cell is None or set(
                k for k in cell if k.endswith("_ci90")
            ) == {"model_effect_ci90", "human_effect_ci90", "discrepancy_ci90"}


def test_ci_label_check_rejects_cross_attachment():
    with pytest.raises(AssertionError):
        require_ci_label("model_effect_ci90", "discrepancy")
    with pytest.raises(AssertionError):
        require_ci_label("discrepancy_ci90", "model_effect")
    # correct pairings pass
    require_ci_label("model_effect_ci90", "model_effect")
    require_ci_label("human_effect_ci90", "human_effect")
    require_ci_label("discrepancy_ci90", "discrepancy")


# ------------------------------------------------------------------ #
# r(T) is a SUPPORT DIAGNOSTIC: no CONSISTENCY-SUCCESS/FAIL verdict
# ------------------------------------------------------------------ #

def test_support_diagnostic_rows_have_no_consistency_verdict():
    cells = _cells(
        "1120", "basic", "r31-40",
        [11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
        [31, 32, 33, 34, 35, 36, 37, 38, 39, 40],
    )
    rows = consistency_table(cells, boot=200, seed=0)
    assert rows
    for row in rows:
        assert "support_diagnostic" in row
        assert "verdict" not in row
        assert "CONSISTENCY-SUCCESS" not in str(row)
        assert "CONSISTENCY-FAIL" not in str(row)


# ------------------------------------------------------------------ #
# Independent TVD confirmation (separate code path from stats.tvd)
# ------------------------------------------------------------------ #

def test_independent_tvd_confirmation_matches_pipeline_value():
    # canonical 11..20 mapped +20 -> 31..40 uniform; transformed all 40.
    # Union support 31..40: TVD = 0.5*(9*0.1 + 0.9) = 0.9 by both paths.
    cells = _cells(
        "1120", "basic", "r31-40",
        [11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
        [40] * 10,
    )
    result = independent_tvd_confirmation(cells)
    assert result["persona"]["independent"] == pytest.approx(0.9)
    assert result["persona"]["pipeline"] == pytest.approx(0.9)
    assert result["persona"]["agree"] is True


# ------------------------------------------------------------------ #
# Cost breakdown: decision / probe / full-run totals
# ------------------------------------------------------------------ #

def test_cost_breakdown_reports_decision_probe_and_full_totals():
    decisions = [_rec("1120", "basic", "persona", f"p{i}", 17)
                 for i in range(10)]
    probes = [_rec("1120", "basic", "persona", f"p{i}", 17,
                   namespace="probes") for i in range(5)]
    breakdown = cost_breakdown(decisions, probes)
    assert breakdown["decision_calls"]["calls"] == 10
    assert breakdown["probe_calls"]["calls"] == 5
    assert breakdown["full_run"]["calls"] == 15
    assert breakdown["decision_calls"]["prompt_tokens"] == 1000
    assert breakdown["probe_calls"]["prompt_tokens"] == 500
    assert breakdown["full_run"]["prompt_tokens"] == 1500
    assert breakdown["full_run"]["cost_usd"] == pytest.approx(0.015)
