# ROOT_CAUSE_ANALYSIS.md — Stage 10 (TASK-3008)

## What this file is
A plain-language explanation of why 145 frozen model-effect estimates disagree with
values rebuilt from the hash-frozen inference records, why the audit examined 530
cells while the frozen analysis contains 524, and exactly which code paths and files
caused it. Everything below was verified against the actual stored files, not assumed.

## 1. Verified root cause (one paragraph)

The frozen analysis script `T2K10-20260923T034851/final_audit/blinding_effect_magnitude_analysis.py`
(SHA-256 `1d07b908a7b81e95e…`, matching FROZEN_ANALYSIS_MANIFEST.json, freeze time
2026-10-12T16:25Z) computes arm means **directly from records.jsonl** via
`load_paired_means()` (line 117), but its run roots are hard-coded at lines 47–48 to:

- `RUN10 = /home/justin/work/fos-data/results/unblinding/T2K10-20260923T034851`
- `RUN6  = /home/justin/work/fos-data/results/unblinding/TWIN2K_...-20260919T025143`

The `fos-data` copy of run10 is a **mid-run mirror frozen on 2026-09-23 ~12:03**: for
9 of the 15 models, the 9 run10 experiment legs hold only 1–2 records per arm
(the first persona's worth), while the canonical tree under
`/home/justin/Documents/ZJU work/fos/results/unblinding/` holds the complete 200
records per leg (finalized 2026-10-06 ~04:57). The frozen chain therefore computed
effects from partial data. It never read `llm_arm_means.json` for these values —
that file is a *co-stale byproduct* (built 2026-10-07 18:32 by
`scripts/twin2k10/llm_arm_means.py`, blinded legs only), not the source.

## 2. The decisive test

The same frozen scoring module (`record_outcome`, `normalize01`, anchor handling) was
run verbatim against both trees:

| Rebuild root | Cells matching frozen `blinding_signed_contrasts.csv` | Mismatches | Missing arm |
|---|---|---|---|
| **fos-data mirror** (path baked into frozen script) | **524 / 524 exact** | 0 | 0 |
| canonical records (`Documents/ZJU work/fos/...`) | 385 | 139 | 10 empty |

Rebuilding from the fos-data mirror reproduces **every one of the 524 frozen values to
<1e-6**. This proves the frozen values came from the stale mirror, not from the
canonical records and not from any other scoring variant. (Harness:
`research/OUTBOX/stage10_artifacts/tmp_alt_rebuild.py`; per-cell residues in
`alt_rebuild_mismatch.csv`; file census in `alt_census.json`.)

### Mirror census (run10, alt vs canonical lines per records.jsonl)

| (alt lines, canonical lines) | Files | Interpretation |
|---|---|---|
| (2, 200) | 165 | 1 record per arm vs full leg — stale mid-run snapshot |
| (1, 100) | 20 | single-arm file stale |
| (119, 200) | 1 | partially synced (`qwen3.6-27b-dense/prob_matching_blinded`) |
| (200, 200) / (100, 100) | 104 + 10 | already-final models (e.g. gpt-oss-20b, both trees mtime 09-23) |
| run6 differences | **0 / 360 files** | run6 mirror is complete — why all run6 cells reproduce |

The 9 stale run10 models: qwen3-4b, qwen3-32b, qwen3.6-35b-a3b, qwen3.6-35b-a3b-uncensored,
granite-4.1-8b, granite-4.1-30b, glm-4.7-flash, muse-glimmer, nemotron-cascade-2-30b-a3b,
plus partial qwen3.6-27b-dense (prob_matching only, n=59) and leg-level gaps for the
gemma-4-26b/31b anchoring arms.

## 3. Role of llm_arm_means.json — hypothesis VERIFIED AND REFINED

The Stage 9 hypothesis ("stale llm_arm_means.json fed the frozen chain") is
**confirmed in substance, corrected in mechanism**:

- `llm_arm_means.json` (2026-10-07 18:32) contains **blinded legs only** (240 entries,
  zero unblinded). For the 9 stale run10 models it holds n=1 per arm — the same
  mid-run state as the fos-data mirror. For fresh models it holds n=99/100 and its
  means equal the canonical record-derived means **exactly in 193/193 comparable cells**.
- The signed-contrast chain that produced `blinding_signed_contrasts.csv` did **not**
  read this file; it read the stale mirror records directly (`load_paired_means`).
- A second frozen chain DID read it literally: `scripts/twin2k10/signed_effects_run.py`
  `main()` line 380 loads `llm_arm_means.json` (blinded only) and builds
  `signed_contrast_effects_REPAIRED.csv` / `final_signed_contrasts.csv`. That lineage
  is stale for the same 9 models and additionally has no unblinded leg at all.

Corroboration within the 139 mismatches: 69 blinded cells match llm_arm_means.json's
stale means to <1e-6 (double evidence); the 70 unblinded cells have no llm-file entry
(file is blinded-only) and are proven by the alt-record rebuild alone.

## 4. Per-cell classification (all 145 mismatches — MISMATCH_CLASSIFICATION.csv)

| Cause class | Cells | Definition |
|---|---|---|
| `stale_value` | **139** | Frozen value reproduces exactly from the fos-data mirror; canonical records give a different value. 69 blinded (llm-file corroborated) + 70 unblinded. **13 of the 139 flip sign** (direction_changed=True). |
| `missing_arm_alt_snapshot_exclusion` | **6** | No frozen value exists: the mirror's incomplete arm coverage made `build_rows()` drop the row (its "incomplete arm coverage: skip" rule, line 186-188). Canonical records DO yield a value for these. |
| extraction_error | 0 | No cell requires a different response-field interpretation to explain the gap. |
| scale_conversion_error | 0 | All gaps reproduce at raw 0-1 normalization with frozen min/max; no rescaling involved. |
| other | 0 | — |

The 139 stale cells concentrate exactly in the 8 run10 experiments (allais, abs_relative,
anchoring_african, anchoring_redwood, linda, myside, outcome_bias, prob_matching) × the
9–11 stale models listed above. All run6 cells match (mirror complete for run6).

## 5. The 530-vs-524 coverage difference, precisely

- `blinding_signed_contrasts.csv` has 270 wide (model, experiment, contrast) rows minus
  **8 anchoring rows dropped** by the frozen pipeline = 262 wide × 2 blinding legs = **524** cells.
  The 8 dropped rows: anchoring_african + anchoring_redwood for {qwen3-4b, gemma-4-26b-a4b,
  gemma-4-31b-it-qat, granite-4.1-30b} — the mirror's anchoring arms were empty/incomplete
  for those models (documented in `stage3_methodology/ROW_RECONCILIATION_NOTES.md`).
- The Stage 9/10 audit grid is the same 270 wide rows × 2 legs = 540, minus **10 cells that
  are empty even in the canonical records** = **530** audited cells.
- The **6 extra** audit cells = anchoring cells the frozen pipeline dropped (because the
  mirror lacked them) but canonical records can score:
  qwen3-4b anchoring_redwood B; granite-4.1-30b anchoring_redwood B (only 3/100 valid
  outcomes even canonically); gemma-4-31b-it-qat anchoring_african B; qwen3-4b
  anchoring_african B (98/100); granite-4.1-30b anchoring_african B (92/100);
  gemma-4-26b-a4b anchoring_african U (90/100). Recalc values for these six are in
  MISMATCH_CLASSIFICATION.csv with `cause_class=missing_arm_alt_snapshot_exclusion`.

## 6. Anchoring scoring detail (explicit zero vs omitted key — spec requirement)

`record_outcome()` for anchoring returns `p_norm.get("A")` → None when the key is
missing **or null**; that outcome is *excluded*, never scored as zero. Verified example:
`T2K10-.../qwen3-4b/anchoring_redwood_unblinded/records.jsonl` — all 100 high-arm records
carry `p_norm["A"] = null` (key present, value null), while the blinded leg of the same
model/experiment has real A values on all 200 records. So the canonical empty anchoring
arms are a leg-specific first-token-mass degeneracy, **not** explicit zero-probability
answers and **not** data loss. Any rebuild must keep treating null/omitted A as missing.

## 7. The 385 "matches" are genuine

Each match required |rebuild − frozen| < 1e-6 using the frozen scoring module verbatim
(same `record_outcome`, same normalization registry, same anchor handling) on
SHA-verified canonical records — the same definition both sides. 193 of the 385 also
have an llm_arm_means.json entry, and all 193 llm means equal the record-derived means
exactly. No coincidental equality mechanism exists (values are long floats).

## 8. Propagation chain (what inherits the wrong values)

1. **fos-data mirror** (stale, 2026-09-23) + **llm_arm_means.json** (built from it, 2026-10-07)
2. → `final_audit/blinding_signed_contrasts.csv` (2026-10-12, from mirror records)
   and `final_signed_contrasts.csv` / `signed_contrast_effects_REPAIRED.csv` (from llm_arm_means.json)
3. → `agreed_figure_code_package/data/blinding_signed_contrasts.csv` (2026-10-14; byte-identical,
   sha256-16 `c2fdb506c03768c2`) — Stage 3 freeze
4. → `stage5_exploratory/data/stage5_dataset.csv`: **verified** that for all 524 original
   rows `y_std × sd_human_pooled_pp` equals the frozen d_m exactly (median residual 0.0);
   `se0` zero-fill is a missing-value sentinel
5. → Stage 9 `MODEL_SE_BOOTSTRAP_DRAFT.csv` / regression inputs (145 flagged cells)

## 9. Unresolved items (stated honestly)

1. **Intent**: whether the canonical tree (Documents/…) or the fos-data mirror was meant
   to be authoritative cannot be decided from files alone; the canonical tree is complete,
   hash-consistent with the Stage 2 manifest, and post-dates the mirror — rebuild should
   use canonical, but an owner should confirm the mirror can be retired/re-synced.
2. The 4 model×experiment anchoring arms empty in canonical data (10 cells) are a real
   data limitation, not fixable by rebuild (leg-specific `p_norm["A"]=null` mass).
3. `signed_effects_run.py` lineage (REPAIRED tables, figures fed by them) was built from
   the blinded-only stale means; quantifying every downstream figure number inherited from
   that file was out of scope here and should be checked during rebuild.
4. granite-4.1-30b anchoring_redwood blinded yields only 3/100 valid outcomes even from
   canonical records — worth a look before that contrast is re-frozen.
