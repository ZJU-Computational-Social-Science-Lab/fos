# Fits the two Bayesian multilevel regressions with NumPyro's NUTS sampler.
# Model A uses a Gamma distribution with a log link for the AI's absolute distance
# from the human result (all distances are strictly positive here, so no zero-shift
# is needed). Model B uses a logistic model for whether the AI pointed the same
# direction as humans, on the subset of contrasts where the human direction itself
# is considered reliable. Both models share the same predictors, include a blinded-
# vs-disclosed main effect plus two interactions (disclosure x role change, and
# disclosure x manipulation location), and have additive "random effect" offsets for
# model (15 levels), experiment (31), contrast nested in experiment (38), and the
# model-by-contrast pair (553 in Model A). Each grouping uses a non-centered
# parameterization with a Half-Normal(0.5) spread prior; slopes get Normal(0, 0.5)
# priors and the intercept Normal(0, 1.5). The Gamma shape parameter gets a
# Half-Normal(2) prior (documented computational choice, as the spec leaves it open).
# Saves posterior draws, convergence summaries, posterior-predictive checks and the
# predictor correlation matrix into the outputs folder.

import argparse
import json
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import numpyro
import numpyro.distributions as dist
import pandas as pd
from numpyro.infer import MCMC, NUTS, Predictive
from numpyro.diagnostics import summary

STAGE9 = Path(__file__).resolve().parents[1]
OUT = STAGE9 / "outputs"
OUT.mkdir(exist_ok=True)
SEED = 20261028

numpyro.set_host_device_count(4)


def load_inputs(model: str) -> pd.DataFrame:
    df = pd.read_csv(STAGE9 / ("MODEL_INPUTS_A.csv" if model == "a" else "MODEL_INPUTS_B.csv"))
    return df


def predictor_names(df: pd.DataFrame) -> list[str]:
    reserved = {"contrast_id", "experiment_id", "study_group", "model", "blinding",
                "model_contrast_pair", "absolute_error", "correct_direction",
                "human_direction_confident", "y_std", "se_y_std_used", "human_se_std",
                "human_direction", "response_format", "self_other", "d_human_std"}
    return [c for c in df.columns if c not in reserved]


def index_map(values: np.ndarray) -> tuple[np.ndarray, int]:
    levels, indexed = np.unique(values, return_inverse=True)
    return indexed.astype(int), len(levels)


def regression_model(x, g_model, n_model, g_exp, n_exp, g_con, n_con, g_pair, n_pair,
                     y=None, gamma=False):
    # Non-centered multilevel linear predictor; Gamma log-link or Bernoulli logit.
    alpha = numpyro.sample("alpha", dist.Normal(0.0, 1.5))
    beta = numpyro.sample("beta", dist.Normal(0.0, 0.5).expand([x.shape[1]]))

    def re(name, g, n):
        sd = numpyro.sample(f"sd_{name}", dist.HalfNormal(0.5))
        z = numpyro.sample(f"z_{name}", dist.Normal(0.0, 1.0).expand([n]).to_event(1))
        return sd * z

    u_model = re("model", g_model, n_model)
    u_exp = re("experiment", g_exp, n_exp)
    u_con = re("contrast", g_con, n_con)
    u_pair = re("pair", g_pair, n_pair)

    eta = (alpha + x @ beta + u_model[g_model] + u_exp[g_exp]
           + u_con[g_con] + u_pair[g_pair])
    if gamma:
        phi = numpyro.sample("phi", dist.HalfNormal(2.0))
        with numpyro.plate("obs", x.shape[0]):
            numpyro.sample("y", dist.Gamma(phi, phi / jnp.exp(eta)), obs=y)
    else:
        with numpyro.plate("obs", x.shape[0]):
            numpyro.sample("y", dist.Bernoulli(logits=eta), obs=y)


def apply_data_modifications(df: pd.DataFrame, args) -> pd.DataFrame:
    # Optional, documented modifications used only by the sensitivity refits:
    # --human-seed resamples the shared per-contrast human benchmark from its own
    # uncertainty (the same draw is used for both blinding rows of a contrast),
    # --drop-qwen removes the largest model family, --exclude-experiment removes
    # one experiment (leave-one-out influence diagnostics).
    df = df.copy()
    if args.drop_qwen:
        n0 = len(df)
        df = df[~df["model"].str.contains("qwen", case=False)]
        print(f"dropped Qwen family: {n0} -> {len(df)} rows")
    if args.exclude_experiment:
        n0 = len(df)
        df = df[df["experiment_id"] != args.exclude_experiment]
        print(f"excluded experiment {args.exclude_experiment}: {n0} -> {len(df)} rows")
    if args.human_seed is not None:
        rng = np.random.default_rng(SEED + int(args.human_seed))
        contrasts = df[["contrast_id", "d_human_std", "human_se_std"]].drop_duplicates()
        draws = {r.contrast_id: r.d_human_std + r.human_se_std * rng.standard_normal()
                 for r in contrasts.itertuples()}
        h = df["contrast_id"].map(draws).to_numpy(np.float64)
        df["absolute_error"] = np.abs(df["y_std"].to_numpy(np.float64) - h)
        print(f"human benchmark resampled with seed {args.human_seed} "
              f"(shared within contrast); mean abs error {df['absolute_error'].mean():.4f}")
    return df


def run_nuts(args) -> None:
    df = apply_data_modifications(load_inputs(args.model), args)
    names = predictor_names(df)
    x = df[names].to_numpy(dtype=np.float64)
    y = df["absolute_error"].to_numpy(np.float64) if args.model == "a" else \
        df["correct_direction"].to_numpy(np.float64)
    g_model, n_model = index_map(df["model"].to_numpy())
    g_exp, n_exp = index_map(df["experiment_id"].to_numpy())
    g_con, n_con = index_map(df["contrast_id"].to_numpy())
    g_pair, n_pair = index_map(df["model_contrast_pair"].to_numpy())

    print(f"Model {args.model.upper()}: {len(df)} rows, {len(names)} predictors, "
          f"{n_pair} pairs; warmup={args.warmup} samples={args.samples}")
    kernel = NUTS(regression_model, target_accept_prob=0.90)
    mcmc = MCMC(kernel, num_warmup=args.warmup, num_samples=args.samples,
                num_chains=4, chain_method="parallel", progress_bar=False)
    mcmc.run(jax.random.PRNGKey(SEED), x=x, g_model=g_model, n_model=n_model,
             g_exp=g_exp, n_exp=n_exp, g_con=g_con, n_con=n_con,
             g_pair=g_pair, n_pair=n_pair, y=y, gamma=(args.model == "a"))

    draws = mcmc.get_samples(group_by_chain=True)
    flat = mcmc.get_samples()
    s = summary(draws, group_by_chain=True)

    # Convergence flags on the slope/intercept parameters (RE-level ESS is expected
    # to be lower for 3-observation groups; flags are reported, not hidden).
    flags = []
    for p in ["alpha", "phi"] if args.model == "a" else ["alpha"]:
        r = float(s[p]["r_hat"]); e = float(s[p]["n_eff"])
        if r >= 1.01 or e < 400:
            flags.append(f"{p}: r_hat={r:.3f} ess={e:.0f}")
    br = s["beta"]["r_hat"]; be = s["beta"]["n_eff"]
    for i, nm in enumerate(names):
        if br[i] >= 1.01 or be[i] < 400:
            flags.append(f"beta[{nm}]: r_hat={br[i]:.3f} ess={be[i]:.0f}")

    # Posterior predictive check on the observed scale: does the simulated data
    # reproduce the observed mean/spread, and do observations fall in their
    # posterior-predictive intervals?
    pred = Predictive(regression_model, posterior_samples=flat,
                      return_sites=["y"])(jax.random.PRNGKey(SEED + 1),
        x=x, g_model=g_model, n_model=n_model, g_exp=g_exp, n_exp=n_exp,
        g_con=g_con, n_con=n_con, g_pair=g_pair, n_pair=n_pair, gamma=(args.model == "a"))
    y_rep = np.asarray(pred["y"])
    ppc = {
        "obs_mean": float(np.mean(y)),
        "ppc_mean_ci": [float(q) for q in np.percentile(y_rep.mean(axis=1), [2.5, 97.5])],
        "obs_sd": float(np.std(y)),
        "ppc_sd_mean": float(np.mean(np.std(y_rep, axis=0))),
        "obs_frac_within_ppc90": float(np.mean(
            (y[None, :] >= np.percentile(y_rep, 5, axis=0)) &
            (y[None, :] <= np.percentile(y_rep, 95, axis=0)))),
    }

    beta_mean = flat["beta"].mean(axis=0)
    corr = np.corrcoef(flat["beta"], rowvar=False)

    np.savez_compressed(OUT / f"posterior_{args.tag}.npz",
                        beta=flat["beta"], alpha=flat["alpha"],
                        beta_names=np.array(names),
                        **{k: v for k, v in flat.items() if k.startswith(("sd_", "u_")) or k == "phi"},
                        **{f"g_{k}": v for k, v in
                           [("model", g_model), ("exp", g_exp), ("con", g_con), ("pair", g_pair)]},
                        n_levels=np.array([n_model, n_exp, n_con, n_pair]))
    (OUT / f"diag_{args.tag}.json").write_text(json.dumps({
        "seed": SEED, "n_rows": int(len(df)), "n_predictors": len(names),
        "predictors": names, "n_pairs": int(n_pair),
        "num_warmup": args.warmup, "num_samples": args.samples,
        "divergences": int(np.array(mcmc.get_extra_fields()["diverging"]).sum()),
        "max_rhat_fixed": float(max(br.max(), s["alpha"]["r_hat"].max())),
        "min_ess_fixed": float(min(be.min(), s["alpha"]["n_eff"].min())),
        "beta_rhat": br.tolist(), "beta_ess": be.tolist(),
        "beta_mean": beta_mean.tolist(),
        "convergence_flags": flags, "ppc": ppc,
        "beta_corr_matrix": corr.tolist(),
    }, indent=2))
    print("divergences:", int(np.array(mcmc.get_extra_fields()["diverging"]).sum()),
          "| max r_hat (fixed):", float(max(br.max(), s["alpha"]["r_hat"].max())),
          "| flags:", len(flags))
    for f in flags:
        print("  FLAG", f)
    print(f"wrote outputs/posterior_{args.tag}.npz and outputs/diag_{args.tag}.json")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--model", choices=["a", "b"], required=True)
    p.add_argument("--tag", required=True)
    p.add_argument("--warmup", type=int, default=1000)
    p.add_argument("--samples", type=int, default=2000)
    p.add_argument("--human-seed", type=int, default=None)
    p.add_argument("--drop-qwen", action="store_true")
    p.add_argument("--exclude-experiment", default=None)
    run_nuts(p.parse_args())
