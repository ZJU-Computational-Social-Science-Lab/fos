# Stage 11 Task A — compression + noise analysis (technical)

Question: can LLM directional errors be explained by proportional underestimation of human effects plus ordinary noise, or is extra contrast-level structure needed? All numbers below come from `analysis/compression_results.csv`, `analysis/compression_diagnostics.md`, and `analysis/run_log.txt`; nothing was refit for this write-up.

## Inputs (exact versions)
- `CANONICAL_MODEL_EFFECTS.csv`, `CANONICAL_PAIRED_ANALYSIS.csv`, `MODEL_EFFECT_UNCERTAINTY_CORRECTED.csv` — Stage 10 **reconciled_v1** (registry-approved, manifest-verified via `stage10_data_reconciliation/scripts/canonical_data.py`; run log records all 4 manifest hashes matching).
- Analysed cells: **1119** contrast × model × blinding rows (560 blinded, 559 disclosed); 38 contrasts; **553 paired cells** used for the signed-convention join. Signed standardized treatment-minus-control effects; the sign convention was verified by joining against the paired table (max deviation 0.00e+00).
- Human-direction confident: 32 contrasts (Pr rule, Stage 6 threshold 0.975, corrected SEs); uncertain: C-17, C-27, C-28, C-33, C-34, C-36 (175 cells, reported separately, excluded from classification).

## A1 — compression fits (with-intercept and zero-intercept)
Model: `y = alpha + beta_m*Human + experiment RE + model RE + Normal(0, sigma)`; non-centered parameterization; HalfNormal(0.5) group SDs; NumPyro NUTS, 4 chains, 800 warmup + 800 samples, target_accept 0.90, seed 20261029 (+fit-specific offsets).

| Condition | β [95% CrI] | α [95% CrI] | σ [95% CrI] |
|---|---|---|---|
| Blinded (intercept) | 0.525 [0.269, 0.775] | 0.018 [−0.194, 0.219] | 0.666 [0.626, 0.708] |
| Blinded (zero-intercept) | 0.530 [0.284, 0.776] | — | 0.667 [0.629, 0.709] |
| Disclosed (intercept) | 0.561 [0.296, 0.810] | 0.045 [−0.172, 0.263] | 0.692 [0.649, 0.737] |
| Disclosed (zero-intercept) | 0.578 [0.322, 0.816] | — | 0.694 [0.656, 0.736] |

- P(β > 0) = 1.000 both conditions; P(β < 1) = 1.000 blinded, 0.999 disclosed.
- P(|α| < 0.05) = 0.356 (blinded), 0.336 (disclosed) — intercepts not distinguishable from 0.
- Dropping the intercept shifts β by 0.006 (blinded) / 0.017 (disclosed) — immaterial.
- Model-specific β (blinded) range 0.210 [−0.125, 0.547] (gemma-4-12b-it-qat) to 1.119 [0.727, 1.494] (gemma-4-31b-it-qat); (disclosed) range 0.115 [−0.255, 0.469] (qwen3.6-35b-a3b) to 1.017 [0.651, 1.405] (gemma-4-31b-it-qat). Full per-model table in the CSV.

**Sign-preservation check (synthetic):** pure proportional compression β·Human never flips sign (4 β values, 10,000 draws each, 0 flips); with unit noise added, flips occur as expected (4,094/40,000 draws) — sign reversal requires intercept/noise, not β alone.

## A2 — direction accuracy vs |human effect|
Primary analysis on the 32 confident contrasts (944 confident cells); quartiles of |h|, experiment-clustered uncertainty.

| Group | Accuracy [95% CrI] | n cells |
|---|---|---|
| Q1 (smallest \|h\|) | 0.551 [0.389, 0.729] | 234 |
| Q2 | 0.767 [0.643, 0.878] | 240 |
| Q3 | 0.787 [0.650, 0.948] | 240 |
| Q4 (largest \|h\|) | 0.861 [0.705, 0.953] | 230 |
| Overall confident | 0.742 [0.667, 0.822] | 944 |
| Uncertain contrasts (separate) | 0.469 | 175 |

## A3 — null benchmark and posterior-predictive test
Null model: `AI = beta*Human + epsilon`, symmetric zero-centered Gaussian noise, separate β/σ per blinding condition, model-level nuisance variation allowed, **no** contrast-level directional adjustments. Posterior-predictive simulation: 1000 draws preserving the real human effects, structure, blinding, and model nuisance; shared human-benchmark draws per contrast where propagated.

Observed vs simulated 95% intervals:

| Statistic | Observed | Simulated [95%] |
|---|---|---|
| Accuracy, blinded | 0.751 | [0.603, 0.698] (observed above) |
| Accuracy, disclosed | 0.732 | [0.635, 0.722] (observed at/above upper edge) |
| Quartile Q1 accuracy | 0.551 | [0.483, 0.607] (inside) |
| Quartile Q2 accuracy | 0.767 | [0.533, 0.658] (observed above) |
| Quartile Q3 accuracy | 0.787 | [0.629, 0.754] (observed above) |
| Quartile Q4 accuracy | 0.861 | [0.778, 0.883] (inside) |
| Majority-wrong contrast-legs (of 64) | 11 | [5, 16] (inside) |
| Heavily reversed contrasts | 2 | [0, 1] (just above) |
| Shared failures, above-median \|h\| (median 0.484) | 3 | [0, 4] (inside) |
| Contrasts with k wrong models (k = 0…15) | see CSV | full distribution in `A3,PPC_count_contrasts_with_k_wrong` rows |

**Analytic check:** per-cell P(wrong) = Φ(−β·|h|/σ) recorded per row in the analytic table; simulation matches the analytic computation within Monte Carlo error.

**Comparison model (one shared contrast-level residual):** sd_contrast = 0.477 [0.375, 0.617] (variance ≈ 0.227); extra contrast-level variance share ≈ 0.235 of total (extra + mean null residual). A non-zero shared contrast residual is clearly present — real contrast-level structure beyond per-cell noise.

## A4 — verdict
See `EXECUTIVE_SUMMARY.md` (plain-English answers to the 5 questions with intervals, per the A4 interpretation rules).

Figures: deferred to the Stage 11 Task B figures worker (stub noted here per coordination rule).

## Limitations
- The noise-only benchmark assumes independence across models given the shared human effect; the non-zero shared contrast residual (A3) shows this assumption is violated to a modest degree (~23% extra variance), so null-interval comparisons should be read as approximate.
- Shared human-benchmark draws propagate human-effect uncertainty, but the human benchmark itself carries estimation uncertainty not fully capturable in the simulation.
- Quartile boundaries are data-defined (no arbitrary cutoffs, but quartile assignment inherits |h| estimation error).
- 6 uncertain contrasts (175 cells) are excluded from classification and reported separately (accuracy 0.469, near chance).
- Exploratory analysis; single comparison model (shared contrast residual) chosen per the spec — no broader model collection, no selection on interestingness.
