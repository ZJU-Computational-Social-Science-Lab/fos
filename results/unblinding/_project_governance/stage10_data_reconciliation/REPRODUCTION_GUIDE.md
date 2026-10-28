# REPRODUCTION_GUIDE — how to rebuild and verify the Stage 10 canonical
# dataset (`reconciled_v1`) from the raw inference records.

## What this package is

A deterministic pipeline that replaces the stale intermediate summaries
with canonical tables rebuilt straight from the raw records:

raw records → registered response coding → arm outcomes → registered
treatment-minus-control contrasts → standardisation by the frozen human
pooled SD → canonical tables; plus corrected persona-bootstrap
uncertainty, a validating loader, provenance manifests, and tests.

Version id: `reconciled_v1`.

## Layout

- `scripts/` — the pipeline code (see below).
- `data/` — the promoted canonical tables (never edited by hand):
  - `CANONICAL_ARM_OUTCOMES.csv` — one row per contrast x model x leg
    (native pp + std effect, SEs, per-cell record accounting, zero-
    probability notes).
  - `CANONICAL_MODEL_EFFECTS.csv` — the analysis-facing effects table.
  - `MODEL_EFFECT_UNCERTAINTY_CORRECTED.csv` — bootstrap SEs per cell.
  - `CANONICAL_PAIRED_ANALYSIS.csv` — Stage 5-equivalent paired table
    with the new uncertainty (`se_y_std_*`).
  - `OLD_VS_CORRECTED_EFFECTS.csv` — row-by-row comparison with the old
    Stage 5 dataset.
- `provenance/CANONICAL_DATA_MANIFEST.json` — input/output SHA-256
  hashes, seed, draws, code version, coverage report.
- `provenance/DATASET_REGISTRY.json` — the approved-version pointer.
- `tests/` — pytest suite (33 tests).

Scripts:
- `stage10_common.py` — paths, frozen inputs, seed (20261028), helpers.
- `originals_scoring.py` — original-14 legs from run6/run10 records,
  reusing the validated T2K10 final-audit outcome rules.
- `expansion_scoring.py` — expansion legs via the frozen expansion
  production pipeline modules.
- `frozen_check.py` — hard gates vs the frozen Stage 3 references.
- `rebuild_model_effects.py` — the pipeline entry point.
- `canonical_tables.py` — table assembly + fail-fast validation.
- `compare_effects.py` — OLD_VS_CORRECTED builder.
- `canonical_data.py` — the supported loader (use this in analyses).
- `verify_integrity.py` — standalone SHA-256/schema verifier.

## Full rebuild (end-to-end)

```bash
cd _project_governance/stage10_data_reconciliation
python3 scripts/rebuild_model_effects.py     # ~10 min; streams all records
python3 scripts/verify_integrity.py          # all checks must PASS
python3 -m pytest tests -q                   # 33 tests must pass
```

The build is atomic: everything is written to a temp directory,
validated, then promoted into `data/` + `provenance/`. A failed run
never leaves partial authoritative tables.

Determinism: the same inputs give byte-identical tables. Bootstrap
seeds are derived deterministically per cell
(`sha256("20261028|contrast|model|blinding")`), 2000 draws each; two
consecutive full runs were verified byte-identical.

## Using the data in analyses

```python
import sys; sys.path.insert(0, "scripts")
from canonical_data import load_model_effects
df = load_model_effects(version="reconciled_v1", require_verified=True)
```

The loader resolves the approved version from the registry, verifies
manifest hashes and schema/keys, and raises `CanonicalDataError`
instead of ever falling back to Stage 5 files or stale caches.

## Raw-record sources (read-only, hashed in the manifest)

- Originals run6: `TWIN2K_UNBLINDING_LOGPROBS_6TASKS-20260919T025143`
- Originals run10: `T2K10-20260923T034851` (2026-10-05 completed state)
- Expansion: `expansion/work/T2KX-20261022T222604` (via the frozen
  `pipeline` package)

## Known documented exception (important)

The frozen 262-row file was computed from the 2026-10-04 state of the
run10 records. The canonical project root holds the 2026-10-05
completed re-run; 139 run10 cells differ in value and 6 anchoring cells
were completed. All are kept in the canonical data and reported
row-by-row in `OLD_VS_CORRECTED_EFFECTS.csv` (columns
`mismatch_reason`, `verification_status`, `coverage_status`). Run6 legs
and ALL expansion contrasts match the frozen references exactly
(1e-8). A parallel root-cause investigation is examining the run10
re-run history; its findings should be reconciled with this table.

Item classification: run6 originals = verified; expansion =
unchanged + independently verified (all 20 contrasts re-derived from
raw records to 1e-8); run10 originals = corrected + verified (raw
records are authoritative; frozen values documented as superseded);
anchoring inclusion policy = preserved unchanged; howard823
unestimable cells = preserved-but-deprecated (stay missing); nothing
unresolved.
