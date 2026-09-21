# Locked tests for the twin2k10 study's experiment register (TASK-2139 RED
# phase; tests ONLY — no implementation lives yet, so every test here errors
# at collection until scripts/twin2k10/experiments.py exists).
#
# WHAT THIS FILE CHECKS, in plain words:
#   - The study registers exactly its 10 experiments, and every one of the
#     23 survey questions is registered under the right experiment.
#   - The experimental versions (arms) of every experiment match the
#     authoritative stimuli file, including each arm's question ids in file
#     order — the two anchoring arms each carry TWO questions (the
#     more/less anchor choice and the numeric estimate).
#   - Choice questions show exactly as many A, B, C... letters as they have
#     answer options.
#   - false_consensus is the one within-subject experiment: a single arm
#     whose question has 10 rows.
#
# All offline: reads the study's own loaded stimuli; no network, no models.
import sys
from pathlib import Path

import pytest

# The launch scripts live in scripts/ and are not on pytest's pythonpath.
_SCRIPTS = str(Path(__file__).resolve().parent.parent / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from twin2k10 import config, experiments  # noqa: E402

# The 10 experiment names, pinned by the task.
EXPECTED_EXPERIMENT_NAMES = {
    "allais", "linda", "base_rate", "anchoring_redwood",
    "anchoring_african", "outcome_bias", "myside", "prob_matching",
    "abs_relative", "false_consensus",
}


def _stimuli() -> dict[str, dict]:
    """The study's own loaded stimuli, keyed by question id (helper)."""
    return experiments.load_stimuli()


def _stimulus_arm_qids() -> dict[tuple[str, str], list[str]]:
    """Every (experiment, arm) with its question ids in file order (helper)."""
    entries = _stimuli().values()
    pairs: dict[tuple[str, str], list[str]] = {}
    for entry in sorted(entries, key=lambda e: e["qid"]):
        pairs.setdefault(
            (entry["experiment"], entry["arm"]), []
        ).append(entry["qid"])
    return pairs


def _spec_arm_qids(spec) -> dict[str, tuple[str, ...]]:
    """An experiment's arm -> question-ids mapping, normalized (helper).

    The registry may store an arm's questions as one id or a tuple; both
    normalize to a tuple here so the tests stay about behaviour, not shape.
    """
    arms: dict[str, tuple[str, ...]] = {}
    for arm_name, qids in spec.arms:
        if isinstance(qids, str):
            arms[arm_name] = (qids,)
        else:
            arms[arm_name] = tuple(qids)
    return arms


def test_the_study_registers_exactly_its_ten_experiments() -> None:
    """EXPERIMENTS holds exactly the 10 study experiments, none else."""
    assert set(experiments.EXPERIMENTS) == EXPECTED_EXPERIMENT_NAMES
    assert len(experiments.EXPERIMENTS) == 10


def test_loading_stimuli_returns_exactly_the_23_questions() -> None:
    """load_stimuli reads the shipped file and indexes it by question id."""
    stimuli = _stimuli()
    assert len(stimuli) == 23
    assert all(qid.startswith("QID") for qid in stimuli)


def test_every_question_is_registered_under_its_experiment() -> None:
    """All 23 question ids appear across the registry, each exactly once."""
    registered: list[str] = []
    for spec in experiments.EXPERIMENTS.values():
        for qids in _spec_arm_qids(spec).values():
            registered.extend(qids)
    assert len(registered) == 23
    assert set(registered) == set(_stimuli())


def test_arms_match_the_stimuli_file_exactly() -> None:
    """Every experiment's arms and their question ids match the file."""
    file_arms = _stimulus_arm_qids()
    for exp_name, spec in experiments.EXPERIMENTS.items():
        spec_arms = _spec_arm_qids(spec)
        file_qids = {
            arm: tuple(qids) for (experiment, arm), qids in file_arms.items()
            if experiment == exp_name
        }
        assert spec_arms == file_qids, exp_name


def test_anchoring_arms_carry_both_the_anchor_choice_and_the_estimate() -> None:
    """Each anchoring arm holds TWO questions: the MC anchor, then the TE."""
    for exp_name in ("anchoring_redwood", "anchoring_african"):
        spec = experiments.EXPERIMENTS[exp_name]
        arms = _spec_arm_qids(spec)
        assert set(arms) == {"low", "high"}, exp_name
        for arm in ("low", "high"):
            qids = arms[arm]
            assert len(qids) == 2, (exp_name, arm)
            kinds = [_stimuli()[qid]["response_kind"] for qid in qids]
            assert kinds == ["choice", "numeric"], (exp_name, arm)


def test_choice_letters_match_the_number_of_answer_options() -> None:
    """Every choice question shows A, B, ... up to its option count."""
    stimuli = _stimuli()
    for entry in stimuli.values():
        if entry["response_kind"] != "choice":
            continue
        options = entry["options"]
        letters = entry["labels"]
        expected = [chr(ord("A") + i) for i in range(len(options))]
        assert letters == expected, entry["qid"]
        assert len(options) == len(entry["labels"]), entry["qid"]


def test_false_consensus_is_within_subject_with_one_arm_and_ten_rows() -> None:
    """The one within-subject experiment: single arm, 10-row question."""
    spec = experiments.EXPERIMENTS["false_consensus"]
    arms = _spec_arm_qids(spec)
    assert list(arms) == ["all"]
    qid = arms["all"][0]
    assert len(_stimuli()[qid]["rows"]) == 10


def test_stimulus_for_returns_the_right_question_for_an_arm() -> None:
    """stimulus_for(experiment, arm) lands on one of that arm's questions."""
    stimulus = experiments.stimulus_for("allais", "form1")
    assert stimulus["qid"] in {"QID192", "QID193"}
    assert stimulus["experiment"] == "allais"
