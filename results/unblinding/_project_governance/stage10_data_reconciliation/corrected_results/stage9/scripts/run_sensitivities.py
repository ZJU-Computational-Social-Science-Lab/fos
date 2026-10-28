# Runs the four focused sensitivity analyses required by the Stage 9 spec.
# A. Human uncertainty: refit Model A on 10 replicated datasets in which the human
#    benchmark of each contrast is redrawn from its own published uncertainty (one
#    shared draw per contrast, never an independent draw per model). Short-chain
#    refits; we report how much the key coefficients move.
# B. Model families: refit Models A and B without the Qwen family and check whether
#    the major effects persist.
# C. Influence: leave-one-experiment-out refits of Model A, tracking the disclosure
#    and human-effect-size coefficients (diagnostics only, not a specification search).
# D. Paired-disclosure comparison: compare the model's average disclosure effect with
#    the Stage 6 direction/disclosure results and explain differences in outcome and
#    weighting. Pure computation on saved posteriors + Stage 6 files.
# Writes outputs/sensitivity_A_B_C.json and outputs/sensitivity_D.json.

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

STAGE9 = Path(__file__).resolve().parents[1]
OUT = STAGE9 / "outputs"
SCRIPT = STAGE9 / "scripts" / "fit_models.py"
SEED = 20261028
VENV_PY = "/home/justin/Documents/ZJU work/fos/venv/bin/python"

HUMAN_DRAWS = 10          # replicated human-benchmark draws (short-chain refits)
SHORT = ["--warmup", "500", "--samples", "750"]


def refit(model: str, tag: str, extra: list[str]) -> dict:
    cmd = [VENV_PY, str(SCRIPT), "--model", model, "--tag", tag] + SHORT + extra
    print(">>", " ".join(cmd), flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout, r.stderr, file=sys.stderr)
        raise RuntimeError(f"refit {tag} failed")
    diag = json.loads((OUT / f"diag_{tag}.json").read_text())
    return {"tag": tag, "beta_mean": diag["beta_mean"], "predictors": diag["predictors"],
            "divergences": diag["divergences"], "max_rhat_fixed": diag["max_rhat_fixed"]}


def key_coefs(result: dict) -> dict:
    b = dict(zip(result["predictors"], result["beta_mean"]))
    return {k: float(b[k]) for k in ["disclosure", "disclosure_x_role_change",
                                     "disclosure_x_manipulation_location",
                                     "human_abs_d_std", "log_se_y_std"]}


def sensitivity_a() -> dict:
    runs = [key_coefs(refit("a", f"sensA{k:02d}", ["--human-seed", str(k)]))
            for k in range(1, HUMAN_DRAWS + 1)]
    keys = runs[0].keys()
    out = {}
    for k in keys:
        vals = np.array([r[k] for r in runs])
        out[k] = {"mean_across_draws": float(vals.mean()),
                  "sd_across_draws": float(vals.std(ddof=1)),
                  "range": [float(vals.min()), float(vals.max())]}
    return {"n_draws": HUMAN_DRAWS, "short_chain_settings": SHORT, "coefficients": out}


def sensitivity_b() -> dict:
    out = {}
    for model, tag in [("a", "sensB_A"), ("b", "sensB_B")]:
        r = refit(model, tag, ["--drop-qwen"])
        b = dict(zip(r["predictors"], r["beta_mean"]))
        out[tag] = {"n": r["divergences"], "max_rhat": r["max_rhat_fixed"],
                    "key_coefs": key_coefs(r), "beta_mean": r["beta_mean"],
                    "predictors": r["predictors"]}
    return out


def sensitivity_c(experiments: list[str]) -> dict:
    rows = []
    for e in experiments:
        r = refit("a", f"loo_{e}", ["--exclude-experiment", e])
        rows.append({"experiment_excluded": e, **key_coefs(r)})
    return {"settings": SHORT, "leave_one_out": rows}


def sensitivity_d() -> dict:
    post = np.load(OUT / "posterior_mainA.npz")
    names = [str(n) for n in post["beta_names"]]
    beta = post["beta"]
    di, ri, mi = names.index("disclosure"), names.index("disclosure_x_role_change"), \
        names.index("disclosure_x_manipulation_location")
    # Average disclosure effect over the data's role-change and manipulation-location mix.
    df = pd.read_csv(STAGE9 / "MODEL_INPUTS_A.csv")
    rc, ml = df["role_change"].mean(), df["manipulation_location"].mean()
    eff = beta[:, di] + beta[:, ri] * rc + beta[:, mi] * ml
    lo, hi = np.percentile(eff, [2.5, 97.5])
    model_res = {"outcome": "log absolute-error ratio (disclosure vs blinded)",
                 "mean": float(eff.mean()), "cri95": [float(lo), float(hi)]}

    s6 = pd.read_csv(Path("/home/justin/work/worktrees/implement-3014/_project_governance/stage10_data_reconciliation/"
                     "corrected_results/stage6/"
                     "DISCLOSURE_ACCURACY_SUMMARY.csv"))
    stage6 = s6[["measure", "weighting", "estimate_sd", "cri95_low", "cri95_high",
                 "n_experiments", "note"]].to_dict("records")
    (OUT / "sensitivity_D.json").write_text(json.dumps(
        {"model_A_average_disclosure_effect": model_res, "stage6_results": stage6}, indent=2))
    print("wrote outputs/sensitivity_D.json")
    return model_res


def main() -> None:
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("a", "all"):
        res = sensitivity_a()
        (OUT / "sensitivity_A.json").write_text(json.dumps(res, indent=2))
        print("wrote outputs/sensitivity_A.json", flush=True)
    if which in ("b", "all"):
        res = sensitivity_b()
        (OUT / "sensitivity_B.json").write_text(json.dumps(res, indent=2))
        print("wrote outputs/sensitivity_B.json", flush=True)
    if which in ("d", "all"):
        sensitivity_d()
    if which in ("c", "all"):
        df = pd.read_csv(STAGE9 / "MODEL_INPUTS_A.csv")
        experiments = sorted(df["experiment_id"].unique())
        res = sensitivity_c(experiments)
        (OUT / "sensitivity_C.json").write_text(json.dumps(res, indent=2))
        print("wrote outputs/sensitivity_C.json", flush=True)


if __name__ == "__main__":
    main()
