# CHARACTERISTICS_CROSSTABS.md — Stage 8 Phase 1, Part 2

Descriptive only. The characteristics were coded from the raw
experimental instructions BEFORE any accuracy number was joined
(ordering evidence: 20_experiment_characteristics.py writes
EXPERIMENT_CHARACTERISTICS.csv; this script runs second and is the
only place where coding meets accuracy). Unit = one contrast
(38 contrasts over 31 experiments). 'majority_wrong' = majority of
paired models point against the confident human direction in at
least one blinding leg (7 contrasts). 'uncertain_human' = human
direction not confident (6 contrasts, kept but never classified).

## Outcome by judgment_type
| category | agreement_or_mixed | majority_wrong | uncertain_human | n_contrasts |
|---|---|---|---|---|
| social | 6 | 3 | 0 | 9 |
| valuation | 2 | 2 | 0 | 4 |
| risk | 5 | 1 | 2 | 8 |
| decision | 9 | 1 | 1 | 11 |
| belief | 1 | 0 | 2 | 3 |
| attribution | 2 | 0 | 1 | 3 |

## Outcome by response_format
| category | agreement_or_mixed | majority_wrong | uncertain_human | n_contrasts |
|---|---|---|---|---|
| rating_scale | 12 | 5 | 2 | 19 |
| binary_choice | 5 | 1 | 1 | 7 |
| numeric_estimate | 7 | 1 | 2 | 10 |
| probability_judgment | 1 | 0 | 1 | 2 |

## Outcome by task_nature flag (contrast counts)

### flag_emotional_reactions
| category | agreement_or_mixed | majority_wrong | uncertain_human | n_contrasts |
|---|---|---|---|---|
| present | 4 | 4 | 1 | 9 |
| absent | 21 | 3 | 5 | 29 |

### flag_incentives_at_stake
| category | agreement_or_mixed | majority_wrong | uncertain_human | n_contrasts |
|---|---|---|---|---|
| present | 11 | 4 | 2 | 17 |
| absent | 14 | 3 | 4 | 21 |

### flag_social_expectations
| category | agreement_or_mixed | majority_wrong | uncertain_human | n_contrasts |
|---|---|---|---|---|
| absent | 19 | 4 | 5 | 28 |
| present | 6 | 3 | 1 | 10 |

### flag_uncertainty_prominent
| category | agreement_or_mixed | majority_wrong | uncertain_human | n_contrasts |
|---|---|---|---|---|
| present | 17 | 6 | 4 | 27 |
| absent | 8 | 1 | 2 | 11 |

### flag_scenario_interpretation
| category | agreement_or_mixed | majority_wrong | uncertain_human | n_contrasts |
|---|---|---|---|---|
| absent | 14 | 5 | 2 | 21 |
| present | 11 | 2 | 4 | 17 |

## Outcome by human effect size (|d| quartiles, confident contrasts only)

| category | agreement_or_mixed | majority_wrong | uncertain_human | n_contrasts |
|---|---|---|---|---|
| small (<=0.2) | 3 | 3 | 0 | 6 |
| 0.2-0.5 | 9 | 2 | 0 | 11 |
| 0.5-1.0 | 9 | 1 | 0 | 10 |
| large (>1.0) | 4 | 1 | 0 | 5 |

## Majority-wrong contrasts: magnitude of the error

| contrast | human \|d\| | blinded mean \|wrong d\| | ratio (pattern) | disclosed mean \|wrong d\| | ratio (pattern) |
|---|---|---|---|---|---|
| C-03 less_is_more | 0.63 | 0.66 | 1.05x (reversal) | 0.52 | 0.83x (intermediate) |
| C-09 wta_wtp | 1.42 | 0.52 | 0.36x (near_zero) | 0.39 | 0.28x (near_zero) |
| C-16 myside | 0.26 | 0.11 | 0.44x (near_zero) | 0.29 | 1.14x (reversal) |
| C-26 T2KX-ml2_risen_tempt_fate | 0.18 | 0.35 | 1.96x (reversal) | 0.79 | 4.36x (reversal) |
| C-30 T2KX-ml2_rottenstreich_affect | 0.07 | 0.34 | 4.65x (reversal) | 0.50 | 6.99x (reversal) |
| C-31 T2KX-ml2_bauer_materialism | 0.12 | 0.10 | 0.80x (intermediate) | 0.09 | 0.74x (intermediate) |
| C-37 T2KX-reedBR32 | 0.24 | 1.02 | 4.25x (reversal) | 0.85 | 3.54x (reversal) |

Reading: a ratio well below 1 means wrong-sign predictions
cluster near zero (models shrink the effect), NOT that they
reverse it. C-26, C-30 and C-37 are the only clear
reversals (2-7x the human effect); C-09's wrong predictions
average ~0.3x the human d — massive shrinkage, not
inversion.
