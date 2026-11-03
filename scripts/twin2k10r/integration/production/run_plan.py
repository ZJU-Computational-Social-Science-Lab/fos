# This file decides WHAT the production run measures and in WHAT order:
# the merged 31-experiment grid (8 twin2k10r grid experiments + 6 restored
# experiments on the twin-style pipeline, 17 T2KX experiments on the
# expansion-style pipeline), the pinned 15-model queue with the two
# flagged models (muse-glimmer, glm-4.7-flash) moved to the very end so
# they can never contaminate the clean aggregates, and the twin-side
# experiment specs (arm structures) including the restored ones.
# Functions:
#   twin_experiments     — the 14 twin-style experiment names in run order.
#   expansion_experiments— the 17 T2KX experiment names in run order.
#   twin_specs           — arm structures (name -> spec) for all 14.
#   ordered_models       — the model queue: clean models first, flagged last.
#   is_flagged           — whether a model is one of the flagged two.
from __future__ import annotations

from twin2k10 import config as twin2k10_config
from twin2k10 import experiments as twin2k10_experiments
from twin2k10r.stimuli_restored.registry import (
    RESTORED_ARMS,
    RESTORED_EXPERIMENT_NAMES,
)

ExperimentSpec = twin2k10_experiments.ExperimentSpec

# The two models run LAST and excluded from clean aggregates (flagged in
# the frozen queue notes: muse-glimmer and the r1-style glm-4.7-flash).
FLAGGED_MODELS = ("muse-glimmer", "glm-4.7-flash")

# The pinned historical model order (the frozen twin2k10 study queue).
HISTORICAL_MODEL_ORDER: tuple[str, ...] = tuple(twin2k10_config.MODELS)

# The twin-style experiments inside the frozen 31-experiment grid: the
# twin2k10r registry's in-grid members (base_rate and false_consensus sit
# outside the frozen grid and do not run in production).
_GRID_TWIN = tuple(
    name for name in twin2k10_experiments.EXPERIMENTS
    if name not in ("base_rate", "false_consensus")
)


def twin_experiments() -> tuple[str, ...]:
    """The 14 twin-style experiments in run order (8 grid + 6 restored)."""
    return _GRID_TWIN + RESTORED_EXPERIMENT_NAMES


def expansion_experiments() -> tuple[str, ...]:
    """The 17 T2KX expansion experiments in run order.

    Read from the merged registry (which marks each row READY or
    MISSING_LOCALLY); only READY experiments can run. Falls back to the
    pinned name order when the frozen expansion pipeline is absent.
    """
    from twin2k10r.stimuli_restored.registry import merged_registry

    rows = [
        row["name"] for row in merged_registry()
        if row["source"] == "T2KX" and row["status"] == "READY"
    ]
    if rows:
        return tuple(rows)
    from twin2k10r.stimuli_restored.registry import _EXPANSION_CONTRASTS

    return tuple(_EXPANSION_CONTRASTS)


def twin_specs() -> dict[str, ExperimentSpec]:
    """Arm structures for every twin-style experiment.

    The 8 grid experiments reuse the frozen twin2k10 specs verbatim; the
    6 restored experiments are built from the archived run6 arm
    structures (verified record-by-record in the restoration tests).
    """
    specs = {
        name: twin2k10_experiments.EXPERIMENTS[name] for name in _GRID_TWIN
    }
    for name in RESTORED_EXPERIMENT_NAMES:
        specs[name] = ExperimentSpec(name, arms=RESTORED_ARMS[name])
    return specs


def ordered_models() -> list[str]:
    """The production model queue: historical order, flagged two last."""
    clean = [m for m in HISTORICAL_MODEL_ORDER if not is_flagged(m)]
    flagged = [m for m in HISTORICAL_MODEL_ORDER if is_flagged(m)]
    return clean + flagged


def is_flagged(model: str) -> bool:
    """Whether this model runs last and stays out of clean aggregates."""
    return model in FLAGGED_MODELS
