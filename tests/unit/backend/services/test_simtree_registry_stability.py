"""
This file checks that cached simulations can be cleaned up safely.

Each test verifies one thing:
- test_registry_evicts_only_idle_records checks idle trees are removed while active trees stay.
- test_registry_remove_cleans_runtime_resources checks removing a tree stops child resources.
- test_registry_metrics_include_tree_node_count checks health metrics can spot tree growth.
"""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from fos.backend.services import simtree_runtime
from fos.backend.services.simtree_runtime import SimTreeRecord, SimTreeRegistry


class FakeTree:
    """Small test tree that records cleanup calls."""

    def __init__(self, node_count: int = 1) -> None:
        self.nodes = {index: {"sim": SimpleNamespace()} for index in range(node_count)}
        self.cleaned = False
        self.loop = None
        self.broadcast = None

    def attach_event_loop(self, loop) -> None:
        self.loop = loop

    def set_tree_broadcast(self, broadcast) -> None:
        self.broadcast = broadcast

    def serialize(self) -> dict:
        return {"nodes": list(self.nodes)}

    def cleanup_runtime_resources(self) -> None:
        self.cleaned = True


def test_registry_evicts_only_idle_records() -> None:
    registry = SimTreeRegistry()
    idle = SimTreeRecord(FakeTree())
    active = SimTreeRecord(FakeTree())
    subscribed = SimTreeRecord(FakeTree())

    now = time.monotonic()
    idle.last_accessed_at = now - 120
    active.last_accessed_at = now - 120
    active.running.add(0)
    subscribed.last_accessed_at = now - 120
    subscribed.subs.append(object())
    registry._records = {
        "IDLE": idle,
        "ACTIVE": active,
        "SUBSCRIBED": subscribed,
    }

    evicted = registry.evict_idle_records(idle_ttl_seconds=60, now=now)

    assert evicted == ["IDLE"]
    assert "IDLE" not in registry._records
    assert "ACTIVE" in registry._records
    assert "SUBSCRIBED" in registry._records
    assert idle.tree.cleaned is True
    assert active.tree.cleaned is False


def test_registry_remove_cleans_runtime_resources() -> None:
    registry = SimTreeRegistry()
    tree = FakeTree()
    registry._records = {"SIM": SimTreeRecord(tree)}

    registry.remove("sim")

    assert tree.cleaned is True
    assert registry.get("SIM") is None


def test_registry_metrics_include_tree_node_count() -> None:
    registry = SimTreeRegistry()
    registry._records = {"SIM": SimTreeRecord(FakeTree(node_count=3))}

    metrics = registry.metrics()

    assert metrics["active_simulations"] == 1
    assert metrics["tree_nodes"] == 3


@pytest.mark.asyncio
async def test_registry_rebuilds_policy_erosion_records_instead_of_rehydrating_bad_runtime(
    monkeypatch,
) -> None:
    registry = SimTreeRegistry()
    rebuilt_tree = FakeTree()

    def _raise_if_deserialized(*args, **kwargs):
        raise AssertionError("policy_erosion should rebuild instead of deserializing latest_state")

    monkeypatch.setattr(simtree_runtime.SimTree, "deserialize", _raise_if_deserialized)
    monkeypatch.setattr(simtree_runtime, "_build_tree_for_sim", lambda *args, **kwargs: rebuilt_tree)

    record = await registry.get_or_create_from_sim(
        SimpleNamespace(
            id="POLICY",
            scene_type="policy_cascade_experiment",
            latest_state={"scene": {"config": {"type": "policy_cascade_experiment"}}},
            scene_config={"scenario_id": "policy_erosion"},
        ),
        clients={},
    )

    assert record.tree is rebuilt_tree
