# Manuscript Corrections — TVD 572/660 reconciliation

**Verdict: NO CORRECTIONS REQUIRED.**

Checked 2026-11-10 against `/home/justin/Documents/Large Scale LLM
Experiment/Paper/`.

## Evidence

1. **No stale count in the manuscript.** `grep -rn "572" --include="*.tex"`
   over the `Paper/` tree returns **zero matches**. The 572-vs-660
   confusion exists only in analysis-side reports/docstrings
   (`MODEL_SPECIFICATION.md`, `BAYESIAN_TVD_RESULTS.md` line 33,
   `write_reports.py` strings) — outside the manuscript.

2. **S11 states 660 and is accurate.** `Supplementary/Supplementary.tex`
   line 257 reads: "660 matched cells in the frozen Bayesian analysis
   (11 expansion experiments × 2 information conditions × 2 contrast
   legs × 15 models)" — exactly matching `matched_cells.csv`
   (660 rows; 15/11/2/2 structure, re-verified).

3. **Filtering description verified against code.** S11's frozen scoring
   rules — first-token branch mass ≥ 0.80 inclusive; exact support match
   else exclude (no re-binning); Twin-2K arms pooled by averaging within
   information condition — match the producer logic in
   `implement-3377/analysis/final15_*`.

4. **Headline numbers reproduce from saved draws**
   (`posterior_ratio_draws.csv`, 8,000 draws):
   TVD 0.4007 [0.3887, 0.4130]; floor 0.0238 [0.0231, 0.0244];
   ratio 16.9 [16.2, 17.6]; P(>10) = 1.000; condition ratios 16.9/16.9;
   per-model range 12.9 (Qwen3.8-27B) – 21.4 (Gemma 4 26B).

5. **Floor/disclosed-limitation text verified** (see
   `TVD_METHOD_AUDIT.md`): same-11-experiments respondent-level floor,
   72,776 respondents, correlation −0.009, worst-case bound 17.40,
   partial coverage disclosed — all consistent between S11, methods.tex,
   and the artifacts.

## Non-manuscript cleanup (deferred, doc-only)

When analysis reports are next regenerated, replace "572" with "660" in:
- `MODEL_SPECIFICATION.md` (lines 6, 8, 10)
- `BAYESIAN_TVD_RESULTS.md` line 33
- `write_reports.py` report strings and `build_dataset.py` docstring
(worktree `implement-3377`, `analysis/final15_bayesian_tvd/`).

No manuscript, output, or analysis code was modified by this task.
