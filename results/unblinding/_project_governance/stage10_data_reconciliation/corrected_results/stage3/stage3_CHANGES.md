# stage3_CHANGES.md — what the corrected effects change in the original
# 14-experiment statistics

## What was rerun
The identical frozen estimators (collapse = model-mean within contrast,
experiment-equal 1/k_e weighting; WLS-through-origin recovery slopes;
signed-bias and Figure-3 average-then-absolute error means; family-cluster
bootstrap seed 20261010 + frozen per-statistic offsets, 10,000 draws;
spec A.2 experiment-cluster bootstrap seed 20261013, 5,000 draws) were fed
the canonical `reconciled_v1` model effects instead of the stale frozen
262-row table. Human effects are unchanged, so only the model side moves.
The 6 `new_only` anchoring cells are excluded to keep the 262-row structure
comparable with the frozen analysis (they add 3 contrast pairs; including
them would change k_e and break like-for-like comparison).

## Headline numbers, frozen → corrected (95% family-bootstrap CI corrected)

| statistic | frozen | corrected | corrected CI |
|---|---|---|---|
| recovery slope blinded | 0.4935 | 0.4762 | 0.302 – 0.648 |
| recovery slope disclosed | 0.8978 | 0.8842 | 0.568 – 1.041 |
| disclosure slope difference | 0.4043 | 0.4080 | 0.059 – 0.592 |
| signed bias blinded (pp) | -12.097 | -12.447 | -20.009 – -5.449 |
| signed bias disclosed (pp) | -3.803 | -4.102 | -7.906 – 0.518 |
| signed bias change U−B (pp) | 8.294 | 8.345 | 1.802 – 18.104 |
| Figure-3 abs error blinded (pp) | 13.114 | 13.423 | 8.411 – 18.944 (spec A.2) |
| Figure-3 abs error disclosed (pp) | 8.498 | 8.400 | 4.901 – 12.569 (spec A.2) |
| contrast-cell abs error blinded (pp) | 21.113 | 20.861 | 12.112 – 28.715 |
| contrast-cell abs error disclosed (pp) | 21.257 | 20.419 | 12.621 – 27.384 |
| contrast-cell abs error change U−B (pp) | 0.144 | **-0.442** | -1.663 – 1.326 |

## What changed qualitatively
- All substantive conclusions survive: recovery slopes drop slightly
  (blinded −0.017, disclosed −0.014), disclosure benefit essentially
  unchanged (+0.004), signed biases slightly more negative.
- **One sign flip**: the contrast-cell absolute-error change U−B goes from
  +0.144 pp (disclosure slightly worse) to −0.442 pp (disclosure slightly
  better). Its interval ([−1.66, 1.33]) straddles zero in both versions, so
  neither was a significant finding — but any text claiming "disclosure
  slightly increases contrast-cell error" must be dropped.
- The run10-derived experiments (abs_relative, prob_matching, allais,
  anchoring_*, linda, myside, outcome_bias) carry all 139 corrected cells;
  run6 experiments are untouched.

## Files
`corrected_signed_contrasts.csv`, `recovery_slopes_signed_bias_figure3.csv`,
`per_model_statistics.csv`, `per_experiment_statistics.csv`,
`bootstrap_cis_frozen_method.csv`,
`bootstrap_cis_spec_A2_experiment_cluster.csv`, `headline_before_after.csv`.
No Bayesian fitting in Stage 3; bootstrap seeds are the frozen ones, so the
intervals are deterministic.
