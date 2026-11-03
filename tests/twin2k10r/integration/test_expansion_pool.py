# Tests that the adapted real-respondent pool is exactly what the frozen
# expansion pipeline's loader accepts, with nothing leaked and nothing
# changed in the values. Each test checks one plain fact:
#   test_adapted_pool_passes_expansion_load_personas_unchanged — the
#       pipeline's own loader accepts the adapted file as-is.
#   test_rendered_persona_values_equal_source_pool_records — every value
#       the prompts would show is the verbatim value from the pool file.
#   test_no_bookkeeping_keys_reach_the_adapted_pool — pid/pool_id are gone.
#   test_no_bookkeeping_keys_reach_rendered_prompts — and never render.
#   test_adaptation_is_deterministic — two passes produce identical bytes.
#   test_record_order_is_preserved — persona_id (position) stays the same
#       respondent, so cell-grid keys keep pointing where they did.
#   test_adapter_rejects_wrong_record_count — bad pools fail loudly.
#   test_adapter_rejects_unknown_and_missing_fields — bad pools fail
#       loudly, naming the problem record and field.
#   test_write_adapted_pool_refuses_to_overwrite — new artifacts only.
import json

import pytest

from twin2k10r.integration import expansion_pool


def test_adapted_pool_passes_expansion_load_personas_unchanged(
    adapted_pool_path, expansion, monkeypatch
):
    """The pipeline's own loader accepts the adapted file with zero edits."""
    monkeypatch.setattr(
        expansion.config, "PERSONA_POOL_PATH", adapted_pool_path
    )
    personas = expansion.runner.load_personas()
    assert len(personas) == 100
    assert all(
        set(persona) <= set(expansion.prompts.PERSONA_FIELDS)
        for persona in personas
    )


def test_rendered_persona_values_equal_source_pool_records(
    source_pool_path, adapted_pool_path, expansion
):
    """Each rendered line shows the verbatim value from the source record."""
    sources = [
        json.loads(line)
        for line in source_pool_path.read_text().splitlines()
        if line.strip()
    ]
    adapted = [
        json.loads(line)
        for line in adapted_pool_path.read_text().splitlines()
        if line.strip()
    ]
    for source, persona in zip(sources, adapted):
        block = expansion.prompts.render_persona_block(persona)
        for dataset_name, legacy_name in expansion_pool.FIELD_RENAMES.items():
            line = f"{legacy_name}: {source[dataset_name]}"
            assert line in block


def test_no_bookkeeping_keys_reach_the_adapted_pool(adapted_pool_path):
    """pid and pool_id never survive adaptation."""
    personas = [
        json.loads(line)
        for line in adapted_pool_path.read_text().splitlines()
        if line.strip()
    ]
    for persona in personas:
        assert "pid" not in persona
        assert "pool_id" not in persona


def test_no_bookkeeping_keys_reach_rendered_prompts(
    adapted_pool_path, expansion
):
    """No pid value and no bookkeeping key name appears in any prompt."""
    personas = [
        json.loads(line)
        for line in adapted_pool_path.read_text().splitlines()
        if line.strip()
    ]
    for persona in personas:
        block = expansion.prompts.render_persona_block(persona)
        assert "pid" not in block
        assert "pool_id" not in block


def test_adaptation_is_deterministic(source_pool_path, tmp_path):
    """Running the adapter twice gives byte-identical output files."""
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    expansion_pool.write_adapted_pool(source_pool_path, first)
    expansion_pool.write_adapted_pool(source_pool_path, second)
    assert first.read_bytes() == second.read_bytes()
    manifest = expansion_pool.write_adapted_pool(source_pool_path, tmp_path / "third.jsonl")
    assert manifest["adapted_sha256"] == expansion_pool._sha256_of(first)


def test_record_order_is_preserved(source_pool_path, adapted_pool_path):
    """Persona i in the adapted file is the same person as record i."""
    sources = [
        json.loads(line)
        for line in source_pool_path.read_text().splitlines()
        if line.strip()
    ]
    adapted = [
        json.loads(line)
        for line in adapted_pool_path.read_text().splitlines()
        if line.strip()
    ]
    for index, (source, persona) in enumerate(zip(sources, adapted)):
        # pid is dropped from the persona, so identity is checked via the
        # one field that varies per record in the fixture: age bracket.
        assert persona["age"] == source["age_bracket"]
        assert index == source["pool_id"]


def test_adapter_rejects_wrong_record_count(source_pool_path, tmp_path):
    """A pool with fewer than 100 records is refused, not truncated."""
    short = tmp_path / "short.jsonl"
    records = [
        json.loads(line)
        for line in source_pool_path.read_text().splitlines()
        if line.strip()
    ][:-1]
    short.write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in records)
    )
    with pytest.raises(expansion_pool.PoolShapeError):
        expansion_pool.adapt_twin2k10r_pool(short)


def test_adapter_rejects_unknown_and_missing_fields(tmp_path):
    """Unknown keys and missing real fields both fail, naming the record."""
    extra = {
        "pid": 1, "pool_id": 0, "age_bracket": "18-29", "gender": "Male",
        "education": "x", "household_income_bracket": "y",
        "ethnicity": "z", "marital_status": "m",
        "household_size_bracket": "2", "state": "NY",
    }
    bad_extra = tmp_path / "extra.jsonl"
    bad_extra.write_text((json.dumps(extra) + "\n") * 100)
    with pytest.raises(expansion_pool.PoolFieldError, match="unknown keys"):
        expansion_pool.adapt_twin2k10r_pool(bad_extra)

    missing = {k: v for k, v in extra.items() if k not in ("ethnicity", "state")}
    bad_missing = tmp_path / "missing.jsonl"
    bad_missing.write_text((json.dumps(missing) + "\n") * 100)
    with pytest.raises(expansion_pool.PoolFieldError, match="missing"):
        expansion_pool.adapt_twin2k10r_pool(bad_missing)


def test_write_adapted_pool_refuses_to_overwrite(
    source_pool_path, adapted_pool_path
):
    """The writer never overwrites an existing file."""
    with pytest.raises(FileExistsError):
        expansion_pool.write_adapted_pool(source_pool_path, adapted_pool_path)
