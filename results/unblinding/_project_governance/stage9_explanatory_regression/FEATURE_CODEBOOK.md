# Feature codebook — Stage 9 experimental feature coding (EXPERIMENT_FEATURES.csv)

One row per contrast (38 rows), coded from the actual stimuli, blind to all
outcome data (no human-effect, model-effect, accuracy, direction, or y_std
file was opened during coding). Categorical/binary features were coded by an
analyst-agent in two passes (see CODING_RECONCILIATION.md); features 7–10
below were computed by `scripts/compute_text_features.py`; the final table is
assembled by `scripts/build_features.py`.

Arm texts live verbatim in `scripts/arm_texts_original.py` (C-01..C-18, from
6TASK/10TASK stimuli.json as quoted in stage8 SCENARIO_TEXT.md) and
`scripts/arm_texts_expansion.py` (C-19..C-38, from verbatim rendered prompts
in expansion/pipeline/sample_prompts/T2KX-*/). Convention: an "arm text" is
the item text plus its response options as the survey presented them,
including any arm-specific context (preceding questions, added reasoning
prompts, reference tables). Identical wrappers (system prompt, persona block,
"Answer with only the corresponding uppercase letter.") are excluded because
they cannot differ between arms. Control is the registered control_condition
arm; treatment the registered treatment_condition arm.

---

## 1. response_format (categorical)

**Definition:** how the outcome was elicited, read off the actual response
options: `binary_choice` (single A/B choice), `rating` (multi-point labeled
scale), `numerical_estimate` (free number or numeric bracket, incl. payment/
time/expense buckets), `probability_judgment` (0–100% probability scale).

**Motivation (survey methodology / JDM):** format shapes how a manipulation
is translated into a response (scale anchors, satisficing, numeric vs verbal
probability processing); format is the most basic moderator of effect
expressivity.

**Example:** C-01 = `rating` (6-point favor scale). C-34 = `probability_judgment`
(0–100% in 10-point steps).

**Reconciliation note:** C-17 (prob_matching) is a per-trial binary prediction
(columns '1'/'2', 'red'/'green'); stage8 recorded `numeric_estimate` because
the aggregated human outcome is a share, but the elicitation itself is binary,
and stage5 `n_options=2` agrees, so `binary_choice` is coded.

**Missing values:** none.

## 2. self_other (categorical)

**Definition:** who the respondent is instructed to evaluate or act as:
`self` (own preference/belief/action), `other` (evaluate or infer a third
party's action/attitude/trustworthiness), `mixed_or_third_party` (respondent
acts in an institutional role over third parties). Generic "you" in
instructions ("Would you drive...") does NOT make a judgment self-referential
beyond its target; the judgment target decides.

**Motivation (JDM / social cognition):** self-relevance changes affective
engagement, egocentric anchoring, and correspondence-bias strength.

**Example:** C-15 = `other` (evaluate the physician's decision); C-18 = `self`
(own drive decision); C-28 = `mixed_or_third_party` (respondent acts as juror
over third parties).

**Missing values:** none. Uncertainty: C-12 (`other`, statements about Linda),
C-25 (`other`, permissibility of Denise/Frank's act) are judgment calls, noted
in `coding_note`.

## 3. role_change (0/1)

**Definition:** 1 if the two arms explicitly assign the respondent DIFFERENT
roles, identities, or relationships (e.g., buyer vs seller). Re-description
without role change = 0.

**Motivation (framing / reference-point theory):** role assignment shifts the
reference transaction (WTA vs WTP) or the in-group whose side the respondent
is on.

**Coded 1:** C-09 (pay vs be paid), C-16 (in-group/out-group car ban flips),
C-31 (respondent framed as "Consumer" vs "Individual" sharing water).
Everything else 0.

**Missing values:** none. C-16 and C-31 are borderline (structural role
constant, identity/relationship changes) — see coding_note.

## 4. gain_loss_framing (0/1)

**Definition:** 1 if one arm explicitly reframes materially equivalent
consequences as gains and the other as losses. Merely mentioning money or a
loss = 0.

**Motivation (prospect theory):** the canonical gain/loss reference-frame
manipulation.

**Coded 1:** C-01 (saved vs die), C-02/C-03 ("winning nothing" vs "losing
$0.05/$0.25"), C-28 (award vs deny custody), C-37/C-38 (same doctor attributes
described positively vs negatively).

**Missing values:** none. C-15 is 0 despite valence change: success vs death
are materially different outcomes, not equivalent consequences reframed
(coding_note). C-37/38 framing-of-equivalent-attributes reading is noted as a
judgment call.

## 5. numerical_manipulation (0/1)

**Definition:** 1 if a number, amount, or numerical probability CHANGES
between the arm texts. Numbers constant across arms do not count; a number
ADDED in one arm counts (something numeric differs).

**Motivation (information processing / anchoring):** numeric content changes
are the carrier of anchoring, proportion, and magnitude manipulations.

**Coded 1 (18):** C-02, C-03, C-04, C-05, C-06, C-07, C-08, C-10, C-11, C-13,
C-14, C-15, C-17, C-18, C-20, C-30, C-34, C-35.

**Borderline (coded 0, see coding_note):** C-19 (number words change
"two come up 6's" → "all three come up 6's" but numerals are constant);
C-09 (identical 1-in-1,000 both arms).

**Missing values:** none.

## 6. explicit_probability (0/1)

**Definition:** 1 if at least one arm contains an explicit numerical
probability (e.g., "1/3 probability", "1 in 1,000", "1% chance", a 0–100%
scale).

**Motivation (JDM):** presence of explicit probabilities enables normative
computation and distinguishes risk from ambiguity/verbal-likelihood tasks.

**Coded 1 (10):** C-01, C-02, C-03, C-09, C-10, C-11, C-15, C-30, C-34, C-35.

**Borderline (coded 0):** C-04..C-07 (98%/95% are shares of a fixed population,
not event probabilities); C-16 ("8 times more likely" is relative likelihood);
C-17 (7-of-10 composition implies probability but states none). See
coding_note for the alternative coding.

**Missing values:** none.

## 7. negation_change (0/1)

**Definition:** 1 if the differing text adds, removes, or changes an explicit
negation. Fixed token list (searched on lowercased punctuation-stripped
tokens): no, not, never, none, cannot, don't, doesn't, isn't, aren't, won't,
wouldn't, shouldn't, couldn't, without, neither, nor, unlikely. Script output
(text_features.csv, negation_tokens_changed plus evidence log) was manually
reviewed for every contrast; ambiguous uses were checked by hand.

**Motivation (survey methodology):** negations reverse propositional polarity
and inflate cognitive load / misreading rates.

**Script flags resolved by hand:**
- Coded 1: C-15 ("The operation did not succeed" vs "succeeded"; script set-diff
  empty because 'not' also occurs in shared option labels), C-26 ("have not
  done ... would not be able" removed; "prefer not to volunteer" added),
  C-37/C-38 ("I will always go back" vs "I will never go back").
- Coded 0 despite script flags: C-01 ('no people' vs 'nobody people' —
  token-list artifact of the frame rewording, not the manipulation), C-34/C-35
  ('unlikely'/'not' enters only via the shared IPCC table rows, identical in
  both contrasts' treatment arms and not manipulated).

**Missing values:** none.

## 8. question_length (continuous, script-computed)

**Definition:** mean word count of the two compared arm texts. Normalization:
lowercase; remove punctuation except %, $, /; split on whitespace. Includes
response-option labels and arm-specific context; excludes identical generic
wrappers (they cannot differ between arms, so including them would only add a
constant).

**Motivation (information processing):** longer stimuli dilute manipulation
strength and increase reading-load-driven noise.

**Algorithm:** `len(tokens_control + tokens_treatment) / 2` after
`normalize()` in compute_text_features.py.

**Example:** C-22 = 15.0 words (arm texts 15 tokens each).

**Missing values:** none.

## 9. wording_difference (continuous, script-computed)

**Definition:** proportion of words changed between arms. Exact algorithm:
lowercase; strip punctuation (except %, $, /); whitespace-tokenize both arm
texts; run `difflib.SequenceMatcher` on the token lists; count tokens in
replace + delete + insert opcodes (a replace counts tokens on BOTH sides);
divide by mean(len_a, len_b). Values can exceed 1 when the arms share few
tokens and differ in length (worst case here: C-17 = 1.59, two entirely
different scenarios).

**Motivation (experimental design):** global wording churn measures how much
of the stimulus varies alongside the registered manipulation — high values
flag contrasts where "the manipulation" is really a scenario change.

**Example:** C-22 = 0.1333 (1 token of 15: allow→forbid); C-24 = 0.7123.

**Missing values:** none.

## 10. manipulation_location (0–1, script-computed; NaN allowed)

**Definition:** position of the FIRST differing token, as a fraction of the
control arm's token count (same normalization as feature 9). Early = the
manipulation sits in the vignette setup; late = in or near the question.

**Motivation (attention / information processing):** manipulations far from
the response are more easily under-weighted; location indexes how proximal
the changed content is to the judgment.

**NaN rule:** for pure question-order manipulations the first-difference
position is meaningless, so the value is NaN with
`manipulation_location_na=1` and a documented reason. Applied to C-36
(same six K6 items reordered). C-21 and C-27 are question-order manipulations
implemented by INSERTING a preceding question, so the location (0.0 = at the
start of the differing text) is kept and explained in coding_note.

**Missing values:** 1 of 38 (C-36), flagged with reason.

## 11. question_order (0/1)

**Definition:** 1 if the arms differ in the ORDER of otherwise identical
questions/items.

**Motivation (survey methodology):** priming/consistency effects of preceding
items (Schwarz style context effects).

**Coded 1:** C-21, C-27, C-36. **Missing values:** none.

## 12. response_options_change (0/1)

**Definition:** 1 if the answer labels, numbers, or their order differ between
arms.

**Motivation (survey methodology):** category-scale range shifts (category
anchoring) live entirely in the response options; identical-vignette/option-
shift designs are a distinct manipulation family.

**Coded 1:** C-11 (whole option set differs), C-17 ('1'/'2' vs 'red'/'green'),
C-20 (hour brackets shift up). **Missing values:** none.

## 13. n_response_options (integer; NaN allowed)

**Definition:** actual number of fixed response options for the outcome
elicitation; NaN when the elicitation is a free numeric entry or the outcome
measure is an open estimate.

**Motivation (survey methodology):** number of options indexes granularity
and scale-induced variance restriction.

**NaN (3):** C-08 (0–20 free entry), C-13/C-14 (outcome is the open numeric
estimate; the 2-option anchor item is not the outcome item). Reason recorded
in `n_response_options_na_reason`.

---

## Provenance and coding method columns

- `arm_control_label`, `arm_treatment_label`: registered arm names compared.
- `stimulus_source`: file(s) the verbatim arm texts come from.
- `negation_evidence`: which negation-list tokens differ (or "identical").
- `diff_evidence`: token excerpt around the first text difference.
- `coding_method_manual` = `two_pass_analyst_reconciled` (all manual features);
  `coding_method_text` = `script (compute_text_features.py)` (features 8–10).
- `coding_note`: free-text uncertainty/judgment-call notes per contrast.

## Statement of blinding

No file containing human or model effect sizes, accuracy, direction results,
disagreement audits, or y_std was read at any point during coding. Inputs
read: this stage's SPEC, stage8 CODING_RULES.md / SCENARIO_TEXT.md /
EXPERIMENT_CHARACTERISTICS.csv (pre-outcome instrument coding), stage3
CONTRAST_REGISTER.csv, the verbatim stimuli and expansion prompt files, and
stage5 `response_format` / `n_options` columns (design descriptors only).
