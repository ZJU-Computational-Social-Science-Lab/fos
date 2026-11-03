# IMPLEMENTATION_SUMMARY.md — TASK-3128 Stage 0 GREEN (rebuild of twin2k10r)

## Summary
Rebuilt `scripts/twin2k10r/` from scratch against the REPAIRED test suite (branch `task/3127`).
**Full GREEN: 72/72 tests/twin2k10r passed** (including the real-mirror tests against the
2,058-respondent panel) + **132 historical regression tests passed** (204 total, 0 failed).
All Stage 0 deliverables built under `scripts/twin2k10r/runs/STAGE0/` and mirrored durably to
`/home/justin/work/crew/OUTBOX-STAGING/twin2k10r/`. No inference ran; no historical
pipeline/results/manuscript file was edited.

## Changes made
- `scripts/twin2k10r/__init__.py` — package marker.
- `scripts/twin2k10r/config.py` — DATASET_ROOT, SEED 42, PERSONA_COUNT 100, POOL_CONFIG "A".
- `scripts/twin2k10r/dataset_manifest.py` — SHA-256 per consumed file; write/verify/manifest_sha256;
  `DatasetHashMismatch` on any change/absence. Manifest file can live in the run dir (dataset
  mirror is read-only).
- `scripts/twin2k10r/respondent_loader.py` — label-CSV loading (verbatim dataset labels), 7-field
  Config A whitelist + 11 Config B scores (always joined; map_fields filters by whitelist);
  `UnknownFieldError` / `MissingDemographicsError` naming pids; blocklist enforced.
- `scripts/twin2k10r/pool_builder.py` — deterministic stratified sampling (sex×age, largest
  remainder, PCG64 seed 42, without replacement, sorted), provenance replay
  (`sample_respondents_from_provenance`), `map_fields` (exact whitelist, verbatim values, excluded
  4 fields absent), idempotent `write_pool` (JSONL + POOL_PROVENANCE.json with seed, RNG name,
  pids, stratum membership, hashes, git SHA, whitelist, excluded-field reasons).
- `scripts/twin2k10r/prompts.py` — twin2k10's pinned scaffold reused byte-identical
  (BLINDED_SYSTEM_LINE, UNBLINDING_PARAGRAPH, VERSIONS_HEADER, FINAL_INSTRUCTION,
  NUMERIC_INSTRUCTION, PERSONA_FIELDS order); own renderer (renders all 7 real fields — the
  documented correction to "prompts.py reused verbatim"; Config B adds MEASURED TRAITS block).
- `scripts/twin2k10r/serving.py` — `ensure_pool` (provenance-gated, idempotent, ZERO model calls)
  and `load_pool` (size + whitelist assert). The twin2k10 health/unload helpers were NOT copied:
  they `import urllib`/`socket`, and the suite bans any network import in the persona path.
- `scripts/twin2k10r/validate_pool.py` — 7 gates with specific error classes; `run()` writes
  VALIDATION_REPORT.md, returns non-zero on any failure, never warns-and-continues.
- `scripts/twin2k10r/example_prompts.py` — 10 anonymized rendered prompts (both arms; choice,
  rating, numeric; uninformed + informed_with_versions; Configs A and B; real pid → pool id).
- `scripts/twin2k10r/build_stage0.py` — builds both pools, validates both, writes the docs.
- `scripts/twin2k10r/runs/STAGE0/` — pools (A + B), POOL_PROVENANCE.json ×2,
  dataset_manifest.json ×2, VALIDATION_REPORT.md ×2 (all PASS), PROMPT_EXAMPLES.md,
  EXPERIMENT_COMPATIBILITY.md, PILOT_PLAN.md (revised copy; original untouched).
- `tests/twin2k10r/` — copied the REPAIRED suite from `~/work/worktrees/test-3127` verbatim
  (test files are LOCKED; not modified by me).
- `IMPLEMENTATION_SUMMARY.md` (this file).

## Key artifacts
- Config A pool sha256: `bdc842334a71aa61f20797f778d77cad1eefd772dec08e4498d4e357f447eea1`
  (100 pids, seed 42, PCG64; sex×age max marginal gap 0.41 pp — within the ±1 rounding unit).
- Config B pool sha256: `766322890547…` (full 64-hex in POOL_PROVENANCE.json).
- Validation: both configs PASS all gates (report in `runs/STAGE0/pools/` and
  `runs/STAGE0/config_B/pools/`).

## Test result
- `pytest tests/twin2k10r` → **72 passed, 0 failed, 0 skipped** (the one `importorskip` test
  became real because the mirror is present).
- Historical suites (RESULT-3127 list) → **132 passed**.
- Combined run: **204 passed, 0 failed**.

## Regressions
None. No file outside `scripts/twin2k10r/`, `tests/twin2k10r/` (copied in), and the two root-level
summaries was touched. Historical `scripts/twin2k10/` is byte-identical.

## Outstanding concerns
1. **Repo .git is read-only — nothing was committed.** Durability is via the mirror:
   `/home/justin/work/crew/OUTBOX-STAGING/twin2k10r/` (full tree, relative paths preserved).
2. **Dataset mirror is read-only**, so `dataset_manifest.json` is stored in the run directory
   (not inside the dataset root as the 2026-11-03 IMPLEMENTATION.md sketch assumed). The manifest
   hash still enters the provenance chain unchanged.
3. **Doc error confirmed** (as flagged in TASK-3128): "prompts.py reused verbatim" is wrong —
   `twin2k10r/prompts.py` must differ (renders all 7 fields, adds MEASURED TRAITS for B).
   CORRECTED_DESIGN/IMPLEMENTATION should be amended by an owner; I did not edit historical docs.
4. **Sex×age gap is 0.41 pp on the real panel** (largest-remainder seats vs exact shares), not
   exactly 0 as CORRECTED_DESIGN §3 idealized; the report states this honestly. The repaired
   suite's exact-zero test runs on the fixture (single age bracket) where it is exactly 0.
5. The 31/38 full-grid registry's expansion component is absent from this worktree;
   EXPERIMENT_COMPATIBILITY.md claims only the demonstrable 10 experiments / 9 contrasts.
