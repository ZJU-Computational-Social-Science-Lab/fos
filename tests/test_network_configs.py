"""
This file checks the Holme-Kim network generator in the council scripts.

It makes sure the mean degree of a generated network stays the same no
matter how often triadic closure is used, and it checks both copies of the
generator (the plain runner and the preloaded runner) behave the same way.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from headless_council import _build_holme_kim_edges as build_holme_kim  # noqa: E402
from headless_council_preloaded import _build_holme_kim_edges as build_holme_kim_preloaded  # noqa: E402

_AGENT_NAMES = [f"agent_{index}" for index in range(100)]


def _mean_degree(edges: list[list[str]], n: int) -> float:
    """Mean degree of a network: twice the edge count divided by node count."""
    return 2.0 * len(edges) / n


@pytest.mark.parametrize(
    "build_edges",
    [build_holme_kim, build_holme_kim_preloaded],
    ids=["headless_council", "headless_council_preloaded"],
)
def test_mean_degree_does_not_depend_on_triad_probability(build_edges) -> None:
    """Mean degree must stay about 2*m whether triadic closure is rare or common."""
    degrees_rare: list[float] = []
    degrees_common: list[float] = []
    for seed in range(20):
        edges_rare, _ = build_edges(_AGENT_NAMES, seed=seed, m=3, p_triad=0.2)
        edges_common, _ = build_edges(_AGENT_NAMES, seed=seed, m=3, p_triad=0.8)
        degrees_rare.append(_mean_degree(edges_rare, len(_AGENT_NAMES)))
        degrees_common.append(_mean_degree(edges_common, len(_AGENT_NAMES)))

    mean_rare = sum(degrees_rare) / len(degrees_rare)
    mean_common = sum(degrees_common) / len(degrees_common)
    assert abs(mean_rare - mean_common) < 0.15
