# stage8_CHANGES.md — what the corrected effects change in the shared-failure
# analysis (error patterns, magnitudes, overlap, regression)

## What was rerun
All five frozen Stage 8 scripts, unchanged in logic (same hand-coded
experiment characteristics, same classification thresholds, same
multilevel logistic spec with priors alpha N(0,2), beta N(0,1), group
SDs HalfNormal(1), seed 20261027 main / 20261028 LOMO), fed the
canonical `reconciled_v1` paired/effects tables instead of the stale
Stage 5 dataset. Human-side quantities are unchanged. Coverage note:
the corrected blinded set includes the 5 `new_only` blinded legs on
C-13/C-14, so the Phase-3 regression has 473 observations (frozen 468)
over the same 32 confident contrasts, 15 models; this is the natural
scope for those cells (same models, same spec). C-32's 10-model
coverage convention is preserved exactly.

## Per-contrast error counts (frozen → corrected, changed contrasts only)
| contrast | agree B/D frozen | agree B/D corrected |
|---|---|---|
| C-11 | 11/9 | **13/10** |
| C-12 | 13/15 | **14/14** |
| C-16 | 7/8 | **5/10** |
| C-17 (uncertain) | 5/8 | **6/9** |

All classes and the 7-contrast disagreement set (C-03, C-09, C-16,
C-26, C-30, C-31, C-37; both-legs-wrong: C-09, C-26, C-30, C-37) are
unchanged.

## Wrong-direction magnitudes (majority-wrong contrasts)
- C-16 is the notable movement: blinded mean |wrong d| vs human |d|
  drops 0.62 (intermediate) → 0.44 (near_zero) — the corrected blinded
  majority shrinks rather than reverses; disclosed stays a reversal
  (1.33 → 1.14).
- C-11 flips pattern blinded: 0.59 intermediate → 1.63 reversal.
- C-03, C-09, C-26, C-30, C-31, C-37 magnitudes are unchanged to 4 dp.
- Reading unchanged: C-26, C-30, C-37 are true reversals; C-09 is
  massive shrinkage (0.36x blinded, 0.28x disclosed).

## Per-model error patterns (changed models only)
| model | wrong B/D frozen | wrong B/D corrected |
|---|---|---|
| qwen3-4b | 14/8 | **15/9** |
| granite-4.1-8b | 11/12 | **10/12** |
| granite-4.1-30b | 8/12 | **7/11** |
| glm-4.7-flash | 7/9 | **8/9** |
| qwen3.6-35b-a3b | 8/10 | **8/9** |
| qwen3.6-35b-a3b-UC | 7/10 | **8/9** |
| nemotron-cascade | 7/13 | **6/13** |

qwen3-4b remains the most error-prone model blinded (15/32 = 0.469).
Disclosure still reduces errors for most models (e.g. gpt-oss 14→6).

## Shared failures / co-error overlap
Mean pairwise blinded co-error count 3.18 → **3.30** (105 pairs); mean
Jaccard 0.266 → **0.278**. Top pair changes from gpt-oss-20b ×
granite-4.1-8b (8 shared) to the qwen3.6-35b pair (qwen3.6-35b-a3b ×
-uncensored, 8 shared) — lineage-related pairs still top the overlap.

## Family-block regression (Phase 3, blinded leg)
- Main fit: beta (z |d_h|) = −0.558, 89% HDI [−1.00, −0.10] (frozen
  −0.55 [−1.00, −0.10]); sd_experiment 0.49 (frozen ~0.5). Larger human
  effects still protect against wrong directions.
- Convergence: rhat_ok=True, headline ESS ok, min bulk ESS 978, max
  R-hat 1.0066 (frozen recorded min ESS 4717, max R-hat 1.002).
- Leave-one-family-out: all 7 exclusions keep beta negative
  (−0.470 to −0.690); frozen range −0.418 to −0.720. The qwen
  exclusion beta moves −0.418 → **−0.516** (frozen's weakest case
  strengthens), so the "not driven by one family" conclusion holds
  with slightly more margin.

## Disclosure transitions (7 disagreement contrasts)
Per-model corrected/newly-wrong patterns move only on C-11/C-12/C-16/
C-17; the both-legs-wrong set is unchanged. Disclosure still corrects
more errors than it introduces overall (Part-5 counts: e.g. gpt-oss
14 blinded → 6 disclosed wrong).

## Files
`ALL_CONTRAST_PATTERNS.csv`, `MODEL_ERROR_PATTERNS.csv`,
`MODEL_ERROR_PATTERNS_FULL.csv`, `CO_ERROR_OVERLAP.csv`,
`disclosure_transitions_both_legs_wrong.csv`,
`disclosure_transitions_disagreement7.csv`,
`disclosure_magnitude_change.csv`, `CHARACTERISTICS_CROSSTABS.md`,
`EXPERIMENT_CHARACTERISTICS.csv`,
`scripts/experiment_residuals.csv`, `scripts/lomo_sensitivity.csv`.
