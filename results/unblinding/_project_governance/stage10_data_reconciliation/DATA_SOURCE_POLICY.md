# DATA_SOURCE_POLICY.md — which numbers win when sources disagree

Authority hierarchy for every quantitative claim in this project,
from the Stage 10 brief. A lower-numbered level always overrides a
higher-numbered one. Old intermediates (e.g. `llm_arm_means.json`)
never override raw records plus registered definitions.

## Level 1 — Raw inference records (highest authority)
Hash-frozen per-run record files: `T2K10-*/<model>/<experiment>_<leg>/
records.jsonl`, `TWIN2K_UNBLINDING_LOGPROBS_6TASKS-*/…`,
`R1-*/…`, plus `RAW_RECORD_MANIFEST.json` and
`RAW_RECORD_COVERAGE.csv` in `_project_governance/
stage10_data_reconciliation/`. These are the only source of what any
model or human actually produced. Note: run10 experiments exist in two
record states (2026-10-04 and the 2026-10-05 re-run); the manifest
pins which state each computation used, and the 2026-10-05 re-run is
authoritative.

## Level 2 — Registered experiment definitions
`_project_governance/stage3_methodology/CONTRAST_REGISTER.csv`,
`experiment_registry.json`, `expansion/pipeline/registry.py`, and the
frozen fingerprints (`expansion/work/T2KX-*/fingerprint.json`).
These define treatments, controls, outcome scales and directions.
Data never redefines a registered contrast.

## Level 3 — Canonical reconciled dataset (reconciled_v1)
`_project_governance/stage10_data_reconciliation/data/`:
`CANONICAL_ARM_OUTCOMES.csv`, `CANONICAL_MODEL_EFFECTS.csv`,
`CANONICAL_PAIRED_ANALYSIS.csv`, `MODEL_EFFECT_UNCERTAINTY_CORRECTED.csv`,
with the per-cell audit trail in `OLD_VS_CORRECTED_EFFECTS.csv`
(974 exact / 139 corrected / 6 new-only). Built only from Levels 1–2.
All corrected stage analyses read exclusively from here.

## Level 4 — Frozen stage outputs (historical record, never edited)
`_project_governance/stage3_results/`, `stage5_exploratory/`,
`stage6_direction_and_disclosure/`, `stage7_replication_evidence/`,
`stage8_shared_failures/`, `stage9_explanatory_regression/`,
`stage4_figures/`, and `figures/`. Useful for before/after comparison
and provenance; superseded numerically wherever Level 3 disagrees
(corrected numbers live in `corrected_results/`, never by overwriting
these).

## Level 5 — Corrected stage outputs (current scientific numbers)
`stage10_data_reconciliation/corrected_results/stage3…stage9/` and
`corrected_figures/` (with `FIGURE_CHANGE_LIST.csv`), summarized in
`SCIENTIFIC_RESULTS_BEFORE_AFTER.md` and `RESULTS_CHANGELOG.csv`.
Any manuscript or report claim must match these (or Level 4 where the
correction confirmed it unchanged).

## Level 6 — Legacy intermediates (never authoritative)
`stage5_exploratory/data/stage5_dataset.csv` (stale for the 139 run10
cells), the fos-data mirror (`llm_arm_means.json` etc., which
reproduces all 524 frozen values and is therefore a witness to the
stale 2026-10-04 state, not a source of truth), `grid.pkl`, `mm.pkl`,
and anything under a `work/` scratch directory. Never feed these into
a new analysis; they exist only to explain what happened.

## Level 7 — Prose, summaries, and slide decks (lowest authority)
`EXECUTIVE_SUMMARY.md`, stage `EXECUTIVE_SUMMARY.md`/`*_RESULTS.md`/
`DRAFT_*.md` files, `PROJECT_AUDIT.md`, and any manuscript text.
These must be derivable from Levels 3–5; whenever they conflict with a
number above, the number wins and the prose is corrected.

## Enforcement
The corrected stage scripts fail fast: they assert row counts (1119
canonical cells, 553 pairs), per-contrast coverage (C-13/C-14 = 11,
C-32 = 10, C-33 = 11), `source_version == reconciled_v1`, and fixed
seeds before running. Any future pipeline must load through the same
canonical loader and manifest checks — never from Level 6 paths.
