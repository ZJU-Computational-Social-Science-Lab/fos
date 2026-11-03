# This module defines what was RESTORED: the six withheld experiments'
# arm structures (which question ids belong to which arm), their ten
# frozen contrasts (which arm is treatment and which is control), and
# the merged view that lines all 33 runnable experiments up in one
# table. Every arm structure and every contrast row here was copied
# from frozen evidence — the archived run6 records and the frozen
# experiment registry CSV — never invented. Functions:
#   merged_registry  — all experiments in one list with source, status,
#                      contrast counts, and grid membership.
#   coverage_counts  — the headline before/after restoration numbers.
#   _twin2k10r_entries / _restored_entries / _expansion_entries — the
#                      three source-specific pieces of the merged view.
from __future__ import annotations

from typing import Any

from twin2k10 import experiments as twin2k10_experiments

# The six restored experiments, in frozen registry (C-01..C-10) order.
RESTORED_EXPERIMENT_NAMES = (
    "disease",
    "less_is_more",
    "fire_extinguisher",
    "seatbelt",
    "sunk_cost",
    "wta_wtp",
)

# Arm structures exactly as the archived run6 legs ran them
# (arm name -> question ids; verified record-by-record in tests).
RESTORED_ARMS: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "disease": (("gain", ("QID157",)), ("loss", ("QID158",))),
    "less_is_more": (
        ("A", ("QID171",)),
        ("B", ("QID172",)),
        ("C", ("QID173",)),
    ),
    "fire_extinguisher": (
        ("all", ("QID174",)),
        ("98pct", ("QID175",)),
        ("95pct", ("QID176",)),
    ),
    "seatbelt": (
        ("all", ("QID177",)),
        ("98pct", ("QID178",)),
        ("95pct", ("QID179",)),
    ),
    "sunk_cost": (("no_card", ("QID181",)), ("card", ("QID182",))),
    "wta_wtp": (
        ("wtp_certainty", ("QID189",)),
        ("wta_certainty", ("QID190",)),
        ("wtp_noncertainty", ("QID191",)),
    ),
}

# The ten restored contrasts, mirroring the frozen experiment registry
# rows C-01..C-10 field for field (contrast parity is tested against
# the CSV itself, so the ids here are the join keys, not a re-typing).
RESTORED_CONTRASTS: tuple[dict[str, str], ...] = (
    {
        "contrast_id": "C-01", "experiment_id": "disease",
        "contrast_name": "p_safe_loss_minus_gain",
        "treatment_condition": "loss", "control_condition": "gain",
    },
    {
        "contrast_id": "C-02", "experiment_id": "less_is_more",
        "contrast_name": "B_minus_A",
        "treatment_condition": "B", "control_condition": "A",
    },
    {
        "contrast_id": "C-03", "experiment_id": "less_is_more",
        "contrast_name": "C_minus_A",
        "treatment_condition": "C", "control_condition": "A",
    },
    {
        "contrast_id": "C-04", "experiment_id": "fire_extinguisher",
        "contrast_name": "98pct_minus_all",
        "treatment_condition": "98pct", "control_condition": "all",
    },
    {
        "contrast_id": "C-05", "experiment_id": "fire_extinguisher",
        "contrast_name": "95pct_minus_all",
        "treatment_condition": "95pct", "control_condition": "all",
    },
    {
        "contrast_id": "C-06", "experiment_id": "seatbelt",
        "contrast_name": "98pct_minus_all",
        "treatment_condition": "98pct", "control_condition": "all",
    },
    {
        "contrast_id": "C-07", "experiment_id": "seatbelt",
        "contrast_name": "95pct_minus_all",
        "treatment_condition": "95pct", "control_condition": "all",
    },
    {
        "contrast_id": "C-08", "experiment_id": "sunk_cost",
        "contrast_name": "card_minus_no_card",
        "treatment_condition": "card", "control_condition": "no_card",
    },
    {
        "contrast_id": "C-09", "experiment_id": "wta_wtp",
        "contrast_name": "wta_minus_wtp_certainty",
        "treatment_condition": "wta_certainty",
        "control_condition": "wtp_certainty",
    },
    {
        "contrast_id": "C-10", "experiment_id": "wta_wtp",
        "contrast_name": "wtp_noncertainty_minus_wtp_certainty",
        "treatment_condition": "wtp_noncertainty",
        "control_condition": "wtp_certainty",
    },
)

# The two twin2k10 experiments outside the frozen 31-experiment grid
# (false_consensus is single-arm; base_rate was never in the frozen
# reconciliation set) and their grid status.
OUTSIDE_GRID = frozenset({"base_rate", "false_consensus"})

# Contrast counts of the twin2k10r side: the 8 frozen-grid experiments
# carry one within-study contrast each (9 experiments total counting
# base_rate), false_consensus carries none.
_TWIN2K10R_CONTRASTS: dict[str, int] = {
    "allais": 1, "anchoring_african": 1, "anchoring_redwood": 1,
    "outcome_bias": 1, "myside": 1, "abs_relative": 1,
    "prob_matching": 1, "linda": 1, "base_rate": 1, "false_consensus": 0,
}

# Expansion-side contrast counts (frozen registry C-19..C-38): 17
# experiments, 20 contrasts. The expansion registry lives in the frozen
# pipeline outside this repository copy, so its READY ids are read from
# there; when that pipeline is absent the counts still stand because
# they come from the frozen registry CSV, not from this machine.
_EXPANSION_CONTRASTS: dict[str, int] = {
    "T2KX-ml1_gamblers_fallacy": 1, "T2KX-ml1_category_scales": 1,
    "T2KX-ml1_reciprocity": 1, "T2KX-ml1_allowed_forbidden": 1,
    "T2KX-ml1_quote_attribution": 1, "T2KX-ml1_imagined_contact": 1,
    "T2KX-ml2_hauser_s1": 1, "T2KX-ml2_risen_tempt_fate": 1,
    "T2KX-ml2_schwarz_order": 1, "T2KX-ml2_shafir_choose_reject": 1,
    "T2KX-ml2_miyamoto_correspondence": 1,
    "T2KX-ml2_rottenstreich_affect": 1, "T2KX-ml2_bauer_materialism": 1,
    "T2KX-howard823": 2, "T2KX-budescu779": 2, "T2KX-keusch433": 1,
    "T2KX-reedBR32": 2,
}


def _twin2k10r_entries() -> list[dict[str, Any]]:
    """The 10 twin2k10r experiments as merged-view rows."""
    rows = []
    for name, spec in twin2k10_experiments.EXPERIMENTS.items():
        rows.append({
            "name": name,
            "source": "twin2k10r",
            "arms": [(arm, list(qids)) for arm, qids in spec.arms],
            "n_contrasts": _TWIN2K10R_CONTRASTS[name],
            "in_grid": name not in OUTSIDE_GRID,
            "status": "READY",
            "withheld_reason": None,
        })
    return rows


def _restored_entries() -> list[dict[str, Any]]:
    """The 6 restored experiments as merged-view rows."""
    return [
        {
            "name": name,
            "source": "restored",
            "arms": [
                (arm, list(qids)) for arm, qids in RESTORED_ARMS[name]
            ],
            "n_contrasts": sum(
                1 for c in RESTORED_CONTRASTS if c["experiment_id"] == name
            ),
            "in_grid": True,
            "status": "READY",
            "withheld_reason": None,
        }
        for name in RESTORED_EXPERIMENT_NAMES
    ]


def _expansion_registry():
    """The frozen expansion registry module, via the existing read-only
    loader (the same one the integration adapter uses). None when the
    pipeline is not present on this machine."""
    try:
        from twin2k10r.integration.expansion_pool import (
            load_expansion_pipeline,
        )

        return load_expansion_pipeline().registry
    except (ImportError, ModuleNotFoundError):
        return None


def _expansion_entries() -> list[dict[str, Any]]:
    """The 17 expansion experiments as merged-view rows (read-only)."""
    expansion_registry = _expansion_registry()
    ready = (
        set(expansion_registry.ready_experiments())
        if expansion_registry else set(_EXPANSION_CONTRASTS)
    )
    rows = []
    for name, n_contrasts in _EXPANSION_CONTRASTS.items():
        arms: list[tuple[str, list[str]]] = []
        if name in ready:
            spec = expansion_registry.get(name).spec
            arms = [
                (condition.name, [item.qid for item in condition.items])
                for condition in spec.conditions
            ]
        rows.append({
            "name": name,
            "source": "T2KX",
            "arms": arms,
            "n_contrasts": n_contrasts,
            "in_grid": True,
            "status": "READY" if name in ready else "MISSING_LOCALLY",
            "withheld_reason": None,
        })
    return rows


def merged_registry() -> list[dict[str, Any]]:
    """Every runnable experiment in one table, source by source.

    One row per experiment with: name, source (twin2k10r / restored /
    T2KX), arms as (arm, question ids) pairs, contrast count, grid
    membership, status, and — for anything still withheld — the reason.
    """
    return _twin2k10r_entries() + _restored_entries() + _expansion_entries()


def coverage_counts(restored: bool = True) -> dict[str, int]:
    """The headline grid counts, before or after the restoration.

    With restored=False the six restored experiments count as withheld
    (the pre-restoration state the inconsistent report described);
    with restored=True they count as reachable.
    """
    restored_experiments = len(RESTORED_EXPERIMENT_NAMES)
    restored_contrasts = len(RESTORED_CONTRASTS)
    return {
        "grid_experiments": 31,
        "grid_experiments_reachable": 25 + (restored_experiments if restored else 0),
        "grid_contrasts": 38,
        "grid_contrasts_reachable": 28 + (restored_contrasts if restored else 0),
        "withheld_experiments": 0 if restored else restored_experiments,
        "withheld_contrasts": 0 if restored else restored_contrasts,
    }
