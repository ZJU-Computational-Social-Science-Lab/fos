"""Minimal Pipeline B Scene base class.

Policy cascade uses this directly. Pending Pipeline A port.
See docs/plans/policy-cascade-port-investigation.md

Contains: Scene
"""

from fos.core.action_controller import ActionController
from fos.core.actions.base_actions import YieldAction
from fos.core.event import PublicEvent


# TODO: Port PolicyCascadeScene to Pipeline A (ExperimentScene
# subclass) and delete this file. See:
# docs/plans/policy-cascade-port-investigation.md


class Scene:
    """Minimal base class for Pipeline B scenes."""

    TYPE = "scene"

    def __init__(self, name, initial_event):
        self.name = name
        self.initial_event = PublicEvent(str(initial_event or ""))
        self.state = {"time": 1080}
        self.minutes_per_turn = 3
        self.action_controller = ActionController()

    def set_simulator(self, simulator):
        self._simulator = simulator

    def initialize_agent(self, agent) -> None:
        """Hook for legacy scenes to initialize per-agent state."""

    def get_scene_actions(self, agent) -> list:
        return [YieldAction()]

    def parse_and_handle_action(self, action_data, agent, simulator) -> tuple:
        raw_action = action_data.get("action") if isinstance(action_data, dict) else None
        if isinstance(raw_action, dict):
            action_name = raw_action.get("name") or raw_action.get("action")
            merged = {key: value for key, value in raw_action.items() if key != "name"}
            for key, value in action_data.items():
                if key != "action":
                    merged[key] = value
            merged["action"] = action_name
            action_data = merged
        else:
            action_name = raw_action

        action_name = str(action_name or "").strip()

        action_instance = None
        for action in getattr(agent, "action_space", []):
            if getattr(action, "NAME", action if isinstance(action, str) else None) == action_name:
                action_instance = action
                break

        if isinstance(action_instance, str):
            # Compatibility for old snapshots that serialized action names.
            from fos.core.registry import ACTION_SPACE_MAP

            action_instance = ACTION_SPACE_MAP.get(action_instance)

        allowed, error = self.action_controller.validate_action(
            action_name,
            action_data,
            agent,
            self.state,
            action_instance,
            self,
        )
        if not allowed:
            agent.add_env_feedback(error)
            return False, {"error": error}, f"{agent.name} action blocked: {error}", {}, False

        if action_instance:
            return action_instance.handle(action_data, agent, simulator, self)

        return False, {}, None, {}, False

    def deliver_message(self, event, sender, simulator) -> None:
        pass

    def post_turn(self, agent, simulator) -> None:
        current = int(self.state.get("time") or 0)
        self.state["time"] = current + int(getattr(self, "minutes_per_turn", 0) or 0)

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

    def serialize(self) -> dict:
        initial_event = (
            self.initial_event.content
            if isinstance(self.initial_event, PublicEvent)
            else str(self.initial_event or "")
        )
        return {
            "type": getattr(self, "TYPE", ""),
            "name": self.name,
            "initial_event": initial_event,
            "state": dict(self.state),
            "config": self.serialize_config(),
        }

    @classmethod
    def deserialize(cls, data: dict) -> "Scene":
        name = data.get("name", "")
        initial_event = data.get("initial_event", "")
        config = data.get("config", {})
        init_kwargs = cls.deserialize_config(config)
        scene = cls(name, initial_event, **init_kwargs)
        scene.state = dict(data.get("state", {}))
        if not hasattr(scene, "action_controller"):
            scene.action_controller = ActionController()
        return scene

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

    def get_agent_status_prompt(self, agent) -> str:
        return ""

    def log(self, msg) -> None:
        pass
