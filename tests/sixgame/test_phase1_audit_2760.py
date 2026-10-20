"""TASK-2760 phase-1 offline audit safeguards.

These tests lock in the phase-1 scientific audit: the stake10 equivalence
fix (n=10/cell degenerate bootstrap intervals can never establish
equivalence), the data-hygiene lineage guarantees (flawed original run,
temp-0 exploratory files and response-cached completions can never enter
a new analysis), the frozen constants and mappings, and the immutability
and labelling of historical reports.  All offline — no model calls.
"""

import hashlib
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from analysis import apply_exclusions, recognition_stratification
from data_root import default_data_root, verify_manifest
from distribution import (
    NO_DIFFERENCE_VERDICT,
    distribution_equivalence_table,
    equivalence_verdict,
)
from games import PMS_PI, level_k_inverted_table, variant_spec
from lineage import classify_input, record_cache_class
from runner import persona_text_for
import benchmarks


# ------------------------------------------------------------------ #
# helpers
# ------------------------------------------------------------------ #

def _die_rec(game, variant, arm, persona, choice, model="m"):
    return {
        "game": game,
        "variant": variant,
        "arm": arm,
        "model": model,
        "persona_id": persona,
        "draw_id": 0,
        "role": None,
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


def _die_cells(can_choices, tra_choices, arm="no_persona"):
    """dieroll private/stake10 cells: 5 personas x 2 draws each."""
    records = []
    for i, choice in enumerate(can_choices):
        records.append(_die_rec("dieroll", "private", arm, f"p{i % 5}", choice))
    for i, choice in enumerate(tra_choices):
        records.append(_die_rec("dieroll", "stake10", arm, f"p{i % 5}", choice))
    cells = {}
    for r in records:
        cells.setdefault((r["game"], r["variant"], r["arm"], r["model"]), []).append(r)
    return cells


def _stake10_row(rows, arm):
    return [r for r in rows if r["transformation"] == "dieroll_stake10_tierB"
            and r["arm"] == arm][0]


# ------------------------------------------------------------------ #
# Safeguard 1: stake10 EQUIVALENT fix (verdict machinery, not strings)
# ------------------------------------------------------------------ #

def test_stake10_degenerate_ci_zero_tvd_cannot_claim_equivalent():
    # Mirrors the real corrective-run no_persona stake10 cell: all ten
    # draws report 6 on both sides -> TVD point 0.0, degenerate [0,0]
    # bootstrap CI.  With n=10 per cell this must NOT be EQUIVALENT.
    cells = _die_cells([6] * 10, [6] * 10)
    rows = distribution_equivalence_table(cells, boot=500, seed=0)
    row = _stake10_row(rows, "no_persona")
    assert row["tvd"] == pytest.approx(0.0)
    assert row["verdict"] != "EQUIVALENT"
    assert row["verdict"] == NO_DIFFERENCE_VERDICT


def test_equivalence_verdict_refuses_degenerate_interval_without_sample_info():
    # A degenerate interval with no finite-sample support can never
    # yield EQUIVALENT, even with a frozen margin.
    assert equivalence_verdict(15.0, [0.0, 0.0]) == NO_DIFFERENCE_VERDICT


def test_equivalence_verdict_needs_defensible_finite_sample_interval():
    # Even a non-degenerate CI inside the margin is refused when the
    # sample is too small for the finite-sample bound to support the
    # frozen margin (n=10 per side, 6 categories).
    verdict = equivalence_verdict(15.0, [0.0, 0.04], n_can=10, n_tra=10,
                                  n_categories=6)
    assert verdict == NO_DIFFERENCE_VERDICT


def test_equivalence_verdict_allows_equivalence_with_defensible_interval():
    # With a large sample the finite-sample bound (point + slack) sits
    # below the frozen margin, so EQUIVALENT is reachable again.
    verdict = equivalence_verdict(15.0, [0.0, 0.04], n_can=2000, n_tra=2000,
                                  n_categories=6)
    assert verdict == "EQUIVALENT"


def test_stake10_equivalence_note_present_in_table_and_report():
    from analysis import run_analysis
    from report import render_markdown
    cells = _die_cells([6] * 10, [6] * 10)
    rows = distribution_equivalence_table(cells, boot=500, seed=0)
    row = _stake10_row(rows, "no_persona")
    assert "equivalence NOT established" in row["equivalence_note"]
    output = {"distribution_equivalence": rows}
    md = render_markdown(output)
    assert "equivalence NOT established" in md
    assert "no difference observed in sample" in row["equivalence_note"]


# ------------------------------------------------------------------ #
# Safeguard 2: data-hygiene lineage
# ------------------------------------------------------------------ #

def test_flawed_original_run_is_excluded_from_lineage():
    verdict = classify_input(
        Path("~/experiment-data/fos/sixgame/engineering_pilot/"
              "decisions_1120_basic_no_persona_deepseek-v4-flash.jsonl")
    )
    assert verdict["status"] == "EXCLUDED"
    assert verdict["run_id"] == "engineering_pilot"


def test_temp0_exploratory_files_are_excluded_from_lineage():
    verdict = classify_input(
        Path("~/Documents/ZJU work/fos/results/"
              "deepseek-v4-flash_cond2_11-20.jsonl")
    )
    assert verdict["status"] == "EXCLUDED"
    verdict3 = classify_input(
        Path("~/Documents/ZJU work/fos/results/"
             "deepseek-v4-flash_cond3_11-20.jsonl")
    )
    assert verdict3["status"] == "EXCLUDED"


def test_corrective_run_files_are_included_in_lineage():
    verdict = classify_input(
        Path("~/experiment-data/fos/sixgame/engineering_pilot_corrective/"
              "decisions_dieroll_stake10_no_persona_deepseek-v4-flash.jsonl")
    )
    assert verdict["status"] == "INCLUDED"
    assert verdict["run_id"] == "engineering_pilot_corrective"


def test_prior_audit_reports_are_marked_superseded():
    verdict = classify_input(
        Path("~/experiment-data/fos/sixgame/engineering_pilot_corrective/"
              "reports/audited_v2/analysis.json")
    )
    assert verdict["status"] == "SUPERSEDED"


def test_response_cache_record_class_is_detectable():
    assert record_cache_class({"cache_kind": "response"}) == "response"
    assert record_cache_class({"cache_kind": "context"}) == "context"
    assert record_cache_class({"cache_status": "MISS"}) == "legacy_miss"


def test_response_cache_records_are_excluded_context_kept():
    response_hit = _die_rec("dieroll", "stake10", "no_persona", "p0", 6)
    response_hit.update({"cache_kind": "response", "cache_status": "HIT"})
    context_hit = _die_rec("dieroll", "stake10", "no_persona", "p0", 6)
    context_hit.update({"cache_kind": "context", "cache_status": "HIT"})
    kept, counts = apply_exclusions([response_hit, context_hit])
    assert len(kept) == 1
    assert kept[0]["cache_kind"] == "context"
    assert counts["cache_hit"] == 1


# ------------------------------------------------------------------ #
# Safeguard 3: frozen constants and mappings
# ------------------------------------------------------------------ #

def test_human_benchmarks_match_frozen_document():
    # Values copied verbatim from HUMAN_BENCHMARKS.md (frozen).
    assert benchmarks.PMF_1120["basic"] == [4, 0, 3, 6, 1, 6, 32, 30, 12, 6]
    assert benchmarks.PMF_1120["costless"] == [0, 4, 0, 4, 4, 4, 9, 21, 40, 15]
    assert benchmarks.PMF_1120["cycle"] == [1, 1, 0, 1, 0, 4, 10, 22, 47, 13]
    assert benchmarks.N_HUMAN_1120 == {"basic": 108, "costless": 53, "cycle": 72}
    assert benchmarks.EFFECTS_1120["basic_to_costless"] == {
        17: -23.0, 18: -9.0, 19: 28.0, 20: 9.0,
    }
    assert benchmarks.EFFECTS_1120["basic_to_cycle"] == {
        17: -22.0, 18: -8.0, 19: 35.0, 20: 7.0,
    }
    assert benchmarks.PMF_DIE["private"] == [3.1, 1.5, 6.2, 18.5, 32.3, 38.5]
    assert benchmarks.PMF_DIE["public"] == [4.6, 7.7, 13.8, 21.5, 23.1, 29.2]
    assert benchmarks.EFFECT_DIE_SHARE6_PP == -9.2
    assert benchmarks.FREQ_PMS["G1"]["Row"] == (0.273, 0.349, 0.378)
    assert benchmarks.FREQ_PMS["G4"]["Column"] == (0.487, 0.147, 0.366)
    assert benchmarks.EFFECT_PMS_PP["Row"] == (20.0, -12.9, -7.1)
    assert benchmarks.EFFECT_PMS_PP["Column"] == (16.2, -16.1, -0.1)
    assert benchmarks.DELTA_1120_PP == 20.0
    assert benchmarks.DELTA_DIE_PP == 25.0
    assert benchmarks.DELTA_DIE_TIER_A_PP == 5.0
    assert benchmarks.DELTA_DIE_TIER_B_PP == 15.0
    assert benchmarks.DELTA_PMS_PP == 25.0


def test_frozen_mappings_r31_40_shift_plus_20():
    mapping = variant_spec("1120", "r31-40").mapping
    assert mapping(11) == 31 and mapping(19) == 39 and mapping(20) == 40


def test_frozen_mapping_inverted_is_31_minus_x():
    table = level_k_inverted_table()
    assert table[20] == 11 and table[17] == 14  # x -> 31 - x
    assert variant_spec("1120", "inverted").mapping(20) == 11


def test_frozen_relabel_pi_mapping():
    assert PMS_PI == {"A1": "J", "A2": "A1", "J": "A2"}
    assert variant_spec("pms", "relabel").mapping("A1") == "J"


def test_no_persona_prompts_never_embed_biography():
    sample = SimpleNamespace(arm="no_persona", persona_id="anyone")
    assert persona_text_for(sample, Path("/nonexistent")) is None


def test_recognition_denominators_are_5_per_cell_30_per_arm():
    # A full arm: 6 cells x 5 probes = 30; every cell denominator is 5.
    probes = []
    for game, variant in (
        ("1120", "r11-20"), ("1120", "r31-40"),
        ("dieroll", "private"), ("dieroll", "public"),
        ("pms", "G1"), ("pms", "G4"),
    ):
        for i in range(5):
            probes.append({
                "game": game, "variant": variant, "arm": "persona",
                "raw_content": "NOT RECOGNISING",
            })
    out = recognition_stratification(probes)
    assert len(out) == 6
    assert all(entry["n"] == 5 for entry in out.values())
    assert sum(entry["n"] for entry in out.values()) == 30


def test_sample_allocation_is_10_draws_per_cell_5_personas():
    # Offline check against the frozen corrective run's raw JSONL.
    run = default_data_root() / "engineering_pilot_corrective"
    if not run.exists():
        pytest.skip("corrective run data not present")
    decision_files = sorted(run.glob("decisions_*.jsonl"))
    assert len(decision_files) == 18
    for path in decision_files:
        n = sum(1 for line in path.read_text().splitlines() if line.strip())
        assert n == 10, f"{path.name} has {n} records"
        personas = {
            __import__("json").loads(line)["persona_id"]
            for line in path.read_text().splitlines() if line.strip()
        }
        assert len(personas) == 5, f"{path.name} has {len(personas)} personas"


# ------------------------------------------------------------------ #
# Safeguard 4: historical files immutable + labelled
# ------------------------------------------------------------------ #

def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_preserved_datasets_unchanged_against_manifest():
    root = default_data_root()
    manifest = root / "PRESERVATION_MANIFEST.sha256"
    if not manifest.exists():
        pytest.skip("preservation manifest not present")
    problems = verify_manifest(root, manifest)
    assert problems == []


def test_historical_report_dirs_carry_superseded_label():
    reports = (default_data_root()
               / "engineering_pilot_corrective" / "reports")
    for version in ("audited", "audited_v2"):
        label = reports / version / "SUPERSEDED-2760.md"
        assert label.exists(), f"{label} missing"
        text = label.read_text()
        assert "SUPERSEDED" in text
        assert "not readable as current" in text or "superseded" in text.lower()
