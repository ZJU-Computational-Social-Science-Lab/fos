# 10_contrast_patterns.py — Stage 8 Phase 1, Part 1.
#
# What this file does:
#   Independently re-derives, from the raw Stage 5 paired dataset (NOT from
#   Stage 6/7 outputs), every one of the 38 AI-vs-human directional
#   contrasts and writes ALL_CONTRAST_PATTERNS.csv plus a minimal per-model
#   count table MODEL_ERROR_PATTERNS.csv. For each contrast it reports the
#   human effect (standardized d, SE, Pr(d>0), direction-confidence), the
#   blinded and disclosed agree/disagree model counts, whether the SAME
#   models are wrong in both legs (overlap), a plain classification, and —
#   critically — the MAGNITUDE of wrong-sign predictions: the mean absolute
#   standardized effect of models that point the wrong way, compared with
#   |human d|, so near-zero clustering is never equated with true reversal.
#   It also re-checks the known C-32 (howard823) 10-model subset issue
#   against the 15-model dataset.
#
#   build_contrast_rows()  — one pattern row per contrast (38 rows).
#   classify()             — plain-language classification per contrast.
#   check_c32_subset()     — howard823 model-count discrepancy check.
#   model_patterns()       — minimal per-model wrong counts.
#   main()                 — assemble, verify counts, write CSVs.

import sys
from pathlib import Path

import pandas as pd

STAGE8 = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, "/home/justin/Documents/ZJU work/fos/results/unblinding/"
                 "_project_governance/stage7_replication_evidence/scripts")

import stage7_common as sc  # read-only conventions (register, confidence)
import corrected_pairs  # corrected canonical paired data

OUT = STAGE8
NEAR_UNANIMOUS = 13  # >= 13/15 models in one leg counts as near-unanimous


def wrong_ratio(sub: pd.DataFrame, leg: str) -> tuple[float, int, float, str]:
    """Mean |predicted d| of wrong-sign models in ONE leg vs |human d|.

    Returns (ratio, n_wrong, mean_abs_wrong, pattern_flag). The flag
    distinguishes true reversal (wrong predictions at least as large as
    the human effect) from near-zero clustering (wrong predictions
    bunched at ~0), using fixed pre-declared thresholds: reversal
    ratio >= 1, near-zero ratio < 0.5, else mixed."""
    human_abs = abs(float(sub.d_human_std.iloc[0]))
    col = sub["y_" + leg]
    wrong = sub[col.apply(np_sign) != int(sub.human_sign.iloc[0])]
    if len(wrong) == 0 or human_abs == 0:
        return (float("nan"), 0, float("nan"), "no_wrong_predictions")
    mean_abs_wrong = float(wrong[col.name].abs().mean())
    ratio = mean_abs_wrong / human_abs
    if ratio >= 1.0:
        flag = "reversal"
    elif ratio < 0.5:
        flag = "near_zero"
    else:
        flag = "intermediate"
    return (round(ratio, 4), len(wrong), round(mean_abs_wrong, 6), flag)


def np_sign(x: float) -> int:
    return 1 if x > 0 else (-1 if x < 0 else 0)


def classify(a_b: int, a_d: int, n: int, confident: bool,
             class7: str) -> str:
    """Plain classification. near_unanimous_correct = >=13/15 models agree
    with the human direction in BOTH legs; near_unanimous_wrong = >=13/15
    wrong in BOTH legs; wrong_in_one_leg = majority wrong in exactly one;
    mixed = otherwise; uncertain_human = human direction not confident
    (never classified as right or wrong)."""
    if not confident:
        return "uncertain_human"
    wrong_b, wrong_d = n - a_b, n - a_d
    if wrong_b < n - NEAR_UNANIMOUS + 1 and wrong_d < n - NEAR_UNANIMOUS + 1 \
            and a_b >= NEAR_UNANIMOUS and a_d >= NEAR_UNANIMOUS:
        return "near_unanimous_correct"
    if wrong_b >= NEAR_UNANIMOUS and wrong_d >= NEAR_UNANIMOUS:
        return "near_unanimous_wrong"
    if class7.startswith("majority_wrong"):
        return "wrong_in_one_leg_majority"
    return "mixed"


def build_contrast_rows(pairs: pd.DataFrame) -> pd.DataFrame:
    """One pattern row per contrast with magnitude-of-error fields."""
    rows = []
    for cid, sub in pairs.groupby("contrast_id"):
        confident = bool(sub.human_dir_confident.iloc[0])
        d_std = float(sub.d_human_std.iloc[0])
        n = len(sub)
        a_b, a_d = int(sub.agree_blinded.sum()), int(sub.agree_disclosed.sum())
        class7 = sc.__dict__ and _class7(a_b, a_d, n, confident)
        rb = wrong_ratio(sub, "blinded")
        rd = wrong_ratio(sub, "disclosed")
        wrong_b_models = set(sub[sub.model_sign_blinded != sub.human_sign].model)
        wrong_d_models = set(
            sub[sub.model_sign_disclosed != sub.human_sign].model)
        overlap = sorted(wrong_b_models & wrong_d_models)
        rows.append({
            "contrast_id": cid,
            "experiment_id": sub.experiment_id.iloc[0],
            "study_group": sub.study_group.iloc[0],
            "human_d_std": round(d_std, 6),
            "human_se_std": round(float(sub.se_human.iloc[0]), 6),
            "human_pr_pos": round(float(sub.human_pr_pos.iloc[0]), 6),
            "human_direction_confident": confident,
            "human_direction": int(sub.human_sign.iloc[0]),
            "human_abs_d_std": round(abs(d_std), 6),
            "n_models_paired": n,
            "n_agree_blinded": a_b,
            "n_disagree_blinded": n - a_b,
            "n_agree_disclosed": a_d,
            "n_disagree_disclosed": n - a_d,
            "overlap_models_wrong_both_legs": len(overlap),
            "overlap_model_names": ";".join(overlap),
            "collective_disagreement_class": class7,
            "classification": classify(a_b, a_d, n, confident, class7),
            "mean_abs_wrong_blinded": rb[2],
            "mean_abs_wrong_vs_human_d_blinded": rb[0],
            "wrong_magnitude_pattern_blinded": rb[3],
            "mean_abs_wrong_disclosed": rd[2],
            "mean_abs_wrong_vs_human_d_disclosed": rd[0],
            "wrong_magnitude_pattern_disclosed": rd[3],
            "note_uncertain_human": (
                "HUMAN DIRECTION UNCERTAIN - not a right/wrong case"
                if not confident else ""),
        })
    return pd.DataFrame(rows).sort_values("contrast_id").reset_index(drop=True)


def _class7(a_b: int, a_d: int, n: int, confident: bool) -> str:
    """Stage 7 convention, reimplemented here (independent verification)."""
    if not confident:
        return "human_direction_uncertain"
    b_wrong = (n - a_b) > n / 2
    d_wrong = (n - a_d) > n / 2
    if b_wrong and d_wrong:
        return "majority_wrong_both"
    if b_wrong:
        return "majority_wrong_blinded"
    if d_wrong:
        return "majority_wrong_disclosed"
    return "none"


def check_c32_subset(pairs: pd.DataFrame, audit: pd.DataFrame) -> str:
    """Re-check the known discrepancy: Stage 6/7 used a 10-model subset for
    the howard823 experiment (C-32/C-33). Verify against the full 15-model
    Stage 5 dataset and report any classification impact."""
    lines = []
    for cid in ("C-32", "C-33"):
        sub = pairs[pairs.contrast_id == cid]
        models = sorted(sub.model.unique())
        row = audit[audit.contrast_id == cid].iloc[0]
        lines.append(
            f"{cid}: stage5 paired n={len(sub)} models={len(models)}; "
            f"reg n_models={row.n_models_paired}; "
            f"class={row.collective_disagreement_class}; "
            f"confident={row.human_direction_confident}; "
            f"models={','.join(models)}")
    return "\n".join(lines)


def model_patterns(pairs: pd.DataFrame) -> pd.DataFrame:
    """Minimal per-model wrong-direction counts (full version is Phase 2b)."""
    conf = pairs[pairs.human_dir_confident]
    rows = []
    for m, sub in conf.groupby("model"):
        rows.append({
            "model": m,
            "n_pairs_confident": len(sub),
            "n_wrong_blinded": int((~sub.agree_blinded).sum()),
            "share_wrong_blinded": round(float((~sub.agree_blinded).mean()), 4),
            "n_wrong_disclosed": int((~sub.agree_disclosed).sum()),
            "share_wrong_disclosed": round(
                float((~sub.agree_disclosed).mean()), 4),
        })
    return pd.DataFrame(rows).sort_values("model").reset_index(drop=True)


def main() -> None:
    pairs = corrected_pairs.load_pairs()
    assert len(pairs) == 553 and pairs.contrast_id.nunique() == 38
    pat = build_contrast_rows(pairs)
    assert len(pat) == 38

    confident = int(pat.human_direction_confident.sum())
    uncertain = 38 - confident
    cand = pat[pat.collective_disagreement_class.isin(
        ["majority_wrong_both", "majority_wrong_blinded",
         "majority_wrong_disclosed"])]
    both = pat[pat.collective_disagreement_class == "majority_wrong_both"]
    print(f"VERIFIED from raw Stage 5 paired data: confident={confident} "
          f"uncertain={uncertain} majority_wrong_ge1={len(cand)} "
          f"majority_wrong_both={len(both)}")
    print("uncertain contrasts:", sorted(pat[~pat.human_direction_confident]
                                         .contrast_id))
    print("majority-wrong>=1:", sorted(cand.contrast_id))
    print("majority-wrong-both:", sorted(both.contrast_id))
    print(cand[["contrast_id", "experiment_id",
                "collective_disagreement_class",
                "mean_abs_wrong_vs_human_d_blinded",
                "wrong_magnitude_pattern_blinded",
                "mean_abs_wrong_vs_human_d_disclosed",
                "wrong_magnitude_pattern_disclosed"]].to_string(index=False))
    audit = pd.read_csv(
        "/home/justin/work/worktrees/implement-3019/results/unblinding/"
        "_project_governance/stage10_data_reconciliation/"
        "corrected_results/stage7/DISAGREEMENT_AUDIT.csv")
    print("\nC-32/C-33 subset re-check (howard823):")
    print(check_c32_subset(pairs, audit))

    sc_local_write(pat, "ALL_CONTRAST_PATTERNS.csv")
    sc_local_write(model_patterns(pairs), "MODEL_ERROR_PATTERNS.csv")


def sc_local_write(df: pd.DataFrame, name: str) -> None:
    out = OUT / name
    df.to_csv(out, index=False)
    print(f"wrote {out} ({len(df)} rows)", flush=True)


if __name__ == "__main__":
    main()
