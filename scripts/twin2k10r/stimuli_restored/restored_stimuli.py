# This module loads the checked-in generated stimuli file and hands it
# out in the useful shapes: as a qid-keyed lookup (like twin2k10's
# load_stimuli) and as the plain entry list. It only ever READS the
# generated file — regeneration is build_stimuli.write_stimuli_file's
# job alone. Functions:
#   load_restored_stimuli — the entry list from the generated file.
#   restored_stimuli      — the same list (the name the tests use).
#   stimulus_by_qid       — one entry per question id.
from __future__ import annotations

import json
from pathlib import Path

from twin2k10r.stimuli_restored.build_stimuli import STIMULI_FILE


def load_restored_stimuli(path: Path = STIMULI_FILE) -> list[dict]:
    """The restored stimulus entries, read from the generated file.

    Accepts the file's {"stimuli": [...]} shape. Raises FileNotFoundError
    when the file is missing and json.JSONDecodeError when it is corrupt.
    """
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    return data["stimuli"] if isinstance(data, dict) else data


def restored_stimuli(path: Path = STIMULI_FILE) -> list[dict]:
    """Alias of load_restored_stimuli under the tests' name."""
    return load_restored_stimuli(path)


def stimulus_by_qid(path: Path = STIMULI_FILE) -> dict[str, dict]:
    """The restored entries keyed by question id (e.g. "QID157")."""
    return {entry["qid"]: entry for entry in load_restored_stimuli(path)}
