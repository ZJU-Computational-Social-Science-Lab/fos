# RESEARCH_DATA_COVERAGE.md — Stage 9 pre-analysis data audit (TASK-2999)

**Written:** 2026-10-28 · research role · read-only audit; no frozen file touched.
**Intended location:** `_project_governance/stage9_explanatory_regression/RESEARCH_DATA_COVERAGE.md`.
**NOTE (environment blocker):** the entire `/home` filesystem is mounted READ-ONLY in this session
(`btrfs ro`, no sudo available), so this file and the accompanying CSVs are delivered in
`~/work/crew/research/OUTBOX/stage9_artifacts/` instead. Nothing under the frozen tree was modified.

## 1. Record reconciliation — ~413,520 CONFIRMED

| Run | Path (under `results/unblinding/`) | `wc -l` over all `records.jsonl` | Study records |
|---|---|---|---|
| run6 | `TWIN2K_UNBLINDING_LOGPROBS_6TASKS-20260919T025143/` | 48,000 | **47,520** (480 = sibling `PREFLIGHT/`, documented non-study data) |
| run10 | `T2K10-20260923T034851/` | 57,000 | **57,000** |
| expansion | `expansion/work/T2KX-20261022T222604/` | 309,000 | **309,000** |
| **Grand total** | | 414,000 raw | **413,520** ✓ |

- File counts: run6 240 study `records.jsonl` (15 models × 16 legs) + 120 PREFLIGHT; run10 300 (15 × 20); expansion 510 (15 models × 34 legs).
- Matches `stage1_inventory/SOURCE_OF_TRUTH.md` §4/§5/§9 exactly (47,520 / 57,000 / 309,000).
- Per-cell table: `COVERAGE_PER_CELL.csv` (1,005 rows: run, model, leg, n, invalid_or_failed, temps, seeds, inference keys, record fields).
- **Zero records with `succeeded=false` or non-empty `error`/`choice_error`** across all 414,000 raw records.
- No unexpected duplicate `(persona_id, qid, arm)` keys; run6 "duplicate personas" are by design: each persona answers every within-leg arm (2–3 arms per experiment, e.g. disease gain/loss; wta_wtp 3 arms).

## 2. Repeat structure

- Sampling config is **identical for every record in all three runs**: `temperature 1.0, top_k 100, scan_tokens 8, seed 42, logprob_mode first_token` (stored per-record in `inference` key).
- Repeats vary by **persona only** (run6: 99 personas/arm; run10: 100; expansion: 100). No repeated draws of the same (persona, prompt) exist; each response is ONE temperature-1.0 stochastic draw at seed 42.
- Prompts: the same persona receives different prompts across blinded/unblinded legs by design (`prompt_sha256` overlap between legs = 0). Within a leg, prompts are shared per (persona, arm/qid).
- **Implication for bootstrap:** within-arm response resampling captures persona-sampling + realized sampling noise jointly; it CANNOT separate persona variation from temperature stochasticity (no repeated draws per persona), and it cannot capture seed-level variability (one seed everywhere).

## 3. Uncertainty feasibility for original-experiment model-effect SEs

Stage 5 zero-fills original `se_y_std` (`stage5_common.py`: `wide["se0"] = wide["se0"].fillna(0.0)`) — confirmed; zero is a missing-value sentinel, not certainty.

**Verdict: FEASIBLE at every response scale, with caveats.** A response-level within-arm bootstrap (resample records with replacement inside each arm; recompute the arm means; rebuild d_m with the FROZEN definitions in `T2K10-20260923T034851/final_audit/blinding_effect_magnitude_analysis.py` — `record_outcome`, `normalization_0_1` registry specs, anchor handling; standardize by frozen `sd_human_pooled_pp`; 500 draws) runs in **~7 s** for the whole original14 × 15-model × 2-blinding grid.

Per response scale:
- `share` (disease p_safe, prob_matching digit shares): fine; occasional **degenerate cells** where all responses in a cell are (near-)identical → SE = 0. 6 such cells flagged.
- `rating_mean` / Likert letter-mean (less_is_more, fire_extinguisher, seatbelt, myside, outcome_bias) and ordinal (sunk_cost, wta_wtp): fine.
- `binary_choice`-style single-option mass (allais, abs_relative): fine.
- `numeric_estimate` / anchoring: fine where arms are populated; **10 cells have an entirely empty arm under `record_outcome`** (8 anchoring cells among others) — the frozen pipeline itself drops these (262 = 270 − 8 rows in `blinding_signed_contrasts.csv`).

### ⚠ Material audit finding: 145 of 530 cells (27%) do NOT reproduce the canonical frozen d_m
- Re-running the frozen module verbatim on the canonical, sha-verified records reproduces `blinding_signed_contrasts.csv` for **all run6 cells** and for 385/524 original contrast-model-leg cells overall, but **145 cells** (8 run10 experiments: allais, abs_relative, anchoring_african, anchoring_redwood, linda, myside, outcome_bias, prob_matching; models incl. qwen3-4b, qwen3-32b, qwen3.6-35b-a3b(-unc), granite-4.1-8b/30b, glm-4.7-flash, muse-glimmer, nemotron-cascade-2, partially qwen3.6-27b-dense and the gemma-4-26b/31b) differ.
- Root cause traced: the frozen chain consumed `~/work/research/T2K10-FIGURES/llm_arm_means.json`, which for exactly those model×experiment legs holds **stale intermediate arm means with n=1 per arm** (e.g. qwen3-4b allais blinded: form1/form2 n=1) instead of the full n=100. All 145 bad cells have `min_n < 200` in that file; zero good cells do. The records themselves are complete (200/leg) and hash-frozen (stage2 manifest hash = current file hash).
- Since Stage 5 `y_std` provably follows the frozen d_m (verified numerically), **the stale values propagate into `stage5_dataset.csv` for those cells**. Stage 9 should recompute these 145 cells from records before any SE-informed regression.

## 4. Deliverables (in `~/work/crew/research/OUTBOX/stage9_artifacts/`)

- `COVERAGE_PER_CELL.csv` — per model×leg: n, failed/error count, inference config, present fields.
- `MODEL_SE_BOOTSTRAP_DRAFT.csv` — 530 rows: contrast_id, experiment, model, blinding, d_m_point, d_m_frozen, point_matches_frozen, se_model_effect (std. scale, 500 draws, seed 20261028), n_resamples, method, n_treatment/n_comparison, degenerate, reliable_flag. Reliable = point matches frozen AND both arms n≥30 AND se>0 → **378/530**. 145 flagged `point_matches_frozen=False` (stale-lineage cells), 6 degenerate, 10 missing (empty arm).
- `tmp_coverage_audit.py`, `tmp_model_se_bootstrap.py` — the read-only audit/bootstrap harnesses (kept for reproduction).
- `RESEARCH_DATA_COVERAGE.md` — this file.

## 5. Gaps / open items

1. Read-only mount prevented writing into `_project_governance/stage9_explanatory_regression/` (see NOTE above).
2. 145 stale-lineage cells in the canonical contrast CSV (Section 3) — needs a decision/orchestration follow-up.
3. 10 original cells lack a bootstrap SE because one arm has zero valid outcomes under the frozen outcome rules — matches the frozen pipeline's own exclusions.
4. Bootstrap SEs capture persona resampling only; single seed (42) and one draw per persona mean temperature-level stochasticity is not separately estimable.
5. `progress.json` staleness in run10 (documented in SOURCE_OF_TRUTH) reconfirmed as irrelevant — record counts verified by direct recount.
