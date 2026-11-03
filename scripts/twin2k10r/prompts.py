# This file builds the exact texts the models are shown in the
# real-respondent study. It reuses the twin2k10 study's pinned scaffold
# (the blinded system line, the randomization note, the version list,
# the closing instructions) unchanged, and changes exactly one thing:
# the "EMBODY THIS PERSON" block is rendered from real respondent
# fields. The four demographic answers the dataset cannot provide are
# skipped (never blanked, never invented); a Config B persona adds a
# separate "MEASURED TRAITS:" block listing the 11 measured scores.
# Functions:
#   render_persona_block  — the EMBODY block (plus traits for Config B).
#   build_system_prompt   — blinded or unblinded system prompt.
#   build_user_prompt     — the user prompt for one persona and one item.
from twin2k10 import experiments
from twin2k10 import prompts as _twin2k10

# The legacy field list keeps the twin2k10 order (all 11 names). The
# persona dicts use the dataset's own field names, mapped below; the 4
# unavailable answers simply have no mapping and are skipped at render.
PERSONA_FIELDS = list(_twin2k10.PERSONA_FIELDS)

# Legacy study field -> real dataset field (the renamed columns).
_REAL_FIELD_OF = {
    "age": "age_bracket",
    "household_income": "household_income_bracket",
    "household_size": "household_size_bracket",
}

# The 11 measured trait scores a Config B persona carries.
SCORE_FIELDS = (
    "score_extraversion",
    "score_agreeableness",
    "score_conscientiousness",
    "score_openness",
    "score_neuroticism",
    "score_needforcognition",
    "score_agency",
    "score_communion",
    "score_minimalism",
    "score_BES",
    "score_GREEN",
)

# Pinned texts, byte-identical to the twin2k10 study's by construction.
BLINDED_SYSTEM_LINE = _twin2k10.BLINDED_SYSTEM_LINE
UNBLINDING_PARAGRAPH = _twin2k10.UNBLINDING_PARAGRAPH
VERSIONS_HEADER = _twin2k10.VERSIONS_HEADER
FINAL_INSTRUCTION = _twin2k10.FINAL_INSTRUCTION
NUMERIC_INSTRUCTION = _twin2k10.NUMERIC_INSTRUCTION


def _demographic_lines(persona: dict) -> list:
    """One "field: value" line per real demographic answer, in the
    legacy PERSONA_FIELDS order. Skips the answers the dataset cannot
    provide — absent keys, never blanks, never invented values."""
    lines = []
    for legacy in PERSONA_FIELDS:
        field = _REAL_FIELD_OF.get(legacy, legacy)
        if field in persona and field not in SCORE_FIELDS:
            lines.append(f"{field}: {persona[field]}")
    return lines


def render_persona_block(persona: dict) -> str:
    """The "EMBODY THIS PERSON" block for one persona.

    Config A personas render exactly their 7 real demographic lines.
    Config B personas additionally carry a "MEASURED TRAITS:" block with
    one line per measured score. Blocklisted scores are never here to
    begin with (the pool builder refuses them), so they cannot render.
    """
    lines = _demographic_lines(persona)
    block = "EMBODY THIS PERSON:\n" + "\n".join(lines)
    traits = [field for field in SCORE_FIELDS if field in persona]
    if traits:
        trait_lines = [f"{field}: {persona[field]}" for field in traits]
        block += "\n\nMEASURED TRAITS:\n" + "\n".join(trait_lines)
    return block


def build_system_prompt(experiment: str, blinded: bool,
                        informed_with_versions: bool = False) -> str:
    """The system prompt: blinded is the one short line; unblinded adds
    the pinned randomization note and, when informed_with_versions, the
    full list of every version of that experiment. Human results are
    never part of any arm."""
    if blinded:
        return BLINDED_SYSTEM_LINE
    head = f"{BLINDED_SYSTEM_LINE}\n\n{UNBLINDING_PARAGRAPH}"
    if informed_with_versions:
        versions = _twin2k10._version_block(
            experiments.EXPERIMENTS[experiment], experiments.load_stimuli()
        )
        head += f"\n\n{versions}"
    return head


def build_user_prompt(persona: dict, experiment: str | None = None,
                      arm: str | None = None, item: dict | None = None) -> str:
    """The user prompt for one persona.

    With an experiment and arm, renders the same per-item shape the
    twin2k10 study uses (persona block, optional anchor question, the
    item with its own answer scale, one closing instruction) — only the
    persona block's content differs from that study. Without an
    experiment (the inspection/example path), renders the persona block
    followed by the closing letter instruction.
    """
    block = render_persona_block(persona)
    if experiment is None or arm is None:
        return f"{block}\n\n{FINAL_INSTRUCTION}"
    stimuli = experiments.load_stimuli()
    if item is None:
        items = experiments.arm_items(experiment, arm, stimuli)
        if any(one["kind"] == "digit" for one in items):
            raise ValueError(
                f"experiment {experiment!r} arm {arm!r} has digit items, "
                "which are asked one per call — pass item="
            )
        parts = [block]
        for one in items:
            parts.append(one["question_text"])
            parts.append(_twin2k10._option_lines(stimuli[one["qid"]]))
        parts.append(FINAL_INSTRUCTION)
        return "\n\n".join(parts)
    parts = [block]
    anchor = _twin2k10._anchor_question_text(experiment, arm, item, stimuli)
    if anchor is not None:
        parts.append(anchor)
    parts.append(item["question_text"])
    if item["kind"] == "choice":
        parts.append(_twin2k10._option_lines(stimuli[item["qid"]]))
        parts.append(FINAL_INSTRUCTION)
        return "\n\n".join(parts)
    if item["statement"] is not None:
        parts.append(item["statement"])
    scale = _twin2k10._scale_lines(stimuli[item["qid"]])
    if scale is not None:
        parts.append(scale)
    parts.append(NUMERIC_INSTRUCTION)
    return "\n\n".join(parts)
