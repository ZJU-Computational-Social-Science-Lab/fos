"""Minimal Pipeline B Scene base class.

Policy cascade uses this directly. Pending Pipeline A port.
See docs/plans/policy-cascade-port-investigation.md

Contains: Scene
"""

# TODO: Port PolicyCascadeScene to Pipeline A (ExperimentScene
# subclass) and delete this file. See:
# docs/plans/policy-cascade-port-investigation.md


class Scene:
    """Minimal base class for Pipeline B scenes."""

    def __init__(self, name, initial_event):
        self.name = name
        self.initial_event = initial_event
        self.state = {}

    def set_simulator(self, simulator):
        self._simulator = simulator

    def get_scene_actions(self, agent) -> list:
        return []

    def parse_and_handle_action(self, action_data, agent, simulator) -> tuple:
        return False, {}, None, {}, False

    def deliver_message(self, event, sender, simulator) -> None:
        pass

    def post_turn(self, agent, simulator) -> None:
        pass

    def should_skip_turn(self, agent, simulator) -> bool:
        return False

    def should_extend_run(self, turns, max_turns) -> bool:
        return False

    def is_complete(self) -> bool:
        return False

    def serialize_config(self) -> dict:
        return {}

    @classmethod
    def deserialize_config(cls, data) -> dict:
        return {}

    def on_event(self, sim, event_type, data) -> None:
        pass

    def on_private_event(self, sim, event_type, data, recipients) -> None:
        pass

    def get_behavior_guidelines(self) -> str:
        return ""

    def get_output_format(self) -> str:
        return ""

    def get_examples(self) -> str:
        return ""

    def log(self, msg) -> None:
        pass
