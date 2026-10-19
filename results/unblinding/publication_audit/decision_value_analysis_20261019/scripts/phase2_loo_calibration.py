# Phase 2 pipeline: does calibrating blinded LLM effect estimates (strategy B/D)
# beat just disclosing the design to the model (strategy A/C)? We test this
# strictly out-of-sample: for each of 14 experiments we hide that experiment,
# fit a multiplicative calibration on the other 13, and predict the hidden one.
#
# What each part does:
#   load_data()        — reads the v2 signed-contrasts CSV and adds weights
#   fit_beta()         — fits d_m = beta * d_h through the origin (weighted)
#   beta_is_stable()   — checks if beta would survive dropping any one experiment
#   predict_loo()      — for each strategy and fold, produce held-out predictions
#   metrics()          — MAE, RMSE, signed bias, recovery slope, direction agreement
#   paired_boot()      — experiment-cluster bootstrap CI on paired error differences
#   error_structure()  — split error into systematic / structured / residual parts
#   main()             — runs everything, writes CSV/JSON outputs and RUN_LOG.md
#
# Prespecifications fixed BEFORE running (per BRIEF + Phase 1 spec §6.1):
#   - Seed: 20261010; bootstrap draws: 10,000; clusters = experiments.
#   - Fallback rule (strategies B/D): if pooled beta <= 0, OR any
#     leave-one-experiment-out refit within the training set gives beta' <= 0
#     or beta' outside [0.5*beta, 2*beta], fall back to the raw (uncalibrated)
#     prediction for that fold and flag it.
#   - Large-error thresholds: |error| > 10, 20, 30, 40 pp tail fractions.
#   - Direction agreement: conv-1 primary (exact zeros counted as incorrect,
#     zero tolerance 1e-9 pp); conv-2 sensitivity (zeros excluded).
#   - NO clipping applied: no outcome-specific physical bound is justified
#     from the spec; raw signed effects preserved everywhere.
#   - No p-values anywhere; confidence intervals only.
import json
import numpy as np
import pandas as pd
from pathlib import Path

BASE = Path("/home/justin/Documents/ZJU work/fos/results/unblinding/publication_audit")
CSV = BASE / "full_records_v2" / "v2_output" / "blinding_signed_contrasts.csv"
OUT = BASE / "decision_value_analysis_20261019"
SEED = 20261010
NDRAWS = 10_000
ZERO_TOL = 1e-9
LARGE_ERR_THRESHOLDS = [10.0, 20.0, 30.0, 40.0]
STRATEGIES = ["A", "B", "C", "D"]


def load_data():
    """Load the 262 v2 rows; recompute derived columns and 1/n_e weights."""
    d = pd.read_csv(CSV)
    assert len(d) == 262, f"expected 262 rows, got {len(d)}"
    d["H_check"] = d["d_h"].abs()
    assert np.allclose(d["H"], d["H_check"], atol=1e-9)
    assert np.allclose(d["M_B"], np.sign(d["d_h"]) * d["d_m_B"], atol=1e-9)
    assert np.allclose(d["M_U"], np.sign(d["d_h"]) * d["d_m_U"], atol=1e-9)
    assert np.allclose(d["E_B"], d["M_B"].sub(d["H"]).abs(), atol=1e-9)
    n_e = d.groupby("experiment")["contrast"].transform("count")
    d["w"] = 1.0 / n_e
    return d


def fit_beta(train, ycol):
    """Weighted through-origin slope beta in d_m = beta * d_h (raw signed)."""
    x = train["d_h"].to_numpy()
    y = train[ycol].to_numpy()
    w = train["w"].to_numpy()
    denom = float(np.sum(w * x * x))
    return float(np.sum(w * x * y) / denom) if denom > 0 else np.nan


def beta_is_stable(train, ycol, beta):
    """True unless a leave-one-experiment refit flips sign or leaves [0.5b, 2b]."""
    for e in train["experiment"].unique():
        b2 = fit_beta(train[train.experiment != e], ycol)
        if not np.isfinite(b2) or b2 <= 0 or b2 < 0.5 * beta or b2 > 2.0 * beta:
            return False
    return True


def predict_loo(d, ycol, calibrated):
    """Leave-one-experiment-out predictions. Returns per-row preds + fold table."""
    preds = pd.Series(index=d.index, dtype=float)
    fold_rows = []
    for e in sorted(d["experiment"].unique()):
        test = d[d.experiment == e]
        train = d[d.experiment != e]
        pred = test[ycol].copy()
        beta, fallback = np.nan, 0
        if calibrated:
            beta = fit_beta(train, ycol)
            if not np.isfinite(beta) or beta <= 0 or not beta_is_stable(train, ycol, beta):
                fallback = 1  # prespecified fallback: no correction this fold
            else:
                pred = test[ycol] / beta
        preds.loc[test.index] = pred
        fold_rows.append({"fold_experiment": e, "beta": beta, "fallback": fallback})
    return preds, pd.DataFrame(fold_rows)


def direction_agreement(pred, d_h, exclude_zeros=False):
    """Fraction where sign(d_h)*pred > 0. conv-1: zeros wrong; conv-2 drops zeros."""
    m = np.sign(d_h) * pred
    if exclude_zeros:
        keep = np.abs(m) > ZERO_TOL
        return float(np.mean(m[keep] > 0)) if keep.any() else np.nan
    return float(np.mean(m > ZERO_TOL))


def wmean(x, w):
    return float(np.sum(w * x) / np.sum(w))


def metrics(pred, d, label):
    """All prespecified out-of-sample metrics for one strategy/level."""
    m = np.sign(d["d_h"].to_numpy()) * pred.to_numpy()  # human-oriented prediction
    h = d["H"].to_numpy()
    err = m - h
    w = d["w"].to_numpy()
    slope = float(np.sum(w * h * m) / np.sum(w * h * h))
    row = {
        "level": label[0], "strategy": label[1],
        "n_rows": len(d), "n_fallback_folds": label[2],
        "MAE_pp": wmean(np.abs(err), w),
        "RMSE_pp": float(np.sqrt(wmean(err ** 2, w))),
        "signed_bias_pp": wmean(err, w),
        "recovery_slope": slope,
        "dir_agreement_conv1": direction_agreement(pred.to_numpy(), d["d_h"].to_numpy()),
        "dir_agreement_conv2": direction_agreement(pred.to_numpy(), d["d_h"].to_numpy(), True),
    }
    for t in LARGE_ERR_THRESHOLDS:
        row[f"frac_abserr_gt_{int(t)}pp"] = wmean((np.abs(err) > t).astype(float), w)
    return row, err


def paired_boot(d, err_a, err_b, clusters, seed_offset):
    """CI on mean paired difference (err_a - err_b), resampling experiments."""
    rng = np.random.default_rng(SEED + seed_offset)
    tmp = pd.DataFrame({"experiment": clusters, "diff": err_a - err_b, "w": d["w"].to_numpy()})
    point = wmean(tmp["diff"].to_numpy(), tmp["w"].to_numpy())
    exps = tmp["experiment"].unique()
    draws = []
    for _ in range(NDRAWS):
        pick = rng.choice(exps, size=len(exps), replace=True)
        parts = [tmp[tmp.experiment == e].assign(k=i) for i, e in enumerate(pick)]
        dd = pd.concat(parts)
        draws.append(wmean(dd["diff"].to_numpy(), dd["w"].to_numpy()))
    arr = np.asarray(draws, dtype=float)
    arr = arr[np.isfinite(arr)]
    lo, hi = np.percentile(arr, [2.5, 97.5])
    return point, lo, hi


def error_structure(d, pred, strategy, level):
    """Decompose weighted MSE into systematic / structured / residual parts."""
    m = np.sign(d["d_h"].to_numpy()) * pred.to_numpy()
    err = m - d["H"].to_numpy()
    w = d["w"].to_numpy()
    mse = wmean(err ** 2, w)
    bias = wmean(err, w)
    rows = [{"level": level, "strategy": strategy, "component": "systematic",
             "share_of_mse": (bias ** 2) / mse if mse > 0 else np.nan,
             "value_pp": bias ** 2, "detail": "squared overall signed bias"}]
    for grp in ["experiment", "model", "paradigm_family"]:
        # structured = weighted variance of group mean signed errors
        gmeans = d.assign(e=err).groupby(grp).apply(
            lambda g: wmean(g["e"].to_numpy(), g["w"].to_numpy()), include_groups=False)
        gw = d.groupby(grp)["w"].sum()
        p = (gw / gw.sum()).to_numpy()
        var_between = float(np.sum(p * (gmeans.to_numpy() - bias) ** 2))
        rows.append({"level": level, "strategy": strategy,
                     "component": f"structured_{grp}", "share_of_mse": var_between / mse,
                     "value_pp": var_between, "detail": "weighted variance of group mean signed errors"})
    residual = mse - bias ** 2 - sum(r["share_of_mse"] * mse for r in rows[1:])
    rows.append({"level": level, "strategy": strategy, "component": "residual",
                 "share_of_mse": residual / mse, "value_pp": residual,
                 "detail": "remainder; NOT called random without a predictability test"})
    # held-out test of error predictability from |d_h|: slope of signed error on H
    h = d["H"].to_numpy()
    mh = wmean(h, w)
    slope_eh = float(np.sum(w * (h - mh) * (err - bias)) / np.sum(w * (h - mh) ** 2))
    rows.append({"level": level, "strategy": strategy, "component": "error_vs_H_slope",
                 "share_of_mse": np.nan, "value_pp": slope_eh,
                 "detail": "weighted slope of signed error on |d_h| (out-of-sample)"})
    return rows


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    d = load_data()
    exps = sorted(d["experiment"].unique())
    assert len(exps) == 14
    anchor_models = d[d.paradigm_family == "anchoring"].model.nunique()
    print(f"anchoring models: {anchor_models} (4 excluded models documented in spec)")

    per_pred, beta_rows, struct_rows = [], [], []
    metrics_rows = []
    fallback_counts = {}
    for strat, ycol, calib in [("A", "d_m_B", False), ("B", "d_m_B", True),
                               ("C", "d_m_U", False), ("D", "d_m_U", True)]:
        preds, folds = predict_loo(d, ycol, calib)
        fallback_counts[strat] = int(folds["fallback"].sum())
        beta_table = folds.copy()
        beta_table.insert(0, "strategy", strat)
        beta_rows.append(beta_table)
        pp = d[["model", "experiment", "contrast", "paradigm_family", "d_h", "H", "w"]].copy()
        pp["strategy"] = strat
        pp["predicted_pp"] = preds
        pp["oriented_pred_pp"] = np.sign(d["d_h"]) * preds
        pp["signed_error_pp"] = pp["oriented_pred_pp"] - pp["H"]
        pp["abs_error_pp"] = pp["signed_error_pp"].abs()
        pp = pp.merge(folds.rename(columns={"fold_experiment": "experiment"}),
                      on="experiment")
        per_pred.append(pp)
        row, _ = metrics(preds, d, ("model_contrast", strat, fallback_counts[strat]))
        metrics_rows.append(row)
        struct_rows += error_structure(d, preds, strat, "model_contrast")
        # family-level detail for anchoring transfer
        for fam, g in d.groupby("paradigm_family"):
            gp = preds.loc[g.index]
            ae = (np.sign(g["d_h"]) * gp - g["H"]).abs()
            struct_rows.append({"level": "family", "strategy": strat,
                                "component": f"MAE_{fam}", "share_of_mse": np.nan,
                                "value_pp": wmean(ae.to_numpy(), g["w"].to_numpy()),
                                "detail": f"n_rows={len(g)}"})
    per_pred = pd.concat(per_pred)
    pd.concat(beta_rows).to_csv(OUT / "phase2_beta_table.csv", index=False)
    per_pred.to_csv(OUT / "phase2_per_prediction.csv", index=False)

    # secondary level: model-averaged contrast cells
    cm = per_pred[per_pred.strategy == "A"].groupby(
        ["experiment", "contrast"], as_index=False)[["H", "w"]].first()
    for strat in STRATEGIES:
        g = per_pred[per_pred.strategy == strat].groupby(
            ["experiment", "contrast"], as_index=False)["oriented_pred_pp"].mean()
        g = g.rename(columns={"oriented_pred_pp": f"oriented_pred_pp{strat}"})
        cm = cm.merge(g, on=["experiment", "contrast"])
    mrows = []
    for strat in STRATEGIES:
        m = cm[f"oriented_pred_pp{strat}"].to_numpy()
        h = cm["H"].to_numpy()
        w = cm["w"].to_numpy()
        err = np.sign(1) * m - h  # already human-oriented
        mrows.append({"level": "contrast_cell", "strategy": strat, "n_rows": len(cm),
                      "n_fallback_folds": fallback_counts[strat],
                      "MAE_pp": wmean(np.abs(err), w),
                      "RMSE_pp": float(np.sqrt(wmean(err ** 2, w))),
                      "signed_bias_pp": wmean(err, w),
                      "recovery_slope": float(np.sum(w * h * m) / np.sum(w * h * h))})
    metrics_rows += mrows
    metrics_df = pd.DataFrame(metrics_rows)
    metrics_df.to_csv(OUT / "phase2_metrics_summary.csv", index=False)

    # paired differences of held-out abs errors (primary level, weighted)
    ae = {s: per_pred[per_pred.strategy == s].sort_values(
        ["experiment", "model", "contrast"])["abs_error_pp"].to_numpy() for s in STRATEGIES}
    keep = per_pred[per_pred.strategy == "A"].sort_values(
        ["experiment", "model", "contrast"])[["experiment", "w"]]
    pairs, offset = [], 0
    for a, b in [("B", "C"), ("A", "B"), ("A", "C"), ("C", "D"), ("B", "D")]:
        pt, lo, hi = paired_boot(keep, ae[a], ae[b], keep["experiment"].to_numpy(), offset)
        offset += 1
        pairs.append({"comparison": f"{a}-{b}", "mean_diff_pp": pt,
                      "ci_low_pp": lo, "ci_high_pp": hi,
                      "note": "positive = first strategy has larger abs error"})
    pd.DataFrame(pairs).to_csv(OUT / "phase2_paired_diff_bootstrap.csv", index=False)

    pd.DataFrame(struct_rows).to_csv(OUT / "phase2_error_structure.csv", index=False)

    # Secondary: model-specific LOO betas (fit each model's rows only), with
    # instability reporting per the brief (fallback rules identical to pooled).
    mrows = []
    for strat, ycol in [("B", "d_m_B"), ("D", "d_m_U")]:
        for e in exps:
            train = d[d.experiment != e]
            for mod, gtr in train.groupby("model"):
                b = fit_beta(gtr, ycol)
                fb = int((not np.isfinite(b)) or b <= 0 or not beta_is_stable(gtr, ycol, b))
                mrows.append({"strategy": strat, "fold_experiment": e, "model": mod,
                              "beta": b, "fallback": fb})
    mb = pd.DataFrame(mrows)
    mb.to_csv(OUT / "phase2_beta_model_table.csv", index=False)
    print("model-specific fallback fraction by strategy:")
    print(mb.groupby("strategy")["fallback"].mean())

    summary = {
        "seed": SEED, "n_bootstrap_draws": NDRAWS, "n_rows": 262,
        "n_experiments": 14, "anchoring_n_models": int(anchor_models),
        "fallback_folds_by_strategy": fallback_counts,
        "metrics_primary_level": metrics_rows[:4],
        "paired_differences": pairs,
    }
    (OUT / "phase2_summary.json").write_text(json.dumps(summary, indent=2, default=float))
    print(json.dumps(summary, indent=2, default=float))


if __name__ == "__main__":
    main()
