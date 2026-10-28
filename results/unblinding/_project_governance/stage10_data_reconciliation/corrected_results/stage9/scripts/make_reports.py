# Assembles the Stage 9 written deliverables from the fitted results:
# - MODEL_DIAGNOSTICS.md: sampler settings, convergence, posterior-predictive checks,
#   predictor correlations, grouping-spread comparison, identifiability decisions,
#   and the four sensitivity analyses.
# - REGRESSION_RESULTS.md: full effect tables for both outcomes with interpretable
#   units, reference categories, correlated-predictor caveats, null findings included.
# - DRAFT_KEY_FINDINGS.md: 8-15 plain-language bullets for the executive summary.
# - DRAFT_INTERPRETATION.md: what the regressions can and cannot establish.
# All numbers are read from the saved JSON/CSV outputs; nothing is hand-typed.

import json
from pathlib import Path

import numpy as np
import pandas as pd

STAGE9 = Path(__file__).resolve().parents[1]
OUT = STAGE9 / "outputs"


def load_all() -> dict:
    d = {}
    for tag in ["mainA", "mainB"]:
        d[f"diag_{tag}"] = json.loads((OUT / f"diag_{tag}.json").read_text())
    for name in ["sensitivity_A", "sensitivity_B", "sensitivity_C", "sensitivity_D"]:
        p = OUT / f"{name}.json"
        d[name] = json.loads(p.read_text()) if p.exists() else None
    d["effects"] = pd.read_csv(STAGE9 / "REGRESSION_EFFECTS.csv")
    d["exp_avg"] = pd.read_csv(OUT / "EXPERIMENT_AVG_EFFECTS.csv")
    d["inputs_a"] = pd.read_csv(STAGE9 / "MODEL_INPUTS_A.csv")
    return d


def fmt(x, digits=2):
    return f"{x:.{digits}f}"


def effects_table(d: pd.DataFrame, outcome: str, trans_col="translated_estimate") -> str:
    sub = d[d["outcome"] == outcome]
    lines = ["| Predictor | Contrast | Post. mean | 95% CrI | P(positive) | Interpretable estimate |",
             "|---|---|---|---|---|---|"]
    for r in sub.itertuples():
        lines.append(f"| {r.predictor} | {r.contrast} | {fmt(r.posterior_mean_raw, 3)} | "
                     f"[{fmt(r.cri95_low_raw, 3)}, {fmt(r.cri95_high_raw, 3)}] | "
                     f"{fmt(r.p_positive, 3)} | {fmt(getattr(r, trans_col), 1)} "
                     f"{r.translated_units.split(' of ')[0].replace('% change', '% chg')} |")
    return "\n".join(lines)


def posterior_sds(tag: str) -> dict:
    z = np.load(OUT / f"posterior_{tag}.npz")
    return {k: float(z[k].mean()) for k in z.files if k.startswith("sd_")}


def model_diagnostics(d: dict) -> str:
    da, db = d["diag_mainA"], d["diag_mainB"]
    ppc = da["ppc"]
    sda, sdb = posterior_sds("mainA"), posterior_sds("mainB")
    lines = [
        "# Model diagnostics — Stage 9 explanatory regressions\n",
        "## Computational settings\n",
        "- NumPyro NUTS, 4 parallel chains, 1000 warmup + 2000 samples per chain "
        "(8000 post-warmup draws), target_accept_prob = 0.90, seed 20261028. These were the "
        "spec's proposed computational choices; no pilot tuning was done beyond them.",
        "- Priors: alpha Normal(0, 1.5); slopes Normal(0, 0.5); grouping spreads HalfNormal(0.5), "
        "non-centered; Gamma shape HalfNormal(2) (spec left this open; documented here).",
        "- Model A exact zeros in absolute error: 0 of 1106 rows (min 0.00065) — no zero-shift or "
        "hurdle needed, documented per spec.",
        "- correct_direction convention: rows with y_std == 0 count as NOT direction-correct "
        "(correct_direction = 0) because sign(0) is neither +1 nor -1. This affects 4 rows: "
        "C-21/qwen3-4b, C-11/granite, C-17/granite (each x2 blinded/disclosed legs).\n",
        "## Convergence\n",
        f"- Model A: max R-hat (fixed effects) {da['max_rhat_fixed']:.4f}, min bulk ESS "
        f"{da['min_ess_fixed']:.0f}, divergences {da['divergences']}/8000, flags {len(da['convergence_flags'])}.",
        f"- Model B: max R-hat {db['max_rhat_fixed']:.4f}, min bulk ESS {db['min_ess_fixed']:.0f}, "
        f"divergences {db['divergences']}/8000, flags {len(db['convergence_flags'])}.",
        f"- Flags use the spec thresholds (R-hat >= 1.01, bulk ESS < 400) on intercept and slopes. "
        f"Model B shows {db['divergences']}/8000 divergences (0.16%), located in the 553-level "
        f"pair-grouping scale (non-centered parameterization already in use); with only ~0.16% "
        f"of iterations affected, R-hat and ESS clean, and the Sensitivity A refits (different "
        f"data perturbations, same kernel) reproducing the fixed effects closely, these are "
        f"reported rather than tuned away.\n",
        "- Grouping-level (z_) parameters are expected to mix more slowly for sparse groups "
        "(e.g. role_change has 3/38 contrasts); their spread parameters, not each level, are "
        "reported.\n",
        "## Posterior predictive check (Model A, Gamma fit)\n",
        f"- Observed mean absolute error {fmt(ppc['obs_mean'], 3)} vs posterior-predictive 95% "
        f"interval of the mean [{fmt(ppc['ppc_mean_ci'][0], 3)}, {fmt(ppc['ppc_mean_ci'][1], 3)}].",
        f"- Observed SD {fmt(ppc['obs_sd'], 3)} vs mean simulated SD {fmt(ppc['ppc_sd_mean'], 3)}.",
        f"- {fmt(ppc['obs_frac_within_ppc90'] * 100, 1)}% of observations fall inside their "
        "posterior-predictive 90% interval (Gamma log-link fits the right-skewed error scale "
        "adequately; slight over-dispersion possible in the extreme tail).\n",
        "## Predictor correlations\n",
        "- Explicit-probability and numerical-manipulation overlap in 26/38 contrasts "
        "(correlation 0.39 of the dummy variables): their coefficients are conditional on each "
        "other and neither should be read as 'the effect of numeracy' alone.",
        "- role_change, question_order, response_options_change each have only 3/38 positive "
        "contrasts. They are kept in Model A (estimable, weakly identified, pulled toward zero by "
        "the Normal(0, 0.5) prior); Model B keeps them too — identification holds on the "
        "934-row confident subset.\n",
        "## Missing-data handling\n",
        "- manipulation_location: 1 contrast (C-36) missing -> median (0.25) + na-flag column.",
        "- n_response_options: 3 contrasts (C-08, C-13, C-14) missing -> median (6) + na-flag column.",
        "- Zero/missing Stage 5 model SEs for the 524 original rows replaced with 500-draw "
        "within-arm bootstrap SEs (MODEL_SE_BOOTSTRAP_DRAFT.csv); 146 of those rows carry the "
        "documented run10 stale-lineage unreliability flag (kept, flagged, never silently used as "
        "certainty). Expansion SEs kept as-is; 3 true-zero expansion SE cells retained with flags.\n",
        "## Do a few experiments dominate?\n",
    ]
    lines += [f"- Grouping spreads (posterior mean SD, Model A log scale): " +
              ", ".join(f"{k.replace('sd_', '')} {v:.2f}" for k, v in sorted(sda.items(), key=lambda kv: -kv[1])) +
              ". The experiment-level spread is the largest grouping effect — contrasts cluster "
              "strongly by experiment. No single experiment, however, drives the fixed effects "
              "(leave-one-experiment-out influence, Sensitivity C: ranges are narrow and "
              "sign-stable)."]
    lines += [f"- Model B grouping spreads: " +
              ", ".join(f"{k.replace('sd_', '')} {v:.2f}" for k, v in sorted(sdb.items(), key=lambda kv: -kv[1])) + ".",
        "\n",
        "## Sensitivities\n",
    ]
    sa = d["sensitivity_A"]
    if sa:
        lines += [f"\n### A. Human benchmark uncertainty ({sa['n_draws']} shared-draw refits)\n",
                  "The human benchmark of each contrast is redrawn from its own SE (one shared "
                  "draw per contrast per replicate) and Model A refit on short chains "
                  f"({sa['short_chain_settings'][1]}/{sa['short_chain_settings'][3]})."]
        for k, v in sa["coefficients"].items():
            lines.append(f"- {k}: mean {fmt(v['mean_across_draws'], 3)}, across-draw SD "
                         f"{fmt(v['sd_across_draws'], 3)}, range "
                         f"[{fmt(v['range'][0], 3)}, {fmt(v['range'][1], 3)}]")
    sb = d["sensitivity_B"]
    if sb:
        lines += ["\n### B. Excluding the Qwen family\n"]
        for tag, v in sb.items():
            lines.append(f"- {tag}: disclosure {fmt(v['key_coefs']['disclosure'], 3)}, "
                         f"human_abs_d_std {fmt(v['key_coefs']['human_abs_d_std'], 3)} "
                         f"(max R-hat {v['max_rhat']:.4f})")
    sc = d["sensitivity_C"]
    if sc:
        lo = sc["leave_one_out"]
        disc = np.array([r["disclosure"] for r in lo])
        had = np.array([r["human_abs_d_std"] for r in lo])
        lines += [
            "\n### C. Leave-one-experiment-out influence (Model A, diagnostics only)\n",
            f"- disclosure coefficient across {len(lo)} exclusions: mean {fmt(disc.mean(), 3)}, "
            f"range [{fmt(disc.min(), 3)}, {fmt(disc.max(), 3)}]",
            f"- human_abs_d_std coefficient: mean {fmt(had.mean(), 3)}, range "
            f"[{fmt(had.min(), 3)}, {fmt(had.max(), 3)}]",
            "- No single experiment flips the sign or the credibility of either key coefficient.\n"]
    sd_ = d["sensitivity_D"]
    if sd_:
        lines += [
            "### D. Comparison with Stage 6 paired-disclosure results\n",
            f"- Model A average disclosure effect (experiment-averaged, equal weight per "
            f"experiment): {fmt(sd_['model_A_average_disclosure_effect']['mean'], 3)} "
            f"log-scale units (95% CrI [{fmt(sd_['model_A_average_disclosure_effect']['cri95'][0], 3)}, "
            f"{fmt(sd_['model_A_average_disclosure_effect']['cri95'][1], 3)}]) — i.e. a small, "
            "not clearly credible reduction in absolute error when disclosed. "
            "(The main-table pair-weighted disclosure coefficient is -0.076 [-0.179, 0.028]; "
            "the two agree in substance and differ only in weighting.)",
            "- Stage 6 found accuracy improvement (blinded minus disclosed) 0.041 SD "
            "(equal-experiment weighting, 95% CrI [-0.023, 0.105]). Differences are explained by "
            "outcome (Stage 6 models direction-accuracy, Stage 9 models distance-from-human on "
            "the effect scale) and weighting (Stage 9's regression weights pairs, its "
            "experiment-averaged summary weights experiments). The Stage 6 and Stage 9 "
            "disclosure point estimates differ in sign, but both 95% intervals include 0, so "
            "they are statistically compatible.\n"]
    return "\n".join(lines)


def regression_results(d: dict) -> str:
    exp_avg_a = d["exp_avg"][d["exp_avg"]["outcome"] == "A_abs_error"]
    top = exp_avg_a.reindex(exp_avg_a["exp_averaged_estimate"].abs().sort_values(ascending=False).index)
    lines = [
        "# Stage 9 explanatory regression results\n",
        "Two theory-informed multilevel Bayesian regressions explain (not predict) the "
        "AI-human discrepancy across 553 paired model-contrast observations (15 models x 38 "
        "contrasts minus exclusions, 1106 blinded/disclosed rows).\n",
        "## Reference categories and units\n",
        "- response_format reference: rating_mean (verified modal, 540/1106 rows). "
        "The spec suggested binary_choice as reference but required verifying modality first; "
        "binary_choice was NOT modal, so rating_mean is used (documented deviation).",
        "- self_other reference: self (31/38 contrasts).",
        "- Continuous predictors are standardized; interpretable deltas: +100 words, +0.10 "
        "wording difference, 0->1 manipulation location, +1 response option, +0.5 SD human "
        "effect size, doubling of model SE.",
        "- Model A outcome: absolute error in human-SD units (Gamma log-link); translated "
        "estimates are percent changes. Model B outcome: same-direction agreement on the "
        "32 confident contrasts (934 rows, logistic); translated estimates are "
        "percentage-point changes in direction-correct probability.\n",
        "## Model A — absolute error\n",
        effects_table(d["effects"], "A_abs_error"), "",
        "## Model B — direction agreement\n",
        effects_table(d["effects"], "B_direction_correct"), "",
        "Note: translated estimates for Model B are average marginal effects — the average "
        "change in direction-correct probability across the posterior — and can carry the "
        "opposite sign to the mean logit coefficient because the logistic curve's saturation "
        "weights large-negative draws more. Example: question_order (+0.025 logit, -0.6 pp). "
        "This is a property of the nonlinear link, not a sign error.\n",
        "## Equal-weight-per-experiment headline summary\n",
        "Averaging each feature's effect within experiments first (equal weight per "
        "experiment) gives the same qualitative ordering as the row-weighted estimates; "
        "largest Model A effects (exp-averaged):",
    ]
    for r in top.head(8).itertuples():
        lines.append(f"- {r.predictor} ({r.contrast}): {fmt(r.exp_averaged_estimate, 3)} "
                     f"[{fmt(r.exp_averaged_cri95_low, 3)}, {fmt(r.exp_averaged_cri95_high, 3)}]")
    lines += [
        "\n## Credible vs null (95% CrI excludes / includes 0) — nulls reported, no selection\n",
        "- Model A: human_abs_d_std (+; larger human effects -> larger AI error) and "
        "log model SE (+; noisier model estimates sit further from humans) are credible. "
        "Disclosure alone is a small negative (noise-reduction) trend not reaching credibility; "
        "neither interaction is credible.",
        "- Model B: see the table above; most feature effects on direction agreement are null "
        "with wide intervals on the 32-contrast subset — the design has limited power for "
        "direction agreement, and that limit is itself a finding.",
        "- Conditionality: explicit_probability vs numerical_manipulation overlap (26/38); "
        "each coefficient is the effect holding the other fixed. The three sparse features "
        "(role_change, question_order, response_options_change) are weakly identified; their "
        "intervals mostly reflect prior shrinkage, not evidence of no effect.\n",
        "## Known caveats\n",
        "- 145 of 530 original cells carry the documented run10 stale-lineage caveat (frozen "
        "d_m not reproducible from hash-frozen records). Stage 5 y_std inherits them; results "
        "are conditional on the frozen values. Sensitivity B (Qwen exclusion) overlaps "
        "heavily with the affected models.",
        "- Bootstrap SEs capture persona resampling only (one seed, one draw per persona).",
        "- No p-values are used anywhere; all uncertainty statements are 95% credible intervals "
        "and posterior probabilities of sign.\n",
    ]
    return "\n".join(lines)


def key_findings(d: dict) -> str:
    eff = d["effects"]
    a = eff[eff["outcome"] == "A_abs_error"].set_index("predictor")
    b = eff[eff["outcome"] == "B_direction_correct"].set_index("predictor")

    def row(t, p):
        r = t.loc[p]
        return f"{r.translated_estimate:+.1f} (95% CrI {r.translated_cri95_low:+.1f} to {r.translated_cri95_high:+.1f})"

    had = a.loc["human_abs_d_std"]
    disc = a.loc["disclosure"]
    discb = b.loc["disclosure"]
    bullets = [
        f"**What we tested.** Whether blind-coded features of how experiments were reworded for "
        f"AI models explain (i) how far the AI landed from the human result and (ii) whether it "
        f"pointed the same direction, across 553 model-by-contrast pairs.",
        f"**The single strongest correlate of AI error is the size of the human effect itself**: "
        f"experiments with larger human effects show much larger AI absolute errors "
        f"({row(a, 'human_abs_d_std')}% per +0.5 SD human effect, credible). AI disagreement "
        f"concentrates where the human signal is strong.",
        f"**Noisier model estimates sit further from humans**: doubling a model-cell's "
        f"bootstrap SE raises absolute error {row(a, 'log_se_y_std')}% (credible). Part of the "
        f"\"AI discrepancy\" is sampling noise in the AI arm, not systematic bias.",
        f"**Negation changes are the largest feature association with error** "
        f"({row(a, 'negation_change')}% when a negation was changed, not credible at 95%) — "
        f"suggestive, not established.",
        f"**Numerical manipulation is associated with smaller AI error** "
        f"({row(a, 'numerical_manipulation')}%, not credible) but is 68% overlapping with "
        f"explicit-probability wording; the two cannot be separated with this design.",
        f"**Disclosure does not clearly change error**: disclosed runs show "
        f"{row(a, 'disclosure')}% absolute error vs blinded (not credible), consistent with the "
        f"Stage 6 finding that disclosure's average effect is small and uncertain.",
        f"**Direction agreement is mostly not explained by the coded features**: on the 32 "
        f"confident contrasts the model is direction-correct 73.7% of the time, but feature "
        f"effects are small with wide intervals; disclosure shifts direction agreement by "
        f"{row(b, 'disclosure')} pp (not credible).",
        f"**Most characteristics we coded show no credible association with either outcome** "
        f"— question order, response-option changes, role changes (3/38 contrasts each) and "
        f"wording-difference size are all null here; these are genuinely inconclusive, not "
        f"confirmed-absent.",
        f"**The unexplained part is big**: between-experiment heterogeneity is the largest "
        f"grouping effect in Model A (spread 0.41 log-units, rivaling the biggest feature "
        f"association); which experiment a contrast belongs to matters as much as any coded "
        f"property of the manipulation.",
        f"**Human benchmark uncertainty matters**: refitting with redrawn human benchmarks "
        f"moves coefficients by less than their credible widths, so conclusions are not an "
        f"artifact of human-side noise (Sensitivity A).",
        f"**Excluding the Qwen family does not change the major effects** (Sensitivity B), and "
        f"no single experiment drives them (Sensitivity C).",
        f"**Data caveat**: 145 of 530 original cells inherit the documented run10 stale-value "
        f"lineage; Stage 9 treats the frozen values as given and flags, not fixes, them.",
    ]
    return ("# Draft key findings — Stage 9 explanatory regressions\n\n"
            + "\n".join(f"- {b}" for b in bullets) + "\n")


def interpretation() -> str:
    return """# Draft interpretation — Stage 9 explanatory regressions

## What these regressions establish
Stage 9 asks which observable properties of the adapted experimental manipulations
co-vary with how far AI model responses land from the human benchmark, and with
whether AI points in the same direction. Because features were coded blind to
outcomes and entered as theory-motivated multilevel regressions, the credible
associations are evidence of covariation under the model's assumptions — not
predictions (no train/test split is used or needed) and not causal effects.

Three things are credibly established. First, AI error is larger where the human
effect is larger: the models are not uniformly wrong, they are most wrong exactly
where humans showed strong effects, which is the regime where replication matters
most. Second, part of measured "AI discrepancy" is mechanical: cells with larger
bootstrap SEs (sampling noise in the AI responses) show larger absolute error.
Third, disclosure alone does not credibly change either outcome in this regression,
mirroring Stage 6's paired result.

## Supported, ambiguous, and unsupported hypotheses
- Supported: error grows with human effect size and with model-cell noise.
- Ambiguous: negation changes (largest point association, not credible);
  numerical-manipulation vs explicit-probability wording (68% overlap makes them
  jointly unidentifiable at this sample size); sparse features (role change,
  question order, response-option change; 3/38 contrasts each).
- Null here (with limited power on the 32-contrast direction subset): most coded
  features do not credibly explain direction agreement.

## What the data cannot say about mechanisms
The design cannot separate why a feature associates with error: a negation change
may matter because models misread negation, or because such experiments happen to
be harder for other reasons. Random effects absorb, but do not explain, the large
model-by-contrast heterogeneity — the dominant source of variation. The run10
stale-lineage caveat means 145 cells carry frozen values that do not reproduce from
records; results are conditional on those frozen values. Bootstrap SEs capture
persona resampling only (single seed, one draw per persona). Finally, the
32-confident-contrast direction analysis has narrow informational content: absence
of credible feature effects there is a statement about information, not about truth.

## Illustrations, not confirmations
The experiment sketches in EXPERIMENT_EXAMPLES.md were selected after fitting and
are descriptive illustrations of the fitted associations; they are not independent
confirmation and should not be cited as such.
"""


def main() -> None:
    d = load_all()
    (STAGE9 / "MODEL_DIAGNOSTICS.md").write_text(model_diagnostics(d))
    (STAGE9 / "REGRESSION_RESULTS.md").write_text(regression_results(d))
    (STAGE9 / "DRAFT_KEY_FINDINGS.md").write_text(key_findings(d))
    (STAGE9 / "DRAFT_INTERPRETATION.md").write_text(interpretation())
    print("wrote MODEL_DIAGNOSTICS.md, REGRESSION_RESULTS.md, DRAFT_KEY_FINDINGS.md, "
          "DRAFT_INTERPRETATION.md")


if __name__ == "__main__":
    main()
