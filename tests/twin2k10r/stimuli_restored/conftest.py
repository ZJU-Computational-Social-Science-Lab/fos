# Fixtures for the restored-stimuli tests. Everything here points at the
# same read-only sources the build itself uses:
#   scripts_path      — puts scripts/ on sys.path so the new package imports
#                       like every other twin2k10r module.
#   catalog_path      — the Twin-2K-500 question catalog (stimulus source of
#                       truth); skipped when the dataset mirror is absent.
#   run6_root         — the archived run6 records (parity evidence); skipped
#                       when the archive is absent.
#   registry_csv      — the frozen 38-contrast experiment registry CSV.
#   contrasts_csv     — the frozen per-model signed-contrasts CSV.
#   restored_pkg      — the package under test, imported once.
import sys
from pathlib import Path

import pytest

_SCRIPTS = str(Path(__file__).resolve().parents[3] / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

_CATALOG = Path(
    "/home/justin/work/datasets/Twin-2K-500/"
    "question_catalog_and_human_response_csv/question_catalog.json"
)
_RUN6 = Path(
    "/home/justin/Documents/ZJU work/fos/results/unblinding/"
    "TWIN2K_UNBLINDING_LOGPROBS_6TASKS-20260919T025143"
)
_REGISTRY = Path(
    "/home/justin/Documents/Large Scale LLM Experiment/"
    "Paper/Supplementary/analysis_files/experiment_registry.csv"
)
_CONTRASTS = Path(
    "/home/justin/Documents/Large Scale LLM Experiment/_project_governance/"
    "stage10_data_reconciliation/corrected_results/stage3/"
    "corrected_signed_contrasts.csv"
)

# The one model leg the investigation used as parity evidence.
PARITY_MODEL = "glm-4.7-flash"


@pytest.fixture(scope="session")
def catalog_path() -> Path:
    if not _CATALOG.is_file():
        pytest.skip("Twin-2K-500 question catalog not present on this machine")
    return _CATALOG


@pytest.fixture(scope="session")
def run6_root() -> Path:
    if not _RUN6.is_dir():
        pytest.skip("archived run6 records not present on this machine")
    return _RUN6


@pytest.fixture(scope="session")
def registry_csv() -> Path:
    if not _REGISTRY.is_file():
        pytest.skip("frozen experiment registry CSV not present")
    return _REGISTRY


@pytest.fixture(scope="session")
def contrasts_csv() -> Path:
    if not _CONTRASTS.is_file():
        pytest.skip("frozen signed-contrasts CSV not present")
    return _CONTRASTS


@pytest.fixture(scope="session")
def restored_pkg():
    import twin2k10r.stimuli_restored as pkg

    return pkg


@pytest.fixture(scope="session")
def run6_record_factory(run6_root: Path):
    """The records.jsonl path of one archived leg:
    (experiment, blinding) -> Path."""

    def factory(experiment: str, blinding: str) -> Path:
        path = run6_root / PARITY_MODEL / f"{experiment}_{blinding}" / "records.jsonl"
        if not path.is_file():
            pytest.skip(f"archived leg missing: {path}")
        return path

    return factory

