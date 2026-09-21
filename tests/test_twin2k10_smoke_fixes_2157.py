# RED-phase tests for the three defects the twin2k10 smoke run exposed
# (TASK-2157; diagnosis in crew debug RESULT-2155). This file is NEW and
# locked: it appends no lines to any existing test file and touches no
# source module.
#
# WHAT THIS FILE CHECKS, in plain words:
#   - F1, parser: when a model answers "1. 42 / 2. 42 / 3. 42" and then
#     chats about its answer with ANOTHER numbered list, the parser must
#     keep the first value it saw for each row number and ignore the
#     chat — one value per distinct row number, never extra slots.
#   - F2, prompts: a multi-row question must show its answer scale (the
#     survey's own column labels with their numbers, "1 = Strongly
#     oppose" ... ) so the model answers numbers instead of words. The
#     "exactly N numbers" instruction stays; choice prompts must not
#     change at all (byte-identical snapshot guard).
#   - F3, legexec: a temperature sample whose list has a row that failed
#     to parse (None) must be counted as a parse failure and must never
#     let the record claim "succeeded: True".
#
# All offline: pure string parsing and fake scorer/sampler calls — no
# network, no models, no run directories.
import sys
from pathlib import Path

# The launch scripts live in scripts/ and are not on pytest's pythonpath.
_SCRIPTS = str(Path(__file__).resolve().parent.parent / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from twin2k10 import config, experiments, legexec, prompts, scoring  # noqa: E402

# A complete 11-field persona, the same fields the locked prompt tests use.
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

# The verbatim stored raw answer of the failing linda sample (qwen3-4b /
# linda / no_conjunction / unblinded, sample 13 — copied character for
# character from RESULT-2155, including the trailing double spaces). A
# compliant 3-row answer is followed by chatty commentary that itself
# contains a nested numbered list, cut off mid-sentence by the token cap.
LINDA_CHATTY_RAW = (
    '1. 42  \n2. 42  \n3. 42  \n\n(Note: This response reflects the '
    'standard result of the "Linda problem" in cognitive psychology, '
    'where people tend to overestimate the probability of specific, '
    'detailed descriptions (like being a teacher or yoga instructor) '
    'over more general ones (like being a bank teller), even though '
    'statistically, the bank teller scenario is more likely. However, '
    'in this case, the correct probabilities — based on statistical '
    'reasoning — would be:  \n1. It is *less likely* that Linda is a '
    'teacher — so 1. 20  \n2. It'
)

# The current allais form1 user prompt, captured byte for byte before any
# scale rendering exists. If F2 accidentally touches choice questions,
# this guard fails; stimuli.json is sha-pinned so this stays stable.
ALLAIS_FORM1_PROMPT_SNAPSHOT = (
    "EMBODY THIS PERSON:\n"
    "age: 41\n"
    "gender: female\n"
    "education: bachelor's degree\n"
    "household_income: $60,000-$79,999\n"
    "occupation: teacher\n"
    "ethnicity: White\n"
    "marital_status: married\n"
    "household_size: 4\n"
    "number_of_children: 2\n"
    "state: Ohio\n"
    "home_ownership: own\n"
    "\n"
    "Choose between:\n"
    "\n"
    "A. One million dollars for sure\n"
    "B. 89% probability of one million dollars 10% probablity of five "
    "miillion dollars 1% probability of nothing\n"
    "\n"
    "Answer with only the corresponding uppercase letter."
)


def _columns(experiment: str, arm: str) -> list[str]:
    """The survey's own answer-scale labels of one arm's item (helper)."""
    stimuli = experiments.load_stimuli()
    entry = next(
        e for e in stimuli.values()
        if e["experiment"] == experiment and e["arm"] == arm
    )
    return list(entry["columns"])


def _offline_multi_record(experiment: str, arm: str,
                          sample_text: str) -> dict:
    """One real multi-row cell's record with a fake sampler (helper).

    Every one of the K temperature samples returns sample_text; the fake
    scorer never fails, so the ONLY possible failure on the record is a
    parse failure — exactly the situation the smoke diagnosis described.
    """
    context = legexec.LegContext(
        model=config.MODELS[0],
        model_id=f"offline-{config.MODELS[0]}",
        base_url="http://127.0.0.1:8080",
        personas=[{"persona_id": 0}],
        stimuli=experiments.load_stimuli(),
        inference=legexec.inference_settings("http://127.0.0.1:8080"),
    )

    def fake_sampler(messages: list) -> dict:
        return {"samples": [sample_text] * config.NUMERIC_SAMPLES_K,
                "first_top_logprobs": [], "calls_failed": 0,
                "errors": [], "elapsed_seconds": 0.0}

    def fake_scorer(messages: list) -> dict:
        return {"top_logprobs": [], "decision_position": 0,
                "skipped_prefix": [], "skipped_len": 0, "succeeded": True}

    cell = (config.MODELS[0], 0, experiment, arm, "blinded")
    return legexec.execute_cell(context, fake_scorer, fake_sampler, cell)


# ---------------------------------------------------------------------------
# F1 — parser over-collection: duplicate row numbers must not add slots.
# ---------------------------------------------------------------------------


def test_parser_keeps_the_first_answer_when_a_row_number_repeats() -> None:
    """The verbatim chatty linda sample parses to exactly [42, 42, 42].

    The model's real answer is the first numbered list ("1. 42 / 2. 42 /
    3. 42"); the "(Note: ...)" commentary repeats row numbers 1 and 2
    while talking ABOUT the answer, and the parser must not fold that
    talk into extra result slots (it produced [42, 1, 42, None, 42]).
    """
    assert scoring.parse_multi_numeric(LINDA_CHATTY_RAW) == [42, 42, 42]


def test_parser_returns_one_value_per_distinct_row_number() -> None:
    """A repeated row number never widens the result: 3 lines, 2 rows."""
    assert scoring.parse_multi_numeric("2. 7\n1. 5\n1. 9") == [5, 7]


# ---------------------------------------------------------------------------
# F2 — prompt scale rendering: multi-row prompts must define the numbers.
# ---------------------------------------------------------------------------


def test_false_consensus_prompt_shows_the_numbered_response_scale() -> None:
    """Every oppose/support label appears with its number in the prompt.

    The item's columns are the survey's 5-point scale, so the prompt must
    map each position ("1 = Strongly oppose" ... "5 = Strongly support")
    and still keep the locked "exactly 10 numbers" instruction.
    """
    user = prompts.build_user_prompt(PERSONA, "false_consensus", "all")
    for number, label in enumerate(_columns("false_consensus", "all"),
                                   start=1):
        assert f"{number} = {label}" in user, (number, label)
    assert "exactly 10 numbers" in user


def test_linda_prompt_shows_the_numbered_response_scale() -> None:
    """Every probability label appears with its number in the prompt.

    Linda's 6-point scale ("1 = Extremely improbable" ... "6 = Extremely
    probable") must be rendered so its three answers mean something, and
    the locked "exactly 3 numbers" instruction stays.
    """
    user = prompts.build_user_prompt(PERSONA, "linda", "conjunction")
    for number, label in enumerate(_columns("linda", "conjunction"),
                                   start=1):
        assert f"{number} = {label}" in user, (number, label)
    assert "exactly 3 numbers" in user


def test_choice_prompt_is_unchanged_by_scale_rendering() -> None:
    """The allais form1 prompt stays byte-identical (green-today guard).

    F2 may only touch multi-row rendering; a choice prompt must be
    exactly what it was before, so this snapshot must keep passing.
    """
    user = prompts.build_user_prompt(PERSONA, "allais", "form1")
    assert user == ALLAIS_FORM1_PROMPT_SNAPSHOT


# ---------------------------------------------------------------------------
# F3 — honest counting: None rows are parse failures, never "succeeded".
# ---------------------------------------------------------------------------


def test_multi_numeric_counter_counts_samples_with_none_rows_as_failures() -> None:
    """Ten Support/Oppose words parse to all-None rows: all K counted.

    The word answers have the right length (10) so the old length-only
    check counted zero failures; every sample whose list holds a None
    row must land in multi_numeric_parse_failures instead.
    """
    words = "\n".join(
        f"{row}. {'Support' if row % 2 else 'Oppose'}"
        for row in range(1, 11)
    )
    record = _offline_multi_record("false_consensus", "all", words)
    assert record["multi_numeric_parse_failures"] == config.NUMERIC_SAMPLES_K
    assert record["parse_failures"] == config.NUMERIC_SAMPLES_K


def test_sample_with_any_none_row_is_not_stamped_succeeded() -> None:
    """One unparseable row in an otherwise complete list blocks success.

    Nine numeric rows plus one "Oppose" give a 10-entry list with exactly
    one None row — the record must not claim succeeded: True, because a
    failure like this must never hide inside a "healthy" record.
    """
    sample = "\n".join(
        f"{row}. {'Oppose' if row == 4 else row * 10}"
        for row in range(1, 11)
    )
    record = _offline_multi_record("false_consensus", "all", sample)
    assert record["succeeded"] is False
