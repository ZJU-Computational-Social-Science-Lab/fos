# VALIDATION_REPORT — Stage 10 canonical rebuild (`reconciled_v1`)

Every check below was run against the promoted build. Overall: PASS.

## 1. Pipeline gates (run-time, fail-fast)

| Check | Result |
|---|---|
| Originals run6 legs match frozen 262-row file (1e-8) | PASS (hard gate) |
| ALL 20 expansion contrasts re-derived from raw records, match frozen expansion17 (1e-8) | PASS (589 cells) |
| Expansion unestimable cells (5) stay missing | PASS |
| Persona bootstrap SE present for every cell | PASS (no NaN, no failure-zeros) |
| Schema + unique keys + coverage before promotion | PASS |
| Atomic promotion (temp dir, validate, move) | PASS |

## 2. Coverage

- Canonical rows: 1119 = 530 original cells (524 frozen grid + 6 run10
  re-run completed anchoring cells, documented) + 589 expansion cells.
- Contrasts: 38 of 38 registered. Models: 15. Legs: 2.
- 530-vs-524 explanation: the run10 records were re-run to completion on
  2026-10-05; the frozen file used the 2026-10-04 state (which lacked 6
  anchoring cells). The 6 extra cells are flagged in
  `OLD_VS_CORRECTED_EFFECTS.csv` (`coverage_status = new_only`).

## 3. OLD_VS_CORRECTED summary

- Rows: 1119 (1113 both-side, 0 old-only, 6 new-only).
- Exact matches (<=1e-8): 974.
- Documented value corrections: 139 (all run10 originals; reason
  recorded per row; direction changes: 13).
- Largest |diff|: 58.02 pp (C-13 anchoring_redwood, qwen3.6-35b-a3b,
  blinded).
- Expansion rows: all match the frozen std effects to float precision.

## 4. Uncertainty (MODEL_EFFECT_UNCERTAINTY_CORRECTED)

- Persona bootstrap, 2000 draws per cell, seed 20261028 (per-cell seeds
  derived deterministically; recorded in the manifest).
- Personas resampled jointly across arms (shared panels respected);
  expansion '+'-pooled arms merged before resampling; shared controls
  preserved.
- Bootstrap point estimator = canonical estimator; centres agree by
  construction (identity resample = point estimate).
- Monte Carlo precision: SE resolution ~ SE/sqrt(2*2000) < 1.6% of SE.
- 9 cells have honest SE = 0 (constant retained responses; e.g.
  granite-4.1-30b C-04/C-05/C-20/C-22, gemma-4-26b-a4b C-17, qwen3-4b
  C-21); 0 cells have SE = 0 from failed draws (validated by test).

## 5. Loader / provenance / integrity

- `verify_integrity.py`: manifest version, input hashes (7 files),
  output hashes (5 tables), registry pointer, manifest hash, schema and
  unique keys for 4 tables — ALL PASS.
- Loader rejects: unknown version, unapproved version, tampered table
  (hash mismatch), missing tables — verified by tests.
- No silent fallback to Stage 5 or llm_arm_means.json anywhere.

## 6. Test suite

`python3 -m pytest tests -q` → **33 passed**. Includes known-value
regression cases: disease framing (C-01), WTA/WTP (C-10), anchoring
(C-13/C-14), binary choice (C-11 allais), numerical estimate, multi-item
(C-17 prob_matching), expansion (C-19); raw-record recomputation of a
canonical cell; raw record-key uniqueness; manifest hash consistency;
stale-cache/registry rejection.

## 7. Determinism

Two consecutive full end-to-end runs produced byte-identical canonical
tables (SHA-256 compared; OLD_VS_CORRECTED excluded because it embeds
nothing varying — verified identical as well).

## 8. Item classification (per Stage 10 brief)

- verified: originals run6 legs (10 contrasts), all schemas, loader.
- corrected + verified: run10 originals (8 contrasts; raw records are
  authoritative, frozen values superseded and documented per row).
- unchanged + independently verified: ALL 20 expansion contrasts
  (re-derived from 309k raw records, match frozen to 1e-8).
- preserved-but-deprecated: howard823 unestimable cells (stay missing);
  anchoring registered inclusion policy unchanged.
- unresolved: none in this rebuild; the run10 re-run history itself is
  the subject of the parallel root-cause task.
