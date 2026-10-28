# Feature descriptives (pre-regression, outcome-free)

## response_format (categorical)
- binary_choice: 8/38 (21%)
- numerical_estimate: 9/38 (24%)
- probability_judgment: 2/38 (5%)
- rating: 19/38 (50%)

## self_other (categorical)
- mixed_or_third_party: 1/38 (3%)
- other: 6/38 (16%)
- self: 31/38 (82%)

## Binary features (1 = present, of 38 contrasts)

| feature | 1s | 0s |
|---|---|---|
| role_change | 3 | 35 |
| gain_loss_framing | 6 | 32 |
| numerical_manipulation | 18 | 20 |
| explicit_probability | 10 | 28 |
| negation_change | 4 | 34 |
| question_order | 3 | 35 |
| response_options_change | 3 | 35 |

## Continuous features

| feature | mean | median | min | max | sd | NaN |
|---|---|---|---|---|---|---|
| question_length | 97.80 | 91.75 | 15.00 | 245.00 | 55.75 | 0 |
| wording_difference | 0.31 | 0.14 | 0.01 | 1.59 | 0.34 | 0 |
| manipulation_location | 0.28 | 0.25 | 0.00 | 0.84 | 0.23 | 0 |
| n_response_options | 6.74 | 6.00 | 2.00 | 15.00 | 3.53 | 0 |

## Zero-variance / near-zero-variance flags

- role_change: near-zero variance (3/38)
- question_order: near-zero variance (3/38)
- response_options_change: near-zero variance (3/38)

## Binary predictor overlap (Yule-style co-occurrence, counts of contrasts where both = 1)

| pair | both=1 |
|---|---|
| role_change x explicit_probability | 1 |
| gain_loss_framing x numerical_manipulation | 2 |
| gain_loss_framing x explicit_probability | 3 |
| gain_loss_framing x negation_change | 2 |
| numerical_manipulation x explicit_probability | 8 |
| numerical_manipulation x negation_change | 1 |
| numerical_manipulation x response_options_change | 3 |
| explicit_probability x negation_change | 1 |
| explicit_probability x response_options_change | 1 |

## Within- vs between-experiment variation

- T2KX-budescu779 (2 contrasts): no variation in manual features; wording_difference range 0.237-0.244
- T2KX-howard823 (2 contrasts): no variation in manual features; wording_difference range 0.622-0.622
- T2KX-reedBR32 (2 contrasts): no variation in manual features; wording_difference range 0.135-0.135
- fire_extinguisher (2 contrasts): no variation in manual features; wording_difference range 0.023-0.023
- less_is_more (2 contrasts): no variation in manual features; wording_difference range 0.093-0.093
- seatbelt (2 contrasts): no variation in manual features; wording_difference range 0.017-0.017
- wta_wtp (2 contrasts): varies within experiment: role_change, numerical_manipulation; wording_difference range 0.184-0.889

## Missingness

- manipulation_location: 1 NaN (all pure question-order cases; na-flagged)
- n_response_options: 3 NaN (free numeric entry / open estimate elicitation)

No outcome data (human effects, model effects, y_std, accuracy) was read or joined in this file.
