# TVD Method Audit — human split-half noise floor

Audit of how the denominator (human split-half noise floor) of the
Bayesian TVD ratio is estimated. Verified 2026-11-10 against frozen
artifacts; no code executed against the pipeline, nothing refitted.

## Data source — respondent-level microdata

- `human_answers.csv`: **22 cells** (11 experiments × 2 information
  conditions), **72,776 respondents** in total (≈75k, as described),
  columns: experiment, condition, support_size, n_respondents, counts.
- Experiments: the **same 11 retained T2KX expansion experiments** as
  the numerator (`matched_cells.csv` experiment set — verified
  identical). Twin-2K human references are aggregate registry cards
  with no respondent-level microdata, so the floor's experiment
  coverage is partial by design and disclosed wherever the ratio is
  used.

## Split-half procedure

- `floor_draws.csv`: **22,000 correlated split-half draws**, shape
  (22000, 4) — each draw is a pair of half-sample distribution
  estimates per cell, so TVD between halves is computed at the
  respondent level.
- The 22,000 draws are modelled at their data source via a
  hierarchical **Dirichlet-multinomial** model on the respondent
  counts (per the frozen design and producer code), so human-reference
  sampling uncertainty is covered where the floor is estimated.

## Weighting agreement

- 660 balanced fitted cells ÷ 11 experiments = **60 cells per
  experiment** in the numerator block.
- The floor block likewise weights the **11 experiments equally**
  (60-cells-per-experiment equivalence holds in both blocks), so
  numerator and denominator use consistent experiment weighting
  (equal-experiment weighting; the descriptive equal-cell anchor
  0.3874/0.0238 = 16.28 is a separate, disclosed estimand).

## Independence of numerator and denominator

- Numerator (model–human TVDs) and denominator (split-half floor)
  blocks share no parameters and no data.
- Empirical correlation of the paired draws in
  `posterior_ratio_draws.csv`: **−0.0085** (published as −0.009) —
  negligible; the one-to-one pairing is an exact joint-posterior
  sample, so ratio draws are valid without any independence
  assumption beyond the shared-joint sampling.

## Disclosed asymmetry (bounded)

- The one asymmetry: human-reference sampling uncertainty is fully
  modelled in the floor (its own data source) but **not propagated
  into the numerator** model–human distances.
- Bound: a worst-case propagation via the triangle inequality
  (Dirichlet posterior draws on the human counts) keeps the ratio no
  greater than **17.40**, inside the published 95% credible interval
  (16.18–17.57). Stated in S11 and methods.tex; not recomputed here
  because the bound draws are not among the frozen artifacts in this
  directory (same limitation as RESULT-3459).
- The partial floor experiment coverage (11 of 17 T2KX experiments;
  no Twin-2K microdata) is disclosed in S11 and methods.tex wherever
  the ratio is used.

## Verdict

The floor methodology is sound: respondent-level microdata from the
same 11 experiments, 22,000 correlated split draws modelled at source,
consistent experiment weighting, independent blocks, and the single
asymmetry is bounded and disclosed. No changes required.
