#!/usr/bin/env python3
"""
Headless council pilot runner — supports Ollama, OpenAI-compatible (LM Studio), and llama.cpp backends.

Usage:
    # LM Studio (default)
    python scripts/headless_council.py \
        --backend lmstudio \
        --base-url http://127.0.0.1:1234/v1 \
        --models "openai/gpt-oss-20b,qwen/qwen3.6-35b-a3b,google/gemma-4-26b-a4b" \
        --agents 15 --seed 7

    # Ollama
    python scripts/headless_council.py \
        --backend ollama \
        --base-url http://127.0.0.1:11434 \
        --models "ministral-3:3b,granite4:3b" \
        --agents 12 --seed 7

    # llama.cpp (local llama-server with GPU offload)
    python scripts/headless_council.py \
        --backend llamacpp \
        --base-url http://127.0.0.1:8080/v1 \
        --models "openai/gpt-oss-20b,google/gemma-4-26b-a4b" \
        --agents 9 --seed 42
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# Ensure the fos package is importable without pip install
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

# Load .env so FOS_LLM_CONCURRENCY and other env vars are available
try:
    from dotenv import load_dotenv

    load_dotenv(_REPO_ROOT / ".env")
except ImportError:
    pass

from fos.backend.services.export_service import export_events
from fos.backend.services.simtree_runtime import ExperimentRunnerAdapter
from fos.core.experiment.config import ExperimentConfig
from fos.core.experiment.scenes.council_experiment import CouncilExperimentScene
from fos.core.llm.client import LLMClient
from fos.core.llm.generation import generate_agents_with_archetypes
from fos.core.llm_config import LLMConfig
from fos.core.simtree import SimTree

# ── Defaults ──────────────────────────────────────────────────────────────────

DEFAULT_DEMOGRAPHICS = [
    {"name": "Age", "categories": ["18-29", "30-49", "50+"]},
    {
        "name": "Political View",
        "categories": ["progressive", "moderate", "conservative"],
    },
    {
        "name": "Work Sector",
        "categories": ["public service", "private sector", "not in paid work"],
    },
]

DEFAULT_TRAITS = [
    {"name": "Openness", "mean": 50, "std": 20},
    {"name": "Conscientiousness", "mean": 50, "std": 20},
    {"name": "Extraversion", "mean": 50, "std": 20},
    {"name": "Agreeableness", "mean": 50, "std": 20},
    {"name": "Neuroticism", "mean": 50, "std": 20},
]


# ── Data classes ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ProposalSpec:
    key: str
    label: str
    text: str


@dataclass(frozen=True)
class NetworkVariant:
    label: str
    network: dict[str, list[list[str]]]


@dataclass(frozen=True)
class BranchCsvExport:
    proposal_key: str
    proposal_label: str
    network_label: str
    csv_text: str


# ── Proposals ──────────────────────────────────────────────────────────────────


def default_proposals() -> list[ProposalSpec]:
    return [
        ProposalSpec(
            key="proposal_a",
            label="Proposal A - Solar geoengineering",
            text=(
                "Should the international community authorise the large-scale "
                "deployment of solar geoengineering (stratospheric aerosol "
                "injection) to reduce global temperatures, accepting the "
                "associated scientific uncertainties and governance risks?"
            ),
        ),
        ProposalSpec(
            key="proposal_b",
            label="Proposal B - Global wealth tax",
            text=(
                "Should a coordinated global wealth tax be levied on the "
                "world's largest fortunes, with the revenue redistributed to "
                "lower-income populations and climate adaptation programmes?"
            ),
        ),
        ProposalSpec(
            key="proposal_c",
            label="Proposal C - Lethal autonomous weapons (LAWS)",
            text=(
                "Should the development and deployment of lethal autonomous "
                "weapons systems - weapons that can select and engage targets "
                "without direct human control - be permitted under "
                "international law?"
            ),
        ),
    ]


# ── Helpers ────────────────────────────────────────────────────────────────────


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(text)


def _make_edge(left: str, right: str) -> tuple[str, str]:
    return tuple(sorted((left, right)))


def _json_get(base_url: str, route: str) -> dict[str, Any]:
    """Fetch one JSON response from an HTTP endpoint."""
    url = base_url.rstrip("/") + route
    req = Request(url, headers={"Accept": "application/json"})
    with urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ── Model verification ────────────────────────────────────────────────────────


def ensure_models_available(
    backend: str, base_url: str, model_names: list[str]
) -> None:
    """Verify all requested models are available on the backend."""
    if backend == "ollama":
        _verify_ollama_models(base_url, model_names)
    elif backend == "llamacpp":
        _verify_llamacpp_models(base_url, model_names)
    elif backend in ("openai", "lmstudio"):
        _verify_openai_models(base_url, model_names)
    else:
        raise ValueError(f"Unknown backend: {backend}")


def _warmup_models(
    backend: str, base_url: str, model_names: list[str], temperature: float
) -> None:
    """Pre-load the first model only. Model-switch preloading is handled
    by the runner (see ExperimentRunner._preload_model).

    For ``llamacpp`` backend: POST /models/load + poll until loaded,
    then send warmup chat.  For other backends, send a simple chat
    message to trigger loading.
    """
    if not model_names:
        return
    first = model_names[0]

    # ── Model router path (llamacpp backend) ────────────────────────
    if backend == "llamacpp":
        import time as _time
        import requests as _requests

        # Strip /v1 from base_url to get router base
        router_base = base_url.rstrip("/")
        if router_base.endswith("/v1"):
            router_base = router_base[:-3]

        router_model = _LLAMACPP_ROUTER_MAP.get(first, first)
        print(
            f"   Warming {first} (router name: {router_model}) via "
            f"{router_base}/models/load ... ",
            end="", flush=True,
        )

        # Step 1: POST /models/load
        load_url = f"{router_base}/models/load"
        try:
            resp = _requests.post(
                load_url,
                json={"model": router_model},
                timeout=30,
            )
            if resp.status_code == 200:
                print("load request accepted", end=" ... ", flush=True)
            elif resp.status_code == 400 and "already running" in resp.text:
                print("already running", end=" ... ", flush=True)
            else:
                print(
                    f"load returned {resp.status_code}: {resp.text[:100]}",
                    end=" ... ", flush=True,
                )
        except Exception as exc:
            print(f"load failed: {exc}", end=" ... ", flush=True)

        # Step 2: Poll GET /models every 2s until loaded (timeout 300s)
        models_url = f"{router_base}/models"
        poll_interval = 2.0
        timeout = 300.0
        deadline = _time.time() + timeout
        loaded = False

        while _time.time() < deadline:
            try:
                resp = _requests.get(models_url, timeout=10)
                if resp.status_code == 200:
                    models_list = resp.json().get("data", [])
                    for m in models_list:
                        m_name = m.get("id", "") if isinstance(m, dict) else ""
                        m_status = m.get("status", {}) if isinstance(m, dict) else {}
                        if isinstance(m_status, dict):
                            status_val = m_status.get("value", "") or m_status.get("status", "")
                        else:
                            status_val = str(m_status)

                        if m_name == router_model:
                            if status_val == "loaded":
                                loaded = True
                                break
                            elif status_val == "error":
                                print(f"status=error for {router_model}")
                                return
                    if loaded:
                        break
                _time.sleep(poll_interval)
            except Exception:
                _time.sleep(poll_interval)
                continue

        if not loaded:
            elapsed = _time.time() - (deadline - timeout)
            print(f"timed out after {elapsed:.0f}s")
            return

        print(f"loaded ({":.1f".format(_time.time() - (deadline - timeout))}s)", end=" ... ", flush=True)

        # Step 3: Warmup chat
        client = make_client(backend, first, base_url, temperature)
        try:
            client.chat(
                [{"role": "user", "content": "Say 'ready'."}],
                json_mode=False,
            )
            print("✓ ready")
        except Exception as exc:
            print(f"⚠ warmup failed ({exc})")
        return

    # ── Non-llamacpp backends: simple chat warmup ─────────────────
    print(f"   Warming {first} (first model only, runner handles switches) ... ", end="", flush=True)
    client = make_client(backend, first, base_url, temperature)
    try:
        client.chat(
            [{"role": "user", "content": "Say 'ready'."}],
            json_mode=False,
        )
        print("✓ ready")
    except Exception as exc:
        print(f"⚠ failed ({exc})")


# Router model name mapping (FOS name → GGUF filename without .gguf)
_LLAMACPP_ROUTER_MAP = {
    "openai/gpt-oss-20b": "gpt-oss-20b",
    "google/gemma-4-26b-a4b": "gemma-4-26b-a4b",
    "qwen/qwen3.6-35b-a3b": "qwen3.6-35b-a3b",
    "gemma4-26b-a4b-uncensored-hauhaucs-balanced": "gemma4-26b-a4b-uncensored",
    "qwen3.6-35b-a3b-uncensored-hauhaucs-aggressive": "qwen3.6-35b-a3b-uncensored",
}


def _verify_llamacpp_models(base_url: str, model_names: list[str]) -> None:
    """Verify all requested models are available via the router's /models endpoint."""
    # The router serves /models (not /v1/models) on the same port as the API
    clean_url = base_url.rstrip("/")
    if clean_url.endswith("/v1"):
        clean_url = clean_url[:-3]
    try:
        payload = _json_get(clean_url, "/models")
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(
            f"llama.cpp router unreachable at {clean_url}/models: {exc}"
        ) from exc
    # The router /models endpoint returns a list of model IDs
    models = payload if isinstance(payload, list) else payload.get("data", [])
    available = set()
    for m in models:
        if isinstance(m, str):
            available.add(m)
        elif isinstance(m, dict):
            available.add(str(m.get("id", "")))
    missing = [n for n in model_names if _LLAMACPP_ROUTER_MAP.get(n, n) not in available]
    if missing:
        raise RuntimeError(
            f"Missing models on llama.cpp router: {', '.join(missing)}\n"
            f"Available: {', '.join(sorted(available))}"
        )
    print(f"  ✓ All {len(model_names)} models present on llama.cpp router")


def _verify_ollama_models(base_url: str, model_names: list[str]) -> None:
    """Check Ollama /api/tags for model availability."""
    try:
        payload = _json_get(base_url, "/api/tags")
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Ollama unreachable at {base_url}: {exc}") from exc

    installed = {str(m["name"]) for m in payload.get("models", [])}
    missing = [n for n in model_names if n not in installed]
    if missing:
        raise RuntimeError(f"Missing Ollama models: {', '.join(missing)}")
    print(f"  ✓ All {len(model_names)} Ollama models present")


def _verify_openai_models(base_url: str, model_names: list[str]) -> None:
    """Check OpenAI-compatible /v1/models for model availability."""
    # Strip /v1 from base_url if present to avoid double /v1/v1/models
    clean_url = base_url.rstrip("/")
    if clean_url.endswith("/v1"):
        clean_url = clean_url[:-3]
    try:
        payload = _json_get(clean_url, "/v1/models")
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(
            f"OpenAI-compatible endpoint unreachable at {base_url}: {exc}"
        ) from exc

    installed = {str(m.get("id", "")) for m in payload.get("data", [])}
    missing = [n for n in model_names if n not in installed]
    if missing:
        raise RuntimeError(
            f"Missing models: {', '.join(missing)}\n"
            f"Available: {', '.join(sorted(installed))}"
        )
    print(f"  ✓ All {len(model_names)} models present")


# ── Client creation ────────────────────────────────────────────────────────────


def make_client(
    backend: str, model_name: str, base_url: str, temperature: float
) -> LLMClient:
    """Create one LLM client for the specified backend."""
    # Translate FOS model identifiers to GGUF filenames for llama.cpp router
    if backend == "llamacpp":
        model_name = _LLAMACPP_ROUTER_MAP.get(model_name, model_name)
    if backend == "ollama":
        return LLMClient(
            LLMConfig(
                dialect="ollama",
                model=model_name,
                base_url=base_url,
                temperature=temperature,
                max_tokens=1024,
            )
        )
    elif backend in ("openai", "lmstudio", "llamacpp"):
        return LLMClient(
            LLMConfig(
                dialect="openai",
                model=model_name,
                base_url=base_url,
                api_key=os.getenv("OPENAI_API_KEY", "lm-studio"),  # dummy for local
                temperature=temperature,
                max_tokens=1024,
            )
        )
    else:
        raise ValueError(f"Unknown backend: {backend}")


# ── Agent building ─────────────────────────────────────────────────────────────


def _generated_agent_to_config(agent: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(agent["name"]),
        "role_prompt": str(agent.get("profile") or ""),
        "properties": dict(agent.get("properties") or {}),
    }


def build_agents(
    backend: str,
    base_url: str,
    model_names: list[str],
    temperature: float,
    total_agents: int,
    seed: int,
) -> list[dict[str, Any]]:
    """Generate demographic agents and distribute models across them."""
    generator_client = make_client(backend, model_names[0], base_url, temperature)

    random_state = random.getstate()
    random.seed(seed)
    try:
        generated = generate_agents_with_archetypes(
            total_agents=total_agents,
            demographics=DEFAULT_DEMOGRAPHICS,
            archetype_probabilities={},
            traits=DEFAULT_TRAITS,
            llm_client=generator_client,
            language="en",
            timeout=120,
        )
    finally:
        random.setstate(random_state)

    agents: list[dict[str, Any]] = []
    agents_per_model = total_agents // len(model_names)
    for idx, agent in enumerate(generated):
        config_agent = _generated_agent_to_config(agent)
        # Block assignment: consecutive agents share the same model,
        # so LM Studio only switches models every N agents, not every agent.
        model_idx = idx // agents_per_model
        if model_idx >= len(model_names):
            model_idx = len(model_names) - 1
        model_name = model_names[model_idx]
        config_agent["provider_id"] = f"provider_{model_idx}"
        config_agent["llm_config"] = _make_agent_llm_config(
            backend, model_name, base_url, temperature
        )
        agents.append(config_agent)
    return agents


def _make_agent_llm_config(
    backend: str, model_name: str, base_url: str, temperature: float
) -> dict[str, Any]:
    """Build the per-agent llm_config dict."""
    # Translate FOS model identifiers to GGUF filenames for llama.cpp router
    if backend == "llamacpp":
        model_name = _LLAMACPP_ROUTER_MAP.get(model_name, model_name)
    if backend == "ollama":
        return {
            "dialect": "ollama",
            "model": model_name,
            "base_url": base_url,
            "temperature": temperature,
        }
    else:
        return {
            "dialect": "openai",
            "model": model_name,
            "base_url": base_url,
            "api_key": os.getenv("OPENAI_API_KEY", "lm-studio"),
            "temperature": temperature,
        }


# ── Network generation ────────────────────────────────────────────────────────


def _build_small_world_edges(agent_names: list[str], seed: int) -> list[list[str]]:
    rng = random.Random(seed)
    edges: set[tuple[str, str]] = set()
    count = len(agent_names)
    for idx, name in enumerate(agent_names):
        for step in (1, 2):
            neighbor = agent_names[(idx + step) % count]
            edges.add(_make_edge(name, neighbor))
    for _ in range(max(1, count // 2)):
        left, right = rng.sample(agent_names, 2)
        edges.add(_make_edge(left, right))
    return [list(e) for e in sorted(edges)]


def _pick_weighted_name(
    rng: random.Random,
    agent_names: list[str],
    degree_map: dict[str, int],
    blocked: set[str],
) -> str:
    choices = [n for n in agent_names if n not in blocked]
    weights = [degree_map.get(n, 0) + 1 for n in choices]
    return rng.choices(choices, weights=weights, k=1)[0]


def _build_holme_kim_edges(agent_names: list[str], seed: int) -> list[list[str]]:
    rng = random.Random(seed)
    edges: set[tuple[str, str]] = {
        _make_edge(agent_names[0], agent_names[1]),
        _make_edge(agent_names[1], agent_names[2]),
        _make_edge(agent_names[0], agent_names[2]),
    }
    degree_map = dict.fromkeys(agent_names, 0)
    for left, right in edges:
        degree_map[left] += 1
        degree_map[right] += 1

    for idx in range(3, len(agent_names)):
        new_name = agent_names[idx]
        chosen: set[str] = set()
        while len(chosen) < 2:
            chosen.add(_pick_weighted_name(rng, agent_names[:idx], degree_map, chosen))
        chosen_names = list(chosen)
        for cn in chosen_names:
            edge = _make_edge(new_name, cn)
            edges.add(edge)
            degree_map[new_name] += 1
            degree_map[cn] += 1
        if rng.random() < 0.35:
            friend = chosen_names[0]
            others = [
                n for n in agent_names[:idx] if n not in {friend, chosen_names[1]}
            ]
            if others:
                tn = rng.choice(others)
                edge = _make_edge(friend, tn)
                if edge not in edges:
                    edges.add(edge)
                    degree_map[friend] += 1
                    degree_map[tn] += 1
    return [list(e) for e in sorted(edges)]


def _build_sbm_edges(agent_names: list[str], seed: int) -> list[list[str]]:
    rng = random.Random(seed)
    mid = len(agent_names) // 2
    left_block = agent_names[:mid]
    right_block = agent_names[mid:]
    edges: set[tuple[str, str]] = set()

    def add_block(block: list[str], prob: float) -> None:
        for i, a in enumerate(block):
            for b in block[i + 1 :]:
                if rng.random() <= prob:
                    edges.add(_make_edge(a, b))

    add_block(left_block, 0.75)
    add_block(right_block, 0.75)
    for a in left_block:
        for b in right_block:
            if rng.random() <= 0.08:
                edges.add(_make_edge(a, b))
    if left_block and right_block:
        edges.add(_make_edge(left_block[0], right_block[0]))
    return [list(e) for e in sorted(edges)]


def build_network_variants(agent_names: list[str], seed: int) -> list[NetworkVariant]:
    return [
        NetworkVariant(
            "small_world",
            {"edges": _build_small_world_edges(agent_names, seed)},
        ),
        NetworkVariant(
            "holme_kim",
            {"edges": _build_holme_kim_edges(agent_names, seed + 1)},
        ),
        NetworkVariant(
            "sbm",
            {"edges": _build_sbm_edges(agent_names, seed + 2)},
        ),
    ]


# ── Scene builder ──────────────────────────────────────────────────────────────


def _build_council_scene(
    agents: list[dict[str, Any]],
    proposal: ProposalSpec,
    network: dict[str, list[list[str]]],
) -> CouncilExperimentScene:
    return CouncilExperimentScene(
        ExperimentConfig(
            scenario_id="council_chamber",
            agents=agents,
            actions=[],
            parameters={
                "proposal_text": proposal.text,
                "deliberation_rounds": 3,
                "voting_threshold": 0.5,
            },
            description=proposal.label,
            social_network=network,
            locale="en",
        )
    )


def _node_logs_to_export_events(
    node_id: int, node_logs: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for seq, log in enumerate(node_logs):
        log_data = dict(log.get("data") or {})
        events.append(
            {
                "sequence": seq,
                "tree_node_id": node_id,
                "event_type": log.get("type"),
                "payload": log_data,
                "created_at": log.get("timestamp") or log_data.get("created_at") or "",
            }
        )
    return events


def combine_branch_csv_exports(exports: list[BranchCsvExport]) -> str:
    combined_rows: list[dict[str, str]] = []
    base_fieldnames: list[str] = []
    for exp in exports:
        reader = csv.DictReader(io.StringIO(exp.csv_text))
        if reader.fieldnames and not base_fieldnames:
            base_fieldnames = list(reader.fieldnames)
        for row in reader:
            combined_rows.append(
                {
                    "proposal_key": exp.proposal_key,
                    "proposal_label": exp.proposal_label,
                    "network_label": exp.network_label,
                    **{k: str(v or "") for k, v in row.items()},
                }
            )

    fieldnames = ["proposal_key", "proposal_label", "network_label", *base_fieldnames]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(combined_rows)
    return output.getvalue()


# ── Main pilot runner ─────────────────────────────────────────────────────────


def run_headless_council(
    output_dir: Path,
    backend: str,
    base_url: str,
    model_names: list[str],
    total_agents: int = 15,
    seed: int = 7,
    temperature: float = 0.7,
    proposals: list[ProposalSpec] | None = None,
) -> dict[str, Any]:
    """Run the full council pilot with the specified backend."""
    print(f"\n{'=' * 60}")
    print("  Headless Council Pilot")
    print(f"  Backend:    {backend}")
    print(f"  Base URL:   {base_url}")
    print(f"  Models:     {', '.join(model_names)}")
    print(
        f"  Agents:     {total_agents} ({total_agents // len(model_names)} per model)"
    )
    print(f"  Seed:       {seed}")
    print(f"  Output:     {output_dir.resolve()}")
    print(f"{'=' * 60}\n")

    # 1. Verify models
    print("1. Checking model availability...")
    ensure_models_available(backend, base_url, model_names)

    # 1.5 Pre-warm first model (runner handles subsequent model switches)
    if len(model_names) > 1:
        print("1.5. Pre-warming first model (runner handles switches)...")
        _warmup_models(backend, base_url, model_names, temperature)

    # 2. Generate agents
    print("2. Generating agent profiles...")
    agents = build_agents(
        backend=backend,
        base_url=base_url,
        model_names=model_names,
        temperature=temperature,
        total_agents=total_agents,
        seed=seed,
    )
    agent_names = [str(a["name"]) for a in agents]
    print(f"   ✓ Generated {len(agents)} agents")

    # 3. Build networks
    print("3. Building network variants...")
    networks = build_network_variants(agent_names, seed)

    # Make the generator client (first model used for agent generation above,
    # also used as the default chat client for the simtree adapter)
    generator_client = make_client(backend, model_names[0], base_url, temperature)

    selected_proposals = proposals or default_proposals()

    combined_exports: list[BranchCsvExport] = []
    summary: dict[str, Any] = {
        "backend": backend,
        "base_url": base_url,
        "seed": seed,
        "temperature": temperature,
        "agent_count": total_agents,
        "models": model_names,
        "runs": [],
    }

    total_branches = len(selected_proposals) * len(networks)
    branch_num = 0

    for proposal in selected_proposals:
        print(f"\n4. Running: {proposal.label}")
        scene = _build_council_scene(agents, proposal, {"edges": []})
        adapter = ExperimentRunnerAdapter(
            scene, {"chat": generator_client, "default": generator_client}
        )
        tree = SimTree.new(adapter, adapter.clients)
        root_id = tree.root
        if root_id is None:
            raise RuntimeError("SimTree root is None — cannot proceed")

        for network in networks:
            branch_num += 1
            print(
                f"   [{branch_num}/{total_branches}] Network: {network.label} ... ",
                end="",
                flush=True,
            )

            branch_id = tree.branch(
                root_id,
                [{"op": "network_replace", "network": network.network}],
            )
            finished_id = tree.advance(branch_id, turns=4)

            node = tree.nodes[finished_id]
            node_logs = list(node.get("logs") or [])
            scenario_params = {
                "scenario_id": "council_chamber",
                "proposal_text": proposal.text,
                "deliberation_rounds": 3,
                "voting_threshold": 0.5,
            }
            csv_text = export_events(
                _node_logs_to_export_events(finished_id, node_logs),
                scenario_params,
                "csv",
            )
            branch_export = BranchCsvExport(
                proposal_key=proposal.key,
                proposal_label=proposal.label,
                network_label=network.label,
                csv_text=csv_text,
            )
            combined_exports.append(branch_export)
            summary["runs"].append(
                {
                    "proposal_key": proposal.key,
                    "proposal_label": proposal.label,
                    "network_label": network.label,
                    "node_id": finished_id,
                    "log_count": len(node_logs),
                }
            )
            print(f"done ({len(node_logs)} events)")

    # 5. Export
    print("\n5. Exporting results...")
    combined_csv = combine_branch_csv_exports(combined_exports)
    _write_text(output_dir / "combined_results.csv", combined_csv)
    _write_text(output_dir / "summary.json", json.dumps(summary, indent=2))
    print(f"   ✓ {output_dir / 'combined_results.csv'}")
    print(f"   ✓ {output_dir / 'summary.json'}")

    print(f"\n{'=' * 60}")
    print(f"  Complete! {len(summary['runs'])} branches run.")
    print(f"  Results: {output_dir.resolve()}")
    print(f"{'=' * 60}\n")

    return summary


# ── CLI ────────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Headless council pilot — Ollama & OpenAI-compatible backends"
    )
    parser.add_argument(
        "--backend",
        choices=["ollama", "openai", "lmstudio", "llamacpp"],
        default="lmstudio",
        help="LLM backend type (default: lmstudio)",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:1234/v1",
        help="Backend base URL (default: http://127.0.0.1:1234/v1)",
    )
    parser.add_argument(
        "--models",
        default="openai/gpt-oss-20b,qwen/qwen3.6-35b-a3b,"
        "qwen3.6-35b-a3b-uncensored-hauhaucs-aggressive,"
        "google/gemma-4-26b-a4b,"
        "gemma4-26b-a4b-uncensored-hauhaucs-balanced",
        help="Comma-separated model names",
    )
    parser.add_argument(
        "--agents", type=int, default=15, help="Total agents (default: 15)"
    )
    parser.add_argument("--seed", type=int, default=7, help="Random seed (default: 7)")
    parser.add_argument(
        "--temperature", type=float, default=0.7, help="LLM temperature (default: 0.7)"
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/headless_council_run",
        help="Output directory (default: artifacts/headless_council_run)",
    )
    parser.add_argument(
        "--proposals",
        choices=["all", "geoengineering", "wealth-tax", "laws"],
        default="all",
        help="Which proposals to run (default: all)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=None,
        help="Max concurrent LLM calls (overrides FOS_LLM_CONCURRENCY env var). Set to 1 to force sequential model loading.",
    )
    args = parser.parse_args()

    model_names = [m.strip() for m in args.models.split(",") if m.strip()]
    if not model_names:
        parser.error("At least one model required (--models)")

    # Apply backend-specific default base_url
    if args.backend == "llamacpp" and args.base_url == "http://127.0.0.1:1234/v1":
        args.base_url = "http://127.0.0.1:8080/v1"

    # Apply concurrency setting before the runner creates its semaphore
    if args.concurrency is not None:
        os.environ["FOS_LLM_CONCURRENCY"] = str(args.concurrency)

    output_dir = Path(args.output_dir)

    # Select proposals
    all_props = default_proposals()
    proposal_map = {
        "geoengineering": [all_props[0]],
        "wealth-tax": [all_props[1]],
        "laws": [all_props[2]],
    }
    proposals = proposal_map.get(args.proposals, all_props)

    run_headless_council(
        output_dir=output_dir,
        backend=args.backend,
        base_url=args.base_url,
        model_names=model_names,
        total_agents=args.agents,
        seed=args.seed,
        temperature=args.temperature,
        proposals=proposals,
    )


if __name__ == "__main__":
    main()
