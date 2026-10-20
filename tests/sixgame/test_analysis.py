"""Tests for the analysis: synthetic known cases plus a smoke run against
the existing exploratory results (choice counts must reproduce exactly)."""

import json
from collections import Counter
from pathlib import Path

import benchmarks
from analysis import (
    apply_exclusions,
    consistency_table,
    contrast_table,
    load_exploratory,
    pmf_for,
    run_analysis,
)


def _rec(game, variant, arm, persona, choice, draw=0, model="m"):
    return {
        "game": game,
        "variant": variant,
        "arm": arm,
        "model": model,
        "persona_id": persona,
        "draw_id": draw,
        "role": None,
        "choice": choice,
        "truncated": False,
        "finish_reason": "stop",
        "cache_status": "MISS",
        "error": None,
        "succeeded": True,
        "prompt_tokens": 100,
        "completion_tokens": 10,
        "cost_usd": 0.001,
        "raw_content": "",
    }


def test_pmf_on_synthetic_cell():
    records = [_rec("1120", "basic", "persona", f"p{i}", 17) for i in range(6)] + [
        _rec("1120", "basic", "persona", f"p{i}", 19) for i in range(4)
    ]
    pmf = pmf_for(records, range(11, 21))
    assert pmf[17] == 0.6 and pmf[19] == 0.4 and pmf[11] == 0.0


def test_exclusion_counts_reported_never_silent():
    records = [
        _rec("1120", "basic", "persona", "p0", 17),
        {**_rec("1120", "basic", "persona", "p1", None), "choice": None},
        {**_rec("1120", "basic", "persona", "p2", 18), "cache_status": "HIT"},
    ]
    kept, counts = apply_exclusions(records)
    assert len(kept) == 1
    assert counts["parse_failure"] == 1
    assert counts["cache_hit"] == 1


def test_contrast_delta_computed_against_frozen_human_effect():
    # Control: everyone picks 19.  Treatment: everyone picks 20.
    # LLM effect on 19 = -100pp; human effect basic->cycle on 19 = +35pp;
    # delta = -135pp regardless of arm.
    control = [_rec("1120", "basic", "persona", f"p{i}", 19) for i in range(10)]
    treatment = [_rec("1120", "cycle", "persona", f"p{i}", 20) for i in range(10)]
    rows = contrast_table(
        {
            ("1120", "basic", "persona"): control,
            ("1120", "cycle", "persona"): treatment,
        },
        boot=200,
        seed=1,
    )
    row = [
        r for r in rows if r["contrast"] == "H1_basic_to_cycle" and r["action"] == 19
    ][0]
    assert row["persona"]["effect_llm_pp"] == -100.0
    assert row["persona"]["effect_human_pp"] == 35.0
    assert row["persona"]["delta_pp"] == -135.0
    assert row["persona"]["ci90"][0] < row["persona"]["ci90"][1]


def test_tost_flag_inside_and_outside_margin():
    control = [_rec("1120", "basic", "persona", f"p{i}", 17) for i in range(20)]
    treatment = [_rec("1120", "costless", "persona", f"p{i}", 17) for i in range(20)]
    rows = contrast_table(
        {
            ("1120", "basic", "persona"): control,
            ("1120", "costless", "persona"): treatment,
        },
        boot=200,
        seed=1,
    )
    row = [r for r in rows if r["action"] == 19][0]
    # effect = 0 - (-100... no: human effect +28; LLM 0 -> delta -28pp,
    # outside the +-20pp margin -> TOST must be False.
    assert row["persona"]["delta_pp"] == -28.0
    assert row["persona"]["tost_within_delta"] is False


def test_consistency_r_t_is_one_when_choices_follow_mapping():
    canonical = [
        _rec("1120", "basic", "persona", f"p{i}", 20 - (i % 4)) for i in range(20)
    ]
    # r31-40 maps x ↦ x+20 (audited rule), so the mapped image of
    # {17..20} is {37..40}; consistency is distribution-level, so the
    # transformed mass must sit on that image set, not pair pointwise.
    transformed = [
        _rec("1120", "r31-40", "persona", f"p{i}", 40 - (i % 4)) for i in range(20)
    ]
    rows = consistency_table(
        {
            ("1120", "basic", "persona"): canonical,
            ("1120", "r31-40", "persona"): transformed,
        },
        boot=200,
        seed=1,
    )
    row = rows[0]
    assert row["r_T"] == 1.0
    assert row["verdict"] == "CONSISTENCY-SUCCESS"


def test_consistency_inverted_counts_mapped_level_k_answers():
    canonical = [_rec("1120", "basic", "persona", f"p{i}", 19) for i in range(10)]
    # Mapped answer under the inverted bonus for 19 is 12.
    good = [_rec("1120", "inverted", "persona", f"p{i}", 12) for i in range(8)]
    bad = [_rec("1120", "inverted", "persona", f"p{i}", 19) for i in range(2)]
    rows = consistency_table(
        {
            ("1120", "basic", "persona"): canonical,
            ("1120", "inverted", "persona"): good + bad,
        },
        boot=200,
        seed=1,
    )
    row = rows[0]
    assert abs(row["r_T"] - 0.8) < 1e-9


def test_die_roll_tier_compared_distributionally():
    private = [_rec("dieroll", "private", "persona", f"p{i}", 6) for i in range(10)]
    identical = [_rec("dieroll", "neutral", "persona", f"p{i}", 6) for i in range(10)]
    rows = consistency_table(
        {
            ("dieroll", "private", "persona"): private,
            ("dieroll", "neutral", "persona"): identical,
        },
        boot=200,
        seed=1,
    )
    assert rows[0]["kind"] == "distributional"
    assert rows[0]["tvd"] == 0.0
    assert rows[0]["tier_margin_pp"] == benchmarks.DELTA_DIE_TIER_A_PP


def test_exploratory_choice_counts_reproduce_exactly():
    fixtures = sorted(
        Path(__file__).parent.joinpath("fixtures").glob("*_cond*_11-20.jsonl")
    )
    assert fixtures, "exploratory fixtures missing"
    expected = {
        "anthropic_claude-sonnet-5": {
            2: {11: 1, 14: 2, 15: 1, 16: 3, 17: 11, 18: 2},
            3: {17: 14, 18: 3, 19: 3},
        },
        "deepseek-v4-flash": {
            2: {16: 1, 18: 4, 19: 15},
            3: {18: 1, 19: 18, 20: 1},
        },
        "openai_gpt-5.6-luna": {2: {19: 20}, 3: {19: 20}},
    }
    for path in fixtures:
        name = path.name
        model_key = next(k for k in expected if name.startswith(k))
        cond = 2 if "_cond2_" in name else 3
        records = load_exploratory([path])
        counts = Counter(r["choice"] for r in records)
        assert dict(counts) == expected[model_key][cond], name
        arm = "no_persona" if cond == 2 else "persona"
        assert all(r["arm"] == arm for r in records)
        assert all(r["variant"] == "basic" for r in records)


def test_full_analysis_smoke_on_exploratory_fixtures():
    fixtures = sorted(
        Path(__file__).parent.joinpath("fixtures").glob("*_cond*_11-20.jsonl")
    )
    output = run_analysis(exploratory_paths=fixtures, boot=100, seed=0)
    counts = output["exploratory_choice_counts"]
    total = sum(sum(c.values()) for c in counts.values())
    assert total == 120  # 6 files x 20 personas
    # every file produced a cell keyed with the right arm split
    import ast

    arms = {ast.literal_eval(key)[2] for key in counts}
    assert arms == {"persona", "no_persona"}


def test_analysis_regenerates_from_raw_jsonl_alone(tmp_path):
    records = [_rec("1120", "basic", "persona", f"p{i}", 17) for i in range(5)]
    path = tmp_path / "cell.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    output = run_analysis([path], boot=100, seed=0)
    key = str(("1120", "basic", "persona", "m"))
    assert output["pmfs"][key][17] == 1.0
    text = json.dumps(output)
    assert "exclusions" in text and "cost_and_tokens" in text
