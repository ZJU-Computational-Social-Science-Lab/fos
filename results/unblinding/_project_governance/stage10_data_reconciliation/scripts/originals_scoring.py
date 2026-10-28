# originals_scoring.py — rebuilds the ORIGINAL-14 experiments' arm outcomes
# straight from the raw inference records of the two production runs
# (run6 = 6-task, run10 = 10-task), reusing the frozen, validated outcome
# rules from the T2K10 final audit instead of reinventing them.
#
# What each function does:
#   _load_rules        — imports the validated record_outcome function from
#                        the frozen final-audit script.
#   load_run_registry  — the experiment registry (arms, normalization,
#                        human benchmark) used by the frozen pipeline.
#   scan_records       — one pass over every original-leg records.jsonl:
#                        keeps each record's outcome, its persona id, and
#                        its branch mass so both the registered flat arm
#                        mean and the persona bootstrap can be computed.
#   arm_outcome        — the registered arm mean (flat mean over retained
#                        records — this reproduces the frozen 262-row file).
#   contrast_delta     — registered treatment-minus-control delta in pp.
#   persona_flat_boot  — bootstrap that resamples personas (records of a
#                        resampled persona move together across arms) and
#                        scores the SAME flat-mean estimator, so the
#                        bootstrap's centre agrees with the point estimate.
#   account_cell       — per-cell record accounting (total, zero mass,
#                        unreadable, retained) so nothing is dropped
#                        silently.

from __future__ import annotations

import importlib.util
import json
import random
from dataclasses import dataclass, field

import numpy as np

from stage10_common import (FINAL_AUDIT, FIG_REGISTRY, ORIGINAL_EXCLUSIONS,
                            RUN10, RUN6, SEED, NDRAWS, UNBL)

# The outcome rule code lives inside the frozen audit script; import it.
_rules = None


def _load_rules():
    """Import record_outcome (and its helpers) from the frozen audit file."""
    global _rules
    if _rules is None:
        spec = importlib.util.spec_from_file_location("t2k10_final_audit",
                                                      FINAL_AUDIT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _rules = mod
    return _rules


@dataclass
class CellData:
    """One model x experiment x blinding x arm cell: every scored record's
    value with the persona it belongs to and its branch mass."""
    persona_values: dict[int, list[float]] = field(default_factory=dict)
    n_total: int = 0
    n_failed: int = 0
    n_unreadable: int = 0
    n_low_mass: int = 0

    def add(self, persona: int, value: float) -> None:
        self.n_total += 1
        if value is None:
            self.n_unreadable += 1
            return
        self.persona_values.setdefault(persona, []).append(value)


def load_run_registry() -> dict:
    """The frozen experiment registry used by the original-14 pipeline."""
    with open(FIG_REGISTRY, encoding="utf-8") as fh:
        return json.load(fh)["experiments"]


def _run_root(run_key: str) -> object:
    """Map the registry's run label to its records directory."""
    roots = {"run6": RUN6, "run10": RUN10}
    if run_key not in roots:
        raise ValueError(f"unknown run label {run_key}")
    return roots[run_key]


def scan_records(models: list[str]) -> dict:
    """Stream every original leg once.

    Returns {(model, experiment, blinding, arm): CellData} for the 14
    non-excluded registered experiments. Blinding keys are the registry's
    'blinded'/'unblinded'; the caller maps them to 0/1.
    """
    rules = _load_rules()
    registry = load_run_registry()
    cells: dict[tuple, CellData] = {}
    for exp, config in registry.items():
        if exp in ORIGINAL_EXCLUSIONS:
            continue
        root = _run_root(config["run"])
        for blinding in ("blinded", "unblinded"):
            for model in models:
                path = root / model / f"{exp}_{blinding}" / "records.jsonl"
                if not path.is_file():
                    raise FileNotFoundError(f"missing original leg: {path}")
                with path.open(encoding="utf-8") as fh:
                    for line in fh:
                        if not line.strip():
                            continue
                        rec = json.loads(line)
                        cell = cells.setdefault(
                            (model, exp, blinding, rec["arm"]), CellData())
                        if not rec.get("succeeded", False):
                            cell.n_total += 1
                            cell.n_failed += 1
                            continue
                        if rec.get("low_branch_mass", False):
                            cell.n_low_mass += 1
                        cell.add(rec["persona_id"],
                                 rules.record_outcome(rec, exp))
    return cells


def arm_outcome(cell: CellData) -> tuple[float, int]:
    """Registered arm mean (flat over retained records) and record count.

    Matches the frozen pipeline exactly: every retained record counts
    once. Returns (nan, 0) for an empty cell — never a quiet zero.
    """
    values = [v for vals in cell.persona_values.values() for v in vals]
    if not values:
        return float("nan"), 0
    return float(np.mean(values)), len(values)


def persona_record_values(cell: CellData) -> dict[int, np.ndarray]:
    """Each persona's retained values as one array (for the bootstrap)."""
    return {p: np.array(v, dtype=float)
            for p, v in cell.persona_values.items()}


def persona_flat_boot(pairs: list[tuple[np.ndarray, np.ndarray]],
                      seed: int, draws: int = NDRAWS) -> dict:
    """Persona bootstrap of the treatment-minus-control delta.

    `pairs` is one (control_values, treatment_values) pair per persona
    that appears in either arm; resampling a persona moves all of its
    records together (shared personas across arms stay paired). The
    estimator inside each draw is the same flat record mean the point
    estimate uses. Returns the seed, the RAW-scale draws' sd (the SE;
    the caller converts to the scale it reports), the share of
    degenerate draws, and the draw list itself.
    """
    if not pairs:
        return {"seed": seed, "se": float("nan"), "degenerate": 1.0,
                "draws": np.array([])}
    ctrl = [p[0] for p in pairs]
    trt = [p[1] for p in pairs]
    n = len(pairs)
    rng = random.Random(seed)
    out = np.empty(draws)
    n_bad = 0
    for i in range(draws):
        cs, ts = [], []
        for _ in range(n):
            j = rng.randrange(n)
            if ctrl[j].size:
                cs.append(ctrl[j])
            if trt[j].size:
                ts.append(trt[j])
        if not cs or not ts:
            out[i] = np.nan
            n_bad += 1
            continue
        c_mean = np.mean(np.concatenate(cs))
        t_mean = np.mean(np.concatenate(ts))
        out[i] = t_mean - c_mean
    se = float(np.nanstd(out, ddof=1)) if n_bad < draws else float("nan")
    return {"seed": seed, "se": se, "degenerate": n_bad / draws,
            "draws": out}
