# This file builds the exact texts the twin-style production legs show the
# models. It reuses the pinned twin2k10r scaffold (the blinded system
# line, the randomization note, persona rendering from real dataset
# fields) and adds what the frozen modules cannot do: prompts for the six
# RESTORED experiments, whose arm structures live outside the frozen
# twin2k10 experiment registry. Disclosure stays design+versions only —
# the unblinded system prompt says the version was randomly assigned and
# lists every version's verbatim question text; nothing else ever leaks.
# Functions:
#   merged_stimuli    — twin2k10's shipped questions + the restored ones.
#   system_prompt     — blinded line, or note + version list (both kinds).
#   item_user_prompt  — one item's own user prompt (anchor-aware).
#   version_block     — the numbered version list of one spec.
from __future__ import annotations

from twin2k10 import prompts as frozen_prompts
from twin2k10r import prompts as twin2k10r_prompts

# Pinned texts, byte-identical to the frozen study's by construction.
BLINDED_SYSTEM_LINE = twin2k10r_prompts.BLINDED_SYSTEM_LINE
UNBLINDING_PARAGRAPH = twin2k10r_prompts.UNBLINDING_PARAGRAPH
VERSIONS_HEADER = twin2k10r_prompts.VERSIONS_HEADER
FINAL_INSTRUCTION = twin2k10r_prompts.FINAL_INSTRUCTION
NUMERIC_INSTRUCTION = twin2k10r_prompts.NUMERIC_INSTRUCTION


def merged_stimuli() -> dict[str, dict]:
    """The shipped twin2k10 questions plus the restored ones, by qid.

    The two question sets are disjoint (the restored ids are QID157-191
    outside the shipped file), so a collision is a data bug and raises.
    """
    shipped = _load_twin_stimuli()
    restored = _load_restored_stimuli()
    overlap = set(shipped) & set(restored)
    if overlap:
        raise ValueError(
            f"restored stimuli collide with shipped qids {sorted(overlap)}"
        )
    return {**shipped, **restored}


def _load_twin_stimuli() -> dict[str, dict]:
    """The shipped survey questions, keyed by question id."""
    from twin2k10 import experiments

    return experiments.load_stimuli()


def _load_restored_stimuli() -> dict[str, dict]:
    """The restored survey questions, keyed by question id."""
    import importlib

    module = importlib.import_module(
        "twin2k10r.stimuli_restored.restored_stimuli")
    return module.stimulus_by_qid()


def version_block(spec, stimuli: dict[str, dict]) -> str:
    """The numbered list of every version with its full question text(s).

    Same shape as the frozen study's: "Version 1:", each arm's verbatim
    question text(s) in survey order. This works for restored specs too
    (the frozen helper looks arms up in the twin2k10 registry only).
    """
    lines = [VERSIONS_HEADER]
    for number, (_arm_name, arm_qids) in enumerate(spec.arms, start=1):
        lines.append(f"Version {number}:")
        for qid in arm_qids:
            lines.append(stimuli[qid]["question_text"])
    return "\n".join(lines)


def system_prompt(spec, stimuli: dict[str, dict], blinded: bool) -> str:
    """The system prompt for one experiment arm.

    Blinded: exactly the one short line. Unblinded: the line, the pinned
    randomization note, and every version's verbatim question text —
    design disclosure only, never human results, never hints.
    """
    if blinded:
        return BLINDED_SYSTEM_LINE
    head = f"{BLINDED_SYSTEM_LINE}\n\n{UNBLINDING_PARAGRAPH}"
    return f"{head}\n\n{version_block(spec, stimuli)}"


def anchor_question_text(spec, arm: str, item: dict,
                         stimuli: dict[str, dict]) -> str | None:
    """The arm's anchor question when a digit item must see it, else None.

    An anchoring-style arm asks a choice anchor FIRST and the numeric
    estimate second; the estimate call must see that anchor or the
    contrast is never measured. Only the question text renders (the
    answer must be a number, never a letter).
    """
    if item["kind"] != "digit":
        return None
    items = arm_items(spec, arm, stimuli)
    if not items or items[0]["kind"] != "choice":
        return None
    return stimuli[items[0]["qid"]]["question_text"]


def response_kind(stimulus: dict) -> str:
    """One question's answer kind: "choice" or "numeric".

    The shipped twin2k10 file names the field response_kind; the restored
    file names it question_type with values MC (multiple choice) and TE
    (text estimate). Both normalize here so the item splitter never
    branches on file provenance.
    """
    if "response_kind" in stimulus:
        return stimulus["response_kind"]
    mapping = {"MC": "choice", "TE": "numeric"}
    try:
        return mapping[stimulus["question_type"]]
    except KeyError:
        raise ValueError(
            f"{stimulus.get('qid', '?')} carries an unknown question type "
            f"{stimulus.get('question_type')!r}"
        ) from None


def arm_items(spec, arm: str, stimuli: dict[str, dict]) -> list[dict]:
    """One first-token item descriptor per single-answer call of an arm.

    Same split as the frozen twin2k10 study: a choice question is ONE
    letter item, a numeric question ONE digit item (0-9), a multi-row
    question one digit item PER ROW on that row's own scale. Reuses the
    frozen row-splitting helper; the arm comes from the passed spec so
    restored experiments work too.
    """
    from twin2k10 import experiments as frozen_experiments

    items: list[dict] = []
    for qid in spec.arm_qids(arm):
        stimulus = stimuli[qid]
        kind = response_kind(stimulus)
        if kind == "choice":
            items.append({
                "qid": qid, "kind": "choice",
                "labels": tuple(stimulus["labels"]),
                "question_text": stimulus["question_text"],
                "row": None, "statement": None,
            })
        elif kind == "numeric":
            items.append({
                "qid": qid, "kind": "digit",
                "labels": tuple("0123456789"),
                "question_text": stimulus["question_text"],
                "row": None, "statement": None,
            })
        else:
            items.extend(frozen_experiments._row_items(qid, stimulus))
    return items


def item_user_prompt(persona: dict, spec, arm: str, item: dict,
                     stimuli: dict[str, dict]) -> str:
    """The full user prompt for ONE first-token item of an arm.

    Shape (frozen): the EMBODY persona block (real dataset fields via the
    twin2k10r renderer), the anchor question when needed, then the item
    itself with its option table or answer scale, ending in the pinned
    instruction line. Each call sees exactly one question to answer.
    """
    parts = [twin2k10r_prompts.render_persona_block(persona)]
    anchor = anchor_question_text(spec, arm, item, stimuli)
    if anchor is not None:
        parts.append(anchor)
    parts.append(item["question_text"])
    if item["kind"] == "choice":
        parts.append(frozen_prompts._option_lines(stimuli[item["qid"]]))
        parts.append(FINAL_INSTRUCTION)
        return "\n\n".join(parts)
    if item["statement"] is not None:
        parts.append(item["statement"])
    scale = frozen_prompts._scale_lines(stimuli[item["qid"]])
    if scale is not None:
        parts.append(scale)
    parts.append(NUMERIC_INSTRUCTION)
    return "\n\n".join(parts)
