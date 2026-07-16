"""
Action validation with declarative metadata.

This legacy controller is used by Pipeline B scenes such as
policy_cascade_scene. Current ExperimentScene paths use their own controller.
"""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, Optional, Set, Tuple

from fos.core.agent import Agent


DEBUG_ACTION_VALIDATION = os.getenv("DEBUG_ACTION_VALIDATION", "false").lower() == "true"


class ActionConstraints:
    ALLOWED_ROLES: Set[str] = set()
    STATE_GUARD: Optional[Callable[[Dict[str, Any]], bool]] = None
    PARAMETER_VALIDATOR: Optional[Callable[[Dict[str, Any]], bool]] = None
    STATE_ERROR: Optional[str] = None


class ActionController:
    """Validate legacy agent actions before execution."""

    def __init__(self):
        self._explicit_rules: Dict[str, dict] = {}

    def validate_action(
        self,
        action_name: str,
        action_data: Dict[str, Any],
        agent: Agent,
        scene_state: Dict[str, Any],
        action_instance: Any = None,
        scene: Any = None,
    ) -> Tuple[bool, Optional[str]]:
        if scene and hasattr(scene, "facilitator") and scene.facilitator:
            allowed, error = scene.facilitator.is_action_allowed(action_name)
            if not allowed:
                return False, error

        if action_instance:
            return self._validate_with_constraints(
                action_instance,
                action_data,
                agent,
                scene_state,
            )

        if action_name in self._explicit_rules:
            return self._validate_with_explicit_rules(
                action_name,
                action_data,
                agent,
                scene_state,
            )

        return True, None

    def _validate_with_constraints(
        self,
        action: Any,
        action_data: Dict[str, Any],
        agent: Agent,
        scene_state: Dict[str, Any],
    ) -> Tuple[bool, Optional[str]]:
        if hasattr(action, "ALLOWED_ROLES") and action.ALLOWED_ROLES:
            if not self._check_role(agent, action.ALLOWED_ROLES):
                return False, self._role_error(agent, action.ALLOWED_ROLES)

        if hasattr(action, "STATE_GUARD") and action.STATE_GUARD:
            if not action.STATE_GUARD(scene_state):
                error = getattr(action, "STATE_ERROR", "Invalid state for this action")
                return False, error

        if hasattr(action, "PARAMETER_VALIDATOR") and action.PARAMETER_VALIDATOR:
            if not action.PARAMETER_VALIDATOR(action_data):
                return False, f"Invalid parameters for '{action.NAME}'"

        return True, None

    def _validate_with_explicit_rules(
        self,
        action_name: str,
        action_data: Dict[str, Any],
        agent: Agent,
        scene_state: Dict[str, Any],
    ) -> Tuple[bool, Optional[str]]:
        rules = self._explicit_rules[action_name]

        if "roles" in rules and not self._check_role(agent, rules["roles"]):
            return False, self._role_error(agent, rules["roles"])

        if "state_guard" in rules and not rules["state_guard"](scene_state):
            return False, rules.get("state_error", "Invalid state")

        if "param_validator" in rules and not rules["param_validator"](action_data):
            return False, f"Invalid parameters for '{action_name}'"

        return True, None

    def _check_role(self, agent: Agent, allowed_roles: Set[str]) -> bool:
        agent_role = (
            agent.properties.get("role", agent.name)
            if hasattr(agent, "properties")
            else agent.name
        )
        if "*" in allowed_roles:
            return str(agent_role).lower() != "host"
        if not allowed_roles:
            return True
        return str(agent_role).lower() in {role.lower() for role in allowed_roles}

    def _role_error(self, agent: Agent, allowed_roles: Set[str]) -> str:
        agent_role = (
            agent.properties.get("role", agent.name)
            if hasattr(agent, "properties")
            else agent.name
        )
        if "*" in allowed_roles:
            return "Permission denied: Host cannot perform this action"
        roles_str = ", ".join(allowed_roles)
        return (
            f"Permission denied: Agent '{agent.name}' (role: '{agent_role}') "
            f"is not allowed (requires: {roles_str})"
        )
