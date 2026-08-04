"""
Deliberation rounds and voting for the checkpointed runner.

Runs the deliberation for a run: agents already recorded in the store are
skipped (so a resumed run never re-executes completed work), and every
remaining agent gets a prompt and a response that is recorded immediately.

LLM integration: the client factory now builds real OpenAI-compatible
clients (openai.OpenAI) pointed at the local llama.cpp router, one cached
client per voting model, using the same model-to-port routing as the
headless council runner. Live calls are only made when the environment
variable FOS_EXPERIMENT_LLM=1 is set; by default the factory returns None
and placeholder responses are recorded, so batch runs, CI, and the test
gate never touch a live model server.

Functions:
    _build_deliberation_prompt() — build the deliberation prompt for one agent
    _build_vote_prompt()         — build the voting prompt for one agent
    _agent_client()              — LLM client factory (real clients or None)
    _placeholder_response()      — response dict used in placeholder mode
    _call_agent()                — call an LLM client; return text or error
    _call_client()               — wrap a deliberation call as the record dict
    _get_vote()                  — ask one agent for its vote (yes/no/abstain)
    _parse_vote()                — turn a model reply into a vote string
    _deliberation_round()        — run a single deliberation round
    _cast_votes()                — record confederate and normal agent votes
"""

from __future__ import annotations

import json
import os
import sqlite3
from typing import Any

import openai

from fos.experiment import store
from fos.experiments import confederates as conf

# Router model-name mapping (FOS name -> GGUF name) and model-to-port
# routing, mirrored from scripts/headless_council.py so agents reach the
# llama.cpp router exactly like the headless council runner does.
# Server A (8080): gpt-oss + qwen.  Server B (8082): qwen-unc + gemma.
_LLAMACPP_ROUTER_MAP: dict[str, str] = {
    "openai/gpt-oss-20b": "gpt-oss-20b",
    "gpt-oss-20b": "gpt-oss-20b",
    "google/gemma-4-26b-a4b": "gemma-4-26b-a4b",
    "gemma-4-26b-a4b": "gemma-4-26b-a4b",
    "qwen/qwen3.6-35b-a3b": "qwen3.6-35b-a3b",
    "gemma4-26b-a4b-uncensored-hauhaucs-balanced": "gemma4-26b-a4b-uncensored",
    "qwen3.6-35b-a3b-uncensored-hauhaucs-aggressive": "qwen3.6-35b-a3b-uncensored",
}

_MODEL_PORT_MAP: dict[str, int] = {
    "openai/gpt-oss-20b": 8080,
    "qwen/qwen3.6-35b-a3b": 8080,
    "qwen3.6-35b-a3b-uncensored-hauhaucs-aggressive": 8082,
    "google/gemma-4-26b-a4b": 8082,
    "gemma4-26b-a4b-uncensored-hauhaucs-balanced": 8082,
}

_LLM_TIMEOUT_S = float(os.environ.get("FOS_LLM_TIMEOUT_S", "120"))

# One cached client per voting model so a run reuses connections.
_CLIENTS: dict[str, openai.OpenAI] = {}


def _llm_enabled() -> bool:
    """Return True when the runner is allowed to make real LLM calls.

    Live calls are off by default (FOS_EXPERIMENT_LLM=1 turns them on) so
    batch runs, CI, and the test gate never contact a live model server.
    """
    return os.environ.get("FOS_EXPERIMENT_LLM", "0") == "1"


def _base_url_for_model(model: str) -> str:
    """Return the llama.cpp router base URL for a voting model."""
    host = os.environ.get("FOS_LLM_HOST", "localhost")
    port = _MODEL_PORT_MAP.get(model, 8080)
    return f"http://{host}:{port}/v1"


def _build_deliberation_prompt(
    agent_config: dict[str, Any], round_idx: int, proposal_statement: str
) -> str:
    """Build the deliberation prompt for one agent in one round.

    Follows the headless council style: a persona line with the agent's
    background, the proposal text, the confederate instruction when the
    agent is a confederate, and a closing instruction to state a view.
    """
    parts = [
        f"You are {agent_config['agent_id']}, a member of a council debating a "
        f"proposal. This is deliberation round {round_idx} of 3.",
    ]
    bio = agent_config.get("bio")
    if bio:
        parts.append(f"Your background: {bio}")
    parts.append(f"Proposal: {proposal_statement}")
    conf_prompt = agent_config.get("confederate_prompt")
    if conf_prompt:
        parts.append(conf_prompt)
    parts.append("State your view on the proposal in one short paragraph.")
    return "\n\n".join(parts)


def _build_vote_prompt(
    agent_config: dict[str, Any],
    proposal_statement: str,
    neighbour_votes: dict[str, str] | None = None,
) -> str:
    """Build the voting prompt for one agent after deliberation ends.

    Lists any neighbour votes the agent may have heard, then asks for a
    one-word reply: yes, no, or abstain.
    """
    parts = [
        f"You are {agent_config['agent_id']}, a member of a council that has "
        f"finished deliberating the following proposal.",
        f"Proposal: {proposal_statement}",
    ]
    if neighbour_votes:
        shown = ", ".join(f"{uid}: {vote}" for uid, vote in neighbour_votes.items())
        parts.append(f"Votes you have heard from your neighbours: {shown}.")
    parts.append('Reply with exactly one word: "yes", "no", or "abstain".')
    return "\n\n".join(parts)


def _agent_client(agent_config: dict[str, Any]) -> Any:
    """Return the LLM client for an agent, or None to use placeholder mode.

    When FOS_EXPERIMENT_LLM=1 this builds a real OpenAI-compatible client
    (openai.OpenAI) for the agent's voting model, routed to the llama.cpp
    port that serves that model, and caches one client per model. Without
    the env flag it returns None so runs never make live calls; tests
    monkeypatch this function to inject a fake client.
    """
    if not _llm_enabled():
        return None
    model = agent_config["voting_model"]
    if model not in _CLIENTS:
        client = openai.OpenAI(
            base_url=_base_url_for_model(model),
            api_key="not-needed",
            timeout=_LLM_TIMEOUT_S,
            max_retries=0,
        )
        # Remember the router model name so the chat call can name it.
        client._voting_model = _LLAMACPP_ROUTER_MAP.get(model, model)
        _CLIENTS[model] = client
    return _CLIENTS[model]


def _placeholder_response(
    agent_config: dict[str, Any], round_idx: int, prompt: str
) -> dict[str, Any]:
    """Response dict recorded in placeholder mode (no LLM calls yet)."""
    return {
        "placeholder": True,
        "round": round_idx,
        "agent_uid": agent_config["agent_id"],
        "prompt": prompt,
        "text": "PLACEHOLDER",
    }


def _call_agent(client: Any, system_prompt: str, user_prompt: str) -> dict[str, Any]:
    """Call an LLM client and return a dict with the response text.

    Two client interfaces are supported so tests can inject FakeLLMClient:
      * a callable client.chat(messages, json_mode, max_tokens) -> str
        (the codebase LLMClient contract, matched by FakeLLMClient), and
      * an openai.OpenAI client with client.chat.completions.create(...).
    Errors on the real OpenAI path are caught and reported as an error
    indicator so a run never crashes when the model server is unavailable.
    Errors raised by the chat() interface are NOT caught, so injected test
    failures still propagate to the runner.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    chat_attr = getattr(client, "chat", None)
    if callable(chat_attr):
        text = chat_attr(messages=messages, json_mode=True, max_tokens=500)
        return {"text": str(text)}
    model = getattr(client, "_voting_model", None) or "default"
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
            max_tokens=500,
        )
    except Exception as exc:  # API/network error: record it, keep the run going
        return {"text": "", "error": f"{type(exc).__name__}: {exc}"}
    text = ""
    if completion.choices:
        text = completion.choices[0].message.content or ""
    result: dict[str, Any] = {"text": text}
    usage = getattr(completion, "usage", None)
    if usage is not None:
        result["usage"] = {
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
        }
    return result


def _call_client(
    client: Any, agent_config: dict[str, Any], round_idx: int, prompt: str
) -> dict[str, Any]:
    """Call an LLM client and return the response dict to record."""
    system_prompt = f"agent_uid={agent_config['agent_id']} round_index={round_idx}"
    result = _call_agent(client, system_prompt, prompt)
    response: dict[str, Any] = {
        "placeholder": False,
        "round": round_idx,
        "agent_uid": agent_config["agent_id"],
        "prompt": prompt,
    }
    response.update(result)
    return response


def _parse_vote(text: str) -> str:
    """Turn a model reply into 'yes', 'no', or 'abstain'."""
    lowered = text.strip().lower()
    for vote in ("abstain", "yes", "no"):
        if vote in lowered:
            return vote
    return "abstain"


def _get_vote(
    client: Any,
    agent_config: dict[str, Any],
    proposal_statement: str,
    neighbour_votes: dict[str, str] | None = None,
) -> str:
    """Ask one agent for its vote and parse the reply.

    Returns 'yes', 'no', or 'abstain'; an unparseable or failed reply
    counts as 'abstain' so a broken model call never crashes the run.
    """
    system_prompt = f"agent_uid={agent_config['agent_id']} vote=1"
    user_prompt = _build_vote_prompt(agent_config, proposal_statement, neighbour_votes)
    result = _call_agent(client, system_prompt, user_prompt)
    return _parse_vote(result.get("text", ""))


def _deliberation_round(
    run_id: str,
    round_idx: int,
    run_agents: list[dict[str, Any]],
    proposal_statement: str,
    conn: sqlite3.Connection | None = None,
) -> None:
    """Run one deliberation round, skipping agents already recorded.

    Agents whose call is already in the store (from a previous interrupted
    run) are skipped so a resumed run never re-executes completed work.
    """
    existing = {
        call["agent_uid"] for call in store.get_agent_calls(run_id, round_idx, conn)
    }
    for agent in run_agents:
        uid = agent["agent_id"]
        if uid in existing:
            continue
        prompt = _build_deliberation_prompt(agent, round_idx, proposal_statement)
        client = _agent_client(agent)
        if client is None:
            response = _placeholder_response(agent, round_idx, prompt)
        else:
            response = _call_client(client, agent, round_idx, prompt)
        store.record_agent_call(run_id, round_idx, uid, json.dumps(response), conn)
    store.record_progress(run_id, f"round_{round_idx}", conn)


def _cast_votes(
    run_agents: list[dict[str, Any]], conf_specs: list[conf.ConfederateSpec]
) -> dict[str, str]:
    """Record confederate votes directly and 'abstain' for everyone else."""
    votes: dict[str, str] = {agent["agent_id"]: "abstain" for agent in run_agents}
    state_extensions: dict[str, Any] = {}
    for spec in conf_specs:
        conf.record_confederate_vote(spec, state_extensions)
    votes.update(state_extensions.get("votes", {}))
    conf.assert_confederate_votes(conf_specs, state_extensions)
    return votes
