# Tests for twin2k10r/pool_builder.py — the deterministic sampling and
# persona-mapping module.
# WHAT THESE TESTS CHECK, in plain words:
#   - The same seed always picks exactly the same people; changing the
#     seed by 1 changes at least one pick (it is genuinely seed-driven).
#   - Stratified sampling on gender x age bracket uses the largest-
#     remainder rule, samples without replacement, and returns exactly
#     n=100 sorted pids.
#   - map_fields hands back ONLY whitelisted keys, with the dataset's own
#     label text; the 4 unavailable fields are simply absent — no
#     placeholders like "N/A".
#   - Config B personas carry exactly 18 keys: 7 demographics + 11
#     measured scores; blocklisted task scores raise.
#   - Writing the pool file twice produces byte-identical files.
#   - The provenance record holds everything needed to replay the sample.
import json

import pytest

from conftest import (
    N_FIXTURE_RESPONDENTS,
    SCORE_WHITELIST,
)


CONFIG_A_KEYS = (
    "age_bracket",
    "gender",
    "education",
    "household_income_bracket",
    "ethnicity",
    "marital_status",
    "household_size_bracket",
)
EXCLUDED_FIELDS = ("occupation", "number_of_children", "state", "home_ownership")


# ---------- 1. Determinism ----------

def test_same_seed_gives_identical_pid_list(fixture_respondents):
    """Same respondents + same seed -> byte-identical pid list."""
    from twin2k10r import pool_builder

    first = pool_builder.sample_respondents(fixture_respondents, n=100, seed=42)
    second = pool_builder.sample_respondents(fixture_respondents, n=100, seed=42)
    assert first == second, "same seed must reproduce the same sample"


def test_seed_plus_one_changes_at_least_one_pid(fixture_respondents):
    """A different seed must change at least one pick (no constant sampler)."""
    from twin2k10r import pool_builder

    base = pool_builder.sample_respondents(fixture_respondents, n=100, seed=42)
    shifted = pool_builder.sample_respondents(fixture_respondents, n=100, seed=43)
    assert set(base) != set(shifted) or base != shifted, (
        "seed+1 must change at least one pid"
    )


# ---------- 2. Stratified sampling properties ----------

def test_sample_returns_exactly_n_sorted_pids(fixture_respondents):
    """Exactly n=100 pids, sorted ascending, no duplicates."""
    from twin2k10r import pool_builder

    pids = pool_builder.sample_respondents(fixture_respondents, n=100, seed=42)
    assert len(pids) == 100
    assert len(set(pids)) == 100, "sampling must be without replacement"
    assert pids == sorted(pids), "pid list must be ascending sorted"
    assert len(set(pids) & set(fixture_respondents["pid"])) == 100


def test_sample_without_replacement_never_repeats(fixture_respondents):
    """A larger-than-frame request is refused, and no pid repeats."""
    from twin2k10r import pool_builder

    with pytest.raises(Exception):
        pool_builder.sample_respondents(
            fixture_respondents, n=N_FIXTURE_RESPONDENTS + 1, seed=42
        )


def test_stratified_marginals_track_panel_exactly_by_construction(
    fixture_respondents,
):
    """Sex x age strata proportions match the panel (largest remainder)."""
    from twin2k10r import pool_builder

    pids = pool_builder.sample_respondents(fixture_respondents, n=100, seed=42)
    panel = fixture_respondents
    total = len(panel)
    for gender in sorted(panel["gender"].unique()):
        for age in sorted(panel["age_bracket"].unique()):
            stratum_share = len(
                panel[(panel["gender"] == gender) & (panel["age_bracket"] == age)]
            ) / total
            expected = stratum_share * 100
            got = len([
                p for p in pids
                if panel.loc[panel["pid"] == p, "gender"].iloc[0] == gender
                and panel.loc[panel["pid"] == p, "age_bracket"].iloc[0] == age
            ])
            # Largest-remainder: each stratum is within 1 seat of exact.
            assert abs(got - expected) <= 1.0 + 1e-9, (
                f"stratum {gender}/{age}: got {got}, expected ~{expected:.2f}"
            )


def test_strata_argument_can_widen_to_all_seven_fields(fixture_respondents):
    """Strata is configurable; other columns work as strata too."""
    from twin2k10r import pool_builder

    pids = pool_builder.sample_respondents(
        fixture_respondents, n=100, seed=42,
        strata=("gender", "age_bracket", "education"),
    )
    assert len(pids) == 100 and pids == sorted(pids)


# ---------- 3. map_fields — whitelist only, verbatim labels ----------

def test_map_fields_config_a_has_exactly_seven_whitelisted_keys(
    fixture_respondents,
):
    """A persona dict carries exactly the 7 Config A keys — no extras."""
    from twin2k10r import pool_builder

    persona = pool_builder.map_fields(1, fixture_respondents, "A")
    assert set(persona.keys()) == set(CONFIG_A_KEYS), set(persona.keys())


def test_map_fields_values_are_verbatim_dataset_label_text(fixture_respondents):
    """Values come straight from the dataset labels: "50-64", "$100,000
    or more", "More than 4" — never reworded, never numeric codes."""
    from twin2k10r import pool_builder

    persona = pool_builder.map_fields(1, fixture_respondents, "A")
    assert persona["age_bracket"] in {"18-29", "30-49", "50-64", "65+"}
    assert persona["gender"] in {"Male", "Female"}
    assert persona["household_size_bracket"] in {
        "1", "2", "3", "4", "More than 4",
    }


def test_map_fields_matches_the_actual_respondent_row(fixture_respondents):
    """Each persona value equals the panel record of that same pid."""
    from twin2k10r import pool_builder

    pid = sorted(fixture_respondents["pid"])[5]
    persona = pool_builder.map_fields(pid, fixture_respondents, "A")
    row = fixture_respondents[fixture_respondents["pid"] == pid].iloc[0]
    for key in CONFIG_A_KEYS:
        assert persona[key] == row[key], f"pid {pid} field {key} mismatched"


def test_map_fields_excluded_fields_are_absent_not_placeholders(
    fixture_respondents,
):
    """The 4 unavailable fields are missing keys — never "", "N/A", None."""
    from twin2k10r import pool_builder

    persona = pool_builder.map_fields(1, fixture_respondents, "A")
    for field in EXCLUDED_FIELDS:
        assert field not in persona, f"{field} must be an absent key"


def test_map_fields_rejects_unknown_config(fixture_respondents):
    """Config "C" raises; the whitelist is the only source of keys."""
    from twin2k10r import pool_builder

    with pytest.raises(Exception):
        pool_builder.map_fields(1, fixture_respondents, "C")


# ---------- 4. Config B scores ----------

def test_config_b_persona_has_exactly_eighteen_keys(fixture_respondents):
    """Config B: 7 demographics + 11 measured scores = 18 keys exactly."""
    from twin2k10r import pool_builder

    persona = pool_builder.map_fields(1, fixture_respondents, "B")
    assert len(persona) == 18
    assert set(persona) == set(CONFIG_A_KEYS) | set(SCORE_WHITELIST)


def test_config_b_scores_match_scores_file(fixture_respondents, fixture_dataset_root):
    """Score values are the measured ones from 'wave 1 scores.csv'."""
    import pandas as pd

    from twin2k10r import pool_builder

    persona = pool_builder.map_fields(1, fixture_respondents, "B")
    scores = pd.read_csv(fixture_dataset_root / "raw_data" / "wave 1 scores.csv")
    row = scores[scores["TWIN_ID"] == 1].iloc[0]
    for score in SCORE_WHITELIST:
        assert float(persona[score]) == float(row[score]), (
            f"{score} does not match the scores file"
        )


def test_blocklisted_scores_raise(fixture_respondents):
    """Requesting a task-performance score raises — hard blocklist."""
    from twin2k10r import pool_builder

    with pytest.raises(Exception):
        pool_builder.map_fields(1, fixture_respondents, "B", extra_fields=("crt2_score",))
    with pytest.raises(Exception):
        pool_builder.map_fields(
            1, fixture_respondents, "B", extra_fields=("score_overconfidence",)
        )


# ---------- 5. write_pool — idempotent bytes + provenance ----------

def test_write_pool_is_idempotent_byte_identical(
    fixture_respondents, tmp_path
):
    """Writing the pool twice yields byte-identical JSONL and provenance."""
    from twin2k10r import pool_builder

    pids = pool_builder.sample_respondents(fixture_respondents, n=100, seed=42)
    out1 = tmp_path / "a" / "twin2k_respondent.jsonl"
    out2 = tmp_path / "b" / "twin2k_respondent.jsonl"
    prov1 = pool_builder.write_pool(pids, fixture_respondents, "A", out1)
    prov2 = pool_builder.write_pool(pids, fixture_respondents, "A", out2)
    assert out1.read_bytes() == out2.read_bytes(), "pool file must be byte-identical"
    p1 = out1.parent / "POOL_PROVENANCE.json"
    p2 = out2.parent / "POOL_PROVENANCE.json"
    assert p1.read_bytes() == p2.read_bytes(), "provenance must be byte-identical"
    assert prov1["pool_sha256"] == prov2["pool_sha256"]


def test_pool_file_is_100_lines_with_ids_zero_to_99(
    fixture_respondents, tmp_path
):
    """The pool is 100 JSONL lines; line order = pool id 0..99."""
    from twin2k10r import pool_builder

    pids = pool_builder.sample_respondents(fixture_respondents, n=100, seed=42)
    out = tmp_path / "twin2k_respondent.jsonl"
    pool_builder.write_pool(pids, fixture_respondents, "A", out)
    lines = out.read_text().splitlines()
    assert len(lines) == 100
    for i, line in enumerate(lines):
        record = json.loads(line)
        assert record["pid"] == pids[i], f"line {i} must carry the {i}-th pid"


# ---------- 6. Provenance contents ----------

def test_provenance_record_is_complete(fixture_respondents, tmp_path):
    """POOL_PROVENANCE.json holds seed, RNG name, pids, hashes, config,
    whitelist, and the 4 excluded fields with reasons."""
    from twin2k10r import pool_builder

    pids = pool_builder.sample_respondents(fixture_respondents, n=100, seed=42)
    out = tmp_path / "twin2k_respondent.jsonl"
    prov = pool_builder.write_pool(pids, fixture_respondents, "A", out)

    assert prov["seed"] == 42
    assert prov["rng_algorithm"] == "numpy PCG64"
    assert prov["n"] == 100
    assert prov["config_id"] == "A"
    assert prov["pid"] == sorted(pids)
    assert len(prov["pool_sha256"]) == 64
    assert len(prov["dataset_manifest_sha256"]) == 64
    assert "pipeline_git_sha" in prov
    assert set(prov["field_whitelist"]) == set(CONFIG_A_KEYS)
    excluded = prov["excluded_fields"]
    for field in EXCLUDED_FIELDS:
        assert field in excluded, f"excluded_fields must list {field}"
        reason = excluded[field]
        assert isinstance(reason, str) and len(reason) > 0, (
            f"{field} needs a reason string"
        )
    # allocation table per stratum
    assert "strata" in prov and "allocation" in prov


def test_provenance_pool_sha_matches_pool_file_bytes(
    fixture_respondents, tmp_path
):
    """pool_sha256 in the provenance equals the pool file's real sha256."""
    import hashlib

    from twin2k10r import pool_builder

    pids = pool_builder.sample_respondents(fixture_respondents, n=100, seed=42)
    out = tmp_path / "twin2k_respondent.jsonl"
    prov = pool_builder.write_pool(pids, fixture_respondents, "A", out)
    actual = hashlib.sha256(out.read_bytes()).hexdigest()
    assert prov["pool_sha256"] == actual


def test_provenance_config_b_whitelist_has_eighteen_names(
    fixture_respondents, tmp_path
):
    """Config B provenance lists all 18 whitelisted field names."""
    from twin2k10r import pool_builder

    pids = pool_builder.sample_respondents(fixture_respondents, n=100, seed=42)
    out = tmp_path / "twin2k_respondent.jsonl"
    prov = pool_builder.write_pool(pids, fixture_respondents, "B", out)
    assert len(prov["field_whitelist"]) == 18
    assert set(SCORE_WHITELIST) <= set(prov["field_whitelist"])
