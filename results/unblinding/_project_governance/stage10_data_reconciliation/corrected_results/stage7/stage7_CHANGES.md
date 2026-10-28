# stage7_CHANGES.md — what the corrected effects change in the
# replication-evidence audit (contrast-level direction agreement)

## What was rerun
The frozen Stage 7 scripts (`30_contrast_audit.py`, `40_screening.py`,
`50_qa_counts.py`) were rerun unchanged — same register, same Stage 6
human-direction confidence convention (Pr(d_h>0) outside (.025,.975)),
same screening rules, no randomness — on the 553-pair canonical paired
table (`reconciled_v1`) instead of the stale Stage 5 dataset. Pair
coverage is identical per contrast (C-13/C-14: 11 pairs, C-32: 10,
C-33: 11), so the C-32 coverage convention is preserved exactly; the 6
`new_only` cells are single-leg and never enter the paired table.
Human-side quantities (d_h, SE, Pr(d_h>0)) are unchanged by the
reconciliation, so the confident/uncertain split is untouched.

## Explicit revisits (C-03, C-09, C-16, C-26, C-30, C-31, C-37)
All seven keep their frozen disagreement class:

| contrast | class (frozen = corrected) | agree B/D frozen | agree B/D corrected |
|---|---|---|---|
| C-03 | majority_wrong_disclosed | 11/5 | 11/5 |
| C-09 | majority_wrong_both | 7/5 | 7/5 |
| C-16 | majority_wrong_blinded | 7/8 | **5/10** |
| C-26 | majority_wrong_both | 4/2 | 4/2 |
| C-30 | majority_wrong_both | 5/7 | 5/7 |
| C-31 | majority_wrong_blinded | 6/8 | 6/8 |
| C-37 | majority_wrong_both | 3/6 | 3/6 |

Only C-16 moves numerically (blinded agreement 0.47→0.33, disclosed
0.53→0.67) — the correction made the blinded majority MORE wrong while
the disclosed leg flipped to a (still slim) majority correct. Its class
and the Stage 6 KEEP verdict are unchanged.

## Headline counts, frozen → corrected
- confident 32 / uncertain 6 (C-17, C-27, C-28, C-33, C-34, C-36): unchanged.
- disagreement candidates: same 7 contrasts, same class distribution
  (4 majority_wrong_both, 2 majority_wrong_blinded, 1 disclosed).
- pooled direction agreement blinded: 349/467 = 0.747 → **350/467 = 0.749**.
- pooled direction agreement disclosed: 339/467 = 0.726 → **341/467 = 0.730**.
- agreement comparisons: C-13 drops out (its corrected blinded agreement
  falls to 10/11 = 0.909, ranking below cutoff) and is replaced by
  C-12 (linda, worst-leg 14/15 = 0.93, |d_h| = 0.83). The other five
  picks (C-15, C-23, C-24, C-29, C-14) are unchanged.
- coding checks: no contrast fails; the same orientation-check notes
  (C-09/C-10, C-03, C-37 shared-control siblings) appear as before.
- Stage 6 candidate re-evaluation: identical verdicts (C-26, C-30,
  C-31, C-16, C-03 KEEP; C-02, C-36, C-27, C-17 DROP).

## Files
`DISAGREEMENT_AUDIT.csv`, `EXPERIMENT_ROLLUP_SECONDARY.csv`,
`SCREENING.csv`, `STAGE6_CANDIDATE_REEVALUATION.csv`,
`scripts/corrected_stage7.py` (patched loader + output dir),
`scripts/50_qa_counts.py` (byte-identical copy of the frozen checker,
run against the corrected CSVs).
