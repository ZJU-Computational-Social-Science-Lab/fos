# INTEGRATION_REPORT.md — twin2k10r ↔ expansion persona integration (TASK-3134)

## Summary

The real-respondent pool (twin2k10r Stage 0, Config A, 100 Twin-2K-500 panel
members, sha256 `bdc84233…`) now drops into BOTH pipelines through one pure,
isolated adapter (`scripts/twin2k10r/integration/expansion_pool.py`). No
historical code, dataset, result, or manuscript file was modified; no
inference ran; no stimulus, arm, scoring, inference setting, or disclosure
text changed. The frozen synthetic pool (sha `26a8660f…`) is untouched.

## Pipeline map

```
Twin-2K-500 panel (read-only dataset mirror)
  └─ scripts/twin2k10r (Stage 0, seed 42) ──► Config A pool  (bdc84233…)
        │                                       │
        │  scripts/twin2k10r/integration/       │  (this task)
        │  expansion_pool.adapt_twin2k10r_pool  │
        │  rename 3 fields, drop pid/pool_id    ▼
        │                             adapted pool (new artifact,
        │                             write-once, separately hashed)
        │                                       │
        ├─► twin2k10r pipeline (10 experiments, consumes dataset-named
        │    keys directly — unchanged, no adapter needed)
        └─► expansion pipeline (17 READY T2KX experiments) —
             expansion.runner.load_personas() accepts the adapted file
             UNCHANGED (verified by test); render_persona_block() emits
             the 7 real fields in PERSONA_FIELDS order
```

## Files changed (all new, all isolated)

- `scripts/twin2k10r/integration/__init__.py` — package marker.
- `scripts/twin2k10r/integration/expansion_pool.py` — the pure adapter:
  `adapt_twin2k10r_pool` (rename `age_bracket`→`age`,
  `household_income_bracket`→`household_income`,
  `household_size_bracket`→`household_size`; strip `pid`/`pool_id`;
  bracket values byte-verbatim; loud specific errors: `PoolShapeError`,
  `PoolFieldError`, `PoolValueError`), `write_adapted_pool` (write-once,
  returns sha256 manifest), `load_expansion_pipeline` (read-only import),
  `expansion_personas` (adapt + verify against `PERSONA_FIELDS`).
- `scripts/twin2k10r/integration/render_prompts.py` — renders
  `INTEGRATION_PROMPTS.md` (anonymized, no model calls).
- `scripts/twin2k10r/integration/INTEGRATION_PROMPTS.md` — generated.
- `tests/twin2k10r/integration/` — conftest + 3 test files (16 tests).
- `scripts/twin2k10r/integration/INTEGRATION_REPORT.md` — this file.

Frozen files verified untouched: `scripts/twin2k10/**`,
`results/unblinding/expansion/pipeline/**` (including the synthetic pool
and its provenance), `data/configs/twin2k10_stimuli.json`, archived
results, manuscript. The dataset mirror is read-only.

## Test counts (exact)

- twin2k10r suite: `pytest tests/twin2k10r` → **72 passed** (was GREEN
  before this task; still GREEN).
- New integration tests: `pytest tests/twin2k10r/integration` →
  **16 passed, 0 skipped** (the real-pool tests ran against the
  hash-pinned Stage 0 pool, present on this machine).
- Historical regression set (RESULT-3127 list): `pytest
  tests/test_twin2k10_prompts.py tests/test_twin2k6_prompts.py
  tests/test_twin2k6_glue.py tests/test_personas.py
  tests/test_twin2k10_config.py tests/test_twin2k10_preflight.py` →
  **132 passed**.
- Combined: **220 passed, 0 failed**.

## Accessibility table — all 31 experiments / 38 contrasts

Real-respondent pool (Config A) is renderable (and runnable, no inference
executed in this task) for every row marked YES. "twin2k10r side" means
the existing twin2k10r pipeline already covers it; "expansion side" means
the expansion pipeline accepts the adapted pool for it.

### Original Twin-2K-era: 14 experiments / 18 contrasts

| # | Experiment | Contrast(s) | Pool works? | Where |
|---|---|---|---|---|
| 1 | abs_relative | p_yes_jacket_minus_calculator | YES (twin2k10r side) | rendered pool + stimuli file |
| 2 | allais | p_opt1_form1_minus_form2 | YES (twin2k10r side) | ditto |
| 3 | anchoring_african | mean_high_minus_low | YES (twin2k10r side) | ditto |
| 4 | anchoring_redwood | mean_high_minus_low | YES (twin2k10r side) | ditto |
| 5 | disease | p_safe_loss_minus_gain | **NO — stimuli withheld** | not in `twin2k10_stimuli.json`; NOT rebuilt |
| 6 | fire_extinguisher | 95pct_minus_all; 98pct_minus_all | **NO — withheld (2 contrasts)** | ditto |
| 7 | less_is_more | B_minus_A; C_minus_A | **NO — withheld (2)** | ditto |
| 8 | linda | critical_mean_conj_minus_noconj | YES (twin2k10r side) | rendered pool + stimuli file |
| 9 | myside | mean_german_minus_ford | YES (twin2k10r side) | ditto |
| 10 | outcome_bias | mean_success_minus_failure | YES (twin2k10r side) | ditto |
| 11 | prob_matching | mean_majority_share_problem1_minus_problem2 | YES (twin2k10r side) | ditto |
| 12 | seatbelt | 95pct_minus_all; 98pct_minus_all | **NO — withheld (2)** | ditto |
| 13 | sunk_cost | card_minus_no_card | **NO — withheld** | ditto |
| 14 | wta_wtp | wta_minus_wtp_certainty; wtp_noncertainty_minus_wtp_certainty | **NO — withheld (2)** | ditto |

Outside the frozen 14 but covered by twin2k10r (outside the 31/38 grid):
`base_rate` (30 vs 70 engineers) and `false_consensus` (single-arm
within-subject; no within-experiment contrast) — YES on the twin2k10r side.

### Expansion: 17 experiments / 20 contrasts (all READY, all render with the adapted pool)

| # | Experiment | Contrast | Pool works? |
|---|---|---|---|
| 15 | T2KX-ml1_gamblers_fallacy | three_sixes − two_sixes | YES (expansion side) |
| 16 | T2KX-ml1_category_scales | high_scale − low_scale | YES |
| 17 | T2KX-ml1_reciprocity | us_second − us_first | YES |
| 18 | T2KX-ml1_allowed_forbidden | allow_wording − forbid_wording | YES |
| 19 | T2KX-ml1_quote_attribution | disliked_source − liked_source | YES |
| 20 | T2KX-ml1_imagined_contact | control_walk − imagined_contact | YES |
| 21 | T2KX-ml2_hauser_s1 | side_effect − greater_good | YES |
| 22 | T2KX-ml2_risen_tempt_fate | unprepared − prepared | YES |
| 23 | T2KX-ml2_schwarz_order | life_first − life_second | YES |
| 24 | T2KX-ml2_shafir_choose_reject | award_framing − deny_framing | YES |
| 25 | T2KX-ml2_miyamoto_correspondence | essay_pro_death − essay_pro_choice | YES |
| 26 | T2KX-ml2_rottenstreich_affect | certainty − one_percent | YES |
| 27 | T2KX-ml2_bauer_materialism | consumer_prime − individual_prime | YES |
| 28 | T2KX-howard823 | atypical − control; typical − control | YES (2 contrasts) |
| 29 | T2KX-budescu779 | verbal_numerical − control ("very likely", "very unlikely") | YES (2) |
| 30 | T2KX-keusch433 | high_to_low_vague − low_to_high_vague | YES |
| 31 | T2KX-reedBR32 | negative − positive (helpfulness; trustworthiness) | YES (2) |

Registered but NOT part of the 31/38 grid (excluded in the registry, never
faked): T2KX-ml1_money_priming, T2KX-ml2_norenzayan_reasoning,
T2KX-ml2_gray_typecast, T2KX-kurzban506, T2KX-tasoff223.

### Reconciliation: 27 reachable of 31 / 35 of 38

- Reachable = 10 (twin2k10 side) + 17 (expansion side) = **27 experiments**.
- Contrasts reachable = 8 (twin2k10, within the frozen set) + 20
  (expansion) = **28 of 38**; the other 10 are the withheld-6's
  contrasts (see below). false_consensus is outside the grid (no
  within-experiment contrast).
- **6 withheld reconciliation experiments** (disease, fire_extinguisher,
  less_is_more, seatbelt, sunk_cost, wta_wtp — 9 contrasts): their
  stimuli are absent from `data/configs/twin2k10_stimuli.json`, the file
  twin2k10r consumes verbatim (10 contrasts of the frozen 18). Per `EXPERIMENT_COMPATIBILITY.md` §3 the
  stimuli were NOT rebuilt and no substitute texts were invented. (The
  research design notes they are recoverable from the dataset catalog
  QID157–191 in a future, separately-scoped task.)
- **base_rate / false_consensus** sit outside the frozen 14-experiment
  set and therefore outside the 31/38 grid; twin2k10r renders them with
  the real pool, but they add no contrast row (false_consensus is
  single-arm within-subject).

## Limitations

1. No inference ran in this task; "works" means renderable + accepted by
   the frozen loaders, not that results exist.
2. Config A only. Config B (11 measured trait scores) would be rejected
   by `load_personas` by design; extending it needs a sanctioned pipeline
   change (research design §4) and was not improvised.
3. The expansion pipeline is imported read-only from the frozen install
   at `~/Documents/ZJU work/fos/results/unblinding/expansion/pipeline`;
   tests skip if it or the hash-pinned source pool is absent.
4. The adapted pool is written by `write_adapted_pool` at run time into
   a NEW write-once file; no adapted pool file was committed to the repo
   (pool files carry respondent data and stay out of git, like Stage 0).
5. Bracket values (e.g. `age: "30-49"`, income bands) render verbatim;
   they are the measured data. Comparing against historical expansion
   runs (point values) is a pool-population difference, documented —
   never converted or harmonized.
