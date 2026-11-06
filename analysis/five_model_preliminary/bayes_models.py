# The three hierarchical Bayesian models and the numbers pulled from their
# posterior draws.
#
# What this file does: it defines the PyMC models comparing the original
# (synthetic-persona) pool against the redesigned (Config-A real-persona)
# pool across the five models, for each of the three outcomes:
#   1. fit_direction  — does the redesigned pool agree with the human
#                       effect's direction more often (Bernoulli-logit,
#                       hierarchical over models, experiments, contrast
#                       cells).
#   2. fit_magnitude  — how closely the model effect tracks the human
#                       effect (normal, per-pool slope on the human
#                       effect, model-level deviations partially pooled).
#   3. fit_tvd        — how far the model's answer distribution sits from
#                       the human one (normal on TVD, per-model pool
#                       effects partially pooled).
# Every model carries: model-level variation, experiment and nested
# contrast-cell variation, a persona-configuration (era) effect, a
# disclosure-condition effect, a configuration×disclosure interaction, and
# model-specific configuration effects that are partially pooled toward the
# shared configuration effect. All summaries come straight from posterior
# draws — no bootstrap anywhere.
#
# What each function does:
#   design_vectors    — the 0/1 columns (era, disclosure, interaction, z).
#   fit_direction     — model 1 (logistic, hierarchical).
#   fit_magnitude     — model 2 (normal, per-pool slopes).
#   fit_tvd           — model 3 (normal on TVD cells).
#   credible          — mean/95% interval/p(improves) from posterior draws.
#   direction_effects — config-effect draws per model and pooled, per condition.
#   magnitude_effects — |error| draws per model/era/condition + slope summaries.
#   tvd_effects       — TVD level and config-effect draws per model, per condition.

from __future__ import annotations

import numpy as np
import pymc as pm
from numpy.typing import ArrayLike

DRAWS = 2000
TUNE = 2000
CHAINS = 4
TARGET_ACCEPT = 0.995
SEED = 3235


def design_vectors(table, *, human_col: str | None = None) -> dict[str, ArrayLike]:
    """Build the 0/1 design columns the models share.

    era: 1 = redesigned (real-persona) pool. disc: 1 = disclosure
    condition. z: standardised |human effect| (used by the direction model
    so the gradient near big human effects is modelled explicitly).
    """
    cfg = (table.era == "redesigned").to_numpy(float)
    disc = (table.condition == "disclosure").to_numpy(float)
    vecs = {"cfg": cfg, "disc": disc, "inter": cfg * disc}
    if human_col is not None:
        z = np.abs(table[human_col].to_numpy(float))
        z = (z - z.mean()) / z.std()
        vecs["z"] = z
    return vecs


def _sample(model: pm.Model, seed_offset: int) -> object:
    """Sample with the shared settings; returns the ArviZ InferenceData."""
    return pm.sample(
        DRAWS, tune=TUNE, chains=CHAINS, target_accept=TARGET_ACCEPT,
        random_seed=SEED + seed_offset, progressbar=False,
    )


def fit_direction(table, prior_scale: float = 1.0) -> object:
    """Model 1: sign agreement of the model effect with the human effect.

    Partially pooled random effects for model, experiment, and contrast
    cell; model-specific configuration effects shrink toward the shared
    configuration effect (non-centred parameterisation).
    """
    v = design_vectors(table, human_col="human_std")
    y = table.sign_agrees.to_numpy(int)
    n_m = table.model_code.nunique()
    n_e = table.experiment_code.nunique()
    n_c = table.cell_code.nunique()
    m = table.model_code.to_numpy()
    e = table.experiment_code.to_numpy()
    c = table.cell_code.to_numpy()
    coords = {"model": sorted(table.model.unique()),
              "experiment": sorted(table.experiment.unique()),
              "cell": sorted((table.experiment + "|" + table.contrast_id).unique()),
              "obs": np.arange(len(y))}
    with pm.Model(coords=coords) as model:
        a = pm.Normal("a", 0.0, 1.25 * prior_scale)
        d_cfg = pm.Normal("d_config", 0.0, 1.25 * prior_scale)
        s_d = pm.HalfNormal("s_config_model", 0.75 * prior_scale)
        d_raw = pm.Normal("d_config_model_raw", 0.0, 1.0, dims="model")
        d_model = pm.Deterministic(
            "d_config_model", d_cfg + d_raw * s_d, dims="model")
        b_disc = pm.Normal("b_disclosure", 0.0, 1.25 * prior_scale)
        b_int = pm.Normal("b_config_disclosure", 0.0, 1.25 * prior_scale)
        b_grad = pm.Normal("b_human_gradient", 0.0, 1.25 * prior_scale)
        s_mod = pm.HalfNormal("s_model", 0.75 * prior_scale)
        s_exp = pm.HalfNormal("s_experiment", 0.5 * prior_scale)
        s_cell = pm.HalfNormal("s_cell", 0.5 * prior_scale)
        u_mod = pm.Deterministic("u_model", pm.Normal("u_model_raw", 0., 1, dims="model") * s_mod, dims="model")
        u_exp = pm.Deterministic("u_experiment", pm.Normal("u_experiment_raw", 0., 1, dims="experiment") * s_exp, dims="experiment")
        u_cell = pm.Deterministic("u_cell", pm.Normal("u_cell_raw", 0., 1, dims="cell") * s_cell, dims="cell")
        eta = (a + d_model[m] * v["cfg"] + b_disc * v["disc"]
               + b_int * v["inter"] + b_grad * v["z"]
               + u_mod[m] + u_exp[e] + u_cell[c])
        pm.Bernoulli("agrees", logit_p=eta, observed=y, dims="obs")
        idata = _sample(model, 0)
        idata.pp = pm.sample_posterior_predictive(idata, progressbar=False)
    return idata


def fit_magnitude(table, prior_scale: float = 1.0) -> object:
    """Model 2: predicted effect regressed on the human effect (SD units).

    Original-pool slope plus redesigned deviations in level and slope, each
    with model-specific deviations partially pooled toward the shared
    deviation. Measurement noise beyond the residual scale lives in
    s_residual.
    """
    v = design_vectors(table)
    y = table.delta_std.to_numpy(float)
    human = table.human_std.to_numpy(float)
    m = table.model_code.to_numpy()
    e = table.experiment_code.to_numpy()
    c = table.cell_code.to_numpy()
    coords = {"model": sorted(table.model.unique()),
              "experiment": sorted(table.experiment.unique()),
              "cell": sorted((table.experiment + "|" + table.contrast_id).unique()),
              "obs": np.arange(len(y))}
    with pm.Model(coords=coords) as model:
        a = pm.Normal("a", 0.0, 0.5 * prior_scale)
        slope = pm.Normal("b_slope", 1.0, 0.5 * prior_scale)
        mu_d0 = pm.Normal("d_level_config", 0.0, 0.5 * prior_scale)
        mu_d1 = pm.Normal("d_slope_config", 0.0, 0.5 * prior_scale)
        s_d0 = pm.HalfNormal("s_level_model", 0.35 * prior_scale)
        s_d1 = pm.HalfNormal("s_slope_model", 0.35 * prior_scale)
        d0_model = pm.Deterministic("d_level_model", mu_d0 + pm.Normal("d_level_model_raw", 0., 1, dims="model") * s_d0, dims="model")
        d1_model = pm.Deterministic("d_slope_model", mu_d1 + pm.Normal("d_slope_model_raw", 0., 1, dims="model") * s_d1, dims="model")
        b_disc = pm.Normal("b_disclosure", 0.0, 0.5 * prior_scale)
        b_int = pm.Normal("b_config_disclosure", 0.0, 0.5 * prior_scale)
        s_mod = pm.HalfNormal("s_model", 0.35 * prior_scale)
        s_exp = pm.HalfNormal("s_experiment", 0.35 * prior_scale)
        s_cell = pm.HalfNormal("s_cell", 0.35 * prior_scale)
        s_res = pm.HalfNormal("s_residual", 0.5 * prior_scale)
        u_mod = pm.Deterministic("u_model", pm.Normal("u_model_raw", 0., 1, dims="model") * s_mod, dims="model")
        u_exp = pm.Deterministic("u_experiment", pm.Normal("u_experiment_raw", 0., 1, dims="experiment") * s_exp, dims="experiment")
        u_cell = pm.Deterministic("u_cell", pm.Normal("u_cell_raw", 0., 1, dims="cell") * s_cell, dims="cell")
        mu = (a + u_mod[m] + slope * human + d0_model[m] * v["cfg"]
              + d1_model[m] * v["cfg"] * human + b_disc * v["disc"]
              + b_int * v["inter"] + u_exp[e] + u_cell[c])
        pm.Normal("predicted", mu=mu, sigma=s_res, observed=y, dims="obs")
        idata = _sample(model, 1)
        idata.pp = pm.sample_posterior_predictive(idata, progressbar=False)
    return idata


def fit_tvd(table, prior_scale: float = 1.0) -> object:
    """Model 3: total-variation distance from the human distribution.

    Model-specific configuration effects partially pooled toward the shared
    configuration effect, plus disclosure and configuration×disclosure
    effects and experiment variation.
    """
    v = design_vectors(table)
    y = table.tvd.to_numpy(float)
    m = table.model_code.to_numpy()
    e = table.experiment_code.to_numpy()
    coords = {"model": sorted(table.model.unique()),
              "experiment": sorted(table.experiment.unique()),
              "obs": np.arange(len(y))}
    with pm.Model(coords=coords) as model:
        a = pm.Normal("a", 0.3, 0.25 * prior_scale)
        mu_d = pm.Normal("d_config", 0.0, 0.25 * prior_scale)
        s_d = pm.HalfNormal("s_config_model", 0.2 * prior_scale)
        d_model = pm.Deterministic("d_config_model", mu_d + pm.Normal("d_config_model_raw", 0., 1, dims="model") * s_d, dims="model")
        b_disc = pm.Normal("b_disclosure", 0.0, 0.25 * prior_scale)
        b_int = pm.Normal("b_config_disclosure", 0.0, 0.25 * prior_scale)
        s_mod = pm.HalfNormal("s_model", 0.2 * prior_scale)
        s_exp = pm.HalfNormal("s_experiment", 0.15 * prior_scale)
        s_res = pm.HalfNormal("s_residual", 0.2 * prior_scale)
        u_mod = pm.Deterministic("u_model", pm.Normal("u_model_raw", 0., 1, dims="model") * s_mod, dims="model")
        u_exp = pm.Deterministic("u_experiment", pm.Normal("u_experiment_raw", 0., 1, dims="experiment") * s_exp, dims="experiment")
        mu = (a + u_mod[m] + d_model[m] * v["cfg"] + b_disc * v["disc"]
              + b_int * v["inter"] + u_exp[e])
        pm.Normal("tvd", mu=mu, sigma=s_res, observed=y, dims="obs")
        idata = _sample(model, 2)
        idata.pp = pm.sample_posterior_predictive(idata, progressbar=False)
    return idata


def credible(draws: np.ndarray, higher_is_better: bool) -> dict[str, float]:
    """Mean, 95% interval, and posterior probability of improvement."""
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return {"mean": float(draws.mean()), "lo95": float(lo), "hi95": float(hi),
            "p_improvement": float((draws > 0).mean() if higher_is_better
                                   else (draws < 0).mean())}


def direction_effects(table, idata) -> dict[str, dict[str, float]]:
    """Config-effect draws (redesigned − original) per model and pooled.

    The effect is evaluated at each disclosure condition: uninformed is the
    configuration effect alone; disclosure adds the interaction.
    """
    post = idata.posterior
    names = list(post.coords["model"].values)
    d = np.asarray(post["d_config_model"])          # (chains, draws, models)
    b_int = np.asarray(post["b_config_disclosure"]).reshape(-1)
    d = d.reshape(-1, len(names))
    out: dict[str, dict[str, float]] = {}
    pooled = np.asarray(post["d_config"]).reshape(-1)
    for cond, add in (("uninformed", 0.0), ("disclosure", 1.0)):
        eff = d if add == 0.0 else d + b_int[:, None]
        for k, name in enumerate(names):
            out[f"direction|{name}|{cond}"] = credible(eff[:, k], True)
        pooled_eff = pooled if add == 0.0 else pooled + b_int
        out[f"direction|POOLED-5|{cond}"] = credible(pooled_eff, True)
    return out


def magnitude_effects(table, idata) -> dict[str, dict[str, float]]:
    """Expected |model − human| error draws per model/era/condition."""
    post = idata.posterior
    names = list(post.coords["model"].values)
    a = np.asarray(post["a"]).reshape(-1)
    b_slope = np.asarray(post["b_slope"]).reshape(-1)
    d0 = np.asarray(post["d_level_model"])
    d1 = np.asarray(post["d_slope_model"])
    b_disc = np.asarray(post["b_disclosure"]).reshape(-1)
    b_int = np.asarray(post["b_config_disclosure"]).reshape(-1)
    d0 = d0.reshape(-1, len(names))
    d1 = d1.reshape(-1, len(names))
    out: dict[str, dict[str, float]] = {}
    for cond, disc in (("uninformed", 0.0), ("disclosure", 1.0)):
        for k, name in enumerate(names):
            sub = table[table.model == name]
            human = sub.human_std.to_numpy(float)
            # per-draw expected absolute error for each era, averaged over cells
            mu_orig = (a[:, None] + b_slope[:, None] * human[None, :]
                       + b_disc[:, None] * disc)
            mu_red = mu_orig + d0[:, k][:, None] + d1[:, k][:, None] * human[None, :]
            err = (np.abs(mu_red - human[None, :]).mean(axis=1)
                   - np.abs(mu_orig - human[None, :]).mean(axis=1))
            out[f"magnitude|{name}|{cond}"] = credible(err, False)
        pooled_d0 = np.asarray(post["d_level_config"]).reshape(-1)
        pooled_d1 = np.asarray(post["d_slope_config"]).reshape(-1)
        out[f"magnitude|POOLED-5|{cond}"] = credible(
            _pooled_mag_err(table, a, b_slope, pooled_d0, pooled_d1,
                            b_disc, disc), False)
    return out


def _pooled_mag_err(table, a, b_slope, d0, d1, b_disc, disc):
    """Pooled-5 expected |error| difference at one condition."""
    human = table.human_std.to_numpy(float)
    disc_vec = (table.condition == "disclosure").to_numpy(float)
    cfg_vec = (table.era == "redesigned").to_numpy(float)
    keep = np.isclose(disc_vec, disc)
    human = human[keep]
    mu_orig = a[:, None] + b_slope[:, None] * human[None, :]
    mu_red = mu_orig + d0[:, None] + d1[:, None] * human[None, :]
    return (np.abs(mu_red - human[None, :]).mean(axis=1)
            - np.abs(mu_orig - human[None, :]).mean(axis=1))


def tvd_effects(idata) -> dict[str, dict[str, float]]:
    """TVD config-effect draws per model and pooled, per condition."""
    post = idata.posterior
    names = list(post.coords["model"].values)
    d = np.asarray(post["d_config_model"]).reshape(-1, len(names))
    pooled = np.asarray(post["d_config"]).reshape(-1)
    b_int = np.asarray(post["b_config_disclosure"]).reshape(-1)
    out: dict[str, dict[str, float]] = {}
    for cond, add in (("uninformed", 0.0), ("disclosure", 1.0)):
        eff = d if add == 0.0 else d + b_int[:, None]
        for k, name in enumerate(names):
            out[f"tvd|{name}|{cond}"] = credible(eff[:, k], False)
        pooled_eff = pooled if add == 0.0 else pooled + b_int
        out[f"tvd|POOLED-5|{cond}"] = credible(pooled_eff, False)
    return out
