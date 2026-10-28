# ppc_benchmark.py — direction statistics and the posterior-predictive
# benchmark simulation for Stage 11 Task A.
#
# What this file does:
#   Computes the observed direction-error statistics of the Stage 10
#   signed effects (overall accuracy, quartile accuracies, majority-wrong
#   and heavily-reversed contrast counts, shared failures on large-|h|
#   contrasts, distribution of #wrong models per contrast), then reruns
#   exactly those statistics on data simulated from the fitted null
#   benchmark (compression + symmetric noise, no contrast-level term) so
#   observed and simulated numbers are directly comparable.
#
#   direction_table()      — per contrast x blinding: n models, #wrong.
#   direction_stats()      — the statistic bundle from a cell table.
#   experiment_bootstrap() — experiment-clustered bootstrap of accuracy
#                            (overall and per quartile), for A2.
#   simulate_null()        — posterior-predictive draws from the null fit,
#                            preserving real human effects, blinding, and
#                            model nuisance; shared human-benchmark draws.
#   analytic_wrong_rate()  — Phi(-beta|h|/sigma) reference rates.

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm


def direction_table(cells: pd.DataFrame) -> pd.DataFrame:
    """Per contrast x blinding: how many models predict the wrong sign.

    Wrong = sign of the signed standardized model effect differs from the
    sign of the human point estimate. Point estimates only — no cutoffs.
    """
    cells = cells.copy()
    cells["wrong"] = np.sign(cells.y) != np.sign(cells.human_effect)
    g = cells.groupby(["contrast_id", "b"])
    tab = g.agg(n_models=("wrong", "size"),
                n_wrong=("wrong", "sum"),
                experiment_id=("experiment_id", "first"),
                human_effect=("human_effect", "first"),
                abs_human=("human_effect", lambda s: s.abs().iloc[0]),
                confident=("direction_confident", "first")).reset_index()
    tab["majority_wrong"] = tab.n_wrong >= np.ceil(tab.n_models / 2)
    tab["heavily_reversed"] = tab.n_wrong >= 0.8 * tab.n_models
    return tab


def direction_stats(cells: pd.DataFrame, contrasts: pd.DataFrame) -> dict:
    """Bundle of direction statistics on a cell table (observed or
    simulated). Confidence flag comes from the shared contrast table so
    the eligibility rules are identical everywhere."""
    ct = direction_table(cells)
    conf = ct[ct.confident]
    uncert = ct[~ct.confident]
    acc_conf = 1 - conf.n_wrong.sum() / conf.n_models.sum()
    stats = {
        "acc_conf": acc_conf,
        "n_cells_conf": int(conf.n_models.sum()),
        "acc_blinded": 1 - conf[conf.b == 0].n_wrong.sum()
        / conf[conf.b == 0].n_models.sum(),
        "acc_disclosed": 1 - conf[conf.b == 1].n_wrong.sum()
        / conf[conf.b == 1].n_models.sum(),
        "quartile_acc": {},
        "majority_wrong": int(conf.majority_wrong.sum()),
        "heavily_reversed": int(conf.heavily_reversed.sum()),
        "n_contrasts_conf": int(conf.contrast_id.nunique()),
        "n_contrast_legs_conf": int(len(conf)),
        "uncertain_acc": (1 - uncert.n_wrong.sum() / uncert.n_models.sum()
                          if len(uncert) else np.nan),
        "uncertain_majority_wrong": int(uncert.majority_wrong.sum()),
        "wrong_dist": conf.groupby("n_wrong").size().to_dict(),
    }
    # Shared failures on large |h|: upper half of |human effect| among the
    # confident contrasts (median split — no arbitrary cutoff).
    med = conf.abs_human.median()
    big = conf[conf.abs_human > med]
    stats["large_h_median"] = float(med)
    stats["shared_fail_large_h"] = int(big.majority_wrong.sum())
    stats["n_large_h_legs"] = int(len(big))
    return stats, ct


def quartile_accuracies(cells: pd.DataFrame, contrasts: pd.DataFrame) -> dict:
    """Direction accuracy per |human effect| quartile (confident contrasts
    only), with cell counts; used for A2 on observed data."""
    df = cells[cells.direction_confident].merge(
        contrasts[["contrast_id", "quartile"]], on="contrast_id")
    df["right"] = np.sign(df.y) == np.sign(df.human_effect)
    out = {}
    for q, grp in df.groupby("quartile"):
        n = len(grp)
        out[q] = {"acc": float(grp.right.mean()), "n_cells": n,
                  "n_right": int(grp.right.sum())}
    # Overall = confident cells, pooled across quartiles.
    out["overall"] = {"acc": float(df.right.mean()), "n_cells": len(df),
                      "n_right": int(df.right.sum())}
    return out


def experiment_bootstrap(cells: pd.DataFrame, contrasts: pd.DataFrame,
                         n_boot: int = 5000, seed: int = 20261029) -> dict:
    """Experiment-clustered bootstrap CIs for quartile accuracies (A2).

    Resamples experiments with replacement (equal weights per experiment
    overall); returns 2.5/97.5 percentiles per quartile and overall.
    """
    rng = np.random.default_rng(seed)
    df = cells[cells.direction_confident].drop(columns=["experiment_id"],
                                               errors="ignore").merge(
        contrasts[["contrast_id", "quartile", "experiment_id"]],
        on="contrast_id")
    df["right"] = (np.sign(df.y) == np.sign(df.human_effect)).astype(float)
    exps = df.experiment_id.unique()
    accs = {q: [] for q in ["overall", "Q1", "Q2", "Q3", "Q4"]}
    for _ in range(n_boot):
        pick = rng.choice(exps, size=len(exps), replace=True)
        parts = [df[df.experiment_id == e] for e in pick]
        boot = pd.concat(parts, ignore_index=True)
        accs["overall"].append(boot.right.mean())
        for q in ["Q1", "Q2", "Q3", "Q4"]:
            sub = boot[boot.quartile == q]
            accs[q].append(sub.right.mean() if len(sub) else np.nan)
    ci = {}
    for q, vals in accs.items():
        v = np.asarray(vals, dtype=float)
        ci[q] = {"lo": float(np.nanpercentile(v, 2.5)),
                 "hi": float(np.nanpercentile(v, 97.5))}
    return ci


def simulate_null(samples: dict, cells: pd.DataFrame, contrasts: pd.DataFrame,
                  n_draws: int = 1000, seed: int = 20261029) -> dict:
    """Posterior-predictive simulation from the null benchmark.

    For each posterior draw: a single human-benchmark value is drawn per
    contrast (N(point, SE), shared across models and blinding legs), then
    every cell's AI is generated as beta_b * h* + model nuisance + N(0,
    sigma_b). The direction statistics are recomputed on each simulated
    dataset with the same eligibility rules as the observed data; we
    return the predictive distribution of each statistic.
    """
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(samples["beta"]), size=n_draws, replace=False)
    beta = np.asarray(samples["beta"])[idx]          # (S, 2)
    sd_model = np.asarray(samples["sd_model"])[idx]  # (S, 2)
    z_model = np.asarray(samples["z_model"])[idx]    # (S, 2, n_model)
    sigma = np.asarray(samples["sigma"])[idx]        # (S, 2)
    mi = cells.model_idx.to_numpy()
    ci_of_row = cells.contrast_idx.to_numpy()
    b_of_row = cells.b.to_numpy()
    c_info = contrasts.set_index("contrast_id")
    uniq_c = cells.contrast_id.drop_duplicates().tolist()
    # Human SEs per contrast (shared draws propagate the benchmark's own
    # uncertainty identically to every model of that contrast).
    h_se = np.array([c_info.loc[c].human_se for c in uniq_c])
    h_pt = np.array([c_info.loc[c].human_effect for c in uniq_c])
    max_wrong = int(cells.groupby(["contrast_id", "b"]).size().max())
    stats_acc, stats_q, stats_mw, stats_hr, stats_big, stats_dist = \
        [], [], [], [], [], []
    for s in range(n_draws):
        # One shared human-benchmark draw per contrast; every model's leg
        # of that contrast sees the same h* (so shared failures can arise
        # only through the shared benchmark or shared noise, not by
        # construction). AI = beta_b*h* + model nuisance + symmetric noise.
        h_draw = rng.normal(0.0, 1.0, size=(len(uniq_c),)) * h_se + h_pt
        h_cell = h_draw[ci_of_row]
        re = sd_model[s][b_of_row] * z_model[s][b_of_row, mi]
        eps = rng.normal(0.0, 1.0, size=len(cells))
        y = beta[s][b_of_row] * h_cell + re + sigma[s][b_of_row] * eps
        sim = cells.copy()
        sim["y"] = y
        sim["human_effect"] = h_cell
        st, ct = direction_stats(sim, contrasts)
        qa = quartile_accuracies(sim, contrasts)
        stats_acc.append([st["acc_blinded"], st["acc_disclosed"]])
        stats_q.append([qa[q]["acc"] for q in ["Q1", "Q2", "Q3", "Q4"]])
        stats_mw.append(st["majority_wrong"])
        stats_hr.append(st["heavily_reversed"])
        stats_big.append(st["shared_fail_large_h"])
        stats_dist.append([st["wrong_dist"].get(k, 0)
                           for k in range(0, max_wrong + 1)])
    return {
        "acc": np.array(stats_acc),
        "quartile": np.array(stats_q),
        "majority_wrong": np.array(stats_mw),
        "heavily_reversed": np.array(stats_hr),
        "shared_fail_large_h": np.array(stats_big),
        "wrong_dist": np.array(stats_dist),
    }


def analytic_wrong_rate(cells: pd.DataFrame, samples: dict) -> pd.DataFrame:
    """Phi(-beta|h|/sigma) reference: probability a single cell points the
    wrong way under the Gaussian null, per blinding and |h| quartile,
    using posterior-mean beta and sigma (no simulation)."""
    beta = np.asarray(samples["beta"]).mean(axis=0)
    sigma = np.asarray(samples["sigma"]).mean(axis=0)
    df = cells.copy()
    df["p_wrong_analytic"] = [
        norm.cdf(-beta[b] * abs(h) / sigma[b])
        for h, b in zip(df.human_effect, df.b)]
    return df
