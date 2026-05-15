"""Minimal Pipeline B Agent class.

Used by policy_cascade and simtree_runtime legacy path.
Pending Pipeline A port.
See docs/plans/policy-cascade-port-investigation.md

Contains: Agent
"""

# TODO: Port PolicyCascadeScene to Pipeline A (ExperimentScene
# subclass) and delete this file. See:
# docs/plans/policy-cascade-port-investigation.md


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
        self.consecutive_llm_errors = 0
        self.is_offline = False
        self.short_memory = Agent._ShortMemory()

    def add_env_feedback(self, msg: str) -> None:
        self.short_memory.append("system", msg)

    def set_global_knowledge(self, knowledge: list) -> None:
        self.knowledge_base = knowledge

    @classmethod
    def deserialize(cls, data: dict) -> "Agent":
        props = data.get("properties", {})
        return cls(
            name=data["name"],
            properties=props,
            role_prompt=data.get("role_prompt") or data.get("rolePrompt", ""),
            user_profile=data.get("user_profile") or data.get("userProfile", ""),
            language=data.get("language", "en"),
            action_space=data.get("action_space") or data.get("actionSpace", []),
            knowledge_base=data.get("knowledge_base") or data.get("knowledgeBase", []),
            documents=data.get("documents", {}),
            score=data.get("score", 0),
        )
