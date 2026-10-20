"""Regression tests for the TASK-2750 audited analysis fixes.

These tests lock in the corrected behaviour diagnosed in RESULT-2749:
PMS label/role contrasts, the +20 mapping for the 31-40 rung,
distribution-level consistency, an MD report rendered from analysis.json,
per-arm recognition tables, and the keep-context-cache rule.
"""

from analysis import (
    apply_exclusions,
    consistency_table,
    contrast_table,
    recognition_stratification,
    render_markdown,
)
from games import variant_spec


def _rec(game, variant, arm, persona, choice, role=None, draw=0, model="m"):
    return {
        "game": game,
        "variant": variant,
        "arm": arm,
        "model": model,
        "persona_id": persona,
        "draw_id": draw,
        "role": role,
        "choice": choice,
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


def _cells(records):
    cells = {}
    for r in records:
        cells.setdefault((r["game"], r["variant"], r["arm"], r["model"]), []).append(r)
    return cells


def test_pms_contrast_uses_labels_and_roles():
    # Control: 4 Row players all chose A2. Treatment: 4 Row players all
    # chose A1. The model effect on A1 must be +100pp for the Row role.
    records = [
        _rec("pms", "G1", "persona", f"p{i}", "A2", role="Row") for i in range(4)
    ] + [
        _rec("pms", "G4", "persona", f"p{i}", "A1", role="Row") for i in range(4)
    ]
    rows = contrast_table(_cells(records), boot=200, seed=0)
    h3 = [r for r in rows if r["contrast"] == "H3_pms_G1_to_G4_row"]
    assert h3, "H3 row contrast missing"
    row_a1 = [r for r in h3 if r["action"] == "A1"][0]
    assert row_a1["role"] == "Row"
    assert row_a1["persona"]["effect_llm_pp"] == 100.0
    # Column records must never be pooled into the Row row: a column-only
    # control keeps the Row effect at the Row-only value.
    column_only = [
        _rec("pms", "G1", "persona", f"q{i}", "J", role="Column") for i in range(4)
    ] + [
        _rec("pms", "G4", "persona", f"q{i}", "J", role="Column") for i in range(4)
    ]
    rows2 = contrast_table(_cells(records + column_only), boot=200, seed=0)
    row_a1b = [
        r
        for r in rows2
        if r["contrast"] == "H3_pms_G1_to_G4_row" and r["action"] == "A1"
    ][0]
    assert row_a1b["persona"]["effect_llm_pp"] == 100.0


def test_range_shift_r31_40_maps_plus_20():
    assert variant_spec("1120", "r31-40").mapping(19) == 39
    assert variant_spec("1120", "r31-40").mapping(15) == 35
    # Neighbouring rungs keep their own offsets.
    assert variant_spec("1120", "r21-30").mapping(19) == 29
    assert variant_spec("1120", "r11-20").mapping(19) == 19
    assert variant_spec("1120", "r41-50").mapping(19) == 49


def test_consistency_is_distribution_level():
    # Canonical support {15, 18, 19}; transformed draws all 39 = image of
    # 19 under the +20 mapping -> share of mass on the image set is 1.0.
    can = [
        _rec("1120", "basic", "persona", f"p{i}", c)
        for i, c in enumerate([15, 18, 19, 19, 15])
    ]
    tra = [_rec("1120", "r31-40", "persona", f"p{i}", 39) for i in range(5)]
    rows = consistency_table(_cells(can + tra), boot=200, seed=0)
    row = [r for r in rows if r["transformation"] == "1120_r31-40"][0]
    assert row["r_T"] == 1.0
    assert "js_divergence" in row, "distribution-level statistic missing"
    # A 9/10 case: one draw (40) lands off the image {35, 36, 38, 39}.
    can2 = [
        _rec("1120", "basic", "no_persona", f"p{i}", c)
        for i, c in enumerate([15, 16, 18, 19, 15])
    ]
    tra2 = [
        _rec("1120", "r31-40", "no_persona", f"p{i}", c)
        for i, c in enumerate([38, 38, 38, 38, 38, 39, 39, 39, 39, 40])
    ]
    rows2 = consistency_table(_cells(can2 + tra2), boot=200, seed=0)
    row2 = [r for r in rows2 if r["transformation"] == "1120_r31-40"][0]
    assert row2["r_T"] == 0.9


def test_md_report_matches_analysis_json():
    output = {
        "pmfs": {
            "('1120', 'basic', 'persona', 'm')": {
                17: 0.3,
                19: 0.7,
            }
        },
        "contrasts": [
            {
                "contrast": "H1_basic_to_costless",
                "action": 19,
                "role": None,
                "persona": {
                    "effect_llm_pp": 11.9,
                    "effect_human_pp": 20.0,
                    "delta_pp": -8.1,
                    "ci90": [-30.0, 13.8],
                },
                "no_persona": None,
            }
        ],
        "recognition": {
            "1120/r11-20/persona": {
                "n": 5,
                "RECOGNISING": 4,
                "NOT_RECOGNISING": 1,
                "UNKNOWN": 0,
                "rates": {"RECOGNISING": 0.8},
            }
        },
        "exclusions": {},
    }
    md = render_markdown(output)
    # Every PMF number in the MD comes from the dict, as a percentage.
    assert "70.0%" in md
    assert "30.0%" in md
    # Every contrast row shows the three quantities explicitly.
    assert "11.9" in md  # model effect
    assert "20.0" in md  # human effect (frozen benchmark)
    assert "-8.1" in md  # discrepancy delta
    # Recognition table shows the denominator and the rate.
    assert "n=5" in md
    assert "80.0%" in md


def test_recognition_tables_split_by_arm():
    probes = []
    for i in range(4):
        probes.append(
            _rec("1120", "r11-20", "persona", f"p{i}", 17).update({"x": 1})
            or {
                **_rec("1120", "r11-20", "persona", f"p{i}", 17),
                "raw_content": "this is the 11-20 game by Arad",
            }
        )
    probes.append(
        {
            **_rec("1120", "r11-20", "persona", "p9", 17),
            "raw_content": "no idea what this is",
        }
    )
    for i in range(3):
        probes.append(
            {
                **_rec("1120", "r11-20", "no_persona", f"q{i}", 17),
                "raw_content": "this is the 11-20 game by Arad",
            }
        )
    for i in range(2):
        probes.append(
            {
                **_rec("1120", "r11-20", "no_persona", f"q{i}", 17),
                "raw_content": "no idea what this is",
            }
        )
    tables = recognition_stratification(probes)
    persona = tables["1120/r11-20/persona"]
    no_persona = tables["1120/r11-20/no_persona"]
    assert persona["n"] == 5
    assert no_persona["n"] == 5
    assert persona["RECOGNISING"] == 4
    assert no_persona["RECOGNISING"] == 3
    assert persona["rates"]["RECOGNISING"] == 0.8


def test_context_cache_records_are_included():
    records = [
        {**_rec("1120", "basic", "persona", f"p{i}", 17), "cache_kind": "context"}
        for i in range(10)
    ]
    kept, counts = apply_exclusions(records)
    assert len(kept) == 10
    assert counts == {}
