"""
PolicyCascadeExperimentScene -- Pipeline A implementation of the
policy cascade scene.

Replaces the legacy PolicyCascadeScene (Pipeline B) with a scene
that uses ExperimentScene as its base, giving it the full Pipeline A
turn loop, structured JSON actions, and ExperimentAgent.

The mixin order mirrors the original PolicyCascadeScene to preserve
MRO-based method resolution.

Contains: PolicyCascadeExperimentScene, _SimulatorAdapter
"""
from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any, Callable, Dict, List, Optional

from fos.core.experiment.scene import ExperimentScene
from fos.core.experiment.config import ExperimentConfig
from fos.core.experiment.runner import ActionResult
from fos.core.experiment.state import ExperimentState
from fos.core.event import MessageEvent
from fos.core.scenes.policy_cascade.base import PolicyCascadeBaseMixin
from fos.core.scenes.policy_cascade.constants import _parse_tier_order, DEFAULT_TIER_ORDER
from fos.core.scenes.policy_cascade.distortion import PolicyCascadeDistortionMixin
from fos.core.scenes.policy_cascade.followup import PolicyCascadeFollowUpMixin
from fos.core.scenes.policy_cascade.messages import PolicyCascadeMessageMixin
from fos.core.scenes.policy_cascade.prompts import PolicyCascadePromptMixin
from fos.core.scenes.policy_cascade.runtime import PolicyCascadeRuntimeMixin
from fos.core.scenes.policy_cascade.state import PolicyCascadeStateMixin
from fos.core.scenes.policy_cascade.threads import PolicyCascadeThreadMixin

logger = logging.getLogger(__name__)


class _PipelineAActionTerminal:
    def parse_and_handle_action(self, action_data, agent, simulator):
        action_name = str(action_data.get("action") or "").strip()
        if action_name == "send_message":
            message = str(action_data.get("message") or "").strip()
            if not message:
                return False, {"error": "message required"}, "message required", {}, True
            self.deliver_message(MessageEvent(agent.name, message), agent, simulator)
            return True, {"message": message}, f"{agent.name} sent a message", {}, True
        if action_name == "yield":
            return True, {}, f"{agent.name} skipped", {}, True
        return False, {"error": f"unknown action: {action_name}"}, f"unknown action: {action_name}", {}, True


class PolicyCascadeExperimentScene(
    PolicyCascadeRuntimeMixin,
    PolicyCascadePromptMixin,
    PolicyCascadeMessageMixin,
    PolicyCascadeFollowUpMixin,
    PolicyCascadeThreadMixin,
    PolicyCascadeStateMixin,
    PolicyCascadeDistortionMixin,
    PolicyCascadeBaseMixin,
    _PipelineAActionTerminal,
    ExperimentScene,
):
    """Pipeline A implementation of the policy cascade scene.

    Uses ExperimentScene's turn loop (LLM prompting, JSON action
    parsing, structured results) while preserving all policy cascade
    domain logic from the mixin layer.

    Replaces simulator.agents with self._agents_dict (built from
    self.agents after initialize()). Replaces simulator.emit_event
    with self._emit (stored during run_round). Replaces
    simulator.broadcast with self._broadcast.
    """

    TYPE = "policy_cascade_experiment"

    def __init__(self, config: ExperimentConfig) -> None:
        # Extract initial_event from config parameters for state setup
        params = config.parameters or {}
        initial_event = str(
            params.get("initial_event")
            or params.get("policy_text")
            or config.description
            or ""
        )

        # Initialize ExperimentScene (stores config, sets up state)
        ExperimentScene.__init__(self, config)

        # Mixin methods expect self.state to be a plain dict (not
        # ExperimentState).  Keep the ExperimentState for the runner
        # but swap self.state to a dict for mixin compatibility.
        self._experiment_state = self.state
        self.state: Dict[str, Any] = {}

        # Inline PolicyCascadeBaseMixin state init (cannot call
        # PolicyCascadeBaseMixin.__init__ because its super() chain
        # passes (name, initial_event) to ExperimentScene.__init__(config)
        # which has an incompatible signature).
        self.tier_order = _parse_tier_order(
            params.get("tier_order") or DEFAULT_TIER_ORDER
        )
        self.state["current_tier_idx"] = 0
        self.state["tier_seen"] = {t: [] for t in self.tier_order}
        self.state["tier_transmitted"] = {t: False for t in self.tier_order}
        self.state["tier_order"] = list(self.tier_order)
        self.state["latest_policy"] = ""
        self.state["source_policy"] = ""
        self.state["relayed_policy"] = ""
        self.state["latest_notice"] = str(initial_event or "")
        self.state["latest_environment_notice"] = ""
        self.state["task_mode"] = "notice"
        self.state["notice_kind"] = "execution"
        self.state["cascade_mode"] = "strict_cascade"
        self.state["distortion_strength"] = 0.6
        self.state["conflict_sensitivity"] = 0.5
        self.state["block_probability"] = 0.25
        self.state["private_events"] = {}
        self.state["active_tier_targets"] = {}
        self.state["policy_version"] = 0
        self.state["processed_policy_version"] = -1
        self.state["conversation_threads"] = {}
        self.state["thread_inboxes"] = {}
        self.state["thread_counter"] = 0
        self.state["persistent_conditions"] = {}
        self.state["pending_follow_up_conditions"] = {}
        self.state["follow_up_thread_seeds"] = []
        self.state["follow_up_no_action_agents"] = []
        self.state["follow_up_public_done_agents"] = []
        self.state["follow_up_force_tier_order"] = False
        self.state["informal_network"] = {}
        self.state["branch_interpretations"] = {}
        self.state["force_complete_current_cascade"] = False
        self.state["complete"] = False
        self._tier_map: Dict[str, str] = {}
        self._agents_by_tier: Dict[str, List[str]] = {
            t: [] for t in self.tier_order
        }

        # Apply policy cascade config from experiment parameters
        self.configure_from_config({"parameters": params})

        # Pipeline A replacements for Pipeline B simulator APIs
        self._agents_dict: Dict[str, Any] = {}
        self._current_round: int = 0
        self._event_emitter: Optional[Callable] = None

    def serialize_config(self) -> dict:
        """Serialize the full Pipeline A scene plus cascade-specific state."""

        agents = []
        for agent in self.agents:
            llm = getattr(agent, "llm_config", None)
            llm_config = None
            if llm is not None:
                llm_config = (
                    llm.model_dump()
                    if hasattr(llm, "model_dump")
                    else dict(llm)
                    if isinstance(llm, dict)
                    else {
                        "dialect": llm.dialect,
                        "api_key": llm.api_key,
                        "model": llm.model,
                        "base_url": llm.base_url,
                        "temperature": llm.temperature,
                        "top_p": llm.top_p,
                        "frequency_penalty": llm.frequency_penalty,
                        "presence_penalty": llm.presence_penalty,
                        "max_tokens": llm.max_tokens,
                        "supports_vision": llm.supports_vision,
                    }
                )
            agents.append(
                {
                    "name": agent.name,
                    "properties": dict(agent.properties),
                    "llm_config": llm_config,
                    "role_prompt": agent.role_prompt,
                    "provider_id": agent.provider_id,
                    "action_history": list(agent.action_history),
                    "score": agent.score,
                    "knowledge_base": list(agent.knowledge_base),
                    "documents": dict(agent.documents),
                }
            )

        return {
            "type": self.TYPE,
            "config": {
                "agents": agents,
                "actions": self.config.actions,
                "parameters": self.config.parameters,
                "state_schema": self.config.state_schema,
                "description": self.config.description,
                "scenario_id": self.config.scenario_id,
                "round_visibility": self.config.round_visibility,
                "social_network": self.config.social_network,
                "locale": self.config.locale,
                "global_knowledge": self.global_knowledge,
            },
            "current_round": self.current_round,
            "history": deepcopy(self._history),
            "state": self._experiment_state.to_dict(),
            "policy_cascade_state": deepcopy(self.state),
            "pending_host_messages": deepcopy(self._pending_host_messages),
            "pgg_phase": self._pgg_phase,
        }

    @classmethod
    def deserialize_config(cls, data: dict) -> "PolicyCascadeExperimentScene":
        """Restore a policy cascade experiment from a SimTree snapshot."""

        config = ExperimentConfig(**data["config"])
        scene = cls(config)
        scene.current_round = data.get("current_round", 0)
        scene._current_round = scene.current_round
        scene._history = deepcopy(data.get("history", []))
        if data.get("state") is not None:
            scene._experiment_state = ExperimentState.from_dict(data["state"])
        scene.state = deepcopy(data.get("policy_cascade_state", scene.state))
        scene._pending_host_messages = deepcopy(data.get("pending_host_messages", []))
        scene._pgg_phase = data.get("pgg_phase", "allocate")
        scene.tier_order = _parse_tier_order(
            scene.state.get("tier_order")
            or config.parameters.get("tier_order")
            or DEFAULT_TIER_ORDER
        )
        scene._agents_by_tier = {tier: [] for tier in scene.tier_order}
        scene._agents_dict = {a.name: a for a in scene.agents}
        return scene

    # ------------------------------------------------------------------
    # Pipeline A -> Pipeline B adapter properties
    # ------------------------------------------------------------------

    @property
    def simulator(self) -> "_SimulatorAdapter":
        """Adapter that makes self look like a Pipeline B Simulator.

        Allows mixin methods written for simulator.agents,
        simulator.emit_event(), simulator.broadcast(), and
        simulator.turns to work unchanged.
        """
        return _SimulatorAdapter(self)

    # ------------------------------------------------------------------
    # ExperimentScene lifecycle overrides
    # ------------------------------------------------------------------

    def initialize(self, llm_client, provider_clients=None):
        """Initialize scene and build agent lookup dict.

        Temporarily restores ExperimentState for the super().initialize()
        call (which expects self.state to be an ExperimentState object),
        then swaps back to the plain dict used by mixin methods.
        """
        cascade_state = self.state
        self.state = self._experiment_state
        super().initialize(llm_client, provider_clients)
        self._experiment_state = self.state
        self.state = cascade_state
        # Build the name->agent dict used by mixin C methods
        self._agents_dict = {a.name: a for a in self.agents}

    def get_scene_actions(self, agent_name: str) -> list[str] | None:
        """Filter available actions by cascade state.

        Pipeline A compatibility: accepts agent name string,
        returns action name strings for the frontend and runner.
        """
        agent = self._agents_dict.get(agent_name)
        if agent is None:
            return None
        try:
            actions = PolicyCascadeRuntimeMixin.get_scene_actions(self, agent)
            return [getattr(a, 'NAME', str(a).lower()) for a in actions]
        except Exception:
            return None

    def process_runner_action_result(self, result: ActionResult, agent) -> ActionResult:
        """Apply policy cascade action semantics to Pipeline A runner output."""

        payload = {"action": result.action_name, **(result.parameters or {})}
        runtime_state = getattr(self, "_policy_cascade_runtime_state", self.state)
        active_state = self.state
        self.state = runtime_state
        try:
            success, action_result, summary, meta, _ = self.parse_and_handle_action(
                payload,
                agent,
                self.simulator,
            )
        finally:
            self.state = active_state
        action_name = str(payload.get("action") or result.action_name)
        parameters = {key: value for key, value in payload.items() if key != "action"}
        if isinstance(action_result, dict):
            parameters.update({key: value for key, value in action_result.items() if key not in {"error"}})
        if meta:
            parameters["meta"] = meta

        return ActionResult(
            success=success,
            action_name=action_name,
            parameters=parameters,
            summary=summary or result.summary,
            agent_name=result.agent_name,
            round_num=result.round_num,
            skipped=(not success) or action_name in {"skip", "yield"},
            error="" if success else str(action_result.get("error", result.error) if isinstance(action_result, dict) else result.error),
            debug_log=result.debug_log,
        )

    async def run_round(self, event_emitter):
        """Run one round, storing event_emitter for mixin use."""
        self._event_emitter = event_emitter
        self._current_round += 1
        # Refresh agent dict (agents may have been updated)
        self._agents_dict = {a.name: a for a in self.agents}

        # Initialize cascade tier mapping from agent properties
        self._rebuild_tiers()

        # Cascade initialization: transition from notice mode to cascade
        # when there is policy text that hasn't been cascaded yet.
        if self.state.get("task_mode") == "notice" and self.state.get("latest_notice"):
            desc = self._clean_policy_text(str(self.state.get("latest_notice", "")))
            if desc and not self.state.get("latest_policy"):
                self.state["policy_version"] = int(self.state.get("policy_version", 0) or 0) + 1
                self.state["latest_policy"] = desc
                self.state["source_policy"] = desc
                self.state["relayed_policy"] = desc
                self.state["task_mode"] = "cascade"
                self.state["notice_kind"] = "execution"
                self._set_force_complete_current_cascade(True)
                self._reset_agents_for_new_policy(self.simulator)
                self.state["complete"] = False
                self._rebuild_tiers()
                self._normalize_active_tier()

        # If cascade is already complete, don't run another round
        if self.state.get("complete"):
            return None

        # Only prompt agents in the current active cascade tier
        active_tier = self._active_tier()
        tier_agents = self._agents_by_tier.get(active_tier, [])
        runner = getattr(self, 'runner', None)
        original_agents = None
        if runner is not None and tier_agents:
            original_agents = list(runner.agents)
            runner.agents = [a for a in original_agents if a.name in tier_agents]
            logger.info(
                "[POLICY CASCADE] Running tier %s: %d agents (%s)",
                active_tier, len(runner.agents), [a.name for a in runner.agents],
            )

        # Swap to ExperimentState for super().run_round() which
        # accesses self.state.round, .history, .agents
        cascade_state = self.state
        self._policy_cascade_runtime_state = cascade_state
        self.state = self._experiment_state
        try:
            result = await super().run_round(event_emitter)
        finally:
            if runner is not None and original_agents is not None:
                runner.agents = original_agents
            self._policy_cascade_runtime_state = cascade_state
        self._experiment_state = self.state
        self.state = cascade_state

        # Post-round cascade advancement: mark each agent that acted
        # as seen for their tier and advance to next tier when all done.
        if result is not None:
            for action in result.actions:
                if action.success and not action.skipped:
                    agent = self._agents_dict.get(action.agent_name)
                    if agent is not None:
                        self.post_turn(agent, self.simulator)

        return result

    # ------------------------------------------------------------------
    # Simulator API replacements (called by mixin C methods)
    # ------------------------------------------------------------------

    def _emit(self, event_type: str, data: dict) -> None:
        """Replace simulator.emit_event() for mixin use."""
        if self._event_emitter:
            self._event_emitter(event_type, data)

    def _broadcast(self, event, receivers=None) -> None:
        """Replace simulator.broadcast() for mixin use."""
        # In Pipeline A, broadcast injects into agent feedback buffers
        targets = self.agents
        if receivers is not None:
            targets = [a for a in self.agents if a.name in receivers]
        for agent in targets:
            if hasattr(event, "content"):
                agent.add_env_feedback(event.content)
            elif isinstance(event, dict) and "content" in event:
                agent.add_env_feedback(event["content"])


class _SimulatorAdapter:
    """Thin adapter that makes PolicyCascadeExperimentScene look like
    a Pipeline B Simulator for mixin methods that still use
    simulator.agents, simulator.emit_event, simulator.broadcast,
    and simulator.turns.

    This is a temporary compatibility layer. As mixin methods are
    updated to use self._agents_dict directly, this adapter shrinks.
    """

    def __init__(self, scene: PolicyCascadeExperimentScene) -> None:
        self._scene = scene

    @property
    def agents(self) -> Dict[str, Any]:
        return self._scene._agents_dict

    @property
    def turns(self) -> int:
        return self._scene._current_round

    def emit_event(self, event_type: str, data: dict) -> None:
        self._scene._emit(event_type, data)

    def emit_event_later(self, event_type: str, data: dict) -> None:
        # In Pipeline A there is no deferred emission -- emit immediately
        self._scene._emit(event_type, data)

    def broadcast(self, event, receivers=None) -> None:
        self._scene._broadcast(event, receivers)
