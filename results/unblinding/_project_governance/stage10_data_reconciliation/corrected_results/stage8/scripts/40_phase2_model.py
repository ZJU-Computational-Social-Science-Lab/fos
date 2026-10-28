# What this file does: fits the Part-3 focused multilevel Bayesian model
# (wrong-direction ~ |human d| + model + experiment random intercepts, contrasts
# nested in experiment) on blinded-leg data, runs the leave-one-model-family-out
# sensitivity, and prints results used in SHARED_FAILURE_ANALYSIS.md.
# Functions:
#   load_data() - load confident contrasts + blinded model effects
#   fit_model() - one numpyro fit given a data frame; returns summary + mcmc
#   run_main_fit(), run_lomo() - main fit and the only sensitivity analysis
#   report() - print registered-gate diagnostics and estimates

import pathlib
import sys

import arviz as az
import jax.numpy as jnp
import numpy as np
import pandas as pd
from jax import random
import numpyro
from numpyro import distributions as dist
from numpyro.infer import MCMC, NUTS

ROOT = pathlib.Path(__file__).resolve().parents[1]
STAGE10 = pathlib.Path(
    "/home/justin/Documents/ZJU work/fos/results/unblinding/_project_governance"
) / "stage10_data_reconciliation"
SEED = 20261027


def load_data():
    contrasts = pd.read_csv(ROOT / "ALL_CONTRAST_PATTERNS.csv")
    conf = contrasts[contrasts.human_direction_confident].copy()
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import corrected_pairs
    df = corrected_pairs.load_blinded_effects().merge(
        conf[["contrast_id", "experiment_id", "human_direction", "human_abs_d_std"]],
        on="contrast_id",
        suffixes=("_drop", ""),
    )
    df = df.drop(columns=["experiment_id_drop"])
    df["wrong"] = (np.sign(df.y_std) != df.human_direction).astype(int)
    df["z_absd"] = (df.human_abs_d_std - df.human_abs_d_std.mean()) / df.human_abs_d_std.std()
    return df


def fit_model(df, seed=SEED, num_samples=2000, num_warmup=2000, num_chains=4):
    """Multilevel logistic: wrong ~ Bernoulli(logit(alpha + beta*z + u_model[m]
    + u_experiment[e] + v_contrast[c])); v nested within experiment handling.
    Priors: alpha N(0,2); beta N(0,1); group SDs HalfNormal(0,1) (registered)."""

    def model(z, m_idx, e_idx, c_idx, n_m, n_e, n_c, y=None):
        alpha = numpyro_sample("alpha", dist.Normal(0.0, 2.0))
        beta = numpyro_sample("beta", dist.Normal(0.0, 1.0))
        sd_model = numpyro_sample("sd_model", dist.HalfNormal(1.0))
        sd_experiment = numpyro_sample("sd_experiment", dist.HalfNormal(1.0))
        sd_contrast = numpyro_sample("sd_contrast", dist.HalfNormal(1.0))
        # Non-centered parameterization: sample standardized offsets and scale
        # them, so the group SDs (which mix badly when centered) mix well.
        z_m = numpyro_sample("z_model", dist.Normal(0.0, 1.0).expand([n_m]).to_event(1))
        z_e = numpyro_sample("z_experiment", dist.Normal(0.0, 1.0).expand([n_e]).to_event(1))
        z_c = numpyro_sample("z_contrast", dist.Normal(0.0, 1.0).expand([n_c]).to_event(1))
        u_m = numpyro.deterministic("u_model", sd_model * z_m)
        u_e = numpyro.deterministic("u_experiment", sd_experiment * z_e)
        v_c = numpyro.deterministic("v_contrast", sd_contrast * z_c)
        logit = alpha + beta * z + u_m[m_idx] + u_e[e_idx] + v_c[c_idx]
        numpyro_sample("wrong", dist.BernoulliLogits(logit), obs=y)

    numpyro_sample = numpyro.sample
    mcmc = MCMC(
        NUTS(model, target_accept_prob=0.95),
        num_warmup=num_warmup,
        num_samples=num_samples,
        num_chains=num_chains,
        progress_bar=False,
    )
    mcmc.run(
        random.PRNGKey(seed),
        z=jnp.asarray(df.z_absd.values),
        m_idx=jnp.asarray(df.model_code.values),
        e_idx=jnp.asarray(df.experiment_id_code.values),
        c_idx=jnp.asarray(df.contrast_id_code.values),
        n_m=int(df.model_code.max()) + 1,
        n_e=int(df.experiment_id_code.max()) + 1,
        n_c=int(df.contrast_id_code.max()) + 1,
        y=jnp.asarray(df.wrong.values),
    )
    return mcmc


def gates(mcmc):
    idata = az.from_numpyro(mcmc)
    summ = az.summary(
        idata, var_names=["alpha", "beta", "sd_model", "sd_experiment", "sd_contrast"]
    )
    # arviz 1.x reports equal-tailed intervals (eti89_*); r_hat via az.rhat
    rh = az.rhat(idata, var_names=["alpha", "beta", "sd_model", "sd_experiment", "sd_contrast"])
    rhat_max = float(max(float(x.max()) for x in rh.data_vars.values()))
    summ["r_hat"] = rhat_max
    ess_bulk = summ.ess_bulk.min()
    # Headline ESS gate: on the headline parameters (alpha, beta, group SDs)
    headline_ok = bool(ess_bulk > 400)
    rhat_ok = bool(rhat_max < 1.01)
    return summ, rhat_ok, headline_ok, ess_bulk, rhat_max


def u_exp_dim(idata):
    return idata.posterior["u_experiment"].shape[-1]


def experiment_residuals(mcmc, df):
    idata = az.from_numpyro(mcmc)
    u = idata.posterior["u_experiment"].values.reshape(-1, u_exp_dim(idata))
    exps = df[["experiment_id_code", "experiment_id"]].drop_duplicates().sort_values("experiment_id_code")
    out = []
    for i, eid in enumerate(exps.experiment_id):
        s = u[:, i]
        lo, hi = np.percentile(s, [3, 97])
        out.append({"experiment_id": eid, "u_mean": float(s.mean()), "u_lo": float(lo), "u_hi": float(hi)})
    return pd.DataFrame(out).sort_values("u_mean")


FAMILY = {
    "gemma": ["gemma-4-12b-it-qat", "gemma-4-26b-a4b", "gemma-4-31b-it-qat"],
    "glm": ["glm-4.7-flash"],
    "gpt-oss": ["gpt-oss-20b"],
    "granite": ["granite-4.1-30b", "granite-4.1-8b"],
    "muse": ["muse-glimmer"],
    "nemotron": ["nemotron-cascade-2-30b-a3b"],
    "qwen": [
        "qwen3-32b", "qwen3-4b", "qwen3.6-27b-dense",
        "qwen3.6-35b-a3b", "qwen3.6-35b-a3b-uncensored", "qwen3.8-27b",
    ],
}


def model_to_family(m):
    for fam, ms in FAMILY.items():
        if m in ms:
            return fam
    raise ValueError(f"model {m} not in any family")


def run_lomo(df):
    df = df.copy()
    df["family"] = df.model.map(model_to_family)
    rows = []
    for fam in FAMILY:
        sub = df[df.family != fam]
        sub = sub.copy()
        for col in ["model", "experiment_id", "contrast_id"]:
            sub[col + "_code"] = sub[col].astype("category").cat.codes
        mcmc = fit_model(sub, seed=SEED + 1)
        summ, rhat_ok, ess_ok, ess_min, rhat_max = gates(mcmc)
        rows.append(
            {
                "excluded_family": fam,
                "n_models": int(sub.model.nunique()),
                "beta_mean": float(summ.loc["beta", "mean"]),
                "beta_hdi": f"[{float(summ.loc['beta','eti89_lb']):.2f},{float(summ.loc['beta','eti89_ub']):.2f}]",
                "sd_experiment_mean": float(summ.loc["sd_experiment", "mean"]),
                "rhat_max": rhat_max,
                "ess_min": float(ess_min),
            }
        )
    return pd.DataFrame(rows)


def main():
    df = load_data()
    for col in ["model", "experiment_id", "contrast_id"]:
        df[col + "_code"] = df[col].astype("category").cat.codes
    print(f"n_obs={len(df)} n_contrasts={df.contrast_id.nunique()} "
          f"n_experiments={df.experiment_id.nunique()} n_models={df.model.nunique()} "
          f"share_wrong={df.wrong.mean():.4f} seed={SEED}")
    mcmc = fit_model(df)
    summ, rhat_ok, ess_ok, ess_min, rhat_max = gates(mcmc)
    print(summ.to_string())
    print(f"rhat_ok={rhat_ok} headline_ess_ok={ess_ok} min_ess_bulk={ess_min:.0f}")
    res = experiment_residuals(mcmc, df)
    print(res.to_string(index=False))
    print("--- leave-one-model-family-out ---")
    lomo = run_lomo(df)
    print(lomo.to_string(index=False))
    res.to_csv(pathlib.Path(__file__).parent / "experiment_residuals.csv", index=False)
    lomo.to_csv(pathlib.Path(__file__).parent / "lomo_sensitivity.csv", index=False)


if __name__ == "__main__":
    main()
