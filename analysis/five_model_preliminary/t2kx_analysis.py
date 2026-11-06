# Expansion (T2KX) experiment outcomes for the five-model comparison.
#
# What this file does: for each of the five in-scope models and each of the
# 17 expansion experiments, it runs the FROZEN expansion pipeline analysis
# (imported read-only) over the archived T2KX run and over the redesigned
# run, giving per-contrast signed effects. Each effect is converted to
# human-SD units with the frozen human pooled SD and checked against the
# frozen historical table (the historical run's recomputed effects must
# match it — a hard gate). It also computes total-variation distance
# between the human response distribution and the model's mean predicted
# distribution for the single-item experiments whose cleaned human
# microdata sit on exactly the same answer support as the model's
# registered outcome coding; first-token probabilities enter as
# PROBABILITY MASS (averaged), never as independent samples. Experiments
# without a genuinely comparable human distribution (TESS raw microdata,
# multi-item scales, support mismatches) are excluded and listed.
#
# What each function does:
#   load_pipeline       — imports the frozen expansion pipeline package.
#   analyze             — one run dir + model -> per-contrast effect rows
#                         (native units), via the frozen analyze_run.
#   join_frozen         — attaches sd_human_pooled and contrast_id, and
#                         validates historical-run effects against the
#                         frozen contrast-level table.
#   outcome_values      — the model's registered coding: letter -> value.
#   support_from_coding — the distinct outcome values of one experiment.
#   human_condition_pmf — empirical human distribution over the outcome
#                         values for one condition, from cleaned microdata.
#   model_condition_pmf — mean probability mass over the same values from
#                         one leg's records (low-mass records excluded,
#                         per the frozen rule; identities deduplicated).
#   compute_t2kx_tvd    — TVD per condition for the support-matched
#                         experiments; writes the exclusions list.
#   main                — loops models and eras; writes the CSVs.

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (BLINDINGS, FROZEN_T2KX, HUMAN_CLEAN, MODELS, NEW_RUN,
                    OLD_T2KX, OUT, T2KX_HUMAN_FILES)

_pipe = None


def load_pipeline():
    """Import the frozen expansion pipeline package (read-only source).
    The pipeline's persona bootstrap is shrunk to a token number of draws:
    this analysis consumes only the frozen pipeline's point estimates (its
    intervals are already frozen in the contrast-level table), and the
    full 2,000-draw bootstrap would multiply runtime by the model count
    for no change in any number we report."""
    global _pipe
    if _pipe is None:
        unbl = OLD_T2KX.parents[2]
        sys.path.insert(0, str(unbl / "expansion"))
        from pipeline import analysis, registry
        analysis.BOOTSTRAP_DRAWS = 20
        _pipe = type("P", (), {"analysis": analysis, "registry": registry})
    return _pipe


def analyze(run_root: Path, model: str, era: str) -> list[dict]:
    """Frozen analyze_run over one run dir -> flat contrast rows."""
    pipe = load_pipeline()
    rows = []
    result = pipe.analysis.analyze_run(run_root, [model],
                                       pipe.registry.ready_experiments())
    for exp_id, by_blind in result["experiments"].items():
        for blinding, payload in by_blind.items():
            for c in payload["contrasts"]:
                rows.append({
                    "model": model, "era": era, "experiment": exp_id,
                    "contrast": c["contrast"], "blinding": blinding,
                    "delta_native": c["llm_mean_diff"],
                    "human_native": c["human_mean_diff"],
                    "human_ci_low": c["human_ci95_low"],
                    "human_ci_high": c["human_ci95_high"],
                })
    return rows


def join_frozen(rows: list[dict]) -> tuple[list[dict], list[str]]:
    """Attach sd_human_pooled + contrast_id from the frozen table and
    validate the historical-run effects against it (hard gate). The join
    key is (experiment, human benchmark), which is constant across models
    and eras — the same validated join the earlier before/after work used.
    The frozen table labels the disclosure condition "disclosed"; run
    folders call it "unblinded"."""
    frozen = pd.read_csv(FROZEN_T2KX)
    frozen = frozen[frozen.model.isin(MODELS)]
    sd = {tuple(k): v for k, v in frozen.groupby(
        ["experiment_id", "delta_human"]).sd_human_pooled.first().items()}
    cid = {tuple(k): v for k, v in frozen.groupby(
        ["experiment_id", "delta_human"]).contrast_id.first().items()}
    ref = {}
    for r in frozen.itertuples():
        ref[(r.model, r.experiment_id, r.contrast_id,
             "unblinded" if r.blinding == "disclosed" else r.blinding)] = (
            r.delta_model)
    out, problems = [], []
    for row in rows:
        key = (row["experiment"], row["human_native"])
        sd_pooled = sd.get(key)
        row["sd_human_pooled"] = sd_pooled
        row["contrast_id"] = cid.get(key)
        row["delta_std"] = (row["delta_native"] / sd_pooled
                            if sd_pooled is not None else float("nan"))
        row["human_std"] = (row["human_native"] / sd_pooled
                            if sd_pooled is not None else float("nan"))
        if row["era"] == "original" and row["contrast_id"] is not None:
            rkey = (row["model"], row["experiment"], row["contrast_id"],
                    row["blinding"])
            if rkey in ref:
                delta = ref[rkey]
                if abs(delta - row["delta_native"]) > 0.01:
                    problems.append(f"{rkey}: recomputed "
                                    f"{row['delta_native']:.4f} vs frozen "
                                    f"{delta:.4f}")
        out.append(row)
    return out, problems


def outcome_values(exp_id: str, condition: str, item: int) -> dict:
    """The frozen registered coding of one item: letter -> outcome value."""
    load_pipeline()
    from pipeline import outcomes
    coding = outcomes.outcome_for(exp_id, condition, item).coding
    return {cl.label: float(cl.value) for cl in coding}


def support_from_coding(coding: dict) -> set[float]:
    """The distinct outcome values behind one coding."""
    return set(coding.values())


def human_condition_pmf(path: Path, condition_wording: str,
                        support: set[float]):
    """Empirical human distribution over the outcome values, one condition.

    Returns None when the cleaned human answers do not sit exactly on the
    model's support — such experiments are excluded, never re-binned."""
    frame = pd.read_csv(path)
    sub = frame[frame.condition == condition_wording]
    if sub.empty or "dv" not in sub.columns:
        return None
    counts = Counter(float(v) for v in sub.dv.dropna())
    if set(counts) != support:
        return None
    total = sum(counts.values())
    return {v: counts[v] / total for v in sorted(counts)}


def model_condition_pmf(records: list[dict], exp_id: str, condition: str,
                        coding: dict) -> dict | None:
    """Mean probability mass over the outcome values, one leg-condition.

    Records enter through their p_norm letter masses mapped through the
    registered coding and averaged — probability mass, not samples.
    Low-mass records are excluded per the frozen rule; duplicate
    observation identities (condition, persona, item, qid) keep the
    first record and are counted."""
    pipe = load_pipeline()
    totals: dict[float, float] = {}
    mass_total = 0.0
    seen: set[tuple] = set()
    duplicates = 0
    for rec in records:
        if rec.get("condition") != condition:
            continue
        identity = (rec.get("condition"), rec.get("persona_id"),
                    rec.get("qid"), rec.get("item_index", 0))
        if identity in seen:
            duplicates += 1
            continue
        seen.add(identity)
        if pipe.analysis.is_low_mass(rec):
            continue
        pn = rec.get("p_norm") or {}
        added = 0.0
        for letter, mass in pn.items():
            if mass and letter in coding:
                totals[coding[letter]] = (totals.get(coding[letter], 0.0)
                                          + float(mass))
                added += float(mass)
        mass_total += added
    if mass_total <= 0:
        return None
    return {v: totals.get(v, 0.0) / mass_total for v in sorted(totals)}


def tvd(p: dict, q: dict) -> float:
    """Half the summed absolute difference of two distributions."""
    keys = set(p) | set(q)
    return 0.5 * sum(abs(p.get(k, 0.0) - q.get(k, 0.0)) for k in keys)


def compute_t2kx_tvd() -> tuple[pd.DataFrame, pd.DataFrame]:
    """TVD rows for support-matched experiments + the exclusions table.
    The 6 in-scope experiments absent from T2KX_HUMAN_FILES are excluded
    on data-availability grounds recorded here explicitly: the TESS
    experiments have only raw (uncleaned) microdata, ml1_gamblers_fallacy
    has no categorical human support matching the model's coding, and
    ml1_imagined_contact is a multi-item scale."""
    pipe = load_pipeline()
    excluded: list[dict] = []
    for exp_id, reason in (
        ("T2KX-ml1_gamblers_fallacy", "human support mismatch"),
        ("T2KX-ml1_imagined_contact", "multi-item scale"),
        ("T2KX-howard823", "TESS raw microdata, no category coding"),
        ("T2KX-reedBR32", "TESS raw microdata, no category coding"),
        ("T2KX-budescu779", "TESS raw microdata, no category coding"),
        ("T2KX-keusch433", "TESS raw microdata, no category coding"),
    ):
        excluded.append({"experiment": exp_id, "reason": reason})
    seen_excluded: set[str] = set()
    rows: list[dict] = []
    for exp_id, (rel_path, wording) in T2KX_HUMAN_FILES.items():
        spec = pipe.registry.get(exp_id).spec
        if any(len(c.items) != 1 for c in spec.conditions):
            if exp_id not in seen_excluded:
                seen_excluded.add(exp_id)
                excluded.append({"experiment": exp_id,
                                 "reason": "multi-item scale"})
            continue
        conditions = [c.name for c in spec.conditions]
        coding = outcome_values(exp_id, conditions[0], 0)
        support = support_from_coding(coding)
        path = HUMAN_CLEAN / rel_path
        human = {cond: human_condition_pmf(path, wording[i], support)
                 for i, cond in enumerate(conditions)}
        if any(h is None for h in human.values()):
            if exp_id not in seen_excluded:
                seen_excluded.add(exp_id)
                excluded.append({"experiment": exp_id,
                                 "reason": "human support mismatch"})
            continue
        for model in MODELS:
            for era, root in (("original", OLD_T2KX), ("redesigned",
                                                       NEW_RUN)):
                for blind in BLINDINGS:
                    leg = root / model / f"{exp_id}_{blind}"
                    records = pipe.analysis.load_records(root, model,
                                                         exp_id, blind)
                    if not records:
                        continue
                    for cond in conditions:
                        mp = model_condition_pmf(records, exp_id, cond,
                                                 coding)
                        rows.append({
                            "model": model, "era": era, "experiment": exp_id,
                            "blinding": blind, "condition": cond,
                            "tvd": tvd(human[cond], mp)
                            if mp is not None else float("nan"),
                            "human_pmf_computed": True,
                            "n_model_records": None,
                        })
    return pd.DataFrame(rows), pd.DataFrame(excluded)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for model in MODELS:
        for era, root in (("original", OLD_T2KX), ("redesigned", NEW_RUN)):
            rows.extend(analyze(root, model, era))
    rows, problems = join_frozen(rows)
    if problems:
        raise SystemExit("VALIDATION FAILED:\n" + "\n".join(problems[:20]))
    effects = pd.DataFrame(rows)
    effects.to_csv(OUT / "five_model_t2kx_effects.csv", index=False)
    tvd_frame, exclusions = compute_t2kx_tvd()
    tvd_frame.to_csv(OUT / "five_model_t2kx_tvd.csv", index=False)
    exclusions.to_csv(OUT / "five_model_t2kx_tvd_exclusions.csv",
                      index=False)
    print(f"wrote {len(effects)} effect rows, {len(tvd_frame)} TVD rows; "
          f"TVD exclusions: {exclusions.to_dict('records')}")


if __name__ == "__main__":
    main()
