# TVD Sample Reconciliation — 572 vs 660

Every number in this document was re-verified directly against the frozen
artifacts in `final_15_model_analysis/` on 2026-11-10. Nothing was copied
from prior report prose.

## Resolution

**The headline Bayesian TVD analysis used exactly N = 660 fitted cells.**
"572" is a stale count from the earlier 13-model preliminary pass
(13 × 44) that survives only in docstrings and older report prose. It has
no effect on any published posterior.

## Fitted N, from artifacts

- `matched_cells.csv`: **660 rows, 0 missing values** — the exact
  `observed` array passed to the Beta likelihood.
- Structure: 15 models × 2 conditions × 11 experiments × 2 contrast legs
  = **660** (verified: 15 distinct models, 11 experiments, 2 conditions,
  22 leg conditions, 30 leg-rows per experiment).
- `build_dataset.py::verify` (worktree `implement-3377`,
  `analysis/final15_bayesian_tvd/`) asserts 15 × 2 × 11 × 2 cells,
  22,000 floor draws, and floor reproduction < 1e-8.

## Experiment accounting

- 17 T2KX expansion experiments in scope.
- **6 excluded at experiment level**, all frozen in
  `final15_primary_tvd_exclusions.csv`:
  - 4 × TESS raw microdata, no category coding
    (`T2KX-budescu779`, `T2KX-howard823`, `T2KX-keusch433`, `T2KX-reedBR32`)
  - 1 × human support mismatch (`T2KX-ml1_gamblers_fallacy`)
  - 1 × multi-item scale (`T2KX-ml1_imagined_contact`)
- 17 − 6 = **11 retained experiments** (list verified from
  `matched_cells.csv`: ml1_category_scales, ml1_reciprocity,
  ml1_allowed_forbidden, ml1_quote_attribution, ml2_hauser_s1,
  ml2_risen_tempt_fate, ml2_schwarz_order, ml2_shafir_choose_reject,
  ml2_miyamoto_correspondence, ml2_rottenstreich_affect,
  ml2_bauer_materialism).
- **660 / 660 cells retained** — zero cell-level exclusions inside the
  retained 11 experiments.

## What 572 was

572 = 13 models × 44 cells: the preliminary five-to-13-model pass count.
It survives as stale text in `MODEL_SPECIFICATION.md`,
`BAYESIAN_TVD_RESULTS.md` (limitations, line 33), and docstrings/strings
in `write_reports.py` / `build_dataset.py`. Doc-only cleanup is due the
next time reports are regenerated; no published number depends on it.

## The 1320-observation fit is a different model

`posterior_tvd.nc` / `diagnostics.json` come from the diagnostics-stage
Normal-likelihood fit over both experiment families (660 valid twin-arm
rows + 660 T2KX-arm rows = 1320; cf. `DISTRIBUTIONAL_FIDELITY.md`,
"n=1320 cells"). It is a diagnostics artifact, not the headline Bayesian
TVD posterior. The headline posterior is the 660-cell Beta fit whose
draws are frozen in `posterior_ratio_draws.csv`.

## Verification evidence table

| Claim | Source artifact | Re-verified value |
|---|---|---|
| Fitted cells | matched_cells.csv | 660 rows, 0 NaN |
| Models / experiments / conditions / legs | matched_cells.csv | 15 / 11 / 2 / 2 |
| Exclusions | final15_primary_tvd_exclusions.csv | 6 rows, reasons as above |
| Retained experiments | matched_cells.csv | 11 |
| Draw count | posterior_ratio_draws.csv | 8,000 |
| Posterior TVD | posterior_ratio_draws.csv | 0.4007 [0.3887, 0.4130] |
| Floor | posterior_ratio_draws.csv | 0.0238 [0.0231, 0.0244] |
| Ratio | posterior_ratio_draws.csv | 16.87 [16.18, 17.57] |
| P(ratio > 10) | posterior_ratio_draws.csv | 1.000 |
