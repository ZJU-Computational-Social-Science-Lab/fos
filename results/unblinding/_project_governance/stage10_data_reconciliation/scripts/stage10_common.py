# stage10_common.py — shared paths, constants, and small helpers for the
# Stage 10 canonical rebuild. Everything the rebuild scripts need to find
# the frozen inputs (read-only) and to write outputs safely lives here, so
# no script hard-codes a path or a seed on its own.
#
# What each thing does:
#   REPO            — the read-write git worktree this stage writes into.
#   UNBL            — the read-only unblinding data root (frozen inputs).
#   STAGE10         — this stage's own output directory.
#   RUN6 / RUN10 / T2KX — the frozen inference-record run roots.
#   SEED            — the single recorded random seed for all resampling.
#   VERSION         — the canonical dataset version id this stage produces.
#   sha256_file     — hex digest of one file (for provenance manifests).
#   atomic_write_csv / atomic_write_json — write to a temp file, then move
#                     into place, so a crash never leaves a partial table.
#   read_records    — parse one records.jsonl, raising on malformed lines.

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pandas as pd

REPO = Path("/home/justin/work/worktrees/implement-3009")
UNBL = Path("/home/justin/Documents/ZJU work/fos/results/unblinding")
STAGE10 = REPO / "results/unblinding/_project_governance/stage10_data_reconciliation"
DATA = STAGE10 / "data"
PROVENANCE = STAGE10 / "provenance"

RUN6 = UNBL / "TWIN2K_UNBLINDING_LOGPROBS_6TASKS-20260919T025143"
RUN10 = UNBL / "T2K10-20260923T034851"
T2KX = UNBL / "expansion/work/T2KX-20261022T222604"

RUN_ROOTS = {"run6": RUN6, "run10": RUN10}

REGISTRY_RUN10 = RUN10 / "experiment_registry.json"
FROZEN_262 = UNBL / "agreed_figure_code_package/data/blinding_signed_contrasts.csv"
CONTRAST_REGISTER = UNBL / "_project_governance/stage3_methodology/CONTRAST_REGISTER.csv"
HUMAN_SD = UNBL / "_project_governance/stage3_results/combined31/original_human_sd_verification.csv"
EXPANSION_FROZEN = UNBL / "_project_governance/stage3_results/expansion17/contrast_level_results.csv"
STAGE5_DATASET = UNBL / "_project_governance/stage5_exploratory/data/stage5_dataset.csv"
EXPANSION_REGISTER_FINGERPRINT = T2KX / "fingerprint.json"

VERSION = "reconciled_v1"
SEED = 20261028
BOOTSTRAP_DRAWS = 2000


def sha256_file(path: Path) -> str:
    """Hex sha256 of one file, read in chunks (inputs are large)."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_replace(tmp: Path, final: Path) -> None:
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, final)


def atomic_write_csv(df: pd.DataFrame, path: Path) -> None:
    """Write one CSV table atomically: temp file first, then rename.

    A failed run therefore never leaves an authoritative-looking partial
    table at the final path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_csv(tmp, index=False)
    os.replace(tmp, path)


def atomic_write_json(payload: dict, path: Path) -> None:
    """Write one JSON document atomically (same two-step dance as CSV)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)


def read_records(path: Path) -> list[dict]:
    """Every parsed record of one records.jsonl; a malformed line raises.

    A missing file is a configuration error here (the canonical rebuild
    must see every registered leg), so it also raises.
    """
    if not path.is_file():
        raise FileNotFoundError(f"registered inference leg missing: {path}")
    records: list[dict] = []
    with open(path, encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{line_number}: malformed record line") from error
    return records


def load_frozen_originals() -> pd.DataFrame:
    """The frozen 262-row original effect table, in long form.

    One row per (model, experiment, contrast, leg) with the frozen model
    effect d_m_B / d_m_U in percentage points — the values the canonical
    rebuild must reproduce (or correct, with the diff documented).
    """
    b = pd.read_csv(FROZEN_262)
    long = b.melt(
        id_vars=["model", "experiment", "contrast", "paradigm_family", "d_h"],
        value_vars=["d_m_B", "d_m_U"], var_name="leg", value_name="d_m_pp",
    )
    long["blinding"] = long["leg"].map({"d_m_B": 0, "d_m_U": 1})
    return long


def load_human_sd() -> pd.DataFrame:
    """Frozen human pooled SDs (native and pp) per contrast id."""
    return pd.read_csv(HUMAN_SD)
