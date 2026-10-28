# Method and QA — Stage 9 explanatory regressions

Reproducibility, data lineage, statistical assumptions, and analysis decisions for
`_project_governance/stage9_explanatory_regression/`. Companion documents:
REGRESSION_RESULTS.md (estimates), MODEL_DIAGNOSTICS.md (convergence/QA),
EXECUTIVE_SUMMARY.md and SCIENTIFIC_INTERPRETATION.md (interpretation).

## 1. How to rerun

Prerequisites (NOT rebuilt by the pipeline; they predate this stage):

- `ANALYSIS_TABLE.csv` (1,106 rows) — built by `scripts/build_analysis_table.py`
  from frozen Stage 5/6 outputs.
- `EXPERIMENT_FEATURES.csv` (38 rows) — built by `scripts/prep_features.py` from the
  blind feature coding (CODING_RECONCILIATION.md documents the two-pass process).
- The frozen record trees (run6/run10/expansion) and the frozen Stage 5 dataset.

Then run:

```bash
./run_pipeline.sh
```

which executes, in order, with the project venv python
(`/home/justin/Documents/ZJU work/fos/venv/bin/python`):

1. `scripts/fit_models.py --model a --tag mainA`
2. `scripts/fit_models.py --model b --tag mainB`
3. `scripts/make_outputs.py`
4. `scripts/run_sensitivities.py all`
5. `scripts/make_reports.py`

All scripts take their paths from their own location (`STAGE9 = parents[1]`), so the
directory is relocatable. Full refit takes roughly 30–60 minutes (main fits +
10 sensitivity-A refits + B variants + 31 LOO refits).

## 2. Script inventory and seeds

| Script | Purpose | Seed |
|---|---|---|
| `scripts/build_analysis_table.py` | builds ANALYSIS_TABLE.csv (pairs, absolute_error, correct_direction) | n/a (deterministic) |
| `scripts/prep_features.py` / `build_features.py` | feature table + codebook cross-check | n/a (deterministic) |
| `scripts/feature_descriptives.py` | FEATURE_DESCRIPTIVES.md (outcome-free) | n/a |
| `scripts/compute_text_features.py` | wording_difference, question_length (+ evidence file) | n/a |
| `scripts/fit_models.py` | NumPyro NUTS fits (A, B, or sensitivity tags) | 20261028 |
| `scripts/make_outputs.py` | REGRESSION_EFFECTS.csv, EXPERIMENT_AVG_EFFECTS.csv, EXPERIMENT_EXAMPLES.md | posterior-based (no resampling) |
| `scripts/run_sensitivities.py` | Sensitivities A (10 shared-draw refits), B (Qwen exclusion), C (31 LOO refits), D (Stage 6 comparison) | 20261028 |
| `scripts/make_reports.py` | REGRESSION_RESULTS.md, MODEL_DIAGNOSTICS.md, DRAFT_KEY_FINDINGS.md, DRAFT_INTERPRETATION.md | posterior-based |
| `scripts/arm_texts_original.py` / `arm_texts_expansion.py` | frozen arm text/prompt data used by feature coding | n/a |
| `scripts/tmp_coverage_audit.py` / `tmp_model_se_bootstrap.py` | data-lineage audit + 500-draw within-arm bootstrap SEs (TASK-2999; kept for reproduction, filename prefix retained) | 20261028 |

Single seed everywhere: **20261028** for all MCMC and bootstrap resampling.

## 3. Data lineage

- **Records:** 413,520 confirmed study records — run6 47,520 (480 PREFLIGHT records
  documented as non-study data), run10 57,000, expansion 309,000. Zero records with
  `succeeded=false`. Verified by direct recount (RESEARCH_DATA_COVERAGE.md).
- **Run10 stale-lineage caveat:** 145 of 530 original cells (27%) do not reproduce
  the canonical frozen d_m from hash-verified records; the frozen chain had consumed
  stale intermediate arm means (n=1) for exactly those cells. The records themselves
  are complete and hash-frozen. Stage 9 keeps the frozen values as given and flags
  (never silently repairs) them; 146 of the 524 original rows used in the models
  carry the flag. Sensitivity B (Qwen exclusion) overlaps heavily with the affected
  models and leaves conclusions unchanged.
- **Zero/missing model SEs:** Stage 5 zero-fills original `se_y_std`; zero is a
  missing-value sentinel. All 524 original rows use 500-draw within-arm bootstrap
  SEs (`MODEL_SE_BOOTSTRAP_DRAFT.csv`, seed 20261028, frozen d_m definitions);
  expansion rows keep their Stage 5 SEs. 3 expansion cells with true-zero SEs are
  retained and flagged. 6 degenerate bootstrap cells and 10 cells with an empty arm
  (matching the frozen pipeline's own exclusions) are documented in the bootstrap
  file.
- **correct_direction convention:** rows with `y_std == 0` count as NOT
  direction-correct (`correct_direction = 0`); 4 rows affected (C-21/qwen3-4b,
  C-11/granite, C-17/granite, ×2 blinded/disclosed legs).

## 4. Coverage

- Original experiments: 16 contrasts × 15 models, run6/run10 lineage.
- Expansion (T2KX): 22 contrasts × 15 models.
- Feature coverage: 38/38 contrasts coded blind (two independent passes; reconciliation in
  CODING_RECONCILIATION.md). Missing cells: manipulation_location 1 contrast
  (C-36, median-imputed + NA flag), n_response_options 3 contrasts (C-08, C-13,
  C-14, median-imputed + NA flag). NA flags enter the models as predictors.
- Analysis samples: Model A 1,106 rows (553 pairs); Model B 934 rows (32
  direction-confident contrasts, 467 pairs).

## 5. Statistical assumptions

- **Model A:** absolute error ~ Gamma(log link); slopes on standardized predictors;
  groupings experiment/contrast/pair/model (non-centered HalfNormal(0.5) SDs).
  Gamma chosen for the right-skewed positive error scale; PPC shows observed mean
  0.630 inside the predictive mean interval [0.590, 0.692], 92.2% coverage of 90%
  intervals, slight over-dispersion possible in the tail (documented).
- **Model B:** same-direction indicator ~ logistic; same grouping structure;
  reference categories response_format=rating_mean (verified modal, 540/1106 — a
  documented deviation from the spec's binary_choice suggestion) and
  self_other=self (31/38).
- **Priors:** intercept Normal(0, 1.5); slopes Normal(0, 0.5); grouping SDs
  HalfNormal(0.5) non-centered; Gamma shape HalfNormal(2). Fixed before fitting; no
  pilot tuning.
- **Dependence structure:** rows within a pair share a contrast and model; the pair
  grouping term models this. Contrasts nest in experiments; experiments supply the
  largest variance component. No exchangeability is assumed across experiments
  beyond the hierarchical shrinkage.
- **Computational:** NumPyro NUTS, 4 chains, 1000 warmup + 2000 samples each (8,000
  draws), target_accept_prob 0.90, seed 20261028.

## 6. Model-validation rules and outcomes

Spec thresholds: flag if R-hat ≥ 1.01 or bulk ESS < 400 on intercept/slopes.

- Model A: max R-hat 1.0028, min bulk ESS 2960, 0 divergences, 0 flags.
- Model B: max R-hat 1.0009, min bulk ESS 5162, 13/8000 divergences (0.16%,
  pair-grouping scale), 0 flags. Divergences reported rather than tuned away:
  R-hat/ESS clean, non-centered parameterization already in use, and Sensitivity A
  refits (different data, same kernel) reproduce fixed effects closely.
- Posterior predictive checks on Model A (above) pass.
- No p-values are computed or reported anywhere in this stage; uncertainty is 95%
  credible intervals and P(positive) only.

## 7. Every analysis decision (log)

1. Direction analysis restricted to the 32 human-direction-confident contrasts
   (spec-defined; 934 rows).
2. Zero-SE replacement by bootstrap (Section 3) — spec-mandated, seed 20261028.
3. response_format reference changed from spec-suggested binary_choice to modal
   rating_mean after the spec's own modality check was applied (documented
   deviation).
4. Missing manipulation_location / n_response_options median-imputed with NA flag
   predictors retained.
5. Overlap between explicit_probability and numerical_manipulation (26/38) handled
   by keeping both and interpreting each conditionally; reported in results.
6. Sparse features (3/38 each) kept in both models under the Normal(0, 0.5) prior;
   flagged as weakly identified rather than dropped.
7. Equal-weight-per-experiment headline summary computed with a draws axis
   (experiments × draws) so 95% credible intervals are defined; regenerated by
   scripts, never hand-edited (QA fix, RESULT-3006 finding #1).
8. Sensitivity D labels experiment-averaged vs pair-weighted disclosure estimates;
   Stage 6/9 sign difference noted as statistically compatible (both intervals
   include 0).
9. Model B footnote documents that translated estimates are average marginal
   effects and can carry opposite sign to the mean logit (question_order example).
10. Null findings reported alongside credible ones (no selection).
11. All results generated by script from frozen posteriors; no manual edits to
    outputs. run_pipeline.sh documents its input prerequisites.
