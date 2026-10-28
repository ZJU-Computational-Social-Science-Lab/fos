# rebuild_model_effects.py — the Stage 10 canonical rebuild entry point.
# It reads the raw inference records, scores every record with the
# registered outcome rules, computes arm outcomes and treatment-minus-
# control contrasts for BOTH blinding legs and all models (originals +
# expansion), standardises by the frozen human pooled SD, adds corrected
# persona-bootstrap uncertainty, and writes the canonical tables
# atomically (build in a temp directory, validate, then promote — a
# failed run never leaves partial authoritative tables).
#
# What each function does:
#   derive_seed                — one deterministic per-cell bootstrap seed.
#   frozen_models              — the 15 registered models, frozen order.
#   original_effects           — raw records -> native pp effects for the
#                                18 original contrasts + arm accounting.
#   expansion_effects          — raw records -> native effects for the 20
#                                expansion contrasts + arm accounting.
#   attach_uncertainty         — persona bootstrap SEs for every cell.
#   _bootstrap_originals       — originals: persona-record bootstrap.
#   _persona_pairs             — per-persona value arrays across arms.
#   _zero_note / _exp_zero_note — honest zero-probability accounting notes.
#   attach_human_denominators  — frozen human pooled SD + std conversions.
#   write_manifest             — provenance manifest with input hashes.
#   promote                    — atomic move of validated tables into data/.
#   update_registry            — DATASET_REGISTRY.json approved pointer.
#   main                       — the full deterministic pipeline run.

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from stage10_common import (DATA_DIR, HERE, MANIFEST, NDRAWS, PROV_DIR,
                            REGISTRY_JSON, SEED, UNBL, VERSION,
                            load_register, log, sha256_file, sha256_text,
                            take_log)
import originals_scoring as orig
import expansion_scoring as exp
import canonical_tables
import frozen_check


def derive_seed(contrast_id: str, model: str, blinding: int) -> int:
    """Deterministic per-cell bootstrap seed (recorded in the manifest)."""
    key = f"{SEED}|{contrast_id}|{model}|{blinding}"
    return int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)


def frozen_models() -> list[str]:
    """The 15 registered models (frozen expansion config order)."""
    return list(exp._pipeline().config.MODELS)


# ---------------------------------------------------------------- originals

def original_effects() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Raw records -> native pp effects for the 18 original contrasts.

    Returns (effects, arm accounting, raw cells). The estimator is the
    frozen one: flat mean over retained records per arm, registered
    normalisation, treatment-minus-control, x100 pp.
    """
    rules = orig._load_rules()
    registry = orig.load_run_registry()
    models = frozen_models()
    cells = orig.scan_records(models)
    register = [r for r in load_register()
                if r["study_group"] == "original"]
    arm_rows, acct = _original_arm_means(cells)
    arms = pd.DataFrame(arm_rows)
    out = []
    for reg in sorted(register, key=lambda r: r["contrast_id"]):
        cfg = registry[reg["experiment_id"]]
        spec = cfg["normalization_0_1"]
        wave = cfg["human"]["wave1_3"]
        anchor = "anchor_mc" in list(wave["arms"].values())[0]
        out.extend(_original_contrast_rows(reg, models, arms, rules, spec,
                                           wave, anchor))
    return pd.DataFrame(out), pd.DataFrame(acct), cells


def _original_arm_means(cells: dict) -> tuple[list[dict], list[dict]]:
    """Registered flat arm means + per-cell record accounting."""
    rows, acct = [], []
    for (model, experiment, blinding, arm), cell in sorted(cells.items()):
        mean, n = orig.arm_outcome(cell)
        rows.append({"model": model, "experiment": experiment,
                     "blinding": blinding, "arm": arm, "mean_raw": mean,
                     "n_retained": n})
        acct.append({"model": model, "experiment": experiment,
                     "blinding": blinding, "arm": arm,
                     "n_total": cell.n_total, "n_failed": cell.n_failed,
                     "n_unreadable": cell.n_unreadable,
                     "n_low_mass": cell.n_low_mass, "n_retained": n})
    return rows, acct


def _original_contrast_rows(reg: dict, models: list[str], arms: pd.DataFrame,
                            rules, spec: dict, wave: dict,
                            anchor: bool) -> list[dict]:
    """One contrast's rows across models and legs (registered rules)."""
    rows = []
    for leg, b in (("blinded", 0), ("unblinded", 1)):
        for model in models:
            sub = arms[(arms.model == model)
                       & (arms.experiment == reg["experiment_id"])
                       & (arms.blinding == leg)]
            got = {r.arm: r.mean_raw for r in sub.itertuples()}
            if set(got) != set(wave["arms"]) or any(
                    v != v for v in got.values()):
                continue  # incomplete coverage: row absent, as frozen
            m_obs = (got if anchor
                     else {a: rules.normalize01(v, spec)
                           for a, v in got.items()})
            d_m = (m_obs[reg["treatment_condition"]]
                   - m_obs[reg["control_condition"]]) * 100.0
            rows.append({"contrast_id": reg["contrast_id"],
                         "experiment_id": reg["experiment_id"],
                         "study_group": "original", "model": model,
                         "blinding": b, "model_effect_native": d_m,
                         "n_t": int(sub[sub.arm ==
                                        reg["treatment_condition"]]
                                    .n_retained.iloc[0]),
                         "n_c": int(sub[sub.arm ==
                                        reg["control_condition"]]
                                    .n_retained.iloc[0])})
    return rows


# ---------------------------------------------------------------- expansion

def expansion_effects() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Raw records -> native effects for the 20 expansion contrasts.

    ALL expansion contrasts are re-derived from the records; none is
    copied from the frozen table. Returns (effects, accounting, cells)."""
    cells = exp.load_cells()
    register = [r for r in load_register()
                if r["study_group"] != "original"]
    rows = []
    for reg in sorted(register, key=lambda r: r["contrast_id"]):
        for model in frozen_models():
            for b, leg in ((0, "blinded"), (1, "unblinded")):
                rows.append(_expansion_row(reg, model, b, leg, cells))
    effects = pd.DataFrame([r for r in rows if r is not None])
    effects = frozen_check.check_expansion(effects)
    return effects, exp.accounting(cells), cells


def _expansion_row(reg: dict, model: str, b: int, leg: str,
                   cells: dict) -> dict | None:
    """One contrast x model x leg row, or None if a leg is missing."""
    names = (reg["treatment_condition"].split("+")
             + reg["control_condition"].split("+"))
    try:
        leg_cells = {cond: cells[(model, reg["experiment_id"], leg, cond)]
                     for cond in names}
    except KeyError:
        raise KeyError(f"missing expansion arm: {reg['contrast_id']} "
                       f"{model} leg {leg}")
    t_cell = exp.pooled_cell(leg_cells, reg["treatment_condition"])
    c_cell = exp.pooled_cell(leg_cells, reg["control_condition"])
    delta, n_c, n_t = exp.contrast_delta_from(t_cell, c_cell)
    return {"contrast_id": reg["contrast_id"],
            "experiment_id": reg["experiment_id"],
            "study_group": "expansion", "model": model, "blinding": b,
            "model_effect_native": delta, "n_t": n_t, "n_c": n_c}


# ------------------------------------------------------------- uncertainty

def attach_uncertainty(orig_effects: pd.DataFrame, orig_cells: dict,
                       exp_effects: pd.DataFrame, exp_cells: dict
                       ) -> pd.DataFrame:
    """Persona bootstrap SEs for both study groups, merged into one frame.

    Originals: persona-record bootstrap on raw values (pp via the
    registered normalisation range). Expansion: persona-pair bootstrap on
    the native scale with one joint resample per draw. Fails if any cell
    lacks an SE — never a quiet zero.
    """
    se_rows = (_bootstrap_originals(orig_effects, orig_cells)
               + _bootstrap_expansion(exp_effects, exp_cells))
    unc = pd.DataFrame(se_rows)
    effects = pd.concat([orig_effects, exp_effects], ignore_index=True)
    effects = effects.merge(unc, on=["contrast_id", "model", "blinding"],
                            how="left", validate="one_to_one")
    if effects.model_effect_se.isna().any():
        n = int(effects.model_effect_se.isna().sum())
        raise ValueError(f"{n} cells without a bootstrap SE")
    return effects


def _bootstrap_originals(effects: pd.DataFrame, cells: dict) -> list[dict]:
    """Persona-record bootstrap per original contrast x model x leg.

    The registered pp scale is linear in the raw scale, so raw-scale draw
    SEs convert to pp with the registered normalisation range.
    """
    registry = orig.load_run_registry()
    register = {r["contrast_id"]: r for r in load_register()
                if r["study_group"] == "original"}
    rows = []
    for r in effects.itertuples():
        reg = register[r.contrast_id]  # unique per contrast_id here
        spec = registry[reg["experiment_id"]]["normalization_0_1"]
        leg = "blinded" if r.blinding == 0 else "unblinded"
        t_cell = cells[(r.model, reg["experiment_id"], leg,
                        reg["treatment_condition"])]
        c_cell = cells[(r.model, reg["experiment_id"], leg,
                        reg["control_condition"])]
        boot = orig.persona_flat_boot(
            _persona_pairs(t_cell, c_cell),
            derive_seed(r.contrast_id, r.model, r.blinding))
        # Anchoring has no raw-unit normalisation (registered): the arm
        # outcome is already a 0-1 anchor share, so the pp span is 1.
        span = ((float(spec["max"]) - float(spec["min"]))
                if spec.get("max") is not None else 1.0)
        rows.append({"contrast_id": r.contrast_id, "model": r.model,
                     "blinding": r.blinding,
                     "model_effect_se": float(boot["se"]) * 100.0 / span,
                     "boot_seed": boot["seed"], "boot_draws": NDRAWS,
                     "degenerate_share": boot["degenerate"],
                     "zero_prob_note": _zero_note(t_cell, c_cell)})
    return rows


def _persona_pairs(t_cell, c_cell) -> list:
    """Per-persona raw-value arrays aligned across the two arms."""
    t_map = orig.persona_record_values(t_cell)
    c_map = orig.persona_record_values(c_cell)
    ids = sorted(set(t_map) | set(c_map))
    empty = np.array([])
    return [(c_map.get(p, empty), t_map.get(p, empty)) for p in ids]


def _zero_note(t_cell, c_cell) -> str:
    """Honest note on failed / unreadable records in an original cell."""
    parts = []
    for name, cell in (("treatment", t_cell), ("control", c_cell)):
        if cell.n_unreadable or cell.n_failed:
            parts.append(f"{name}: {cell.n_failed} failed, "
                         f"{cell.n_unreadable} unreadable kept missing")
    return "; ".join(parts) if parts else "none"


def _bootstrap_expansion(effects: pd.DataFrame, cells: dict) -> list[dict]:
    """Persona-pair bootstrap per expansion contrast x model x leg.

    Personas are shared across the arms of a leg (same panel), so one
    resample is applied to both arms jointly; '+'-pooled arms are merged
    first with the registered pooling.
    """
    register = {r["contrast_id"]: r for r in load_register()
                if r["study_group"] != "original"}
    rows = []
    for r in effects.itertuples():
        reg = register[r.contrast_id]
        leg = "blinded" if r.blinding == 0 else "unblinded"
        names = (reg["treatment_condition"].split("+")
                 + reg["control_condition"].split("+"))
        leg_cells = {cond: cells[(r.model, reg["experiment_id"], leg, cond)]
                     for cond in names}
        t_cell = exp.pooled_cell(leg_cells, reg["treatment_condition"])
        c_cell = exp.pooled_cell(leg_cells, reg["control_condition"])
        boot = exp.persona_boot(
            t_cell, c_cell, derive_seed(r.contrast_id, r.model, r.blinding),
            NDRAWS)
        rows.append({"contrast_id": r.contrast_id, "model": r.model,
                     "blinding": r.blinding,
                     "model_effect_se": float(boot["se"]),
                     "boot_seed": boot["seed"], "boot_draws": NDRAWS,
                     "degenerate_share": boot["degenerate"],
                     "zero_prob_note": _exp_zero_note(t_cell, c_cell)})
    return rows


def _exp_zero_note(t_cell, c_cell) -> str:
    """Honest note on zero-mass records in an expansion cell."""
    parts = []
    for name, cell in (("treatment", t_cell), ("control", c_cell)):
        if cell.n_zero_mass:
            parts.append(f"{name}: {cell.n_zero_mass} zero-mass records "
                         "kept missing (D.6-A(d))")
    return "; ".join(parts) if parts else "none"


# ------------------------------------------------- human denominators (std)

def attach_human_denominators(effects: pd.DataFrame) -> pd.DataFrame:
    """Frozen human pooled SD (pp) and human effect per contrast.

    Originals: stage 3 frozen SD verification file (native SD x pp
    factor; frozen human pp effect). Expansion: the frozen expansion17
    per-contrast SD and d_human_std. LLM variability is NEVER a
    denominator.
    """
    sd = pd.read_csv(stage10_paths_HUMAN_SD())
    sd["sd_human_pooled_pp"] = (sd.sd_human_pooled_native
                                * sd.native_to_pp_factor)
    sd["human_effect_std"] = (sd.frozen_delta_human_pp
                              / sd.sd_human_pooled_pp)
    orig_sd = sd.set_index("contrast_id")
    exp_sd = expansion_sd_by_contrast()
    rows = []
    for r in effects.itertuples():
        if r.study_group == "original":
            row = orig_sd.loc[r.contrast_id]
            rows.append({"sd_human_pooled_pp": row.sd_human_pooled_pp,
                         "delta_human_pp": row.frozen_delta_human_pp,
                         "human_effect_std": row.human_effect_std})
        else:
            row = exp_sd.loc[r.contrast_id]
            rows.append({"sd_human_pooled_pp": row.sd_human_pooled,
                         "delta_human_pp": row.delta_human,
                         "human_effect_std": row.d_human_std})
    den = pd.DataFrame(rows, index=effects.index)
    out = pd.concat([effects, den], axis=1)
    out["model_effect_std"] = out.model_effect_native / out.sd_human_pooled_pp
    out["model_effect_se_std"] = out.model_effect_se / out.sd_human_pooled_pp
    return out


def stage10_paths_HUMAN_SD():
    """Frozen human SD verification file (imported late for clarity)."""
    from stage10_common import HUMAN_SD
    return HUMAN_SD


def expansion_sd_by_contrast() -> pd.DataFrame:
    """Frozen expansion human SD / human std effect per contrast."""
    from stage10_common import EXPANSION17
    exp17 = pd.read_csv(EXPANSION17)
    keep = exp17[~exp17["unestimable"].astype(str).str.lower().eq("true")]
    return keep.groupby("contrast_id").agg(
        sd_human_pooled=("sd_human_pooled", "first"),
        d_human_std=("d_human_std", "first"),
        delta_human=("delta_human", "first"))


# ------------------------------------------------------------ atomic main

def write_manifest(out_dir: Path, outputs: list[str],
                   acct: pd.DataFrame) -> None:
    """Provenance manifest: input hashes, code version, seed, outputs."""
    from stage10_common import (COVERAGE, EXPANSION17, FROZEN_262,
                                FIG_REGISTRY, HUMAN_SD, REGISTER_CSV,
                                STAGE5_DATASET)
    inputs = {str(p): sha256_file(p) for p in
              [FROZEN_262, EXPANSION17, REGISTER_CSV, HUMAN_SD, COVERAGE,
               STAGE5_DATASET, FIG_REGISTRY, Path(__file__)]}
    payload = {
        "version": VERSION, "seed": SEED, "bootstrap_draws": NDRAWS,
        "created": pd.Timestamp.now(tz="UTC").isoformat(),
        "scoring_code_version": sha256_text(
            Path(__file__).read_text()),
        "experiment_registry": str(REGISTER_CSV),
        "inputs": inputs,
        "outputs": {name: sha256_file(out_dir / name) for name in outputs},
        "coverage": canonical_tables.coverage_report(
            pd.read_csv(out_dir / outputs[0])),
        "accounting_rows": int(len(acct)),
    }
    (out_dir / "provenance/CANONICAL_DATA_MANIFEST.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n")


def promote(tmp: Path) -> None:
    """Atomically move the validated build into place."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROV_DIR.mkdir(parents=True, exist_ok=True)
    for name in ["CANONICAL_ARM_OUTCOMES.csv", "CANONICAL_MODEL_EFFECTS.csv",
                 "MODEL_EFFECT_UNCERTAINTY_CORRECTED.csv",
                 "CANONICAL_PAIRED_ANALYSIS.csv",
                 "OLD_VS_CORRECTED_EFFECTS.csv"]:
        shutil.move(str(tmp / name), str(DATA_DIR / name))
    shutil.move(str(tmp / "provenance/CANONICAL_DATA_MANIFEST.json"),
                str(MANIFEST))


def update_registry() -> None:
    """DATASET_REGISTRY.json: the approved canonical version pointer."""
    entry = {"version": VERSION, "status": "approved",
             "manifest": "provenance/CANONICAL_DATA_MANIFEST.json",
             "manifest_sha256": sha256_file(MANIFEST),
             "tables": ["data/CANONICAL_ARM_OUTCOMES.csv",
                        "data/CANONICAL_MODEL_EFFECTS.csv",
                        "data/MODEL_EFFECT_UNCERTAINTY_CORRECTED.csv",
                        "data/CANONICAL_PAIRED_ANALYSIS.csv"]}
    REGISTRY_JSON.write_text(
        json.dumps({"approved": VERSION, "versions": {VERSION: entry}},
                   indent=2) + "\n")


def _build_effects(cache: Path) -> None:
    """Stages 1-3: rebuild effects from raw records, add uncertainty,
    cache the combined effects frame so table iterations stay cheap."""
    log("[1/6] originals from raw records ...")
    orig_effects, orig_acct, orig_cells = original_effects()
    orig_effects, orig_exceptions = frozen_check.check_originals(
        orig_effects)
    log("[2/6] expansion from raw records ...")
    exp_effects, exp_acct, exp_cells = expansion_effects()
    log("[3/6] persona bootstrap uncertainty ...")
    effects = attach_uncertainty(orig_effects, orig_cells,
                                 exp_effects, exp_cells)
    effects.to_csv(cache, index=False)
    orig_exceptions.to_csv(HERE / "data" / ".cache_exceptions.csv",
                           index=False)
    (HERE / "data" / ".cache_acct.csv").write_text(
        pd.concat([orig_acct, exp_acct], ignore_index=True).to_csv(
            index=False))


def main() -> None:
    """Full deterministic pipeline run (seeds recorded in the manifest)."""
    cache = HERE / "data" / ".cache_effects.csv"
    if not cache.exists():
        _build_effects(cache)
    effects = pd.read_csv(cache)
    orig_exceptions = pd.read_csv(HERE / "data" / ".cache_exceptions.csv")
    acct = pd.read_csv(HERE / "data" / ".cache_acct.csv")
    log("loaded cached effects (delete data/.cache_effects.csv to "
        "force a full rebuild)")
    effects = attach_human_denominators(effects)
    log("[4/6] building canonical tables ...")
    log("[3/6] persona bootstrap uncertainty ...")
    log("[4/6] building canonical tables ...")
    tables = canonical_tables.build_tables(effects)
    canonical_tables.validate_tables(tables)
    log("[5/6] atomic promotion ...")
    names = ["CANONICAL_ARM_OUTCOMES.csv", "CANONICAL_MODEL_EFFECTS.csv",
             "MODEL_EFFECT_UNCERTAINTY_CORRECTED.csv",
             "CANONICAL_PAIRED_ANALYSIS.csv"]
    with tempfile.TemporaryDirectory(dir=HERE) as td:
        tmp = Path(td)
        for table, name in zip(tables, names):
            table.to_csv(tmp / name, index=False)
        import compare_effects
        compare_effects.write_old_vs_corrected(
            effects, orig_exceptions,
            tmp / "OLD_VS_CORRECTED_EFFECTS.csv")
        (tmp / "provenance").mkdir()
        write_manifest(tmp, names, acct)
        promote(tmp)
    update_registry()
    log("[6/6] writing build log ...")
    arm = pd.read_csv(DATA_DIR / names[0])
    (DATA_DIR / "build_log.txt").write_text(
        take_log() + str(canonical_tables.coverage_report(arm)) + "\n")
    print("canonical rebuild complete:", VERSION)


if __name__ == "__main__":
    main()
