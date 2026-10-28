# fig02_common.py — shared maths and data types for the Figure 02
# all-31-experiment distributional-distance analysis.
#
# What this file does: it defines the one distance used everywhere (a
# normalized 1-D Wasserstein distance on each experiment's REGISTERED
# outcome space) and the helpers to aggregate distances fairly across
# arms, models and experiments.
#
# Functions:
#   weighted_dist      -> distance between a human and an LLM response
#                         distribution (0 = identical, 1 = maximal)
#   split_half_dist    -> distance between two random halves of one arm's
#                         human respondents (the noise reference)
#   exp_mean           -> equal-arm-weight average of arm distances
#   ecdf_points        -> sorted (x, cumulative share) pairs for plotting

from dataclasses import dataclass, field

import numpy as np
from scipy.stats import wasserstein_distance


@dataclass
class ArmData:
    """One arm's responses on the registered outcome scale.

    human_values — one registered-scale value per human respondent
                   (multi-item respondents already averaged to one value);
    llm_values   — one registered-scale value per LLM persona (per-persona
                   mean over that persona's scored items);
    space        — (lo, hi): the registered outcome space's bounds, used
                   to normalize distances into [0, 1].
    """
    human_values: np.ndarray
    llm_values: dict = field(default_factory=dict)  # model -> values array
    llm_weights: dict = field(default_factory=dict)  # model -> weights
    space: tuple = (0.0, 1.0)

    @property
    def span(self) -> float:
        return self.space[1] - self.space[0]


def _norm(values: np.ndarray, span_lo: float, span_hi: float) -> np.ndarray:
    """Scale registered outcome values into [0, 1] (both sides equally)."""
    return (np.asarray(values, dtype=float) - span_lo) / (span_hi - span_lo)


def weighted_dist(human_values: np.ndarray, llm_values: np.ndarray,
                  span_lo: float, span_hi: float,
                  llm_weights: np.ndarray = None) -> float:
    """Normalized Wasserstein-1 distance between human and LLM responses.

    Both samples are put on the same registered outcome scale and
    normalized by that scale's range, so the distance lives in [0, 1]
    (0 = identical distributions). For a two-point (binary) registered
    space this equals the total variation distance.
    """
    if len(human_values) == 0 or len(llm_values) == 0:
        raise ValueError("empty sample: a missing cell is never scored as "
                         "zero distance")
    h = _norm(human_values, span_lo, span_hi)
    m = _norm(llm_values, span_lo, span_hi)
    w = None if llm_weights is None else np.asarray(llm_weights, float)
    return float(wasserstein_distance(h, m, v_weights=w))


def split_half_dist(values: np.ndarray, span_lo: float, span_hi: float,
                    rng: np.random.Generator) -> float:
    """Distance between two random halves of one arm's respondents.

    Respondents are split without replacement (odd sizes drop one at
    random); both halves enter with equal weight, same metric as the
    human-vs-LLM distance.
    """
    values = np.asarray(values, dtype=float)
    perm = rng.permutation(len(values))
    half = len(values) // 2
    a = values[perm[:half]]
    b = values[perm[half:2 * half]]
    return weighted_dist(a, b, span_lo, span_hi)


def exp_mean(arm_dists: dict) -> float:
    """Equal-weight average of arm-level distances for one experiment.

    arm_dists maps arm name -> distance; every arm counts once (a shared
    control arm that serves two contrasts enters once, not twice).
    """
    vals = [v for v in arm_dists.values() if np.isfinite(v)]
    if not vals:
        return float("nan")
    return float(np.mean(vals))


def ecdf_points(samples: list, weights: list) -> tuple:
    """Weighted ECDF as plotting arrays (x sorted, y cumulative share)."""
    x = np.asarray(samples, dtype=float)
    w = np.asarray(weights, dtype=float)
    ok = np.isfinite(x)
    x, w = x[ok], w[ok]
    order = np.argsort(x)
    x = x[order]
    w = w[order] / w.sum()
    y = np.cumsum(w)
    # start the step plot at zero
    return np.concatenate(([x[0]], x)), np.concatenate(([0.0], y))
