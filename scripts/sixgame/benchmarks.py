"""Frozen human benchmark numbers for the three-game experiment.

Every number here is copied verbatim from HUMAN_BENCHMARKS.md (frozen
before data collection) and carries its source in a comment.  Nothing in
this file is computed; the analysis code only reads these constants.
"""

from __future__ import annotations

# ------------------------------------------------------------------ #
# Game 1: 11-20 money request (Arad & Rubinstein 2012 via Manning &
# Horton 2025 Table 1 — VERBATIM).  PMFs are choice 11 -> 20 shares (%).
# ------------------------------------------------------------------ #

PMF_1120: dict[str, list[float]] = {
    # Full PMF (11->20): 4,0,3,6,1,6,32,30,12,6 (n=108)
    "basic": [4, 0, 3, 6, 1, 6, 32, 30, 12, 6],
    # Full PMF (11->20): 0,4,0,4,4,4,9,21,40,15 (n=53)
    "costless": [0, 4, 0, 4, 4, 4, 9, 21, 40, 15],
    # Full PMF (11->20): 1,1,0,1,0,4,10,22,47,13 (n=72)
    "cycle": [1, 1, 0, 1, 0, 4, 10, 22, 47, 13],
}

#: Benchmark sample sizes (for propagating human sampling uncertainty).
N_HUMAN_1120: dict[str, int] = {"basic": 108, "costless": 53, "cycle": 72}

#: Treatment-effect targets in percentage points, actions {17,18,19,20}
#: (HUMAN_BENCHMARKS section 1.2).
EFFECTS_1120: dict[str, dict[int, float]] = {
    "basic_to_costless": {17: -23.0, 18: -9.0, 19: 28.0, 20: 9.0},
    "basic_to_cycle": {17: -22.0, 18: -8.0, 19: 35.0, 20: 7.0},
}

#: TOST equivalence margin for H1 (ANALYSIS_PLAN section 1.4): 20pp.
DELTA_1120_PP = 20.0

#: Frozen human SE for the H1 contrast (action 19): 6.7pp.
SE_HUMAN_1120_PP = 6.7

# ------------------------------------------------------------------ #
# Game 2: die-roll honesty (Ostermaier & Uhl 2017, authors' raw data —
# VERBATIM).  Shares per report 1..6 (%).
# ------------------------------------------------------------------ #

PMF_DIE: dict[str, list[float]] = {
    # Private (n=65): 3.1, 1.5, 6.2, 18.5, 32.3, 38.5
    "private": [3.1, 1.5, 6.2, 18.5, 32.3, 38.5],
    # Public (n=65): 4.6, 7.7, 13.8, 21.5, 23.1, 29.2
    "public": [4.6, 7.7, 13.8, 21.5, 23.1, 29.2],
}

N_HUMAN_DIE: dict[str, int] = {"private": 65, "public": 65}

#: Die-roll mean reports (HUMAN_BENCHMARKS section 2.1).
MEAN_DIE: dict[str, float] = {"private": 4.908, "public": 4.385}

#: Treatment-effect targets: delta share-6 = -9.2pp, delta mean = -0.52.
EFFECT_DIE_SHARE6_PP = -9.2
EFFECT_DIE_MEAN = -0.52

#: TOST margin for H2: 25pp (ANALYSIS_PLAN section 1.4/6).
DELTA_DIE_PP = 25.0

#: Frozen human SE for the H2 contrast (share-6): 8.3pp.
SE_HUMAN_DIE_PP = 8.3

#: Tier margins for the die-roll consistency ladder (ANALYSIS_PLAN 2.1):
#: Tier A (neutral rewording) strict small margin; Tier B (stake x10)
#: wider, separately pre-agreed margin.
DELTA_DIE_TIER_A_PP = 5.0
DELTA_DIE_TIER_B_PP = 15.0

# ------------------------------------------------------------------ #
# Game 3: PMS Joker 3x3 (Pogorelskiy, Melo & Shum 2018 — VERBATIM,
# HUMAN_BENCHMARKS section 3.3).  Frequencies per (action 1, 2, J).
# ------------------------------------------------------------------ #

FREQ_PMS: dict[str, dict[str, tuple[float, float, float]]] = {
    "G1": {
        "Row": (0.273, 0.349, 0.378),
        "Column": (0.325, 0.308, 0.367),
    },
    "G4": {
        "Row": (0.473, 0.220, 0.307),
        "Column": (0.487, 0.147, 0.366),
    },
}

#: Human treatment effects G1->G4 in percentage points per action
#: (1, 2, J); HUMAN_BENCHMARKS section 3.3.
EFFECT_PMS_PP: dict[str, tuple[float, float, float]] = {
    "Row": (20.0, -12.9, -7.1),
    "Column": (16.2, -16.1, -0.1),
}

#: TOST margin for H3: 25pp (ANALYSIS_PLAN section 6: 25-30; frozen 25).
DELTA_PMS_PP = 25.0

#: Frozen human SE for the H3 contrast (Row, per action): ~9.5pp.
SE_HUMAN_PMS_PP = 9.5

#: The mandatory repeated-play qualification sentence (HUMAN_BENCHMARKS
#: section 3.4) attached to every PMS result.
PMS_QUALIFICATION = (
    "Pogorelskiy, Melo and Shum (2018) report choice frequencies aggregated "
    "over 10-20 repeated rounds of play per game with random rematching each "
    "round (96 subjects; payoffs accumulated across rounds), whereas our LLM "
    "data are one-shot. Human aggregate frequencies may therefore reflect "
    "within-session learning and are not strictly comparable to true one-shot "
    "human play; we treat the PMS frequencies as a repeated-play human "
    "benchmark, not a one-shot baseline."
)

#: Level-k best-reply answers under the basic 11-20 game, used to
#: classify mapping failures descriptively (ANALYSIS_PLAN section 2.2).
#: level -> choice: k=0: 20, k=1: 19, k=2: 18, k=3: 17.
LEVEL_K_BASIC: dict[int, int] = {0: 20, 1: 19, 2: 18, 3: 17}

#: Inverted-game level-k answers (the rule-implied mapping applied to
#: LEVEL_K_BASIC): k -> 31 - basic answer.
LEVEL_K_INVERTED: dict[int, int] = {
    level: 31 - choice for level, choice in LEVEL_K_BASIC.items()
}
