# Tests that run against the canonical Stage 0 Config A pool (the real
# Twin-2K-500 respondents, hash-pinned). They skip when that file is not
# on this machine, so the suite stays green everywhere:
#   test_real_pool_passes_expansion_load_personas_unchanged — the real
#       pool, adapted, goes through the pipeline's own loader as-is.
#   test_real_pool_rendered_values_equal_panel_records — every rendered
#       demographic line equals the verbatim value in the pool record.
#   test_real_pool_renders_every_ready_experiment — persona 0 renders a
#       full user prompt for every READY expansion experiment, both arms.
import json

import pytest


def test_real_pool_passes_expansion_load_personas_unchanged(
    real_pool_path, expansion, monkeypatch, tmp_path
):
    """The pipeline's own loader accepts the adapted real pool as-is."""
    if real_pool_path is None:
        pytest.skip("the Stage 0 Config A pool is not on this machine")
    from twin2k10r.integration import expansion_pool

    adapted = tmp_path / "real_adapted.jsonl"
    expansion_pool.write_adapted_pool(real_pool_path, adapted)
    monkeypatch.setattr(expansion.config, "PERSONA_POOL_PATH", adapted)
    personas = expansion.runner.load_personas()
    assert len(personas) == 100


def test_real_pool_rendered_values_equal_panel_records(
    real_pool_path, expansion
):
    """Each rendered line is the verbatim bracket from the panel record."""
    if real_pool_path is None:
        pytest.skip("the Stage 0 Config A pool is not on this machine")
    from twin2k10r.integration import expansion_pool

    personas = expansion_pool.adapt_twin2k10r_pool(real_pool_path)
    sources = [
        json.loads(line)
        for line in real_pool_path.read_text().splitlines()
        if line.strip()
    ]
    for source, persona in zip(sources, personas):
        block = expansion.prompts.render_persona_block(persona)
        for dataset_name, legacy_name in expansion_pool.FIELD_RENAMES.items():
            assert f"{legacy_name}: {source[dataset_name]}" in block


def test_real_pool_renders_every_ready_experiment(
    real_pool_path, expansion
):
    """Persona 0 renders a prompt for every READY experiment, both arms."""
    if real_pool_path is None:
        pytest.skip("the Stage 0 Config A pool is not on this machine")
    from twin2k10r.integration import expansion_pool

    personas = expansion_pool.adapt_twin2k10r_pool(real_pool_path)
    ready = expansion.registry.ready_experiments()
    assert len(ready) == 17
    for exp_id in ready:
        entry = expansion.registry.get(exp_id)
        for condition in entry.spec.conditions:
            prompt = expansion.prompts.build_user_prompt(
                personas[0], exp_id, condition.name, 0
            )
            assert prompt.startswith("EMBODY THIS PERSON:")
            for blinded in (True, False):
                system = expansion.prompts.build_system_prompt(exp_id, blinded)
                assert system.startswith("You are a survey respondent.")
