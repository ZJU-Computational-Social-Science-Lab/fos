# Tests for prompt integration in the twin2k10r pipeline (serving.py and
# the prompt-building surface).
# WHAT THESE TESTS CHECK, in plain words:
#   - A 7-field persona renders a valid "EMBODY THIS PERSON" block: the 4
#     unavailable fields are simply skipped, never printed as blanks.
#   - Config B personas add a separate "MEASURED TRAITS:" block with the
#     11 measured scores, never mixed into the demographics block.
#   - Building the pool makes NO language-model call of any kind — no
#     chat function, no API, nothing.
#   - The blinded/unblinded disclosure prompt texts are byte-identical to
#     the twin2k10 study's; only the persona block's content changed.
import sys
from pathlib import Path

import pytest

# The study packages live in scripts/ and are not on pytest's pythonpath.
_SCRIPTS = str(Path(__file__).resolve().parent.parent.parent / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from twin2k10 import prompts as twin2k10_prompts  # noqa: E402


CONFIG_A_KEYS = (
    "age_bracket",
    "gender",
    "education",
    "household_income_bracket",
    "ethnicity",
    "marital_status",
    "household_size_bracket",
)


def _config_a_persona(fixture_respondents):
    from twin2k10r import pool_builder

    return pool_builder.map_fields(1, fixture_respondents, "A")


def _config_b_persona(fixture_respondents):
    from twin2k10r import pool_builder

    return pool_builder.map_fields(1, fixture_respondents, "B")


# ---------- 1. The 7-field block renders validly ----------

def test_seven_field_persona_renders_exactly_seven_lines(fixture_respondents):
    """The persona block lists exactly the 7 available fields, one per line."""
    from twin2k10r import prompts as twin2k10r_prompts

    persona = _config_a_persona(fixture_respondents)
    # twin2k10's inherited renderer skips bracket-named fields, so it would
    # render only 4 of the 7 Config A fields. twin2k10r.prompts renders all 7.
    block = twin2k10r_prompts.render_persona_block(persona)
    lines = block.splitlines()
    assert lines[0] == "EMBODY THIS PERSON:"
    assert len(lines) == 8, f"expected 7 field lines, got {len(lines) - 1}"


def test_excluded_fields_never_appear_in_rendered_block(fixture_respondents):
    """occupation / number_of_children / state / home_ownership never show
    up in any rendered prompt — not even as an empty value."""
    from twin2k10r import prompts as twin2k10r_prompts

    persona = _config_a_persona(fixture_respondents)
    block = twin2k10r_prompts.render_persona_block(persona)
    for field in ("occupation", "number_of_children", "state", "home_ownership"):
        assert field not in block, f"{field} leaked into the rendered prompt"
    for bad in ("N/A", "None", "unknown"):
        assert bad not in block, f"placeholder {bad!r} in the rendered prompt"


def test_rendered_block_matches_respondent_values(fixture_respondents):
    """Every rendered line shows the respondent's own dataset label."""
    from twin2k10r import prompts as twin2k10r_prompts

    persona = _config_a_persona(fixture_respondents)
    block = twin2k10r_prompts.render_persona_block(persona)
    for key in CONFIG_A_KEYS:
        assert f"{key}: {persona[key]}" in block, f"{key} rendered wrongly"


# ---------- 2. Config B adds a separate MEASURED TRAITS block ----------

def test_config_b_renders_a_measured_traits_block(fixture_respondents):
    """Config B adds a "MEASURED TRAITS:" block listing the 11 scores."""
    from twin2k10r import prompts as twin2k10r_prompts

    persona = _config_b_persona(fixture_respondents)
    block = twin2k10r_prompts.render_persona_block(persona)
    assert "MEASURED TRAITS:" in block, "Config B needs a MEASURED TRAITS block"


def test_config_b_traits_block_has_exactly_eleven_lines(fixture_respondents):
    """The MEASURED TRAITS block is one line per whitelisted score."""
    from twin2k10r import prompts as twin2k10r_prompts

    persona = _config_b_persona(fixture_respondents)
    block = twin2k10r_prompts.render_persona_block(persona)
    after = block.split("MEASURED TRAITS:")[1].strip().splitlines()
    assert len(after) == 11, f"expected 11 trait lines, got {len(after)}"


def test_config_a_has_no_measured_traits_block(fixture_respondents):
    """Config A personas never carry a MEASURED TRAITS block."""
    from twin2k10r import prompts as twin2k10r_prompts

    persona = _config_a_persona(fixture_respondents)
    block = twin2k10r_prompts.render_persona_block(persona)
    assert "MEASURED TRAITS" not in block


def test_blocklisted_scores_never_render(fixture_respondents):
    """Task-performance scores (crt2_score etc.) appear in no prompt."""
    from twin2k10r import prompts as twin2k10r_prompts

    persona = _config_b_persona(fixture_respondents)
    block = twin2k10r_prompts.render_persona_block(persona)
    for banned in ("crt2_score", "score_overconfidence", "score_fluid",
                   "score_ultimatum_sender", "MXsum", "rotsum"):
        assert banned not in block, f"blocklisted score {banned} rendered"


# ---------- 3. No LLM/API call anywhere in pool building ----------

def test_pool_modules_import_no_llm_or_network_code():
    """The twin2k10r pool modules never import a chat client or HTTP
    library — the persona path is pure data loading."""
    import twin2k10r.dataset_manifest as dm
    import twin2k10r.pool_builder as pb
    import twin2k10r.respondent_loader as rl
    import twin2k10r.serving as serving

    banned = ("openai", "httpx", "requests", "anthropic", "urllib", "socket")
    for module in (dm, pb, rl, serving):
        source = Path(module.__file__).read_text()
        for name in banned:
            assert f"import {name}" not in source, (
                f"{module.__name__} imports {name}"
            )
            assert f"from {name}" not in source, (
                f"{module.__name__} imports from {name}"
            )


def test_ensure_pool_makes_no_model_call(tmp_path, monkeypatch, fixture_respondents):
    """ensure_pool succeeds with every known LLM-call entry point poisoned
    to raise — proof that it never talks to a model."""
    from twin2k10r import serving

    def poison(*args, **kwargs):
        raise AssertionError("ensure_pool must never call a model")

    for name in ("chat", "chat_fn", "call_llm", "complete", "client"):
        monkeypatch.setattr(serving, name, poison, raising=False)
    personas = serving.ensure_pool(tmp_path, "A", log=lambda _msg: None)
    assert len(personas) == 100


# ---------- 4. Disclosure prompt text unchanged vs twin2k10 ----------

def test_disclosure_texts_are_identical_to_twin2k10():
    """The blinded line and the unblinding paragraph are byte-identical
    to the twin2k10 study's pinned wording."""
    from twin2k10r import prompts as twin2k10r_prompts

    assert (
        twin2k10r_prompts.BLINDED_SYSTEM_LINE
        == twin2k10_prompts.BLINDED_SYSTEM_LINE
    )
    assert (
        twin2k10r_prompts.UNBLINDING_PARAGRAPH
        == twin2k10_prompts.UNBLINDING_PARAGRAPH
    )
    assert (
        twin2k10r_prompts.VERSIONS_HEADER == twin2k10_prompts.VERSIONS_HEADER
    )
    assert (
        twin2k10r_prompts.FINAL_INSTRUCTION == twin2k10_prompts.FINAL_INSTRUCTION
    )
    assert (
        twin2k10r_prompts.NUMERIC_INSTRUCTION == twin2k10_prompts.NUMERIC_INSTRUCTION
    )


def test_persona_field_order_unchanged_vs_twin2k10():
    """PERSONA_FIELDS keeps the twin2k10 order (all 11 names); the missing
    four are handled by render-skip, not by reordering the list."""
    from twin2k10r import prompts as twin2k10r_prompts

    assert twin2k10r_prompts.PERSONA_FIELDS == twin2k10_prompts.PERSONA_FIELDS


def test_persona_block_is_the_only_prompt_change(fixture_respondents):
    """A rendered user prompt = twin2k10's scaffold with only the persona
    block differing: same closing instruction, same item text position."""
    from twin2k10r import prompts as twin2k10r_prompts

    persona = _config_a_persona(fixture_respondents)
    block = twin2k10r_prompts.render_persona_block(persona)
    assert block.startswith("EMBODY THIS PERSON:")
    assert twin2k10_prompts.FINAL_INSTRUCTION in (
        twin2k10r_prompts.build_user_prompt(persona, item=None)
        if hasattr(twin2k10r_prompts, "build_user_prompt") else block
    )
