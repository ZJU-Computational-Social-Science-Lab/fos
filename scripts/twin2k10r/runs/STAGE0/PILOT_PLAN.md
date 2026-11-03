# PILOT_PLAN.md — Pilot for the real-respondent persona pipeline (Stage 0 revision)

**Task:** TASK-3128 (Stage 0 rebuild) · **Date:** 2026-11-03 ·
**Status:** Stage 0 EXECUTED (pools built + validated); stages 1–3 not run.
Based on `results/unblinding/twin2k_redesign/PILOT_PLAN.md` (TASK-3119), revised per the Stage 0
evaluation policy: **no ±10pp per-contrast gate, no per-contrast slopes, aggregate
matched-comparison evaluation, symmetric treatment of better/worse results, explicit uncertainty
caveats.** The original document is NOT edited; this is the revised copy governing the pilot.

---

## Summary

A three-stage pilot: (0) pool build + validation only (no inference) — **done**, (1) a
single-model minimal-cell run, (2) a two-model × 4-experiment pilot evaluated by an aggregate
matched comparison against the original study's archived records, and (3) the full 15-model rerun,
launched only if the stage-2 aggregate criteria pass. Pilot compute is ≈9–10% of one original
production run.

## 1. Reference numbers from the original study ([Verified] — audit §3)

| Metric | Uninformed | Informed |
|---|---|---|
| Directional accuracy | 350/467 = 74.95% | 73.0% |
| Signed bias | −12.10 pp | −3.80 pp |
| Absolute error | 21.11 pp | 21.26 pp |
| Recovery slope | 0.4935 | 0.8978 |

Original structure: 15 models, 31 experiments, 38 contrasts, 1,119 usable sets, 100-persona pool,
temp 1.0 / top_k 100 / seed 42, disclosure = design + versions only.

## 2. Stages

**Stage 0 — pool build & validation (EXECUTED, no GPU inference):**
- Config A pool: 100 real respondents, seed 42, sex×age stratified without replacement;
  `pools/twin2k_respondent.jsonl`, sha256 `bdc842334a71aa61f20797f778d77cad1eefd772dec08e4498d4e357f447eea1`.
- Config B pool (robustness leg): `config_B/pools/`, sha256 `766322890547…` (see POOL_PROVENANCE.json).
- `validate_pool.py` both pools → VALIDATION_REPORT.md: **all gates PASS** (panel 2,058; pool size
  100; persona↔panel truth; marginals within rounding; one shared pool; no leaking fields;
  seed replay identical).
- This stage alone already delivers the reproducibility and provenance evidence the synthetic
  pool never had (`seed: null` in the original).

**Stage 1 — minimal cell (not run):** 1 model (mid-tier, no `low_branch_mass` flag, no
duplicate-run ambiguity in the audit; final pick at launch from the registry), 2 experiments ×
2 arms × 100 personas, logprob scoring.

**Stage 2 — pilot proper (not run):**
- **Models:** 2 (stage-1 model + one stronger model from the original 15).
- **Experiments:** 4, one per contrast family, spanning stimulus types: anchoring (two-question
  numeric), Disease framing (gain/loss), sunk-cost yes/no, one T2K10 numeric pricing item (k=20).
- **Arms:** uninformed + informed (design+versions, never human results); byte-identical prompts
  per cell.
- **Configs:** A primary on all cells; B only as a labeled robustness leg, never merged with A.

**Stage 3 — full rerun (contingent):** 15 models × 31 experiments × 2 arms × 100 personas,
Config A only, identical to the original grid with the pool swapped.

## 3. Stage-2 evaluation — aggregate matched comparison (REVISED)

**What changed vs the 2026-11-03 draft and why:** the draft's stage-2 gate ("directional accuracy
per contrast within ±10 pp of the original same-model same-contrast values", "recovery slope same
sign for ≥3 of 4 contrasts") treated per-contrast point estimates as decision-grade evidence. With
≈16 contrast-model cells and 100 personas per cell, per-contrast sampling noise is far larger than
a 10pp band, so such a gate would mostly measure noise — and it was asymmetric (only "no
degradation" counted). The revision:

1. **Aggregate matched comparison, not per-contrast gates.** Extract the original archived records
   for exactly the pilot's (model, contrast) cells, pool across the 4 contrasts × 2 models, and
   compare the pilot's aggregate directional accuracy, signed bias, and absolute error against
   that matched original subset (like-for-like, not against the 38-contrast aggregate).
2. **Symmetric treatment.** The aggregate result is read in whichever direction it moves: a shift
   toward the human benchmark is reported, and so is a shift away, with equal weight. Neither
   direction "validates" or "invalidates" the original numbers — the persona source changed, so
   differences are the object of study.
3. **No per-contrast slopes.** Recovery slopes are computed only at the aggregate level
   (pooled-cell predicted-vs-human regression), with the slope's uncertainty reported, not a
   pass/fail on sign per contrast.
4. **Launch criterion for stage 3 (the only gate).** Stage 3 launches if: (a) stage-0 validation
   gates all PASS (absolute, already met); (b) pilot branch-mass / parse-failure rates are within
   the historical range of the original runs (a health check, not an accuracy gate); (c) measured
   stage-2 records/minute supports the stage-3 budget. Accuracy differences — in either direction —
   are reported, not gated.
5. **Uncertainty caveats (mandatory in any write-up).** Report bootstrap CIs over personas for
   every aggregate number; state that stage 2 covers ≈16 contrast-model cells and cannot estimate
   the full-grid directional accuracy (467-set basis); state that the reference is the *panel*, not
   the census; state that 7-field real prompts differ from the original 11-field synthetic ones and
   that this design difference, not noise alone, can move any metric.

## 4. Pilot steps (execution order)

1. ~~Freeze dataset manifest~~ — done (`dataset_manifest.json`, sha-of-manifest in provenance).
2. ~~Build Config A + B pools; write POOL_PROVENANCE.json~~ — done.
3. ~~`validate_pool.py` both pools → all gates PASS~~ — done.
4. Stage 1 run; verify per-record prompt_sha256 archive intact; eyeball 10 anonymized prompts
   (`PROMPT_EXAMPLES.md`).
5. Score stage 1 with untouched `logprob_scoring.py`; sanity-check option probabilities sum to 1;
   binary renormalization behaving; no low_branch_mass anomalies.
6. Stage 2 run (both configs); score; assemble the aggregate matched comparison (§3).
7. Write PILOT_REPORT: aggregate comparison + CIs + symmetric readout + go/no-go for stage 3;
   pre-register the stage-3 analysis before launching it.

## 5. Risks and mitigations

| Risk | Mitigation |
|---|---|
| 7-field prompts weaker than 11-field synthetic ones | That shift is the object of study; Config A′ (US region added) runs as a labeled variant on stage-2 cells only |
| Panelists ARE the benchmark population | Intended design; leakage gates keep personas to attribute-level information |
| Config B trait scores as covert outcome hints | Robustness-only; whitelist/blocklist asserts; never pooled with A |
| Per-contrast noise mistaken for signal | Aggregate matched comparison with CIs; no per-contrast gates (this revision) |
| Compute overrun on stage 3 | Launch gate uses measured records/min; campaign resumes per model block |

## References

1. FORENSIC_EXPERIMENT_AUDIT.md; 2. DESIGN_HISTORY.md; 3. DATA_INVENTORY.md;
4. CORRECTED_DESIGN.md & IMPLEMENTATION.md (TASK-3119);
5. original PILOT_PLAN.md (results/unblinding/twin2k_redesign/, unmodified).
