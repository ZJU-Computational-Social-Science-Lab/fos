"""
Run 12 single-round 11-20 Money Request Game decisions per model across 3
LM Studio models, using 12 different personas (36 decisions in total).

The script reads the first 12 usernames from final_200_personas.csv, loads
each persona text file from personas/{username}.txt, and for each of the 3
models in MODELS runs exactly one round of the 11-20 game for every persona
against a real LLM served by LM Studio at http://localhost:1234/v1.

A fresh LLMConfig (dialect="openai", base_url="http://localhost:1234/v1",
api_key="lm-studio", model=current model) is built for every persona, and a
fresh LLMClient is created for every model. If LM Studio cannot be reached
at startup, the script prints "LM Studio not reachable" and exits with
code 1.

It prints a per-model table of which amount each persona requested with a
count of how many personas chose each number from 11 to 20, then a
cross-model comparison table. Exit code is 0 on success.

Functions:
    lm_studio_reachable()       — Check whether LM Studio answers on port 1234.
    load_twelve_usernames()     — Read the first 12 usernames from final_200_personas.csv.
    load_persona_text(user)     — Read one persona file as a single string.
    build_payoff_matrix()       — Build the full 10x10 payoff matrix for the game.
    build_game_config()         — Build the GameConfig for the 11-20 Money Request Game.
    build_llm_config(model)     — Build a fresh LLMConfig pointing at LM Studio.
    run_one_decision(user, model, client) — Run one round and return the choice.
    parse_chosen_number()       — Extract the requested number from an action name.
    print_model_table()         — Print one model's table plus per-number counts.
    print_comparison_table()    — Print the cross-model comparison table.
    main()                      — Run all 36 decisions and print all tables.
"""

import asyncio
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

# Make the worktree's `src` importable when this script is run directly.
_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from fos.core.experiment.agent import ExperimentAgent  # noqa: E402
from fos.core.experiment.game_configs import GameConfig  # noqa: E402
from fos.core.experiment.runner import ExperimentRunner  # noqa: E402
from fos.core.llm.client import LLMClient  # noqa: E402
from fos.core.llm_config import LLMConfig  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parent.parent
_LM_STUDIO_BASE_URL = "http://localhost:1234/v1"
_LM_STUDIO_API_KEY = "lm-studio"

# The 3 models to test on LM Studio.
MODELS = [
    "openai/gpt-oss-20b",
    "google/gemma-4-26b-a4b",
    "qwen/qwen3.6-35b-a3b",
]

# Short display names used for the cross-model comparison table.
_COMPARISON_COLUMNS = ["gpt-oss-20b", "gemma-4-26b", "qwen3.6-35b"]

_PERSONA_COUNT = 12


@dataclass
class Decision:
    """One persona's single decision in the 11-20 game."""

    username: str
    chosen_number: int | None
    action_name: str
    success: bool
    error: str | None


def lm_studio_reachable() -> bool:
    """Check whether LM Studio answers a models request on localhost:1234."""
    try:
        with urllib.request.urlopen(
            f"{_LM_STUDIO_BASE_URL}/models", timeout=5
        ) as resp:
            return resp.status == 200
    except Exception:
        return False


def load_twelve_usernames() -> list[str]:
    """Read the first 12 usernames from final_200_personas.csv."""
    csv_path = _REPO_ROOT / "final_200_personas.csv"
    lines = csv_path.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines[:_PERSONA_COUNT]]


def load_persona_text(username: str) -> str:
    """Read one persona file from the personas/ directory as a string."""
    persona_path = _REPO_ROOT / "personas" / f"{username}.txt"
    return persona_path.read_text(encoding="utf-8")


def build_payoff_matrix() -> dict:
    """Build the full 10x10 payoff matrix for the 11-20 game.

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
            "You and another player are playing a game in which each player requests "
            "an amount of money. The amount must be (an integer) between 11 and 20 "
            "shekels. Each player will receive the amount he requests. A player will "
            "receive an additional amount of 20 shekels if he asks for exactly one "
            "shekel less than the other player."
        ),
        action_type="discrete",
        actions=actions,
        action_descriptions=action_descriptions,
        payoff_type="matrix",
        grouping_mode="pairwise",
        payoff_config={"matrix": build_payoff_matrix()},
    )


def build_llm_config(model: str) -> LLMConfig:
    """Build a fresh LLMConfig pointing at LM Studio for one model."""
    return LLMConfig(
        dialect="openai",
        base_url=_LM_STUDIO_BASE_URL,
        api_key=_LM_STUDIO_API_KEY,
        model=model,
    )


def parse_chosen_number(action_name: str) -> int | None:
    """Extract the requested number (11-20) from an action name like request_15."""
    if not action_name or not action_name.startswith("request_"):
        return None
    try:
        return int(action_name[len("request_"):])
    except ValueError:
        return None


async def run_one_decision(
    username: str, model: str, llm_client: LLMClient
) -> Decision:
    """Run exactly one round of the 11-20 game for one persona on one model."""
    persona_text = load_persona_text(username)
    game_config = build_game_config()
    llm_config = build_llm_config(model)

    agent = ExperimentAgent(
        name=username,
        properties={},
        llm_config=llm_config,
        role_prompt=persona_text,
    )

    runner = ExperimentRunner(
        agents=[agent],
        game_config=game_config,
        llm_client=llm_client,
        round_visibility="simultaneous",
    )
    round_results = await runner.run(max_rounds=1)

    action = round_results[0].actions[0]
    return Decision(
        username=username,
        chosen_number=parse_chosen_number(action.action_name),
        action_name=action.action_name,
        success=action.success,
        error=action.error,
    )


def print_model_table(model: str, decisions: list[Decision]) -> None:
    """Print one model's username/chosen table and the 11-20 counts."""
    print(f"=== MODEL: {model} ===")
    print(f"{'username':<22}{'chosen':<13}")
    print("-" * 35)
    for decision in decisions:
        chosen = decision.action_name if decision.action_name else "error"
        print(f"{decision.username:<22}{chosen:<13}")

    print()
    print("Counts:")
    counts = {n: 0 for n in range(11, 21)}
    for decision in decisions:
        if decision.chosen_number is not None:
            counts[decision.chosen_number] += 1
    for n in range(11, 21):
        print(f"  {n}: {counts[n]}")


def print_comparison_table(
    usernames: list[str], all_decisions: dict[str, list[Decision]]
) -> None:
    """Print the cross-model comparison table of chosen actions."""
    header = f"{'username':<18}"
    for column in _COMPARISON_COLUMNS:
        header += f"{column:<15}"
    print(header)
    print("-" * 67)
    for i, username in enumerate(usernames):
        row = f"{username:<18}"
        for model in MODELS:
            decision = all_decisions[model][i]
            chosen = decision.action_name if decision.action_name else "error"
            row += f"{chosen:<15}"
        print(row)


async def main() -> None:
    """Run 36 decisions (3 models x 12 personas), print tables and counts."""
    if not lm_studio_reachable():
        print("LM Studio not reachable")
        sys.exit(1)

    usernames = load_twelve_usernames()
    all_decisions: dict[str, list[Decision]] = {}

    for model in MODELS:
        print(f"Running model: {model} ...")
        llm_client = LLMClient(build_llm_config(model))
        decisions: list[Decision] = []
        for username in usernames:
            decision = await run_one_decision(username, model, llm_client)
            decisions.append(decision)
            print(f"  {username}: {decision.action_name}")
        all_decisions[model] = decisions
        print_model_table(model, decisions)

    print_comparison_table(usernames, all_decisions)


if __name__ == "__main__":
    asyncio.run(main())
