"""Tests for showing runtime failures in the simulation tree.

This file checks that a node can keep its logs even when its simulator stops
with a runtime problem.
"""

from __future__ import annotations

import pytest

from fos.backend.services.simtree_advance import (
    record_advance_runtime_failure,
    run_simulator_for_advance,
)


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


def test_record_advance_runtime_failure_adds_node_status_and_log() -> None:
    """Runtime failures are visible on the node and in its event logs."""
    simulator = RuntimeFailingSimulator()
    emitted: list[tuple[str, dict]] = []
    simulator.log_event = lambda event_type, data: emitted.append((event_type, data))  # type: ignore[attr-defined]
    node = {"logs": [], "meta": {}}

    message = record_advance_runtime_failure(
        node,
        simulator,
        RuntimeError("model not found"),
    )

    assert message == "model not found"
    assert node["meta"]["runtime_status"] == "failed"
    assert node["meta"]["runtime_error"] == "model not found"
    assert emitted == [
        (
            "run_failed",
            {"message": "model not found", "error_type": "RuntimeError"},
        )
    ]
