#!/usr/bin/env python3
"""Quick leak audit: 9 agents, 5 models, 2 rounds — measure leak rates by model."""
import asyncio, os, sys, time, re
from collections import defaultdict
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from fos.core.experiment.runner import ExperimentRunner
from fos.core.experiment.agent import ExperimentAgent
from fos.core.experiment.config import ExperimentConfig
from fos.core.experiment.scenes.council_experiment import CouncilExperimentScene
from fos.core.llm_config import LLMConfig
from fos.core.llm.client import LLMClient
from fos.core.experiment.game_configs import create_council_config
from fos.core.experiment.debug_log import write_debug

MODELS = ["gpt-oss-20b","qwen3.6-35b-a3b","gemma-4-26b-a4b","gemma4-26b-a4b-uncensored","qwen3.6-35b-a3b-uncensored"]
BASE_URL = "http://127.0.0.1:8080/v1"
PROPOSAL = "Should the international community authorise the large-scale deployment of solar geoengineering (stratospheric aerosol injection) to reduce global temperatures, accepting the associated scientific uncertainties and governance risks?"

async def main():
    agent_llm_clients = {}
    agents_raw = []
    for i in range(9):
        model_name = MODELS[i % len(MODELS) if i < len(MODELS) else i % len(MODELS)]
        agent_name = f"Agent_{i+1}"
        llm_cfg = LLMConfig(dialect="openai", model=model_name, base_url=BASE_URL, api_key="not-needed", temperature=0.7)
        client = LLMClient(llm_cfg)
        agent_llm_clients[agent_name] = client
        agents_raw.append({
            "name": agent_name,
            "properties": {"age_group": "adult"},
            "llm_config": {"dialect": "openai", "model": model_name, "base_url": BASE_URL, "api_key": "not-needed", "temperature": 0.7},
        })

    config = ExperimentConfig(
        scenario_id="council_chamber",
        agents=agents_raw,
        actions=[],
        parameters={"proposal_text": PROPOSAL, "deliberation_rounds": 2, "voting_threshold": 0.5},
        description="Leak Audit",
        social_network={"edges": [["Agent_1","Agent_2"],["Agent_2","Agent_3"],["Agent_3","Agent_4"],["Agent_4","Agent_5"],["Agent_5","Agent_6"],["Agent_6","Agent_7"],["Agent_7","Agent_8"],["Agent_8","Agent_9"]]},
        locale="en",
    )
    scene = CouncilExperimentScene(config)
    scene.initialize(llm_client=agent_llm_clients["Agent_1"], provider_clients={})

    gc = create_council_config(proposal_text=PROPOSAL, deliberation_rounds=2, voting_threshold=0.5)
    runner = ExperimentRunner(
        agents=scene.agents, game_config=gc, llm_client=agent_llm_clients["Agent_1"],
        agent_llm_clients=agent_llm_clients, round_visibility="simultaneous", scene=scene,
    )
    runner.set_scene_state({"state": scene.state, "graph": {"edges": [["Agent_1","Agent_2"],["Agent_2","Agent_3"],["Agent_3","Agent_4"],["Agent_4","Agent_5"],["Agent_5","Agent_6"],["Agent_6","Agent_7"],["Agent_7","Agent_8"],["Agent_8","Agent_9"]]}})
    scene.runner = runner

    print(f"Running leak audit: {len(scene.agents)} agents, {len(MODELS)} models, 2 rounds")
    t0 = time.time()
    results = await runner.run(max_rounds=2)
    elapsed = time.time() - t0
    print(f"Done in {elapsed:.0f}s")

    total = sum(len(r.actions) for r in results)
    failed = sum(1 for r in results for a in r.actions if not a.success and not a.skipped)
    skipped = sum(1 for r in results for a in r.actions if a.skipped)
    print(f"Actions: {total} total ({total-failed-skipped} ok, {failed} failed, {skipped} skipped)")
    print(f"\nCheck the latest debug log in test_results/ for leak_detected counts")

if __name__ == "__main__":
    asyncio.run(main())
