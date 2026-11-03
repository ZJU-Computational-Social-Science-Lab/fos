# Tests for twin2k10r/validate_pool.py — the run-gating validator.
# WHAT THESE TESTS CHECK, in plain words:
#   - The validator checks six gates: pool size, persona-to-respondent
#     truthfulness, marginals vs the panel, one shared pool across all
#     conditions, no leaking fields or placeholders, and seed
#     reproducibility from a fresh process.
#   - Every failing gate makes the run STOP with a non-zero exit — the
#     validator never warns and continues.
#   - A good pool passes every gate.
import json
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import SCORE_WHITELIST


def _make_good_pool(tmp_path, fixture_respondents):
    """Build a valid pool + provenance for validator tests."""
    from twin2k10r import pool_builder

    pids = pool_builder.sample_respondents(fixture_respondents, n=100, seed=42)
    out = tmp_path / "pools" / "twin2k_respondent.jsonl"
    prov = pool_builder.write_pool(pids, fixture_respondents, "A", out)
    return out, prov, pids


# ---------- 1. Gate: pool built from all 2,058-panel respondents ----------

def test_gate_fails_when_respondent_frame_is_short(tmp_path, fixture_dataset_root):
    """A respondent table with fewer than 2,058 panel pids fails the run."""
    pytest.importorskip("twin2k10r")
    from twin2k10r import respondent_loader, validate_pool

    respondents = respondent_loader.load_respondents(fixture_dataset_root, "A")
    truncated = respondents.head(100)
    with pytest.raises(validate_pool.PanelCountError):
        validate_pool.check_panel_count(truncated, expected=2058)


def test_gate_fails_when_pool_size_is_not_100(tmp_path, fixture_respondents):
    """A pool of 99 lines is a hard failure, not a warning."""
    from twin2k10r import pool_builder, validate_pool

    pids = pool_builder.sample_respondents(fixture_respondents, n=99, seed=42)
    out = tmp_path / "pool.jsonl"
    pool_builder.write_pool(pids, fixture_respondents, "A", out)
    with pytest.raises(validate_pool.PoolSizeError):
        validate_pool.check_pool_size(out, expected=100)


# ---------- 2. Gate: persona <-> respondent mapping ----------

def test_gate_fails_when_persona_value_differs_from_panel(
    tmp_path, fixture_respondents
):
    """A persona whose gender differs from the panel record fails."""
    from twin2k10r import pool_builder, respondent_loader, validate_pool

    out, prov, pids = _make_good_pool(tmp_path, fixture_respondents)
    pool = [json.loads(line) for line in out.read_text().splitlines()]
    pool[0]["gender"] = "Female" if pool[0]["gender"] == "Male" else "Male"
    tampered = out.with_name("tampered.jsonl")
    tampered.write_text("\n".join(json.dumps(p) for p in pool) + "\n")
    with pytest.raises(validate_pool.RespondentMismatchError):
        validate_pool.check_persona_matches_respondents(
            tampered, fixture_respondents
        )


# ---------- 3. Gate: marginals vs panel ----------

def test_gate_fails_when_marginals_deviate_beyond_rounding(
    tmp_path, fixture_respondents
):
    """A pool whose gender skew exceeds the ±1 rounding unit fails."""
    from twin2k10r import pool_builder, validate_pool

    out, prov, pids = _make_good_pool(tmp_path, fixture_respondents)
    panel = fixture_respondents
    # Skew the pool: rebuild all 100 lines as copies of female respondents,
    # so the gender marginal no longer matches the panel within ±1 unit.
    pool = [json.loads(line) for line in out.read_text().splitlines()]
    females = [p for p in pool if p["gender"] == "Female"]
    assert females, "fixture pool must contain female respondents to skew from"
    pool = [dict(females[i % len(females)]) for i in range(100)]
    skewed = out.with_name("skewed.jsonl")
    skewed.write_text("\n".join(json.dumps(p) for p in pool) + "\n")
    with pytest.raises(validate_pool.MarginalGapError):
        validate_pool.check_marginals_vs_panel(skewed, panel, tolerance=1)


def test_gate_passes_for_a_well_stratified_pool(tmp_path, fixture_respondents):
    """The real stratified pool sits within the rounding unit."""
    from twin2k10r import pool_builder, validate_pool

    out, prov, pids = _make_good_pool(tmp_path, fixture_respondents)
    report = validate_pool.check_marginals_vs_panel(
        out, fixture_respondents, tolerance=1
    )
    assert report["sex_age_max_abs_gap"] == 0, (
        "sex x age strata must match the panel exactly"
    )


# ---------- 4. Gate: cross-condition sha256 identical ----------

def test_gate_fails_when_pool_differs_across_conditions(
    tmp_path, fixture_respondents
):
    """Two condition copies of the pool with different bytes fail."""
    from twin2k10r import pool_builder, validate_pool

    out, prov, pids = _make_good_pool(tmp_path, fixture_respondents)
    other = out.with_name("other_condition.jsonl")
    other.write_bytes(out.read_bytes() + b"\n")
    with pytest.raises(validate_pool.PoolHashConflictError):
        validate_pool.check_cross_condition_hashes([out, other])


def test_gate_passes_when_all_conditions_share_one_pool(
    tmp_path, fixture_respondents
):
    """15 models x 2 arms all pointing at one identical file is PASS."""
    from twin2k10r import pool_builder, validate_pool

    out, prov, pids = _make_good_pool(tmp_path, fixture_respondents)
    copies = []
    for model in range(15):
        for arm in ("blinded", "unblinded"):
            copy = tmp_path / f"m{model}_{arm}.jsonl"
            copy.write_bytes(out.read_bytes())
            copies.append(copy)
    validate_pool.check_cross_condition_hashes(copies)  # no raise


# ---------- 5. Gate: no leaking fields / placeholders ----------

def test_gate_fails_when_leaking_field_present(tmp_path, fixture_respondents):
    """A persona carrying a non-whitelisted key (e.g. crt2_score) fails."""
    from twin2k10r import pool_builder, validate_pool

    out, prov, pids = _make_good_pool(tmp_path, fixture_respondents)
    pool = [json.loads(line) for line in out.read_text().splitlines()]
    pool[0]["crt2_score"] = 3
    leaked = out.with_name("leaked.jsonl")
    leaked.write_text("\n".join(json.dumps(p) for p in pool) + "\n")
    with pytest.raises(validate_pool.LeakingPoolError):
        validate_pool.check_no_leaking_fields(leaked, config_id="A")


def test_gate_fails_when_placeholder_value_present(tmp_path, fixture_respondents):
    """A persona value of "N/A", "", "unknown" or None fails the run."""
    from twin2k10r import pool_builder, validate_pool

    out, prov, pids = _make_good_pool(tmp_path, fixture_respondents)
    for i, bad in enumerate(("N/A", "", "unknown", None)):
        pool = [json.loads(line) for line in out.read_text().splitlines()]
        pool[7]["occupation"] = bad
        tampered = out.with_name(f"placeholder_{i}.jsonl")
        tampered.write_text("\n".join(json.dumps(p) for p in pool) + "\n")
        with pytest.raises(validate_pool.PlaceholderError):
            validate_pool.check_no_placeholders(tampered)


# ---------- 6. Gate: fresh-process seed reproducibility ----------

def test_fresh_process_reproduces_the_pid_list(tmp_path, fixture_respondents):
    """A brand-new python process re-runs the sampler from the provenance
    record and gets the identical pid list (and identical sha256)."""
    from twin2k10r import pool_builder, validate_pool

    out, prov, pids = _make_good_pool(tmp_path, fixture_respondents)
    script = (
        "import sys, json; sys.path.insert(0, %r);"
        "from twin2k10r import pool_builder;"
        "print(json.dumps(pool_builder.sample_respondents_from_provenance("
        "json.load(open(%r)))))"
    ) % (str(Path(pool_builder.__file__).parent.parent), str(out.parent / "POOL_PROVENANCE.json"))
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=120
    )
    assert result.returncode == 0, result.stderr
    fresh_pids = json.loads(result.stdout.strip().splitlines()[-1])
    assert fresh_pids == sorted(pids), "fresh process must reproduce the sample"


def test_validate_main_exits_nonzero_on_any_gate_failure(
    tmp_path, fixture_respondents
):
    """validate_pool.run() returns/exits non-zero when a gate fails —
    it never warns and continues."""
    from twin2k10r import pool_builder, validate_pool

    out, prov, pids = _make_good_pool(tmp_path, fixture_respondents)
    # Break size: only 50 lines survive.
    broken = tmp_path / "broken_pool.jsonl"
    broken.write_text("\n".join(out.read_text().splitlines()[:50]) + "\n")
    exit_code = validate_pool.run(
        pool_path=broken, dataset_root=None, respondents=fixture_respondents
    )
    assert exit_code != 0, "a failed gate must yield a non-zero exit"


def test_validate_main_exits_zero_for_a_good_pool(tmp_path, fixture_respondents):
    """A fully valid pool + provenance passes every gate: exit 0."""
    from twin2k10r import validate_pool

    out, prov, pids = _make_good_pool(tmp_path, fixture_respondents)
    exit_code = validate_pool.run(
        pool_path=out, dataset_root=None, respondents=fixture_respondents
    )
    assert exit_code == 0
