# stage9_CHANGES.md — corrected explanatory regressions (identical specs,
# priors and seed 20261028; only the input effects/SEs changed)

## What was rerun
`ANALYSIS_TABLE.csv` was rebuilt from `CANONICAL_PAIRED_ANALYSIS.csv`
(same 553 pairs / 1106 cells, corrected model effects AND corrected
bootstrap SEs for every cell — the frozen pipeline's bootstrap-SE
substitution step is no longer needed and was dropped, `se_source =
canonical_reconciled_v1`), the corrected Stage 7 audit (human side
unchanged), and the SAME frozen `EXPERIMENT_FEATURES.csv`. Feature
prep, model specs (Gamma log-link absolute error + logistic direction;
non-centered multilevel offsets for model/experiment/contrast/pair;
HalfNormal(0.5) group SDs, Normal(0,0.5) slopes, Gamma shape
HalfNormal(2)), scaling, seed 20261028 and chains are byte-identical
to the frozen run. Both regressions refit; sensitivities A (human
uncertainty, 10 redrawn benchmarks), B (Qwen-family exclusion) and D
(average disclosure effect vs corrected Stage 6) rerun.

## Convergence and PPC (corrected fits)
- Model A: 0 divergences, max R-hat 1.0022, min bulk ESS 3412; PPC:
  obs mean 0.624 inside posterior-predictive mean CI [0.583, 0.690],
  92.0% of obs inside the 90% PPC interval.
- Model B: 3 divergences (frozen also reported divergences; same spec
  and sampler), max R-hat 1.0005, min bulk ESS 4247; PPC obs mean
  0.740 inside CI [0.706, 0.772], 100% inside 90% interval.

## Model A — absolute error (frozen → corrected, posterior mean, 95% CrI)
| predictor | frozen | corrected |
|---|---|---|
| human_abs_d_std | 0.429 (0.217, 0.627), p+ = 0.9999 | 0.416 (0.209, 0.617), p+ = 1.000 |
| log_se_y_std | 0.090 (0.020, 0.158), p+ = 0.994 | 0.077 (0.019, 0.133), p+ = 0.994 |
| disclosure | −0.076 (−0.179, 0.028), p+ = 0.074 | −0.083 (−0.187, 0.020), p+ = 0.060 |
| disclosure_x_role_change | 0.029 (−0.307, 0.369) | 0.016 (−0.323, 0.363) |
| disclosure_x_manip_location | −0.094 (−0.194, 0.005), p+ = 0.031 | −0.069 (−0.171, 0.032), p+ = 0.090 |

Translation (raw units): +0.5 SD human effect size → +59.0% absolute
error (frozen +61.3%); disclosure main effect −7.9% (frozen −7.2%).
**One significance change**: the disclosure x manipulation-location
interaction no longer excludes zero (frozen 95% CrI [−0.194, 0.005],
corrected [−0.171, 0.032]) — any text treating "disclosure helps more
when the manipulation sits late in the vignette" as established must
be dropped. Equal-experiment-averaged disclosure effect: −0.079
(−0.171, 0.021).

## Model B — direction-correct (frozen → corrected)
| predictor | frozen | corrected |
|---|---|---|
| human_abs_d_std | 0.508 (0.025, 0.987), p+ = 0.980 | 0.482 (0.003, 0.965), p+ = 0.976 |
| log_se_y_std | 0.197 (−0.031, 0.435) | 0.158 (−0.048, 0.360) |
| disclosure | −0.110 (−0.453, 0.234) | −0.128 (−0.472, 0.216) |
| disclosure_x_role_change | −0.172 (−0.852, 0.527) | 0.006 (−0.686, 0.699) |
| disclosure_x_manip_location | −0.276 (−0.630, 0.073), p+ = 0.065 | −0.347 (−0.696, 0.005), p+ = 0.026 |

Translation: +0.5 SD human effect size → +6.1 pp direction-correct
(frozen +6.5 pp), 95% CrI [0.04, 11.7] — still positive but now
barely excluding zero. The disclosure x manipulation-location
interaction moves the OTHER way (away from significance in A, toward
it in B); neither leg is a stable finding. Equal-experiment-averaged
disclosure effect: −2.0 pp (−7.6, +2.9); direction-correct share
934/32 contrasts = 0.740.

## Sensitivities
- A (human uncertainty, 10 draws): all key coefficients stable —
  disclosure −0.079 ± 0.008 (range −0.088 to −0.065), human_abs_d_std
  0.408 ± 0.011, log_se_y_std 0.080 ± 0.011. Conclusions robust to
  human-benchmark uncertainty.
- B (drop Qwen, 9 models left): Model A disclosure −0.053, human
  effect 0.448; Model B human effect 0.374 — same signs, slightly
  attenuated; no conclusion depends on the Qwen family.
- D (average disclosure effect, log absolute-error ratio): −0.082
  (−0.182, +0.018) — consistent with corrected Stage 6
  equal-experiment accuracy improvement +0.041 SD (−0.023, +0.105),
  pr>0 = 0.895: no detectable overall disclosure benefit in either
  parameterization.

## Files
`ANALYSIS_TABLE.csv`, `MODEL_INPUTS_A.csv`, `MODEL_INPUTS_B.csv`,
`FEATURE_SCALING.json`, `REGRESSION_EFFECTS.csv`,
`outputs/EXPERIMENT_AVG_EFFECTS.csv`, `outputs/diag_*.json`,
`outputs/posterior_*.npz`, `outputs/sensitivity_A/B/D.json`,
`EXPERIMENT_EXAMPLES.md`, `scripts/corrected_build_analysis_table.py`
plus byte-identical copies of the frozen `prep_features.py`,
`fit_models.py`, `make_outputs.py`, `run_sensitivities.py` (stage6
comparison path pointed at corrected_results/stage6),
`make_reports.py`.
