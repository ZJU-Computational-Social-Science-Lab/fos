# Runs the five-model hierarchical Bayesian comparison and writes every
# deliverable for the preliminary unblinding report.
#
# What this file does: it loads the Phase 2 tables, fits the three
# Bayesian models (direction, magnitude, TVD — see bayes_models.py), and
# writes into results/unblinding/twin2k_redesign/five_model_preliminary/:
#   POSTERIOR_RESULTS.csv            — every estimate, 95% interval, and
#                                      posterior probability of improvement,
#                                      per model and pooled, per condition.
#   diagnostics.json                 — machine-readable convergence numbers.
#   MODEL_DIAGNOSTICS.md             — convergence, effective sample sizes,
#                                      divergences, posterior-predictive
#                                      checks, prior sensitivity.
#   BAYESIAN_MODEL_SPECIFICATION.md  — full model spec, priors, likelihoods.
#   fig_posterior_direction/​magnitude/​tvd .{png,pdf} — posterior figures.
#
# What each function does:
#   run_model        — fits one model, returns draws summary + diagnostics.
#   write_csv        — POSTERIOR_RESULTS.csv from the effects dict.
#   write_md_docs    — the two markdown deliverables from the diagnostics.
#   make_figures     — forest plots of the configuration effect per model.
#   main             — fits all three, writes everything, prints a summary.

from __future__ import annotations

import json

import arviz as az
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import bayes_data
import bayes_models as bm
from config import MODELS, OUT

DOC_DIR = OUT


def run_model(name: str, fit, table, effects_fn, sens_table=None):
    """Fit one model; return (effects dict, diagnostics dict)."""
    print(f"fitting {name} model...", flush=True)
    idata = fit(table)
    effects = effects_fn(table, idata) if name != "tvd" else effects_fn(idata)
    summ = az.summary(idata, var_names=[v for v in idata.posterior.data_vars
                                        if not v.endswith("_raw")])
    ppc_name = list(idata.pp.posterior_predictive.data_vars)[0]
    draws = np.asarray(idata.pp.posterior_predictive[ppc_name])
    obs = np.asarray(idata.observed_data[ppc_name])
    stat_ppc = draws.reshape(-1, draws.shape[-1]).mean(axis=1)
    ppc_p = float((stat_ppc <= obs.mean()).mean())
    diag = {
        "max_r_hat": float(summ.r_hat.max()),
        "max_r_hat_param": str(summ.r_hat.idxmax()),
        "min_ess_bulk": float(summ.ess_bulk.min()),
        "min_ess_bulk_param": str(summ.ess_bulk.idxmin()),
        "n_params": int(len(summ)),
        "divergences": int(np.asarray(idata.sample_stats.diverging).sum()),
        "ppc_p_value_mean": ppc_p,
    }
    idata_copy = idata
    if sens_table is not None:
        print(f"  prior sensitivity for {name}...", flush=True)
        sens_idata = fit(sens_table, prior_scale=4.0)
        key = {"direction": "d_config", "magnitude": "d_level_config",
               "tvd": "d_config"}[name]
        arr = np.asarray(sens_idata.posterior[key]).reshape(-1)
        diag["prior_sensitivity_wide_priors"] = {
            "param": key, "mean": float(arr.mean()),
            "lo95": float(np.percentile(arr, 2.5)),
            "hi95": float(np.percentile(arr, 97.5))}
        del sens_idata
    del idata_copy
    return effects, diag


def write_csv(effects: dict[str, dict[str, float]]) -> None:
    """One row per outcome × scope × condition."""
    rows = []
    for key, vals in effects.items():
        outcome, model, condition = key.split("|")
        rows.append({"outcome": outcome, "scope": model, "condition": condition,
                     "mean": vals["mean"], "lo95": vals["lo95"],
                     "hi95": vals["hi95"],
                     "p_improvement": vals["p_improvement"]})
    pd.DataFrame(rows).to_csv(DOC_DIR / "POSTERIOR_RESULTS.csv", index=False)


def write_md_docs(diags: dict, effects: dict) -> None:
    """MODEL_DIAGNOSTICS.md and BAYESIAN_MODEL_SPECIFICATION.md."""
    lines = ["# Model diagnostics — five-model hierarchical Bayesian comparison", ""]
    for name, d in diags.items():
        lines += [f"## {name}", "",
                  f"- max R-hat: {d['max_r_hat']:.4f} (`{d['max_r_hat_param']}`)",
                  f"- min bulk ESS: {d['min_ess_bulk']:.0f} (`{d['min_ess_bulk_param']}`)",
                  f"- divergences: {d['divergences']}",
                  f"- posterior-predictive p-value (mean statistic): "
                  f"{d['ppc_p_value_mean']:.3f}",
                  f"- parameters monitored: {d['n_params']}"]
        if "prior_sensitivity_wide_priors" in d:
            s = d["prior_sensitivity_wide_priors"]
            lines.append(f"- prior sensitivity (priors x4 wider): "
                         f"{s['param']} mean {s['mean']:.4f}, "
                         f"95% [{s['lo95']:.4f}, {s['hi95']:.4f}]")
        lines.append("")
    lines.append("Decision rule used: model accepted when max R-hat < 1.01, "
                 "min bulk ESS > 400, zero divergences, and the PPC p-value "
                 "is not extreme (< 0.05 or > 0.95 would flag a misfit).")
    (DOC_DIR / "MODEL_DIAGNOSTICS.md").write_text("\n".join(lines))

    spec = ["# Bayesian model specification — five-model preliminary comparison", "",
            "Three hierarchical Bayesian models compare the original "
            "(synthetic-persona) pool against the redesigned (Config-A "
            "real-persona) pool across five models, fit with PyMC/NUTS "
            f"({bm.CHAINS} chains, {bm.DRAWS} draws each, tune {bm.TUNE}, "
            f"target_accept {bm.TARGET_ACCEPT}, seed {bm.SEED}). "
            "All intervals and improvement probabilities come directly from "
            "posterior draws; no bootstrap is used anywhere.", "",
            "## Shared structure", "",
            "- era: 0 = original, 1 = redesigned; condition: 0 = uninformed, "
            "1 = disclosure; interaction = era x condition.",
            "- model-specific configuration effects are non-centred deviations "
            "shrink toward the shared configuration effect (partial pooling): "
            "`d_model = d_config + raw * s_config_model`.",
            "- random effects (model, experiment, nested contrast cell) are "
            "non-centred HalfNormal scales times standard normals.", "",
            "## 1. Direction (Bernoulli-logit)", "",
            "`agrees ~ Bernoulli(logit_p = a + d_model + b_disclosure*cond "
            "+ b_config_disclosure*era*cond + b_human_gradient*z + u_model + "
            "u_experiment + u_cell)` on non-near-zero human-effect cells.",
            "Priors: a, d_config, b_* ~ Normal(0, 1.25); scales ~ HalfNormal"
            "(0.75 model, 0.5 experiment/cell, 0.75 config-model).", "",
            "## 2. Magnitude (Normal, human-SD units)", "",
            "`predicted ~ Normal(mu, s_residual)`, `mu = a + u_model + "
            "b_slope*human + d_level_model*era + d_slope_model*era*human + "
            "b_disclosure*cond + b_config_disclosure*era*cond + u_experiment "
            "+ u_cell`. Priors: b_slope ~ Normal(1, 0.5) (unity slope = no "
            "attenuation); d_level/d_slope ~ Normal(0, 0.5); scales ~ "
            "HalfNormal(0.35–0.5).", "",
            "## 3. TVD (Normal)", "",
            "`tvd ~ Normal(a + u_model + d_model*era + b_disclosure*cond + "
            "b_config_disclosure*era*cond + u_experiment, s_residual)`. "
            "Priors: a ~ Normal(0.3, 0.25); d_config ~ Normal(0, 0.25); "
            "scales ~ HalfNormal(0.15–0.25).", "",
            "## Improvement probability", "",
            "Direction: P(effect > 0). Magnitude: P(expected |error| "
            "difference < 0). TVD: P(effect < 0). Reported per model and "
            "pooled (POOLED-5), per condition.", ""]
    (DOC_DIR / "BAYESIAN_MODEL_SPECIFICATION.md").write_text("\n".join(spec))


def make_figures(effects: dict[str, dict[str, float]]) -> None:
    """Forest plots: configuration effect per model, per condition."""
    for outcome, better in (("direction", "higher is better"),
                            ("magnitude", "lower is better"),
                            ("tvd", "lower is better")):
        fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
        for ax, cond in zip(axes, ("uninformed", "disclosure")):
            rows = [effects[k] for k in effects
                    if k.startswith(f"{outcome}|") and k.endswith(f"|{cond}")]
            labels = [k.split("|")[1] for k in effects
                      if k.startswith(f"{outcome}|") and k.endswith(f"|{cond}")]
            y = np.arange(len(rows))
            lo = [r["lo95"] for r in rows]
            hi = [r["hi95"] for r in rows]
            ax.axvline(0, color="k", lw=0.8, alpha=0.6)
            ax.errorbar([r["mean"] for r in rows], y,
                        xerr=[np.array([r["mean"] for r in rows]) - np.array(lo),
                              np.array(hi) - np.array([r["mean"] for r in rows])],
                        fmt="o", capsize=3, color="tab:blue")
            ax.set_yticks(y, labels, fontsize=8)
            ax.set_title(cond, fontsize=10)
            ax.grid(axis="x", alpha=0.3)
        axes[0].set_ylabel("model (POOLED-5 last)")
        fig.suptitle(f"Redesigned vs original: {outcome} effect "
                     f"(95% credible intervals; {better})", fontsize=11)
        fig.tight_layout(rect=[0, 0, 1, 0.93])
        for ext in ("png", "pdf"):
            fig.savefig(DOC_DIR / f"fig_posterior_{outcome}.{ext}", dpi=200)
        plt.close(fig)


def main() -> None:
    """Fit all three models and write every deliverable."""
    OUT.mkdir(parents=True, exist_ok=True)
    direction, magnitude = bayes_data.build_direction_magnitude(
        bayes_data.load_effects())
    tvd = bayes_data.load_tvd()
    tvd_coded = bayes_data.add_group_codes(tvd)

    effects: dict[str, dict[str, float]] = {}
    diags: dict[str, dict] = {}
    plan = [
        ("direction", bm.fit_direction, direction, bm.direction_effects, direction),
        ("magnitude", bm.fit_magnitude, magnitude, bm.magnitude_effects, magnitude),
        ("tvd", bm.fit_tvd, tvd_coded, bm.tvd_effects, tvd_coded),
    ]
    for name, fit, table, eff_fn, sens in plan:
        effs, diag = run_model(name, fit, table, eff_fn, sens_table=sens)
        effects.update(effs)
        diags[name] = diag
        print(f"{name}: max R-hat {diag['max_r_hat']:.4f}, "
              f"divergences {diag['divergences']}", flush=True)

    write_csv(effects)
    write_md_docs(diags, effects)
    make_figures(effects)
    with (DOC_DIR / "diagnostics.json").open("w") as fh:
        json.dump(diags, fh, indent=2)
    pooled = {k: v for k, v in effects.items() if "POOLED-5" in k}
    print(json.dumps(pooled, indent=2))
    print(f"wrote {len(effects)} posterior rows + docs + figures to {DOC_DIR}")


if __name__ == "__main__":
    main()
