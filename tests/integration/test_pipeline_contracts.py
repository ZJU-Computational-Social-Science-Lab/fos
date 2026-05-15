"""
Pipeline contract tests — verifies ExperimentScene fulfills its public API contract.

These tests check that the Pipeline A ExperimentScene produces results with the
required fields and emits events, without requiring a real LLM (uses mock dialect).

Contains: TestExperimentSceneContract
"""
import asyncio
import pytest
from fos.core.experiment.config import ExperimentConfig
from fos.core.experiment.scene import ExperimentScene
from fos.core.llm.client import LLMClient
from fos.core.llm_config import LLMConfig


def _mock_client():
    return LLMClient(LLMConfig(dialect="mock"))


def _make_scene(num_agents=2):
    config = ExperimentConfig(
        scenario_id="custom",
        agents=[
            {"name": f"Agent{i+1}", "properties": {}}
            for i in range(num_agents)
        ],
        actions=[
            {"name": "cooperate", "description": "Work together"},
            {"name": "defect", "description": "Act alone"},
        ],
    )
    scene = ExperimentScene(config)
    scene.initialize(_mock_client())
    return scene


def _run(scene):
    events = []
    def emitter(event_type, data):
        events.append({"type": event_type, "data": data})
    return asyncio.run(scene.run_round(emitter)), events


class TestExperimentSceneContract:

    def test_run_round_returns_result(self):
        scene = _make_scene()
        result, _ = _run(scene)
        assert result is not None

    def test_result_has_required_fields(self):
        scene = _make_scene()
        result, _ = _run(scene)
        assert hasattr(result, "round_num")
        assert hasattr(result, "actions")
        assert hasattr(result, "completed")
        assert isinstance(result.actions, list)

    def test_each_agent_produces_an_action(self):
        scene = _make_scene(num_agents=2)
        result, _ = _run(scene)
        assert len(result.actions) == 2

    def test_action_result_has_required_fields(self):
        scene = _make_scene(num_agents=2)
        result, _ = _run(scene)
        for action in result.actions:
            assert hasattr(action, "agent_name")
            assert hasattr(action, "action_name")
            assert action.agent_name in {"Agent1", "Agent2"}

    def test_multiple_rounds_increment_counter(self):
        scene = _make_scene()
        r1, _ = _run(scene)
        r2, _ = _run(scene)
        assert r2.round_num > r1.round_num

    def test_agents_accessible_after_initialize(self):
        scene = _make_scene(num_agents=3)
        assert hasattr(scene, "agents")
        assert len(scene.agents) == 3
        assert all(hasattr(a, "name") for a in scene.agents)

    def test_events_emitted_during_round(self):
        scene = _make_scene(num_agents=2)
        _, events = _run(scene)
        assert len(events) > 0
        assert all("type" in e for e in events)
