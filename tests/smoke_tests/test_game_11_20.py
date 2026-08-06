"""
Standalone smoke test for the 11-20 Money Request Game.

Runs one round of the game with two mock agents (no real LLM needed),
then prints what each agent chose, the computed payoffs, and a few known
payoff table entries as a sanity check.

Run it directly with:
    python tests/smoke_tests/test_game_11_20.py
"""

import asyncio

from fos.core.experiment.agent import ExperimentAgent
from fos.core.experiment.game_configs import GameConfig
from fos.core.experiment.runner import ExperimentRunner
from fos.core.llm.client import LLMClient
from fos.core.llm_config import LLMConfig


def build_payoff_matrix() -> dict:
    """Build the full 10x10 payoff matrix for the game.

    Payoff for the row player = their number, plus 20 if the row number
    is exactly one less than the column number. Payoff for the column
    player = their number, plus 20 if the column number is exactly one
    less than the row number.
    """
    matrix = {}
    for row_num in range(11, 21):
        for col_num in range(11, 21):
            row_payoff = row_num + (20 if row_num == col_num - 1 else 0)
            col_payoff = col_num + (20 if col_num == row_num - 1 else 0)
            matrix[f"request_{row_num}_request_{col_num}"] = {
                "row": row_payoff,
                "col": col_payoff,
            }
    return matrix


def build_game_config() -> GameConfig:
    """Build the game configuration for the 11-20 Money Request Game."""
    actions = [f"request_{n}" for n in range(11, 21)]
    action_descriptions = {
        f"request_{n}": f"Request {n} shekels" for n in range(11, 21)
    }
    return GameConfig(
        name="game_11_20",
        description=(
            "Two agents each pick a whole number from 11 to 20. "
            "Your payoff equals the number you pick. "
            "If you pick exactly one less than your opponent, "
            "you get a bonus of 20."
        ),
        action_type="discrete",
        actions=actions,
        action_descriptions=action_descriptions,
        payoff_type="matrix",
        grouping_mode="pairwise",
        payoff_config={"matrix": build_payoff_matrix()},
    )


async def main() -> None:
    """Run one round of the game with mock agents and print the results."""
    game_config = build_game_config()
    llm_config = LLMConfig(dialect="mock")
    llm_client = LLMClient(llm_config)

    agents = [
        ExperimentAgent(
            name="Alice",
            properties={},
            llm_config=llm_config,
            role_prompt="You are Alice, an ambitious agent who wants to maximize your payoff.",
        ),
        ExperimentAgent(
            name="Bob",
            properties={},
            llm_config=llm_config,
            role_prompt="You are Bob, a cautious agent who wants a fair outcome.",
        ),
    ]

    runner = ExperimentRunner(
        agents=agents,
        game_config=game_config,
        llm_client=llm_client,
        round_visibility="simultaneous",
    )
    round_results = await runner.run(max_rounds=1)

    round_result = round_results[0]
    print("=== Round 1 results ===")
    for action in round_result.actions:
        print(f"  {action.agent_name} chose: {action.action_name}")

    print("\nComputed payoffs (round_results[0].payoffs):")
    for agent_name, payoff in (round_result.payoffs or {}).items():
        print(f"  {agent_name}: {payoff}")

    print("\nFinal scores:")
    for agent in agents:
        print(f"  {agent.name}: {agent.score}")

    print("\n=== Sanity checks (known payoff table entries) ===")
    matrix = build_payoff_matrix()
    known_entries = [
        ("request_11_request_11", {"row": 11, "col": 11}),
        ("request_19_request_20", {"row": 39, "col": 20}),
        ("request_20_request_19", {"row": 20, "col": 39}),
        ("request_15_request_15", {"row": 15, "col": 15}),
    ]
    for key, expected in known_entries:
        actual = matrix[key]
        if actual != expected:
            raise AssertionError(
                f"Payoff mismatch for {key}: got {actual}, expected {expected}"
            )
        print(f"  {key}: {actual} (expected {expected}) OK")

    print("\nAll sanity checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
