"""
Deliberation rounds and voting for the checkpointed runner.

Runs the deliberation for a run: agents already recorded in the store are
skipped (so a resumed run never re-executes completed work), and every
remaining agent gets a prompt and a response that is recorded immediately.
Phase 2A has no LLM integration: the client factory returns None and
placeholder responses are recorded. Voting writes confederate stances
directly and 'abstain' for everyone else.

Functions:
    _build_prompt()         — build the deliberation prompt for one agent
    _agent_client()         — LLM client factory (None = placeholder mode)
    _placeholder_response() — response dict used in placeholder mode
    _call_client()          — call an LLM client and wrap its response
    _deliberation_round()   — run a single deliberation round
    _cast_votes()           — record confederate and normal agent votes
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from fos.experiment import store
from fos.experiments import confederates as conf


def _build_prompt(
    agent_config: dict[str, Any], round_idx: int, proposal_statement: str
) -> str:
    """Build the deliberation prompt for one agent in one round."""
    parts = [
        f"You are {agent_config['agent_id']}, a member of a council debating a "
        f"proposal. This is deliberation round {round_idx} of 3.",
        f"Proposal: {proposal_statement}",
    ]
    conf_prompt = agent_config.get("confederate_prompt")
    if conf_prompt:
        parts.append(conf_prompt)
    parts.append("State your view on the proposal in one short paragraph.")
    return "\n\n".join(parts)


def _agent_client(agent_config: dict[str, Any]) -> Any:
    """Return the LLM client for an agent, or None to use placeholder mode.

    Phase 2A has no LLM integration, so this always returns None and every
    call writes a PLACEHOLDER response. Tests monkeypatch this function to
    inject a fake client.
    """
    return None


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


def _call_client(
    client: Any, agent_config: dict[str, Any], round_idx: int, prompt: str
) -> dict[str, Any]:
    """Call an LLM client and return the response dict to record."""
    messages = [
        {
            "role": "system",
            "content": f"agent_uid={agent_config['agent_id']} round_index={round_idx}",
        },
        {"role": "user", "content": prompt},
    ]
    raw = client.chat(messages=messages, json_mode=True)
    return {
        "placeholder": False,
        "round": round_idx,
        "agent_uid": agent_config["agent_id"],
        "prompt": prompt,
        "text": raw,
    }


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
        prompt = _build_prompt(agent, round_idx, proposal_statement)
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
