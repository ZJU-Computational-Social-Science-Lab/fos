# FIGURE_GUIDE.md — Stage 11 final journal figures (7-figure set)

What this file does: it documents the 7 retained journal figures in
`figures/` — the question each answers, exactly which data files it was
built from (with provenance), the estimand and interval method behind every
plotted number, exclusions, and a proposed journal caption. It also records
the slope-estimator decision (figs 03–05), the TVD provenance verdict
(fig02), the interval audit table, and the recommended figure set.

All 7 figures were regenerated end-to-end by `scripts/generate_figures.py`
(seeded, SEED=20261028 in `fig_common.py`), visually inspected as PNGs, and
are reproducible. Every figure ships as PNG (300 dpi) + vector PDF
(identical content) + a CSV holding the exact plotted numbers.

**Global visual rule (verified on every PNG):** no titles, subtitles,
annotations, printed estimates, sample-size text or interpretive notes
anywhere in the figures. Only axis labels, tick labels, data, minimal
legends, reference lines and necessary experiment names.

**Blinding color rule (every figure):** blinded = blue (points, fitted
lines, bands), disclosed = orange/muted red, human references = grey/black.

## Data provenance (applies to all figures)

- **Figures 03–07** are built only from the Stage 10 reconciled_v1 canonical
  tables, read read-only from
  `stage10_data_reconciliation/data/CANONICAL_MODEL_EFFECTS.csv` and
  `CANONICAL_PAIRED_ANALYSIS.csv` (see `fig_common.load_effects()` /
  `contrast_table()`). Frozen Stage 3/5/9 effect estimates are never used.
- **Figure 02** recomputes distributional distances for all 31
  experiments from the complete authoritative response records (see the
  Figure 02 provenance note below).
- **Direction figures (07)** use only the 32 contrasts whose human direction
  is confident (two-sided 95% interval excluding zero, same rule as Stage 6).
  The 6 uncertain contrasts are excluded from direction scoring and are never
  counted as failures. Confidence is recomputed in
  `fig_common.contrast_table()`; the script raises if the count is not 32.

## Slope-estimator decision (figs 03, 04, 05)

Three slope sets existed: (a) the Stage 10 corrected Stage 3 WLS estimator
(**0.476 [0.302, 0.648]** blinded, **0.884 [0.568, 1.041]** disclosed);
(b) the Stage 11 exploratory figure method — pooled OLS on all model×contrast
cells with a contrast-cluster bootstrap CI (~0.63 / ~0.78); (c) the Stage 11
hierarchical posterior beta (~0.53 / ~0.56). Traced: (a) collapses to
model-means within experiment×contrast, weights each experiment once (1/k_e),
fits WLS through the origin, and gets its CI from a family-cluster bootstrap
(frozen seeds 20261010 + offsets, deterministic); (b) weights every cell
equally (so model-heavy contrasts dominate) and clusters only by contrast;
(c) is a Bayesian partial-pooling model with experiment and model random
effects — a different estimand, reported in COMPRESSION_ANALYSIS.md.

**Decision:** the prespecified Stage 10 primary magnitude-recovery estimator
(a) is used for the fitted lines in figs 03/04 and the points+CIs in fig05 —
one estimator and one interval method across all three. Rationale: it is the
estimator prespecified before unblinding and already rerun unchanged on the
corrected reconciled_v1 data in Stage 10; no refitting was done. Its CIs are
wider than (b)'s because resampling paradigm families is coarser than
resampling contrasts — this is honest, not a defect. The slope is
scale-invariant here (both axes divide by the same per-contrast pooled SD),
so the pp-scale Stage 10 values apply directly to the standardized axes;
`fig_common.stage10_slope_ci()` recomputes the point estimate from the
corrected signed table and refuses to plot on any mismatch.

## Figure 02 provenance and metric note

Figure 02 was rebuilt (2026-10-28) as an all-31-experiment overlaid
histogram with a common distance metric, replacing the earlier
7-experiment TVD figure. Data provenance, per side:

- **Original 14 units** — human answer codes from the registered primary
  wave (`agreed_figure_code_package/data/wave1_3_response.csv`) and LLM
  persona distributions from the run-10/run-6 unblinding logprob records
  (`T2K10-…/`, `TWIN2K_…/`), reusing the validated
  `publication_audit/distributional_error_explanation_20261019` loaders
  (seeded 20261010). Verified: these are the complete canonical records;
  the stale fos-data mid-run mirror (Stage 10 ROOT_CAUSE_ANALYSIS.md)
  appears nowhere in the path.
- **Expansion 17 experiments** — human respondents from the cleaned ML1/ML2
  tidy files and the archived TESS `.sav` studies, coded with each
  experiment's registered outcome coding; LLM persona values streamed from
  the complete production records of the expansion run
  (`expansion/work/T2KX-20261022T222604/`, the Stage 10-verified
  authoritative source), retained at the registered primary cut
  (`branch_mass >= 0.80`); excluded records are missing, never zero.

**Metric:** normalized 1-D Wasserstein distance. Each experiment's
registered outcome space (the registered answer coding's value range, read
from the frozen pipeline codings) is scaled to [0, 1]; the distance between
the human and LLM response distributions is the Wasserstein-1 distance on
that scale. For two-point (binary) spaces this equals the total variation
distance (verified: the binary original-14 values reproduce the old TVD
table exactly, e.g. allais control 0.2706). No bins, no invented orderings,
no mean substitutes. The metric is therefore a generalization, not TVD —
the figure and files are renamed `fig02_distributional_distance.*`.
Anchoring units are scored on the registered anchor more/less item (the
same eligibility the validated TVD analysis used).

**Split-half reference:** per experiment and arm, 500 seeded splits
(SEED=20261028 + experiment offset) of the human respondents into halves;
the same Wasserstein distance is computed between the halves. The grey
histogram is the FULL reference distribution (one value per draw, aggregated
equal-weight over the experiment's arms), not a percentile point.

**Aggregation:** equal weight per experiment. Arm-level distances average
within experiment x model x blinding (a shared control arm counts once),
models average equally within experiment, and each experiment carries
total weight 1/31 in every curve; the split-half pool is
experiment-equal-weighted the same way. Raw responses are never pooled
across experiments.

**Validation:** distances all within [0, 1] (observed 0.002–0.935), no
missing cell scored as zero, human and LLM sides scored on the identical
registered coding, and the plotted CSV holds the exact plotted numbers.
All 31 experiments are included (coverage table:
`analysis/fig02_coverage_table.csv`); none excluded.

## Figure 02 — Distributional mismatch (all 31 experiments)

Files: `fig02_distributional_distance.*`

- **Purpose:** how far LLM answer distributions sit from the human ones,
  blinded vs disclosed, across ALL 31 experiments; both LLM histograms
  sit far to the right of the human split-half distribution.
- **Source:** recomputed end-to-end by `scripts/figures_distributions.py`
  + `run_fig02_all31.py` (+ `fig02_original14.py`, `fig02_expansion.py`,
  `fig02_tess.py`, `fig02_common.py`), seeded 20261028; provenance and
  metric above. Per-arm numbers: `analysis/fig02_dist_by_arm.csv`; plotted
  per-bin values: `figures/fig02_distributional_distance.csv` (raw
  weighted points behind each histogram:
  `figures/fig02_hist_points.csv`,
  `figures/fig02_hist_splithalf_points.csv`);
  split-half draws: `analysis/fig02_split_half_draws.csv`.
- **Estimand:** normalized Wasserstein-1 distance between the human and
  LLM response distributions on the registered outcome space (0 =
  identical, 1 = completely different; = TVD for binary spaces),
  experiment-equal aggregated. Human–human distance is not zero because of
  split-half sampling variability — hence the grey reference histogram.
- **Interval:** none plotted; no statistically justified clustered band —
  model×arm observations are not independent experiments, so no uncertainty
  band is drawn rather than an unjustified one.
- **Display:** one panel, three overlaid step-outline histograms
  (blinded blue, disclosed orange, human split-half grey), x-axis 0–1,
  bin width exactly 0.01 (100 bins).
- **Normalization:** experiment-equal weighted PROPORTION — each curve's
  bin heights sum to 1, using the same per-experiment weights as the
  aggregation above (each experiment carries total weight 1/31; the
  split-half pool 1/(31·500) per draw). Not a density; the three curves
  are directly comparable as shares of all scored distances.
- **Exclusions:** none — all 31 experiments support a registered-space
  distributional comparison (`fig02_coverage_table.csv`, included=yes
  for all).
- **Proposed caption:** "Distributions of the distance between LLM and
  human response distributions, for all 31 experiments (each experiment
  weighted equally; bin width 0.01, proportions normalized to sum to one
  per curve). Blinded (blue) and disclosed (orange) LLM distances against
  the human split-half reference distribution (grey), computed with the
  same normalized Wasserstein metric on each experiment's registered
  response scale."

## Figures 03 + 04 — Effect recovery (blinded / disclosed)

Files: `fig03_recovery_blinded.*`, `fig04_recovery_disclosed.*`

- **Purpose:** raw evidence of magnitude compression: all eligible
  model×contrast cells against the human effect, with the 45° line and the
  Stage 10 corrected recovery line. fig03: 560 cells; fig04: 559 cells;
  38 contrasts × 15 models (one disclosed cell missing).
- **Source:** `CANONICAL_MODEL_EFFECTS.csv` (reconciled_v1); plotted values
  in the two CSVs.
- **Estimand:** y = LLM standardized effect, x = human standardized effect;
  fitted line = y = b·x with the Stage 10 corrected WLS-through-origin slope
  (see slope decision above).
- **Interval:** none drawn on the scatter (slope CIs live in fig05, same
  estimator/method). Points are display-only; identical axes (±1.45),
  aspect, marker size and opacity across both figures.
- **Exclusions:** none beyond data availability (the one missing cell).
- **Proposed caption:** "Standardized human effects versus standardized LLM
  effects for every eligible model×contrast cell, blinded (a) and disclosed
  (b). Dotted line: perfect recovery. Solid line: recovery slope estimated
  with the prespecified experiment-weighted through-origin regression on the
  corrected data (0.48 blinded, 0.88 disclosed)."

## Figure 05 — Recovery slopes

Files: `fig05_recovery_slopes.*`

- **Purpose:** the headline compression result and its disclosure effect.
- **Source/data:** Stage 10 corrected outputs
  (`stage10_data_reconciliation/corrected_results/stage3/`):
  point estimates recomputed from `corrected_signed_contrasts.csv`, CIs from
  `bootstrap_cis_frozen_method.csv`; values also in `fig05_slopes.csv`.
- **Estimand:** WLS-through-origin recovery slope on model-means within
  contrast, experiments weighted 1/k_e (18 original-14 contrasts).
  Blinded 0.476 [0.302, 0.648]; disclosed 0.884 [0.568, 1.041].
- **Interval:** 95% family-cluster bootstrap CI (resampling paradigm
  families; frozen seeds 20261010 + per-statistic offsets) — the same
  estimator and interval method as the fig03/04 fitted lines.
- **Proposed caption:** "Magnitude-recovery slopes by disclosure condition
  (points: point estimates; bars: 95% family-cluster bootstrap intervals).
  A slope below 1 indicates compression of LLM effect magnitudes relative to
  human effects. Disclosure moves the slope toward, and statistically within
  reach of, perfect calibration."

## Figure 06 — Absolute error by disclosure

Files: `fig06_abs_error_by_disclosure.*`

- **Purpose:** does disclosure reduce how far LLM point effects sit from
  human effects? (It does not, beyond a small insignificant difference.)
- **Source:** `CANONICAL_MODEL_EFFECTS.csv`; per-cell |LLM − human|
  averaged within experiment, then across experiments. Values in
  `fig06_abs_error_by_experiment.csv`.
- **Estimand:** experiment-equal-weighted mean absolute standardized error
  (kept as established — not switched to cell-weighted); the paired
  within-experiment difference (disclosed − blinded) is plotted on its own
  side of a visual separator. Denominator verified: **31 experiments** with
  both conditions.
- **Interval:** actual 95% **bootstrap CIs** over experiments (2,000 draws,
  seeded) from the existing experiment-level procedure — NOT credible
  intervals.
- **Exclusions:** 7 experiments lack one condition and drop out of the
  paired comparison.
- **Proposed caption:** "Mean absolute standardized error by disclosure
  condition (left of the divider) and the paired within-experiment
  difference (right). Each experiment contributes once; bars are 95%
  bootstrap intervals over the 31 experiments."

## Figure 07 — Direction accuracy vs |human effect| (2 files)

Files: `fig07_direction_accuracy_blinded.*`,
`fig07_direction_accuracy_disclosed.*`

- **Purpose:** directional agreement rises with human effect magnitude.
- **Source:** `CANONICAL_MODEL_EFFECTS.csv` + `contrast_table()`; values in
  the two CSVs (per-contrast accuracy and actual per-contrast model counts).
- **Estimand:** share of eligible LLMs with the correct direction, one point
  per direction-confident contrast (32), vs |human effect|.
- **Interval:** 95% confidence band from an experiment-clustered bootstrap
  (experiments resampled, 2,000 draws, seeded). Band values outside 0–1 are
  clipped visually by the axis limits only — the computed band is
  unmodified.
- **Exclusions:** the 6 direction-uncertain contrasts (never counted as
  failures); missing model cells reduce a contrast's denominator (counts in
  the CSV). Identical axis limits (x: 0–1.5, y: 0–1) across both files.
- **Proposed caption:** "Share of eligible LLMs reproducing the human effect
  direction, per direction-confident contrast, against the standardized
  human effect magnitude. Line and band: linear fit with 95% interval from a
  bootstrap over experiments."

## Interval audit (§10 of the brief)

| Figure | Observations | Estimated quantity | Interval type | Procedure / resampled unit | Same calculation for estimate+interval? |
|---|---|---|---|---|---|
| 02 | model×arm×condition TVDs, 7 experiments | TVD per cell; grey ref | none / descriptive reference | split-half 95th percentile of human TVD (not a CI, not a mean) | reference line from the validated split-half table; points are exact validated TVDs |
| 03/04 | 560/559 model×contrast cells | scatter + fitted line slope | none drawn (CI in fig05) | fitted line = Stage 10 corrected estimator | n/a (no band plotted) |
| 05 | 262 cells → 18 collapsed contrasts | recovery slope per condition | 95% CI | family-cluster bootstrap, resampling paradigm families, frozen seeds | yes — points and CIs both from the Stage 10 corrected run |
| 06 | cells → 31 experiments | experiment-equal mean abs error + paired difference | 95% bootstrap CI (not credible) | resampling experiments (2,000 draws, seeded) | yes |
| 07 | 32 confident contrasts | per-contrast direction accuracy + linear trend | 95% CI band | experiment-clustered bootstrap | yes |

Checks confirmed: no naive cell-level bootstrap replaced a cluster
bootstrap; model×contrast cells were never treated as independent
experiments; wide intervals from 31 experiments preserved; no interval was
narrowed for appearance; no interval-definition error was found in the
retained figures (the only genuine inconsistency was the slope estimator,
resolved above).

## Excluded from the journal set (historical files, untouched)

fig01 (distribution examples, 6 files), fig08 (abs error trend), fig09
(agreement by experiment), fig10/fig11 (heatmaps) remain in `figures/` as
exploratory/history; their earlier documentation still applies to those
files. They are NOT part of the recommended set.

## Recommendations — the 7-figure journal set (manuscript order)

1. **fig02** — LLMs do not reproduce human response distributions.
2. **fig03 + fig04** — direction often recovered, magnitude compressed.
3. **fig05** — the compression slopes with honest CIs (headline numbers).
4. **fig06** — disclosure improves calibration (slope) without a clear
   absolute-error reduction.
5. **fig07_blinded + fig07_disclosed** — directional agreement increases
   with human effect magnitude.
