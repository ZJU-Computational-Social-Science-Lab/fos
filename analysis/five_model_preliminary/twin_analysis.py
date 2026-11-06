# Twin-experiment outcomes for the five-model preliminary comparison.
#
# What this file does: for each of the five in-scope models and each of the
# 14 twin experiments, it reads the archived inference records from the
# ORIGINAL runs (run10 + run6, synthetic personas) and the REDESIGNED run
# (real-respondent personas) and computes, per contrast and blinding
# condition, the signed model effect (in percentage points and in human-SD
# units) and whether its sign agrees with the human effect. It also
# computes the total-variation distance between the human response
# distribution and the model's mean predicted distribution per arm,
# following the historically validated procedure: first-token
# probabilities are averaged as PROBABILITY MASS over the answer
# categories — they are never treated as independent samples. Outputs are
# two tidy CSVs. Both run directories are read-only.
#
# What each function does:
#   load_frozen_audit   — imports the frozen run10 audit module, which owns
#                         the validated per-experiment outcome rules.
#   outcome_value       — the one raw-scale number one record contributes
#                         (frozen rules, with the two documented new-run
#                         adaptations for disease and sunk_cost).
#   mass_vector         — the record's categorical probability mass on the
#                         outcome support (for TVD).
#   collect_cell        — reads one records.jsonl into per-persona outcome
#                         values per arm plus per-record mass vectors,
#                         deduplicating under the full observation identity
#                         (arm, persona, qid, item index) and counting any
#                         collisions.
#   arm_means           — flat mean over retained records (frozen estimator).
#   contrast_delta      — signed treatment-minus-control effect in pp.
#   human_label_pmf     — human PMF over numeric codes from the labeled
#                         human CSV, gated on reproducing the card mean.
#   human_pmf           — human per-arm PMF on the model's outcome support.
#   model_pmf           — mean predicted distribution from mass vectors.
#   tvd                 — half the summed absolute difference of two
#                         distributions over the same support.
#   validate_against_frozen — gate: recomputed original-run effects must
#                         match the frozen signed-contrasts table.
#   main                — loops models, runs, experiments; writes the CSVs.

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path
from statistics import fmean

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (BLINDINGS, CANONICAL, CODEBOOK, FROZEN_SIGNED, LABEL_CSV,
                    LIKERT5, MODELS, OLD_RUN10, OLD_RUN6, OUT, PROB6, REGISTRY,
                    SUPPORT, TVD_PLAN, UNBL)

AUDIT = UNBL / "T2K10-20260923T034851/final_audit/"
AUDIT = AUDIT / "blinding_effect_magnitude_analysis.py"

_audit = None


def load_frozen_audit():
    """Import the frozen audit module (validated outcome rules)."""
    global _audit
    if _audit is None:
        spec = importlib.util.spec_from_file_location("fa", AUDIT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _audit = mod
    return _audit


def outcome_value(record: dict, exp: str, era: str):
    """The one raw-scale number a record contributes (frozen rules)."""
    fa = load_frozen_audit()
    if exp == "disease" and era == "redesigned":
        pn = record.get("p_norm") or {}
        total = sum(pn.get(letter) or 0 for letter in "ABC")
        return float(total) if total > 0 else None
    if exp == "sunk_cost" and era == "redesigned":
        # redesigned records carry the 21-option mass as one digit item
        item = next(iter(record.get("digit_items") or []), None)
        pn = (item or {}).get("p_norm") or {}
        in_scale = {int(d): m for d, m in pn.items()
                    if d.isdigit() and int(d) <= 20 and m and m > 0}
        total = sum(in_scale.values())
        if total <= 0:
            return None
        return sum(code * m for code, m in in_scale.items()) / total
    return fa.record_outcome(record, exp)


def mass_vector(record: dict, exp: str, kind: str):
    """The record's categorical mass on the outcome support (for TVD)."""
    if kind == "p_safe":
        pn = record.get("p_norm") or {}
        s = sum(pn.get(l) or 0 for l in "ABC")
        return {1: s, 2: 1.0 - s} if s > 0 else None
    if kind == "digit6":
        item = next((i for i in (record.get("digit_items") or [])
                     if i.get("row") == 3), None)
        pn = (item or {}).get("p_norm") or {}
        return {int(d): pn[d] for d in "123456" if pn.get(d)} or None
    pn = record.get("p_norm") or {}
    letters = SUPPORT[kind]
    vec = {i + 1: pn.get(l) for i, l in enumerate(letters)}
    return {k: v for k, v in vec.items() if v is not None} or None


def collect_cell(path: Path, exp: str, era: str, kind: str | None):
    """Per-persona outcome values and mass vectors per arm, one leg.

    Deduplication: the full observation identity is (arm, persona,
    qid, item index); a repeated identity keeps its first record and is
    counted as a collision (reported, never silently merged).
    """
    per_arm: dict[str, dict[int, list[float]]] = {}
    masses: dict[str, list[dict]] = {}
    account = {"n": 0, "failed": 0, "no_outcome": 0, "duplicates": 0}
    seen: set[tuple] = set()
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            account["n"] += 1
            identity = (rec.get("arm"), rec.get("persona_id"),
                        rec.get("qid"), rec.get("item_index", 0))
            if identity in seen:
                account["duplicates"] += 1
                continue
            seen.add(identity)
            if not rec.get("succeeded", False):
                account["failed"] += 1
                continue
            val = outcome_value(rec, exp, era)
            if val is None:
                account["no_outcome"] += 1
                continue
            arm = rec["arm"]
            pid = int(rec.get("persona_id", -1))
            per_arm.setdefault(arm, {}).setdefault(pid, []).append(val)
            if kind:
                mv = mass_vector(rec, exp, kind)
                if mv:
                    masses.setdefault(arm, []).append(mv)
    return per_arm, masses, account


def arm_means(per_arm: dict) -> dict[str, float]:
    """Flat mean over retained records per arm (frozen estimator)."""
    return {a: fmean([v for vs in p.values() for v in vs])
            for a, p in per_arm.items()}


def contrast_delta(spec: dict, arms: dict[str, float], cb: dict):
    """Signed treatment-minus-control effect in pp for one contrast."""
    wave = spec["human"]["wave1_3"]
    anchor = "anchor_mc" in list(wave["arms"].values())[0]
    trt, cmp = cb["treatment_arm"], cb["comparison_arm"]
    if trt not in arms or cmp not in arms:
        return None
    t, c = arms[trt], arms[cmp]
    if not anchor:
        nz = spec["normalization_0_1"]
        t = (t - nz["min"]) / (nz["max"] - nz["min"])
        c = (c - nz["min"]) / (nz["max"] - nz["min"])
    return (t - c) * 100.0


def human_label_pmf(frame: pd.DataFrame, columns: list[str],
                    label_to_code: dict, expected_mean):
    """Human PMF over numeric codes from labeled CSV columns (gated)."""
    counts: dict[int, int] = {}
    total = 0
    for col in columns:
        if col not in frame.columns:
            return None
        for text in frame[col].dropna():
            code = label_to_code.get(str(text).strip())
            if code is None:
                continue
            counts[code] = counts.get(code, 0) + 1
            total += 1
    if total == 0 or expected_mean is None:
        return None
    pmf = {c: n / total for c, n in counts.items()}
    mean = sum(c * p for c, p in pmf.items())
    if abs(mean - expected_mean) > 0.08:  # coding-validation gate
        return None
    return pmf


def human_pmf(spec: dict, card: dict, kind: str, frame: pd.DataFrame):
    """Human per-arm PMF on the model's outcome support."""
    if kind == "dist":
        return {int(k): float(v["pct"]) / 100.0
                for k, v in card["dist"].items()}
    if kind == "anchor":
        p = float(card["anchor_mc"]["1"]) / 100.0
        return {1: p, 2: 1.0 - p}
    if kind == "p_safe":
        p = float(card["p_safe"]) / 100.0
        return {1: p, 2: 1.0 - p}
    qid = card.get("qid", "")
    if kind == "label_prob6":
        mapping = {label: i + 1 for i, label in enumerate(PROB6)}
        key = f"{qid}_3"
        mean = card["per_statement"].get(key, {}).get("mean")
        return human_label_pmf(frame, [key], mapping, mean)
    if kind == "label_likert5":
        mapping = {label: i + 1 for i, label in enumerate(LIKERT5)}
        return human_label_pmf(frame, [qid], mapping, card.get("mean"))
    if kind == "label_seat6":
        from config import SEAT6
        mapping = {label: i + 1 for i, label in enumerate(SEAT6)}
        return human_label_pmf(frame, [qid], mapping, card.get("mean"))
    return None


def model_pmf(masses: list[dict]) -> dict | None:
    """Mean predicted distribution over the support from mass vectors."""
    if not masses:
        return None
    keys = sorted({k for m in masses for k in m})
    total = sum(sum(m.values()) for m in masses)
    if total <= 0:
        return None
    return {k: sum(m.get(k, 0.0) for m in masses) / total for k in keys}


def tvd(p: dict, q: dict) -> float:
    """Half the summed absolute difference of two distributions."""
    keys = set(p) | set(q)
    return 0.5 * sum(abs(p.get(k, 0.0) - q.get(k, 0.0)) for k in keys)


def contrast_id_map() -> dict:
    """(experiment, contrast name) -> contrast id, from the register."""
    from config import UNBL
    reg = UNBL / "_project_governance/stage3_methodology/CONTRAST_REGISTER.csv"
    out = {}
    with open(reg, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out[(row["experiment_id"], row["contrast_name"])] = row["contrast_id"]
    return out


def human_sd_map() -> dict:
    """contrast_id -> (human effect in SD units, human pooled SD in pp)."""
    frame = pd.read_csv(CANONICAL)
    frame = frame.drop_duplicates(subset=["contrast_id"])
    return {r.contrast_id: (r.human_effect_std, r.sd_human_pooled_pp)
            for r in frame.itertuples()}


def validate_against_frozen(rows: list[dict]) -> list[str]:
    """Re-scoring gate: recomputed original-run effects must match the
    frozen signed-contrasts table for every in-scope model."""
    frozen = pd.read_csv(FROZEN_SIGNED)
    lookup = {}
    for r in frozen.itertuples():
        lookup[(r.model, r.experiment, r.contrast, "blinded")] = r.d_m_B
        lookup[(r.model, r.experiment, r.contrast, "unblinded")] = r.d_m_U
    problems = []
    for r in rows:
        if r["era"] != "original" or "contrast" not in r:
            continue
        key = (r["model"], r["experiment"], r["contrast"], r["blinding"])
        if key not in lookup:
            continue
        ref = lookup[key]
        if abs(ref - r["delta_pp"]) > 0.05:
            problems.append(f"{key}: recomputed {r['delta_pp']:.4f} "
                            f"vs frozen {ref:.4f}")
    return problems


def run_root_for(spec: dict, era: str) -> Path:
    """The archived root holding this experiment's legs for this era."""
    if era == "redesigned":
        from config import NEW_RUN
        return NEW_RUN
    return OLD_RUN10 if spec["run"] == "run10" else OLD_RUN6


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    reg = json.load(open(REGISTRY))["experiments"]
    codebook = list(csv.DictReader(open(CODEBOOK)))
    frame = pd.read_csv(LABEL_CSV, dtype=str, low_memory=False)
    cid = contrast_id_map()
    sd = human_sd_map()
    rows: list[dict] = []
    tvd_rows: list[dict] = []
    for model in MODELS:
        for era in ("original", "redesigned"):
            for exp, spec in reg.items():
                if exp in ("base_rate", "false_consensus"):
                    continue  # frozen exclusions; absent from the new run
                plan = TVD_PLAN.get(exp)
                kind = plan[0] if plan else None
                root = run_root_for(spec, era)
                for blind in BLINDINGS:
                    path = root / model / f"{exp}_{blind}" / "records.jsonl"
                    if not path.is_file():
                        continue
                    per_arm, masses, account = collect_cell(path, exp,
                                                            era, kind)
                    arms = arm_means(per_arm)
                    wave = spec["human"]["wave1_3"]
                    if set(arms) != set(wave["arms"]):
                        rows.append({"model": model, "era": era,
                                     "experiment": exp, "blinding": blind,
                                     "note": "arm coverage mismatch",
                                     "n_records": account["n"]})
                        continue
                    for cb in codebook:
                        if cb["experiment"] != exp:
                            continue
                        delta = contrast_delta(spec, arms, cb)
                        if delta is None:
                            continue
                        key = cid.get((exp, cb["contrast"]))
                        h_std, sd_pp = sd.get(key, (float("nan"),
                                                    float("nan")))
                        rows.append({
                            "model": model, "era": era, "experiment": exp,
                            "contrast": cb["contrast"], "contrast_id": key,
                            "blinding": blind, "delta_pp": delta,
                            "delta_std": (delta / sd_pp if sd_pp
                                          else float("nan")),
                            "human_std": h_std,
                            "n_records": account["n"],
                            "n_failed": account["failed"],
                            "n_no_outcome": account["no_outcome"],
                            "n_duplicates": account["duplicates"],
                        })
                    if plan:
                        hkind = plan[1]
                        for arm, card in wave["arms"].items():
                            hp = human_pmf(spec, card, hkind, frame)
                            mp = model_pmf(masses.get(arm, []))
                            ok = hp is not None and mp is not None
                            tvd_rows.append({
                                "model": model, "era": era,
                                "experiment": exp, "blinding": blind,
                                "arm": arm,
                                "tvd": tvd(hp, mp) if ok else float("nan"),
                                "human_pmf_computed": hp is not None,
                                "n_model_records": len(masses.get(arm, [])),
                            })
    problems = validate_against_frozen(rows)
    if problems:
        raise SystemExit("VALIDATION FAILED:\n" + "\n".join(problems[:20]))
    effects = pd.DataFrame(rows)
    tvd_frame = pd.DataFrame(tvd_rows)
    effects.to_csv(OUT / "five_model_twin_effects.csv", index=False)
    tvd_frame.to_csv(OUT / "five_model_twin_tvd.csv", index=False)
    dup_total = int(effects.get("n_duplicates", pd.Series([0])).sum())
    print(f"wrote {len(effects)} effect rows, {len(tvd_frame)} TVD rows, "
          f"{dup_total} duplicate identities (kept-first)")


if __name__ == "__main__":
    main()
