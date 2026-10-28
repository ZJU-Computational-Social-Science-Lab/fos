# Stage 9 explanatory regression results

Two theory-informed multilevel Bayesian regressions explain (not predict) the AI-human discrepancy across 553 paired model-contrast observations (15 models x 38 contrasts minus exclusions, 1106 blinded/disclosed rows).

## Reference categories and units

- response_format reference: rating_mean (verified modal, 540/1106 rows). The spec suggested binary_choice as reference but required verifying modality first; binary_choice was NOT modal, so rating_mean is used (documented deviation).
- self_other reference: self (31/38 contrasts).
- Continuous predictors are standardized; interpretable deltas: +100 words, +0.10 wording difference, 0->1 manipulation location, +1 response option, +0.5 SD human effect size, doubling of model SE.
- Model A outcome: absolute error in human-SD units (Gamma log-link); translated estimates are percent changes. Model B outcome: same-direction agreement on the 32 confident contrasts (934 rows, logistic); translated estimates are percentage-point changes in direction-correct probability.

## Model A — absolute error

| Predictor | Contrast | Post. mean | 95% CrI | P(positive) | Interpretable estimate |
|---|---|---|---|---|---|
| gain_loss_framing | present vs absent | 0.235 | [-0.304, 0.765] | 0.812 | 31.2 % chg in absolute error |
| numerical_manipulation | present vs absent | -0.336 | [-0.795, 0.123] | 0.080 | -26.5 % chg in absolute error |
| explicit_probability | present vs absent | 0.056 | [-0.416, 0.525] | 0.590 | 8.8 % chg in absolute error |
| negation_change | present vs absent | 0.479 | [-0.118, 1.037] | 0.945 | 68.5 % chg in absolute error |
| role_change | present vs absent | -0.289 | [-0.876, 0.305] | 0.157 | -21.7 % chg in absolute error |
| question_order | present vs absent | -0.066 | [-0.656, 0.531] | 0.418 | -2.0 % chg in absolute error |
| response_options_change | present vs absent | 0.209 | [-0.436, 0.862] | 0.740 | 30.1 % chg in absolute error |
| question_length | +100 words | -0.130 | [-0.399, 0.150] | 0.175 | -18.1 % chg in absolute error |
| wording_difference | +0.10 wording difference (10pp) | -0.039 | [-0.263, 0.191] | 0.353 | -1.1 % chg in absolute error |
| manipulation_location | 0 -> 1 manipulation location | 0.016 | [-0.242, 0.276] | 0.543 | 26.8 % chg in absolute error |
| n_response_options | +1 response option | -0.139 | [-0.413, 0.145] | 0.160 | -3.9 % chg in absolute error |
| human_abs_d_std | +0.5 SD human effect size | 0.429 | [0.217, 0.627] | 1.000 | 61.3 % chg in absolute error |
| log_se_y_std | model SE doubled (log 2) | 0.090 | [0.020, 0.158] | 0.994 | 2.7 % chg in absolute error |
| fmt_binary_choice | present vs absent | -0.124 | [-0.686, 0.472] | 0.330 | -7.7 % chg in absolute error |
| fmt_bracket_mean | present vs absent | 0.293 | [-0.419, 0.959] | 0.801 | 42.5 % chg in absolute error |
| fmt_numeric_estimate | present vs absent | -0.334 | [-0.932, 0.271] | 0.137 | -24.9 % chg in absolute error |
| fmt_numeric_open | present vs absent | 0.243 | [-0.545, 1.034] | 0.728 | 38.0 % chg in absolute error |
| fmt_share | present vs absent | 0.053 | [-0.437, 0.550] | 0.584 | 8.8 % chg in absolute error |
| selfother_mixed_or_third_party | present vs absent | 0.277 | [-0.551, 1.072] | 0.753 | 43.6 % chg in absolute error |
| selfother_other | present vs absent | -0.133 | [-0.695, 0.430] | 0.316 | -8.8 % chg in absolute error |
| manipulation_location_na | imputed (missing) vs observed | 0.224 | [-0.613, 1.054] | 0.701 | 37.0 % chg in absolute error |
| n_response_options_na | imputed (missing) vs observed | 0.163 | [-0.559, 0.878] | 0.669 | 25.8 % chg in absolute error |
| disclosure | disclosed vs blinded | -0.076 | [-0.179, 0.028] | 0.074 | -7.2 % chg in absolute error |
| disclosure_x_role_change | interaction: disclosure x role change | 0.029 | [-0.307, 0.369] | 0.566 | 4.4 % chg in absolute error |
| disclosure_x_manipulation_location | interaction: disclosure x manipulation location | -0.094 | [-0.194, 0.005] | 0.031 | -8.9 % chg in absolute error |

## Model B — direction agreement

| Predictor | Contrast | Post. mean | 95% CrI | P(positive) | Interpretable estimate |
|---|---|---|---|---|---|
| gain_loss_framing | present vs absent | -0.417 | [-1.221, 0.375] | 0.154 | -7.7 percentage points |
| numerical_manipulation | present vs absent | 0.088 | [-0.636, 0.812] | 0.590 | 0.6 percentage points |
| explicit_probability | present vs absent | -0.128 | [-0.880, 0.632] | 0.372 | -2.7 percentage points |
| negation_change | present vs absent | -0.332 | [-1.163, 0.531] | 0.224 | -6.3 percentage points |
| role_change | present vs absent | -0.564 | [-1.419, 0.288] | 0.099 | -10.6 percentage points |
| question_order | present vs absent | 0.025 | [-0.899, 0.966] | 0.519 | -0.6 percentage points |
| response_options_change | present vs absent | 0.084 | [-0.785, 0.959] | 0.574 | 0.4 percentage points |
| question_length | +100 words | -0.364 | [-0.971, 0.266] | 0.121 | -12.7 percentage points |
| wording_difference | +0.10 wording difference (10pp) | -0.436 | [-1.057, 0.191] | 0.086 | -2.0 percentage points |
| manipulation_location | 0 -> 1 manipulation location | 0.108 | [-0.435, 0.657] | 0.648 | 0.8 percentage points |
| n_response_options | +1 response option | 0.303 | [-0.270, 0.890] | 0.844 | 1.2 percentage points |
| human_abs_d_std | +0.5 SD human effect size | 0.508 | [0.025, 0.987] | 0.980 | 6.5 percentage points |
| log_se_y_std | model SE doubled (log 2) | 0.197 | [-0.031, 0.435] | 0.953 | 0.8 percentage points |
| fmt_binary_choice | present vs absent | -0.019 | [-0.837, 0.813] | 0.482 | -1.1 percentage points |
| fmt_bracket_mean | present vs absent | -0.092 | [-1.003, 0.818] | 0.416 | -2.3 percentage points |
| fmt_numeric_estimate | present vs absent | -0.083 | [-0.953, 0.796] | 0.430 | -2.1 percentage points |
| fmt_numeric_open | present vs absent | -0.154 | [-1.072, 0.761] | 0.367 | -3.4 percentage points |
| fmt_share | present vs absent | 0.503 | [-0.337, 1.313] | 0.886 | 5.6 percentage points |
| selfother_mixed_or_third_party | present vs absent | -0.001 | [-0.999, 0.980] | 0.501 | -1.1 percentage points |
| selfother_other | present vs absent | 0.501 | [-0.326, 1.331] | 0.877 | 5.5 percentage points |
| manipulation_location_na | imputed (missing) vs observed | 0.003 | [-0.988, 0.951] | 0.506 | -1.0 percentage points |
| n_response_options_na | imputed (missing) vs observed | -0.126 | [-1.027, 0.774] | 0.388 | -2.9 percentage points |
| disclosure | disclosed vs blinded | -0.110 | [-0.453, 0.234] | 0.268 | -1.8 percentage points |
| disclosure_x_role_change | interaction: disclosure x role change | -0.172 | [-0.852, 0.527] | 0.311 | -3.2 percentage points |
| disclosure_x_manipulation_location | interaction: disclosure x manipulation location | -0.276 | [-0.630, 0.073] | 0.065 | -4.6 percentage points |

Note: translated estimates for Model B are average marginal effects — the average change in direction-correct probability across the posterior — and can carry the opposite sign to the mean logit coefficient because the logistic curve's saturation weights large-negative draws more. Example: question_order (+0.025 logit, -0.6 pp). This is a property of the nonlinear link, not a sign error.

## Equal-weight-per-experiment headline summary

Averaging each feature's effect within experiments first (equal weight per experiment) gives the same qualitative ordering as the row-weighted estimates; largest Model A effects (exp-averaged):
- negation_change (present vs absent): 0.685 [-0.112, 1.820]
- human_abs_d_std (+0.5 SD human effect size): 0.613 [0.270, 0.991]
- manipulation_location_na (imputed (missing) vs observed): 0.370 [-0.458, 1.870]
- gain_loss_framing (present vs absent): 0.312 [-0.262, 1.149]
- response_options_change (present vs absent): 0.301 [-0.353, 1.368]
- manipulation_location (0 -> 1 manipulation location): 0.268 [-0.657, 2.382]
- numerical_manipulation (present vs absent): -0.265 [-0.548, 0.131]
- n_response_options_na (imputed (missing) vs observed): 0.258 [-0.428, 1.405]

## Credible vs null (95% CrI excludes / includes 0) — nulls reported, no selection

- Model A: human_abs_d_std (+; larger human effects -> larger AI error) and log model SE (+; noisier model estimates sit further from humans) are credible. Disclosure alone is a small negative (noise-reduction) trend not reaching credibility; neither interaction is credible.
- Model B: see the table above; most feature effects on direction agreement are null with wide intervals on the 32-contrast subset — the design has limited power for direction agreement, and that limit is itself a finding.
- Conditionality: explicit_probability vs numerical_manipulation overlap (26/38); each coefficient is the effect holding the other fixed. The three sparse features (role_change, question_order, response_options_change) are weakly identified; their intervals mostly reflect prior shrinkage, not evidence of no effect.

## Known caveats

- 145 of 530 original cells carry the documented run10 stale-lineage caveat (frozen d_m not reproducible from hash-frozen records). Stage 5 y_std inherits them; results are conditional on the frozen values. Sensitivity B (Qwen exclusion) overlaps heavily with the affected models.
- Bootstrap SEs capture persona resampling only (one seed, one draw per persona).
- No p-values are used anywhere; all uncertainty statements are 95% credible intervals and posterior probabilities of sign.
