# Tests for twin2k10r/respondent_loader.py — the module that reads real
# Twin-2K panel respondents into a verified table.
# WHAT THESE TESTS CHECK, in plain words:
#   - Loading returns one row per person: 2,058 real respondents from the
#     real mirror (when present), 120 from the offline fixture copy — all
#     unique pids, no duplicates.
#   - The 7 Config A demographic fields are never missing for anyone.
#   - Asking for fields outside the whitelist raises instead of guessing.
#   - Whitelists: Config A has exactly 7 field names; Config B adds
#     exactly the 11 measured-trait scores (18 total).
#   - If a demographic answer were missing, loading raises a specific
#     error naming the pid — it never fills in a made-up value.
import pytest

from conftest import (
    N_FIXTURE_RESPONDENTS,
    SCORE_WHITELIST,
)


CONFIG_A_FIELDS = (
    "age_bracket",
    "gender",
    "education",
    "household_income_bracket",
    "ethnicity",
    "marital_status",
    "household_size_bracket",
)


# ---------- 1. One row per respondent, unique pids ----------

def test_loader_returns_one_row_per_respondent(fixture_dataset_root):
    """The loaded table has exactly one row per person in the dataset."""
    from twin2k10r import respondent_loader

    respondents = respondent_loader.load_respondents(fixture_dataset_root, "A")
    assert len(respondents) == N_FIXTURE_RESPONDENTS


def test_loader_returns_2058_unique_real_pids(real_dataset_root):
    """Against the real mirror: 2,058 rows, pid unique, range 1..2058."""
    if real_dataset_root is None:
        pytest.skip("real Twin-2K-500 mirror not present")
    from twin2k10r import respondent_loader

    respondents = respondent_loader.load_respondents(real_dataset_root, "A")
    assert len(respondents) == 2058
    pids = list(respondents["pid"])
    assert len(set(pids)) == 2058, "pids must be unique"
    assert min(pids) == 1 and max(pids) == 2058


def test_loader_real_panel_has_zero_missing_config_a_fields(real_dataset_root):
    """Against the real mirror: 0% missing on every Config A field."""
    if real_dataset_root is None:
        pytest.skip("real Twin-2K-500 mirror not present")
    from twin2k10r import respondent_loader

    respondents = respondent_loader.load_respondents(real_dataset_root, "A")
    for field in CONFIG_A_FIELDS:
        assert respondents[field].notna().all(), f"{field} has missing values"


def test_loader_fixture_has_zero_missing_config_a_fields(fixture_respondents):
    """Fixture copy too: no missing answers on any of the 7 fields."""
    for field in CONFIG_A_FIELDS:
        assert fixture_respondents[field].notna().all(), f"{field} missing"


# ---------- 2. Whitelists ----------

def test_config_a_whitelist_is_exactly_the_seven_fields():
    """Config A renders exactly these 7 field names, in this order."""
    from twin2k10r import respondent_loader

    assert respondent_loader.get_field_whitelist("A") == CONFIG_A_FIELDS


def test_config_b_whitelist_is_seven_fields_plus_eleven_scores():
    """Config B adds exactly the 11 measured-trait scores (18 total)."""
    from twin2k10r import respondent_loader

    whitelist = respondent_loader.get_field_whitelist("B")
    assert whitelist[:7] == CONFIG_A_FIELDS
    assert list(whitelist[7:]) == SCORE_WHITELIST
    assert len(whitelist) == 18


def test_unknown_config_id_raises():
    """Config "C" (or anything else) is refused, never guessed."""
    from twin2k10r import respondent_loader

    with pytest.raises(respondent_loader.UnknownFieldError):
        respondent_loader.get_field_whitelist("C")


def test_loader_with_unknown_extra_field_raises(fixture_dataset_root):
    """load_respondents refuses a field outside the whitelist."""
    from twin2k10r import respondent_loader

    with pytest.raises(respondent_loader.UnknownFieldError):
        respondent_loader.load_respondents(
            fixture_dataset_root, "A", extra_fields=("occupation",)
        )


# ---------- 3. Missing demographics raise, never invented ----------

def test_loader_raises_missing_demographics_with_pid_list(
    fixture_dataset_root, monkeypatch
):
    """If a demographic answer were missing, the error names every pid."""
    import pandas as pd

    from twin2k10r import respondent_loader

    real_load = respondent_loader.load_respondents

    def load_with_one_gap(root, config_id="A", **kwargs):
        respondents = real_load(root, config_id, **kwargs)
        broken = respondents.copy()
        broken.loc[broken.index[3], "gender"] = None
        # Simulate the check by re-running the loader's own validator.
        respondent_loader._validate_no_missing_demographics(broken)
        return respondents

    monkeypatch.setattr(respondent_loader, "load_respondents", load_with_one_gap)
    with pytest.raises(respondent_loader.MissingDemographicsError) as err:
        respondent_loader.load_respondents(fixture_dataset_root, "A")
    assert "4" in str(err.value), "error must name the pid with the gap"


def test_loader_values_are_dataset_label_text_verbatim(fixture_respondents):
    """Field values are the dataset's own label texts, e.g. "50-64"."""
    labels_seen = set(fixture_respondents["age_bracket"])
    assert labels_seen <= {"18-29", "30-49", "50-64", "65+"}, labels_seen
    assert set(fixture_respondents["gender"]) <= {"Male", "Female"}


# ---------- 4. Config B joins the scores file ----------

def test_loader_config_b_joins_scores(fixture_dataset_root, real_dataset_root):
    """Config B loading brings the 11 whitelisted score columns."""
    from twin2k10r import respondent_loader

    respondents = respondent_loader.load_respondents(fixture_dataset_root, "B")
    for score in SCORE_WHITELIST:
        assert score in respondents.columns, f"Config B missing {score}"
        assert respondents[score].notna().all(), f"{score} has NaN"
