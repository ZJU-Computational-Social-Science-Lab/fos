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
            actions = self._policy_reprompt_missing_action_params(
                actions,
                client,
                messages,
                cleaned,
                scene,
            )
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
        if scene is not None and getattr(scene, "TYPE", "") == "policy_cascade_scene":
            return self._build_policy_cascade_prompt(scene, initiative)

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
        parts.append(
            'Reply as JSON only. Use canonical action names exactly, for example '
            '{"action":"send_message","message":"..."} or {"action":"yield"}.'
        )
        return "\n\n".join(part for part in parts if part)

    def _build_policy_cascade_prompt(self, scene: Any, initiative: bool) -> str:
        action_catalog = "\n".join(
            f"- {getattr(action, 'NAME', '')}: {getattr(action, 'DESC', '')}".strip()
            for action in self.action_space
            if getattr(action, "NAME", "")
        )
        action_instructions = "".join(
            str(getattr(action, "INSTRUCTION", "") or "") for action in self.action_space
        )

        knowledge_block = ""
        enabled_kb = [item for item in self.knowledge_base if isinstance(item, dict) and item.get("enabled", True)]
        if enabled_kb:
            kb_preview = []
            for index, item in enumerate(enabled_kb[:5], start=1):
                title = item.get("title") or "Untitled"
                content_preview = str(item.get("content") or "")[:80]
                if len(str(item.get("content") or "")) > 80:
                    content_preview += "..."
                kb_preview.append(f"  [{index}] {title}: {content_preview}")
            knowledge_block = "\nKnowledge Base:\n" + "\n".join(kb_preview)

        identity_parts = [self.name]
        if self.role_prompt:
            identity_parts.append(self.role_prompt)
        identity_line = " - ".join(identity_parts)

        scene_block = ""
        if hasattr(scene, "get_compact_description"):
            scene_block = str(scene.get_compact_description() or "")
        elif hasattr(scene, "get_scenario_description"):
            scene_block = str(scene.get_scenario_description() or "")
        if hasattr(scene, "get_behavior_guidelines"):
            scene_block = f"{scene_block}\n\n{scene.get_behavior_guidelines()}".strip()
        if hasattr(scene, "get_agent_status_prompt"):
            status_prompt = str(scene.get_agent_status_prompt(self) or "")
            if status_prompt:
                scene_block = f"{scene_block}\n\n{status_prompt}".strip()

        example_block = self._policy_cascade_example_block(scene)
        initial_instruction = "Take initiative if the scene calls for it." if initiative else ""

        return f"""{identity_line}

{self.user_profile if len(self.user_profile) < 500 else self.user_profile[:500] + "..."}

Language: {self.language}. Respond in {self.language} for content; use English for action names.
{knowledge_block}

{scene_block}

Action Space:
{action_catalog}

Usage:
{action_instructions}

{initial_instruction}

IMPORTANT - Output Format:
You MUST respond with a valid JSON object containing these 5 sections:

1. "thoughts": Your brief thinking about the current situation (1-2 sentences)

2. "response": What you want to communicate (can be empty string if no speech needed)

3. "action": The action you want to take, containing:
   - "name": action name from the Action Space above
   - Additional key-value pairs for action parameters (if required)

4. "context_update": Brief notes to remember for future (goals, observations, plans)

5. "metadata": Optional object with any additional metadata

{example_block}

You must always provide an "action" with a valid "name" from the Action Space. If you only want to speak, use "send_message" and include the text in the "message" field. Use "yield" when you are done with your turn.
""".strip()

    def _policy_cascade_example_block(self, scene: Any) -> str:
        def _compact_policy_example(text: str) -> str:
            if hasattr(scene, "_policy_prompt_excerpt"):
                summary = scene._policy_prompt_excerpt(text)
                if summary:
                    return summary
            cleaned = str(text or "").strip()
            return cleaned[:48] if cleaned else "逐级传达政策，并保留关键执行条款"

        private_event = scene._private_event_for(self.name) if hasattr(scene, "_private_event_for") else {}
        has_private_source = bool(private_event)
        task_mode = str(private_event.get("task_mode") or scene.state.get("task_mode", "notice") or "notice")
        notice_kind = str(private_event.get("notice_kind") or scene.state.get("notice_kind", "execution") or "execution")
        cascade_mode = str(scene.state.get("cascade_mode", "strict_cascade") or "strict_cascade")
        policy_text = str(
            private_event.get("relayed_policy")
            or private_event.get("latest_policy")
            or scene.state.get("relayed_policy", "")
            or scene.state.get("latest_policy", "")
            or ""
        ).strip()
        source_policy_text = str(private_event.get("source_policy") or scene.state.get("source_policy", "") or policy_text).strip()
        notice_text = str(private_event.get("latest_notice") or scene.state.get("latest_notice", "") or "").strip()
        tier = str(getattr(scene, "_tier_map", {}).get(self.name, self.properties.get("tier", "")) or "").strip()
        role_kind = scene._tier_role_kind(tier) if hasattr(scene, "_tier_role_kind") else "mid"

        if task_mode == "cascade":
            example_policy = policy_text or source_policy_text or "最新政策原文"
            example_policy_summary = _compact_policy_example(source_policy_text or example_policy)
            if cascade_mode == "distortion_cascade":
                if role_kind == "top":
                    if has_private_source:
                        example_message = f"对于这条仅向我私下传达的政策，我决定先强调“{example_policy_summary}”，暂不展开全部资源承诺。"
                    else:
                        example_message = f"关于上级刚才的传达，我决定继续强调“{example_policy_summary}”，暂不展开全部资源承诺。"
                    context_update = "已按本层利益重述政策重点，并保留部分信息"
                elif role_kind == "mid":
                    if has_private_source:
                        example_message = f"我会只向下传达可立即执行的部分，先保留“{example_policy_summary}”，其余内容暂缓。"
                    else:
                        example_message = f"考虑到本部门考核压力，我只向下传达可立即执行的部分，先保留“{example_policy_summary}”。"
                    context_update = "已结合中层压力选择性下传政策"
                else:
                    if has_private_source:
                        example_message = f"该政策与一线负担存在冲突，我会先按基层可执行口径保留“{example_policy_summary}”，并上报执行困难。"
                    else:
                        example_message = f"该政策与一线负担存在冲突，我会先保留“{example_policy_summary}”中的最低执行要求。"
                    context_update = "已因基层执行冲突而弱化落实"
                distortion_note = (
                    f"当前失真参数：失真强度={float(scene.state.get('distortion_strength', 0.6) or 0.6):.2f}，"
                    f"利益冲突敏感度={float(scene.state.get('conflict_sensitivity', 0.5) or 0.5):.2f}，"
                    f"截留概率={float(scene.state.get('block_probability', 0.25) or 0.25):.2f}。"
                )
            elif role_kind == "top":
                example_message = f"我会按原文继续传达“{example_policy_summary}”。态度：完全支持并按原文执行。补充：由我批准专项预算并建立月度问责机制。"
                context_update = "已按原文转发，并补充高层统筹与资源安排"
                distortion_note = ""
            elif role_kind == "mid":
                example_message = f"我会按原文继续传达“{example_policy_summary}”。态度：完全支持并按原文执行。补充：我将在48小时内拆解任务到各部门并建立周报台账。"
                context_update = "已按原文转发，并补充中层协调与任务拆解"
                distortion_note = ""
            else:
                example_message = f"我会按原文继续传达“{example_policy_summary}”。态度：完全支持并按原文执行。补充：我将按排查清单逐项核验，并在发现异常后24小时内上报。"
                context_update = "已按原文转发，并补充基层执行与异常上报"
                distortion_note = ""
            message_json = json.dumps(example_message, ensure_ascii=False)
            silent_context = "等待下一级反馈" if cascade_mode != "distortion_cascade" else "因本层利益冲突暂缓下传"
            example_block = f"""Example JSON response:
```json
{{
    "thoughts": "转发最新政策，保持原文并附执行计划。",
    "response": "",
    "action": {{
        "name": "send_message",
        "message": {message_json}
    }},
    "context_update": "{context_update}",
    "metadata": {{}}
}}
```

If you only want to speak without taking an action:
```json
{{
    "thoughts": "无需转发时保持静默等待。",
    "response": "",
    "action": {{
        "name": "yield"
    }},
    "context_update": "{silent_context}",
    "metadata": {{}}
}}
```"""
            return f"{distortion_note}\n\n{example_block}" if cascade_mode == "distortion_cascade" else example_block

        if notice_kind == "analysis":
            if role_kind == "top":
                notice_message = f"作为高层，我对“{notice_text or '最新任务'}”的看法是：优点在于有利于统一部署、压实责任和跟踪问效；缺点在于如果资源和配套制度不足，容易形成层层加码；建议同步明确牵头单位、预算安排和督促检查节奏。"
                context_update = "已从高层视角完成政策解读与优缺点分析"
            elif role_kind == "mid":
                notice_message = f"作为中层，我对“{notice_text or '最新任务'}”的看法是：优点在于便于分解任务、建立台账和协同推进；缺点在于若验收标准不清，容易造成重复报送和责任交叉；建议尽快细化举措、明确时间表和周报机制。"
                context_update = "已从中层视角完成政策解读与优缺点分析"
            else:
                notice_message = f"作为基层执行者，我对“{notice_text or '最新任务'}”的看法是：优点在于有助于逐项排查、现场核验和及时上报；缺点在于若模板过多、口径频繁变化，会增加执行负担；建议简化报送字段并明确整改、复查和销号标准。"
                context_update = "已从基层视角完成政策解读与优缺点分析"
        elif role_kind == "top":
            notice_message = f"关于系统公告“{notice_text or '最新任务'}”，作为高层，我将明确总体目标、资源投放、压实责任和考核机制，并指定牵头负责人。"
            context_update = "已从高层视角回应系统公告"
        elif role_kind == "mid":
            notice_message = f"关于系统公告“{notice_text or '最新任务'}”，作为中层，我将分解任务、协调相关单位、建立工作台账，并给出周度推进时间表。"
            context_update = "已从中层视角回应系统公告"
        else:
            notice_message = f"关于系统公告“{notice_text or '最新任务'}”，作为基层执行者，我将按清单落实排查步骤、现场核验问题、推进整改复查并及时上报反馈。"
            context_update = "已从基层视角回应系统公告"
        message_json = json.dumps(notice_message, ensure_ascii=False)
        return f"""Example JSON response:
```json
{{
    "thoughts": "需要直接回应最新系统公告，并给出符合本职位职责的解读。",
    "response": "",
    "action": {{
        "name": "send_message",
        "message": {message_json}
    }},
    "context_update": "{context_update}",
    "metadata": {{}}
}}
```

If you only want to speak without taking an action:
```json
{{
    "thoughts": "当前没有新增任务时可以结束回合。",
    "response": "",
    "action": {{
        "name": "yield"
    }},
    "context_update": "等待下一条系统公告",
    "metadata": {{}}
}}
```"""

    def _policy_reprompt_missing_action_params(
        self,
        actions: list[dict[str, Any]],
        client: Any,
        messages: list[dict[str, str]],
        llm_output: str,
        scene: Any | None,
    ) -> list[dict[str, Any]]:
        if not scene or getattr(scene, "TYPE", "") != "policy_cascade_scene":
            return actions
        action_lookup = {getattr(action, "NAME", ""): action for action in self.action_space}
        for item in actions:
            if not isinstance(item, dict):
                continue
            action_payload = item.get("action") or {}
            if not isinstance(action_payload, dict):
                continue
            action_name = str(action_payload.get("name") or action_payload.get("action") or "").strip()
            if not action_name:
                continue
            action_def = action_lookup.get(action_name)
            if action_def is None:
                continue
            reprompt_param = getattr(action_def, "REPROMPT_PARAM", None)
            if not reprompt_param:
                continue
            reprompt_scene_types = getattr(action_def, "REPROMPT_SCENE_TYPES", None)
            if reprompt_scene_types and getattr(scene, "TYPE", "") not in reprompt_scene_types:
                continue
            reprompt_task_modes = getattr(action_def, "REPROMPT_TASK_MODES", None)
            if reprompt_task_modes and hasattr(scene, "_effective_task_mode_for"):
                task_mode = scene._effective_task_mode_for(self)
                if task_mode not in reprompt_task_modes:
                    continue
            if str(action_payload.get(reprompt_param) or item.get(reprompt_param) or "").strip():
                continue
            reprompt_instruction = self._json_retry_feedback(
                f"Action '{action_name}' is missing required field '{reprompt_param}'. Return only the {reprompt_param} text."
            )
            reprompt_messages = [
                *messages,
                {"role": "assistant", "content": llm_output},
                {"role": "user", "content": reprompt_instruction},
            ]
            reprompt_output = strip_thinking_tokens(str(client.chat(reprompt_messages, json_mode=False) or "")).strip()
            if reprompt_output:
                action_payload[reprompt_param] = reprompt_output
        return actions

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
