# Turns the fitted posteriors into the Stage 9 reporting deliverables.
# - REGRESSION_EFFECTS.csv: every estimable feature for BOTH outcomes, with posterior
#   mean, 95% credible interval, probability of being positive, and a translation into
#   real units (percentage-point changes in direction-correct probability for Model B;
#   changes in absolute error, in human-SD units and percent, for Model A).
# - EXPERIMENT_AVG_EFFECTS.csv: the equal-weight-per-experiment headline summary —
#   the same feature contrasts averaged over the contrasts inside each experiment
#   first, then across experiments, so big experiments don't dominate the headline.
# - EXPERIMENT_EXAMPLES.md: descriptive case sketches for a handful of named
#   experiments, with the honest caveat that they illustrate, not confirm.

import json
from pathlib import Path

import numpy as np
import pandas as pd

STAGE9 = Path(__file__).resolve().parents[1]
OUT = STAGE9 / "outputs"

# Interpretable unit changes for continuous predictors (raw units -> model works on
# standardized values, so each delta is divided by the saved SD).
DELTAS = {
    "question_length": ("+100 words", 100.0),
    "wording_difference": ("+0.10 wording difference (10pp)", 0.10),
    "manipulation_location": ("0 -> 1 manipulation location", 1.0),
    "n_response_options": ("+1 response option", 1.0),
    "human_abs_d_std": ("+0.5 SD human effect size", 0.5),
    "log_se_y_std": ("model SE doubled (log 2)", float(np.log(2))),
}
DESCRIBE = {
    "gain_loss_framing": "present vs absent",
    "numerical_manipulation": "present vs absent",
    "explicit_probability": "present vs absent",
    "negation_change": "present vs absent",
    "role_change": "present vs absent",
    "question_order": "present vs absent",
    "response_options_change": "present vs absent",
    "manipulation_location_na": "imputed (missing) vs observed",
    "n_response_options_na": "imputed (missing) vs observed",
    "disclosure": "disclosed vs blinded",
    "disclosure_x_role_change": "interaction: disclosure x role change",
    "disclosure_x_manipulation_location": "interaction: disclosure x manipulation location",
}


def load_posteriors(tag: str):
    post = np.load(OUT / f"posterior_{tag}.npz")
    names = [str(n) for n in post["beta_names"]]
    return post["beta"], post["alpha"], names


def avg_row(df: pd.DataFrame, names: list[str]) -> np.ndarray:
    return df[names].mean(axis=0).to_numpy(np.float64)


def feature_delta(names: list[str], predictor: str) -> tuple[str, float]:
    # 0/1 features move 0 -> 1; continuous features move by their interpretable delta
    # (converted from raw units to standard deviations using FEATURE_SCALING.json).
    if predictor in DELTAS:
        label, raw = DELTAS[predictor]
        scaling = json.loads((STAGE9 / "FEATURE_SCALING.json").read_text())
        sd = scaling["continuous_scaling"][predictor]["sd"]
        return label, raw / sd
    return DESCRIBE.get(predictor, "present vs absent"), 1.0


def effect_rows(outcome: str, beta: np.ndarray, alpha: np.ndarray,
                names: list[str], design: pd.DataFrame) -> list[dict]:
    xbar = avg_row(design, names)
    base = alpha + xbar @ beta.T  # per-draw linear predictor of the "average" row
    rows = []
    for j, predictor in enumerate(names):
        label, delta = feature_delta(names, predictor)
        raw = beta[:, j]
        if outcome == "A_abs_error":
            pct = np.expm1(raw * delta)  # multiplicative change in absolute error
            sd_units = pct * float(design["absolute_error"].mean())
            lo, hi = np.percentile(pct * 100, [2.5, 97.5])
            trans = float((pct * 100).mean())
            units = "% change in absolute error"
            trans2 = sd_units.mean()
        else:
            p0, p1 = 1 / (1 + np.exp(-base)), 1 / (1 + np.exp(-(base + raw * delta)))
            diff = (p1 - p0) * 100
            trans, lo, hi = (float(diff.mean()), *np.percentile(diff, [2.5, 97.5]))
            units = "percentage points of direction-correct probability"
            trans2 = np.nan
        row = {
            "outcome": outcome, "predictor": predictor, "contrast": label,
            "posterior_mean_raw": float(raw.mean()),
            "cri95_low_raw": float(np.percentile(raw, 2.5)),
            "cri95_high_raw": float(np.percentile(raw, 97.5)),
            "p_positive": float((raw > 0).mean()),
            "translated_estimate": float(trans), "translated_cri95_low": float(lo),
            "translated_cri95_high": float(hi), "translated_units": units,
        }
        if outcome == "A_abs_error":
            row["translated_abs_change_sd_units"] = float(sd_units.mean())
        rows.append(row)
    return rows


def experiment_avg_effects(outcome: str, beta: np.ndarray, alpha: np.ndarray,
                           names: list[str], design: pd.DataFrame) -> list[dict]:
    # Equal-weight-per-experiment summary: apply each feature contrast inside every
    # experiment, average within the experiment, then average the experiment means.
    rows = []
    for j, predictor in enumerate(names):
        if predictor in ("log_se_y_std",) or predictor.startswith(("disclosure_x", "fmt_",
                                                                   "selfother_")):
            continue
        label, delta = feature_delta(names, predictor)
        per_exp = []
        for exp, g in design.groupby("experiment_id"):
            xbar = avg_row(g, names)
            base = alpha + xbar @ beta.T
            if outcome == "A_abs_error":
                eff = np.expm1(beta[:, j] * delta)
            else:
                p0 = 1 / (1 + np.exp(-base))
                p1 = 1 / (1 + np.exp(-(base + beta[:, j] * delta)))
                eff = (p1 - p0) * 100
            # keep the draws axis: averaging over draws here would collapse the
            # stack to 1-D and make the percentile-based CrI undefined (NaN)
            per_exp.append(eff)
        stack = np.array(per_exp)  # experiments x draws
        est = stack.mean(axis=0)
        lo, hi = np.percentile(est, [2.5, 97.5]) if est.ndim else (np.nan, np.nan)
        rows.append({"outcome": outcome, "predictor": predictor, "contrast": label,
                     "n_experiments": len(per_exp),
                     "exp_averaged_estimate": float(np.mean(est)),
                     "exp_averaged_cri95_low": float(lo),
                     "exp_averaged_cri95_high": float(hi)})
    return rows


def experiment_examples() -> str:
    df = pd.read_csv(STAGE9 / "ANALYSIS_TABLE.csv")
    keep_feats = ["gain_loss_framing", "numerical_manipulation", "explicit_probability",
                  "negation_change", "role_change", "question_order",
                  "response_options_change", "question_length", "wording_difference",
                  "manipulation_location", "n_response_options", "self_other",
                  "response_format"]
    lines = ["# Experiment examples (illustrations, not independent confirmation)\n",
             "These sketches show which blind-coded features are present in a few named",
             "experiments and what the AI actually did there (descriptive). Consistency",
             "with fitted associations is suggestive only: these examples were picked",
             "after seeing the results and are not independent evidence.\n"]
    for cid in ["C-09", "C-26", "C-23", "C-24", "C-13", "C-14"]:
        g = df[df["contrast_id"] == cid]
        feats = g.iloc[0]
        present = [f for f in keep_feats if f in ("question_length", "wording_difference",
                                                  "manipulation_location", "n_response_options")
                   or (f in feats and feats[f] in (1, True, "other", "mixed_or_third_party"))]
        lines.append(f"\n## {cid} — {feats['experiment_id']} ({feats['study_group']})\n")
        lines.append(f"- Features flagged: {', '.join(str(p) for p in present)}")
        lines.append(f"- Human effect: d = {feats['d_human_std']:.2f} SD, "
                     f"direction confident: {bool(feats['human_direction_confident'])}")
        for col, lab in [("absolute_error", "|AI - human| (SD units)"),
                         ("correct_direction", "same direction as human")]:
            piv = g.groupby("disclosure")[col].mean()
            lines.append(f"- {lab}: blinded {piv.get(0, float('nan')):.3f}, "
                         f"disclosed {piv.get(1, float('nan')):.3f}")
        lines.append(f"- Range of AI error across the 15 models: "
                     f"{g['absolute_error'].min():.2f} to {g['absolute_error'].max():.2f} SD")
    lines.append("\nSource: ANALYSIS_TABLE.csv; descriptives only.\n")
    return "\n".join(lines)


def main() -> None:
    inputs_a = pd.read_csv(STAGE9 / "MODEL_INPUTS_A.csv")
    inputs_b = pd.read_csv(STAGE9 / "MODEL_INPUTS_B.csv")
    beta_a, alpha_a, names_a = load_posteriors("mainA")
    beta_b, alpha_b, names_b = load_posteriors("mainB")

    rows = (effect_rows("A_abs_error", beta_a, alpha_a, names_a, inputs_a)
            + effect_rows("B_direction_correct", beta_b, alpha_b, names_b, inputs_b))
    effects = pd.DataFrame(rows)
    effects.to_csv(STAGE9 / "REGRESSION_EFFECTS.csv", index=False)

    exp_rows = (experiment_avg_effects("A_abs_error", beta_a, alpha_a, names_a, inputs_a)
                + experiment_avg_effects("B_direction_correct", beta_b, alpha_b, names_b, inputs_b))
    pd.DataFrame(exp_rows).to_csv(OUT / "EXPERIMENT_AVG_EFFECTS.csv", index=False)

    (STAGE9 / "EXPERIMENT_EXAMPLES.md").write_text(experiment_examples())
    print(f"REGRESSION_EFFECTS.csv: {len(effects)} rows "
          f"({len(names_a)} + {len(names_b)} features x 1 outcome each)")
    print("wrote EXPERIMENT_AVG_EFFECTS.csv, EXPERIMENT_EXAMPLES.md")


if __name__ == "__main__":
    main()
