# TVD Posterior Verification — recomputed from saved draws

All summaries below were recomputed on 2026-11-10 from
`final_15_model_analysis/posterior_ratio_draws.csv` (8,000 joint
posterior draws) with pandas/numpy. Nothing was refitted.

## Headline posterior (recomputed)

| Quantity | Mean | 95% CrI (2.5%, 97.5%) |
|---|---|---|
| Model–human TVD (numerator) | 0.4007 | [0.3887, 0.4130] |
| Human split-half floor (denominator) | 0.0238 | [0.0231, 0.0244] |
| Divergence ratio | 16.87 | [16.18, 17.57] |

- P(ratio > 10) = **1.000** (all 8,000 draws above 10).
- Condition split: `numcond_disclosure` mean 0.4010,
  `numcond_uninformed` mean 0.4004 → condition ratios 16.9 vs 16.9,
  matching the published "essentially identical in the two information
  conditions".
- Per-model ratio range (each model's numerator draws over the
  equal-experiment-weighted floor): **12.9 (qwen3.8-27b) to
  21.4 (gemma-4-26b-a4b)** — matches S11 exactly.
- Descriptive anchor check: cell mean of `matched_cells.csv` tvd =
  **0.3874**; 0.3874 / 0.0238 = **16.28** — matches the frozen anchor.

## Fitted-N evidence

`matched_cells.csv` is the exact `observed` array passed to
`pm.Beta` in the producer code
(`implement-3377/analysis/final15_bayesian_tvd/build_dataset.py`).
Its contents pin the likelihood:

- 660 rows, zero missing values;
- 15 models × 11 experiments × 2 conditions × 2 legs = 660;
- `build_dataset.py::verify` asserts 660 cells, 15 models, 22,000
  floor draws and floor reproduction < 1e-8 before any fit runs.

## Ratio validity

- Numerator (model–human TVDs) and denominator (split-half floor)
  blocks share no parameters and no data; the one-to-one draw pairing
  in `posterior_ratio_draws.csv` is therefore an exact sample from the
  joint posterior.
- Empirical correlation between the paired numerator and denominator
  draws: **−0.0085** (published as ≈ −0.009). Negligible, consistent
  with independence.
- Posterior range of the ratio across draws: 15.5–18.26 (median
  16.87), far above the 10 threshold.

## Notes / limitations

- `posterior_tvd.nc` is HDF5-backed and no netCDF4/HDF5 reader was
  available in this session (same limitation as RESULT-3459); it is a
  diagnostics-stage artifact (1320 obs) and not needed to verify the
  headline posterior, which is fully pinned by
  `posterior_ratio_draws.csv` and `matched_cells.csv`.
- The worst-case triangle-inequality bound of 17.40 (human-reference
  uncertainty propagated into the numerator) is stated in S11 and
  methods.tex; its underlying bound draws are not among the frozen
  artifacts in this directory, so it is verified here as
  manuscript-consistent (17.40 < upper CrI 17.57) rather than
  recomputed.
