"""Tests for showing runtime failures in the simulation tree.

This file checks that a node can keep its logs even when its simulator stops
with a runtime problem.
"""

from __future__ import annotations

import pytest

from fos.backend.services.simtree_advance import run_simulator_for_advance


class RuntimeFailingSimulator:
    """Small simulator that raises a runtime problem when it runs."""

    def __init__(self) -> None:
        self.run_calls = 0

    def run(self, max_turns: int = 1) -> None:
        self.run_calls += max_turns
        raise RuntimeError("missing gaworld api key")


@pytest.mark.asyncio
async def test_advance_runner_returns_runtime_error_for_log_hydration() -> None:
    """Advance runner returns runtime errors so the frontend can still hydrate logs."""
    simulator = RuntimeFailingSimulator()

    error = await run_simulator_for_advance(simulator, max_turns=1)

    assert isinstance(error, RuntimeError)
    assert str(error) == "missing gaworld api key"
    assert simulator.run_calls == 1
