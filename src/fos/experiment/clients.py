"""
LLM client wrappers and factories for the checkpointed runner.

Builds the clients dict the FOS adapter expects and, in the test path, wraps
the injected fake client in a TrackedClient that records every chat call so
the runner can later attribute prompts to agents and rounds.

Functions:
    TrackedClient      — records every chat call and splits calls by round
    _llm_enabled()     — whether real LLM calls are allowed (FOS_EXPERIMENT_LLM)
    _model_client()    — build (and cache) a real FOS LLMClient per model
    _agent_client()    — default chat client for a run (tests replace this)
    _build_clients()   — the clients dict passed to the FOS adapter
"""

from __future__ import annotations

import os
from typing import Any

# Router model-name mapping (FOS name -> GGUF name) and model-to-port routing,
# mirrored from scripts/headless_council.py so agents reach the llama.cpp
# router exactly like the headless council runner does.
LLAMACPP_ROUTER_MAP: dict[str, str] = {
    "openai/gpt-oss-20b": "gpt-oss-20b",
    "gpt-oss-20b": "gpt-oss-20b",
    "google/gemma-4-26b-a4b": "gemma-4-26b-a4b",
    "gemma-4-26b-a4b": "gemma-4-26b-a4b",
    "qwen/qwen3.6-35b-a3b": "qwen3.6-35b-a3b",
    "gemma4-26b-a4b-uncensored-hauhaucs-balanced": "gemma4-26b-a4b-uncensored",
    "qwen3.6-35b-a3b-uncensored-hauhaucs-aggressive": "qwen3.6-35b-a3b-uncensored",
}

MODEL_PORT_MAP: dict[str, int] = {
    "openai/gpt-oss-20b": 8080,
    "qwen/qwen3.6-35b-a3b": 8080,
    "qwen3.6-35b-a3b-uncensored-hauhaucs-aggressive": 8082,
    "google/gemma-4-26b-a4b": 8082,
    "gemma4-26b-a4b-uncensored-hauhaucs-balanced": 8082,
}

_LLM_TIMEOUT_S = float(os.environ.get("FOS_LLM_TIMEOUT_S", "120"))
_CLIENTS: dict[str, Any] = {}


class TrackedClient:
    """Wraps an LLM client and records every chat call for result extraction.

    Records the prompt text, the response text, any usage metadata the
    wrapped client exposes, and splits the calls by round so the runner can
    attribute prompts to agents and rounds afterwards.
    """

    def __init__(self, inner: Any):
        """Store the wrapped client and reset the call history."""
        self._inner = inner
        self.calls: list[dict[str, Any]] = []
        self.round_calls: dict[int, list[dict[str, Any]]] = {}
        self._round_start = 0

    def __getattr__(self, name: str) -> Any:
        """Delegate unknown attributes to the wrapped client."""
        return getattr(self._inner, name)

    def chat(self, messages: list[dict[str, Any]], json_mode: bool = False, max_tokens: int | None = None) -> Any:
        """Record one call, then delegate to the wrapped client."""
        prompt = "".join(str(m.get("content", "")) for m in messages)
        entry: dict[str, Any] = {"prompt": prompt, "response": "", "error": None, "usage": None}
        try:
            response = self._inner.chat(messages, json_mode=json_mode, max_tokens=max_tokens)
            entry["response"] = str(response or "")
            entry["usage"] = getattr(self._inner, "last_usage", None)
            return response
        except Exception as exc:
            entry["error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            self.calls.append(entry)

    def begin_round(self, round_idx: int) -> None:
        """Mark the start of a round's calls."""
        self._round_start = len(self.calls)

    def end_round(self, round_idx: int) -> None:
        """Record the slice of calls that happened during one round."""
        self.round_calls[round_idx] = self.calls[self._round_start:]

    def preload_rounds(self, round_calls: dict[int, list[dict[str, Any]]]) -> None:
        """Restore previously completed rounds' calls (resume path)."""
        self.round_calls.update(round_calls)


# ── Client factory ───────────────────────────────────────────────────────────


def _llm_enabled() -> bool:
    """Return True when the runner is allowed to make real LLM calls.

    Live calls are off by default (FOS_EXPERIMENT_LLM=1 turns them on) so
    CI and the test gate never contact a live model server. Tests replace
    _agent_client with a fake.
    """
    return os.environ.get("FOS_EXPERIMENT_LLM", "0") == "1"


def _model_client(model: str) -> Any:
    """Build (and cache) a real FOS LLMClient for a voting model."""
    from fos.core.llm.client import LLMClient
    from fos.core.llm_config import LLMConfig

    if model not in _CLIENTS:
        port = MODEL_PORT_MAP.get(model, 8080)
        base_url = f"http://{os.environ.get('FOS_LLM_HOST', 'localhost')}:{port}/v1"
        config = LLMConfig(
            dialect="openai",
            model=LLAMACPP_ROUTER_MAP.get(model, model),
            api_key="not-needed",
            base_url=base_url,
            temperature=0.7,
        )
        _CLIENTS[model] = LLMClient(config)
    return _CLIENTS[model]


def _agent_client(agent_config: dict[str, Any] | None = None) -> Any:
    """Return the LLM client used as the run's default chat client.

    Tests monkeypatch this function to inject a FakeLLMClient.
    """
    if not _llm_enabled():
        return None
    model = (agent_config or {}).get("voting_model") or "openai/gpt-oss-20b"
    return _model_client(model)


def _build_clients(run_agents: list[dict[str, Any]]) -> tuple[dict[str, Any], TrackedClient | None]:
    """Build the clients dict passed to the FOS adapter.

    Real path (FOS_EXPERIMENT_LLM=1): the default client is untracked and
    each agent gets its own tracked per-model client via provider_id, so the
    per-agent model distribution is preserved while every call is recorded.
    Test path: the injected fake is wrapped in one shared tracked client.
    """
    default = _agent_client(run_agents[0] if run_agents else None)
    if default is None:
        raise RuntimeError("FOS_EXPERIMENT_LLM is not set — no LLM client available")
    from fos.core.llm.client import LLMClient

    if isinstance(default, LLMClient):
        providers: dict[str, TrackedClient] = {}
        models = sorted({a.get("voting_model", "openai/gpt-oss-20b") for a in run_agents})
        for idx, model in enumerate(models):
            providers[f"provider_{idx}"] = TrackedClient(_model_client(model))
        model_to_pid = {model: f"provider_{idx}" for idx, model in enumerate(models)}
        for agent in run_agents:
            agent["provider_id"] = model_to_pid[agent.get("voting_model", "openai/gpt-oss-20b")]
        return {"chat": default, "default": default, "providers": providers}, None

    tracker = TrackedClient(default)
    return {"chat": tracker, "default": tracker, "providers": {}}, tracker
