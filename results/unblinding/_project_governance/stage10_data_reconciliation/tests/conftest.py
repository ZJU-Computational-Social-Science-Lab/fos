# conftest.py — shared pytest fixtures for the Stage 10 test suite: the
# verified canonical tables (loaded through the real loader, so a broken
# manifest fails every test loudly) and a few frozen reference frames.

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import canonical_data  # noqa: E402
import stage10_common as sc  # noqa: E402


@pytest.fixture(scope="session")
def arm() -> pd.DataFrame:
    return canonical_data.load_table("arm_outcomes")


@pytest.fixture(scope="session")
def effects() -> pd.DataFrame:
    return canonical_data.load_table("model_effects")


@pytest.fixture(scope="session")
def uncertainty() -> pd.DataFrame:
    return canonical_data.load_table("uncertainty")


@pytest.fixture(scope="session")
def paired() -> pd.DataFrame:
    return canonical_data.load_table("paired")


@pytest.fixture(scope="session")
def old_vs_new() -> pd.DataFrame:
    return canonical_data.load_table("old_vs_corrected")


@pytest.fixture(scope="session")
def register() -> list[dict]:
    return sc.load_register()


@pytest.fixture(scope="session")
def frozen_stage5() -> pd.DataFrame:
    return pd.read_csv(sc.STAGE5_DATASET)


@pytest.fixture(scope="session")
def frozen_262() -> pd.DataFrame:
    return pd.read_csv(sc.FROZEN_262)
