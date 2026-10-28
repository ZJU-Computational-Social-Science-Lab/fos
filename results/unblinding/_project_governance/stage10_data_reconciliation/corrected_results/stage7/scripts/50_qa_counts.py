# What this script does: re-derives the headline counts quoted in the Stage 7
# Phase-3 deliverables directly from the Phase-1/2 CSV files, so every number
# in EXECUTIVE_SUMMARY.md and REPLICATION_PATTERN.md can be checked in one run.
# It reads only, writes nothing, and is fully deterministic (fixed seed set for
# convention; no randomness is actually used).
import csv
import random
from pathlib import Path

random.seed(20261027)  # convention only; no random draws below

DIR = Path(__file__).resolve().parent.parent


def rows(name):
    with open(DIR / name, newline="") as f:
        return list(csv.DictReader(f))


def main():
    audit = rows("DISAGREEMENT_AUDIT.csv")
    screening = rows("SCREENING.csv")

    n = len(audit)
    confident = [r for r in audit if r["human_direction_confident"] == "True"]
    uncertain = [r for r in audit if r["human_direction_confident"] != "True"]
    classes = {}
    for r in audit:
        classes[r["collective_disagreement_class"]] = (
            classes.get(r["collective_disagreement_class"], 0) + 1
        )
    sel = {}
    for r in screening:
        sel[r["candidate_class"]] = sel.get(r["candidate_class"], 0) + 1
    bad_coding = [r["contrast_id"] for r in audit if r["coding_verified"] != "True"]

    print(f"contrasts total: {n}")
    print(f"confident human direction: {len(confident)}")
    print(f"direction-uncertain: {len(uncertain)} -> {[r['contrast_id'] for r in uncertain]}")
    print(f"collective_disagreement_class counts: {classes}")
    print(f"SCREENING class counts: {sel}")
    print(f"coding_verified=False contrasts: {bad_coding or 'none'}")

    print("\ndisagreement candidates (contrast, class, agree_blinded, agree_disclosed, |d_h|):")
    for r in audit:
        if r["collective_disagreement_class"].startswith("majority_wrong"):
            print(
                f"  {r['contrast_id']} {r['collective_disagreement_class']} "
                f"{float(r['agree_share_blinded']):.2f}/{float(r['agree_share_disclosed']):.2f} "
                f"|d_h|={float(r['human_abs_d_std']):.2f}"
            )

    print("\nagreement comparisons (contrast, worst-leg agree share, |d_h|):")
    for r in screening:
        if r["candidate_class"] == "AGREEMENT_COMPARISON":
            a = next(x for x in audit if x["contrast_id"] == r["contrast_id"])
            worst = min(float(a["agree_share_blinded"]), float(a["agree_share_disclosed"]))
            print(f"  {r['contrast_id']} worst_leg={worst:.2f} |d_h|={float(a['human_abs_d_std']):.2f}")

    # pooled direction agreement over confident contrasts (descriptive only;
    # models are correlated, so this is NOT an independent-replication rate)
    for leg in ("blinded", "disclosed"):
        ag = sum(int(r[f"n_agree_{leg}"]) for r in confident)
        tot = sum(int(r[f"n_agree_{leg}"]) + int(r[f"n_disagree_{leg}"]) for r in confident)
        print(f"\npooled direction agreement {leg}: {ag}/{tot} = {ag / tot:.3f}")


if __name__ == "__main__":
    main()
