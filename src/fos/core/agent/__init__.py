"""Minimal Pipeline B Agent class.

Used by policy_cascade and simtree_runtime legacy path.
Pending Pipeline A port.
See docs/plans/policy-cascade-port-investigation.md

Contains: Agent
"""

# TODO: Port PolicyCascadeScene to Pipeline A (ExperimentScene
# subclass) and delete this file. See:
# docs/plans/policy-cascade-port-investigation.md

from __future__ import annotations

import json
import re
from typing import Any

from fos.core.config import MAX_REPEAT
from fos.core.agent.parsing import parse_actions, strip_thinking_tokens
from fos.i18n import T


class Agent:
    """Minimal legacy Agent for Pipeline B scenes."""

    class _ShortMemory:
        def __init__(self):
            self.history = []

        def get_all(self) -> list:
            return self.history

        def append(self, role, content):
            self.history.append({"role": role, "content": content})

        def clear(self):
            self.history = []

        def __len__(self) -> int:
            return len(self.history)

    def __init__(self, name: str, **kwargs):
        self.name = name
        self.properties = kwargs.get("properties", {})
        self.role_prompt = kwargs.get("role_prompt", "")
        self.user_profile = kwargs.get("user_profile", "")
        self.language = kwargs.get("language", "en")
        self.action_space = kwargs.get("action_space", [])
        self.knowledge_base = kwargs.get("knowledge_base", [])
        self.documents = kwargs.get("documents", {})
        self.score = kwargs.get("score", 0)
        self.max_repeat = kwargs.get("max_repeat", MAX_REPEAT)
        self.max_consecutive_llm_errors = int(
            kwargs.get("max_consecutive_llm_errors", 3) or 3
        )
        self.consecutive_llm_errors = 0
        self.is_offline = False
        self.log_event = kwargs.get("event_handler")
        self.short_memory = Agent._ShortMemory()

    def serialize(self) -> dict:
        return {
            "name": self.name,
            "properties": dict(self.properties),
            "role_prompt": self.role_prompt,
            "user_profile": self.user_profile,
            "language": self.language,
            "action_space": [_serialize_action(action) for action in self.action_space],
            "knowledge_base": list(self.knowledge_base),
            "documents": dict(self.documents),
            "score": self.score,
            "short_memory": self.short_memory.get_all(),
        }

    def process(
        self,
        clients: dict[str, Any],
        initiative: bool = False,
        scene: Any | None = None,
    ) -> list[dict[str, Any]]:
        """Ask the model for one legacy action and return it as plain data."""
        client = _select_chat_client(clients, self.properties)
        prompt = self._build_prompt(scene, initiative)
        messages = [*self.short_memory.get_all(), {"role": "user", "content": prompt}]
        attempts = int(getattr(self, "max_repeat", 0) or 0) + 1
        actions = []
        cleaned = ""
        policy_scene = bool(scene and getattr(scene, "TYPE", "") == "policy_cascade_scene")
        success = False
        for attempt in range(attempts):
            response = client.chat(messages, json_mode=True)
            cleaned = strip_thinking_tokens(str(response or ""))
            try:
                actions = parse_actions(
                    cleaned,
                    strict_duplicate_actions=policy_scene,
                )
                self.consecutive_llm_errors = 0
                success = True
                break
            except Exception as error:
                fallback_actions = self._policy_plain_text_fallback(cleaned, scene)
                if fallback_actions:
                    actions = fallback_actions
                    self.consecutive_llm_errors = 0
                    success = True
                    break
                if attempt < attempts - 1:
                    messages.append({"role": "user", "content": self._json_retry_feedback(error)})
                    continue
                self._record_llm_error("parse", error, attempt + 1, True)

        if not success:
            if policy_scene:
                return []
            action = _parse_action_response(cleaned)
            actions = [action] if action else []
        if policy_scene:
            assistant_memory = _compact_assistant_memory(actions, scene)
        else:
            actions = [_flatten_legacy_action(action) for action in actions]
            assistant_memory = cleaned or _compact_assistant_memory(actions, scene)
        if assistant_memory:
            self.short_memory.append("assistant", assistant_memory)
        return actions

    def _policy_plain_text_fallback(
        self,
        cleaned_response: str,
        scene: Any | None,
    ) -> list[dict[str, Any]]:
        """Accept safe plain-language policy replies from small local models.

        The policy cascade newui flow expects JSON actions, but small models
        sometimes answer with plain language. Convert only non-action-like text
        into policy actions. Deliberately refuse JSON-like or action-like
        fragments so malformed action payloads are not rebroadcast.
        """
        if not scene or getattr(scene, "TYPE", "") != "policy_cascade_scene":
            return []

        mode = str(getattr(scene, "state", {}).get("task_mode") or "")
        if hasattr(scene, "_effective_task_mode_for"):
            try:
                mode = str(scene._effective_task_mode_for(self) or mode)
            except Exception:
                pass
        if mode not in {"cascade", "follow_up", "follow_up_thread"}:
            return []

        text = str(cleaned_response or "").strip()
        if not text:
            return []

        lowered = text.lower()
        looks_like_action_fragment = (
            "{" in text
            or "}" in text
            or "<action" in lowered
            or '"action"' in lowered
            or "'action'" in lowered
            or "action:" in lowered
        )
        if looks_like_action_fragment:
            return []

        yield_markers = [
            "结束本轮发言",
            "结束回合",
            "结束发言",
            "让出发言权",
            "yield",
            "pass",
        ]
        if mode == "cascade" and any(marker in lowered for marker in yield_markers):
            return [
                {
                    "thoughts": "Accepted plain cascade yield from a small local model.",
                    "response": text,
                    "action": {"name": "yield"},
                    "context_update": "Cascade yield normalized from plain text.",
                    "metadata": {"fallback": "policy_cascade_plain_yield"},
                }
            ]

        no_action_message = ""
        if hasattr(scene, "_follow_up_no_action_message"):
            try:
                no_action_message = str(scene._follow_up_no_action_message(self) or "").strip()
            except Exception:
                no_action_message = ""
        no_action_markers = [
            "无动作倾向",
            "没有任何动作倾向",
            "no remaining action tendency",
            "no further action tendency",
        ]
        message = (
            no_action_message
            if mode in {"follow_up", "follow_up_thread"}
            and any(marker in lowered for marker in no_action_markers)
            and no_action_message
            else text
        )
        return [
            {
                "thoughts": "Accepted plain policy response from a small local model.",
                "response": "",
                "action": {"name": "send_message", "message": message},
                "context_update": "Policy response normalized from plain text.",
                "metadata": {"fallback": f"policy_{mode}_plain_text"},
            }
        ]

    def _build_prompt(self, scene: Any | None, initiative: bool) -> str:
        """Build the short prompt used by the old policy cascade runner."""
        parts = [f"You are {self.name}."]
        if self.user_profile:
            parts.append(self.user_profile)
        if self.role_prompt:
            parts.append(self.role_prompt)
        if scene is not None and hasattr(scene, "get_behavior_guidelines"):
            parts.append(str(scene.get_behavior_guidelines()))
        if scene is not None and hasattr(scene, "get_agent_status_prompt"):
            parts.append(str(scene.get_agent_status_prompt(self)))
        if scene is not None and hasattr(scene, "get_output_format"):
            parts.append(str(scene.get_output_format()))
        if scene is not None and hasattr(scene, "get_examples"):
            parts.append(str(scene.get_examples()))
        actions = [_serialize_action(action) for action in self.action_space]
        if actions:
            parts.append("Available actions: " + ", ".join(actions))
        if initiative:
            parts.append("Take initiative if the scene calls for it.")
        if scene is not None and getattr(scene, "TYPE", "") == "policy_cascade_scene":
            no_action = ""
            if hasattr(scene, "_follow_up_no_action_message"):
                try:
                    no_action = str(scene._follow_up_no_action_message(self) or "")
                except Exception:
                    no_action = ""
            parts.append(
                "IMPORTANT - Output Format:\n"
                "You MUST respond with one valid JSON object containing these five fields: "
                '"thoughts", "response", "action", "context_update", and "metadata".\n'
                'The "action" field MUST be an object with a valid "name" from Available actions.\n'
                "Use English action names exactly. Do not output plain text, Markdown, Python dicts, or nested JSON strings.\n"
                'For speech/transmission use: {"action":{"name":"send_message","message":"..."}}.\n'
                'For yielding use: {"action":{"name":"yield"}}.\n'
                f'If there is truly no further follow-up action, still output JSON with send_message and message "{no_action}".'
            )
            parts.append(
                "Valid JSON examples:\n"
                '{"thoughts":"I should respond to the current policy state.",'
                '"response":"",'
                '"action":{"name":"send_message","message":"I will report the concrete execution blocker and requested support."},'
                '"context_update":"Reported one concrete execution blocker.",'
                '"metadata":{}}\n'
                '{"thoughts":"No further action remains.",'
                '"response":"",'
                f'"action":{{"name":"send_message","message":"{no_action}"}},'
                '"context_update":"No further follow-up action remains.",'
                '"metadata":{}}'
            )
        else:
            parts.append(
                'Reply as JSON only. Use canonical action names exactly, for example '
                '{"action":"send_message","message":"..."} or {"action":"yield"}.'
            )
        return "\n\n".join(part for part in parts if part)

    def add_env_feedback(self, msg: str) -> None:
        self.short_memory.append("system", msg)

    def set_global_knowledge(self, knowledge: list) -> None:
        self.knowledge_base = knowledge

    def _json_retry_feedback(self, error) -> str:
        return T("prompts.agent.json_retry_feedback", locale=self.language, error=str(error))

    def _record_llm_error(self, kind: str, error, attempt: int, final: bool) -> None:
        if not final:
            return
        self.consecutive_llm_errors += 1
        if self.log_event:
            self.log_event(
                "agent_error",
                {
                    "agent": self.name,
                    "kind": kind,
                    "error": str(error),
                    "attempt": int(attempt),
                    "consecutive_errors": int(self.consecutive_llm_errors),
                    "final_attempt": bool(final),
                },
            )
        if self.consecutive_llm_errors >= self.max_consecutive_llm_errors:
            self.is_offline = True

    @classmethod
    def deserialize(cls, data: dict) -> "Agent":
        props = data.get("properties", {})
        raw_actions = data.get("action_space") or data.get("actionSpace", [])
        action_space = []
        if raw_actions:
            from fos.core.registry import ACTION_SPACE_MAP

            for action in raw_actions:
                if isinstance(action, str):
                    action_space.append(ACTION_SPACE_MAP.get(action, action))
                else:
                    action_space.append(action)
        agent = cls(
            name=data["name"],
            properties=props,
            role_prompt=data.get("role_prompt") or data.get("rolePrompt", ""),
            user_profile=data.get("user_profile") or data.get("userProfile", ""),
            language=data.get("language", "en"),
            action_space=action_space,
            knowledge_base=data.get("knowledge_base") or data.get("knowledgeBase", []),
            documents=data.get("documents", {}),
            score=data.get("score", 0),
        )
        for entry in data.get("short_memory", []):
            agent.short_memory.append(entry.get("role", ""), entry.get("content", ""))
        return agent


def _select_chat_client(clients: dict[str, Any], properties: dict) -> Any:
    """Pick the chat client the old agent should use."""
    provider_id = properties.get("provider_id")
    if provider_id is not None and provider_id in clients:
        return clients[provider_id]
    client = clients.get("chat") or clients.get("default")
    if client is None:
        raise RuntimeError(T("api.errors.legacy_chat_client_missing"))
    return client


def _serialize_action(action: Any) -> str:
    """Turn an action object or string into a saved action name."""
    if isinstance(action, str):
        return action
    name = getattr(action, "NAME", None) or getattr(action, "name", None)
    return str(name or action.__class__.__name__)


def _parse_action_response(response: str) -> dict[str, Any]:
    """Turn a model response into one action dictionary."""
    text = response.strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            _normalize_action_names(parsed)
            return parsed
    except json.JSONDecodeError:
        pass
    match = re.search(r'<Action\s+name="([^"]+)"\s*(?:/|>(.*?)</Action>)', text, re.DOTALL)
    if not match:
        return {"action": "send_message", "message": text}
    action: dict[str, Any] = {"action": match.group(1)}
    for key, value in re.findall(r"<(\w+)>(.*?)</\1>", match.group(2) or "", re.DOTALL):
        action[key] = value.strip()
    _normalize_action_names(action)
    return action


def _flatten_legacy_action(action: dict[str, Any]) -> dict[str, Any]:
    """Keep non-policy legacy Agent output in its historical flat shape."""
    if not isinstance(action, dict):
        return action
    raw_action = action.get("action")
    if not isinstance(raw_action, dict):
        return action
    flattened = {k: v for k, v in action.items() if k != "action"}
    action_name = raw_action.get("name") or raw_action.get("action")
    if action_name:
        flattened["action"] = action_name
    for key, value in raw_action.items():
        if key not in {"name", "action"} and key not in flattened:
            flattened[key] = value
    return flattened


def _compact_assistant_memory(actions: list[dict[str, Any]], scene: Any | None) -> str:
    memory_parts = []
    scene_type = getattr(scene, "TYPE", "") if scene else ""
    scene_state = getattr(scene, "state", {}) if scene else {}
    scene_mode = str(scene_state.get("task_mode", "") or "")

    for item in actions:
        response = str(item.get("response", "") or "").strip()
        if response:
            memory_parts.append(response)

        action_payload = item.get("action") or {}
        action_name = ""
        action_message = ""
        if type(action_payload) is dict:
            action_name = str(action_payload.get("name") or action_payload.get("action") or "").strip()
            action_message = str(action_payload.get("message", "") or "").strip()
        elif isinstance(action_payload, str):
            action_name = action_payload.strip()
            action_message = str(item.get("message", "") or "").strip()

        if action_message and action_message != response and not (scene_type == "policy_cascade_scene" and scene_mode == "notice"):
            memory_parts.append(action_message)

        context_update = str(item.get("context_update", "") or "").strip()
        if context_update:
            memory_parts.append(f"[Remember] {context_update}")

    assistant_memory = "\n".join(memory_parts).strip()
    if assistant_memory:
        return assistant_memory

    fallback_parts = []
    for item in actions:
        action_payload = item.get("action") or {}
        if type(action_payload) is not dict:
            continue
        action_name = str(action_payload.get("name") or action_payload.get("action") or "").strip()
        if not action_name or action_name == "yield":
            continue
        target = str(action_payload.get("target", "") or "").strip()
        if target:
            fallback_parts.append(f"[Action] {action_name} -> {target}")
        else:
            fallback_parts.append(f"[Action] {action_name}")
    return "\n".join(fallback_parts).strip()


def _normalize_action_names(action: dict[str, Any]) -> None:
    raw_action = action.get("action")
    if isinstance(raw_action, dict):
        raw_name = raw_action.get("name") or raw_action.get("action")
        canonical = _canonical_action_name(str(raw_name or ""))
        if canonical:
            raw_action["name"] = canonical
            raw_action["action"] = canonical
        return

    canonical = _canonical_action_name(str(raw_action or action.get("name") or ""))
    if canonical:
        action["action"] = canonical


def _canonical_action_name(name: str) -> str:
    normalized = name.strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "发送消息": "send_message",
        "发消息": "send_message",
        "传递消息": "send_message",
        "传达政策": "send_message",
        "send": "send_message",
        "message": "send_message",
        "结束本轮发言": "yield",
        "结束回合": "yield",
        "结束你的回合": "yield",
        "结束发言": "yield",
        "让出发言权": "yield",
        "暂停": "yield",
        "无动作": "yield",
        "pass": "yield",
        "wait": "yield",
        "end_turn": "yield",
    }
    return aliases.get(normalized, normalized)
