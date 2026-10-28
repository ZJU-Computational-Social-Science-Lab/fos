# Executive summary — Stage 11 Task A (compression + noise)

**Question:** can the LLMs' directional errors be explained by proportional underestimation of human effects (compression) plus ordinary noise, or is extra contrast-level structure needed?

**Scope:** Task A only (Task B figures add their own recommendation). All numbers are posterior means with 95% credible intervals from `analysis/compression_results.csv`, fitted on the Stage 10 **reconciled_v1** dataset (1,119 contrast × model × blinding cells; 38 contrasts, 32 human-direction-confident). This is an exploratory, descriptive analysis — no causal or psychological-mechanism claims are made.

## Q1. Can sign reversal happen at all under compression + noise?

No under pure compression, yes once an intercept or noise is allowed. A purely proportional model (AI = β·Human with β > 0) can never flip the direction of an effect; a synthetic check of this assertion passed (10,000 draws per β, zero flips). With an intercept, the predicted sign flips whenever β·|h| falls inside the intercept/noise band — so sign reversal is *mechanically possible* in the fitted model. This is a property of the model class, not a finding about the data.

## Q2. Do the LLMs compress human effects? Is there an intercept?

Yes, substantial compression, in both blinding conditions:

| Condition | β (with intercept) | β (zero-intercept) | α (intercept) |
|---|---|---|---|
| Blinded | 0.525 [0.269, 0.775] | 0.530 [0.284, 0.776] | 0.018 [−0.194, 0.219] |
| Disclosed | 0.561 [0.296, 0.810] | 0.578 [0.322, 0.816] | 0.045 [−0.172, 0.263] |

- **β > 0:** posterior probability 1.000 in both conditions — the LLM effects point in the same direction as the human effects overall.
- **β < 1:** posterior probability 1.000 (blinded) and 0.999 (disclosed) — roughly half-strength effects, i.e. compression is real.
- **Intercept material?** No. Both α intervals include 0 (P(|α| < 0.05) ≈ 0.36 blinded / 0.34 disclosed), and dropping the intercept shifts β by only 0.006 (blinded) / 0.017 (disclosed). The zero-intercept (pure-compression) specification fits essentially as well.

## Q3. Does compression + noise reproduce the small-effect accuracy decline?

Largely yes. Observed direction accuracy falls with smaller |human effect| (Q1 0.551 [0.389, 0.729] → Q4 0.861 [0.705, 0.953]; overall confident 0.742 [0.667, 0.822], n=944). Under the 1000-draw posterior-predictive simulation:

| Quartile | Observed | Simulated 95% interval |
|---|---|---|
| Q1 (smallest \|h\|) | 0.551 | [0.483, 0.607] ✓ inside |
| Q2 | 0.767 | [0.533, 0.658] ✗ observed above |
| Q3 | 0.787 | [0.629, 0.754] ✗ observed above |
| Q4 (largest \|h\|) | 0.861 | [0.778, 0.883] ✓ inside |

The small-effect decline (low Q1) is reproduced: observed Q1 sits inside the simulated interval, while Q4 accuracy is high in both. The one mismatch is that observed accuracy in the *middle* quartiles (Q2, Q3) is slightly **higher** than the noise-only benchmark predicts — the benchmark under-predicts mid-range accuracy (overall: blinded observed 0.751 vs simulated [0.603, 0.698]; disclosed 0.732 vs [0.635, 0.722]).

## Q4. Are shared failures (many models wrong on the same contrast) reproduced?

Mostly, but not entirely. Observed majority-wrong contrast-legs: **11 of 64**, simulated 95% interval **[5, 16]** — the count itself is reproduced. Shared failures on large-|h| contrasts: observed 3, simulated [0, 4] — inside. Heavily reversed contrasts: observed 2 vs simulated [0, 1] — just above the interval.

However, a comparison model adding one shared contrast-level residual estimates a clearly non-zero contrast SD: **0.477 [0.375, 0.617]** (extra variance share ≈ 0.235). That is, there **is** real contrast-level structure in the errors beyond what symmetric per-cell noise produces — but this analysis does not identify *what* that structure is, and it should not be read as a proven psychological mechanism. It is a residual pattern awaiting explanation.

## Q5. Are blinded and disclosed conditions consistent?

Yes. β: 0.525 [0.269, 0.775] blinded vs 0.561 [0.296, 0.810] disclosed — overlapping intervals, same conclusions (β > 0, β < 1, α ≈ 0). Residual SD 0.666 vs 0.692; direction accuracy 0.751 vs 0.732. Knowing the human result (disclosure) does not materially change the compression pattern.

## Overall verdict (per A4 interpretation rules)

Compression + symmetric noise is a **good first-order account** of the LLMs' directional behaviour: sign reversal is possible only via intercept/noise, effects are compressed to roughly half human strength with no material intercept, the small-effect accuracy decline and the majority-wrong counts fall inside (or at the edge of) the simulated intervals, and blinded/disclosed results agree. It is **not a complete account**: a shared contrast-level residual (SD 0.477, ~23% extra variance) is clearly present, meaning some contrasts are systematically harder or easier for many models in ways per-cell noise cannot produce. All findings are exploratory; no causal claims are made.
