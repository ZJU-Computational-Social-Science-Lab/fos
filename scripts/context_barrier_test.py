#!/usr/bin/env python3
"""
context_barrier_test.py — a standalone test that checks whether agents with
big social networks run out of context during a council deliberation.

What this script does, in plain words:
- Loads 30 agent profiles from artifacts/Seed_8_Full/profiles_seed8.json.
- Builds a hand-made social network where agent_1 talks to everyone (a "star"),
  and agents 2-7 get extra connections until they reach their degree targets.
- Runs only Proposal K (household privacy norms) for 4 turns (3 deliberation
  rounds + 1 voting round) on two local llama.cpp models.
- Prints a table showing, per agent: name, degree, how many of the 4 rounds it
  finished, and any context-overflow errors it hit.
- Saves the same information as a CSV under artifacts/context_barrier_test/.

Functions (one job each): load_profiles (read the first N profiles),
make_agent_llm_config (LLM settings for one llama-server port), build_agent_configs
(profiles -> agent configs, 15 per model), _edge_key/_neighbors (edge helpers),
_pick_partner (choose the best new neighbour), _try_add_edge (add one edge),
build_degree_network (star, then top up agents 2-7 to targets), make_client
(LLM client for a local model), check_servers (verify model manager + llama-servers
respond), warmup_models (load both models and send a warm-up chat), run_council
(run Proposal K for 4 turns, return logs), is_overflow (is this a context-overflow
message?), collect_results (logs -> one result row per agent), print_results_table
(print the table), write_csv (save results as CSV), main (run everything).

Note on degree targets: the requested sequence is not fully realisable —
agent_2 needs 23 extra neighbours but only 12 agents (3-14) have any degree
left, so agents 8-30 necessarily end up above their targets. The script
reports the real degrees next to the targets.
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Make the fos package importable without a pip install.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

# Load .env so FOS_* environment variables are available.
try:
    from dotenv import load_dotenv

    load_dotenv(_REPO_ROOT / ".env")
except ImportError:
    pass

from fos.backend.services.simtree_runtime import ExperimentRunnerAdapter
from fos.core.experiment.config import ExperimentConfig
from fos.core.experiment.scenes.council_experiment import CouncilExperimentScene
from fos.core.llm.client import LLMClient
from fos.core.llm_config import LLMConfig
from fos.core.simtree import SimTree

PROFILES_PATH = _REPO_ROOT / "artifacts" / "Seed_8_Full" / "profiles_seed8.json"
# Outputs (results + LLM traffic log) go under the local data repo, honoring
# FOS_DATA_DIR when set — never into the fos source checkout.
_DATA_BASE = Path(
    os.environ.get("FOS_DATA_DIR") or os.path.expanduser("~/work/fos-data")
)
OUTPUT_DIR = _DATA_BASE / "artifacts" / "context_barrier_test"

NUM_AGENTS = 30
TURNS = 4  # 3 deliberation rounds + 1 voting round
DELIBERATION_ROUNDS = 3

# Which llama-server each model lives on, and what the router calls it.
MODELS: dict[str, dict[str, Any]] = {
    "google/gemma-4-26b-a4b": {"router": "gemma-4-26b-a4b", "base_url": "http://127.0.0.1:8082/v1", "port": 8082},
}
MODEL_MANAGER_URL = os.getenv("FOS_MODEL_MANAGER_URL", "http://127.0.0.1:8081")

PROPOSAL_K_LABEL = "Proposal K — Household Privacy Norms"
PROPOSAL_K_TEXT = (
    "Reading a partner's or family member's phone messages without "
    "asking is acceptable when there is no specific reason to suspect "
    "anything is wrong, rather than being a privacy violation "
    "regardless of suspicion."
)

# Error phrases that mean "the prompt did not fit in the context window": the
# first two are exact llama.cpp server messages, the last two are client-side
# overflow errors the fos code raises.
OVERFLOW_PHRASES: tuple[str, ...] = (
    "context size has been exceeded",
    "exceeds the available context",
    "exceeds context size",
    "prompt too large",
)

# Target degree per agent, in agent order. agent_1 is the star hub.
TARGET_DEGREES: list[int] = [29, 24, 19, 14, 9, 4, 3] + [2] * 7 + [1] * 16


@dataclass
class AgentRunResult:
    """One row of results for one agent after the council run."""

    name: str
    model: str
    degree: int
    target_degree: int
    rounds_completed: int
    total_rounds: int
    overflow_count: int
    overflow_messages: list[str] = field(default_factory=list)
    other_errors: list[str] = field(default_factory=list)

    @property
    def completed_all(self) -> bool:
        """True when the agent finished every round without failing."""
        return self.rounds_completed >= self.total_rounds


def load_profiles(path: Path, count: int) -> list[dict[str, Any]]:
    """Read agent profiles from the JSON file and return the first `count`."""
    with path.open("r", encoding="utf-8") as f:
        profiles = json.load(f)
    if not isinstance(profiles, list):
        raise ValueError(f"Expected a list of profiles in {path}, got {type(profiles).__name__}")
    return profiles[:count]


def make_agent_llm_config(model_key: str) -> dict[str, Any]:
    """Build the LLM settings that send one agent to the right llama-server port."""
    info = MODELS[model_key]
    return {
        "dialect": "openai",
        "model": info["router"],
        "base_url": info["base_url"],
        "api_key": os.getenv("OPENAI_API_KEY", "not-needed"),
        "temperature": 0.7,
    }


def build_agent_configs(profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Turn profiles into agent configs, giving the first 15 agents model A and the rest model B."""
    model_keys = list(MODELS.keys())
    per_model = (len(profiles) + len(model_keys) - 1) // len(model_keys)
    agents: list[dict[str, Any]] = []
    for idx, profile in enumerate(profiles):
        model_idx = min(idx // per_model, len(model_keys) - 1)
        agents.append({
            "name": str(profile["name"]),
            "role_prompt": str(profile.get("role_prompt") or profile.get("profile") or ""),
            "properties": dict(profile.get("properties") or {}),
            "provider_id": f"provider_{model_idx}",
            "llm_config": make_agent_llm_config(model_keys[model_idx]),
        })
    return agents


def _edge_key(left: str, right: str) -> tuple[str, str]:
    """Return a canonical (sorted) key for an undirected edge."""
    return tuple(sorted((left, right)))


def _neighbors(edges: set[tuple[str, str]], name: str) -> set[str]:
    """Return the set of agents directly connected to `name`."""
    return {other for pair in edges if name in pair for other in pair if other != name}


def _pick_partner(agent: str, agent_names: list[str], edges: set[tuple[str, str]],
                  deficit: dict[str, int], degree_now: Counter, protected: set[str]) -> str | None:
    """Choose the best new partner (most deficit, then lowest degree, then earliest index)."""
    candidates = [
        n for n in agent_names if n != agent and n not in protected and n not in _neighbors(edges, agent)
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda n: (deficit.get(n, 0), -degree_now.get(n, 0), -agent_names.index(n)),
    )


def _try_add_edge(agent: str, agent_names: list[str], edges: set[tuple[str, str]],
                  deficit: dict[str, int], degree_now: Counter, protected: set[str],
                  core: set[str]) -> bool:
    """Give `agent` one more edge to the best available partner; True when added."""
    partner = _pick_partner(agent, agent_names, edges, deficit, degree_now, protected)
    if partner is None:
        return False
    edges.add(_edge_key(agent, partner))
    degree_now[agent] += 1
    degree_now[partner] += 1
    deficit[agent] -= 1
    deficit[partner] -= 1
    if agent in core and deficit[agent] <= 0:
        protected.add(agent)
    if partner in core and deficit[partner] <= 0:
        protected.add(partner)
    return True


def build_degree_network(
    agent_names: list[str], target_degrees: list[int]
) -> tuple[list[list[str]], dict[str, int]]:
    """Build the star (agent_1 to everyone), then top up agents 2-7 to their targets.

    Returns (edges, actual_degree_map). No duplicate edges or self-loops are ever
    created. Agents 8-30 may exceed their targets because the exact requested
    sequence is mathematically impossible (see module docstring).
    """
    edges: set[tuple[str, str]] = set()
    for other in agent_names[1:]:
        edges.add(_edge_key(agent_names[0], other))

    degree_now = Counter(n for pair in edges for n in pair)
    target_map = dict(zip(agent_names, target_degrees))
    deficit = {name: target_map[name] - degree_now.get(name, 0) for name in agent_names}

    # Top up the core agents (agent_2 .. agent_7) to their targets. A core agent
    # becomes "protected" once its deficit reaches zero, so later core agents use
    # agents 8-30 as filler partners and agents 2-7 stay exactly on target.
    core = agent_names[1:7]
    core_set = set(core)
    protected: set[str] = set()
    for agent in core:
        if deficit[agent] <= 0:
            protected.add(agent)
        while deficit[agent] > 0 and _try_add_edge(
            agent, agent_names, edges, deficit, degree_now, protected, core_set
        ):
            pass

    # Safety net: give any agent still below target (agents 8-14) one more edge.
    for agent in agent_names:
        while deficit[agent] > 0 and _try_add_edge(
            agent, agent_names, edges, deficit, degree_now, protected, core_set
        ):
            pass

    return [list(e) for e in sorted(edges)], dict(degree_now)


def make_client(model_key: str) -> LLMClient:
    """Create an LLM client for one of the two local models."""
    info = MODELS[model_key]
    config = LLMConfig(dialect="openai", model=info["router"], base_url=info["base_url"],
                       api_key=os.getenv("OPENAI_API_KEY", "not-needed"), temperature=0.7)
    return LLMClient(config)


def check_servers() -> None:
    """Verify the model manager and both llama-servers are reachable, or abort."""
    import urllib.request
    from urllib.error import HTTPError, URLError

    endpoints = (
        ("model manager (8081)", f"{MODEL_MANAGER_URL}/models"),
        ("llama-server 8080", "http://127.0.0.1:8080/models"),
        ("llama-server 8082", "http://127.0.0.1:8082/models"),
    )
    dead: list[str] = []
    for label, url in endpoints:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                resp.read(64)
        except HTTPError as exc:
            exc.read()  # an HTTP error still means the server answered
        except (URLError, TimeoutError, OSError) as exc:
            dead.append(f"{label}: {exc}")
    if dead:
        raise RuntimeError("LLM stack not reachable — start the model manager and llama-servers first:\n  " + "\n  ".join(dead))
    print("  ✓ model manager and both llama-servers are reachable")


def warmup_models() -> None:
    """Load both models on their ports via the model manager, then send a warm-up chat."""
    import requests

    for model_key, info in MODELS.items():
        router, port = str(info["router"]), int(info["port"])
        print(f"  Warming {model_key} (port {port}) ... ", end="", flush=True)
        try:
            resp = requests.post(f"{MODEL_MANAGER_URL}/models/load", json={"model": router, "port": port}, timeout=300)
            if resp.status_code not in (200, 400):
                print(f"load returned {resp.status_code} ... ", end="", flush=True)
        except Exception as exc:
            print(f"load failed: {exc} ... ", end="", flush=True)

        deadline = time.time() + 300.0
        loaded = False
        while time.time() < deadline and not loaded:
            try:
                resp = requests.get(f"{MODEL_MANAGER_URL}/models", timeout=10)
                loaded = resp.status_code == 200 and any(
                    m.get("id") == router and (m.get("status") or {}).get("value") == "loaded"
                    for m in resp.json().get("data", [])
                )
            except Exception:
                loaded = False
            if not loaded:
                time.sleep(2.0)
        print("loaded" if loaded else "timed out — continuing", end=" ... ", flush=True)

        try:
            make_client(model_key).chat([{"role": "user", "content": "Say 'ready'."}], json_mode=False)
            print("warm-up chat OK")
        except Exception as exc:
            print(f"warm-up chat failed: {exc}")


def run_council(
    agents: list[dict[str, Any]], edges: list[list[str]]
) -> tuple[list[dict[str, Any]], Exception | None]:
    """Run the Proposal K council for 4 turns; return the node logs and any run-level error."""
    scene = CouncilExperimentScene(ExperimentConfig(
        scenario_id="council_chamber", agents=agents, actions=[],
        parameters={"proposal_text": PROPOSAL_K_TEXT, "deliberation_rounds": DELIBERATION_ROUNDS,
                    "voting_threshold": 0.5},
        description=PROPOSAL_K_LABEL, social_network={"edges": edges}, locale="en",
    ))
    default_client = make_client(next(iter(MODELS)))
    adapter = ExperimentRunnerAdapter(scene, {"chat": default_client, "default": default_client})
    tree = SimTree.new(adapter, adapter.clients)
    root_id = tree.root
    if root_id is None:
        raise RuntimeError("SimTree root is None — cannot proceed")

    run_error: Exception | None = None
    try:
        finished_id = tree.advance(root_id, turns=TURNS)
    except Exception as exc:
        run_error = exc
        # Salvage the branch node created by copy_sim; it holds the partial logs.
        finished_id = max(tree.nodes.keys()) if tree.nodes else root_id

    node = tree.nodes[finished_id]
    return list(node.get("logs") or []), run_error


def is_overflow(text: str) -> bool:
    """True when an error message is one of the known context-overflow phrases."""
    lowered = text.lower()
    return any(phrase in lowered for phrase in OVERFLOW_PHRASES)


def collect_results(
    node_logs: list[dict[str, Any]],
    agent_names: list[str],
    degrees: dict[str, int],
    target_map: dict[str, int],
    model_map: dict[str, str],
    total_rounds: int,
) -> list[AgentRunResult]:
    """Walk the run logs and build one result row per agent."""
    success_rounds: dict[str, set[int]] = {name: set() for name in agent_names}
    overflow: dict[str, list[str]] = {name: [] for name in agent_names}
    other: dict[str, list[str]] = {name: [] for name in agent_names}
    run_level: list[str] = []

    for entry in node_logs:
        etype = entry.get("type")
        data = entry.get("data") or {}
        if etype == "experiment_action":
            agent = str(data.get("agent", ""))
            if agent not in success_rounds:
                continue
            if data.get("success") is True:
                success_rounds[agent].add(int(data.get("round", 0) or 0))
            elif data.get("error"):
                error_text = str(data["error"])
                (overflow if is_overflow(error_text) else other)[agent].append(error_text)
        elif etype == "error" and data.get("message"):
            run_level.append(str(data["message"]))

    results = [
        AgentRunResult(
            name=name,
            model=model_map.get(name, ""),
            degree=degrees.get(name, 0),
            target_degree=target_map.get(name, 0),
            rounds_completed=len(success_rounds[name]),
            total_rounds=total_rounds,
            overflow_count=len(overflow[name]),
            overflow_messages=overflow[name],
            other_errors=other[name] + run_level,
        )
        for name in agent_names
    ]
    return results


def print_results_table(results: list[AgentRunResult]) -> None:
    """Print the per-agent results as a readable table."""
    header = f"{'Agent':<10} {'Model':<24} {'Degree':>6} {'Target':>6} {'Rounds':>7} {'Complete?':>9} {'Overflow':>8}"
    print(f"\n{header}\n{'-' * len(header)}")
    for r in results:
        print(
            f"{r.name:<10} {r.model:<24} {r.degree:>6} {r.target_degree:>6} "
            f"{f'{r.rounds_completed}/{r.total_rounds}':>7} {str(r.completed_all):>9} {r.overflow_count:>8}"
        )

    overflow_agents = [r for r in results if r.overflow_count > 0]
    if overflow_agents:
        print("\nContext-overflow details:")
        for r in overflow_agents:
            for msg in r.overflow_messages:
                print(f"  {r.name}: {msg}")
    else:
        print("\nNo context-overflow errors detected.")


def write_csv(results: list[AgentRunResult], output_dir: Path) -> Path:
    """Save the per-agent results to a CSV file in the output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "context_barrier_results.csv"
    fieldnames = [
        "agent", "model", "degree", "target_degree", "rounds_completed",
        "total_rounds", "completed_all", "overflow_count", "overflow_messages", "other_errors",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow(
                {
                    "agent": r.name,
                    "model": r.model,
                    "degree": r.degree,
                    "target_degree": r.target_degree,
                    "rounds_completed": r.rounds_completed,
                    "total_rounds": r.total_rounds,
                    "completed_all": r.completed_all,
                    "overflow_count": r.overflow_count,
                    "overflow_messages": " | ".join(r.overflow_messages),
                    "other_errors": " | ".join(r.other_errors),
                }
            )
    return path


def main() -> None:
    """Run the whole context-barrier experiment end to end."""
    os.environ.setdefault("FOS_SERVER_CTX_SIZE", "32768")
    os.environ.setdefault("FOS_MODEL_MANAGER_URL", MODEL_MANAGER_URL)
    os.environ.setdefault("FOS_LLM_CONCURRENCY", "4")
    os.environ.setdefault("LLM_MAX_RETRIES", "1")
    # Keep the LLM traffic log inside our output folder instead of the repo root.
    os.environ["FOS_LLM_LOG"] = str(OUTPUT_DIR / "llm_traffic.jsonl")

    print("=" * 70)
    print("  Context Barrier Test — Proposal K (Privacy Norms)")
    print(f"  Agents: {NUM_AGENTS} | Turns: {TURNS} (3 deliberation + 1 voting)\n  Models: {', '.join(MODELS)}\n{'=' * 70}")

    profiles = load_profiles(PROFILES_PATH, NUM_AGENTS)
    if len(profiles) < NUM_AGENTS:
        raise RuntimeError(f"Only {len(profiles)} profiles found in {PROFILES_PATH}; need {NUM_AGENTS}")
    print(f"1. Loaded {len(profiles)} profiles from {PROFILES_PATH.name}")

    agents = build_agent_configs(profiles)
    agent_names = [str(a["name"]) for a in agents]

    print("2. Checking the LLM stack ...")
    check_servers()
    warmup_models()

    print("3. Building the custom degree network ...")
    edges, degrees = build_degree_network(agent_names, TARGET_DEGREES)
    print(f"   ✓ {len(edges)} edges\n   ✓ target: {TARGET_DEGREES}\n   ✓ actual: {[degrees[n] for n in agent_names]}")

    print("4. Running the council (Proposal K, 4 turns) ...")
    node_logs, run_error = run_council(agents, edges)
    print(f"   ✓ run finished, {len(node_logs)} log events captured")

    print("5. Collecting per-agent results ...")
    target_map = dict(zip(agent_names, TARGET_DEGREES))
    model_map = {str(a["name"]): str((a.get("llm_config") or {}).get("model", "?")) for a in agents}
    results = collect_results(node_logs, agent_names, degrees, target_map, model_map, TURNS)
    print_results_table(results)

    csv_path = write_csv(results, OUTPUT_DIR)
    print(f"\n   ✓ CSV saved to {csv_path}")

    if run_error is not None:
        print(f"\nNOTE: the council run raised an error: {run_error!r}")

    completed = sum(1 for r in results if r.completed_all)
    print(f"\nSummary: {completed}/{len(results)} agents completed all {TURNS} rounds; "
          f"{sum(r.overflow_count for r in results)} context-overflow errors total.")


if __name__ == "__main__":
    main()
