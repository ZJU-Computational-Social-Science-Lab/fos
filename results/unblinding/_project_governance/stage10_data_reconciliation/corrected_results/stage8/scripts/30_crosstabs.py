# 30_crosstabs.py — Stage 8 Phase 1, Part 2 (step 2: the join).
#
# What this file does:
#   Runs AFTER the coding was frozen (20_experiment_characteristics.py) and
#   joins the 31 coded experiments to the AI-accuracy results from Part 1
#   (ALL_CONTRAST_PATTERNS.csv), then writes CHARACTERISTICS_CROSSTABS.md —
#   purely descriptive cross-tabs of failures vs agreements by each coded
#   characteristic. No inferential models, no post-hoc categories.

from pathlib import Path

import pandas as pd

STAGE8 = Path(__file__).resolve().parents[1]

WRONG_CLASSES = {"majority_wrong_both", "majority_wrong_blinded",
                 "majority_wrong_disclosed"}


def contrast_table() -> pd.DataFrame:
    """Contrast-level outcomes joined to the frozen experiment coding."""
    pat = pd.read_csv(STAGE8 / "ALL_CONTRAST_PATTERNS.csv")
    cod = pd.read_csv(STAGE8 / "EXPERIMENT_CHARACTERISTICS.csv")
    df = pat.merge(cod, on="experiment_id", validate="many_to_one")
    assert len(df) == 38
    df["outcome"] = df.collective_disagreement_class.map(
        lambda c: ("majority_wrong" if c in WRONG_CLASSES
                   else "uncertain_human" if c == "human_direction_uncertain"
                   else "agreement_or_mixed"))
    return df


def crosstab(df: pd.DataFrame, col: str) -> pd.DataFrame:
    ct = pd.crosstab(df[col], df.outcome)
    for c in ("agreement_or_mixed", "majority_wrong", "uncertain_human"):
        if c not in ct:
            ct[c] = 0
    ct = ct[["agreement_or_mixed", "majority_wrong", "uncertain_human"]]
    ct["n_contrasts"] = ct.sum(axis=1)
    return ct.sort_values("majority_wrong", ascending=False)


def magnitude_block(df: pd.DataFrame) -> str:
    """Wrong-sign prediction magnitude per majority-wrong contrast, so
    near-zero clustering is never read as true reversal."""
    rows = df[df.collective_disagreement_class.isin(WRONG_CLASSES)]
    lines = []
    for _, r in rows.iterrows():
        lines.append(
            f"| {r.contrast_id} {r.experiment_id} | {r.human_abs_d_std:.2f} | "
            f"{r.mean_abs_wrong_blinded:.2f} | {r.mean_abs_wrong_vs_human_d_blinded:.2f}x "
            f"({r.wrong_magnitude_pattern_blinded}) | "
            f"{r.mean_abs_wrong_disclosed:.2f} | "
            f"{r.mean_abs_wrong_vs_human_d_disclosed:.2f}x "
            f"({r.wrong_magnitude_pattern_disclosed}) |")
    return "\n".join(lines)


def to_md(ct: pd.DataFrame) -> str:
    """Render a crosstab as a markdown table without extra deps."""
    head = "| " + " | ".join(["category", *ct.columns]) + " |"
    sep = "|" + "---|" * (len(ct.columns) + 1)
    body = "\n".join("| " + " | ".join([str(i)] + [str(v) for v in row])
                     + " |" for i, row in ct.iterrows())
    return "\n".join([head, sep, body])


def main() -> None:
    df = contrast_table()
    lines = [
        "# CHARACTERISTICS_CROSSTABS.md — Stage 8 Phase 1, Part 2",
        "",
        "Descriptive only. The characteristics were coded from the raw",
        "experimental instructions BEFORE any accuracy number was joined",
        "(ordering evidence: 20_experiment_characteristics.py writes",
        "EXPERIMENT_CHARACTERISTICS.csv; this script runs second and is the",
        "only place where coding meets accuracy). Unit = one contrast",
        "(38 contrasts over 31 experiments). 'majority_wrong' = majority of",
        "paired models point against the confident human direction in at",
        "least one blinding leg (7 contrasts). 'uncertain_human' = human",
        "direction not confident (6 contrasts, kept but never classified).",
        "",
        "## Outcome by judgment_type",
        to_md(crosstab(df, "judgment_type")),
        "",
        "## Outcome by response_format",
        to_md(crosstab(df, "response_format")),
        "",
        "## Outcome by task_nature flag (contrast counts)",
        "",
    ]
    for col in ["flag_emotional_reactions", "flag_incentives_at_stake",
                "flag_social_expectations", "flag_uncertainty_prominent",
                "flag_scenario_interpretation"]:
        df["flag_txt"] = df[col].map({1: "present", 0: "absent"})
        lines += [f"### {col}", to_md(crosstab(df, "flag_txt")), ""]
    lines += [
        "## Outcome by human effect size (|d| quartiles, confident contrasts only)",
        "",
    ]
    conf = df[~df.human_direction_confident.isna()].copy()
    conf = df[df.human_direction_confident].copy()
    conf["size_bin"] = pd.cut(conf.human_abs_d_std,
                              [0, 0.2, 0.5, 1.0, 10],
                              labels=["small (<=0.2)", "0.2-0.5",
                                      "0.5-1.0", "large (>1.0)"])
    lines += [to_md(crosstab(conf, "size_bin")), "",
              "## Majority-wrong contrasts: magnitude of the error",
              "",
              "| contrast | human \\|d\\| | blinded mean \\|wrong d\\| | "
              "ratio (pattern) | disclosed mean \\|wrong d\\| | ratio "
              "(pattern) |",
              "|---|---|---|---|---|---|",
              magnitude_block(df), "",
              "Reading: a ratio well below 1 means wrong-sign predictions",
              "cluster near zero (models shrink the effect), NOT that they",
              "reverse it. C-26, C-30 and C-37 are the only clear",
              "reversals (2-7x the human effect); C-09's wrong predictions",
              "average ~0.3x the human d — massive shrinkage, not",
              "inversion.", ""]
    out = STAGE8 / "CHARACTERISTICS_CROSSTABS.md"
    out.write_text("\n".join(lines))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
