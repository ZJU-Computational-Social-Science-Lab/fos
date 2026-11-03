# This file reads real Twin-2K panel respondents into a verified table.
# It reads the dataset's own label CSV (so every value is the dataset's
# own wording, verbatim), renames the survey question ids to the study's
# persona field names, and (for Config B) joins the measured trait
# scores from the wave-1 scores file. It refuses to guess: unknown
# fields raise UnknownFieldError, missing demographic answers raise
# MissingDemographicsError naming every affected person.
# Functions:
#   get_field_whitelist — the exact renderable field names for "A" or "B".
#   load_respondents    — one row per person, verified and complete.
#   _validate_no_missing_demographics — the missing-answer check, kept
#                         separate so tests can exercise it directly.
from pathlib import Path

import pandas as pd

# Config A: the 7 real demographic fields, in render order. These are the
# dataset columns that exist; the 4 unavailable fields (occupation,
# number_of_children, state, home_ownership) are simply never here.
CONFIG_A_FIELDS = (
    "age_bracket",
    "gender",
    "education",
    "household_income_bracket",
    "ethnicity",
    "marital_status",
    "household_size_bracket",
)

# Config B adds these 11 measured trait scores (questionnaire-based, never
# task-performance based — see the blocklist below).
SCORE_WHITELIST = (
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

# Task-performance scores that must NEVER be rendered: they are computed
# from the panel's own experiment items, so they would leak the outcome.
SCORE_BLOCKLIST = (
    "score_fluid",
    "score_crystallized",
    "score_syllogism_priming",
    "score_syllogism_test",
    "score_syllogism_merged",
    "score_actual_total",
    "score_overconfidence",
    "score_overplacement",
    "score_ultimatum_sender",
    "score_ultimatum_accepted",
    "score_mentalaccounting",
    "crt2_score",
    "MXsum",
    "rotsum",
)

# Survey question id -> study field name (the dataset's QID mapping).
QID_TO_FIELD = {
    "QID13": "age_bracket",
    "QID12": "gender",
    "QID14": "education",
    "QID21": "household_income_bracket",
    "QID15": "ethnicity",
    "QID17": "marital_status",
    "QID23": "household_size_bracket",
}

# The full panel size; a shorter table means the dataset is not the one
# the study was designed for.
EXPECTED_PANEL_COUNT = 2058


class UnknownFieldError(Exception):
    """A field outside the whitelist was requested. Never guessed around."""


class MissingDemographicsError(Exception):
    """Some respondents' demographic answers are missing. Names the pids."""


def get_field_whitelist(config_id: str) -> tuple:
    """The exact renderable field names for one configuration.

    In: "A" or "B". Out: the field-name tuple, Config A's 7 demographics
    plus (for B) the 11 measured scores. Anything else raises
    UnknownFieldError — this function is the single place the whitelist
    lives.
    """
    if config_id == "A":
        return CONFIG_A_FIELDS
    if config_id == "B":
        return CONFIG_A_FIELDS + SCORE_WHITELIST
    raise UnknownFieldError(f"unknown pool config {config_id!r} (use A or B)")


def _validate_no_missing_demographics(respondents) -> None:
    """Refuse a table where any Config A answer is missing.

    Raises MissingDemographicsError listing every affected pid — the
    pipeline never fills a gap with a made-up value.
    """
    missing_pids = []
    for field in CONFIG_A_FIELDS:
        gap = respondents[respondents[field].isna()]
        missing_pids.extend(int(pid) for pid in gap["pid"])
    if missing_pids:
        raise MissingDemographicsError(
            "missing demographic answers for pids "
            f"{sorted(set(missing_pids))} — refusing to invent values"
        )


def load_respondents(dataset_root, config_id: str = "A",
                     extra_fields: tuple = ()):
    """Read every Twin-2K respondent once, verified.

    In: the dataset root path, the config id ("A" or "B"), and optional
    extra fields (which must themselves be whitelisted). Out: a table
    with one row per pid and exactly the whitelisted columns (string
    values, the dataset's own label text). Raises UnknownFieldError for
    unknown fields or configs, FileNotFoundError for a missing dataset
    file, MissingDemographicsError for gaps.
    """
    whitelist = get_field_whitelist(config_id)
    for field in extra_fields:
        if field in SCORE_BLOCKLIST:
            raise UnknownFieldError(
                f"{field} is blocklisted (task-performance score) and can "
                "never be rendered"
            )
        if field not in whitelist:
            raise UnknownFieldError(
                f"{field} is not on the {config_id!r} whitelist"
            )
    label_csv = (Path(dataset_root)
                 / "question_catalog_and_human_response_csv"
                 / "wave1_3_response_label.csv")
    panel = pd.read_csv(label_csv, usecols=["pid", *QID_TO_FIELD])
    if panel["pid"].duplicated().any():
        raise MissingDemographicsError("panel pids are not unique")
    respondents = panel.rename(columns=QID_TO_FIELD)
    respondents = respondents[["pid", *CONFIG_A_FIELDS]]
    _validate_no_missing_demographics(respondents)

    # Both configs need the scores joined at load time: Config B renders
    # them, Config A carries them harmlessly (map_fields filters by the
    # whitelist, so A personas never show a score).
    scores_csv = (Path(dataset_root) / "raw_data" / "wave 1 scores.csv")
    scores = pd.read_csv(scores_csv).rename(columns={"TWIN_ID": "pid"})
    missing_scores = [c for c in SCORE_WHITELIST if c not in scores.columns]
    if missing_scores:
        raise UnknownFieldError(f"scores file lacks {missing_scores}")
    respondents = respondents.merge(scores[["pid", *SCORE_WHITELIST]],
                                    on="pid", how="left")
    for score in SCORE_WHITELIST:
        if respondents[score].isna().any():
            raise MissingDemographicsError(
                f"{score} has missing values after the join"
            )
    return respondents
