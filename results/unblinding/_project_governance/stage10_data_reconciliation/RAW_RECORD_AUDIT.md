# RAW_RECORD_AUDIT.md — Stage 10 raw record inventory (TASK-3008)

## What this file is
A plain-language audit of every raw model-response record used by the unblinding
study: where each file lives, its SHA-256 checksum, how many responses it holds,
and whether those counts match the registered totals. Nothing here was modified —
all frozen files were only read and hashed.

## Headline counts (verified by direct recount, not trusted from prior docs)

| Run | Study records | Preflight records | records.jsonl files | Status |
|---|---|---|---|---|
| run6 (`TWIN2K_UNBLINDING_LOGPROBS_6TASKS-20260919T025143/`) | **47,520** | 480 (120 files, `PREFLIGHT/` category) | 240 study + 120 preflight = 360 | matches Stage 1 inventory |
| run10 (`T2K10-20260923T034851/`) | **57,000** | 0 | 300 (15 models × 20 legs) | matches |
| expansion (`expansion/work/T2KX-20261022T222604/`) | **309,000** | 0 | 510 (15 models × 34 legs) | matches |
| **Total** | **413,520** | 480 | 1,170 | ✓ exact |

- Every one of the 1,170 files was SHA-256 hashed successfully; **zero hash failures**.
- Every record line parsed as JSON; **zero unparseable lines, zero `succeeded=false` records**.
- Per-file detail (path, sha256, size, mtime, n records, unique personas, failed count,
  record fields) is in **RAW_RECORD_MANIFEST.json**; the study-file flat table is
  **RAW_RECORD_COVERAGE.csv** (1,050 rows = 240 + 300 + 510).

## Repeat structure (preserved, not collapsed)
- run6: 99 personas per arm; run10/expansion: 100 personas per arm. Each persona answers
  every arm of a leg (2–3 arms per experiment). Persona sharing across arms is by design
  (within-persona arm comparison), NOT a duplicate-record defect.
- Sampling config identical in every record of all three runs: temperature 1.0, top_k 100,
  scan_tokens 8, seed 42, first-token logprob mode (stored per-record under `inference`).
- One draw per (persona, prompt); no repeated draws exist anywhere.

## Auxiliary / provenance files hashed (see RAW_RECORD_MANIFEST.json → auxiliary_files)

| File | Role | SHA-256 (first 16) |
|---|---|---|
| `T2K10-.../final_audit/blinding_signed_contrasts.csv` | frozen per-contrast effects | `c2fdb506c03768c2` (byte-identical to agreed_figure_code_package copy) |
| `agreed_figure_code_package/data/blinding_signed_contrasts.csv` | Stage 3 frozen canonical | `c2fdb506c03768c2` |
| `T2K10-.../final_audit/blinding_effect_magnitude_analysis.py` | frozen analysis code | `1d07b908a7b81e95e` (matches FROZEN_ANALYSIS_MANIFEST code hash) |
| `T2K10-.../final_audit/FROZEN_ANALYSIS_MANIFEST.json` | freeze manifest (2026-10-12T16:25Z) | in manifest |
| `/home/justin/work/research/T2K10-FIGURES/llm_arm_means.json` | historical intermediate arm means | in manifest (mtime 2026-10-07 18:32) |
| `scripts/twin2k10/llm_arm_means.py`, `signed_effects_run.py` | intermediate-mean builder / signed-effect runner | in manifest |
| `stage3_methodology/ROW_RECONCILIATION.csv` (+NOTES) | Stage 3 row-level provenance (570 join keys) | in manifest |

## Known non-study data
- run6 `PREFLIGHT/` (120 files, 480 records): documented pilot data, excluded from all study counts.
- run10 `progress.json` is stale (documented in SOURCE_OF_TRUTH); irrelevant — counts verified by direct recount.

## Verdict
The raw record layer is complete, internally consistent, and hash-verified:
**413,520 study records exactly as registered**. The mismatches investigated in
ROOT_CAUSE_ANALYSIS.md originate DOWNSTREAM of these records (a stale path mirror),
not in the records themselves.
