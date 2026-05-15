"""
Unit tests for ContagionScene after Pipeline A rewrite.

Uses a lightweight FakeSimulator stub instead of Pipeline B's Simulator.
Tests initialization, decay rules, proximity transmission, and serialization.

Contains: TestContagionSceneInit, TestContagionSceneDecay,
          TestContagionSceneProximity, TestContagionSceneSerialization
"""
import pytest
from fos.core.contagion.scene import ContagionScene
from fos.core.contagion.states import ContagionState
from fos.core.contagion.rules import StateTransition
from fos.core.map.grid import GameMap


# ---------------------------------------------------------------------------
# Test infrastructure
# ---------------------------------------------------------------------------

class FakeAgent:
    """Minimal agent stub for ContagionScene tests."""
    def __init__(self, name: str, xy=None):
        self.name = name
        self.properties = {}
        if xy:
            self.properties["map_xy"] = list(xy)


class FakeSimulator:
    """Minimal simulator stub for ContagionScene tests."""
    def __init__(self, agents: list):
        self.agents = {a.name: a for a in agents}
        self.turns = 0
        self.events = []

    def emit_event_later(self, event_type: str, data: dict):
        self.events.append({"type": event_type, "data": data})


def _make_scene(width=5, height=5, initial_infected=1, rules=None) -> ContagionScene:
    game_map = GameMap(width=width, height=height)
    if rules is None:
        rules = [
            StateTransition(
                from_state=ContagionState.INFECTED,
                to_state=ContagionState.RECOVERED,
                trigger_type="decay",
                probability=1.0,
                decay_turns=3,
            ),
            StateTransition(
                from_state=ContagionState.SUSCEPTIBLE,
                to_state=ContagionState.INFECTED,
                trigger_type="proximity",
                probability=1.0,
            ),
        ]
    return ContagionScene(
        name="test",
        initial_event="start",
        game_map=game_map,
        rules=rules,
        initial_infected_count=initial_infected,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestContagionSceneInit:

    def test_does_not_inherit_pipeline_b(self):
        scene = _make_scene()
        mro_names = [c.__name__ for c in type(scene).__mro__]
        assert "VillageScene" not in mro_names
        assert "Scene" not in mro_names

    def test_type_attribute(self):
        assert ContagionScene.TYPE == "contagion_scene"

    def test_pre_run_sets_one_infected(self):
        agents = [FakeAgent(f"A{i}") for i in range(5)]
        sim = FakeSimulator(agents)
        scene = _make_scene(initial_infected=1)
        scene.pre_run(sim)

        infected = [
            a for a in agents
            if a.properties.get("contagion_state") == ContagionState.INFECTED.value
        ]
        assert len(infected) == 1

    def test_pre_run_sets_remaining_susceptible(self):
        agents = [FakeAgent(f"A{i}") for i in range(5)]
        sim = FakeSimulator(agents)
        scene = _make_scene(initial_infected=1)
        scene.pre_run(sim)

        susceptible = [
            a for a in agents
            if a.properties.get("contagion_state") == ContagionState.SUSCEPTIBLE.value
        ]
        assert len(susceptible) == 4

    def test_pre_run_initializes_contagion_turns_to_zero(self):
        agents = [FakeAgent("A")]
        sim = FakeSimulator(agents)
        scene = _make_scene(initial_infected=1)
        scene.pre_run(sim)
        assert agents[0].properties["contagion_turns"] == 0

    def test_pre_run_emits_stats_event(self):
        agents = [FakeAgent("A")]
        sim = FakeSimulator(agents)
        scene = _make_scene(initial_infected=1)
        scene.pre_run(sim)
        assert any(e["type"] == "contagion_stats" for e in sim.events)


class TestContagionSceneDecay:

    def test_decay_rule_transitions_after_enough_turns(self):
        agent = FakeAgent("A")
        sim = FakeSimulator([agent])

        scene = _make_scene(rules=[
            StateTransition(
                from_state=ContagionState.INFECTED,
                to_state=ContagionState.RECOVERED,
                trigger_type="decay",
                probability=1.0,
                decay_turns=2,
            )
        ])
        agent.properties["contagion_state"] = ContagionState.INFECTED.value
        agent.properties["contagion_turns"] = 2  # exactly at threshold

        scene._evaluate_decay_rules(agent, sim)
        assert agent.properties["contagion_state"] == ContagionState.RECOVERED.value

    def test_decay_rule_does_not_fire_before_enough_turns(self):
        agent = FakeAgent("A")
        sim = FakeSimulator([agent])

        scene = _make_scene(rules=[
            StateTransition(
                from_state=ContagionState.INFECTED,
                to_state=ContagionState.RECOVERED,
                trigger_type="decay",
                probability=1.0,
                decay_turns=5,
            )
        ])
        agent.properties["contagion_state"] = ContagionState.INFECTED.value
        agent.properties["contagion_turns"] = 3

        scene._evaluate_decay_rules(agent, sim)
        assert agent.properties["contagion_state"] == ContagionState.INFECTED.value

    def test_decay_resets_contagion_turns(self):
        agent = FakeAgent("A")
        sim = FakeSimulator([agent])

        scene = _make_scene(rules=[
            StateTransition(
                from_state=ContagionState.INFECTED,
                to_state=ContagionState.RECOVERED,
                trigger_type="decay",
                probability=1.0,
                decay_turns=1,
            )
        ])
        agent.properties["contagion_state"] = ContagionState.INFECTED.value
        agent.properties["contagion_turns"] = 5

        scene._evaluate_decay_rules(agent, sim)
        assert agent.properties["contagion_turns"] == 0


class TestContagionSceneProximity:

    def test_proximity_rule_infects_adjacent_susceptible(self):
        # Infected at (0,0), Susceptible at (1,0)
        infected = FakeAgent("I", xy=(0, 0))
        infected.properties["contagion_state"] = ContagionState.INFECTED.value

        susceptible = FakeAgent("S", xy=(1, 0))
        susceptible.properties["contagion_state"] = ContagionState.SUSCEPTIBLE.value

        sim = FakeSimulator([infected, susceptible])

        scene = _make_scene(width=5, height=5, rules=[
            StateTransition(
                from_state=ContagionState.SUSCEPTIBLE,
                to_state=ContagionState.INFECTED,
                trigger_type="proximity",
                probability=1.0,
            )
        ])

        transitioned = set()
        scene._check_proximity_transmission(
            ContagionState.INFECTED.value,
            ContagionState.SUSCEPTIBLE.value,
            infected, susceptible, sim, transitioned,
        )
        assert susceptible.properties["contagion_state"] == ContagionState.INFECTED.value

    def test_no_chaining_within_turn(self):
        # Already-transitioned agent should not spread further in same turn
        infected = FakeAgent("I", xy=(0, 0))
        infected.properties["contagion_state"] = ContagionState.INFECTED.value

        susceptible = FakeAgent("S", xy=(1, 0))
        susceptible.properties["contagion_state"] = ContagionState.SUSCEPTIBLE.value

        sim = FakeSimulator([infected, susceptible])
        scene = _make_scene(rules=[
            StateTransition(
                from_state=ContagionState.SUSCEPTIBLE,
                to_state=ContagionState.INFECTED,
                trigger_type="proximity",
                probability=1.0,
            )
        ])

        # Mark susceptible agent as already transitioned this turn
        transitioned = {"S"}
        scene._check_proximity_transmission(
            ContagionState.INFECTED.value,
            ContagionState.SUSCEPTIBLE.value,
            infected, susceptible, sim, transitioned,
        )
        # State should be unchanged
        assert susceptible.properties["contagion_state"] == ContagionState.SUSCEPTIBLE.value


class TestContagionSceneSerialization:

    def test_serialize_config_round_trips(self):
        scene = _make_scene()
        config = scene.serialize_config()
        kwargs = ContagionScene.deserialize_config(config)

        restored = ContagionScene(**kwargs)
        assert restored.name == scene.name
        assert restored.initial_infected_count == scene.initial_infected_count
        assert len(restored.rules) == len(scene.rules)

    def test_serialize_includes_game_map(self):
        scene = _make_scene(width=10, height=8)
        config = scene.serialize_config()
        assert "game_map" in config
        assert config["game_map"]["width"] == 10
        assert config["game_map"]["height"] == 8

    def test_deserialize_reconstructs_rules(self):
        scene = _make_scene()
        config = scene.serialize_config()
        kwargs = ContagionScene.deserialize_config(config)

        restored = ContagionScene(**kwargs)
        original_types = {r.trigger_type for r in scene.rules}
        restored_types = {r.trigger_type for r in restored.rules}
        assert original_types == restored_types


class TestContagionSceneGetMooreNeighbors:

    def test_center_cell_has_eight_neighbors(self):
        scene = _make_scene(width=5, height=5)
        neighbors = scene.get_moore_neighbors(2, 2)
        assert len(neighbors) == 8

    def test_corner_cell_has_three_neighbors(self):
        scene = _make_scene(width=5, height=5)
        neighbors = scene.get_moore_neighbors(0, 0)
        assert len(neighbors) == 3

    def test_edge_cell_has_five_neighbors(self):
        scene = _make_scene(width=5, height=5)
        neighbors = scene.get_moore_neighbors(0, 2)
        assert len(neighbors) == 5

    def test_center_not_in_neighbors(self):
        scene = _make_scene(width=5, height=5)
        neighbors = scene.get_moore_neighbors(2, 2)
        assert (2, 2) not in neighbors
