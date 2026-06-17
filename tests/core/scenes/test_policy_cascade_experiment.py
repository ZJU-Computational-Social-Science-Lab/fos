"""
Tests for PolicyCascadeExperimentScene scaffold and ExperimentAgent feedback.

Verifies import, MRO, feedback_buffer, _agents_dict, _SimulatorAdapter,
and configure_from_config.

Contains: test fixtures and 9 test functions.
"""
import asyncio
from unittest.mock import MagicMock


from fos.core.experiment.agent import ExperimentAgent
from fos.core.experiment.config import ExperimentConfig
from fos.core.experiment.scene import ExperimentScene
from fos.core.simtree import SimTree
from fos.backend.services.simtree_runtime import ExperimentRunnerAdapter
from fos.core.llm_config import LLMConfig
from fos.core.scenes.policy_cascade_experiment import (
    PolicyCascadeExperimentScene,
    _SimulatorAdapter,
)


def _make_config(**overrides):
    defaults = {
        "agents": [
            {"name": "Alice", "properties": {"tier": "high"}, "llm_config": {"dialect": "mock"}},
            {"name": "Bob", "properties": {"tier": "low"}, "llm_config": {"dialect": "mock"}},
        ],
        "actions": [],
        "parameters": {"tier_order": ["high", "low"]},
    }
    defaults.update(overrides)
    return ExperimentConfig(**defaults)


def _mock_llm_client():
    client = MagicMock()
    client.provider = MagicMock()
    client.provider.api_key = "test"
    client.provider.base_url = "http://test"
    return client


# Test 1: is ExperimentScene subclass
def test_is_experiment_scene_subclass():
    assert issubclass(PolicyCascadeExperimentScene, ExperimentScene)


# Test 2: has correct TYPE
def test_type_attribute():
    assert PolicyCascadeExperimentScene.TYPE == "policy_cascade_experiment"


# Test 3: add_env_feedback appends
def test_add_env_feedback_appends():
    agent = ExperimentAgent(name="X", properties={}, llm_config=LLMConfig(dialect="mock"))
    agent.add_env_feedback("error 1")
    agent.add_env_feedback("error 2")
    assert agent.feedback_buffer == ["error 1", "error 2"]


# Test 4: clear_feedback_buffer empties
def test_clear_feedback_buffer():
    agent = ExperimentAgent(name="X", properties={}, llm_config=LLMConfig(dialect="mock"))
    agent.add_env_feedback("msg")
    agent.clear_feedback_buffer()
    assert agent.feedback_buffer == []


# Test 5: get_feedback_text joins
def test_get_feedback_text():
    agent = ExperimentAgent(name="X", properties={}, llm_config=LLMConfig(dialect="mock"))
    assert agent.get_feedback_text() == ""
    agent.add_env_feedback("line 1")
    agent.add_env_feedback("line 2")
    assert agent.get_feedback_text() == "line 1\nline 2"


# Test 6: initialize builds _agents_dict
def test_initialize_builds_agents_dict():
    config = _make_config()
    scene = PolicyCascadeExperimentScene(config)
    scene.initialize(_mock_llm_client())
    assert "Alice" in scene._agents_dict
    assert "Bob" in scene._agents_dict
    assert scene._agents_dict["Alice"].name == "Alice"


# Test 7: _SimulatorAdapter.agents returns _agents_dict
def test_simulator_adapter_agents():
    config = _make_config()
    scene = PolicyCascadeExperimentScene(config)
    scene.initialize(_mock_llm_client())
    adapter = _SimulatorAdapter(scene)
    assert adapter.agents is scene._agents_dict


# Test 8: _SimulatorAdapter.turns returns _current_round
def test_simulator_adapter_turns():
    config = _make_config()
    scene = PolicyCascadeExperimentScene(config)
    scene._current_round = 5
    adapter = _SimulatorAdapter(scene)
    assert adapter.turns == 5


# Test 9: configure_from_config applies tier_order
def test_configure_from_config_tier_order():
    config = _make_config(parameters={"tier_order": ["high", "mid", "low"]})
    scene = PolicyCascadeExperimentScene(config)
    assert scene.tier_order == ["high", "mid", "low"]


def test_simtree_clone_preserves_policy_cascade_experiment_scene():
    config = _make_config(
        scenario_id="policy_cascade",
        parameters={"tier_order": ["high", "low"], "policy_text": "Policy A"},
    )
    scene = PolicyCascadeExperimentScene(config)
    adapter = ExperimentRunnerAdapter(scene, {"chat": _mock_llm_client()})

    tree = SimTree.new(adapter, adapter.clients)

    root_sim = tree.nodes[tree.root]["sim"]
    assert isinstance(root_sim.scene, PolicyCascadeExperimentScene)
    assert root_sim.scene.config.scenario_id == "policy_cascade"
    assert root_sim.scene.state["tier_order"] == ["high", "low"]


def test_extract_tier_accepts_frontend_localized_properties():
    config = _make_config(parameters={"tier_order": ["top", "mid", "low"]})
    scene = PolicyCascadeExperimentScene(config)

    localized_agent = ExperimentAgent(
        name="Localized",
        properties={"层级": "top"},
        llm_config=LLMConfig(dialect="mock"),
    )
    tier_level_agent = ExperimentAgent(
        name="TierLevel",
        properties={"tier_level": "low"},
        llm_config=LLMConfig(dialect="mock"),
    )

    assert scene._extract_tier(localized_agent) == "top"
    assert scene._extract_tier(tier_level_agent) == "low"


def test_extract_tier_prefers_localized_profile_over_stale_tier():
    config = _make_config(parameters={"tier_order": ["top", "mid", "low"]})
    scene = PolicyCascadeExperimentScene(config)
    conflicting_agent = ExperimentAgent(
        name="Conflicting",
        properties={"tier": "top", "层级": "mid"},
        llm_config=LLMConfig(dialect="mock"),
    )

    assert scene._extract_tier(conflicting_agent) == "mid"


def test_required_cascade_converts_yield_to_policy_message():
    config = _make_config(
        scenario_id="policy_cascade",
        actions=[
            {"name": "send_message", "description": "Send a message"},
            {"name": "yield", "description": "End your turn"},
        ],
        parameters={
            "tier_order": ["high", "low"],
            "policy_text": "Policy A must be passed downward.",
        },
    )
    scene = PolicyCascadeExperimentScene(config)
    client = _mock_llm_client()
    client.chat.return_value = '{"action":"yield"}'
    scene.initialize(client)

    result = asyncio.run(scene.run_round(lambda _type, _data: None))

    alice_action = next(action for action in result.actions if action.agent_name == "Alice")
    assert alice_action.action_name == "send_message"
    assert alice_action.skipped is False
    assert "Policy A must be passed downward." in alice_action.parameters["message"]
