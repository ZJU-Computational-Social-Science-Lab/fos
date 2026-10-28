# What this file does: computes the Part-5 per-model error patterns (all 15
# models, co-error overlap on the blinded leg) and the Part-6 disclosure
# analysis (transitions on the 4 both-legs-wrong and 7 disagreement contrasts,
# paired magnitude change of wrong-direction predictions).
# Functions:
#   load() - confident contrasts + per-model blinded/disclosed effects
#   part5() - per-model wrong counts, disclosure transitions, Jaccard overlap
#   part6() - disclosure transitions and magnitude changes on target sets
# Everything is written to CSV next to this script for the MD reports.

import itertools
import sys
import pathlib

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
STAGE10 = pathlib.Path(
    "/home/justin/Documents/ZJU work/fos/results/unblinding/_project_governance"
) / "stage10_data_reconciliation"
OUT = pathlib.Path(__file__).parent
SEVEN = ["C-03", "C-09", "C-16", "C-26", "C-30", "C-31", "C-37"]


def load():
    contrasts = pd.read_csv(ROOT / "ALL_CONTRAST_PATTERNS.csv")
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import corrected_pairs
    ds = corrected_pairs.load_all_legs()
    conf = contrasts[contrasts.human_direction_confident]
    df = ds.merge(
        conf[["contrast_id", "human_direction"]], on="contrast_id", how="inner"
    )
    df["wrong"] = (np.sign(df.y_std) != df.human_direction).astype(int)
    return contrasts, df


def part5(contrasts, df):
    rows = []
    wide = {}
    for m, g in df.groupby("model"):
        b = g[g.blinding == 0].set_index("contrast_id")
        d = g[g.blinding == 1].set_index("contrast_id")
        wrong_b = set(b.index[b.wrong == 1])
        wrong_d = set(d.index[d.wrong == 1])
        wide[m] = wrong_b
        rows.append(
            {
                "model": m,
                "n_contrasts_confident": len(b),
                "n_wrong_blinded": len(wrong_b),
                "share_wrong_blinded": round(len(wrong_b) / len(b), 4),
                "n_wrong_disclosed": len(wrong_d),
                "share_wrong_disclosed": round(len(wrong_d) / len(d), 4),
                "wrong_both_legs": len(wrong_b & wrong_d),
                "wrong_blinded_only": len(wrong_b - wrong_d),
                "wrong_disclosed_only": len(wrong_d - wrong_b),
                "n_new_wrong_under_disclosure": len(wrong_d - wrong_b),
                "n_corrected_under_disclosure": len(wrong_b - wrong_d),
                "wrong_contrasts_blinded": ";".join(sorted(wrong_b)),
            }
        )
    per_model = pd.DataFrame(rows).sort_values("n_wrong_blinded", ascending=False)

    overlap = []
    for m1, m2 in itertools.combinations(sorted(wide), 2):
        inter = len(wide[m1] & wide[m2])
        union = len(wide[m1] | wide[m2])
        overlap.append(
            {
                "model_1": m1,
                "model_2": m2,
                "n_co_wrong_blinded": inter,
                "jaccard_blinded": round(inter / union, 4) if union else 0.0,
            }
        )
    ov = pd.DataFrame(overlap).sort_values("jaccard_blinded", ascending=False)
    per_model.to_csv(OUT / "MODEL_ERROR_PATTERNS_FULL.csv", index=False)
    ov.to_csv(OUT / "CO_ERROR_OVERLAP.csv", index=False)
    return per_model, ov


def part6(contrasts, df):
    cls = contrasts.set_index("contrast_id").collective_disagreement_class
    both_wrong = list(cls[cls == "majority_wrong_both"].index)
    for tag, ids in [("both_legs_wrong", both_wrong), ("disagreement7", SEVEN)]:
        sub = df[df.contrast_id.isin(ids)]
        rows = []
        for m, g in sub.groupby("model"):
            b = g[g.blinding == 0].set_index("contrast_id")
            d = g[g.blinding == 1].set_index("contrast_id")
            wb = set(b.index[b.wrong == 1])
            wd = set(d.index[d.wrong == 1])
            rows.append(
                {
                    "model": m,
                    "wrong_blinded": len(wb),
                    "wrong_disclosed": len(wd),
                    "corrected": ";".join(sorted(wb - wd)),
                    "newly_wrong": ";".join(sorted(wd - wb)),
                    "wrong_both_legs": ";".join(sorted(wb & wd)),
                }
            )
        pd.DataFrame(rows).sort_values("model").to_csv(
            OUT / f"disclosure_transitions_{tag}.csv", index=False
        )
        print(f"--- {tag}: contrasts {ids} ---")
        print(pd.DataFrame(rows).sort_values("model").to_string(index=False))

    cols = [
        "contrast_id",
        "collective_disagreement_class",
        "human_abs_d_std",
        "mean_abs_wrong_blinded",
        "mean_abs_wrong_vs_human_d_blinded",
        "mean_abs_wrong_disclosed",
        "mean_abs_wrong_vs_human_d_disclosed",
    ]
    mag = contrasts[contrasts.contrast_id.isin(set(both_wrong) | set(SEVEN))][cols]
    mag.to_csv(OUT / "disclosure_magnitude_change.csv", index=False)
    print(mag.to_string(index=False))


def main():
    contrasts, df = load()
    per_model, ov = part5(contrasts, df)
    print(per_model.to_string(index=False))
    print("--- top co-error overlaps ---")
    print(ov.head(12).to_string(index=False))
    print("--- family-block check (mean jaccard within vs across families) ---")
    FAM = {
        "gemma": ["gemma-4-12b-it-qat", "gemma-4-26b-a4b", "gemma-4-31b-it-qat"],
        "glm": ["glm-4.7-flash"],
        "gpt-oss": ["gpt-oss-20b"],
        "granite": ["granite-4.1-30b", "granite-4.1-8b"],
        "muse": ["muse-glimmer"],
        "nemotron": ["nemotron-cascade-2-30b-a3b"],
        "qwen": ["qwen3-32b", "qwen3-4b", "qwen3.6-27b-dense",
                 "qwen3.6-35b-a3b", "qwen3.6-35b-a3b-uncensored", "qwen3.8-27b"],
    }

    def fam(m):
        return next(f for f, ms in FAM.items() if m in ms)

    ov["same_family"] = ov.apply(lambda r: fam(r.model_1) == fam(r.model_2), axis=1)
    print(ov.groupby("same_family").jaccard_blinded.agg(["mean", "count"]))
    ov.to_csv(OUT / "CO_ERROR_OVERLAP.csv", index=False)
    part6(contrasts, df)


if __name__ == "__main__":
    main()
