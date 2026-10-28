# expansion_scoring.py — rebuilds the 17 EXPANSION experiments' arm
# outcomes and contrast deltas straight from the raw production records by
# reusing the frozen expansion pipeline modules (registry, outcomes,
# analysis conventions). No new estimators: the scoring is the production
# code, imported as-is; this module only adds the numpy-vectorised
# persona bootstrap (resampling personas jointly across the paired arms)
# and per-cell accounting.
#
# What each function does:
#   _pipeline          — imports the frozen expansion pipeline package.
#   load_cells         — one streaming pass over all 309k expansion
#                        records; keeps persona-level retained values
#                        (primary cut mass >= 0.80) per arm.
#   contrast_delta     — registered delta under the analysis.py estimator
#                        (per-persona item means, then mean over personas);
#                        reproduces the frozen contrast_level_results.
#   persona_boot       — vectorised persona-pair bootstrap of the delta on
#                        the native scale, seed and draws passed in.
#   account_cell       — per-cell record accounting from the same pass.

from __future__ import annotations

import sys

import pandas as pd
from dataclasses import dataclass, field

import numpy as np

from stage10_common import EXPANSION_RUN, UNBL

_pipe = None


def _pipeline():
    """Import the frozen expansion pipeline package (read-only source)."""
    global _pipe
    if _pipe is None:
        sys.path.insert(0, str(UNBL / "expansion"))
        from pipeline import analysis, config, outcomes, registry  # noqa: F401
        _pipe = type("P", (), {"config": config, "registry": registry,
                               "outcomes": outcomes})
    return _pipe


@dataclass
class ExpCell:
    """One model x experiment x blinding x condition cell: each retained
    record's outcome value, kept per persona (values may repeat if an
    experiment has multiple items per persona)."""
    persona_values: dict[int, list[float]] = field(default_factory=dict)
    n_total: int = 0
    n_zero_mass: int = 0
    n_excluded: int = 0


def load_cells() -> dict:
    """Stream every expansion leg once, keeping retained persona values.

    Returns {(model, exp, blinding, condition): ExpCell} where blinding is
    'blinded'/'unblinded'. Records with zero branch mass are counted as
    missing (registered D.6-A rule) — never folded in as zero.
    """
    pipe = _pipeline()
    cells: dict[tuple, ExpCell] = {}
    for model in pipe.config.MODELS:
        for exp_id in pipe.registry.ready_experiments():
            for blinding in pipe.config.BLINDINGS:
                path = EXPANSION_RUN / model / f"{exp_id}_{blinding}" / "records.jsonl"
                if not path.exists():
                    raise FileNotFoundError(f"missing production leg: {path}")
                with path.open(encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        rec = json_record(line)
                        cond = rec["condition"]
                        cell = cells.setdefault(
                            (model, exp_id, blinding, cond), ExpCell())
                        cell.n_total += 1
                        mass = rec.get("branch_mass")
                        mass = float(mass) if mass is not None else 0.0
                        if mass <= 0.0:
                            cell.n_zero_mass += 1
                        if mass < 0.80:
                            cell.n_excluded += 1
                            continue
                        outcome = pipe.outcomes.outcome_for(
                            exp_id, cond, rec["item_index"])
                        value = outcome.value_of(rec["p_norm"])
                        cell.persona_values.setdefault(
                            rec["persona_id"], []).append(value)
    return cells


def json_record(line: str) -> dict:
    """Parse one JSONL record (tiny wrapper so tests can monkeypatch)."""
    import json
    return json.loads(line)


def condition_mean(cell: ExpCell) -> tuple[float, int]:
    """Registered arm mean: per-persona item means, then mean over
    personas (analysis.py semantics). Returns (nan, 0) when empty."""
    if not cell.persona_values:
        return float("nan"), 0
    per_persona = [np.mean(v) for v in cell.persona_values.values()]
    return float(np.mean(per_persona)), len(per_persona)


def persona_boot(cell_t: ExpCell, cell_c: ExpCell, seed: int,
                 draws: int) -> dict:
    """Vectorised persona bootstrap of the native-scale delta.

    The expansion run uses the same persona panel in every condition of a
    leg, so one persona resample is applied to BOTH arms jointly (a
    persona missing from one arm contributes only to the other). The
    estimator is the same per-persona-mean average as the point estimate.
    Returns SE, degenerate-draw share, and the draws.
    """
    t_pv = ({p: float(np.mean(v)) for p, v in cell_t.persona_values.items()}
            if cell_t else {})
    c_pv = ({p: float(np.mean(v)) for p, v in cell_c.persona_values.items()}
            if cell_c else {})
    ids = sorted(set(t_pv) | set(c_pv))
    if not ids:
        return {"seed": seed, "se": float("nan"), "degenerate": 1.0,
                "draws": np.array([])}
    t = np.array([t_pv.get(p, np.nan) for p in ids])
    c = np.array([c_pv.get(p, np.nan) for p in ids])
    n = len(ids)
    idx = np.random.RandomState(seed).randint(0, n, size=(draws, n))
    with np.errstate(invalid="ignore"):
        t_means = np.nanmean(t[idx], axis=1)
        c_means = np.nanmean(c[idx], axis=1)
    out = t_means - c_means
    bad = int(np.isnan(out).sum())
    if bad == draws:
        return {"seed": seed, "se": float("nan"), "degenerate": 1.0,
                "draws": out}
    return {"seed": seed, "se": float(np.nanstd(out, ddof=1)),
            "degenerate": bad / draws, "draws": out}


def pooled_cell(cells: dict, arm_spec: str) -> ExpCell:
    """Merge a '+'-pooled arm spec into one cell (registered pooling)."""
    merged = ExpCell()
    for part in arm_spec.split("+"):
        cell = cells[part.strip()]
        merged.n_total += cell.n_total
        merged.n_zero_mass += cell.n_zero_mass
        merged.n_excluded += cell.n_excluded
        for persona, values in cell.persona_values.items():
            merged.persona_values.setdefault(persona, []).extend(values)
    return merged


def contrast_delta_from(t_cell: ExpCell, c_cell: ExpCell
                        ) -> tuple[float, int, int]:
    """Treatment-minus-control delta with the registered estimator.

    Per-persona item means first, then mean over personas (the production
    analysis.py semantics). Returns (delta, n_control, n_treatment);
    delta is NaN (not zero) when either arm has no retained persona.
    """
    t_mean, n_t = condition_mean(t_cell)
    c_mean, n_c = condition_mean(c_cell)
    if t_mean != t_mean or c_mean != c_mean:
        return float("nan"), n_c, n_t
    return t_mean - c_mean, n_c, n_t


def accounting(cells: dict) -> pd.DataFrame:
    """Per-cell record accounting for every expansion arm."""
    rows = [{"model": k[0], "experiment": k[1], "blinding": k[2],
             "arm": k[3], "n_total": c.n_total,
             "n_zero_mass": c.n_zero_mass, "n_excluded": c.n_excluded,
             "n_retained": sum(len(v) for v in c.persona_values.values())}
            for k, c in sorted(cells.items())]
    return pd.DataFrame(rows)
