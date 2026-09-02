# Comparison of 11-20 Game Variants Across Three API Models

**Date:** 2026-09-01

**Title:** Payoff-flip and range-shift sensitivity of LLM play in the "ask for an amount" game

## Methodology

Three versions of a two-player "ask for an amount" game were played by the same 20 personas
(first 20 of `final_200_personas.csv`) on 3 API models, under prompt condition 0
("orig": full persona embedding + game text with reason instruction + amount-only JSON output):

1. **11-20 baseline** (existing data, `results/all_conditions_3x3.csv`, `condition=cond0` rows):
   each player requests a number in 11-20 and receives what they request;
   +20 bonus for requesting exactly one shekel LESS than the opponent.
2. **31-40 variant** (new data): same game re-ranged to 31-40
   (receive what you request; +20 bonus for exactly one shekel LESS than the opponent).
3. **Inverted 11-20** (new data): range 11-20; each player receives 31 − request;
   +20 bonus for requesting exactly one shekel MORE than the opponent.

Models: `deepseek-v4-flash`, `anthropic/claude-sonnet-5`, `openai/gpt-5.6-luna`.
Sample: n=20 per model-cell (one shot per persona, temperature 0).
Total: 120 new decisions (3 models × 2 variants × 20) + 60 baseline decisions (3 models × 20).
New data files (20 rows each, 0 errors): `*_cond0_31-40.csv/.jsonl` and `*_cond0_inverted.csv/.jsonl`.

## Per-Model Distributions

### deepseek-v4-flash

| Game | Distribution (chosen → count) | Mean | Mode |
|---|---|---|---|
| 11-20 baseline | {18: 2, 19: 16, 20: 2} | 19.0 | 19 |
| 31-40 | {36: 1, 39: 17, 40: 2} | 39.0 | 39 |
| Inverted 11-20 | {11: 5, 12: 14, 16: 1} | 11.9 | 12 |

### anthropic/claude-sonnet-5

| Game | Distribution (chosen → count) | Mean | Mode |
|---|---|---|---|
| 11-20 baseline | {17: 17, 19: 3} | 17.3 | 17 |
| 31-40 | {39: 20} | 39.0 | 39 |
| Inverted 11-20 | {17: 16, 19: 4} | 17.4 | 17 |

### openai/gpt-5.6-luna

| Game | Distribution (chosen → count) | Mean | Mode |
|---|---|---|---|
| 11-20 baseline | {15: 1, 19: 17, 20: 2} | 18.9 | 19 |
| 31-40 | {31: 2, 39: 18} | 38.2 | 39 |
| Inverted 11-20 | {11: 2, 12: 7, 15: 1, 19: 1, 20: 9} | 16.0 | 20 |

## Full 3×3 Summary (mode (mean))

| Model | 11-20 baseline | 31-40 | Inverted 11-20 |
|---|---|---|---|
| deepseek-v4-flash | 19 (19.0) | 39 (39.0) | 12 (11.9) |
| anthropic/claude-sonnet-5 | 17 (17.3) | 39 (39.0) | 17 (17.4) |
| openai/gpt-5.6-luna | 19 (18.9) | 39 (38.2) | 20 (16.0) |

## Observations

- **31-40 behaves like a pure translation upward.** All three models concentrate at
  39 (= range max − 1, the highest bonus-eligible pick). Baseline behavior in 11-20 was
  already anchored near the top (modes 19/19/17); under the range shift the anchor moves
  to 39, with the mode at 39 for all 3 models.
- **deepseek is the cleanest mirror under the axis flip x → 31−x.** Baseline mode 19 →
  inverted mode 12 (= 31−19). Its inverted cluster {11: 5, 12: 14} approximately mirrors
  its baseline cluster {18: 2, 19: 16, 20: 2}.
- **luna partially mirrors but also exploits the inverted bonus aggressively.**
  12×7 ↔ baseline 19×17 and 11×2 ↔ baseline 20×2 mirror approximately, but luna also
  plays the inverted bonus at 20 (9 picks = beats 19), making its inverted distribution
  bimodal (modes 12 and 20).
- **claude does NOT mirror.** It anchors at 17 in both 11-20 and inverted 11-20
  (16 of 20 same number), i.e. insensitive to the payoff flip; only the range shift to
  31-40 moves it (to 39, unanimously).
- **Bonus-seeking direction flips as designed.** Original-game bonus chases are
  x = y−1 (19 beats 20); inverted-game bonus chases are x = y+1 (20 beats 19, 12 beats 11)
  — visible in the clusters above.

## Caveats

- n=20 per model-cell; single shot per persona (no repeated play); temperature 0.
- Only condition 0 ("orig" prompt) is covered.
- Reasoning is captured in the `.jsonl` files; deepseek mean reasoning tokens ≈ 12-16k
  (12.2k for 31-40, 15.7k for inverted); claude/luna expose little or no reasoning token data.
