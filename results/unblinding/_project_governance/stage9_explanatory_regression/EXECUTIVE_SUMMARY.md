# Executive summary — Stage 9 explanatory regressions

## What we tested

Across 38 classic judgment-and-decision-making experiments (553 experiment-model
pairs, 1,106 blinded/disclosed runs of 15 AI models), we asked a simple question:
**can we explain why AI answers sometimes land far from the human result and
sometimes point in the wrong direction?** For every experiment, research assistants
who did not know the outcomes coded *how the experiment had been reworded for the
AI* — whether negations were flipped, numbers added or removed, questions reordered,
sentences lengthened, probabilities made explicit, and so on. We then fitted two
statistical models: one explaining **how far the AI landed from the human result**
(measured in standard-deviation units), and one explaining **whether the AI pointed
in the same direction as humans**.

This analysis is exploratory and theory-informed. It was not preregistered, and the
feature coding choices were made for this stage. It describes associations — it
cannot prove that a rewording *causes* the AI to err.

## What we found

**The single clearest pattern: the AI is most wrong exactly where humans showed the
strongest effects.** Experiments where humans moved a lot show much larger AI errors.
When the human effect grows by half a standard deviation, the AI's distance from the
human result grows by about **61% (95% plausible range: +27% to +99%)**. This
relationship is solid — it holds when we redraw the human benchmarks, when we exclude
any single experiment, and when we exclude the Qwen model family.

**Part of the "AI discrepancy" is ordinary noise, not bias.** When a model's answers
in one experiment are more variable (a noisier estimate), that model lands further
from the human result. Doubling that variability raises the measured gap by about
2.7% (range +0.6% to +4.7%). Some of what looks like AI error is simply sampling
wobble in the AI's answers.

**No single rewording feature is proven to matter.** The largest associations were
with negation changes (errors roughly 68% larger when a negation was flipped; range
−11% to +182%) and numerical manipulations (errors about 26% smaller when numbers
were manipulated; range −55% to +13%) — but both ranges include zero, so neither is
established. Question order, role changes, response-option changes, question length,
wording-difference size, and explicit probability wording all show small, uncertain
associations.

## Which experimental characteristics appear most relevant?

In order of the strength of their association with AI error (equal weight per
experiment):

- **Size of the human effect** — the strongest, and the only feature-adjacent
  quantity with a clearly non-zero association (see above).
- **Negation changes** — suggestive but not established (+69%, range −11% to +182%).
- **Numerical manipulation** — suggestive in the direction of *smaller* error
  (−26%, range −55% to +13%), but it overlaps heavily (26 of 38 experiments) with
  explicit-probability wording, so the two cannot be separated with this data.

## How large are the associations, and how certain are we?

Every number above comes with a 95% plausible range (credible interval). Only two
relationships have ranges that exclude zero: the human-effect-size relationship
(+61%, +27% to +99%) and the model-noise relationship (+2.7%, +0.6% to +4.7%).
Everything else — every rewording feature, every disclosure effect — has a range
that includes zero. Sparse features (role change, question order, response-option
changes appear in only 3 of 38 experiments each) have especially wide ranges; for
these, the data genuinely cannot tell us much, which is different from showing no
effect.

## Does disclosure matter?

**On average, no — not clearly.** Letting the AI see the human results first
("disclosure") was associated with a small *reduction* in error (−7.2%, range −16.4%
to +2.9%), but this is not established. For direction agreement, disclosure shifted
things by −1.8 percentage points (range −7.9 to +3.2) — again not established. An
earlier stage of the project (Stage 6) found a similarly small and uncertain
disclosure effect on direction accuracy; the two stages' point estimates differ in
sign but both ranges include zero, so they are statistically compatible. Neither
stage finds a clear disclosure effect.

## What remains unexplained?

A lot. Which *experiment* a question comes from matters about as much as any coded
feature — experiments differ among themselves in ways our coding did not capture.
Direction agreement (whether the AI points the same way as humans, correct 73.7% of
the time on confident contrasts) is barely explained by any feature we coded, though
the design has limited power there. And none of this analysis can say *why* an
association exists — only that it does, under the model's assumptions.

## Data caveat

A portion of the original-experiment data (145 of 530 cells) carries frozen values
from an earlier run that could not be independently reproduced from the stored
records; we kept the frozen values as given and flagged them rather than silently
changing them. The main conclusions were unchanged when we excluded the model family
most affected by this caveat. Technical details are in METHOD_AND_QA.md.
