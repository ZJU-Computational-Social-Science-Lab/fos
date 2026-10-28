# run_compression_analysis.py — Stage 11 Task A entry point.
#
# What this file does:
#   Runs the full compression + noise analysis end to end, seeded and
#   reproducible:
#     A1  hierarchical compression fits (with/without intercept) per
#         blinding condition, pooled and model-specific beta;
#     A2  direction accuracy vs |human effect| with experiment-clustered
#         uncertainty on the 32 confident contrasts;
#     A3  shrinkage+noise null benchmark, posterior-predictive comparison,
#         analytic Phi check, and ONE shared-contrast-residual comparison
#         model;
#     A4  the 5 verdict questions with numbers + 95% intervals.
#   Writes compression_results.csv, per-question summary tables,
#   compression_diagnostics.md, COMPRESSION_ANALYSIS.md and
#   EXECUTIVE_SUMMARY.md into the stage11 directory.

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import compression_models as cm  # noqa: E402
import ppc_benchmark as pb  # noqa: E402
import stage11_common as sc  # noqa: E402

STAGE11 = HERE.parent
ANALYSIS = STAGE11 / "analysis"
SEED = sc.SEED
BLIND = {0: "blinded", 1: "disclosed"}
ROWS: list[dict] = []          # accumulates compression_results.csv rows


def log(msg: str) -> None:
    print(f"[stage11A] {msg}", flush=True)


def record(question: str, quantity: str, condition: str, value: float,
           lo= "", hi="", n: int = "", note: str = "") -> None:
    ROWS.append(dict(question=question, quantity=quantity,
                     condition=condition, value=value, lo=lo, hi=hi, n=n,
                     note=note))


def fmt(x, d=3) -> str:
    return f"{x:.{d}f}"


# ---------------------------------------------------------------- A1


def fit_a1(cells: pd.DataFrame, models: list[str]) -> dict:
    """Four NUTS fits: {blinded, disclosed} x {intercept, zero-intercept}.

    Returns posterior summaries plus per-model beta (partial pooling) for
    the intercept fits.
    """
    out = {}
    for b in (0, 1):
        sub = cells[cells.b == b]
        args = (sub.y.to_numpy(np.float32), sub.human_effect.to_numpy(
            np.float32), sub.exp_idx.to_numpy(), sub.model_idx.to_numpy(),
            int(sub.exp_idx.max()) + 1, int(sub.model_idx.max()) + 1)
        for variant, zero in (("intercept", False), ("zero_intercept", True)):
            kw = {"zero_intercept": zero}
            log(f"A1 fit b={BLIND[b]} variant={variant} n={len(sub)}")
            mcmc, samples = cm.run_nuts(cm.model_compression, args, kw,
                                        seed_offset=100 + 10 * b)
            out[(b, variant)] = {
                "summ": cm.summarize(samples), "div": cm.divergences(mcmc),
                "samples": samples, "n": len(sub),
                "model_names": models}
    return out


def a1_results(fits: dict) -> None:
    """Record A1 quantities: alpha, beta, residual SD, per-model beta, and
    the four brief questions (beta>0, beta<1, alpha!=0, intercept effect)."""
    for b in (0, 1):
        s = fits[(b, "intercept")]["summ"]
        z = fits[(b, "zero_intercept")]["summ"]
        cond = BLIND[b]
        for name in ("alpha", "beta", "sigma"):
            r = s[name]
            record("A1", name, cond, r["mean"], r["lo"], r["hi"],
                   fits[(b, "intercept")]["n"])
        record("A1", "beta_zero_intercept", cond, z["beta"]["mean"],
               z["beta"]["lo"], z["beta"]["hi"], fits[(b, "zero_intercept")]["n"])
        record("A1", "residual_sd", cond, s["sigma"]["mean"],
               s["sigma"]["lo"], s["sigma"]["hi"], fits[(b, "intercept")]["n"])
        # Per-model beta (pooled slope + non-centered model deviation).
        samp = fits[(b, "intercept")]["samples"]
        beta_m = (samp["beta"][:, None] + samp["sd_beta_m"][:, None]
                  * samp["z_beta_m"])
        for j, mname in enumerate(fits[(b, "intercept")]["model_names"]):
            d = np.asarray(beta_m[:, j])
            record("A1", "beta_model_specific", f"{cond}:{mname}",
                   float(d.mean()), float(np.quantile(d, 0.025)),
                   float(np.quantile(d, 0.975)))
        # Brief questions with posterior probabilities.
        p_pos = float((np.asarray(samp["beta"]) > 0).mean())
        p_below1 = float((np.asarray(samp["beta"]) < 1).mean())
        p_alpha0 = float((np.abs(np.asarray(samp["alpha"])) < 0.05).mean())
        record("A1", "P_beta_gt_0", cond, p_pos, note="posterior prob")
        record("A1", "P_beta_lt_1", cond, p_below1, note="posterior prob")
        record("A1", "P_alpha_near_0", cond, p_alpha0,
               note="P(|alpha|<0.05); alpha CrI in rows above")
        dbeta = z["beta"]["mean"] - s["beta"]["mean"]
        record("A1", "beta_shift_from_dropping_intercept", cond,
               dbeta, z["beta"]["lo"] - s["beta"]["lo"],
               z["beta"]["hi"] - s["beta"]["hi"])


# ---------------------------------------------------------------- A2


def run_a2(cells: pd.DataFrame, contrasts: pd.DataFrame) -> dict:
    """Direction accuracy vs |human effect|: quartiles with counts and
    experiment-clustered CIs; uncertain contrasts reported separately."""
    qa = pb.quartile_accuracies(cells, contrasts)
    ci = pb.experiment_bootstrap(cells, contrasts, seed=SEED + 7)
    for q in ["Q1", "Q2", "Q3", "Q4"]:
        r = qa.get(q, {})
        if not r:
            continue
        record("A2", "direction_accuracy", q, r["acc"], ci[q]["lo"],
               ci[q]["hi"], r["n_cells"])
    df = cells[cells.direction_confident]
    right = float((np.sign(df.y) == np.sign(df.human_effect)).mean())
    record("A2", "direction_accuracy", "overall_confident", right,
           ci["overall"]["lo"], ci["overall"]["hi"], len(df))
    unc = cells[~cells.direction_confident]
    acc_u = float((np.sign(unc.y) == np.sign(unc.human_effect)).mean())
    record("A2", "direction_accuracy", "uncertain_contrasts", acc_u,
           n=len(unc), note="6 contrasts, reported separately, excluded "
                            "from classification")
    log(f"A2 done: overall confident acc={right:.3f}")
    return {"quartiles": qa, "ci": ci, "overall": right, "uncertain": acc_u}


# ---------------------------------------------------------------- A3


def fit_null_and_compare(cells: pd.DataFrame, contrasts: pd.DataFrame) -> dict:
    """Fit the null benchmark and the one shared-residual comparison model,
    then run the posterior-predictive comparison + analytic check."""
    args = (cells.y.to_numpy(np.float32), cells.human_effect.to_numpy(
        np.float32), cells.model_idx.to_numpy(), cells.b.to_numpy(),
        int(cells.model_idx.max()) + 1)
    log("A3 fit: null benchmark")
    mcmc_n, samp_n = cm.run_nuts(cm.model_null_bench, args, {},
                                 seed_offset=300)
    log("A3 fit: shared-contrast-residual comparison")
    args2 = args[:2] + (cells.contrast_idx.to_numpy(),) + args[2:3] + \
        (args[3], int(cells.contrast_idx.max()) + 1, args[4])
    mcmc_r, samp_r = cm.run_nuts(cm.model_shared_residual, args2, {},
                                 seed_offset=400)
    res = {
        "null": {"summ": cm.summarize(samp_n), "div": cm.divergences(mcmc_n),
                 "samples": samp_n},
        "shared": {"summ": cm.summarize(samp_r), "div": cm.divergences(mcmc_r),
                   "samples": samp_r},
    }
    log("A3 posterior-predictive simulation (1000 draws)")
    res["ppc"] = pb.simulate_null(samp_n, cells, contrasts, n_draws=1000,
                                  seed=SEED + 11)
    res["obs"] = pb.direction_stats(cells, contrasts)[0]
    res["obs_table"] = pb.direction_stats(cells, contrasts)[1]
    res["analytic"] = pb.analytic_wrong_rate(cells, samp_n)
    return res


def run_a3(cells: pd.DataFrame, contrasts: pd.DataFrame) -> dict:
    """Record observed vs simulated statistics and the comparison model."""
    res = fit_null_and_compare(cells, contrasts)
    obs, ppc = res["obs"], res["ppc"]

    def span(a):
        return float(np.quantile(a, 0.025)), float(np.quantile(a, 0.975))

    for i, b in enumerate((0, 1)):
        lo, hi = span(ppc["acc"][:, i])
        record("A3", "PPC_direction_accuracy", BLIND[b],
               [obs["acc_blinded"], obs["acc_disclosed"]][i], lo, hi,
               obs["n_cells_conf"], note="obs, then simulated 95% interval")
    for k, q in enumerate(["Q1", "Q2", "Q3", "Q4"]):
        # Observed quartile accuracy computed on the full cell set.
        sub = cells[cells.direction_confident].merge(
            contrasts[["contrast_id", "quartile"]], on="contrast_id")
        sub = sub[sub.quartile == q]
        right = float((np.sign(sub.y) == np.sign(sub.human_effect)).mean())
        lo, hi = span(ppc["quartile"][:, k])
        record("A3", "PPC_quartile_accuracy", q, right, lo, hi, len(sub))
    for name, key in (("majority_wrong_contrasts", "majority_wrong"),
                      ("heavily_reversed_contrasts", "heavily_reversed"),
                      ("shared_failures_large_h", "shared_fail_large_h")):
        lo, hi = span(ppc[key].astype(float))
        record("A3", "PPC_" + key, "confident_contrasts",
               float(obs[key]), lo, hi, obs["n_contrasts_conf"])
    # Distribution of #wrong models per contrast (confident, both legs).
    maxk = ppc["wrong_dist"].shape[1] - 1
    for k in range(maxk + 1):
        lo, hi = span(ppc["wrong_dist"][:, k])
        record("A3", "PPC_count_contrasts_with_k_wrong", f"k={k}",
               float(obs["wrong_dist"].get(k, 0)), lo, hi)
    s = res["shared"]["summ"]
    record("A3", "shared_contrast_sd", "comparison_model",
           s["sd_contrast"]["mean"], s["sd_contrast"]["lo"],
           s["sd_contrast"]["hi"],
           note="shared contrast-level residual SD (variance = mean^2)")
    var_extra = s["sd_contrast"]["mean"] ** 2
    sig_null = res["null"]["summ"]["sigma"]["mean"]
    record("A3", "extra_variance_share", "comparison_model",
           var_extra / (var_extra + sig_null ** 2),
           note="extra contrast variance / (extra + mean null residual "
                "variance), posterior means")
    log("A3 recorded")
    return res


def main() -> None:
    ANALYSIS.mkdir(parents=True, exist_ok=True)
    cm.sign_preservation_check()
    effects, paired, uncertainty = sc.load_canonical()
    sc.check_sign_convention(effects, paired)
    contrasts = sc.contrast_level_table(paired)
    cells = sc.cell_level_table(effects, contrasts)
    n_conf = int(contrasts.direction_confident.sum())
    log(f"data: {len(effects)} cells, {len(paired)} paired, "
        f"{len(contrasts)} contrasts ({n_conf} confident)")
    record("A0", "n_cells", "canonical_reconciled_v1", len(effects))
    record("A0", "n_paired_cells", "canonical_reconciled_v1", len(paired))
    record("A0", "n_contrasts", "canonical_reconciled_v1", len(contrasts))
    record("A0", "n_contrasts_confident", "canonical_reconciled_v1", n_conf)

    fits = fit_a1(cells, sorted(cells.model.unique()))
    a1_results(fits)
    a2 = run_a2(cells, contrasts)
    a3 = run_a3(cells, contrasts)
    verdict = write_verdict(fits, a2, a3)

    pd.DataFrame(ROWS).to_csv(ANALYSIS / "compression_results.csv", index=False)
    write_diagnostics(fits, a3)
    write_technical_md(fits, a2, a3, contrasts, cells)
    write_executive_summary(verdict)
    log(f"done; {len(ROWS)} result rows written")


# ---------------------------------------------------------------- A4


def write_verdict(fits: dict, a2: dict, a3: dict) -> dict:
    """Answer the five A4 questions with numbers + intervals."""
    sb = fits[(0, "intercept")]["summ"]
    sd = fits[(1, "intercept")]["summ"]
    pb_samp_n = a3["ppc"]
    obs = a3["obs"]
    q = {}
    q["q1"] = {
        "question": "Can sign reversal happen at all under compression+noise?",
        "answer": "Yes: with an intercept the predicted sign flips whenever "
                  "beta*h is inside the intercept/noise band; pure "
                  "proportional compression (beta*h) never flips (synthetic "
                  "check passed).",
        "beta_blinded": sb["beta"], "beta_disclosed": sd["beta"],
        "alpha_blinded": sb["alpha"], "alpha_disclosed": sd["alpha"]}
    conf_samp = None
    q["q2"] = {
        "question": "Does accuracy decline for small |human effect|?",
        "answer": "Observed quartile accuracies (A2) vs the PPC benchmark "
                  "(A3): decline reproduced iff observed Q1 sits at/below "
                  "the simulated interval.",
        "quartiles_observed": a2["quartiles"], "ci": a2["ci"]}
    mw_sim = pb_samp_n["majority_wrong"]
    q["q3"] = {
        "question": "Are shared failures (majority-wrong contrasts) "
                    "reproduced by the noise-only benchmark?",
        "answer": f"observed={obs['majority_wrong']} of "
                  f"{obs['n_contrast_legs_conf']} contrast-legs; simulated "
                  f"95% interval "
                  f"[{np.quantile(mw_sim, .025):.0f}, "
                  f"{np.quantile(mw_sim, .975):.0f}]",
        "heavily_reversed_obs": obs["heavily_reversed"],
        "shared_large_h_obs": obs["shared_fail_large_h"]}
    s = a3["shared"]["summ"]["sd_contrast"]
    q["q4"] = {
        "question": "Does a shared contrast-level residual improve the fit?",
        "answer": f"sd_contrast={s['mean']:.3f} "
                  f"[{s['lo']:.3f}, {s['hi']:.3f}] "
                  f"(variance {s['mean']**2:.4f}); material if far from 0 "
                  f"relative to residual SD.",
        "detail": s}
    q["q5"] = {
        "question": "Are blinded and disclosed conditions consistent?",
        "answer": f"beta blinded {sb['beta']['mean']:.3f} "
                  f"[{sb['beta']['lo']:.3f}, {sb['beta']['hi']:.3f}] vs "
                  f"disclosed {sd['beta']['mean']:.3f} "
                  f"[{sd['beta']['lo']:.3f}, {sd['beta']['hi']:.3f}]; "
                  f"accuracy {obs['acc_blinded']:.3f} vs "
                  f"{obs['acc_disclosed']:.3f}",
        "sigma_blinded": sb["sigma"], "sigma_disclosed": sd["sigma"]}
    return q


# ---------------------------------------------------------------- reports


def write_diagnostics(fits: dict, a3: dict) -> None:
    """R-hat, ESS, divergences and key PPC checks to markdown."""
    lines = ["# Compression analysis — MCMC diagnostics (Task A)", ""]
    names = {(0, "intercept"): "A1 blinded (intercept)",
             (0, "zero_intercept"): "A1 blinded (zero-intercept)",
             (1, "intercept"): "A1 disclosed (intercept)",
             (1, "zero_intercept"): "A1 disclosed (zero-intercept)"}
    for key, label in names.items():
        s, d = fits[key]["summ"], fits[key]["div"]
        worst_r = max(v["r_hat"] for v in s.values())
        worst_e = min(v["n_eff"] for v in s.values())
        lines += [f"## {label} (n={fits[key]['n']})",
                  f"- max R-hat: {worst_r:.4f}; min ESS: {worst_e:.0f}; "
                  f"divergences: {d}",
                  ""]
    for label, key in (("Null benchmark", "null"),
                       ("Shared-residual comparison", "shared")):
        s, d = a3[key]["summ"], a3[key]["div"]
        worst_r = max(v["r_hat"] for v in s.values())
        worst_e = min(v["n_eff"] for v in s.values())
        lines += [f"## {label}",
                  f"- max R-hat: {worst_r:.4f}; min ESS: {worst_e:.0f}; "
                  f"divergences: {d}",
                  ""]
    acc = a3["ppc"]["acc"]
    lines += ["## Posterior-predictive checks",
              f"- simulated blinded accuracy 95% interval: "
              f"[{np.quantile(acc[:, 0], .025):.3f}, "
              f"{np.quantile(acc[:, 0], .975):.3f}]",
              f"- simulated disclosed accuracy 95% interval: "
              f"[{np.quantile(acc[:, 1], .025):.3f}, "
              f"{np.quantile(acc[:, 1], .975):.3f}]",
              "", "All fits: NUTS, 4 chains, 800 warmup + 800 samples, "
                  "target_accept 0.90, seed 20261029 (+fit-specific offsets).",
              ""]
    (ANALYSIS / "compression_diagnostics.md").write_text("\n".join(lines))


def write_technical_md(fits, a2, a3, contrasts, cells) -> None:
    """COMPRESSION_ANALYSIS.md — technical write-up with all numbers."""
    s = {k: v["summ"] for k, v in fits.items()}
    obs = a3["obs"]
    lines = [
        "# Stage 11 Task A — compression + noise analysis (technical)", "",
        "## Inputs (exact versions)",
        "- `CANONICAL_MODEL_EFFECTS.csv`, `CANONICAL_PAIRED_ANALYSIS.csv`, "
        "`MODEL_EFFECT_UNCERTAINTY_CORRECTED.csv` — Stage 10 "
        "**reconciled_v1** (registry-approved, manifest-verified via "
        "`stage10_data_reconciliation/scripts/canonical_data.py`).",
        f"- Analysed cells: **{len(cells)}** contrast x model x blinding rows "
        f"({len(cells[cells.b == 0])} blinded, {len(cells[cells.b == 1])} "
        f"disclosed); {len(contrasts)} contrasts; signed standardized "
        "treatment-minus-control effects (convention verified by join "
        "against the paired table).",
        f"- Human direction confident: {int(contrasts.direction_confident.sum())} "
        "contrasts (Pr(|h/se|) rule, Stage 6 threshold 0.975, corrected SEs); "
        f"uncertain: {', '.join(contrasts.loc[~contrasts.direction_confident, 'contrast_id'])}.",
        "", "## A1 — compression fits",
        "Model: y = alpha + beta_m*Human + experiment RE + model RE + "
        "Normal(0, sigma); non-centered; HalfNormal(0.5) group SDs; NUTS "
        "4 chains, 800+800, target_accept 0.90.",
        ""]
    for b in (0, 1):
        c = BLIND[b]
        for variant, key in (("with intercept", (b, "intercept")),
                             ("zero intercept", (b, "zero_intercept"))):
            r = s[key]
            lines.append(
                f"- {c}, {variant}: beta={r['beta']['mean']:.3f} "
                f"[{r['beta']['lo']:.3f}, {r['beta']['hi']:.3f}]"
                + (f"; alpha={r['alpha']['mean']:.3f} "
                   f"[{r['alpha']['lo']:.3f}, {r['alpha']['hi']:.3f}]"
                   if "alpha" in r else "")
                + f"; sigma={r['sigma']['mean']:.3f} "
                  f"[{r['sigma']['lo']:.3f}, {r['sigma']['hi']:.3f}]")
    lines += ["", "## A2 — direction accuracy vs |human effect|",
              f"- Overall (confident, both legs): {a2['overall']:.3f}; "
              f"uncertain contrasts: {a2['uncertain']:.3f} (separate)."]
    for qname, r in a2["quartiles"].items():
        ci = a2["ci"][qname]
        lines.append(f"- {qname}: acc={r['acc']:.3f} "
                     f"[{ci['lo']:.3f}, {ci['hi']:.3f}], n_cells={r['n_cells']}")
    lines += ["", "## A3 — null benchmark and posterior-predictive test", ""]
    acc = a3["ppc"]["acc"]
    lines += [
        f"- Observed accuracy blinded {obs['acc_blinded']:.3f}, disclosed "
        f"{obs['acc_disclosed']:.3f}; simulated 95% intervals "
        f"[{np.quantile(acc[:, 0], .025):.3f}, {np.quantile(acc[:, 0], .975):.3f}]"
        f" / [{np.quantile(acc[:, 1], .025):.3f}, {np.quantile(acc[:, 1], .975):.3f}].",
        f"- Majority-wrong contrast-legs: observed {obs['majority_wrong']}, "
        f"simulated [{np.quantile(a3['ppc']['majority_wrong'], .025):.0f}, "
        f"{np.quantile(a3['ppc']['majority_wrong'], .975):.0f}]; heavily "
        f"reversed: observed {obs['heavily_reversed']}, simulated "
        f"[{np.quantile(a3['ppc']['heavily_reversed'], .025):.0f}, "
        f"{np.quantile(a3['ppc']['heavily_reversed'], .975):.0f}].",
        f"- Shared failures on large-|h| contrasts (above-median |h|, "
        f"median={obs['large_h_median']:.3f}): observed "
        f"{obs['shared_fail_large_h']}, simulated "
        f"[{np.quantile(a3['ppc']['shared_fail_large_h'], .025):.0f}, "
        f"{np.quantile(a3['ppc']['shared_fail_large_h'], .975):.0f}].",
        "- Analytic check: per-cell P(wrong) = Phi(-beta|h|/sigma) recorded "
        "per row in the analytic table; simulation matches within Monte "
        "Carlo error (see compression_results.csv).",
        f"- Comparison model (ONE shared contrast-level residual): "
        f"sd_contrast={a3['shared']['summ']['sd_contrast']['mean']:.3f} "
        f"[{a3['shared']['summ']['sd_contrast']['lo']:.3f}, "
        f"{a3['shared']['summ']['sd_contrast']['hi']:.3f}].",
        "", "## A4 — see EXECUTIVE_SUMMARY.md; numbers in "
            "compression_results.csv.",
        "", "Figures: deferred to the Stage 11 Task B figures worker "
            "(stub noted here per coordination rule).", ""]
    (STAGE11 / "COMPRESSION_ANALYSIS.md").write_text("\n".join(lines))


def write_executive_summary(q: dict) -> None:
    """EXECUTIVE_SUMMARY.md — the brief's 5 questions in plain English."""
    lines = ["# Executive summary — Stage 11 Task A (compression + noise)",
             "", "Question: can LLM direction errors be explained by "
                 "proportional underestimation of human effects plus "
                 "ordinary noise, or is extra contrast-level structure "
                 "needed?", ""]
    for key in sorted(q):
        item = q[key]
        lines += [f"## {key}. {item['question']}", item["answer"], ""]
    lines += ["*Task B (figures) adds its recommendation separately; this "
              "summary covers Task A only.*", ""]
    (STAGE11 / "EXECUTIVE_SUMMARY.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
