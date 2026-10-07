# This module holds the twin2k10 figures' NUMBERS side: the fixed model and
# experiment orders, the 0-1 normalization rule, the error formulas that
# compare model answers against the human benchmark, the result-table row,
# the table builder with its special cases (anchoring excluded, base_rate
# first-digit variant, false_consensus without a contrast), the human
# test-retest band, and the descriptive variance split and per-model
# correlation. The drawing code lives in figures.py, which re-exports
# everything from here.

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np

MODEL_ORDER: list[str] = [
    "gpt-oss-20b",
    "gemma-4-26b-a4b",
    "gemma-4-31b-it-qat",
    "gemma-4-12b-it-qat",
    "qwen3.8-27b",
    "qwen3.6-27b-dense",
    "qwen3.6-35b-a3b",
    "qwen3.6-35b-a3b-uncensored",
    "qwen3-32b",
    "qwen3-4b",
    "granite-4.1-8b",
    "granite-4.1-30b",
    "nemotron-cascade-2-30b-a3b",
    "muse-glimmer",
    "glm-4.7-flash",
]

# The 16 registry experiments in registry order.
EXPERIMENT_ORDER: list[str] = [
    "disease",
    "less_is_more",
    "fire_extinguisher",
    "seatbelt",
    "sunk_cost",
    "wta_wtp",
    "allais",
    "linda",
    "base_rate",
    "anchoring_redwood",
    "anchoring_african",
    "outcome_bias",
    "myside",
    "prob_matching",
    "abs_relative",
    "false_consensus",
]

_TOL = 1e-3  # tolerance when matching a contrast value back to an arm pair


def normalize(value: float, spec: Mapping) -> float | None:
    """Map one raw answer onto 0-1 with the experiment's registered
    min/max. Returns None when the registry has no rule (NEEDS-OWNER)."""
    lo = spec.get("min")
    hi = spec.get("max")
    if lo is None or hi is None:
        return None
    return (value - lo) / (hi - lo)


def profile_error(
    model_means: Mapping[str, float], human_means: Mapping[str, float]
) -> float:
    """Average distance between the model's and the humans' arm means on
    the 0-1 scale, times 100. Both inputs must already be normalized."""
    gaps = [
        abs(model_means[arm] - human_means[arm])
        for arm in model_means
        if arm in human_means
    ]
    if not gaps:
        raise ValueError("no shared arms between model and human means")
    return float(np.mean(gaps) * 100.0)


def contrast_error(
    model_contrasts: Mapping[str, float], human_contrasts: Mapping[str, float]
) -> float:
    """Average distance between the model's and the humans' pre-specified
    contrast values (0-1 scale), times 100."""
    names = [name for name in model_contrasts if name in human_contrasts]
    if not names:
        raise ValueError("no shared contrasts between model and human")
    gaps = [abs(model_contrasts[name] - human_contrasts[name]) for name in names]
    return float(np.mean(gaps) * 100.0)


def profile_error_first_digit(
    model_dist: Mapping[int, float], human_dist: Mapping[int, float]
) -> float:
    """Average distance between two digit distributions (0-9 buckets),
    times 100. Used where the model side is a first-digit distribution."""
    digits = range(10)
    gaps = [abs(model_dist.get(d, 0.0) - human_dist.get(d, 0.0)) for d in digits]
    return float(np.mean(gaps) * 100.0)


@dataclass
class ErrorRow:
    """One line of the result table: a model's error numbers on one
    experiment, plus which comparison method was used."""

    model: str
    experiment: str
    method: str  # "arm_mean" or "first_digit"
    profile_error_blinded: float | None
    profile_error_unblinded: float | None
    contrast_error: float | None


def _normalize_arms(
    arms: Mapping[str, float], spec: Mapping
) -> dict[str, float] | None:
    """Normalize every arm of one experiment; None if any arm has no rule."""
    out: dict[str, float] = {}
    for arm, value in arms.items():
        if value is None:
            return None
        normed = normalize(value, spec)
        if normed is None:
            return None
        out[arm] = normed
    return out


def _model_contrasts(
    model_arms: Mapping[str, float],
    human_arms: Mapping[str, float],
    human_contrasts: Mapping,
) -> dict[str, float]:
    """Recover the model's contrast values by finding, for each human
    contrast, the arm pair whose difference reproduces it, then applying
    the same pair to the model's (normalized) arms."""
    out: dict[str, float] = {}
    for name, info in human_contrasts.items():
        if not info.get("computable"):
            continue
        target = info["value"]
        pair = _find_arm_pair(human_arms, target)
        if pair is None:
            continue
        a, b = pair
        out[name] = model_arms[a] - model_arms[b]
    return out


def _find_arm_pair(arms: Mapping[str, float], target: float) -> tuple[str, str] | None:
    """Find two arms whose difference equals the target contrast value."""
    names = list(arms)
    for a in names:
        for b in names:
            if a != b and abs(arms[a] - arms[b] - target) < _TOL:
                return (a, b)
    return None


def _experiment_row(
    model: str,
    experiment: str,
    spec: Mapping,
    human_wave: Mapping,
    blinding_arms: Mapping[str, Mapping],
    first_digit: bool,
) -> ErrorRow:
    """Build one model-x-experiment row: normalize arms, compute both
    blinding conditions' profile errors and the contrast error."""
    method = "first_digit" if first_digit else "arm_mean"
    profile: dict[str, float | None] = {}
    contrast: float | None = None
    human_arms = _normalize_arms(human_wave["arms"], spec)
    if method == "arm_mean" and human_arms is not None:
        for label, arms in blinding_arms.items():
            model_arms = _normalize_arms(arms, spec)
            profile[label] = (
                None if model_arms is None else profile_error(model_arms, human_arms)
            )
        if all(v is not None for v in profile.values()):
            model_blinded = _normalize_arms(blinding_arms["blinded"], spec)
            human_contrasts = human_wave.get("contrasts", {})
            model_c = _model_contrasts(model_blinded or {}, human_arms, human_contrasts)
            if model_c:
                human_c = {
                    name: info["value"]
                    for name, info in human_contrasts.items()
                    if info.get("computable")
                }
                contrast = contrast_error(model_c, human_c)
    else:
        # base_rate: no human first-digit distribution supplied by the
        # caller -> the metrics stay None but the method label documents
        # the variant. Anchoring: no normalization rule -> None.
        profile = {label: None for label in blinding_arms}
    return ErrorRow(
        model=model,
        experiment=experiment,
        method=method,
        profile_error_blinded=profile.get("blinded"),
        profile_error_unblinded=profile.get("unblinded"),
        contrast_error=contrast,
    )


def compute_error_rows(registry_subset: Mapping, llm_means: Mapping) -> list[ErrorRow]:
    """Build the error table for every model and experiment present in the
    caller's data, in the pinned MODEL_ORDER / EXPERIMENT_ORDER."""
    rows: list[ErrorRow] = []
    for model in MODEL_ORDER:
        if model not in llm_means:
            continue
        for experiment in EXPERIMENT_ORDER:
            if experiment not in llm_means[model]:
                continue
            spec = registry_subset[experiment]["normalization_0_1"]
            human_wave = registry_subset[experiment]["human"]["wave1_3"]
            blinding = llm_means[model][experiment]
            first_digit = bool(registry_subset[experiment].get("first_digit_profile"))
            rows.append(
                _experiment_row(
                    model, experiment, spec, human_wave, blinding, first_digit
                )
            )
    return rows


def human_test_retest_errors(registry_subset: Mapping) -> dict:
    """Run the SAME profile and contrast formulas between the humans'
    wave1_3 and wave4 answers. This is the test-retest band: how far the
    same humans drift between the two waves. Split-half is never used."""
    band: dict[str, dict] = {}
    for experiment, config in registry_subset.items():
        spec = config["normalization_0_1"]
        wave13 = config["human"]["wave1_3"]
        wave4 = config["human"]["wave4"]
        arms13 = _normalize_arms(wave13["arms"], spec)
        arms4 = _normalize_arms(wave4["arms"], spec)
        profile = (
            None if arms13 is None or arms4 is None else profile_error(arms4, arms13)
        )
        contrast = None
        c13 = {
            n: i["value"]
            for n, i in wave13.get("contrasts", {}).items()
            if i.get("computable")
        }
        c4 = {
            n: i["value"]
            for n, i in wave4.get("contrasts", {}).items()
            if i.get("computable")
        }
        if c13 and c4:
            contrast = contrast_error(c4, c13)
        band[experiment] = {"profile_error": profile, "contrast_error": contrast}
    return band


def variance_components(rows: list[ErrorRow]) -> dict:
    """Split the model-x-experiment profile-error table into three
    descriptive shares (model, experiment, leftover) that add up to 1."""
    cells: list[tuple[str, str, float]] = []
    for row in rows:
        value = row.profile_error_blinded
        if value is not None:
            cells.append((row.model, row.experiment, value))
    if not cells:
        return {"model": 0.0, "experiment": 0.0, "residual": 1.0}
    grand = float(np.mean([v for _, _, v in cells]))
    model_effects = []
    experiment_effects = []
    residuals = []
    for m, e, v in cells:
        m_mean = float(np.mean([x for mm, _, x in cells if mm == m]))
        e_mean = float(np.mean([x for _, ee, x in cells if ee == e]))
        model_effects.append(m_mean - grand)
        experiment_effects.append(e_mean - grand)
        residuals.append(v - m_mean - e_mean + grand)
    total = (
        float(np.mean(np.square(model_effects)))
        + float(np.mean(np.square(experiment_effects)))
        + float(np.mean(np.square(residuals)))
    )
    if total <= 0:
        return {"model": 0.0, "experiment": 0.0, "residual": 1.0}
    return {
        "model": float(np.mean(np.square(model_effects)) / total),
        "experiment": float(np.mean(np.square(experiment_effects)) / total),
        "residual": float(np.mean(np.square(residuals)) / total),
    }


def profile_contrast_correlation(rows: list[ErrorRow]) -> dict:
    """For each model, how its profile error moves with its contrast
    error across experiments. None when fewer than 3 points line up."""
    by_model: dict[str, list[tuple[float, float]]] = {}
    for row in rows:
        if row.profile_error_blinded is None or row.contrast_error is None:
            continue
        by_model.setdefault(row.model, []).append(
            (row.profile_error_blinded, row.contrast_error)
        )
    corr: dict[str, float | None] = {}
    for model in MODEL_ORDER:
        if model not in by_model:
            continue
        pairs = by_model[model]
        if len(pairs) < 3:
            corr[model] = None
            continue
        xs = np.array([p for p, _ in pairs])
        ys = np.array([c for _, c in pairs])
        if np.std(xs) == 0 or np.std(ys) == 0:
            corr[model] = None
            continue
        corr[model] = float(np.corrcoef(xs, ys)[0, 1])
    return corr
