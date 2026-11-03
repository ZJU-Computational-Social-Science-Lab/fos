# Tests for twin2k10r/example_prompts.py — the example-prompt helper that
# renders anonymized example prompts for human inspection.
# WHAT THESE TESTS CHECK, in plain words:
#   - The helper produces exactly 10 fully rendered example prompts, with
#     the real pid replaced by the pool id (0-99) — anonymized.
#   - Both arms are covered: blinded and unblinded (disclosure).
#   - Several stimulus types appear: a choice question, a rating
#     statement, a numeric estimate, and both informed/uninformed
#     disclosure variants.
#   - Both pool configs work: A (7 fields) and B (7 + MEASURED TRAITS).
#   - No example prompt contains banned outcome tokens ("human results",
#     "% of participants", ...) — no leaking of study results.
import json

import pytest


def _build(run_dir, config_id):
    from twin2k10r import example_prompts

    return example_prompts.build_example_prompts(run_dir, config_id)


def _make_run_dir(tmp_path, fixture_respondents, config_id="A"):
    from twin2k10r import pool_builder

    pids = pool_builder.sample_respondents(fixture_respondents, n=100, seed=42)
    out = tmp_path / "pools" / "twin2k_respondent.jsonl"
    pool_builder.write_pool(pids, fixture_respondents, config_id, out)
    return tmp_path


# ---------- 1. Ten anonymized prompts ----------

def test_helper_returns_exactly_ten_prompts(tmp_path, fixture_respondents):
    """Exactly 10 example prompts are produced for human inspection."""
    run_dir = _make_run_dir(tmp_path, fixture_respondents)
    examples = _build(run_dir, "A")
    assert len(examples) == 10


def test_examples_never_contain_a_real_pid(tmp_path, fixture_respondents):
    """Every real pid (1..2058) is replaced by the pool id (0..99)."""
    run_dir = _make_run_dir(tmp_path, fixture_respondents)
    examples = _build(run_dir, "A")
    for example in examples:
        text = example["prompt"] if isinstance(example, dict) else str(example)
        assert "pid" not in text, "raw pid key must be anonymized away"
        pool_id = example["pool_id"]
        assert 0 <= pool_id <= 99


# ---------- 2. Both arms ----------

def test_examples_cover_both_arms(tmp_path, fixture_respondents):
    """Some examples are blinded, some are unblinded (disclosure)."""
    run_dir = _make_run_dir(tmp_path, fixture_respondents)
    examples = _build(run_dir, "A")
    arms = {example["arm"] for example in examples}
    assert arms == {"blinded", "unblinded"}, arms


# ---------- 3. Several stimulus types ----------

def test_examples_cover_several_stimulus_types(tmp_path, fixture_respondents):
    """Choice, rating, and numeric stimulus types all appear."""
    run_dir = _make_run_dir(tmp_path, fixture_respondents)
    examples = _build(run_dir, "A")
    kinds = {example["stimulus_type"] for example in examples}
    assert {"choice", "rating", "numeric"} <= kinds, kinds


def test_examples_cover_informed_and_uninformed_disclosure(
    tmp_path, fixture_respondents
):
    """Uninformed and informed-with-versions disclosure variants appear."""
    run_dir = _make_run_dir(tmp_path, fixture_respondents)
    examples = _build(run_dir, "A")
    disclosure_kinds = {
        example.get("disclosure_variant") for example in examples
        if example.get("disclosure_variant")
    }
    assert {"uninformed", "informed_with_versions"} <= disclosure_kinds


# ---------- 4. Both configs ----------

def test_examples_work_for_config_a(tmp_path, fixture_respondents):
    """Config A examples render the 7 demographics, no traits block."""
    run_dir = _make_run_dir(tmp_path, fixture_respondents, "A")
    examples = _build(run_dir, "A")
    for example in examples:
        assert "EMBODY THIS PERSON:" in example["prompt"]
        assert "MEASURED TRAITS:" not in example["prompt"]


def test_examples_work_for_config_b(tmp_path, fixture_respondents):
    """Config B examples add the MEASURED TRAITS block."""
    run_dir = _make_run_dir(tmp_path, fixture_respondents, "B")
    examples = _build(run_dir, "B")
    assert any("MEASURED TRAITS:" in ex["prompt"] for ex in examples)


# ---------- 5. No banned outcome tokens in any example ----------

def test_no_banned_outcome_tokens_in_examples(tmp_path, fixture_respondents):
    """The banned result-leaking phrases appear in zero examples."""
    run_dir = _make_run_dir(tmp_path, fixture_respondents)
    for config_id in ("A", "B"):
        examples = _build(run_dir, config_id)
        for example in examples:
            text = example["prompt"]
            for banned in (
                "% of participants",
                "of participants chose",
                "human results",
                "actual human",
            ):
                assert banned.lower() not in text.lower(), (
                    f"banned token {banned!r} leaked into an example prompt"
                )


# ---------- 6. Examples are complete, renderable prompts ----------

def test_examples_are_nonempty_and_rendered(tmp_path, fixture_respondents):
    """Each example carries a non-empty rendered prompt string."""
    run_dir = _make_run_dir(tmp_path, fixture_respondents)
    examples = _build(run_dir, "A")
    for example in examples:
        assert isinstance(example["prompt"], str) and len(example["prompt"]) > 50
        assert "EMBODY THIS PERSON:" in example["prompt"]
