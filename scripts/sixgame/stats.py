"""Statistics helpers for the sixgame analysis.

Plain-language summary of what each function does:

- ``bootstrap_ci``: a bootstrap confidence interval.  We resample the
  data (whole personas at a time, so repeated draws from the same
  persona stay together) many times and report the interval that covers
  the middle of the resampled estimates.
- ``tost_equivalent``: the two one-sided tests equivalence check.  It
  answers "is the number we measured close enough to zero that we can
  call it practically equivalent?", by asking whether the whole
  confidence interval lies inside (-delta, +delta).
- ``tvd``: total variation distance between two choice distributions
  (the largest disagreement, from 0 = identical to 1 = no overlap).
- ``cluster_mean_stat``: the pessimistic (cluster-mean) estimate of a
  share: average each persona first, then average the personas.
"""

from __future__ import annotations

import random
from typing import Callable, Sequence


def bootstrap_ci(
    clusters: Sequence[Sequence[float]],
    stat: Callable[[list[list[float]]], float],
    confidence: float = 0.90,
    n_boot: int = 10_000,
    seed: int = 0,
) -> tuple[float, float, float]:
    """A cluster-bootstrap CI for `stat` over persona-level clusters.

    clusters[i] holds every draw belonging to persona i.  Each bootstrap
    replicate resamples personas with replacement (B times, seeded, so a
    rerun reproduces the interval exactly) and returns
    (point_estimate, ci_low, ci_high).
    """
    clusters = [list(c) for c in clusters if len(c) > 0]
    point = stat(clusters)
    if not clusters:
        return point, point, point
    rng = random.Random(seed)
    reps: list[float] = []
    for _ in range(n_boot):
        sample = [
            list(clusters[rng.randrange(len(clusters))]) for _ in range(len(clusters))
        ]
        reps.append(stat(sample))
    alpha = (1.0 - confidence) / 2.0
    reps.sort()
    low = reps[max(0, int(alpha * n_boot))]
    high = reps[min(n_boot - 1, int((1 - alpha) * n_boot) - 1)]
    return point, low, high


def share_of(clusters: list[list[float]], target: float) -> float:
    """The pooled share of draws equal to `target` across all clusters."""
    total = sum(len(c) for c in clusters)
    if total == 0:
        return 0.0
    return sum(1 for c in clusters for v in c if v == target) / total


def cluster_mean_share(clusters: list[list[float]], target: float) -> float:
    """The pessimistic estimate: per-persona shares, then averaged."""
    if not clusters:
        return 0.0
    return sum(share_of([c], target) for c in clusters) / len(clusters)


def tost_equivalent(low: float, high: float, delta: float) -> bool:
    """TOST: equivalent iff the whole 90% CI lies inside (-delta, +delta)."""
    return low > -delta and high < delta


def tvd(pmf_a: dict | Sequence[float], pmf_b: dict | Sequence[float]) -> float:
    """Total variation distance between two distributions (0..1).

    Inputs are either equal-length share lists or {category: share}
    dicts (missing categories count as zero).
    """
    if isinstance(pmf_a, dict) or isinstance(pmf_b, dict):
        a = pmf_a if isinstance(pmf_a, dict) else dict(enumerate(pmf_a))
        b = pmf_b if isinstance(pmf_b, dict) else dict(enumerate(pmf_b))
        keys = set(a) | set(b)
        return 0.5 * sum(abs(a.get(k, 0.0) - b.get(k, 0.0)) for k in keys)
    return 0.5 * sum(abs(x - y) for x, y in zip(pmf_a, pmf_b))


def se_of_share(share: float, n: int) -> float:
    """The standard error of a share from n independent observations."""
    if n <= 0:
        return 0.0
    return (share * (1.0 - share) / n) ** 0.5
