# Model diagnostics — Stage 9 explanatory regressions

## Computational settings

- NumPyro NUTS, 4 parallel chains, 1000 warmup + 2000 samples per chain (8000 post-warmup draws), target_accept_prob = 0.90, seed 20261028. These were the spec's proposed computational choices; no pilot tuning was done beyond them.
- Priors: alpha Normal(0, 1.5); slopes Normal(0, 0.5); grouping spreads HalfNormal(0.5), non-centered; Gamma shape HalfNormal(2) (spec left this open; documented here).
- Model A exact zeros in absolute error: 0 of 1106 rows (min 0.00065) — no zero-shift or hurdle needed, documented per spec.
- correct_direction convention: rows with y_std == 0 count as NOT direction-correct (correct_direction = 0) because sign(0) is neither +1 nor -1. This affects 4 rows: C-21/qwen3-4b, C-11/granite, C-17/granite (each x2 blinded/disclosed legs).

## Convergence

- Model A: max R-hat (fixed effects) 1.0028, min bulk ESS 2960, divergences 0/8000, flags 0.
- Model B: max R-hat 1.0009, min bulk ESS 5162, divergences 13/8000, flags 0.
- Flags use the spec thresholds (R-hat >= 1.01, bulk ESS < 400) on intercept and slopes. Model B shows 13/8000 divergences (0.16%), located in the 553-level pair-grouping scale (non-centered parameterization already in use); with only ~0.16% of iterations affected, R-hat and ESS clean, and the Sensitivity A refits (different data perturbations, same kernel) reproducing the fixed effects closely, these are reported rather than tuned away.

- Grouping-level (z_) parameters are expected to mix more slowly for sparse groups (e.g. role_change has 3/38 contrasts); their spread parameters, not each level, are reported.

## Posterior predictive check (Model A, Gamma fit)

- Observed mean absolute error 0.630 vs posterior-predictive 95% interval of the mean [0.590, 0.692].
- Observed SD 0.626 vs mean simulated SD 0.557.
- 92.2% of observations fall inside their posterior-predictive 90% interval (Gamma log-link fits the right-skewed error scale adequately; slight over-dispersion possible in the extreme tail).

## Predictor correlations

- Explicit-probability and numerical-manipulation overlap in 26/38 contrasts (correlation 0.39 of the dummy variables): their coefficients are conditional on each other and neither should be read as 'the effect of numeracy' alone.
- role_change, question_order, response_options_change each have only 3/38 positive contrasts. They are kept in Model A (estimable, weakly identified, pulled toward zero by the Normal(0, 0.5) prior); Model B keeps them too — identification holds on the 934-row confident subset.

## Missing-data handling

- manipulation_location: 1 contrast (C-36) missing -> median (0.25) + na-flag column.
- n_response_options: 3 contrasts (C-08, C-13, C-14) missing -> median (6) + na-flag column.
- Zero/missing Stage 5 model SEs for the 524 original rows replaced with 500-draw within-arm bootstrap SEs (MODEL_SE_BOOTSTRAP_DRAFT.csv); 146 of those rows carry the documented run10 stale-lineage unreliability flag (kept, flagged, never silently used as certainty). Expansion SEs kept as-is; 3 true-zero expansion SE cells retained with flags.

## Do a few experiments dominate?

- Grouping spreads (posterior mean SD, Model A log scale): experiment 0.41, pair 0.18, model 0.18, contrast 0.13. The experiment-level spread is the largest grouping effect — contrasts cluster strongly by experiment. No single experiment, however, drives the fixed effects (leave-one-experiment-out influence, Sensitivity C: ranges are narrow and sign-stable).
- Model B grouping spreads: contrast 0.87, experiment 0.57, pair 0.35, model 0.32.


## Sensitivities


### A. Human benchmark uncertainty (10 shared-draw refits)

The human benchmark of each contrast is redrawn from its own SE (one shared draw per contrast per replicate) and Model A refit on short chains (500/750).
- disclosure: mean -0.072, across-draw SD 0.009, range [-0.087, -0.060]
- disclosure_x_role_change: mean 0.044, across-draw SD 0.024, range [0.016, 0.080]
- disclosure_x_manipulation_location: mean -0.090, across-draw SD 0.016, range [-0.122, -0.067]
- human_abs_d_std: mean 0.425, across-draw SD 0.015, range [0.401, 0.440]
- log_se_y_std: mean 0.090, across-draw SD 0.008, range [0.080, 0.105]

### B. Excluding the Qwen family

- sensB_A: disclosure -0.043, human_abs_d_std 0.468 (max R-hat 1.0019)
- sensB_B: disclosure -0.020, human_abs_d_std 0.370 (max R-hat 1.0022)

### C. Leave-one-experiment-out influence (Model A, diagnostics only)

- disclosure coefficient across 31 exclusions: mean -0.076, range [-0.105, -0.044]
- human_abs_d_std coefficient: mean 0.424, range [0.340, 0.459]
- No single experiment flips the sign or the credibility of either key coefficient.

### D. Comparison with Stage 6 paired-disclosure results

- Model A average disclosure effect (experiment-averaged, equal weight per experiment): -0.074 log-scale units (95% CrI [-0.172, 0.026]) — i.e. a small, not clearly credible reduction in absolute error when disclosed. (The main-table pair-weighted disclosure coefficient is -0.076 [-0.179, 0.028]; the two agree in substance and differ only in weighting.)
- Stage 6 found accuracy improvement (blinded minus disclosed) 0.041 SD (equal-experiment weighting, 95% CrI [-0.023, 0.105]). Differences are explained by outcome (Stage 6 models direction-accuracy, Stage 9 models distance-from-human on the effect scale) and weighting (Stage 9's regression weights pairs, its experiment-averaged summary weights experiments). The Stage 6 and Stage 9 disclosure point estimates differ in sign, but both 95% intervals include 0, so they are statistically compatible.
