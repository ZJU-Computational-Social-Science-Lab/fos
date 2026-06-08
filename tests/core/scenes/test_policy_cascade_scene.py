"""This file checks that the old policy cascade scene can be copied safely.

The tests make sure saved scene data comes back as the same kind of scene.
"""

from fos.core.scenes.policy_cascade import PolicyCascadeScene


class FakeAgent:
    """A small agent used to test scene tier movement."""

    def __init__(self, name: str, tier: str) -> None:
        self.name = name
        self.properties = {"tier": tier}
        self.role_prompt = ""
        self.user_profile = ""
        self.feedback: list[str] = []

    def add_env_feedback(self, message: str) -> None:
        self.feedback.append(message)


class FakeSimulator:
    """A small simulator used to capture scene events."""

    def __init__(self, agents: list[FakeAgent]) -> None:
        self.agents = {agent.name: agent for agent in agents}
        self.events: list[tuple[str, dict]] = []

    def emit_event(self, event_type: str, data: dict) -> None:
        self.events.append((event_type, data))


def test_policy_cascade_scene_deserialize_keeps_scene_type() -> None:
    """A copied policy cascade scene is still a policy cascade scene."""
    scene = PolicyCascadeScene(
        name="policy erosion",
        initial_event="Share the new policy carefully.",
        tier_order=["top", "middle", "street"],
    )
    scene.state["latest_policy"] = "Protect the original policy meaning."

    cloned = PolicyCascadeScene.deserialize(scene.serialize())

    assert isinstance(cloned, PolicyCascadeScene)
    assert cloned.TYPE == "policy_cascade_scene"
    assert cloned.name == scene.name
    assert cloned.initial_event == scene.initial_event
    assert cloned.state == scene.state
    assert cloned.tier_order == ["top", "middle", "street"]
    assert cloned._tier_map == {}
    assert cloned._agents_by_tier == {"top": [], "middle": [], "street": []}


def test_notice_phase_does_not_call_full_network_a_dead_end() -> None:
    """A notice can move to the next tier without being a cascade dead end."""
    agents = [
        FakeAgent("Agent 1", "top"),
        FakeAgent("Agent 2", "mid"),
        FakeAgent("Agent 3", "low"),
    ]
    simulator = FakeSimulator(agents)
    scene = PolicyCascadeScene(
        name="policy erosion",
        initial_event="Initial policy background.",
        tier_order=["top", "mid", "low"],
    )
    scene.state["social_network"] = {
        "Agent 1": ["Agent 2", "Agent 3"],
        "Agent 2": ["Agent 1", "Agent 3"],
        "Agent 3": ["Agent 1", "Agent 2"],
    }
    scene.set_simulator(simulator)

    scene.post_turn(agents[0], simulator)

    event_types = [event_type for event_type, _data in simulator.events]
    assert "cascade_network_dead_end" not in event_types
    assert scene.state["current_tier_idx"] == 1
    assert scene.state["complete"] is False
