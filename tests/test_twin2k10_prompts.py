# Locked tests for the twin2k10 study's prompt builder (TASK-2139 RED
# phase; tests ONLY — no implementation lives yet, so every test here
# errors at collection until scripts/twin2k10/prompts.py exists).
#
# WHAT THIS FILE CHECKS, in plain words:
#   - The persona block renders the same 11 demographic fields as twin2k6,
#     and extra persona keys never leak into a prompt.
#   - The blinded system prompt is the same single line as twin2k6's; the
#     unblinded one adds twin2k6's exact randomization note plus every
#     version of that experiment. The banned words ("uniform", "equal
#     probability") appear in no prompt, ever.
#   - Every user prompt carries the verbatim question text of each of the
#     arm's questions. Choice questions render "A. <option>" lines;
#     numeric questions ask for a single number; multi-row questions ask
#     for one numbered answer per row (false_consensus: 10 answers).
#
# All offline: pure string building; no network, no models.
import sys
from pathlib import Path

import pytest

# The launch scripts live in scripts/ and are not on pytest's pythonpath.
_SCRIPTS = str(Path(__file__).resolve().parent.parent / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from twin2k10 import experiments, prompts  # noqa: E402

# A complete 11-field persona, the same fields twin2k6 renders.
PERSONA = {
    "age": 41,
    "gender": "female",
    "education": "bachelor's degree",
    "household_income": "$60,000-$79,999",
    "occupation": "teacher",
    "ethnicity": "White",
    "marital_status": "married",
    "household_size": 4,
    "number_of_children": 2,
    "state": "Ohio",
    "home_ownership": "own",
}

ARMS = [
    ("allais", "form1"), ("linda", "conjunction"),
    ("base_rate", "30_engineers"), ("anchoring_redwood", "low"),
    ("anchoring_african", "high"), ("outcome_bias", "success"),
    ("myside", "ford"), ("prob_matching", "problem1"),
    ("abs_relative", "calculator"), ("false_consensus", "all"),
]


def _stimuli() -> dict[str, dict]:
    """The study's loaded stimuli, keyed by question id (helper)."""
    return experiments.load_stimuli()


def _arm_qids(experiment: str, arm: str) -> list[str]:
    """The question ids of one arm, in file order (helper)."""
    stimuli = _stimuli()
    return [
        qid for qid, entry in sorted(stimuli.items())
        if entry["experiment"] == experiment and entry["arm"] == arm
    ]


def _last_paragraph(prompt: str) -> str:
    """The final instruction block of a prompt (helper)."""
    return prompt.split("\n\n")[-1]


def test_persona_block_renders_the_same_11_fields_as_twin2k6() -> None:
    """The demographic fields equal twin2k6's, in the same order."""
    from twin2k6 import prompts as k6_prompts

    assert prompts.PERSONA_FIELDS == k6_prompts.PERSONA_FIELDS
    block = prompts.render_persona_block(PERSONA)
    assert block.startswith("EMBODY THIS PERSON:")
    assert "age: 41" in block and "state: Ohio" in block


def test_extra_persona_keys_never_leak_into_the_block() -> None:
    """Behavioural or bookkeeping keys are silently excluded, never shown."""
    noisy = {**PERSONA, "product_favourites": ["coke"], "twin2k_item": 7}
    block = prompts.render_persona_block(noisy)
    assert "coke" not in block and "twin2k_item" not in block


def test_blinded_system_prompt_is_the_same_one_liner_as_twin2k6() -> None:
    """Every blinded arm sees exactly twin2k6's short line, nothing else."""
    from twin2k6 import prompts as k6_prompts

    for experiment in experiments.EXPERIMENTS:
        assert prompts.build_system_prompt(experiment, blinded=True) \
            == k6_prompts.BLINDED_SYSTEM_LINE


def test_unblinded_system_prompt_adds_the_note_and_all_versions() -> None:
    """Unblinded = blinded line + twin2k6's note + every version's text."""
    from twin2k6 import prompts as k6_prompts

    for experiment, arm in ARMS:
        unblinded = prompts.build_system_prompt(experiment, blinded=False)
        assert k6_prompts.BLINDED_SYSTEM_LINE in unblinded, experiment
        assert k6_prompts.UNBLINDING_PARAGRAPH in unblinded, experiment
        spec = experiments.EXPERIMENTS[experiment]
        for other_arm, _ in spec.arms:
            for qid in _arm_qids(experiment, other_arm):
                assert _stimuli()[qid]["question_text"] in unblinded, \
                    (experiment, other_arm, qid)
        assert unblinded != prompts.build_system_prompt(experiment,
                                                        blinded=True)


def test_banned_words_never_appear_in_any_prompt() -> None:
    """'uniform' and 'equal probability' are banned by the research design."""
    for experiment, arm in ARMS:
        user = prompts.build_user_prompt(PERSONA, experiment, arm)
        for blinded in (True, False):
            system = prompts.build_system_prompt(experiment, blinded=blinded)
            for text in (user, system):
                assert "uniform" not in text.lower(), experiment
                assert "equal probability" not in text.lower(), experiment


def test_user_prompt_carries_every_verbatim_question_of_the_arm() -> None:
    """Each arm's question texts appear word for word in the user prompt."""
    for experiment, arm in ARMS:
        user = prompts.build_user_prompt(PERSONA, experiment, arm)
        for qid in _arm_qids(experiment, arm):
            assert _stimuli()[qid]["question_text"] in user, \
                (experiment, arm, qid)
        assert "EMBODY THIS PERSON:" in user


def test_choice_options_render_as_letter_lines_matching_option_count() -> None:
    """A choice question shows 'A. <text>', 'B. <text>', ... for all options."""
    user = prompts.build_user_prompt(PERSONA, "allais", "form1")
    stimulus = _stimuli()["QID192"]
    for letter, option in zip(stimulus["labels"], stimulus["options"]):
        assert f"{letter}. {option}" in user, letter
    assert _last_paragraph(user) == prompts.FINAL_INSTRUCTION


def test_numeric_prompt_asks_for_a_single_number() -> None:
    """base_rate asks for one number and shows no letter options."""
    user = prompts.build_user_prompt(PERSONA, "base_rate", "30_engineers")
    assert "number" in _last_paragraph(user).lower()
    assert "A." not in user


def test_anchoring_prompt_carries_both_questions_and_asks_a_number() -> None:
    """An anchoring arm shows the anchor choice AND the numeric estimate."""
    user = prompts.build_user_prompt(PERSONA, "anchoring_redwood", "low")
    assert "A. more" in user and "B. less" in user
    assert "number" in _last_paragraph(user).lower()


def test_multi_numeric_prompt_requests_one_numbered_answer_per_row() -> None:
    """Multi-row questions list every row and ask for that many answers."""
    cases = [
        ("linda", "conjunction", 3),
        ("prob_matching", "problem1", 10),
        ("prob_matching", "problem2", 6),
        ("false_consensus", "all", 10),
    ]
    for experiment, arm, n_rows in cases:
        user = prompts.build_user_prompt(PERSONA, experiment, arm)
        rows = [e for e in _stimuli().values()
                if e["experiment"] == experiment and e["arm"] == arm][0]["rows"]
        for row in rows:
            assert row in user, (experiment, arm, row)
        assert str(n_rows) in _last_paragraph(user), (experiment, arm)
        assert n_rows == 10 or experiment != "false_consensus"


def test_false_consensus_asks_for_exactly_ten_answers() -> None:
    """The within-subject arm requests all 10 percentage answers."""
    user = prompts.build_user_prompt(PERSONA, "false_consensus", "all")
    assert "10" in _last_paragraph(user)
