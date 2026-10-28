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
- **Figure 02** re-plots the validated TVD table `T1_tvd.csv` from
  `publication_audit/distributional_error_explanation_20261019/` (seeded
  20261010) — see the TVD provenance note below.
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

## TVD provenance verdict (fig02)

The TVD table `T1_tvd.csv` was **already built from the authoritative,
complete records** and is reused without recalculation. Verified: its
pipeline (RUN_LOG.md, scripts/exp_config.py) reads run10/run6 records from
`/home/justin/Documents/ZJU work/fos/results/unblinding/T2K10-…/` and
`TWIN2K_…/` — the canonical tree holding the full 200 records per leg. The
stale fos-data mid-run mirror (`/home/justin/work/fos-data/...`, frozen
2026-09-23 ~12:03, 1–2 records per arm for 9 models; see Stage 10
ROOT_CAUSE_ANALYSIS.md) appears nowhere in that package. No stale inputs, no
recalculation needed.

The grey reference is the **95th percentile of split-half human TVD**
(sampling variability), averaged over the experiment's contrasts and arms —
it is a descriptive reference, NOT a confidence interval and NOT a mean TVD.

## Figure 02 — Distributional mismatch (TVD)

Files: `fig02_tvd_mismatch.*`

- **Purpose:** how far each LLM's answer distribution sits from the human
  one per experiment, blinded vs disclosed; LLMs sit far above the human
  split-half noise line.
- **Source:** validated `T1_tvd.csv` (provenance above), reconciled-era
  records, seeded 20261010. n: 7 eligible experiments (Anchoring pools the
  african+redwood units); 15 models per experiment except Anchoring (11);
  one point per model × arm × condition.
- **Estimand:** TVD between the human answer distribution and the
  persona-averaged LLM distribution, per model, arm, condition (0 = identical
  distributions, 1 = completely different). TVD ≠ 0 for humans themselves
  because of split-half sampling variability — hence the grey reference.
- **Interval:** none plotted; the grey line is the 95th percentile of
  split-half human TVD (descriptive reference, see above).
- **Exclusions:** experiments without a registered common category set
  (e.g. base_rate, false_consensus); anchoring numeric estimates.
- **Proposed caption:** "Total variation distance (TVD) between each LLM's
  answer distribution and the human distribution, per model and arm, for the
  seven eligible experiments. Blinded: circles; disclosed: triangles. Grey
  lines mark the 95th percentile of human split-half TVD, the distance
  attributable to sampling variation alone."

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
