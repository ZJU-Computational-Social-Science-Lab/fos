# EXECUTIVE_SUMMARY.md — Stage 10 data reconciliation, for the project owner

## 1. What was wrong?
VERIFIED: the frozen run10 effect values were computed from the
**2026-10-04 state** of the raw inference records, while the project
root holds a **2026-10-05 re-run** of those records. Rebuilding from
the hash-frozen `fos-data` mirror reproduces **every one of the 524
frozen values exactly**; rebuilding from the canonical records gives
different values for 139 cells — so the frozen pipeline provably read
the older snapshot. In addition, the frozen pipeline (whose baked-in
data mirror lacked the anchoring arms) **dropped 6 anchoring cells**
that have usable canonical data. No estimator, spec, or seed was
wrong — only the inputs.

## 2. How much was wrong?
Of 1119 canonical effect cells (38 contrasts × 15 models × 2 blinding
legs, minus true coverage gaps): **139 corrected** (all in the 8 run10
original-14 experiments; 13 of them flip sign) and **6 new-only**
anchoring cells added. The coverage arithmetic: the frozen wide table
was 262 model-experiment rows × 2 legs = **524**; the audit examined
**530** cells because 4 anchoring model-experiment arms are empty even
in the canonical records (10 cells) and 6 of the previously dropped
anchoring cells have real data (90–99 of 100 valid outcomes). Those 6
are the new-only cells; they are reported but kept OUT of the paired
553-pair analyses so every before/after comparison stays like-for-like.

## 3. What was corrected vs already correct?
**974 of 1119 cells (87%) were already exactly correct** — every run6
experiment (disease, fire_extinguisher, seatbelt, sunk_cost,
wta_wtp, less_is_more) and all expansion contrasts. All 139
corrections sit in the run10 experiments (abs_relative, prob_matching,
allais, anchoring_×2, linda, myside, outcome_bias) × 15 models ×
2 legs. Human benchmarks were never affected.

## 4. Did the findings change?
Substantively, **no**. With real estimates and intervals
(SCIENTIFIC_RESULTS_BEFORE_AFTER.md, all 17 rows):
- Recovery slopes: blinded 0.4935 → 0.4762 (CI 0.302–0.648);
  disclosed 0.8978 → 0.8842 (0.568–1.041); disclosure difference
  0.4043 → 0.4080 (0.059–0.592).
- Direction agreement: blinded 0.747 → 0.749; disclosed 0.726 → 0.730.
- The same **7 majority-wrong contrasts** (C-03, C-09, C-16, C-26,
  C-30, C-31, C-37) with identical classifications — each explicitly
  re-audited; C-16's corrected blinded majority shrinks toward zero
  rather than reversing.
- Shared-failure regression beta −0.55 → −0.558 (89% HDI −1.00, −0.10);
  holds when each model family is excluded.
- Stage 9: larger human effects → larger AI absolute error
  (+61.3% → +59.0% per 0.5 SD) and slightly better direction accuracy
  (+6.5 → +6.1 pp); disclosure shows no overall benefit (−7.2% → −7.9%).
Two numerical claims change status: the contrast-cell absolute-error
change U−B flips sign (+0.144 → −0.442 pp, CI straddles zero in both)
and the Stage 9 disclosure × manipulation-location interaction on
absolute error loses its borderline significance (CrI −0.194–0.005 →
−0.171–0.032). Neither was a headline finding.

## 5. Why can't it happen again?
Three safeguards now in place: (1) a single canonical dataset
(`stage10_data_reconciliation/data/`, version tag `reconciled_v1`)
rebuilt from hash-verified records, with `OLD_VS_CORRECTED_EFFECTS.csv`
auditing every cell; (2) a raw-records manifest
(`RAW_RECORD_MANIFEST.json` + `VALIDATION_REPORT.md`) that pins each
cell to the record state it was computed from; (3) a fail-fast loader
— every corrected stage script asserts row counts, coverage
(C-13/C-14 = 11 pairs, C-32 = 10, C-33 = 11) and source_version before
any analysis runs, so a stale or partial mirror raises an error
instead of silently producing numbers.

*All corrected outputs live under `stage10_data_reconciliation/
corrected_results/` and `corrected_figures/`. Frozen stage outputs and
canonical data files were never modified. No causal language, no new
headlines, no manuscript edits.*
