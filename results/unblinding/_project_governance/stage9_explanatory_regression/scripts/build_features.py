# Reconcile the two manual coding passes, join them with the script-computed
# text features, verify contrast-id set equality with the frozen Stage 5
# dataset, and write EXPERIMENT_FEATURES.csv plus a reconciliation summary.
#
# Functions:
#   load_*()      -> read the pass files / text features / stage5 ids
#   reconcile()   -> compare pass1 vs pass2 per feature, report disagreements
#   build_rows()  -> assemble the final feature table with provenance columns
#   main()        -> write EXPERIMENT_FEATURES.csv and CODING_RECONCILIATION.md

import csv
import json
from pathlib import Path

from arm_texts_original import CONTRAST_ARMS_ORIGINAL
from arm_texts_expansion import CONTRAST_ARMS_EXPANSION

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE.parent
STAGE5 = OUT_DIR.parent / "stage5_exploratory" / "data" / "stage5_dataset.csv"
REGISTER = OUT_DIR.parent / "stage3_methodology" / "CONTRAST_REGISTER.csv"

MANUAL_FEATURES = [
    "response_format", "self_other", "role_change", "gain_loss_framing",
    "numerical_manipulation", "explicit_probability", "question_order",
    "n_response_options",
]
SOURCE = "results/unblinding/_project_governance/stage9_explanatory_regression"

# Pure question-order manipulations: the same items appear in a different
# ORDER, so the position of the first differing token is meaningless and the
# spec requires NaN + na flag. (C-21/C-27 are insertions of a preceding
# question, not pure reorders, so their location is kept and documented.)
PURE_REORDER = {"C-36"}

# Manual-review outcomes that the token-set diff could not see (shared option
# labels masked the change); value is negation_change=1 with this evidence.
NEGATION_MANUAL = {
    "C-15": "'did not succeed' (control) vs 'succeeded' (treatment); script set-diff masked by 'not' in shared option labels",
    "C-26": "'You have not done the reading ... would not be able' removed; 'prefer not to volunteer' added",
    "C-37": "'I will always go back' vs 'I will never go back'",
    "C-38": "'I will always go back' vs 'I will never go back'",
}


def load_json_passes():
    pass1 = json.loads((HERE / "coding_pass1.json").read_text())
    pass2 = json.loads((HERE / "coding_pass2.json").read_text())
    pass1.pop("_meta", None)
    pass2.pop("_meta", None)
    return pass1, pass2


def load_text_features():
    rows = {}
    with open(OUT_DIR / "text_features.csv") as fh:
        for row in csv.DictReader(fh):
            rows[row["contrast_id"]] = row
    return rows


def load_stage5_contrast_ids():
    ids = set()
    with open(STAGE5) as fh:
        for row in csv.DictReader(fh):
            ids.add(row["contrast_id"])
    return ids


def load_register():
    meta = {}
    with open(REGISTER) as fh:
        for row in csv.DictReader(fh):
            meta[row["contrast_id"]] = row
    return meta


def reconcile(pass1, pass2, text_features):
    """Compare the two passes; return (disagreement list, per-feature agreement)."""
    disagreements = []
    agreement = {}
    for feature in MANUAL_FEATURES:
        n_match = 0
        for cid in sorted(pass1):
            v1, v2 = pass1[cid][feature], pass2[cid][feature]
            if v1 == v2:
                n_match += 1
            else:
                disagreements.append((cid, feature, v1, v2))
        agreement[feature] = (n_match, len(pass1))
    return disagreements, agreement


def na_flag(row):
    return 1 if row["manipulation_location"] == "" else 0


def na_reason(row):
    return "pure question-order manipulation: token position of first difference is meaningless" if row["manipulation_location"] == "" else ""


def build_rows(pass1, text_features, register, arms):
    rows = []
    for cid in sorted(pass1):
        tf = text_features[cid]
        arm = arms[cid]
        reg = register[cid]
        p1 = pass1[cid]
        row = {
            "contrast_id": cid,
            "experiment_id": reg["experiment_id"],
            "study_group": reg["study_group"],
            "response_format": p1["response_format"],
            "self_other": p1["self_other"],
            "role_change": p1["role_change"],
            "gain_loss_framing": p1["gain_loss_framing"],
            "numerical_manipulation": p1["numerical_manipulation"],
            "explicit_probability": p1["explicit_probability"],
            "negation_change": p1.get("negation_change", 0),
            "question_order": p1["question_order"],
            "response_options_change": p1.get("response_options_change", 0),
            "question_length": tf["question_length"],
            "wording_difference": tf["wording_difference"],
            "manipulation_location": (
                "" if cid in PURE_REORDER else tf["manipulation_location"]
            ),
            "manipulation_location_na": (
                1 if cid in PURE_REORDER else na_flag(tf)
            ),
            "manipulation_location_na_reason": (
                "pure question-order manipulation: token position of first "
                "difference is meaningless"
                if cid in PURE_REORDER else na_reason(tf)
            ),
            "n_response_options": "" if p1["n_response_options"] is None else p1["n_response_options"],
            "n_response_options_na_reason": (
                "outcome elicitation is a free numeric entry, no fixed option set"
                if p1["n_response_options"] is None else ""
            ),
            "arm_control_label": arm["control_label"],
            "arm_treatment_label": arm["treatment_label"],
            "stimulus_source": arm.get("source", SOURCE),
            "negation_evidence": NEGATION_MANUAL.get(cid, tf["negation_tokens_changed"] or "(negation sets identical)"),
            "diff_evidence": tf["first_diff_excerpt"],
            "coding_method_manual": "two_pass_analyst_reconciled",
            "coding_method_text": "script (compute_text_features.py)",
            "coding_note": p1.get("note", ""),
        }
        rows.append(row)
    return rows


def main():
    pass1, pass2 = load_json_passes()
    text_features = load_text_features()
    stage5_ids = load_stage5_contrast_ids()
    register = load_register()
    arms = {**CONTRAST_ARMS_ORIGINAL, **CONTRAST_ARMS_EXPANSION}

    coded_ids = set(pass1)
    missing_in_coding = sorted(stage5_ids - coded_ids)
    extra_in_coding = sorted(coded_ids - stage5_ids)
    set_equal = stage5_ids == coded_ids

    disagreements, agreement = reconcile(pass1, pass2, text_features)

    rows = build_rows(pass1, text_features, register, arms)
    fields = list(rows[0].keys())
    with open(OUT_DIR / "EXPERIMENT_FEATURES.csv", "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Two-pass coding reconciliation",
        "",
        "Both passes were made by the same analyst-agent (not independent human",
        "raters): pass 2 re-read the stimuli and re-derived every manual feature",
        "without consulting pass 1. Text features (question_length,",
        "wording_difference, manipulation_location) are script-computed and were",
        "not hand-coded.",
        "",
        f"Contrast-id set equality with stage5_dataset.csv: **{set_equal}** "
        f"(stage5 n={len(stage5_ids)}, coded n={len(coded_ids)})",
    ]
    if missing_in_coding:
        lines.append(f"Missing from coding: {missing_in_coding}")
    if extra_in_coding:
        lines.append(f"Extra in coding: {extra_in_coding}")
    lines += ["", "## Per-feature agreement (of 38 contrasts)", ""]
    for feature, (n_match, n_total) in agreement.items():
        pct = 100.0 * n_match / n_total
        lines.append(f"- {feature}: {n_match}/{n_total} ({pct:.0f}%)")
    lines += ["", f"## Disagreements ({len(disagreements)})", ""]
    if disagreements:
        for cid, feature, v1, v2 in disagreements:
            lines.append(f"- {cid} {feature}: pass1={v1}, pass2={v2}")
    else:
        lines.append("None. The two passes converged on identical values for all "
                     "manual features; this reflects within-agent consistency and "
                     "should not be read as inter-rater reliability.")
    (OUT_DIR / "CODING_RECONCILIATION.md").write_text("\n".join(lines) + "\n")
    print(f"set_equal={set_equal}; disagreements={len(disagreements)}; wrote EXPERIMENT_FEATURES.csv ({len(rows)} rows)")


if __name__ == "__main__":
    main()
