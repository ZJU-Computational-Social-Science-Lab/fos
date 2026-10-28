# Corrected-rerun conventions (Stage 10 downstream, TASK-3014)

Applies to every stage recalculated from `reconciled_v1` canonical data.

## Absolute rules
- NEVER modify anything under the frozen stage dirs in UNBL (`stage3_results/`,
  `stage4_figures/`, `stage5_exploratory/`, `stage6_direction_and_disclosure/`,
  `stage7_replication_evidence/`, `stage8_shared_failures/`,
  `stage9_explanatory_regression/`) or the canonical `data/` files.
  Read them freely; write nothing into them.
- ALL corrected outputs go to `corrected_results/stageN/` (e.g. `corrected_results/stage5/`),
  mirroring the file names of the frozen originals where comparable.
- Statistical definitions, estimators, priors, seeds, model specs are IDENTICAL to the frozen
  runs. Only the input data differs: canonical `reconciled_v1` instead of stale intermediates.
  Do not "improve" any estimator while porting. If a frozen script can be imported and reused
  as-is, do that; copy-and-patch only path constants.

## Inputs (canonical, under UNBL/_project_governance/stage10_data_reconciliation/data/)
- `CANONICAL_MODEL_EFFECTS.csv` — 1119 rows, one per contrast x model x blinding leg:
  model_effect_pp / model_effect_std (corrected), model_effect_se_pp / model_effect_se_std
  (corrected bootstrap SE), human_effect_std, sd_human_pooled_pp, source_version.
- `CANONICAL_PAIRED_ANALYSIS.csv` — one row per contrast x model with BOTH legs
  (y_std_blinded / y_std_disclosed and corrected SEs), plus human columns.
- `MODEL_EFFECT_UNCERTAINTY_CORRECTED.csv` — per-cell bootstrap SE detail.
- `OLD_VS_CORRECTED_EFFECTS.csv` — old vs new per cell; use to verify what changed
  (139 value corrections, all run10 original14 cells; 6 `coverage_status=new_only` cells;
  13 direction changes).

## Outputs per stage
- The recalculated tables, named as the frozen originals (e.g. `posterior_summary.csv`).
- `stageN_CHANGES.md` — short: what changed numerically vs frozen (with key numbers),
  what did not, and any handling of the 6 `new_only` cells (include only where natural; flag
  comparability impact either way).
- Bayesian fits: record convergence (max R-hat, min bulk ESS) and PPC/LOO where the frozen
  run recorded it, in the same format, plus a one-line diagnostics note in stageN_CHANGES.md.

## Environment
- `python` has numpy/pandas/jax/numpyro/arviz/scipy/matplotlib. Set
  `MPLCONFIGDIR=/tmp/mplcache` if figures are made.
- UNBL = `/home/justin/Documents/ZJU work/fos/results/unblinding/` (read-only).
- OUT = `/home/justin/work/worktrees/implement-3014/_project_governance/stage10_data_reconciliation/`
  (all writes here).
- Seeds: keep every frozen seed constant (e.g. Stage 5 SEED_MAIN 20261027, Stage 6
  SEED_DIRECTION 20261101, Stage 3 bootstrap seeds 20261010/20261013).

## Files
- Every new script needs a plain-language header comment (what the file does, what each
  function does). Keep scripts under `corrected_results/stageN/scripts/`.
- Report concrete numbers in stageN_CHANGES.md — real estimates and intervals, not prose.
