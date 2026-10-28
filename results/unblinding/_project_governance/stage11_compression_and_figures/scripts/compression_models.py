# compression_models.py — the hierarchical NumPyro models for Stage 11
# Task A and helpers to fit them and summarize the posterior.
#
# What this file does:
#   Defines every model fitted in the analysis, all non-centered with
#   regularizing priors (HalfNormal(0.5) for group SDs, following Stage 9's
#   convention), plus a fit helper (NUTS, 4 chains, recorded seed,
#   target_accept 0.90) and a posterior-summary helper.
#
#   model_compression()        — A1: AI = alpha + beta_m*Human + experiment
#                                and model intercept noise + residual;
#                                zero_intercept=True drops alpha and the
#                                model intercepts (pure compression variant).
#   model_null_bench()         — A3 null: AI = beta_b*Human + model-level
#                                nuisance per blinding + symmetric noise;
#                                NO contrast-level term.
#   model_shared_residual()    — A3 comparison: null + one shared
#                                contrast-level residual component.
#   run_nuts()                 — fit a model, return mcmc + samples.
#   summarize()                — posterior mean, 95% CrI, R-hat, ESS per site.
#   sign_preservation_check()  — synthetic check: with zero noise, pure
#                                compression (beta*Human) never flips sign.

from __future__ import annotations

import jax.numpy as jnp
import numpy as np
from numpyro import diagnostics, distributions as dist, handlers, infer

SEED = 20261029
NUM_WARMUP = 800
NUM_SAMPLES = 800
NUM_CHAINS = 4

# Parallel chains on CPU (32-core host).
import numpyro  # noqa: E402
numpyro.set_host_device_count(NUM_CHAINS)


def model_compression(y, h, exp_idx, model_idx, n_exp, n_model,
                      zero_intercept=False):
    """A1 regression of signed standardized AI effect on human effect.

    Pooled slope with model-level slope deviations (partial pooling);
    experiment and (unless zero_intercept) model random intercepts;
    Gaussian residual. All group terms non-centered.
    """
    alpha = jnp.float32(0.0)
    if not zero_intercept:
        alpha = numpyro_sample("alpha", dist.Normal(0.0, 1.0))
    beta = numpyro_sample("beta", dist.Normal(0.0, 1.0))
    sd_beta_m = numpyro_sample("sd_beta_m", dist.HalfNormal(0.5))
    z_beta_m = numpyro_sample("z_beta_m", dist.Normal(0., 1.).expand([n_model]))
    beta_m = beta + sd_beta_m * z_beta_m
    sd_exp = numpyro_sample("sd_exp", dist.HalfNormal(0.5))
    z_exp = numpyro_sample("z_exp", dist.Normal(0., 1.).expand([n_exp]))
    exp_re = sd_exp * z_exp
    model_re = jnp.zeros(n_model)
    if not zero_intercept:
        sd_model = numpyro_sample("sd_model", dist.HalfNormal(0.5))
        z_model = numpyro_sample("z_model",
                                 dist.Normal(0., 1.).expand([n_model]))
        model_re = sd_model * z_model
    sigma = numpyro_sample("sigma", dist.HalfNormal(1.0))
    mu = alpha + beta_m[model_idx] * h + exp_re[exp_idx] + model_re[model_idx]
    numpyro_sample("y", dist.Normal(mu, sigma), obs=y)


def model_null_bench(y, h, model_idx, b, n_model):
    """A3 null benchmark, both blinding conditions in one fit.

    AI = beta_b * Human + model-level nuisance (per blinding) + symmetric
    zero-centered Gaussian noise with scale sigma_b. There is deliberately
    no contrast-level directional adjustment of any kind.
    """
    beta = numpyro_sample("beta", dist.Normal(0.0, 1.0).expand([2]))
    sd_model = numpyro_sample("sd_model", dist.HalfNormal(0.5).expand([2]))
    z_model = numpyro_sample(
        "z_model", dist.Normal(0., 1.).expand([2, n_model]))
    model_re = sd_model[b] * z_model[b, model_idx]
    sigma = numpyro_sample("sigma", dist.HalfNormal(1.0).expand([2]))
    mu = beta[b] * h + model_re
    numpyro_sample("y", dist.Normal(mu, sigma[b]), obs=y)


def model_shared_residual(y, h, contrast_idx, model_idx, b, n_contrast,
                          n_model):
    """A3 comparison model: the null plus ONE shared contrast-level
    residual component (a single contrast random intercept, common to both
    blinding legs). Its estimated variance answers whether a shared
    contrast-level error materially improves the shared-error pattern."""
    beta = numpyro_sample("beta", dist.Normal(0.0, 1.0).expand([2]))
    sd_model = numpyro_sample("sd_model", dist.HalfNormal(0.5).expand([2]))
    z_model = numpyro_sample(
        "z_model", dist.Normal(0., 1.).expand([2, n_model]))
    model_re = sd_model[b] * z_model[b, model_idx]
    sd_contrast = numpyro_sample("sd_contrast", dist.HalfNormal(0.5))
    z_contrast = numpyro_sample("z_contrast",
                                dist.Normal(0., 1.).expand([n_contrast]))
    contrast_re = sd_contrast * z_contrast
    sigma = numpyro_sample("sigma", dist.HalfNormal(1.0).expand([2]))
    mu = beta[b] * h + model_re + contrast_re[contrast_idx]
    numpyro_sample("y", dist.Normal(mu, sigma[b]), obs=y)


def numpyro_sample(name, distribution, **kwargs):
    """Thin wrapper so the models stay readable without a global import."""
    import numpyro
    return numpyro.sample(name, distribution, **kwargs)


def run_nuts(model, args, kwargs, seed_offset=0):
    """Fit a model with NUTS and return (mcmc, posterior samples dict)."""
    kernel = infer.NUTS(model, target_accept_prob=0.90)
    mcmc = infer.MCMC(kernel, num_warmup=NUM_WARMUP, num_samples=NUM_SAMPLES,
                      num_chains=NUM_CHAINS, progress_bar=False)
    mcmc.run(jax_random(SEED + seed_offset), *args, **kwargs)
    return mcmc, mcmc.get_samples()


def jax_random(seed):
    import jax
    return jax.random.PRNGKey(seed)


def summarize(samples: dict) -> dict:
    """Posterior mean, 95% CrI, R-hat and ESS per named parameter.

    Chains are stacked back into (chain, draw, ...) shape for the
    diagnostics; returns {name: {mean, lo, hi, r_hat, n_eff, divergences
    handled separately}}.
    """
    out = {}
    for name, draws in samples.items():
        arr = np.asarray(draws, dtype=np.float64)
        flat = arr.reshape(-1, *arr.shape[1:]) if arr.ndim >= 1 else arr
        per_chain = arr.reshape(NUM_CHAINS, -1, *arr.shape[1:])
        split = diagnostics.split_gelman_rubin(per_chain) \
            if per_chain.shape[1] > 1 else np.array([1.0])
        flat_draws = flat.reshape(-1)
        out[name] = {
            "mean": float(np.mean(flat_draws)),
            "lo": float(np.quantile(flat_draws, 0.025)),
            "hi": float(np.quantile(flat_draws, 0.975)),
            "r_hat": float(np.max(split)),
            "n_eff": float(diagnostics.effective_sample_size(per_chain)
                           .min()) if per_chain.shape[1] > 2 else float("nan"),
        }
    return out


def divergences(mcmc) -> int:
    """Number of divergent transitions (extra sensitivity reported)."""
    extra = mcmc.get_extra_fields(group_by_chain=True)
    return int(np.asarray(extra.get("diverging", [])).sum())


def sign_preservation_check() -> None:
    """Synthetic check from the brief: a pure compression model
    AI = beta*Human with beta > 0 can never flip the human sign, whatever
    beta (as long as it is positive) — only added intercept/noise can.
    Asserts this on synthetic data and raises on violation."""
    rng = np.random.default_rng(SEED)
    h = rng.normal(size=10000)
    for beta in [0.05, 0.3, 1.0, 5.0]:
        flips = int(np.sum(np.sign(beta * h) != np.sign(h)))
        if flips != 0:
            raise AssertionError(
                f"pure compression with beta={beta} flipped {flips} signs")
    # With additive noise it can flip — sanity that the test can detect it.
    flips_noisy = int(np.sum(np.sign(0.3 * h + rng.normal(scale=1.0,
                                                       size=10000))
                             != np.sign(h)))
    if flips_noisy == 0:
        raise AssertionError("noisy variant never flipped — check broken")
    print(f"[sign check] pure compression never flips (4 betas, n=10000); "
          f"with unit noise flips={flips_noisy} (expected >0)")
