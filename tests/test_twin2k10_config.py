# Locked tests for the twin2k10 study's configuration module (TASK-2139 RED
# phase; tests ONLY — no implementation lives yet, so every test here errors
# at collection until scripts/twin2k10/config.py exists).
#
# WHAT THIS FILE CHECKS, in plain words:
#   - The study runs the exact same 15 local models as the proven twin2k6
#     study, in the same order.
#   - The grid knobs match twin2k6: two blinding arms, 100 personas, design
#     seed 42, the R1 inference knobs, the 0.80 branch-mass flag, and the
#     at-most-50-records fsync promise.
#   - twin2k10's own knobs: 20 temperature samples per numeric answer, and
#     run names that start with "T2K10-".
#   - The 23 survey questions (10 experiments) are shipped inside this repo
#     and are a verbatim copy of the authoritative research delivery.
#
# All offline: file reads and pure asserts; no network, no model loads.
import json
import sys
from pathlib import Path

import pytest

# The launch scripts live in scripts/ and are not on pytest's pythonpath.
_SCRIPTS = str(Path(__file__).resolve().parent.parent / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from twin2k10 import config  # noqa: E402

_REPO = Path(__file__).resolve().parent.parent

# The authoritative research delivery this study's questions must match.
# Read-only source of truth; the repo ships its own verbatim copy.
AUTHORITATIVE_STIMULI = Path(
    "/home/justin/work/research/TWIN2K-UNBLIND-10TASKS/human_benchmark/stimuli.json"
)


def _load_authoritative() -> list[dict]:
    """The 23 authoritative stimulus entries, in file order (helper)."""
    with open(AUTHORITATIVE_STIMULI, encoding="utf-8") as handle:
        return json.load(handle)


def _load_shipped_entries() -> list[dict]:
    """The repo's shipped stimulus entries, wrapper-agnostic (helper).

    Accepts either a bare list of entries or a dict carrying them under a
    "stimuli" key — same two shapes the research delivery uses.
    """
    with open(config.STIMULI_PATH, encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, dict):
        return data["stimuli"]
    return data


def test_model_list_is_exactly_twin2k6s_15_models_in_the_same_order() -> None:
    """twin2k10 reuses twin2k6's pinned 15-model queue, byte for byte."""
    from twin2k6 import config as k6_config

    assert list(config.MODELS) == list(k6_config.MODELS)
    assert len(set(config.MODELS)) == 15


def test_grid_constants_mirror_twin2k6() -> None:
    """Blinding arms, persona pool, seed and inference knobs equal twin2k6."""
    from twin2k6 import config as k6_config

    assert config.BLINDINGS == ("blinded", "unblinded")
    assert config.BLINDINGS == k6_config.BLINDINGS
    assert config.PERSONA_COUNT == 100
    assert config.SEED == 42
    assert config.SCAN_TOKENS == k6_config.SCAN_TOKENS
    assert config.TEMPERATURE == k6_config.TEMPERATURE
    assert config.TOP_K >= 100
    assert config.PROBABILITY_FLOOR == k6_config.PROBABILITY_FLOOR
    assert config.LOW_BRANCH_MASS_THRESHOLD == k6_config.LOW_BRANCH_MASS_THRESHOLD
    assert config.FSYNC_EVERY == 50
    assert config.DEFAULT_BASE_URL == k6_config.DEFAULT_BASE_URL
    assert config.DEFAULT_MANAGER_URL == k6_config.DEFAULT_MANAGER_URL


def test_numeric_answers_use_exactly_20_temperature_samples() -> None:
    """NUMERIC_SAMPLES_K pins the K=20 sample count for numeric items."""
    assert config.NUMERIC_SAMPLES_K == 20


def test_run_names_start_with_the_T2K10_prefix() -> None:
    """Run folders can never collide with twin2k6 runs."""
    from twin2k6 import config as k6_config

    assert config.RUN_NAME_PREFIX == "T2K10-"
    assert config.STUDY_NAME != k6_config.STUDY_NAME


def test_stimuli_file_is_shipped_inside_this_repo() -> None:
    """The study never depends on a machine-specific research path."""
    assert config.STIMULI_PATH.is_file(), config.STIMULI_PATH
    assert config.REPO_ROOT in config.STIMULI_PATH.resolve().parents


def test_shipped_stimuli_are_a_verbatim_copy_of_the_research_delivery() -> None:
    """All 23 shipped entries equal the authoritative file, entry by entry."""
    authoritative = {entry["qid"]: entry for entry in _load_authoritative()}
    shipped = {entry["qid"]: entry for entry in _load_shipped_entries()}
    assert len(_load_shipped_entries()) == 23
    assert shipped == authoritative


def test_shipped_stimuli_cover_10_experiments_and_23_questions() -> None:
    """The shipped catalogue holds the 10 study experiments, 23 qids."""
    experiments = {entry["experiment"] for entry in _load_shipped_entries()}
    assert len(_load_shipped_entries()) == 23
    assert experiments == {
        "allais", "linda", "base_rate", "anchoring_redwood",
        "anchoring_african", "outcome_bias", "myside", "prob_matching",
        "abs_relative", "false_consensus",
    }


# --------------------------------------------------------------------------
# TASK-2150 RED tests — review blocker B1 (RESULT-2146): the numeric
# generation window must fit a bare 10-row multi-row answer (~50 tokens
# even with zero prose) with comfortable headroom, or every 10-row
# sample is silently cut off before its last rows.
# --------------------------------------------------------------------------


def test_numeric_max_tokens_fits_a_full_ten_row_answer_with_headroom() -> None:
    """A bare 10-row answer is ~50 tokens; the window must be >= 128."""
    assert config.NUMERIC_MAX_TOKENS >= 128, (
        f"NUMERIC_MAX_TOKENS={config.NUMERIC_MAX_TOKENS} truncates a bare "
        "10-row multi_numeric answer (~50 tokens) before its last rows"
    )
