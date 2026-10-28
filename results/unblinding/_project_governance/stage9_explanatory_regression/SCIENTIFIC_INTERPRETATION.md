# Scientific interpretation — Stage 9 explanatory regressions

Analysis framing: exploratory, theory-informed, not preregistered. All statements
below are covariation claims conditional on the fitted models; no causal language is
intended or warranted. No p-values are used; uncertainty is expressed as 95%
credible intervals throughout.

## 1. What the regressions establish

Two multilevel Bayesian regressions model the AI-human discrepancy over 553
model-contrast pairs (1,106 blinded/disclosed rows; 15 models × 38 blind-coded
contrasts minus exclusions). Model A explains absolute error |AI − human| in
human-SD units (Gamma log-link); Model B explains direction agreement on the 32
confident contrasts (934 rows; logistic). Predictors are blind-coded features of the
adapted manipulations plus outcome-dependent controls (human effect size, model-cell
SE); groupings are experiment, contrast, pair, and model.

Two relationships are credibly non-zero (95% CrI excludes 0) and survive all
sensitivity checks (Sensitivities A–C):

- **human_abs_d_std** (Model A): +61.3% absolute error per +0.5 SD human effect
  [+27.0, +99.1]. AI error concentrates precisely where the human signal is strong —
  the regime of greatest substantive interest.
- **log_se_y_std** (Model A): +2.7% absolute error per doubling of the model-cell
  bootstrap SE [+0.6, +4.7]. A measurable fraction of the "discrepancy" is
  sampling noise in the AI arm rather than systematic divergence.

Between-experiment heterogeneity is the largest grouping effect in Model A
(posterior SD 0.41 log-units), rivaling the biggest fixed-effect association: which
experiment a contrast belongs to matters as much as any coded property. Leave-one-
experiment-out refits (Sensitivity C) show no single experiment drives the fixed
effects.

## 2. Which characteristics show associations

Ranked by the equal-weight-per-experiment (experiment-averaged) summary, Model A:

- negation_change: +0.685 SD-equivalent [−0.112, 1.820] — largest feature
  association, not credible.
- human_abs_d_std: +0.613 [0.270, 0.991] — credible.
- manipulation_location_na (imputed): +0.370 [−0.458, 1.870] — not credible;
  confounded with the C-36 missing cell.
- gain_loss_framing: +0.312 [−0.262, 1.149]; response_options_change: +0.301
  [−0.353, 1.368]; manipulation_location: +0.268 [−0.657, 2.382] — all null.
- numerical_manipulation: −0.265 [−0.548, 0.131] — suggestive of smaller error, not
  credible, and 26/38-overlapping with explicit_probability so the two are not
  separately identifiable.

In the pair-weighted main table the same ordering holds qualitatively (negation
+68.5% [−11.2, +182.0]; numerical manipulation −26.5% [−54.8, +13.1]). On Model B
(direction agreement), no feature reaches credibility; intervals are wide and the
32-contrast confident subset has limited power. Disclosure is null in both models
(A: −7.2% [−16.4, +2.9]; B: −1.8 pp [−7.9, +3.2]), as are both disclosure
interactions (disclosure_x_manipulation_location −8.9% [−19.4, +0.5] is the closest
to credible and is reported as null).

## 3. Which hypothesized explanations get support

- **Supported:** error scales with human effect size (larger human effects → larger
  AI misses) and with model-cell sampling noise (noisier AI estimates sit further
  from humans). Both are robust to human-benchmark redraws (Sensitivity A: key
  coefficients stable within narrow ranges), Qwen-family exclusion (Sensitivity B:
  disclosure −0.043, human_abs_d_std 0.468, same signs), and leave-one-out
  exclusions (Sensitivity C).
- **Ambiguous (suggestive but not credible):** negation changes; numerical
  manipulation (partially confounded with explicit probability); the imputed-
  location flag; the disclosure × manipulation-location interaction.
- **Unsupported / uninformative here:** question order, role change, and
  response-option change (3/38 contrasts each; intervals mostly reflect prior
  shrinkage, not evidence of absence); wording-difference magnitude; explicit
  probability wording alone; response-format and self/other dummies; and any
  feature effect on direction agreement.

The Stage 6 cross-check (Sensitivity D): Stage 9's experiment-averaged disclosure
effect −0.074 [−0.172, 0.026] and Stage 6's blinded-minus-disclosed accuracy +0.041
[−0.023, 0.105] differ in point-estimate sign (different outcomes and weightings)
but both intervals include 0 — statistically compatible. Neither stage supports a
clear disclosure effect.

## 4. Which relationships remain ambiguous

- The negation-change association is the largest single feature estimate but its
  interval spans zero widely (4/38 contrasts).
- numerical_manipulation vs explicit_probability: 26/38 overlap means each
  coefficient is only the effect *holding the other fixed*; neither can be read as
  "the effect of numeracy."
- Sparse features (role_change, question_order, response_options_change): intervals
  are prior-dominated. Genuine inconclusiveness, not confirmation of absence.
- Direction agreement overall: 73.7% of confident-contrast rows are
  direction-correct, but feature effects on this outcome are uniformly small with
  wide intervals; the design, not the features, sets the limit here.
- Whether disclosure interacts with manipulation type: the interaction point
  estimates are non-trivial but not credible.

## 5. What the dataset cannot say about causal mechanisms

The design is observational within the adaptation space: features were not
experimentally assigned to experiments, so any association may be confounded with
unmeasured properties of the underlying human experiments (exemplified by the large
between-experiment heterogeneity). The regressions cannot distinguish "models
misread negations" from "negation experiments are harder for other reasons." Random
effects absorb, but do not explain, model-by-contrast heterogeneity — the dominant
variance component in Model B (contrast SD 0.87). Bootstrap SEs capture persona
resampling only (one seed, one temperature-1.0 draw per persona), so seed-level and
temperature-level variability are not separately estimable. Finally, 145 of 530
original cells carry the run10 stale-lineage flag (frozen d_m values not
reproducible from hash-verified records); all results are conditional on those
frozen values, and Sensitivity B shows the main conclusions survive excluding the
most-affected model family.
