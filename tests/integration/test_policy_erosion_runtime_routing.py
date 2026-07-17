"""Regression tests for Policy Meaning Erosion runtime routing."""

from __future__ import annotations

from types import SimpleNamespace

from fos.backend.api.routes.simulations.crud import _normalize_scene_type
from fos.backend.services import simtree_runtime
from fos.core.agent import Agent
from fos.core.event import PublicEvent
from fos.core.ordering import SequentialOrdering
from fos.core.scenes.policy_cascade import PolicyCascadeScene
from fos.core.simulator import Simulator


class FakeChatClient:
    """Small chat client that returns one policy message action."""

    def __init__(self) -> None:
        self.messages: list[list[dict[str, str]]] = []

    def chat(self, messages: list[dict[str, str]], json_mode: bool = False) -> str:
        self.messages.append(messages)
        return '{"action": "send_message", "message": "Policy stays clear."}'


class DistortingFakeChatClient:
    """Chat client that produces a visibly rewritten policy message."""

    def chat(self, messages: list[dict[str, str]], json_mode: bool = False) -> str:
        return '{"action": "send_message", "message": "Only communicate the easy parts first."}'


class ChineseYieldFakeChatClient:
    """Small-model style response that uses a localized yield phrase."""

    def chat(self, messages: list[dict[str, str]], json_mode: bool = False) -> str:
        return '{"action": {"name": "结束本轮发言"}}'


class NewUiFiveSectionFakeChatClient:
    """newui-style five-section JSON response used by the policy Agent."""

    def chat(self, messages: list[dict[str, str]], json_mode: bool = False) -> str:
        return """
        {
          "thoughts": "I should relay the current policy.",
          "response": "",
          "action": {
            "name": "send_message",
            "message": "Keep the policy wording intact.\\n态度：完全支持并按原文执行。"
          },
          "context_update": "Relayed the policy without wrapping action JSON.",
          "metadata": {}
        }
        """


class RetryThenNewUiFakeChatClient:
    """First returns invalid JSON, then follows the newui contract."""

    def __init__(self) -> None:
        self.calls = 0

    def chat(self, messages: list[dict[str, str]], json_mode: bool = False) -> str:
        self.calls += 1
        if self.calls == 1:
            return "{'action': 'send_message', 'message': '{\"action\":\"send_message\"}'}"
        return """
        {
          "thoughts": "Retry with valid JSON.",
          "response": "",
          "action": {
            "name": "send_message",
            "message": "Keep the policy wording intact."
          },
          "context_update": "Recovered after parse retry.",
          "metadata": {}
        }
        """


class AlwaysInvalidActionStringFakeChatClient:
    """Repeatedly returns a Python-dict action string that must not be broadcast."""

    def chat(self, messages: list[dict[str, str]], json_mode: bool = False) -> str:
        return "{'action': 'send_message', 'message': '{\"action\":\"send_message\"}'}"


class PlainFollowUpNoActionFakeChatClient:
    """Small-model style follow-up reply without JSON."""

    def chat(self, messages: list[dict[str, str]], json_mode: bool = False) -> str:
        return "当前已没有任何动作倾向，建议注入新的环境事件或发布新的政策。"


class PlainCascadeTextFakeChatClient:
    """Small-model style cascade reply without JSON."""

    def chat(self, messages: list[dict[str, str]], json_mode: bool = False) -> str:
        return "我会按原文继续传达该政策，并补充本层执行安排。"


class PlainCascadeYieldFakeChatClient:
    """Small-model style localized yield without JSON."""

    def chat(self, messages: list[dict[str, str]], json_mode: bool = False) -> str:
        return "结束本轮发言"


class PlaceholderCascadeFakeChatClient:
    """Model reply that copies prompt placeholders instead of policy content."""

    def chat(self, messages: list[dict[str, str]], json_mode: bool = False) -> str:
        return """
        {
          "thoughts": "I should relay the policy.",
          "response": "",
          "action": {
            "name": "send_message",
            "message": "态度：...\\n补充：...\\n补充：本层只补充高层统筹、资源批准和督办问责安排。"
          },
          "context_update": "Copied a placeholder draft.",
          "metadata": {}
        }
        """


class CascadeSpecialActionFakeChatClient:
    """Small model may pick a follow-up action while it is still relaying policy."""

    def __init__(self) -> None:
        self.calls = 0

    def chat(self, messages: list[dict[str, str]], json_mode: bool = False) -> str:
        self.calls += 1
        if self.calls == 2:
            return """
            {
              "thoughts": "I should notify the next tier, but this is still cascade relay.",
              "response": "第二条分支继续传达政策。",
              "action": {
                "name": "notify_subordinate",
                "message": "第二条分支继续传达政策。"
              },
              "metadata": {}
            }
            """
        return '{"action": "send_message", "message": "Policy stays clear."}'


class MissingMessageRepromptFakeChatClient:
    """First selects a policy follow-up action, then answers the reprompt."""

    def __init__(self) -> None:
        self.calls = 0

    def chat(self, messages: list[dict[str, str]], json_mode: bool = False) -> str:
        self.calls += 1
        if self.calls == 1:
            return """
            {
              "thoughts": "I need to report upward.",
              "response": "",
              "action": {
                "name": "report_upward",
                "target": "Director"
              },
              "context_update": "Selected report_upward without message.",
              "metadata": {}
            }
            """
        return "资源缺口和执行成本已经影响政策落地，需要上级明确支持口径。"


class FixedJsonChatClient:
    """Current-architecture fake client that always returns a valid policy action."""

    def __init__(self, message: str = "Policy stays clear.") -> None:
        self.message = message

    def chat(self, messages: list[dict[str, str]], json_mode: bool = False) -> str:
        return '{"action": "send_message", "message": "%s"}' % self.message


def _legacy_agent(name: str, tier: str) -> Agent:
    return Agent(
        name=name,
        user_profile=f"Test profile for {name}",
        properties={"tier": tier, "政治职位层级": tier},
    )


def _legacy_simulator(
    scene: PolicyCascadeScene,
    agents: list[Agent],
    events: list[tuple[str, dict]] | None = None,
) -> Simulator:
    return Simulator(
        agents,
        scene,
        clients={"chat": FixedJsonChatClient(), "default": FixedJsonChatClient()},
        event_handler=(lambda event_type, data: events.append((event_type, data))) if events is not None else None,
        ordering=SequentialOrdering(),
    )


def _complete_single_branch_cascade(scene: PolicyCascadeScene, simulator: Simulator, agents: list[Agent]) -> None:
    simulator.broadcast(PublicEvent("「系统公告」 后续反馈测试\n目标：逐级传达"), receivers=[agents[0].name])
    scene.parse_and_handle_action({"action": "send_message", "message": "Top version"}, agents[0], simulator)
    scene.post_turn(agents[0], simulator)
    scene.parse_and_handle_action({"action": "send_message", "message": "Mid version"}, agents[1], simulator)
    scene.post_turn(agents[1], simulator)
    scene.parse_and_handle_action({"action": "send_message", "message": "Low version"}, agents[2], simulator)
    scene.post_turn(agents[2], simulator)


def _policy_record(scene_type: str, *, cascade_mode: str = "strict_cascade") -> SimpleNamespace:
    return SimpleNamespace(
        id="POLICY-ROUTING",
        scene_type=scene_type,
        scene_config={
            "generic_config": {
                "scenario_id": "policy_erosion",
                "description": "Transmit the policy through tiers.",
                "parameters": {
                    "policy_text": "Keep the policy wording intact.",
                    "tier_order": ["top", "mid", "low"],
                    "cascade_mode": cascade_mode,
                    "distortion_strength": 0.8,
                    "conflict_sensitivity": 0.7,
                    "block_probability": 0.0,
                },
            },
        },
        name="Policy erosion",
        description="Transmit the policy through tiers.",
        notes="",
        agent_config={
            "agents": [
                {"name": "Director", "properties": {"tier": "top"}},
                {"name": "Manager", "properties": {"tier": "mid"}},
                {"name": "Staff", "properties": {"tier": "low"}},
            ]
        },
    )


def _branched_policy_record() -> SimpleNamespace:
    return SimpleNamespace(
        id="POLICY-BRANCH",
        scene_type="policy_cascade_scene",
        scene_config={
            "generic_config": {
                "scenario_id": "policy_erosion",
                "description": "Transmit the policy through two branches.",
                "social_network": {
                    "Agent 1": ["Agent 3"],
                    "Agent 2": ["Agent 4"],
                    "Agent 3": ["Agent 5"],
                    "Agent 4": ["Agent 6"],
                    "Agent 5": [],
                    "Agent 6": [],
                },
                "parameters": {
                    "policy_text": "Keep the policy wording intact.",
                    "tier_order": ["top", "mid", "low"],
                    "cascade_mode": "distortion_cascade",
                    "distortion_strength": 0.6,
                    "conflict_sensitivity": 0.5,
                    "block_probability": 0.0,
                },
            },
        },
        name="Policy erosion",
        description="Transmit the policy through tiers.",
        notes="",
        agent_config={
            "agents": [
                {"name": "Agent 1", "properties": {"tier": "top"}},
                {"name": "Agent 2", "properties": {"tier": "top"}},
                {"name": "Agent 3", "properties": {"tier": "mid"}},
                {"name": "Agent 4", "properties": {"tier": "mid"}},
                {"name": "Agent 5", "properties": {"tier": "low"}},
                {"name": "Agent 6", "properties": {"tier": "low"}},
            ]
        },
    )


def test_create_simulation_normalizes_policy_erosion_scene_type() -> None:
    """Policy erosion should be stored on the dedicated cascade scene."""
    scene_config = _policy_record("experiment").scene_config

    assert _normalize_scene_type("experiment", scene_config) == "policy_cascade_scene"


def test_runtime_corrects_existing_policy_erosion_experiment_records() -> None:
    """Old records with scene_type=experiment still build PolicyCascadeScene."""
    tree = simtree_runtime._build_tree_for_sim(_policy_record("experiment"), clients={})

    scene = tree.nodes[tree.root]["sim"].scene

    assert isinstance(scene, PolicyCascadeScene)
    assert scene.TYPE == "policy_cascade_scene"
    assert scene.state["latest_notice"] == "Keep the policy wording intact."
    assert scene.state["task_mode"] == "cascade"
    assert scene.state["latest_policy"] == "Keep the policy wording intact."
    assert scene.tier_order == ["top", "mid", "low"]


def test_policy_erosion_runtime_runs_initial_cascade_then_follow_up() -> None:
    """Initial policy text should cascade tier-by-tier before follow-up discussion."""
    client = FakeChatClient()
    tree = simtree_runtime._build_tree_for_sim(
        _policy_record("policy_cascade_scene"),
        clients={"chat": client},
    )
    simulator = tree.nodes[tree.root]["sim"]

    simulator.run(max_turns=1)

    logs = tree.nodes[tree.root]["logs"]
    assert client.messages
    broadcasts = [log for log in logs if log["type"] == "system_broadcast"]
    assert [(log["data"]["sender"], log["data"]["recipients"]) for log in broadcasts[-3:]] == [
        ("Director", ["Manager"]),
        ("Manager", ["Staff"]),
        ("Staff", []),
    ]
    assert simulator.scene.state["task_mode"] == "cascade"
    assert simulator.scene.state["processed_policy_version"] == simulator.scene.state["policy_version"]

    before_follow_up_logs = len(tree.nodes[tree.root]["logs"])
    simulator.run(max_turns=1)

    assert simulator.scene.state["task_mode"] == "follow_up"
    assert len(tree.nodes[tree.root]["logs"]) > before_follow_up_logs


def test_policy_erosion_cascade_prompt_uses_newui_contract_without_no_action_hint() -> None:
    """Cascade prompt should match newui's mode-specific contract."""
    tree = simtree_runtime._build_tree_for_sim(
        _policy_record("policy_cascade_scene", cascade_mode="distortion_cascade"),
        clients={"chat": FixedJsonChatClient()},
    )
    simulator = tree.nodes[tree.root]["sim"]
    agent = simulator.agents["Director"]
    simulator._refresh_scene_action_space(agent)

    prompt = agent._build_prompt(simulator.scene, initiative=False)

    assert "Action Space:" in prompt
    assert "Usage:" in prompt
    assert "当前失真参数" in prompt
    assert "Available actions:" not in prompt
    assert "当前已没有任何动作倾向" not in prompt
    assert '"name": "yield"' in prompt


def test_policy_erosion_follow_up_prompt_uses_yield_not_no_action_template() -> None:
    """Follow-up prompt should not prime small models to emit the no-action sentence."""
    tree = simtree_runtime._build_tree_for_sim(
        _policy_record("policy_cascade_scene", cascade_mode="distortion_cascade"),
        clients={"chat": FixedJsonChatClient()},
    )
    simulator = tree.nodes[tree.root]["sim"]
    scene = simulator.scene
    scene.state["task_mode"] = "follow_up"
    scene.state["latest_notice"] = "员工反馈出现口径分歧，需要继续讨论。"
    agent = simulator.agents["Manager"]
    simulator._refresh_scene_action_space(agent)

    prompt = agent._build_prompt(scene, initiative=False)

    assert "Action Space:" in prompt
    assert "report_upward" in prompt
    assert "consult_peer" in prompt
    assert "当前已没有任何动作倾向" not in prompt
    assert '"name": "yield"' in prompt


def test_policy_erosion_follow_up_action_message_reprompt_matches_newui_contract() -> None:
    """Policy-only Agent path should reprompt for missing action message text."""
    scene = PolicyCascadeScene("policy", "", cascade_mode="distortion_cascade")
    director = _legacy_agent("Director", "top")
    manager = _legacy_agent("Manager", "mid")
    simulator = Simulator(
        [director, manager],
        scene,
        clients={"chat": MissingMessageRepromptFakeChatClient()},
        ordering=SequentialOrdering(),
    )
    scene.state["task_mode"] = "follow_up"
    simulator._refresh_scene_action_space(manager)

    actions = manager.process(simulator.clients, scene=scene)

    action_payload = actions[0]["action"]
    assert action_payload["name"] == "report_upward"
    assert action_payload["target"] == "Director"
    assert "资源缺口" in action_payload["message"]


def test_policy_erosion_follow_up_target_name_tolerates_missing_spaces() -> None:
    """Policy follow-up actions should resolve model target names like 智能体4."""
    events: list[tuple[str, dict]] = []
    scene = PolicyCascadeScene("policy", "", cascade_mode="distortion_cascade")
    agent3 = _legacy_agent("智能体 3", "mid")
    agent4 = _legacy_agent("智能体 4", "mid")
    simulator = _legacy_simulator(scene, [agent3, agent4], events)
    scene.state["task_mode"] = "follow_up"

    success, result, summary, _, _ = scene.handle_policy_special_action(
        "consult_peer",
        {"target": "智能体4", "message": "我们需要统一阶段性薪酬调整的解释口径。"},
        agent3,
        simulator,
    )

    assert success is True
    assert result["target"] == "智能体 4"
    assert "解释口径" in result["message"]
    assert "No such person" not in summary
    opened = [payload for event_type, payload in events if event_type == "policy_thread_opened"]
    assert opened[0]["recipient"] == "智能体 4"
    assert "解释口径" in opened[0]["message"]


def test_policy_erosion_follow_up_target_name_tolerates_common_small_model_aliases() -> None:
    """Policy follow-up target matching should tolerate common local-model aliases."""
    scene = PolicyCascadeScene("policy", "", cascade_mode="distortion_cascade")
    agent3 = _legacy_agent("智能体 3", "mid")
    agent4 = _legacy_agent("智能体 4", "mid")
    simulator = _legacy_simulator(scene, [agent3, agent4])
    scene.state["task_mode"] = "follow_up"

    for alias in ["4号智能体", "Agent4", "智能体四"]:
        success, result, summary, _, _ = scene.handle_policy_special_action(
            "consult_peer",
            {"target": alias, "message": f"请{alias}一起核对政策调整口径。"},
            agent3,
            simulator,
        )

        assert success is True
        assert result["target"] == "智能体 4"
        assert "No such person" not in summary


def test_policy_erosion_infers_target_from_common_small_model_aliases() -> None:
    """Policy target inference should understand aliases in the message text."""
    scene = PolicyCascadeScene("policy", "", cascade_mode="distortion_cascade")
    agent3 = _legacy_agent("智能体 3", "mid")
    agent4 = _legacy_agent("智能体 4", "mid")
    _legacy_simulator(scene, [agent3, agent4])
    scene.state["task_mode"] = "follow_up"

    inferred = scene._infer_special_action_target(
        "consult_peer",
        {"message": "我需要和4号智能体统一阶段性薪酬调整口径。"},
        agent3,
        "follow_up",
    )

    assert inferred == "智能体 4"


def test_policy_erosion_thread_ignored_emits_readable_notice() -> None:
    """Ignoring a policy thread should emit the policy_thread_ignored event."""
    events: list[tuple[str, dict]] = []
    scene = PolicyCascadeScene("policy", "", cascade_mode="distortion_cascade")
    agent3 = _legacy_agent("智能体 3", "mid")
    agent4 = _legacy_agent("智能体 4", "mid")
    simulator = _legacy_simulator(scene, [agent3, agent4], events)

    thread = scene._open_thread(
        "peer_consult",
        agent3,
        agent4.name,
        "请核对政策调整口径。",
        simulator,
        {"issues": ["口径分歧"]},
    )
    scene._ignore_thread(thread, agent4, simulator)

    ignored = [payload for event_type, payload in events if event_type == "policy_thread_ignored"]
    assert ignored
    assert ignored[-1]["agent"] == "智能体 4"
    assert ignored[-1]["kind"] == "peer_consult"
    assert ignored[-1]["notice"]


def test_policy_erosion_policy_adjustment_reopens_branch_cascade() -> None:
    """announce_policy_adjustment should broadcast and queue downstream cascade."""
    events: list[tuple[str, dict]] = []
    scene = PolicyCascadeScene("policy", "", cascade_mode="distortion_cascade")
    top = _legacy_agent("智能体 1", "top")
    manager = _legacy_agent("智能体 3", "mid")
    staff = _legacy_agent("智能体 5", "low")
    simulator = _legacy_simulator(scene, [top, manager, staff], events)
    scene.state["task_mode"] = "follow_up"
    scene.state["latest_policy"] = "原政策文本"
    scene.state["source_policy"] = "原政策文本"
    scene.state["relayed_policy"] = "原政策文本"
    scene.state["policy_version"] = 1
    scene.state["processed_policy_version"] = 1
    scene.state["persistent_conditions"] = {"public_opinion_pressure": 0.7}
    scene.state["social_network"] = {"智能体 1": ["智能体 3"], "智能体 3": ["智能体 5"], "智能体 5": []}

    success, result, summary, _, _ = scene.handle_policy_special_action(
        "announce_policy_adjustment",
        {"message": "统一补充稳岗安排和申诉反馈渠道。"},
        manager,
        simulator,
    )
    simulator.emit_remaining_events()

    assert success is True
    assert result["recipients"] == ["智能体 5"]
    assert "政策调整" in result["message"]
    assert "发布" in summary
    issued = [payload for event_type, payload in events if event_type == "policy_adjustment_issued"]
    assert issued[-1]["sender"] == "智能体 3"
    assert issued[-1]["recipients"] == ["智能体 5"]
    private_event = scene.state["private_events"]["智能体 5"]
    assert private_event["task_mode"] == "cascade"
    assert "稳岗安排" in private_event["relayed_policy"]
    broadcasts = [payload for event_type, payload in events if event_type == "system_broadcast"]
    assert any(payload.get("recipients") == ["智能体 5"] for payload in broadcasts)


def test_policy_erosion_prompt_does_not_include_copyable_placeholders() -> None:
    """Policy prompts should not contain placeholders that small models can copy."""
    client = FakeChatClient()
    tree = simtree_runtime._build_tree_for_sim(
        _policy_record("policy_cascade_scene"),
        clients={"chat": client},
    )
    simulator = tree.nodes[tree.root]["sim"]

    simulator.run(max_turns=1)

    prompt_text = "\n\n".join(
        str(message.get("content", ""))
        for batch in client.messages
        for message in batch
    )
    assert "<policy text>" not in prompt_text
    assert "态度：..." not in prompt_text
    assert "补充：..." not in prompt_text


def test_policy_erosion_private_broadcast_starts_from_selected_tier() -> None:
    """A scoped policy broadcast should only be visible to selected recipients first."""
    client = FakeChatClient()
    tree = simtree_runtime._build_tree_for_sim(
        _policy_record("policy_cascade_scene"),
        clients={"chat": client},
    )
    simulator = tree.nodes[tree.root]["sim"]
    tree.nodes[tree.root]["logs"].clear()

    simulator.broadcast(
        PublicEvent("Private policy update", prefix="SYSTEM BROADCAST"),
        receivers=["Manager"],
    )
    simulator.emit_remaining_events()

    logs = tree.nodes[tree.root]["logs"]
    private_inputs = [log for log in logs if log["type"] == "private_cascade_input"]
    assert [log["data"]["visible_to"] for log in private_inputs] == ["Manager"]
    assert simulator.scene.state["task_mode"] == "cascade"
    assert simulator.scene.state["current_tier_idx"] == 1
    assert set(simulator.scene.state["private_events"]) == {"Manager"}

    simulator.run(max_turns=1)

    broadcasts = [
        log
        for log in tree.nodes[tree.root]["logs"]
        if log["type"] == "system_broadcast"
        and log["data"].get("code") == "scene_chat"
    ]
    assert [(log["data"]["sender"], log["data"]["recipients"]) for log in broadcasts[-2:]] == [
        ("Manager", ["Staff"]),
        ("Staff", []),
    ]
    assert all(log["data"]["sender"] != "Director" for log in broadcasts)


def test_policy_erosion_branch_broadcast_uses_private_cascade_semantics() -> None:
    """Experiment branch broadcast ops should use the same policy semantics as host broadcast."""
    tree = simtree_runtime._build_tree_for_sim(
        _policy_record("policy_cascade_scene"),
        clients={"chat": FakeChatClient()},
    )

    child_id = tree.branch(
        tree.root,
        [
            {
                "op": "environment_event",
                "event_type": "broadcast",
                "text": "Branch-only policy update",
                "receivers": ["Manager"],
            }
        ],
    )
    simulator = tree.nodes[child_id]["sim"]

    assert simulator.scene.state["task_mode"] == "cascade"
    assert simulator.scene.state["current_tier_idx"] == 1
    assert set(simulator.scene.state["private_events"]) == {"Manager"}

    simulator.run(max_turns=1)

    branch_logs = tree.nodes[child_id]["logs"]
    private_inputs = [log for log in branch_logs if log["type"] == "private_cascade_input"]
    assert [log["data"]["visible_to"] for log in private_inputs[-1:]] == ["Manager"]
    broadcasts = [
        log
        for log in branch_logs
        if log["type"] == "system_broadcast"
        and log["data"].get("code") == "scene_chat"
    ]
    assert [(log["data"]["sender"], log["data"]["recipients"]) for log in broadcasts[-2:]] == [
        ("Manager", ["Staff"]),
        ("Staff", []),
    ]


def test_policy_erosion_forced_cascade_does_not_stall_on_localized_yield() -> None:
    """A localized yield from a small model should not leave the policy cascade empty."""
    tree = simtree_runtime._build_tree_for_sim(
        _policy_record("policy_cascade_scene"),
        clients={"chat": ChineseYieldFakeChatClient()},
    )
    simulator = tree.nodes[tree.root]["sim"]

    simulator.run(max_turns=1)

    broadcasts = [
        log
        for log in tree.nodes[tree.root]["logs"]
        if log["type"] == "system_broadcast"
        and log["data"].get("code") == "scene_chat"
    ]
    assert broadcasts
    assert [(log["data"]["sender"], log["data"]["recipients"]) for log in broadcasts[-3:]] == [
        ("Director", ["Manager"]),
        ("Manager", ["Staff"]),
        ("Staff", []),
    ]
    assert "Keep the policy wording intact." in broadcasts[0]["data"]["params"]["message"]


def test_policy_erosion_distortion_mode_emits_policy_diff_logs() -> None:
    """Distortion cascade should emit the dedicated event consumed by the policy UI."""
    tree = simtree_runtime._build_tree_for_sim(
        _policy_record("policy_cascade_scene", cascade_mode="distortion_cascade"),
        clients={"chat": DistortingFakeChatClient()},
    )
    simulator = tree.nodes[tree.root]["sim"]

    simulator.run(max_turns=1)

    distortion_logs = [
        log for log in tree.nodes[tree.root]["logs"] if log["type"] == "cascade_distortion"
    ]
    assert distortion_logs
    assert distortion_logs[0]["data"]["agent"] == "Director"
    assert "original_message" in distortion_logs[0]["data"]
    assert "final_message" in distortion_logs[0]["data"]


def test_policy_erosion_distortion_first_follow_up_does_not_auto_skip_level() -> None:
    """First follow-up discussion should not immediately become a skip-level complaint."""
    record = _policy_record("policy_cascade_scene", cascade_mode="distortion_cascade")
    record.scene_config["generic_config"]["parameters"]["policy_text"] = (
        "关于实施阶段性薪酬调整与稳岗安排的通知\n"
        "原文：\n"
        "1. 政策目标：保障组织整体稳定运行，在未来 “6 个月内” 完成目标。\n"
        "2. 调整标准：实施 “10% 的阶段性下调”。\n"
        "3. 不可改写条款：必须原样保留 “6 个月内” “10% 的阶段性下调” “保障组织整体稳定运行”。\n"
        "4. 报告要求：5个工作日内提交落实情况。"
    )
    tree = simtree_runtime._build_tree_for_sim(
        record,
        clients={"chat": DistortingFakeChatClient()},
    )
    simulator = tree.nodes[tree.root]["sim"]

    simulator.run(max_turns=1)
    before_follow_up = len(tree.nodes[tree.root]["logs"])
    for _ in range(3):
        simulator.run(max_turns=1)

    follow_up_logs = tree.nodes[tree.root]["logs"][before_follow_up:]
    opened_threads = [
        log["data"]
        for log in follow_up_logs
        if log["type"] == "policy_thread_opened"
    ]
    assert all(thread.get("kind") != "skip_level_complaint" for thread in opened_threads)


def test_policy_erosion_cascade_special_action_is_relayed_not_threaded() -> None:
    """Cascade relay should not fail when a model picks a follow-up-only action."""
    tree = simtree_runtime._build_tree_for_sim(
        _branched_policy_record(),
        clients={"chat": CascadeSpecialActionFakeChatClient()},
    )
    simulator = tree.nodes[tree.root]["sim"]

    simulator.run(max_turns=1)

    logs = tree.nodes[tree.root]["logs"]
    action_errors = [
        log
        for log in logs
        if log["type"] == "action_end"
        and "Provide 'target'" in str(log["data"].get("summary") or log["data"].get("error") or "")
    ]
    broadcasts = [
        log
        for log in logs
        if log["type"] == "system_broadcast"
        and log["data"].get("code") == "scene_chat"
    ]

    assert not action_errors
    assert ("Agent 2", ["Agent 4"]) in [
        (log["data"]["sender"], log["data"]["recipients"])
        for log in broadcasts
    ]
    assert ("Agent 4", ["Agent 6"]) in [
        (log["data"]["sender"], log["data"]["recipients"])
        for log in broadcasts
    ]


def test_policy_erosion_distortion_rejects_placeholder_cascade_draft() -> None:
    """Placeholder attitude/supplement drafts must not become transmitted policy."""
    tree = simtree_runtime._build_tree_for_sim(
        _policy_record("policy_cascade_scene", cascade_mode="distortion_cascade"),
        clients={"chat": PlaceholderCascadeFakeChatClient()},
    )
    simulator = tree.nodes[tree.root]["sim"]

    simulator.run(max_turns=1)

    broadcasts = [
        log
        for log in tree.nodes[tree.root]["logs"]
        if log["type"] == "system_broadcast"
        and log["data"].get("code") == "scene_chat"
    ]
    distortion_logs = [
        log for log in tree.nodes[tree.root]["logs"] if log["type"] == "cascade_distortion"
    ]
    assert broadcasts
    assert distortion_logs
    transmitted = [log["data"]["params"]["message"] for log in broadcasts]
    final_messages = [log["data"]["final_message"] for log in distortion_logs]

    assert all("态度：..." not in message for message in transmitted)
    assert all("补充：..." not in message for message in transmitted)
    assert all("态度：..." not in message for message in final_messages)
    assert all("补充：..." not in message for message in final_messages)
    assert any("Keep the policy wording intact." in message or "阶段" in message for message in final_messages)


def test_policy_erosion_agent_memory_does_not_replay_action_json() -> None:
    """The newui Agent boundary stores compact speech, not raw action JSON."""
    tree = simtree_runtime._build_tree_for_sim(
        _policy_record("policy_cascade_scene"),
        clients={"chat": NewUiFiveSectionFakeChatClient()},
    )
    simulator = tree.nodes[tree.root]["sim"]

    simulator.run(max_turns=1)

    broadcasts = [
        log
        for log in tree.nodes[tree.root]["logs"]
        if log["type"] == "system_broadcast"
        and log["data"].get("code") == "scene_chat"
    ]
    messages = [log["data"]["params"]["message"] for log in broadcasts]
    assert messages
    assert all('"action"' not in message and "'action'" not in message for message in messages)
    assert all('"send_message"' not in message and "'send_message'" not in message for message in messages)

    director_memory = simulator.agents["Director"].short_memory.get_all()
    assistant_entries = [
        entry["content"]
        for entry in director_memory
        if entry.get("role") == "assistant"
    ]
    assert assistant_entries
    assert all('"action"' not in entry and "'action'" not in entry for entry in assistant_entries)


def test_policy_erosion_parse_failure_retries_with_newui_contract() -> None:
    """Invalid action strings should trigger JSON retry instead of raw broadcast."""
    client = RetryThenNewUiFakeChatClient()
    tree = simtree_runtime._build_tree_for_sim(
        _policy_record("policy_cascade_scene"),
        clients={"chat": client},
    )
    simulator = tree.nodes[tree.root]["sim"]

    simulator.run(max_turns=1)

    assert client.calls >= 2
    broadcasts = [
        log
        for log in tree.nodes[tree.root]["logs"]
        if log["type"] == "system_broadcast"
        and log["data"].get("code") == "scene_chat"
    ]
    assert broadcasts
    assert all("'action'" not in log["data"]["params"]["message"] for log in broadcasts)


def test_policy_erosion_parse_failure_never_broadcasts_raw_action_string() -> None:
    """If retries fail, policy runtime should stay quiet rather than spreading JSON."""
    tree = simtree_runtime._build_tree_for_sim(
        _policy_record("policy_cascade_scene"),
        clients={"chat": AlwaysInvalidActionStringFakeChatClient()},
    )
    simulator = tree.nodes[tree.root]["sim"]

    simulator.run(max_turns=1)

    broadcasts = [
        log
        for log in tree.nodes[tree.root]["logs"]
        if log["type"] == "system_broadcast"
        and log["data"].get("code") == "scene_chat"
    ]
    assert not broadcasts


def test_policy_erosion_plain_cascade_text_is_logged_without_parse_error() -> None:
    """Small local models can transmit policy text even when they omit JSON."""
    tree = simtree_runtime._build_tree_for_sim(
        _policy_record("policy_cascade_scene"),
        clients={"chat": PlainCascadeTextFakeChatClient()},
    )
    simulator = tree.nodes[tree.root]["sim"]

    simulator.run(max_turns=1)

    logs = tree.nodes[tree.root]["logs"]
    errors = [log for log in logs if log["type"] == "agent_error"]
    broadcasts = [
        log
        for log in logs
        if log["type"] == "system_broadcast"
        and log["data"].get("code") == "scene_chat"
    ]
    assert not errors
    assert broadcasts
    assert all("'action'" not in log["data"]["params"]["message"] for log in broadcasts)
    assert all('"action"' not in log["data"]["params"]["message"] for log in broadcasts)


def test_policy_erosion_plain_cascade_yield_still_forces_required_policy_transmission() -> None:
    """Plain localized yield should not stall a forced new policy cascade."""
    tree = simtree_runtime._build_tree_for_sim(
        _policy_record("policy_cascade_scene"),
        clients={"chat": PlainCascadeYieldFakeChatClient()},
    )
    simulator = tree.nodes[tree.root]["sim"]

    simulator.run(max_turns=1)

    broadcasts = [
        log
        for log in tree.nodes[tree.root]["logs"]
        if log["type"] == "system_broadcast"
        and log["data"].get("code") == "scene_chat"
    ]
    assert broadcasts
    assert [(log["data"]["sender"], log["data"]["recipients"]) for log in broadcasts[-3:]] == [
        ("Director", ["Manager"]),
        ("Manager", ["Staff"]),
        ("Staff", []),
    ]
    assert "Keep the policy wording intact." in broadcasts[0]["data"]["params"]["message"]


def test_policy_erosion_plain_follow_up_no_action_is_logged_without_parse_error() -> None:
    """Small local models may answer late follow-up with plain text; keep it visible."""
    tree = simtree_runtime._build_tree_for_sim(
        _policy_record("policy_cascade_scene"),
        clients={"chat": FakeChatClient()},
    )
    simulator = tree.nodes[tree.root]["sim"]

    simulator.run(max_turns=1)
    simulator.clients["chat"] = PlainFollowUpNoActionFakeChatClient()
    before = len(tree.nodes[tree.root]["logs"])

    simulator.run(max_turns=1)

    new_logs = tree.nodes[tree.root]["logs"][before:]
    errors = [log for log in new_logs if log["type"] == "agent_error"]
    broadcasts = [
        log
        for log in new_logs
        if log["type"] == "system_broadcast"
        and log["data"].get("code") == "scene_chat"
    ]
    assert not errors
    assert broadcasts
    assert all("'action'" not in log["data"]["params"]["message"] for log in broadcasts)
    assert all('"action"' not in log["data"]["params"]["message"] for log in broadcasts)


def test_policy_erosion_skipped_follow_up_agent_emits_idle_log() -> None:
    """Skipped policy agents should be visible instead of disappearing from a round."""
    tree = simtree_runtime._build_tree_for_sim(
        _policy_record("policy_cascade_scene"),
        clients={"chat": FakeChatClient()},
    )
    simulator = tree.nodes[tree.root]["sim"]
    simulator.scene.state["task_mode"] = "follow_up"
    simulator.scene.state["complete"] = False
    simulator.scene.state["follow_up_no_action_agents"] = ["Director"]
    tree.nodes[tree.root]["logs"].clear()

    simulator.run(max_turns=1)

    idle_logs = [log for log in tree.nodes[tree.root]["logs"] if log["type"] == "agent_idle"]
    assert idle_logs
    assert idle_logs[0]["data"]["agent"] == "Director"
    assert "Director" in idle_logs[0]["data"]["message"]


def test_policy_erosion_routes_only_along_network_branches() -> None:
    """newui parity: a scoped policy should travel only through selected branches."""
    scene = PolicyCascadeScene("policy", "")
    scene.state["social_network"] = {
        "Agent 1": ["Agent 3"],
        "Agent 2": ["Agent 4"],
        "Agent 3": ["Agent 5"],
        "Agent 4": ["Agent 6"],
        "Agent 5": [],
        "Agent 6": [],
    }
    agents = [
        _legacy_agent("Agent 1", "top"),
        _legacy_agent("Agent 2", "top"),
        _legacy_agent("Agent 3", "mid"),
        _legacy_agent("Agent 4", "mid"),
        _legacy_agent("Agent 5", "low"),
        _legacy_agent("Agent 6", "low"),
    ]
    simulator = _legacy_simulator(scene, agents)

    simulator.broadcast(
        PublicEvent("「系统公告」 分支化传递测试\n目标：逐级传达"),
        receivers=["Agent 1", "Agent 2"],
    )

    assert set(scene._private_recipient_names()) == {"Agent 1", "Agent 2"}

    scene.parse_and_handle_action({"action": "send_message", "message": "Top route from Agent 1"}, agents[0], simulator)
    scene.post_turn(agents[0], simulator)

    upstream_3 = list((scene._private_event_for("Agent 3").get("upstream_messages") or []))
    upstream_4 = list((scene._private_event_for("Agent 4").get("upstream_messages") or []))
    assert len(upstream_3) == 1
    assert upstream_3[0].get("sender") == "Agent 1"
    assert upstream_4 == []

    scene.parse_and_handle_action({"action": "send_message", "message": "Top route from Agent 2"}, agents[1], simulator)
    scene.post_turn(agents[1], simulator)

    upstream_4 = list((scene._private_event_for("Agent 4").get("upstream_messages") or []))
    assert len(upstream_4) == 1
    assert upstream_4[0].get("sender") == "Agent 2"
    assert scene.state.get("active_tier_targets", {}).get("mid") == ["Agent 3", "Agent 4"]


def test_policy_erosion_merges_multiple_upstream_inputs_for_one_recipient() -> None:
    """newui parity: one downstream agent can see multiple upstream versions."""
    scene = PolicyCascadeScene("policy", "")
    scene.state["social_network"] = {
        "Agent 1": ["Agent 3"],
        "Agent 2": ["Agent 3"],
        "Agent 3": [],
    }
    agents = [
        _legacy_agent("Agent 1", "top"),
        _legacy_agent("Agent 2", "top"),
        _legacy_agent("Agent 3", "mid"),
    ]
    simulator = _legacy_simulator(scene, agents)

    simulator.broadcast(
        PublicEvent("「系统公告」 多上游融合测试\n目标：逐级传达"),
        receivers=["Agent 1", "Agent 2"],
    )
    scene.parse_and_handle_action({"action": "send_message", "message": "Version A from Agent 1"}, agents[0], simulator)
    scene.post_turn(agents[0], simulator)
    scene.parse_and_handle_action({"action": "send_message", "message": "Version B from Agent 2"}, agents[1], simulator)
    scene.post_turn(agents[1], simulator)

    private_event = scene._private_event_for("Agent 3")
    upstream_messages = list(private_event.get("upstream_messages") or [])

    assert len(upstream_messages) == 2
    assert any(item.get("sender") == "Agent 1" for item in upstream_messages)
    assert any(item.get("sender") == "Agent 2" for item in upstream_messages)
    assert "多个上层版本" in str(private_event.get("relayed_policy") or "")

    status_prompt = scene.get_agent_status_prompt(agents[2])
    assert "多个上层版本" in status_prompt
    assert "Agent 1" in status_prompt
    assert "Agent 2" in status_prompt


def test_policy_erosion_run_extends_until_current_cascade_tier_finishes() -> None:
    """newui parity: max_turns=1 should not split an active tier in half."""
    scene = PolicyCascadeScene("policy", "")
    scene.state["social_network"] = {
        "Agent 1": ["Agent 3"],
        "Agent 2": ["Agent 4"],
        "Agent 3": ["Agent 5"],
        "Agent 4": ["Agent 6"],
        "Agent 5": [],
        "Agent 6": [],
    }
    agents = [
        _legacy_agent("Agent 1", "top"),
        _legacy_agent("Agent 2", "top"),
        _legacy_agent("Agent 3", "mid"),
        _legacy_agent("Agent 4", "mid"),
        _legacy_agent("Agent 5", "low"),
        _legacy_agent("Agent 6", "low"),
    ]
    seen_events: list[tuple[str, dict]] = []
    simulator = _legacy_simulator(scene, agents, seen_events)

    scene.state["latest_notice"] = "「系统公告」 关于开展高风险算法应用排查与标识工作的通知"
    scene.state["latest_policy"] = "「系统公告」 关于开展高风险算法应用排查与标识工作的通知\n1. 目标：在未来 4 个月内完成排查。"
    scene.state["source_policy"] = scene.state["latest_policy"]
    scene.state["relayed_policy"] = scene.state["latest_policy"]
    scene.state["task_mode"] = "cascade"
    scene.state["notice_kind"] = "execution"
    scene.state["current_tier_idx"] = 2
    scene.state["tier_seen"] = {"top": [], "mid": [], "low": []}
    scene.state["tier_transmitted"] = {"top": True, "mid": True, "low": False}
    scene.state["active_tier_targets"] = {"low": ["Agent 5", "Agent 6"]}
    scene.state["private_events"] = {
        "Agent 5": {
            "latest_notice": scene.state["latest_notice"],
            "latest_policy": scene.state["latest_policy"],
            "source_policy": scene.state["source_policy"],
            "relayed_policy": scene.state["relayed_policy"],
            "task_mode": "cascade",
            "notice_kind": "execution",
        },
        "Agent 6": {
            "latest_notice": scene.state["latest_notice"],
            "latest_policy": scene.state["latest_policy"],
            "source_policy": scene.state["source_policy"],
            "relayed_policy": scene.state["relayed_policy"],
            "task_mode": "cascade",
            "notice_kind": "execution",
        },
    }
    scene._rebuild_tiers()

    simulator.run(max_turns=1)

    processed_agents = [
        data.get("agent")
        for event_type, data in seen_events
        if event_type == "agent_process_start"
    ]
    assert "Agent 5" in processed_agents
    assert "Agent 6" in processed_agents
    assert scene.state["complete"] is True


def test_policy_erosion_new_policy_broadcast_revives_agents_and_clears_action_trace_memory() -> None:
    """newui parity: a new policy must restart stalled/offline agents cleanly."""
    scene = PolicyCascadeScene("policy", "")
    scene.state["social_network"] = {"Top": ["Mid"], "Mid": ["Low"], "Low": []}
    agents = [
        _legacy_agent("Top", "top"),
        _legacy_agent("Mid", "mid"),
        _legacy_agent("Low", "low"),
    ]
    simulator = _legacy_simulator(scene, agents)

    agents[1].is_offline = True
    agents[1].consecutive_llm_errors = 3
    agents[1].short_memory.append("assistant", "[Action] send_message\n旧的级联动作")

    simulator.broadcast(PublicEvent("「系统公告」 新一轮级联测试\n目标：重新启动"), receivers=["Top"])

    assert agents[1].is_offline is False
    assert agents[1].consecutive_llm_errors == 0
    assert "[Action]" not in agents[1].short_memory.get_all()[0]["content"]
    assert scene.state["task_mode"] == "cascade"


def test_policy_erosion_follow_up_no_action_agent_waits_for_next_broadcast() -> None:
    """newui parity: no-action agents become idle, not failed or invisible."""
    scene = PolicyCascadeScene("policy", "", cascade_mode="strict_cascade")
    scene.state["social_network"] = {"Top": ["Mid"], "Mid": ["Low"], "Low": []}
    agents = [
        _legacy_agent("Top", "top"),
        _legacy_agent("Mid", "mid"),
        _legacy_agent("Low", "low"),
    ]
    seen_events: list[tuple[str, dict]] = []
    simulator = _legacy_simulator(scene, agents, seen_events)

    scene.state["latest_policy"] = "执行要求：继续推进落实"
    scene.state["source_policy"] = "执行要求：继续推进落实"
    scene.state["relayed_policy"] = "执行要求：继续推进落实"
    scene.state["task_mode"] = "follow_up"
    scene.state["policy_version"] = 1
    scene.state["processed_policy_version"] = 1

    scene.parse_and_handle_action(
        {"action": "send_message", "message": "当前已没有任何动作倾向，建议注入新的环境事件或发布新的政策。"},
        agents[0],
        simulator,
    )

    assert scene.should_skip_turn(agents[0], simulator) is True
    assert "等待新的环境事件或下一轮政策广播" in scene.get_skip_reason(agents[0], simulator)

    simulator.run(max_turns=1)

    top_idle = [
        data for event_type, data in seen_events
        if event_type == "agent_idle" and data.get("agent") == "Top"
    ]
    assert top_idle
    assert "等待新的环境事件或下一轮政策广播" in top_idle[0]["message"]
