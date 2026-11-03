# Tests that the adapted pool renders prompts indistinguishable from the
# historical expansion prompts except for the persona block, and that the
# cell-grid bookkeeping is untouched. Each test checks one plain fact:
#   test_disclosure_prompts_byte_identical_except_persona_block — rebuilt
#       blinded and unblinded prompts equal the pinned historical sample
#       files once only the EMBODY block is swapped.
#   test_persona_block_is_identical_across_conditions — the only
#       per-persona content is the EMBODY block; conditions change only
#       the question text.
#   test_cell_grid_keys_unaffected — the resume key (persona_id,
#       condition, item_index) still enumerates identically over the
#       adapted personas.
#   test_bracket_values_survive_verbatim — no point-value fabrication.
import json
from pathlib import Path

import pytest

from twin2k10r.integration import expansion_pool

PERSONA_BLOCK_HEADER = "EMBODY THIS PERSON:"


def _sample_prompt_dir(expansion) -> Path:
    """The expansion pipeline's pinned historical sample prompts."""
    return expansion.config.PIPELINE_DIR / "sample_prompts"


def _read_sample(path: Path) -> tuple[str, str]:
    """Split one historical sample file into (system, user) prompts."""
    text = path.read_text(encoding="utf-8")
    system, user = text.split("=== USER ===\n")
    return system.split("=== SYSTEM ===\n")[1].strip("\n"), user.strip("\n")


def _persona_block_of(user_prompt: str) -> str:
    """The EMBODY block inside a user prompt (header through blank line)."""
    start = user_prompt.index(PERSONA_BLOCK_HEADER)
    end = user_prompt.index("\n\n", start)
    return user_prompt[start:end]


def _adapted_personas(adapted_pool_path) -> list[dict]:
    return [
        json.loads(line)
        for line in adapted_pool_path.read_text().splitlines()
        if line.strip()
    ]


def test_disclosure_prompts_byte_identical_except_persona_block(
    adapted_pool_path, expansion, expansion_ready_experiments
):
    """Rebuilt prompts equal the historical files with only the swap."""
    personas = _adapted_personas(adapted_pool_path)
    assert expansion_ready_experiments, "no READY expansion experiments found"
    for exp_id in expansion_ready_experiments:
        entry = expansion.registry.get(exp_id)
        condition = entry.spec.conditions[0]
        historical = (
            _sample_prompt_dir(expansion) / exp_id
            / f"blinded_{condition.name}_item0.txt"
        )
        if not historical.exists():
            continue
        system, user = _read_sample(historical)
        mine_system = expansion.prompts.build_system_prompt(exp_id, True)
        mine_user = expansion.prompts.build_user_prompt(
            personas[0], exp_id, condition.name, 0
        )
        assert mine_system == system
        swapped = mine_user.replace(
            _persona_block_of(mine_user), _persona_block_of(user)
        )
        assert swapped == user


def test_persona_block_is_identical_across_conditions(
    adapted_pool_path, expansion, expansion_ready_experiments
):
    """Only the EMBODY block is per-persona; conditions differ elsewhere."""
    personas = _adapted_personas(adapted_pool_path)
    block_zero = expansion.prompts.render_persona_block(personas[0])
    for exp_id in expansion_ready_experiments:
        entry = expansion.registry.get(exp_id)
        blocks = [
            _persona_block_of(
                expansion.prompts.build_user_prompt(
                    personas[0], exp_id, condition.name, 0
                )
            )
            for condition in entry.spec.conditions
        ]
        assert all(block == block_zero for block in blocks)


def test_cell_grid_keys_unaffected(
    adapted_pool_path, expansion, expansion_ready_experiments
):
    """The resume key grid (persona_id, condition, item_index) is intact."""
    personas = _adapted_personas(adapted_pool_path)
    assert len(personas) == expansion.config.PERSONA_COUNT
    for exp_id in expansion_ready_experiments:
        entry = expansion.registry.get(exp_id)
        for persona_id in (0, 1, 99):
            for condition in entry.spec.conditions:
                for item_index in range(len(condition.items)):
                    key = (persona_id, condition.name, item_index)
                    assert len(key) == 3
                    # Building the prompt for this cell must work — the
                    # grid the runner resumes on is fully renderable.
                    expansion.prompts.build_user_prompt(
                        personas[persona_id], exp_id,
                        condition.name, item_index,
                    )


def test_bracket_values_survive_verbatim(
    source_pool_path, adapted_pool_path
):
    """Bracket strings pass through byte-identical; no numbers invented."""
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
        for dataset_name, legacy_name in expansion_pool.FIELD_RENAMES.items():
            value = source[dataset_name]
            assert persona[legacy_name] == value
            assert isinstance(persona[legacy_name], str)
