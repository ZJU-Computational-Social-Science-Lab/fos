"""
ContagionScene - standalone Pipeline A scene for SEIR contagion dynamics.

Manages agent contagion states (S, E, I, R), evaluates decay and proximity
transmission rules each turn, and emits statistics to the frontend. Does not
inherit from any Pipeline B base class.

Contains: ContagionScene
"""
import random
from typing import Dict, List, Optional, Tuple

from fos.core.contagion.states import ContagionState
from fos.core.contagion.rules import StateTransition, check_probability
from fos.core.contagion.statistics import ContagionStatistics, TransitionEvent
from fos.core.contagion.actions import MoveAdjacentAction, SpeakToAction
from fos.core.map.grid import GameMap


class ContagionScene:
    """Standalone scene with SEIR contagion state tracking.

    Does not inherit from any Pipeline B base class.

    Attributes:
        name: Scene name
        initial_event: Initial event message for agents
        game_map: Grid for agent positioning
        rules: List of StateTransition rules defining allowed transitions
        initial_infected_count: Number of agents to start as infected
        _statistics: Internal tracker for state counts and events
        _current_simulator: Runtime reference for adjacent agent queries
    """

    TYPE = "contagion_scene"

    def __init__(
        self,
        name: str,
        initial_event: str,
        game_map: GameMap,
        rules: List[StateTransition],
        initial_infected_count: int = 1,
    ):
        self.name = name
        self.initial_event = initial_event
        self.game_map = game_map
        self.rules = rules
        self.initial_infected_count = initial_infected_count
        self._statistics = ContagionStatistics()
        self._current_simulator: Optional["Simulator"] = None

    def pre_run(self, simulator: "Simulator"):
        """Initialize agent contagion states before simulation starts."""
        self._current_simulator = simulator

        agents = list(simulator.agents.values())
        agent_names = [a.name for a in agents]

        infected_names: set = set()
        if agent_names:
            count = min(self.initial_infected_count, len(agent_names))
            infected_names = set(random.sample(agent_names, count))

        for agent in agents:
            if agent.name in infected_names:
                agent.properties["contagion_state"] = ContagionState.INFECTED.value
            else:
                agent.properties["contagion_state"] = ContagionState.SUSCEPTIBLE.value
            agent.properties["contagion_turns"] = 0

        self._update_statistics(simulator)

    def pre_turn_rules(self, simulator: "Simulator"):
        """Evaluate decay and proximity rules for all agents before they act."""
        for agent in simulator.agents.values():
            agent.properties["contagion_turns"] = agent.properties.get("contagion_turns", 0) + 1

        for agent in simulator.agents.values():
            self._evaluate_decay_rules(agent, simulator)

        self._evaluate_proximity_rules(simulator)
        self._update_statistics(simulator)

    def _evaluate_decay_rules(self, agent: "Agent", simulator: "Simulator"):
        """Check if any decay rules apply and apply the first matching one."""
        current_state = agent.properties.get("contagion_state", "")
        turns = agent.properties.get("contagion_turns", 0)

        for rule in self.rules:
            if rule.trigger_type != "decay":
                continue
            if rule.from_state.value == current_state and turns >= rule.decay_turns:
                self._apply_transition(agent, rule, simulator)
                break  # Only one transition per turn

    def _apply_transition(
        self,
        agent: "Agent",
        rule: StateTransition,
        simulator: "Simulator",
        source_agent_id: Optional[str] = None,
    ):
        """Apply a state transition: update agent properties and record event."""
        from_state = agent.properties.get("contagion_state", "")
        agent.properties["contagion_state"] = rule.to_state.value
        agent.properties["contagion_turns"] = 0

        event = TransitionEvent(
            turn=simulator.turns,
            agent_id=agent.name,
            from_state=from_state,
            to_state=rule.to_state.value,
            trigger_type=rule.trigger_type,
            source_agent_id=source_agent_id,
        )
        self._statistics.record_transition(event)

    def _evaluate_proximity_rules(self, simulator: "Simulator"):
        """Evaluate proximity-based transmission for all adjacent agent pairs."""
        position_to_agent: Dict[Tuple[int, int], "Agent"] = {}
        for agent in simulator.agents.values():
            xy = agent.properties.get("map_xy")
            if xy:
                position_to_agent[(xy[0], xy[1])] = agent

        transitioned_this_turn: set = set()

        for agent in simulator.agents.values():
            xy = agent.properties.get("map_xy")
            if not xy or agent.name in transitioned_this_turn:
                continue

            agent_state = agent.properties.get("contagion_state", "")

            for neighbor_xy in self.get_moore_neighbors(xy[0], xy[1]):
                neighbor = position_to_agent.get(neighbor_xy)
                if not neighbor or neighbor.name in transitioned_this_turn:
                    continue

                neighbor_state = neighbor.properties.get("contagion_state", "")

                if self._check_proximity_transmission(
                    agent_state, neighbor_state, agent, neighbor,
                    simulator, transitioned_this_turn,
                ):
                    break

                if self._check_proximity_transmission(
                    neighbor_state, agent_state, neighbor, agent,
                    simulator, transitioned_this_turn,
                ):
                    break

    def _check_proximity_transmission(
        self,
        source_state: str,
        target_state: str,
        source_agent: "Agent",
        target_agent: "Agent",
        simulator: "Simulator",
        transitioned_set: set,
    ) -> bool:
        """Return True and apply transition if proximity transmission occurs."""
        if target_agent.name in transitioned_set:
            return False

        for rule in self.rules:
            if rule.trigger_type != "proximity":
                continue
            if rule.from_state.value == target_state and check_probability(rule.probability):
                self._apply_transition(
                    target_agent, rule, simulator,
                    source_agent_id=source_agent.name,
                )
                transitioned_set.add(target_agent.name)
                return True

        return False

    def _update_statistics(self, simulator: "Simulator"):
        """Recount states and emit contagion_stats event to frontend."""
        self._statistics.update(simulator.agents)
        simulator.emit_event_later(
            "contagion_stats",
            {
                "counts": self._statistics.counts,
                "agent_states": self._statistics.get_agent_states(simulator.agents),
            },
        )

    def get_moore_neighbors(self, x: int, y: int) -> List[Tuple[int, int]]:
        """Return all valid 8-directional (Moore) neighbor coordinates."""
        neighbors = []
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if self.game_map.in_bounds(nx, ny):
                    neighbors.append((nx, ny))
        return neighbors

    def get_adjacent_agents(self, agent_name: str, simulator: "Simulator") -> List[str]:
        """Return names of agents in Moore-adjacent cells to the named agent."""
        agent = simulator.agents.get(agent_name)
        if not agent:
            return []
        xy = agent.properties.get("map_xy")
        if not xy:
            return []

        neighbor_coords = set(self.get_moore_neighbors(xy[0], xy[1]))
        return [
            other_name
            for other_name, other_agent in simulator.agents.items()
            if other_name != agent_name
            and other_agent.properties.get("map_xy")
            and (other_agent.properties["map_xy"][0], other_agent.properties["map_xy"][1]) in neighbor_coords
        ]

    def get_scene_actions(self, agent: "Agent"):
        """Return contagion-specific actions available to the agent."""
        return [MoveAdjacentAction(), SpeakToAction()]

    def check_action_transmission(self, sender: "Agent", target: "Agent", simulator: "Simulator"):
        """Check if action-directed transmission occurs. Implements ACT-01/ACT-02."""
        sender_state = sender.properties.get("contagion_state", "")

        for rule in self.rules:
            if rule.trigger_type != "action" or rule.from_state.value != sender_state:
                continue
            if check_probability(rule.probability):
                self._apply_transition(target, rule, simulator, source_agent_id=sender.name)
                break  # First-match-wins

    def get_agent_status_prompt(self, agent: "Agent") -> str:
        """Return position and contagion state. Implements HIDE-02: neighbors show names only."""
        xy = agent.properties.get("map_xy") or [None, None]
        loc = None
        if xy[0] is not None:
            loc = self.game_map.get_location_at(xy[0], xy[1])
        loc_name = loc.name if loc else agent.properties.get("map_position", "?")

        contagion_state = agent.properties.get("contagion_state", "unknown")
        contagion_turns = agent.properties.get("contagion_turns", 0)

        lines = [
            "--- Status ---",
            f"Current position: {loc_name} at ({xy[0]},{xy[1]})",
            f"Contagion state: {contagion_state.upper()}",
        ]
        if contagion_state != "susceptible":
            lines.append(f"Turns in state: {contagion_turns}")

        if self._current_simulator:
            adjacent = self.get_adjacent_agents(agent.name, self._current_simulator)
            lines.append(f"Nearby agents: {', '.join(adjacent)}" if adjacent else "Nearby agents: None")

        return "\n".join(lines) + "\n"

    def serialize_config(self) -> dict:
        """Serialize scene configuration for persistence."""
        return {
            "name": self.name,
            "initial_event": self.initial_event,
            "game_map": self.game_map.serialize(),
            "rules": [
                {
                    "from_state": rule.from_state.value,
                    "to_state": rule.to_state.value,
                    "trigger_type": rule.trigger_type,
                    "probability": rule.probability,
                    "decay_turns": rule.decay_turns,
                }
                for rule in self.rules
            ],
            "initial_infected_count": self.initial_infected_count,
        }

    @classmethod
    def deserialize_config(cls, config: dict) -> dict:
        """Parse a configuration dict into constructor kwargs."""
        game_map = GameMap.deserialize(config.get("game_map") or {})

        rules = []
        for rule_data in config.get("rules", []):
            rules.append(StateTransition(
                from_state=ContagionState(rule_data["from_state"]),
                to_state=ContagionState(rule_data["to_state"]),
                trigger_type=rule_data["trigger_type"],
                probability=rule_data["probability"],
                decay_turns=rule_data.get("decay_turns"),
            ))

        return {
            "name": config.get("name", ""),
            "initial_event": config.get("initial_event", ""),
            "game_map": game_map,
            "rules": rules,
            "initial_infected_count": config.get("initial_infected_count", 1),
        }
