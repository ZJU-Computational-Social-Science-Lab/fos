"""
Unit tests for ContagionScene as ExperimentScene subclass (Pipeline A).

Verifies initialization, agent placement, SEIR state assignment, run_round
execution, and inheritance. Uses mock LLM dialect to avoid external API calls.

Contains: test_instantiation, test_initialize_assigns_map_xy,
          test_initialize_marks_infected, test_run_round_completes,
          test_seir_states_change, test_is_experiment_scene_subclass
"""
import asyncio
import pytest

from fos.core.contagion.scene import ContagionScene
from fos.core.contagion.states import ContagionState
from fos.core.contagion.rules import StateTransition
from fos.core.experiment.scene import ExperimentScene
from fos.core.map.grid import GameMap


def _make_rules():
    """Build standard SEIR transition rules for tests."""
    return [
        StateTransition(
            from_state=ContagionState.SUSCEPTIBLE,
            to_state=ContagionState.INFECTED,
            trigger_type="proximity",
            probability=0.3,
        ),
        StateTransition(
            from_state=ContagionState.SUSCEPTIBLE,
            to_state=ContagionState.INFECTED,
            trigger_type="action",
            probability=0.5,
        ),
        StateTransition(
            from_state=ContagionState.INFECTED,
            to_state=ContagionState.RECOVERED,
            trigger_type="decay",
            probability=1.0,
            decay_turns=2,
        ),
    ]


def _make_scene(initial_infected=1):
    """Create a ContagionScene with a 5x5 grid and standard rules."""
    return ContagionScene(
        name="test_contagion",
        initial_event="A virus spreads.",
        game_map=GameMap(width=5, height=5),
        rules=_make_rules(),
        initial_infected_count=initial_infected,
    )


def _mock_llm_client():
    """Create a mock LLM client using the 'mock' dialect."""
    from fos.core.llm_config import LLMConfig
    from fos.core.llm.client import LLMClient
    config = LLMConfig(dialect="mock", model="test")
    return LLMClient(config)


def _init_with_agents(scene, agent_names=("Alice", "Bob", "Carol")):
    """Initialize scene with agents via mock LLM."""
    scene.config.agents = [
        {"name": name, "properties": {}, "role_prompt": f"You are {name}."}
        for name in agent_names
    ]
    scene.initialize(_mock_llm_client())
    return scene


# --- Tests ---


def test_instantiation():
    """ContagionScene can be instantiated with a GameMap and rules."""
    scene = _make_scene()
    assert scene.game_map.width == 5
    assert scene.game_map.height == 5
    assert len(scene.rules) == 3
    assert scene.initial_infected_count == 1


def test_initialize_assigns_map_xy():
    """initialize() assigns map_xy to all agents."""
    scene = _init_with_agents(_make_scene())
    for agent in scene.agents:
        xy = agent.properties["map_xy"]
        assert isinstance(xy, list)
        assert 0 <= xy[0] < 5
        assert 0 <= xy[1] < 5


def test_initialize_marks_infected():
    """initialize() marks initial_infected_count agents as infected."""
    scene = _init_with_agents(_make_scene(initial_infected=2))
    infected_count = sum(
        1 for a in scene.agents
        if a.properties.get("contagion_state") == "infected"
    )
    assert infected_count == 2
    for a in scene.agents:
        assert "contagion_turns" in a.properties
        assert "contagion_state" in a.properties


def test_run_round_completes():
    """run_round() completes and returns a RoundResult."""
    scene = _init_with_agents(_make_scene())
    events = []

    async def _run():
        return await scene.run_round(lambda t, d: events.append((t, d)))

    result = asyncio.get_event_loop().run_until_complete(_run())
    assert result is not None
    assert len(result.actions) == 3  # One per agent
    assert any(e[0] == "contagion_stats" for e in events)


def test_seir_states_change():
    """SEIR states change after rounds with infected agents present.

    With 3 agents in a 5x5 grid and 1 infected, decay_turns=2,
    after 2 rounds the infected agent should recover.
    """
    scene = _init_with_agents(_make_scene(initial_infected=1))
    # Find the infected agent and place all agents adjacent for proximity check
    infected = next(
        a for a in scene.agents
        if a.properties["contagion_state"] == "infected"
    )
    infected.properties["map_xy"] = [2, 2]
    for i, agent in enumerate(scene.agents):
        if agent is not infected:
            agent.properties["map_xy"] = [2 + (i % 2), 3]

    async def _run():
        return await scene.run_round(lambda t, d: None)

    # Run 2 rounds to trigger decay recovery (decay_turns=2)
    asyncio.get_event_loop().run_until_complete(_run())
    asyncio.get_event_loop().run_until_complete(_run())

    stats = scene.get_statistics()["counts"]
    # After 2 rounds, the infected agent should have recovered
    assert stats.get("recovered", 0) >= 1


def test_is_experiment_scene_subclass():
    """ContagionScene is a subclass of ExperimentScene."""
    assert issubclass(ContagionScene, ExperimentScene)
    scene = _make_scene()
    assert isinstance(scene, ExperimentScene)
