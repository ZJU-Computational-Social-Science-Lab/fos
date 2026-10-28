# SCIENTIFIC_RESULTS_BEFORE_AFTER.md — Stage 10 corrected rerun vs frozen

All "corrected" numbers come from the completed Stage 10 reruns on the
canonical `reconciled_v1` data (stages 3/5/6 done in TASK-3014; stages
7/8/9 in TASK-3019). Identical specifications, priors and seeds; only
the input effects/SEs differ. CIs are the same interval types as the
frozen analyses (family-cluster bootstrap for Stage 3, 95% credible
intervals for the Bayesian fits). 1119 canonical cells = 974 verified
exact + 139 corrected (all run10 original-14 cells, 13 with direction
flips) + 6 new-only anchoring cells (excluded from the paired 553 to
keep like-for-like comparability).

## Side-by-side results

| # | result | previous (frozen) estimate + interval | corrected estimate + interval | difference | interpretation changed? |
|---|---|---|---|---|---|
| 1 | Recovery slope, blinded (Stage 3 WLS; Stage 5 A2 posterior) | 0.4935; A2: 0.5192 (0.263, 0.787) | 0.4762 (CI 0.302–0.648); A2: 0.5089 (0.263, 0.787) | −0.017 / −0.010 | No — models recover roughly half the human effect blinded |
| 2 | Recovery slope, disclosed | 0.8978; A2: 0.6630 (frozen CrI similar width) | 0.8842 (CI 0.568–1.041); A2: 0.6469 (0.390, 0.917) | −0.014 / −0.016 | No |
| 3 | Disclosure slope difference (disclosed − blinded) | 0.4043 | 0.4080 (CI 0.059–0.592); A2: 0.1380 (0.009, 0.267) | +0.004 | No — disclosure still improves recovery, barely excluding 0 |
| 4 | Mean absolute effect error, blinded (contrast-cell, pp) | 21.113 | 20.861 (CI 12.112–28.715) | −0.25 pp | No |
| 5 | Mean absolute effect error, disclosed (pp) | 21.257 | 20.419 (CI 12.621–27.384) | −0.84 pp | No |
| 6 | Absolute-error change U−B (pp) | +0.144 (CI straddles 0) | **−0.442** (CI −1.663–1.326) | sign flip | **Yes, numerically** — disclosure now slightly REDUCES contrast-cell error; neither version significant. Any claim that disclosure increases error must be dropped |
| 7 | Pooled direction agreement, blinded (467 confident pairs) | 349/467 = 0.747 | 350/467 = 0.749 | +0.002 | No |
| 8 | Pooled direction agreement, disclosed | 339/467 = 0.726 | 341/467 = 0.730 | +0.004 | No |
| 9 | Majority-wrong contrasts (confident human direction) | 7: C-03 (disclosed), C-09/C-26/C-30/C-37 (both), C-16/C-31 (blinded) | identical set and classes | 0 | No — all seven explicitly revisited and confirmed |
| 10 | Shared-model blinded co-error overlap (105 model pairs) | mean 3.18 co-wrong, Jaccard 0.266; top pair gpt-oss-20b × granite-4.1-8b (8) | mean 3.30, Jaccard 0.278; top pair qwen3.6-35b-a3b × -uncensored (8) | small | No — models still share errors; lineage-related pairs dominate |
| 11 | Shared-failure regression, beta on z(\|d_h\|), blinded | −0.55 (89% HDI −1.00, −0.10) | −0.558 (−1.00, −0.10); LOMO all families beta<0, qwen-excluded −0.516 (was −0.418) | ~0 | No — larger human effects still protect; not family-driven |
| 12 | Stage 9 human effect size → absolute error (+0.5 SD) | +61.3% (log-coef 0.429, CrI 0.217–0.627) | +59.0% (0.416, CrI 0.209–0.617) | small | No — bigger human effects still mean bigger AI error |
| 13 | Stage 9 human effect size → direction-correct (+0.5 SD) | +6.5 pp (0.508, CrI 0.025–0.987) | +6.1 pp (0.482, CrI 0.003–0.965) | small | Borderline — still positive but now only barely excludes 0 |
| 14 | Stage 9 disclosure → absolute error | −7.2% (−0.076, CrI −0.179–0.028) | −7.9% (−0.083, CrI −0.187–0.020) | small | No — no detectable overall disclosure benefit |
| 15 | Stage 9 disclosure × manipulation-location (abs error) | −0.094 (CrI −0.194–0.005), p+ = 0.031 | −0.069 (CrI −0.171–0.032), p+ = 0.090 | CrI now includes 0 | **Yes** — this interaction was borderline-significant frozen, not significant corrected; drop it |
| 16 | Stage 6 accuracy improvement, blinded − disclosed (SD, equal-experiment) | +0.041 (−0.023, +0.105), pr>0 = 0.895 | identical procedure on corrected data: +0.041 (−0.023, +0.105) | ~0 | No |
| 17 | Wrong→right / right→wrong transitions under disclosure | 0.133 / 0.142, net −0.009 (−0.056, +0.035) | 0.130 / 0.137, net −0.007 (−0.058, +0.044) | small | No — disclosure causes no net direction change |

## Convergence of the corrected Bayesian refits
- Stage 5 A1/A2/A3: max R-hat 1.006, min bulk ESS 589–816 (A2
  prior-doubled sensitivity FAILED the gate and is documented as
  unstable, not substituted). PPC coverage 0.94 blinded / 0.94 disclosed.
- Stage 8 regression: max R-hat 1.0066, min bulk ESS 978, gates passed;
  all 7 leave-one-family-out refits converged.
- Stage 9 A: 0 divergences, max R-hat 1.0022, min ESS 3412, PPC ok.
  Stage 9 B: 3 divergences (sampler-level, same as frozen spec),
  max R-hat 1.0005, min ESS 4247, PPC ok.

## Bottom line
Every substantive headline survives the correction. Two numerical
claims change status: the contrast-cell absolute-error change U−B
flips from +0.14 pp to −0.44 pp (never significant either way), and
the Stage 9 disclosure × manipulation-location interaction on
absolute error loses its borderline significance. No direction
classification, no majority-wrong contrast, and no ranking changes.
