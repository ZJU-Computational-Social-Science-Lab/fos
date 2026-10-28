# stage5_CHANGES.md — corrected Stage 5 exploratory analysis
# (identical specs/priors/seeds; only the input data changed)

## What was rerun
A1 (disclosure susceptibility), A2 (compression, errors-in-variables) and
A3 (joint predictor model) were refit on the 553 canonical paired cells
from `CANONICAL_PAIRED_ANALYSIS.csv` — corrected model effects AND the
corrected per-model persona-bootstrap SEs (the frozen run had no per-model
SE for the original 18 contrasts; the canonical build supplies honest
bootstrap SEs, 0 only where responses are constant). Priors, model specs,
seeds (fits 20261027, PPC 20261028, sensitivity 20261027–31), chains,
warmup/samples and all derived tables are byte-identical procedures from
the frozen scripts. All 6 `new_only` cells concern pairs absent from the
frozen 553, so they do not enter (flagged: comparability preserved by
construction).

## Headline numbers, frozen → corrected (posterior mean, 95% CrI)

| result | frozen | corrected | interpretation |
|---|---|---|---|
| A1 disclosure effect b_disc | 0.0390 | 0.0298 (−0.116, 0.178) | unchanged: no detectable overall disclosure effect |
| A2 recovery slope blinded g_blind | 0.5192 | 0.5089 (0.263, 0.787) | unchanged |
| A2 recovery slope disclosed g_disc | 0.6630 | 0.6469 (0.390, 0.917) | unchanged |
| A2 slope difference | 0.1438 | 0.1380 (0.009, 0.267) | still positive, barely excluding 0 |
| pr(accuracy improves) > 0, equal-weight | 0.900 | 0.929 | unchanged qualitatively |
| pr(> 0.1 meaningful) | 0.035 | 0.043 | unchanged |

## Sensitivity results (all corrected refits unless noted)
- Prior halve/double (A1, A2), pp-tier refit, LOEO: same conclusions as
  frozen; LOEO sign flips of the headline effect: 6 of 31 (vs 5 of 31
  frozen) — all driven by small original-group experiments.
- **A2 prior-doubled refit FAILED the convergence gate** (R-hat 1.012,
  ESS 244). Documented as an unstable fit, not substituted (frozen run
  passed with ESS 401 — borderline there too).
- Group split: original-only b_disc −0.234 (−0.477, −0.010) — now
  **excludes zero** (frozen −0.209 (−0.449, +0.045) included it).
  Expansion-only +0.259 (0.100, 0.404), essentially unchanged. The
  original-vs-expansion contrast sharpens slightly.

## Convergence / PPC (corrected main fits)
- A1: max R-hat 1.006, min bulk ESS 816; PPC coverage blinded 0.942,
  disclosed 0.940, SD posterior-p 0.498.
- A2: max R-hat 1.006, min bulk ESS 589; PPC coverage 0.942/0.940,
  SD posterior-p 0.480.
- A3: passed the same gate; predictor estimates essentially unchanged
  (expansion_group 0.523 vs 0.527 frozen; all CIs overlap).

## Files
posterior_summary.csv, experiment_susceptibility.csv, overall_summary.csv,
compression_analysis.csv, predictor_analysis.csv, diagnostics_a1/a2/a3.csv,
sensitivity_results.csv, MODEL_VALIDATION.md.
