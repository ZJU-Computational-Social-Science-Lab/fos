# fig02_tess.py — human and LLM response distributions for the 4 TESS
# experiments (howard823, budescu779, keusch433, reedBR32).
#
# What this file does: human side straight from the archived TESS .sav
# studies, re-binned/coded exactly as the LLM pipeline registered the
# coding (bucket midpoints for howard823 and budescu779, shared 1-5
# frequency scale for keusch433, raw 1-7 ratings for reedBR32); LLM side
# streamed from the complete production records like every other
# expansion experiment.
#
# Functions:
#   load_tess       -> {exp_id: ExpansionExp} for the four TESS studies
#   _howard_human   -> per-arm re-binned $ bucket values from the .sav
#   _budescu_human  -> per-arm 10-point bucket values (very-likely and
#                      very-unlikely item subsets)
#   _keusch_human   -> per-arm 1-5 mean frequency (pooled vague labels)
#   _reed_human     -> per-arm 1-7 helpfulness / trustworthiness

import sys

import numpy as np
import pyreadstat
import pandas as pd

UNBL = "/home/justin/Documents/ZJU work/fos/results/unblinding"
sys.path.insert(0, f"{UNBL}/expansion")
TESS = f"{UNBL}/expansion/raw/tess"

from pipeline import registry as pr  # noqa: E402

from fig02_common import ArmData  # noqa: E402
from fig02_expansion import ExpansionExp, _models, _load_llm  # noqa: E402

CONDITIONS = ("blinded", "unblinded")


def _clip_check(vals: np.ndarray, lo: float, hi: float, where: str) -> np.ndarray:
    """Drop NaNs, verify the registered coding, clip into the space."""
    vals = vals[np.isfinite(vals)]
    outside = int(np.sum((vals < lo - 1e-9) | (vals > hi + 1e-9)))
    if outside:
        raise ValueError(f"{where}: {outside} human values outside the "
                         f"registered space [{lo}, {hi}]")
    return np.clip(vals, lo, hi)


def _howard_human() -> dict:
    """control/atypical/typical raw $ answers re-binned onto the
    registered $100 bucket midpoints (the benchmarks.py convention)."""
    sys.path.insert(0, f"{UNBL}/expansion/pipeline")
    from pipeline import benchmarks as bm
    answers = bm._read_condition_answers()
    return {name: np.array([bm.rebin_dollars_to_bucket_value(v)
                            for v in rows], dtype=float)
            for name, rows in answers.items()}


def _budescu_arms() -> dict:
    """Human bucket values per (condition, item subset).

    Control = xtess021 in {1,2} answering the IPCC_1a_* items;
    verbal-numerical = {5,6} answering IPCC_1c_*; raw 0-100 estimates
    re-binned to the nearest registered 10-point bucket value. Item
    subsets per the registered contrasts: very likely = sentences 1-2,
    very unlikely = sentences 7-8.
    """
    df, _ = pyreadstat.read_sav(f"{TESS}/budescu779/"
                                "TESS 021_Budescu_final_data.sav")

    def subset(codes, prefix, sentences):
        rows = df[df.xtess021.isin(codes)]
        cols = [f"{prefix}_{s}" for s in sentences]
        block = rows[cols].apply(pd.to_numeric, errors="coerce")
        block = block.where(block >= 0)  # -1 refused -> missing
        # per-respondent mean over the subset's sentences (registered
        # aggregation before any contrast), then re-binned to buckets
        per_resp = block.mean(axis=1).dropna().to_numpy(float)
        return np.clip(np.round(per_resp / 10.0) * 10.0, 0.0, 100.0)

    return {
        ("control", "very_likely"): subset((1, 2), "IPCC_1a", (1, 2)),
        ("verbal_numerical", "very_likely"): subset((5, 6), "IPCC_1c",
                                                    (1, 2)),
        ("control", "very_unlikely"): subset((1, 2), "IPCC_1a", (7, 8)),
        ("verbal_numerical", "very_unlikely"): subset((5, 6), "IPCC_1c",
                                                      (7, 8)),
    }


def _keusch_human() -> dict:
    """Pooled vague-label K6 mean frequency (1-5) per direction.

    Direction = DOV_DIRECT (1 = high->low, 2 = low->high; coding
    assumption documented in FIGURE_GUIDE.md), labels = DOV_LABEL 1
    (vague), both alignment columns (Q1?_1 + Q1?_4) pooled because the
    screen-alignment factor is excluded from the pipeline design. -1 =
    missing; a respondent enters with the mean over their answered items.
    """
    df, _ = pyreadstat.read_sav(f"{TESS}/keusch433/keusch433_unz/"
                                "TESS3_150_Keusch_Final_Client.sav")
    items = ["Q1A", "Q1B", "Q1C", "Q1D", "Q1E", "Q1F"]
    vague = df[df.DOV_LABEL == 1]
    out = {}
    for direct, name in ((1.0, "high_to_low_vague"),
                         (2.0, "low_to_high_vague")):
        rows = vague[vague.DOV_DIRECT == direct]
        block = rows[[f"{q}_1" for q in items] +
                     [f"{q}_4" for q in items]].apply(pd.to_numeric,
                                                      errors="coerce")
        block = block.where(block >= 0)  # -1 refused -> missing
        out[name] = block.mean(axis=1).dropna().to_numpy(float)
    return out


def _reed_human() -> dict:
    """Per-valence 1-7 ratings (stakes pooled): valence codes 1/2 =
    positive, 3/4 = negative (verified against the registered benchmark
    means: negative helpfulness > positive, trustworthiness < positive).
    -1 = refused -> missing."""
    df, _ = pyreadstat.read_sav(f"{TESS}/reedBR32/TESS_166_Reed_Client.sav")
    out = {}
    for valence, codes in (("positive", (1.0, 2.0)),
                           ("negative", (3.0, 4.0))):
        rows = df[df.xTess166.isin(codes)]
        for col, name in (("QR1", "helpfulness"), ("QR2", "trustworthiness")):
            vals = pd.to_numeric(rows[col], errors="coerce").to_numpy(float)
            out[(f"{valence}_pooled", name)] = vals[vals >= 0]
    return out


def _finish(exp_id, group, contrasts, otype, arm_llm, arm_human,
            space) -> ExpansionExp:
    exp = ExpansionExp(exp_id=exp_id, contrasts=list(contrasts),
                       models=_models(), outcome_type=otype, group=group)
    lo, hi = space
    for arm_name, human in arm_human.items():
        exp.arms[arm_name] = ArmData(
            human_values=_clip_check(np.asarray(human, float), lo, hi,
                                     f"{exp_id}/{arm_name}"),
            llm_values={k: np.clip(np.array(list(v["means"].values())), lo, hi)
                        for k, v in arm_llm.items()},
            space=space)
    return exp


def load_tess() -> dict:
    """The four TESS experiments, human + LLM sides."""
    out = {}
    # howard823: $100 bucket midpoints 0..1100
    human = _howard_human()
    llm = _load_llm("T2KX-howard823", _models())
    out["T2KX-howard823"] = _finish(
        "T2KX-howard823", "TESS",
        [("atypical_minus_control", "control", "atypical"),
         ("typical_minus_control", "control", "typical")],
        "numerical ($100 bucket midpoints 0-1100)", llm,
        {k: v for k, v in human.items()}, (0.0, 1100.0))
    # budescu779: two registered item-subset contrasts; arm = condition
    # x item subset (keys carry the subset so no arm is shared)
    space_b = (0.0, 100.0)
    for subset, item_idx in (("very_likely", (0, 1)),
                             ("very_unlikely", (6, 7))):
        human_b = {f"{cond}#{subset}": vals for (cond, s), vals in
                   _budescu_arms().items() if s == subset}
        exp_id = f"T2KX-budescu779#{subset}"
        llm_b = _load_llm("T2KX-budescu779", _models(),
                          item_filter=lambda idx, s=set(item_idx):
                          idx in s)
        out[exp_id] = _finish(
            exp_id, "TESS",
            [(f"vn_minus_{subset}", f"control#{subset}",
              f"verbal_numerical#{subset}")],
            "numerical (10-point probability buckets 0-100)", llm_b,
            human_b, space_b)
    # keusch433: K6 mean frequency 1-5, pooled vague labels
    llm_k = _load_llm("T2KX-keusch433", _models())
    out["T2KX-keusch433"] = _finish(
        "T2KX-keusch433", "TESS",
        [("low_to_high_minus_high_to_low", "high_to_low_vague",
          "low_to_high_vague")],
        "ordinal (1-5 K6 mean frequency, pooled vague labels)", llm_k,
        _keusch_human(), (1.0, 5.0))
    # reedBR32: two outcome contrasts, stakes pooled within valence
    human_r = _reed_human()
    for outcome in ("helpfulness", "trustworthiness"):
        arm_h = {f"{v}_pooled": human_r[(f"{v}_pooled", outcome)]
                 for v in ("negative", "positive")}
        exp_id = f"T2KX-reedBR32#{outcome}"
        llm_r = _load_llm(
            "T2KX-reedBR32", _models(),
            item_filter=(lambda idx: idx == 0) if outcome == "helpfulness"
            else (lambda idx: idx == 1))
        out[exp_id] = _finish(
            exp_id, "TESS",
            [(f"negative_minus_positive_{outcome}", "positive_pooled",
              "negative_pooled")],
            f"ordinal (1-7 {outcome}, stakes pooled)", llm_r, arm_h,
            (1.0, 7.0))
    return out


if __name__ == "__main__":
    for name, exp in load_tess().items():
        print(exp.group, name, {a: len(d.human_values)
                                for a, d in exp.arms.items()})
