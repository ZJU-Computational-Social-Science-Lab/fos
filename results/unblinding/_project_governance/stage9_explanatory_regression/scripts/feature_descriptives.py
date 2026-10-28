# Generate FEATURE_DESCRIPTIVES.md from EXPERIMENT_FEATURES.csv.
# Strictly outcome-free: this script touches only the feature table and the
# contrast register; it never reads model-effect, accuracy, or y_std columns.

import csv
from collections import Counter
from math import isnan
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent

CATEGORICAL = ["response_format", "self_other"]
BINARY = [
    "role_change", "gain_loss_framing", "numerical_manipulation",
    "explicit_probability", "negation_change", "question_order",
    "response_options_change",
]
CONTINUOUS = ["question_length", "wording_difference", "manipulation_location",
              "n_response_options"]


def load_rows():
    with open(OUT_DIR / "EXPERIMENT_FEATURES.csv") as fh:
        return list(csv.DictReader(fh))


def num(value):
    return float("nan") if value == "" else float(value)


def stats(values):
    values = sorted(v for v in values if not isnan(v))
    n_nan = sum(1 for v in values if isnan(v))
    n = len(values)
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    median = values[n // 2] if n % 2 else (values[n // 2 - 1] + values[n // 2]) / 2
    return mean, median, values[0], values[-1], var ** 0.5, n_nan


def main():
    rows = load_rows()
    lines = ["# Feature descriptives (pre-regression, outcome-free)", ""]

    for feature in CATEGORICAL:
        counts = Counter(r[feature] for r in rows)
        lines.append(f"## {feature} (categorical)")
        for key, count in sorted(counts.items()):
            lines.append(f"- {key}: {count}/38 ({100 * count / 38:.0f}%)")
        lines.append("")

    lines.append("## Binary features (1 = present, of 38 contrasts)")
    lines.append("")
    lines.append("| feature | 1s | 0s |")
    lines.append("|---|---|---|")
    for feature in BINARY:
        ones = sum(int(r[feature]) for r in rows)
        lines.append(f"| {feature} | {ones} | {38 - ones} |")
    lines.append("")

    lines.append("## Continuous features")
    lines.append("")
    lines.append("| feature | mean | median | min | max | sd | NaN |")
    lines.append("|---|---|---|---|---|---|---|")
    for feature in CONTINUOUS:
        mean, median, lo, hi, sd, n_nan = stats([num(r[feature]) for r in rows])
        lines.append(
            f"| {feature} | {mean:.2f} | {median:.2f} | {lo:.2f} | {hi:.2f} "
            f"| {sd:.2f} | {n_nan} |"
        )
    lines.append("")

    # zero-variance flags
    lines.append("## Zero-variance / near-zero-variance flags")
    lines.append("")
    for feature in BINARY:
        ones = sum(int(r[feature]) for r in rows)
        if ones in (0, 38):
            lines.append(f"- {feature}: ZERO variance")
        elif ones <= 3 or ones >= 35:
            lines.append(f"- {feature}: near-zero variance ({ones}/38)")
    for feature in CATEGORICAL:
        counts = Counter(r[feature] for r in rows)
        if len(counts) == 1:
            lines.append(f"- {feature}: single category")
    lines.append("")

    # overlap between binary predictors
    lines.append("## Binary predictor overlap (Yule-style co-occurrence, counts of contrasts where both = 1)")
    lines.append("")
    lines.append("| pair | both=1 |")
    lines.append("|---|---|")
    for i, a in enumerate(BINARY):
        for b in BINARY[i + 1:]:
            both = sum(1 for r in rows if r[a] == "1" and r[b] == "1")
            if both > 0:
                lines.append(f"| {a} x {b} | {both} |")
    lines.append("")

    # within vs between experiment variation
    lines.append("## Within- vs between-experiment variation")
    lines.append("")
    by_experiment = {}
    for r in rows:
        by_experiment.setdefault(r["experiment_id"], []).append(r)
    for exp, exp_rows in sorted(by_experiment.items()):
        if len(exp_rows) > 1:
            varying = [
                f for f in BINARY + CATEGORICAL
                if len({r[f] for r in exp_rows}) > 1
            ]
            wd = [float(r["wording_difference"]) for r in exp_rows]
            lines.append(
                f"- {exp} ({len(exp_rows)} contrasts): "
                f"{'no variation in manual features' if not varying else 'varies within experiment: ' + ', '.join(varying)}; "
                f"wording_difference range {min(wd):.3f}-{max(wd):.3f}"
            )
    lines.append("")

    lines.append("## Missingness")
    lines.append("")
    n_loc_na = sum(int(r["manipulation_location_na"]) for r in rows)
    n_opt_na = sum(1 for r in rows if r["n_response_options"] == "")
    lines.append(f"- manipulation_location: {n_loc_na} NaN (all pure question-order cases; na-flagged)")
    lines.append(f"- n_response_options: {n_opt_na} NaN (free numeric entry / open estimate elicitation)")
    lines.append("")
    lines.append("No outcome data (human effects, model effects, y_std, accuracy) was read or joined in this file.")

    (OUT_DIR / "FEATURE_DESCRIPTIVES.md").write_text("\n".join(lines) + "\n")
    print("wrote FEATURE_DESCRIPTIVES.md")


if __name__ == "__main__":
    main()
