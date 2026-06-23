#!/usr/bin/env python3
"""Dress rehearsal: 9 agents, 5 models, 4 rounds — tests model-batching speed."""
import asyncio, os, time, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from fos.core.experiment.runner import ExperimentRunner
from fos.core.experiment.agent import ExperimentAgent
from fos.core.experiment.game_configs import PRISONERS_DILEMMA
from fos.core.llm_config import LLMConfig
from fos.core.llm.client import LLMClient

# Router model names (GGUF filenames) for llama.cpp server
MODELS = [
    "gpt-oss-20b",
    "qwen3.6-35b-a3b",
    "gemma-4-26b-a4b",
    "gemma4-26b-a4b-uncensored",
    "qwen3.6-35b-a3b-uncensored",
]

BASE_URL = "http://127.0.0.1:8080/v1"
NUM_AGENTS = 9
NUM_ROUNDS = 4

async def main():
    agent_llm_clients = {}
    agents = []
    for i in range(NUM_AGENTS):
        model_name = MODELS[i % len(MODELS)]
        agent_name = f"Agent_{i+1}"
        llm_config = LLMConfig(
            dialect="openai",
            model=model_name,
            base_url=BASE_URL,
            api_key="not-needed",
        )
        client = LLMClient(llm_config)
        agent_llm_clients[agent_name] = client
        agent = ExperimentAgent(
            name=agent_name,
            properties={"age_group": "adult", "model": model_name},
            llm_config=LLMConfig(dialect="openai"),
        )
        agents.append(agent)

    print(f"Starting dress rehearsal: {len(agents)} agents, {len(MODELS)} models, {NUM_ROUNDS} rounds")
    print(f"Model distribution: {[(a.name, a.properties.get('model','?')) for a in agents]}")

    runner = ExperimentRunner(
        agents=agents,
        game_config=PRISONERS_DILEMMA,
        llm_client=agent_llm_clients[agents[0].name],
        agent_llm_clients=agent_llm_clients,
        round_visibility="simultaneous",
    )

    t0 = time.time()
    results = await runner.run(max_rounds=NUM_ROUNDS)
    elapsed = time.time() - t0

    total_actions = sum(len(r.actions) for r in results)
    failed = sum(1 for r in results for a in r.actions if not a.success and not a.skipped)
    skipped = sum(1 for r in results for a in r.actions if a.skipped)
    succeeded = total_actions - failed - skipped

    print(f"\n{'='*60}")
    print(f"DRESS REHEARSAL COMPLETE")
    print(f"{'='*60}")
    print(f"Time: {elapsed:.1f}s ({elapsed/60:.1f} minutes)")
    print(f"Rounds: {len(results)}")
    print(f"Actions: {total_actions} total ({succeeded} success, {failed} failed, {skipped} skipped)")
    print(f"Model switches: {len(MODELS)} unique models x {NUM_ROUNDS} rounds = {len(MODELS)*NUM_ROUNDS} (ideal)")
    print(f"{'='*60}")

    if failed > 0 or skipped > 0:
        print("FAILURES DETECTED:")
        for r in results:
            for a in r.actions:
                if a.skipped or not a.success:
                    print(f"  Round {r.round_num}: {a.agent_name} — skipped={a.skipped} success={a.success} error={getattr(a, 'error', 'N/A')}")

    assert failed == 0, f"{failed} failed actions"
    assert skipped == 0, f"{skipped} skipped actions"
    assert elapsed < 18.7 * 60, f"Took {elapsed:.0f}s, expected <1122s (18.7min)"
    print("\n✓ ALL CHECKS PASSED")

if __name__ == "__main__":
    asyncio.run(main())
