# EXPERIMENT_COMPATIBILITY.md — what the twin2k10r pipeline demonstrably supports

**Date:** 2026-11-03 · **Status:** Stage 0 (pool build + validation only — NO inference has run).

This document registers the twin2k10r pipeline against the project's experiment registries and
states exactly which experiments/contrasts are *demonstrably* supported by what was built and
verified in Stage 0. Nothing is claimed that was not exercised here.

## 1. What twin2k10r is

twin2k10r is the twin2k10 study with only the persona source swapped (synthetic LLM personas →
real Twin-2K respondent records). Stimuli, prompt scaffold, arms, inference settings (temp 1.0,
top_k 100, seed 42), and scoring are consumed from twin2k10 unmodified. Therefore twin2k10r
supports exactly the experiments twin2k10's shipped registry defines — no more.

## 2. Demonstrably supported: the 10 twin2k10 experiments (9 contrasts)

Source of truth: `data/configs/twin2k10_stimuli.json` + `scripts/twin2k10/experiments.py`
(EXPERIMENTS). Every experiment below was exercised end-to-end in Stage 0: real stimulus text
rendered into a full anonymized prompt (see `PROMPT_EXAMPLES.md`), real 7-field persona block,
both arms' system prompts built, and the suite `tests/twin2k10r` GREEN (72 passed).

| Experiment | Arms (contrast) | Stimulus types | Demonstrated by |
|---|---|---|---|
| allais | form1 vs form2 (1 contrast) | choice | PROMPT_EXAMPLES; suite |
| anchoring_african | low vs high (1) | choice anchor + numeric estimate | suite |
| anchoring_redwood | low vs high (1) | choice anchor + numeric estimate | suite |
| outcome_bias | success vs failure (1) | choice | PROMPT_EXAMPLES; suite |
| myside | ford vs german (1) | choice | PROMPT_EXAMPLES; suite |
| abs_relative | calculator vs jacket (1) | choice | suite |
| linda | conjunction vs no_conjunction (1) | rating statements | PROMPT_EXAMPLES; suite |
| base_rate | 30_engineers vs 70_engineers (1) | numeric estimate | PROMPT_EXAMPLES; suite |
| prob_matching | problem1 vs problem2 (1) | rating statements | suite |
| false_consensus | all (single arm — no within-experiment contrast) | rating statements | suite |

**9 between-arm contrasts + 10 experiments demonstrably supported.**

## 3. Overlap with the frozen reconciliation registry (14 experiments / 18 contrasts)

`results/unblinding/_project_governance/stage10_data_reconciliation/corrected_results/stage3/
corrected_signed_contrasts.csv` lists 14 experiments / 18 contrasts. Overlap with the twin2k10
registry above:

- **In both (8 experiments, demonstrably supported by twin2k10r):** abs_relative, allais,
  anchoring_african, anchoring_redwood, linda, myside, outcome_bias, prob_matching.
- **In the reconciliation only (6 experiments, NOT demonstrable here):** disease,
  fire_extinguisher, less_is_more, seatbelt, sunk_cost, wta_wtp — their stimuli are not in
  `twin2k10_stimuli.json`, so twin2k10r cannot render them; claiming support would be false.
- **In twin2k10 only (2):** base_rate, false_consensus (outside the 14-experiment frozen set).

## 4. The 31-experiment / 38-contrast full grid

The audit's full grid (31 experiments / 38 contrasts) includes the expansion experiments. The
expansion registry (`expansion/pipeline/registry.py`) is **not present in this worktree**, so
support for expansion experiments is **not demonstrable and is not claimed**. Any later claim
must first ship those stimuli into the twin2k10-style layout and re-run the render verification.

## 5. Honest limits

- Stage 0 built and validated pools only — **zero inference**. "Supported" means: the pipeline
  can render valid prompts and run these cells; it does NOT mean results exist or replicate.
- Config A (7 real fields) is the primary path; Config B (11 measured scores) is robustness-only.
- The 4 unavailable demographic fields (occupation, number_of_children, state, home_ownership)
  are omitted from every prompt; prompts are shorter than the original study's 11-field synthetic
  ones. That difference is the object of the pilot, not a defect to hide.
