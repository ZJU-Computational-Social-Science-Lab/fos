# Draft interpretation — Stage 9 explanatory regressions

## What these regressions establish
Stage 9 asks which observable properties of the adapted experimental manipulations
co-vary with how far AI model responses land from the human benchmark, and with
whether AI points in the same direction. Because features were coded blind to
outcomes and entered as theory-motivated multilevel regressions, the credible
associations are evidence of covariation under the model's assumptions — not
predictions (no train/test split is used or needed) and not causal effects.

Three things are credibly established. First, AI error is larger where the human
effect is larger: the models are not uniformly wrong, they are most wrong exactly
where humans showed strong effects, which is the regime where replication matters
most. Second, part of measured "AI discrepancy" is mechanical: cells with larger
bootstrap SEs (sampling noise in the AI responses) show larger absolute error.
Third, disclosure alone does not credibly change either outcome in this regression,
mirroring Stage 6's paired result.

## Supported, ambiguous, and unsupported hypotheses
- Supported: error grows with human effect size and with model-cell noise.
- Ambiguous: negation changes (largest point association, not credible);
  numerical-manipulation vs explicit-probability wording (68% overlap makes them
  jointly unidentifiable at this sample size); sparse features (role change,
  question order, response-option change; 3/38 contrasts each).
- Null here (with limited power on the 32-contrast direction subset): most coded
  features do not credibly explain direction agreement.

## What the data cannot say about mechanisms
The design cannot separate why a feature associates with error: a negation change
may matter because models misread negation, or because such experiments happen to
be harder for other reasons. Random effects absorb, but do not explain, the large
model-by-contrast heterogeneity — the dominant source of variation. The run10
stale-lineage caveat means 145 cells carry frozen values that do not reproduce from
records; results are conditional on those frozen values. Bootstrap SEs capture
persona resampling only (single seed, one draw per persona). Finally, the
32-confident-contrast direction analysis has narrow informational content: absence
of credible feature effects there is a statement about information, not about truth.

## Illustrations, not confirmations
The experiment sketches in EXPERIMENT_EXAMPLES.md were selected after fitting and
are descriptive illustrations of the fitted associations; they are not independent
confirmation and should not be cited as such.
