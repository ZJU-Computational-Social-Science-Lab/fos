# RESEARCH_FINDINGS.md — handoff for the Stage 10 rebuild task (TASK-3008)

## What this file is
A short, practical handoff for whoever rebuilds the 145 affected model-effect
estimates from the canonical records. Diagnosis only — nothing was rebuilt here.

## Where staleness entered (exact stages)
1. **Path mirror divergence.** The frozen analysis
   `T2K10-20260923T034851/final_audit/blinding_effect_magnitude_analysis.py` (sha256
   `1d07b908a7b81e95e…`, lines 47–48) hard-codes its data roots to
   `/home/justin/work/fos-data/results/unblinding/…`. That copy of run10 stopped
   syncing on 2026-09-23; the canonical tree
   (`/home/justin/Documents/ZJU work/fos/results/unblinding/…`) holds the completed
   records (finalized 2026-10-06). Evidence: rebuilding from the mirror reproduces
   **all 524 frozen values exactly**; rebuilding from canonical leaves 139 mismatches
   + 6 dropped rows. Census: 186/300 run10 mirror files short (165 @2 lines, 20 @1, 1 @119).
2. **`llm_arm_means.json`** (`/home/justin/work/research/T2K10-FIGURES/`, 2026-10-07
   18:32) was generated from the same mirror by `scripts/twin2k10/llm_arm_means.py`:
   blinded legs only, n=1 per arm for 9 run10 models, n=59 for qwen3.6-27b-dense
   prob_matching. It fed `scripts/twin2k10/signed_effects_run.py` (line 380) →
   `final_signed_contrasts.csv` / REPAIRED tables. The signed-contrast chain itself
   did NOT read it — it read the mirror records directly.

## Downstream files that inherit wrong values (Stage 3 → 5 → 9)
- `agreed_figure_code_package/data/blinding_signed_contrasts.csv`
  (= `final_audit/blinding_signed_contrasts.csv`, sha256-16 `c2fdb506c03768c2`) —
  139 wrong cells + 6 rows missing that canonical data supports (anchoring).
- `stage5_exploratory/data/stage5_dataset.csv` — verified: `y_std × sd_human_pooled_pp`
  equals the frozen d_m exactly for all 524 original rows; `se0=0` is a missing
  sentinel. All 145 flagged cells inherit stale effects.
- Stage 9 `MODEL_SE_BOOTSTRAP_DRAFT.csv` / `MODEL_INPUTS_A/B.csv` and any regression
  using `point_matches_frozen=False` cells.
- The `signed_effects_run.py` lineage (`final_signed_contrasts.csv`,
  `signed_contrast_effects_REPAIRED.csv`, figure inputs) — blinded-only and stale for
  the same models; check figure numbers derived from it.

## Rebuild guidance
- **Source of truth:** canonical records only —
  `/home/justin/Documents/ZJU work/fos/results/unblinding/{TWIN2K_...-20260919T025143, T2K10-20260923T034851}`.
  Never read `/home/justin/work/fos-data/...`.
- **Arm definitions / scoring entry point:** reuse
  `final_audit/blinding_effect_magnitude_analysis.py::record_outcome` + `normalize01`
  verbatim (registry `normalization_0_1` min/max; anchor experiments use arm-level
  `anchor_mc["1"]` share, NOT numeric estimates). It reproduced 385/524 cells to <1e-6,
  so the scoring code is correct — only the roots were wrong.
- **Known pitfalls:**
  - Anchoring: treat `p_norm["A"]` null/omitted as MISSING (exclude), never as zero.
    qwen3-4b anchoring_redwood_unblinded high arm is 100× `A=null` canonically → that
    arm is legitimately unscoreable; 10 anchoring cells stay empty (see ROOT_CAUSE_ANALYSIS §6).
  - granite-4.1-30b anchoring_redwood blinded: only 3/100 valid outcomes canonically —
    decide explicitly whether to freeze or flag.
  - Keep the frozen exclusion set (base_rate, false_consensus) and the 8-dropped-wide-row
    handling separate from the stale-mirror drops: after rebuild, 6 anchoring cells gain
    values; the table becomes 530 scoreable cells minus the 10 truly-empty = re-derive
    the drop list from canonical arm coverage.
  - Do not use `llm_arm_means.json` for anything; if needed, regenerate it from
    canonical records (blinded AND unblinded legs).
- **Verification gate for the rebuild:** recompute all 530 grid cells from canonical
  records; expect 385 unchanged, 139 replaced, 6 new; 0 rebuildable mismatches remaining.
- 13 of the 139 replaced cells change sign — expect direction-of-effect statements in
  downstream summaries to change for those cells (list in MISMATCH_CLASSIFICATION.csv,
  `direction_changed=True`).

## Key numbers
- Records: 413,520 study (47,520 + 57,000 + 309,000) + 480 preflight; all hashed, 0 anomalies.
- Mismatches: 139 `stale_value` + 6 `missing_arm_alt_snapshot_exclusion` = 145; 13 sign flips.
- Coverage: 530 (audit grid) = 540 − 10 canonically-empty cells; 524 (frozen) = 530 − 6
  mirror-induced drops.
