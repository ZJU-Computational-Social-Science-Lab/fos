"""
Execution loop for the checkpointed experiment runner.

Runs one experiment run end to end: rebuilds and verifies the network,
loads and sha256-checks the population, places agents and confederates
deterministically, runs three deliberation rounds, casts votes, and writes
the result file atomically. Phase 2A has no LLM integration yet, so
deliberation and votes are placeholders; the SIGINT handler leaves a run
marked 'running' so a later invocation can resume it.

Functions:
    run()                   — execute pending runs (or one specific run)
    retry()                 — reset failed runs back to pending
    _execute_one_run()      — run the full pipeline for a single run
    _check_interrupted()    — raise RunInterrupted when SIGINT arrived
    _matrix_row()           — one row of the run matrix CSV
    _load_population()      — load and sha256-verify a population file
    _proposal_statement()   — statement text for a proposal id
    _derive_placement()     — compute permutation, confederates, agent copies
    _build_result()         — assemble the full result dict
    _write_result_atomically() — fsync then os.replace the result file
"""

from __future__ import annotations

import copy
import csv
import hashlib
import json
import os
import random
import signal
import sqlite3
import traceback
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from fos.experiment import deliberation, network, store
from fos.experiments import confederates as conf
from fos.proposals import load_proposals

REPO_ROOT = store.REPO_ROOT
RUN_MATRIX_PATH = store.RUN_MATRIX_PATH
POPULATIONS_DIR = REPO_ROOT / "data" / "populations"
RESULTS_DIR = store.RESULTS_DIR

CONFEDERATE_N_YES = 3
CONFEDERATE_N_NO = 3
DELIBERATION_ROUNDS = (1, 2, 3)


class RunInterrupted(Exception):
    """Raised between run steps when a SIGINT was received."""


# ── SIGINT handling ─────────────────────────────────────────────────────────

_interrupted = False


def _handle_sigint(signum: int, frame: Any) -> None:
    """Record the interrupt; the run loop stops at the next step boundary."""
    global _interrupted
    _interrupted = True


signal.signal(signal.SIGINT, _handle_sigint)


def _check_interrupted(run_id: str, stage: str) -> None:
    """Raise RunInterrupted when SIGINT arrived since the last check."""
    if _interrupted:
        raise RunInterrupted(f"Interrupted during {stage} for run {run_id}")


# ── Public commands ──────────────────────────────────────────────────────────


def run(
    limit: int | None = None,
    run_id: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> int:
    """Execute pending runs, or one specific run; returns how many completed.

    Recover crashed 'running' runs first, then process runs in execution
    order. A NetworkMismatchError aborts the whole batch; any other failure
    marks that run failed and moves on; an interrupt stops the batch with
    the current run still marked 'running'.
    """
    global _interrupted
    _interrupted = False
    store.reset_stale_runs(conn)
    if run_id is not None:
        run_row = store.get_run(run_id, conn)
        if run_row is None:
            print(f"Unknown run {run_id}")
            return 0
        if run_row["status"] == "complete":
            print(f"Run {run_id} already complete")
            return 0
        targets = [run_row]
    else:
        try:
            targets = store.list_runs(status="pending", conn=conn)
        except sqlite3.OperationalError:
            print(
                "State store not initialised — run 'python -m fos.experiment init' first"
            )
            return 0
        if limit is not None:
            targets = targets[:limit]
    if not targets:
        print("No runs to execute")
        return 0

    executed = 0
    for run_row in targets:
        if _interrupted:
            print("Interrupted — batch stopped (no run was in progress)")
            break
        try:
            _execute_one_run(run_row["run_id"], conn)
            executed += 1
        except network.NetworkMismatchError as exc:
            print(f"ABORT: {exc}")
            break
        except RunInterrupted as exc:
            print(f"{exc} — run left in 'running' state")
            break
        except Exception as exc:
            store.mark_failed(run_row["run_id"], traceback.format_exc(), conn)
            print(f"Run {run_row['run_id']} FAILED: {exc}")
            continue
    return executed


def retry(conn: sqlite3.Connection | None = None) -> int:
    """Reset every failed run back to pending; prints and returns the count."""
    count = store.reset_failed_runs(conn)
    if count:
        print(f"Reset {count} failed run(s) to pending")
    else:
        print("No failed runs to reset")
    return count


# ── Per-run pipeline ─────────────────────────────────────────────────────────


def _execute_one_run(run_id: str, conn: sqlite3.Connection | None = None) -> None:
    """Run the full pipeline for one run id (see module docstring for steps)."""
    store.mark_running(run_id, conn)
    run_row = store.get_run(run_id, conn)
    if run_row is None:
        raise ValueError(f"Unknown run {run_id}")
    matrix = _matrix_row(run_id)
    config = network._load_network_config(int(run_row["config_id"]))
    network_seed = int(matrix["network_seed"])
    proposal_id = run_row["proposal_id"]
    network_label = network._network_label(config)

    # Step 2 — rebuild the network and verify it against the expected stats.
    edges = network._build_network(config, network_seed)
    expected = network._load_expected_stats(
        int(run_row["config_id"]), proposal_id, network_seed
    )
    network_stats = network._verify_network(edges, expected)
    store.record_progress(run_id, "network_built", conn)
    _check_interrupted(run_id, "network_built")

    # Step 3 — load the population and check its sha256.
    agents = _load_population(run_row["population_id"])
    proposal_statement = _proposal_statement(proposal_id)

    # Step 4 — placement: permutation, confederates, per-run agent copies.
    placement = _derive_placement(matrix, config, agents, proposal_statement)
    store.record_agent_call(
        run_id,
        0,
        "_placement",
        json.dumps(
            {
                "confederates": [
                    {
                        "agent_id": s.agent_id,
                        "stance": s.stance,
                        "speech_mode": s.speech_mode,
                    }
                    for s in placement["confederates"]
                ],
                "node_permutation": placement["permuted"],
                "placement_seed": placement["placement_seed"],
                "network_label": network_label,
            }
        ),
        conn,
    )
    store.record_progress(run_id, "placement_done", conn)
    _check_interrupted(run_id, "placement_done")

    # Step 5 — three deliberation rounds (placeholder responses for now).
    for round_idx in DELIBERATION_ROUNDS:
        deliberation._deliberation_round(
            run_id, round_idx, placement["run_agents"], proposal_statement, conn
        )
        _check_interrupted(run_id, f"round_{round_idx}")

    # Step 6 — voting: confederates vote their stance, everyone else abstains.
    votes = deliberation._cast_votes(placement["run_agents"], placement["confederates"])
    store.record_progress(run_id, "votes_cast", conn)
    _check_interrupted(run_id, "votes_cast")

    # Step 7 — write the result file atomically.
    result = _build_result(
        run_id, run_row, matrix, config, placement, edges, network_stats, votes, conn
    )
    output_path = _write_result_atomically(run_id, result)
    store.record_progress(run_id, "written", conn)

    # Step 8 — mark the run complete.
    store.mark_complete(run_id, output_path, conn)
    print(f"Run {run_id} complete -> {output_path}")


# ── Data loading ─────────────────────────────────────────────────────────────


def _matrix_row(run_id: str) -> dict[str, str]:
    """Return the run matrix CSV row for a run id."""
    with RUN_MATRIX_PATH.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["run_id"] == run_id:
                return row
    raise ValueError(f"run_id {run_id} not in run matrix")


def _load_population(population_id: str) -> list[dict[str, Any]]:
    """Load a population file, verify its sha256, and return its agents."""
    path = POPULATIONS_DIR / f"{population_id}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    stored = data.pop("sha256", None)
    if stored is None:
        raise ValueError(f"population {population_id} has no sha256 field")
    payload = json.dumps(data, sort_keys=True, ensure_ascii=False)
    recomputed = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    if stored != recomputed:
        raise ValueError(
            f"population {population_id} sha256 mismatch: "
            f"stored {stored}, recomputed {recomputed}"
        )
    return data["agents"]


def _proposal_statement(proposal_id: str) -> str:
    """Return the statement text for a proposal id."""
    for proposal in load_proposals():
        if proposal.id == proposal_id:
            return proposal.statement
    raise ValueError(f"unknown proposal id {proposal_id}")


# ── Placement ────────────────────────────────────────────────────────────────


def _derive_placement(
    matrix: dict[str, str],
    config: dict[str, Any],
    agents: list[dict[str, Any]],
    proposal_statement: str,
) -> dict[str, Any]:
    """Compute the deterministic placement for a run.

    Placement uses branch 0 of the placement seed; confederate assignment
    uses branch 1, so the two randomisations never overlap. Returns the
    permuted node assignment, the confederate specs, and deep copies of the
    agent configs with confederate prompts injected on the copy.
    """
    agent_names = [agent["agent_id"] for agent in agents]
    base = int(matrix["placement_seed"])
    label = network._network_label(config)
    proposal_id = matrix["proposal_id"]
    placement_seed = conf.derive_placement_seed(base, proposal_id, label, 0)
    confederate_seed = conf.derive_placement_seed(base, proposal_id, label, 1)
    placement_rng = random.Random(placement_seed)
    confederate_rng = random.Random(confederate_seed)

    permuted = conf.permute_node_assignment(agent_names, placement_rng)
    conf_specs = conf.assign_confederates(
        agent_names,
        n_yes=CONFEDERATE_N_YES,
        n_no=CONFEDERATE_N_NO,
        rng=confederate_rng,
        speech_mode="llm",
    )
    lookup = conf.build_confederate_lookup(conf_specs)

    run_agents: list[dict[str, Any]] = []
    for agent in agents:
        run_agent = copy.deepcopy(agent)
        spec = lookup.get(agent["agent_id"])
        if spec is not None:
            run_agent["confederate_prompt"] = conf.confederate_system_prompt(
                spec, proposal_statement
            )
            run_agent["confederate_stance"] = spec.stance
        else:
            run_agent["confederate_prompt"] = None
            run_agent["confederate_stance"] = ""
        run_agents.append(run_agent)

    return {
        "agent_names": agent_names,
        "permuted": permuted,
        "confederates": conf_specs,
        "placement_seed": placement_seed,
        "run_agents": run_agents,
    }


# ── Result file ──────────────────────────────────────────────────────────────


def _build_result(
    run_id: str,
    run_row: dict[str, Any],
    matrix: dict[str, str],
    config: dict[str, Any],
    placement: dict[str, Any],
    edges: list[list[str]],
    network_stats: dict[str, Any],
    votes: dict[str, str],
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Assemble the full result dict: run-level, per-agent, and deliberation."""
    relabeled_edges = conf.relabel_edges(
        edges, network.AGENT_NAMES, placement["permuted"]
    )
    degree_counts = Counter(node for pair in relabeled_edges for node in pair)
    node_of = {name: idx for idx, name in enumerate(placement["permuted"])}
    lookup = conf.build_confederate_lookup(placement["confederates"])

    agents_out: list[dict[str, Any]] = []
    for agent in placement["run_agents"]:
        uid = agent["agent_id"]
        spec = lookup.get(uid)
        agents_out.append(
            {
                "agent_uid": uid,
                "big_five": agent["big_five"],
                "voting_model": agent["voting_model"],
                "is_confederate": spec is not None,
                "confederate_stance": spec.stance if spec is not None else "",
                "degree": degree_counts.get(uid, 0),
                "node_label": node_of.get(uid, -1),
                "vote": votes.get(uid, "abstain"),
            }
        )

    deliberation_out: list[dict[str, Any]] = []
    for call in store.get_agent_calls(run_id, conn=conn):
        if call["round_index"] < 1:
            continue
        response = json.loads(call["response_json"])
        deliberation_out.append(
            {
                "round": call["round_index"],
                "agent_uid": call["agent_uid"],
                "text": response.get("text", ""),
                "prompt": response.get("prompt", ""),
            }
        )

    return {
        "run_id": run_id,
        "schema_version": "1.0",
        "config_id": int(run_row["config_id"]),
        "proposal_id": run_row["proposal_id"],
        "population_id": run_row["population_id"],
        "generator": config["generator"],
        "network_label": network._network_label(config),
        "network_seed": int(matrix["network_seed"]),
        "placement_seed": placement["placement_seed"],
        "network_stats": network_stats,
        "confederates": [
            {"agent_id": s.agent_id, "stance": s.stance, "speech_mode": s.speech_mode}
            for s in placement["confederates"]
        ],
        "node_permutation": placement["permuted"],
        "agents": agents_out,
        "deliberation": deliberation_out,
        "completed_at": _now_iso(),
    }


def _write_result_atomically(run_id: str, payload: dict[str, Any]) -> str:
    """Write the result file via temp file + fsync + atomic rename."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = RESULTS_DIR / f"{run_id}.json.tmp"
    final_path = RESULTS_DIR / f"{run_id}.json"
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, final_path)
    return f"runs/results/{run_id}.json"


def _now_iso() -> str:
    """Current UTC time in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()
