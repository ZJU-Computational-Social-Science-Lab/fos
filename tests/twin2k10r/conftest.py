# Fixtures for the twin2k10r real-respondent persona pipeline tests.
# This file builds a small, fully offline copy of the Twin-2K-500 dataset
# layout (a "fixture dataset root") so the tests never need the real
# ~699 MB mirror or any network access. Each helper below makes one piece
# of that fake dataset:
#   _LABEL_TO_CODE / _CODE_TO_LABEL — the fixed number <-> text mapping the
#       real dataset uses for its demographic answer codes.
#   _write_catalog, _write_response_csvs, _write_scores_csv — write the
#       question catalog, the two response CSVs (numeric + label), and the
#       wave-1 scores CSV.
#   fixture_dataset_root (session fixture) — a tmp directory holding all of
#       the above for 120 fake respondents.
#   real_dataset_root (session fixture) — the path of the real mirror, or
#       None when it is not present on this machine (tests skip then).
#   fixture_respondents (session fixture) — the loaded respondent table for
#       the fixture dataset, ready for pool-builder tests.
import sys
from pathlib import Path

import pytest

# The study packages live in scripts/ and are not on pytest's pythonpath.
_SCRIPTS = str(Path(__file__).resolve().parent.parent.parent / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

REAL_DATASET_ROOT = Path("/home/justin/work/datasets/Twin-2K-500")

N_FIXTURE_RESPONDENTS = 120

# The fixed code mapping the real dataset uses (numeric CSV -> label CSV).
# Option codes are 1-based positions into the catalog option list.
GENDER = {1: "Male", 2: "Female"}
AGE = {1: "18-29", 2: "30-49", 3: "50-64", 4: "65+"}
EDUCATION = {
    1: "Less than high school",
    2: "High school graduate",
    3: "Some college, no degree",
    4: "Associate's degree",
    5: "College graduate/some postgrad",
    6: "Postgraduate",
}
ETHNICITY = {1: "White", 2: "Black", 3: "Asian", 4: "Hispanic", 5: "Other"}
MARITAL = {
    1: "Married",
    2: "Living with a partner",
    3: "Divorced",
    4: "Separated",
    5: "Widowed",
    6: "Never been married",
}
INCOME = {
    1: "Less than $30,000",
    2: "$30,000-$50,000",
    3: "$50,000-$75,000",
    4: "$75,000-$100,000",
    5: "$100,000 or more",
}
HOUSEHOLD_SIZE = {1: "1", 2: "2", 3: "3", 4: "4", 5: "More than 4"}

# QID -> (column name, code->label map)
DEMOGRAPHIC_QIDS = {
    "QID12": ("QID12", GENDER),
    "QID13": ("QID13", AGE),
    "QID14": ("QID14", EDUCATION),
    "QID15": ("QID15", ETHNICITY),
    "QID17": ("QID17", MARITAL),
    "QID21": ("QID21", INCOME),
    "QID23": ("QID23", HOUSEHOLD_SIZE),
}

# The 11 whitelisted Config B score columns (from CORRECTED_DESIGN §2.3).
SCORE_WHITELIST = [
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
]

# Task-performance scores that must NEVER be rendered (the blocklist).
SCORE_BLOCKLIST = [
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
]


def _fake_answer(pid: int, qid: str):
    """A fixed, deterministic fake demographic answer for one fake pid."""
    labels = DEMOGRAPHIC_QIDS[qid][1]
    return pid * (list(DEMOGRAPHIC_QIDS).index(qid) + 3) % len(labels) + 1


def _write_catalog(root: Path) -> None:
    """A minimal question_catalog.json listing the demographic QIDs."""
    import json

    d = root / "question_catalog_and_human_response_csv"
    d.mkdir(parents=True, exist_ok=True)
    entries = []
    for qid, (_col, labels) in DEMOGRAPHIC_QIDS.items():
        entries.append({
            "QuestionID": qid,
            "QuestionType": "MC",
            "Options": sorted(set(labels.values())),
            "BlockName": "Demographics",
            "csv_columns": [qid],
        })
    (d / "question_catalog.json").write_text(json.dumps(entries, indent=1))


def _write_response_csvs(root: Path) -> None:
    """The numeric and label variants of wave1_3_response for the fixture."""
    import pandas as pd

    d = root / "question_catalog_and_human_response_csv"
    d.mkdir(parents=True, exist_ok=True)
    rows_num = []
    rows_lab = []
    for pid in range(1, N_FIXTURE_RESPONDENTS + 1):
        num = {"pid": pid}
        lab = {"pid": pid}
        for qid, (col, labels) in DEMOGRAPHIC_QIDS.items():
            code = _fake_answer(pid, qid)
            num[col] = code
            lab[col] = labels[code]
        rows_num.append(num)
        rows_lab.append(lab)
    pd.DataFrame(rows_num).to_csv(d / "wave1_3_response.csv", index=False)
    pd.DataFrame(rows_lab).to_csv(d / "wave1_3_response_label.csv", index=False)


def _write_scores_csv(root: Path) -> None:
    """The wave-1 scores CSV with whitelisted + blocklisted score columns."""
    import pandas as pd

    d = root / "raw_data"
    d.mkdir(parents=True, exist_ok=True)
    rows = []
    for pid in range(1, N_FIXTURE_RESPONDENTS + 1):
        row = {"TWIN_ID": pid}
        for i, col in enumerate(SCORE_WHITELIST):
            row[col] = round(1.0 + ((pid * (i + 2)) % 40) / 10.0, 3)
        for col in SCORE_BLOCKLIST:
            row[col] = 0
        rows.append(row)
    pd.DataFrame(rows).to_csv(d / "wave 1 scores.csv", index=False)


@pytest.fixture(scope="session")
def fixture_dataset_root(tmp_path_factory) -> Path:
    """A small offline stand-in for the Twin-2K-500 dataset root."""
    root = tmp_path_factory.mktemp("twin2k500_fixture")
    _write_catalog(root)
    _write_response_csvs(root)
    _write_scores_csv(root)
    return root


@pytest.fixture(scope="session")
def real_dataset_root() -> Path | None:
    """The real dataset root, or None when the mirror is absent."""
    return REAL_DATASET_ROOT if REAL_DATASET_ROOT.exists() else None


@pytest.fixture(scope="session")
def fixture_respondents(fixture_dataset_root):
    """The loaded respondent table for the fixture dataset (Config A)."""
    from twin2k10r import respondent_loader

    return respondent_loader.load_respondents(fixture_dataset_root, "A")
