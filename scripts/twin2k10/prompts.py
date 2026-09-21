# This file builds the exact texts the models are shown. The system prompt
# is one short line normally, or that line plus a fixed note plus the full
# list of every version of the experiment when the model is told the setup
# was randomized ("unblinded"). The user prompt carries the "EMBODY THIS
# PERSON" block with the 11 demographic fields, then every question of the
# arm in survey order (an anchoring arm shows its anchor choice question
# AND its numeric estimate question), then one final instruction: a
# letter answer for choice questions, a single number for numeric
# questions, and a numbered list with exactly one number per row for
# multi-row questions. Nothing here ever mentions question ids or the
# banned words "uniform" / "equal probability"; blinding lives only in
# the system prompt.

from twin2k10 import experiments

# The 11 demographic fields every persona shows, in this exact order.
# Mirrors PERSONA_FIELDS in src/fos/experiments/personas.py — kept local so
# the study package needs nothing from src/. Extra persona keys (behavioural
# measures, product favourites, ...) are never rendered.
PERSONA_FIELDS = [
    "age",
    "gender",
    "education",
    "household_income",
    "occupation",
    "ethnicity",
    "marital_status",
    "household_size",
    "number_of_children",
    "state",
    "home_ownership",
]

# The one-line system prompt the blinded arm sees.
BLINDED_SYSTEM_LINE = "You are a survey respondent."

# The unblinding note: says the version was randomly assigned and must not
# be read as information. Pinned wording — research banned "uniform" and
# "equal probability", so those words must never be added.
UNBLINDING_PARAGRAPH = (
    "This question comes from a randomized experiment. Participants were "
    "randomly assigned to one of the experimental versions listed below, and "
    "each participant saw only the version assigned to them. The version "
    "shown to you below was randomly assigned. Because the experimental "
    "condition was randomly assigned, do not infer any other differences in "
    "the participant or surrounding situation from which version was shown."
)

# Header of the version list in the unblinded system prompt.
VERSIONS_HEADER = "The experimental versions are:"

# The last line of a choice question's user prompt.
FINAL_INSTRUCTION = "Answer with only the corresponding uppercase letter."

# The last line of a numeric question's user prompt.
NUMERIC_INSTRUCTION = "Answer with a single number."

# The last line of an anchoring arm's user prompt: its TWO questions (the
# more/less anchor choice, then the numeric estimate) are answered in one
# reply, in order.
CHOICE_THEN_NUMERIC_INSTRUCTION = (
    "Answer the first question with only the corresponding uppercase "
    "letter. Then answer the second question with a single number."
)


def render_persona_block(persona: dict) -> str:
    """The "EMBODY THIS PERSON" block: one "field: value" line per field.

    Renders the 11 demographic fields in PERSONA_FIELDS order, skipping any
    field the persona dict does not carry (never a crash, never an invented
    value). Extra persona keys are ignored so behavioural-measure names and
    other bookkeeping can never leak into a prompt.
    """
    lines = [
        f"{field}: {persona[field]}" for field in PERSONA_FIELDS
        if field in persona
    ]
    return "EMBODY THIS PERSON:\n" + "\n".join(lines)


def _version_block(spec, stimuli: dict[str, dict]) -> str:
    """The numbered list of every version with its full question text(s).

    Each arm of the experiment appears as "Version {i}:" followed by that
    arm's complete verbatim question text(s) in survey order (an anchoring
    version shows both its questions). Only this experiment's own
    questions are ever included.
    """
    lines = [VERSIONS_HEADER]
    for number, (arm_name, arm_qids) in enumerate(spec.arms, start=1):
        lines.append(f"Version {number}:")
        for qid in arm_qids:
            lines.append(stimuli[qid]["question_text"])
    return "\n".join(lines)


def build_system_prompt(experiment: str, blinded: bool) -> str:
    """The system prompt for one experiment, blinded or unblinded.

    Blinded: exactly the one short line, with no hint of randomization.
    Unblinded: the blinded line, a blank line, the pinned randomization
    note, a blank line, then every version of this experiment with its
    full verbatim question text(s). Raises KeyError for an unknown
    experiment.
    """
    if blinded:
        return BLINDED_SYSTEM_LINE
    spec = experiments.EXPERIMENTS[experiment]
    head = (
        f"{BLINDED_SYSTEM_LINE}\n\n{UNBLINDING_PARAGRAPH}\n\n"
        f"{_version_block(spec, experiments.load_stimuli())}"
    )
    return head


def _option_lines(stimulus: dict) -> str:
    """The lettered answer options of a choice question, one per line.

    Renders the catalogue options verbatim ("A. more", "B. less", ...).
    Raises ValueError when the catalogue option count does not match the
    question's own label list (a broken survey file must stop the run,
    never render a wrong option table).
    """
    options = stimulus.get("options")
    labels = stimulus.get("labels")
    if options is None or labels is None:
        raise ValueError(
            f"{stimulus['qid']} is a choice question but carries no "
            "options/labels — refusing to render a made-up option table"
        )
    if len(options) != len(labels):
        raise ValueError(
            f"{stimulus['qid']} has {len(options)} options but "
            f"{len(labels)} labels — the survey file is inconsistent"
        )
    return "\n".join(
        f"{letter}. {option}" for letter, option in zip(labels, options)
    )


def _rows_lines(stimulus: dict) -> str:
    """The numbered statement rows of a multi-row question, one per line.

    Renders "1. <statement>", "2. <statement>", ... in the row order the
    survey file ships, so the model can answer with one numbered value
    per row.
    """
    return "\n".join(
        f"{number}. {row}"
        for number, row in enumerate(stimulus["rows"], start=1)
    )


def _final_instruction(stimuli: dict[str, dict], qids: tuple[str, ...]) -> str:
    """The closing instruction an arm's prompt ends with.

    Choice-only arm: the pinned letter instruction. Numeric arm: ask for
    a single number. Anchoring arm (choice + numeric): ask for the letter
    first, then the number. Multi-row arm: ask for one numbered answer
    per row and say how many rows there are.
    """
    kinds = [stimuli[qid]["response_kind"] for qid in qids]
    if kinds == ["choice"]:
        return FINAL_INSTRUCTION
    if "multi_numeric" in kinds:
        multi = next(stimuli[qid] for qid in qids
                     if stimuli[qid]["response_kind"] == "multi_numeric")
        n_rows = len(multi["rows"])
        return (
            f"The statements above are {n_rows} in total. Answer with a "
            f"numbered list of exactly {n_rows} numbers, one per line, "
            f"formatted like '1. 42'."
        )
    if kinds == ["choice", "numeric"]:
        return CHOICE_THEN_NUMERIC_INSTRUCTION
    return NUMERIC_INSTRUCTION


def build_user_prompt(persona: dict, experiment: str, arm: str) -> str:
    """The full user prompt for one persona answering one experiment arm.

    Shape: the EMBODY persona block, then each of the arm's questions in
    survey order (its verbatim question text, then its lettered options
    for a choice question or its numbered rows for a multi-row question),
    then the closing instruction for the arm's answer kinds. Takes no
    blinding argument — blinding lives only in the system prompt. Raises
    KeyError for an unknown experiment or arm.
    """
    spec = experiments.EXPERIMENTS[experiment]
    stimuli = experiments.load_stimuli()
    parts = [render_persona_block(persona)]
    for qid in spec.arm_qids(arm):
        stimulus = stimuli[qid]
        parts.append(stimulus["question_text"])
        kind = stimulus["response_kind"]
        if kind == "choice":
            parts.append(_option_lines(stimulus))
        elif kind == "multi_numeric":
            parts.append(_rows_lines(stimulus))
    parts.append(_final_instruction(stimuli, spec.arm_qids(arm)))
    return "\n\n".join(parts)
