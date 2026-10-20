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
- ``js_divergence_bits``: Jensen-Shannon divergence in bits (base 2,
  so it can never exceed 1) between two choice distributions.
- ``cluster_tvd_ci``: a cluster-bootstrap confidence interval for the
  TVD between a canonical and a transformed distribution, where whole
  personas are resampled (the SAME persona indices for both sides —
  the paired 5-persona design) and the interval covers the middle of
  the resampled TVDs.  Also reports n_eff, how many effectively
  independent personas the interval rests on.
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


def require_ci_label(label: str, kind: str) -> None:
    """Structural CI-label hygiene (TASK-2755 SPEC §3): refuses any
    attempt to attach a CI under a label that does not name its kind, so
    a discrepancy CI can never masquerade as a model effect CI (or the
    reverse).  Raises AssertionError on mismatch."""
    expected = f"{kind}_ci90"
    assert label == expected, (
        f"CI label '{label}' does not match its kind '{kind}' "
        f"(expected '{expected}')"
    )


def se_of_share(share: float, n: int) -> float:
    """The standard error of a share from n independent observations."""
    if n <= 0:
        return 0.0
    return (share * (1.0 - share) / n) ** 0.5


def js_divergence_bits(
    pmf_a: dict | Sequence[float], pmf_b: dict | Sequence[float]
) -> float:
    """Jensen-Shannon divergence in bits (base 2, bounded by 1).

    Inputs are {category: share} dicts or equal-length share lists.
    Missing categories count as zero.  Identical inputs give 0.0.
    """
    import math

    a = dict(pmf_a) if isinstance(pmf_a, dict) else dict(enumerate(pmf_a))
    b = dict(pmf_b) if isinstance(pmf_b, dict) else dict(enumerate(pmf_b))
    total_a, total_b = sum(a.values()) or 1.0, sum(b.values()) or 1.0
    js = 0.0
    for k in set(a) | set(b):
        pa, pb = a.get(k, 0.0) / total_a, b.get(k, 0.0) / total_b
        m = (pa + pb) / 2.0
        for p in (pa, pb):
            if p > 0 and m > 0:
                js += 0.5 * p * math.log2(p / m)
    return js


def tvd_of_outcomes(
    outcomes_a: list, outcomes_b: list, support: Sequence | None = None
) -> float:
    """TVD between the empirical distributions of two outcome lists.

    Every distinct value seen in either list is a category (missing
    counts as zero), unless an explicit support is given.
    """
    if support is None:
        support = set(outcomes_a) | set(outcomes_b)
    n_a, n_b = len(outcomes_a) or 1, len(outcomes_b) or 1
    counts_a: dict = {}
    counts_b: dict = {}
    for v in outcomes_a:
        counts_a[v] = counts_a.get(v, 0) + 1
    for v in outcomes_b:
        counts_b[v] = counts_b.get(v, 0) + 1
    return 0.5 * sum(
        abs(counts_a.get(k, 0) / n_a - counts_b.get(k, 0) / n_b)
        for k in support
    )


def _kish_neff(sizes: Sequence[int]) -> float:
    """How many effectively independent clusters the data carry
    (Kish formula: the closer the cluster sizes are to equal, the
    closer n_eff is to the cluster count)."""
    if not sizes:
        return 0.0
    total = float(sum(sizes))
    return total * total / sum(float(s) ** 2 for s in sizes)


def cluster_tvd_ci(
    can_clusters: Sequence[Sequence[float]],
    tra_clusters: Sequence[Sequence[float]],
    confidence: float = 0.90,
    n_boot: int = 10_000,
    seed: int = 0,
) -> tuple[float, float, float, float]:
    """A paired cluster-bootstrap 90% CI for the TVD between a canonical
    and a transformed distribution.

    Each cluster is a persona's list of 1/0 hits for one category; the
    categories "hit" and "miss" form the support.  Each bootstrap
    replicate resamples PERSONA INDICES ONCE and uses the same indices
    for both sides (the paired 5-persona design — the same personas
    played canonical and transformed).  Returns
    (point_estimate, ci_low, ci_high, n_eff).
    """
    can = [list(c) for c in can_clusters if len(c) > 0]
    tra = [list(c) for c in tra_clusters if len(c) > 0]
    n_pairs = min(len(can), len(tra))
    can_flat = [v for c in can for v in c]
    tra_flat = [v for c in tra for v in c]
    point = tvd_of_outcomes(can_flat, tra_flat, support=(1.0, 0.0))
    if n_pairs == 0:
        return point, point, point, 0.0
    rng = random.Random(seed)
    reps: list[float] = []
    for _ in range(n_boot):
        idx = [rng.randrange(n_pairs) for _ in range(n_pairs)]
        c_rep = [v for i in idx for v in can[i]]
        t_rep = [v for i in idx for v in tra[i]]
        reps.append(tvd_of_outcomes(c_rep, t_rep, support=(1.0, 0.0)))
    alpha = (1.0 - confidence) / 2.0
    reps.sort()
    low = reps[max(0, int(alpha * n_boot))]
    high = reps[min(n_boot - 1, int((1 - alpha) * n_boot) - 1)]
    return point, low, high, _kish_neff([len(c) for c in can])
