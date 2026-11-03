# Fixtures for the twin2k10r ↔ expansion integration tests. Each helper
# builds one piece of the picture the tests need, fully offline:
#   _make_source_record — one fake Config A pool record (dataset field
#       names, bracket-style values, pid/pool_id bookkeeping keys).
#   source_pool_path — a 100-record stand-in for the real Stage 0 pool.
#   adapted_pool_path — that stand-in pool after the adapter ran on it,
#       written once per session.
#   real_pool_path — the canonical Stage 0 Config A pool if it exists on
#       this machine (hash-pinned); tests skip when it does not.
#   expansion — the frozen expansion pipeline package, imported read-only.
#   integration_pkg — puts scripts/ on sys.path so `twin2k10r.integration`
#       imports like the other twin2k10r modules.
import hashlib
import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = str(Path(__file__).resolve().parents[2] / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from twin2k10r.integration import expansion_pool  # noqa: E402

FIXTURE_AGES = ["18-29", "30-49", "50-64", "65+"]
FIXTURE_GENDERS = ["Male", "Female"]
FIXTURE_EDUCATION = "High school graduate"
FIXTURE_ETHNICITY = "White"
FIXTURE_MARITAL = "Married"
FIXTURE_INCOME = "$75,000-$100,000"
FIXTURE_HOUSEHOLD_SIZE = "4"


def _make_source_record(pool_id: int) -> dict:
    """One deterministic fake Config A record for fake pid pool_id+1."""
    return {
        "pid": 900000 + pool_id,
        "pool_id": pool_id,
        "age_bracket": FIXTURE_AGES[pool_id % len(FIXTURE_AGES)],
        "gender": FIXTURE_GENDERS[pool_id % len(FIXTURE_GENDERS)],
        "education": FIXTURE_EDUCATION,
        "household_income_bracket": FIXTURE_INCOME,
        "ethnicity": FIXTURE_ETHNICITY,
        "marital_status": FIXTURE_MARITAL,
        "household_size_bracket": FIXTURE_HOUSEHOLD_SIZE,
    }


def _write_pool(path: Path, records: list[dict]) -> str:
    """Write records as JSONL and return the file's SHA-256."""
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="session")
def integration_pkg():
    """The adapter package, imported the way the repo's tests import it."""
    return expansion_pool


@pytest.fixture(scope="session")
def source_pool_path(tmp_path_factory) -> Path:
    """A 100-record stand-in for the real Config A pool."""
    path = tmp_path_factory.mktemp("integration") / "source_pool.jsonl"
    records = [_make_source_record(i) for i in range(100)]
    _write_pool(path, records)
    return path


@pytest.fixture(scope="session")
def adapted_pool_path(source_pool_path, tmp_path_factory) -> Path:
    """The stand-in pool after one adapter pass (write-once)."""
    out = tmp_path_factory.mktemp("integration") / "adapted_pool.jsonl"
    expansion_pool.write_adapted_pool(source_pool_path, out)
    return out


@pytest.fixture(scope="session")
def real_pool_path() -> Path | None:
    """The canonical Stage 0 pool, or None when this machine lacks it."""
    path = expansion_pool.SOURCE_POOL_PATH
    if not path.exists():
        return None
    assert (
        expansion_pool._sha256_of(path) == expansion_pool.SOURCE_POOL_SHA256
    ), "the Stage 0 pool on disk no longer matches its pinned hash"
    return path


@pytest.fixture(scope="session")
def expansion():
    """The frozen expansion pipeline package (read-only import)."""
    return expansion_pool.load_expansion_pipeline()


@pytest.fixture(scope="session")
def expansion_ready_experiments(expansion) -> dict:
    """One READY expansion experiment per family, for prompt tests."""
    families = {
        "T2KX-ml1_gamblers_fallacy": "ML1",
        "T2KX-ml2_hauser_s1": "ML2",
        "T2KX-howard823": "TESS",
    }
    ready = set(expansion.registry.ready_experiments())
    return {
        exp_id: family
        for exp_id, family in families.items()
        if exp_id in ready
    }
