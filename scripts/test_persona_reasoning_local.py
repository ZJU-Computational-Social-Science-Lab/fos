"""
Play the 11-20 Money Request Game once per persona on LM Studio with the
reasoning prompt and the persona text attached, writing each decision to
results/{model}_persona_reasoning.csv the moment it finishes.

What this does, in plain terms:
- Read the first N usernames (--personas, default 3) from final_200_personas.csv.
- For each username, load the persona text from personas/{username}.txt and run
  the SAME 11-20 scenario (including the "respond with reason + amount"
  instruction) once against the LM Studio model given by the REQUIRED --model
  argument, temperature 0.0 and max_tokens 4096.
- FOS validates only on the "amount" field; "reason" passes through as an extra
  parameter and is captured from action.parameters (with a fallback parse of the
  raw response content).
- Right after each decision finishes, append one row to
  results/{model}_persona_reasoning.csv with columns:
  username, model, chosen_number, reason, succeeded, finish_reason.
- If a single decision fails, it is recorded as failed and the run continues.
- At the end, print the count of each number from 11 to 20 with percentages,
  and the full reason text for up to 3 runs that chose distinct numbers.
- If LM Studio cannot be reached at startup, print "LM Studio not reachable"
  and exit with code 1.

FOS does not surface finish_reason or raw content, so attach_response_capture()
wraps the OpenAI SDK's chat.completions.create call to record both. When
--verbose is passed, the full raw model response content is printed after each
decision so a human can confirm both "reason" and "amount" fields are present.

Functions:
    lm_studio_reachable()        - check whether LM Studio answers on port 1234.
    load_usernames(n)            - read the first n usernames from final_200_personas.csv.
    load_persona_text(username)  - read one persona file as a single string.
    build_payoff_matrix()        - build the 10x10 payoff matrix.
    build_game_config()          - build the GameConfig (with reasoning prompt).
    build_llm_config(model)      - build an LM Studio LLMConfig for one model.
    attach_response_capture()    - wrap the SDK to record finish_reason + content.
    extract_reason(content)      - pull the "reason" field out of raw JSON text.
    parse_chosen_number(value)   - validate/return the chosen number (11-20).
    run_one_decision(...)        - run one round, return choice + reason + meta.
    results_csv_path(model)      - the CSV path for a model (safe file name).
    write_csv_header(model)      - write the results CSV header.
    append_csv_row(model, ...)   - append one decision's row immediately.
    running_counts(decisions)    - short count string for progress lines.
    print_final_stats(decisions) - counts, percentages, and distinct reasons.
    main()                       - run all decisions, stream CSV, print stats.
"""

import argparse
import asyncio
import csv
import json
import re
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
_PROGRESS_EVERY = 10


@dataclass
class Decision:
    """One persona's decision in the 11-20 game (persona reasoning run)."""

    username: str
    chosen_number: int | None
    reason: str
    action_name: str
    success: bool
    error: str | None
    finish_reason: str | None


def lm_studio_reachable() -> bool:
    """Check whether LM Studio answers a models request on localhost:1234."""
    try:
        with urllib.request.urlopen(
            f"{_LM_STUDIO_BASE_URL}/models", timeout=5
        ) as resp:
            return resp.status == 200
    except Exception:
        return False


def load_usernames(n: int) -> list[str]:
    """Read the first n usernames from final_200_personas.csv."""
    csv_path = _REPO_ROOT / "final_200_personas.csv"
    lines = csv_path.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines[:n]]


def load_persona_text(username: str) -> str:
    """Read one persona file from the personas/ directory as a string."""
    persona_path = _REPO_ROOT / "personas" / f"{username}.txt"
    return persona_path.read_text(encoding="utf-8")


def build_payoff_matrix() -> dict:
    """Build the full 10x10 payoff matrix for the 11-20 game.

    Row payoff = row number, plus 20 if the row number is exactly one less than
    the column number. Column payoff is the mirror of that rule.
    """
    matrix = {}
    for row_num in range(11, 21):
        for col_num in range(11, 21):
            row_payoff = row_num + (20 if row_num == col_num - 1 else 0)
            col_payoff = col_num + (20 if col_num == row_num - 1 else 0)
            matrix[f"{row_num}_{col_num}"] = {"row": row_payoff, "col": col_payoff}
    return matrix


def build_game_config() -> GameConfig:
    """Build the game configuration for the 11-20 game with the reasoning prompt.

    This is the same scenario text used in the persona reasoning run, asking the
    model to respond with JSON containing both "reason" and "amount".
    """
    return GameConfig(
        name="game_11_20",
        description=(
            "You and another player are playing a game in which each player "
            "requests an amount of money. The amount must be (an integer) "
            "between 11 and 20 shekels. Each player will receive the amount "
            "he requests. A player will receive an additional amount of 20 "
            "shekels if he asks for exactly one shekel less than the other "
            "player.\n\n"
            "What amount of money would you request? "
            "Think as the person you are -- at the strategic level you just identified.\n"
            "What amount of money would you request? (must be an integer between 11 and 20)\n\n"
            "Respond with ONLY JSON containing two fields, in this order:\n"
            '{"reason": "explain what kind of thinker you are based on your data, what you expect the other player to do, and why you chose this number", "amount": <number>}'
        ),
        action_type="integer",
        actions=[],
        output_field="amount",
        min=11,
        max=20,
        payoff_type="matrix",
        grouping_mode="pairwise",
        payoff_config={"matrix": build_payoff_matrix()},
    )


def build_llm_config(model: str) -> LLMConfig:
    """Build an LM Studio LLMConfig (OpenAI-compatible dialect) for a model."""
    return LLMConfig(
        dialect="openai",
        base_url=_LM_STUDIO_BASE_URL,
        api_key=_LM_STUDIO_API_KEY,
        model=model,
        temperature=0.0,
        max_tokens=4096,
    )


def attach_response_capture(llm_client: LLMClient) -> dict:
    """Wrap the OpenAI SDK create() to record finish_reason and raw content.

    FOS returns only the parsed action, so we patch the Completions class method
    to stash the most recent finish_reason and message content into the holder.
    The only SDK call during a single run is the decision itself.
    """
    holder = {"finish_reason": None, "content": None}
    completions = llm_client.client.chat.completions
    cls = type(completions)
    original = cls.create

    def wrapped(self, *args, **kwargs):
        resp = original(self, *args, **kwargs)
        try:
            holder["finish_reason"] = resp.choices[0].finish_reason
        except Exception:
            holder["finish_reason"] = None
        try:
            holder["content"] = resp.choices[0].message.content
        except Exception:
            holder["content"] = None
        return resp

    cls.create = wrapped
    return holder


def extract_reason(content: str | None) -> str:
    """Pull the "reason" field out of the model's raw JSON response text.

    Tolerates markdown code fences and extra text around the JSON object. If no
    reason can be parsed, returns an empty string.
    """
    if not content:
        return ""
    text = content.strip()
    fence = re.match(r"^```(?:json|JSON)?\s*", text)
    if fence:
        text = text[fence.end():]
    text = text.rstrip("`").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        blob = text[start:end + 1]
        try:
            obj = json.loads(blob)
        except Exception:
            return ""
        if isinstance(obj, dict):
            value = obj.get("reason")
            if isinstance(value, str):
                return value
            if value is not None:
                return str(value)
    return ""


def parse_chosen_number(value) -> int | None:
    """Return the requested number (11-20) the agent chose, else None."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if 11 <= number <= 20:
        return number
    return None


async def run_one_decision(
    username: str, model: str, llm_client: LLMClient, holder: dict
) -> Decision:
    """Run one round of the 11-20 game for one persona on LM Studio.

    role_prompt is the persona text loaded from personas/{username}.txt.
    """
    game_config = build_game_config()
    llm_config = build_llm_config(model)

    agent = ExperimentAgent(
        name=username,
        properties={},
        llm_config=llm_config,
        role_prompt=load_persona_text(username),
    )
    runner = ExperimentRunner(
        agents=[agent],
        game_config=game_config,
        llm_client=llm_client,
        round_visibility="simultaneous",
    )
    holder["finish_reason"] = None
    holder["content"] = None
    try:
        round_results = await runner.run(max_rounds=1)
        action = round_results[0].actions[0]
        reason = ""
        params = getattr(action, "parameters", None) or {}
        if isinstance(params.get("reason"), str) and params["reason"]:
            reason = params["reason"]
        elif params.get("reason") is not None:
            reason = str(params["reason"])
        if not reason:
            reason = extract_reason(holder.get("content"))
        return Decision(
            username=username,
            chosen_number=parse_chosen_number(action.action_name),
            reason=reason,
            action_name=action.action_name,
            success=bool(action.success),
            error=getattr(action, "error", None),
            finish_reason=holder.get("finish_reason"),
        )
    except Exception as exc:
        return Decision(
            username=username,
            chosen_number=None,
            reason=extract_reason(holder.get("content")),
            action_name="",
            success=False,
            error=repr(exc),
            finish_reason=holder.get("finish_reason"),
        )


def results_csv_path(model: str) -> Path:
    """Build the results CSV path for a model, with '/' replaced by '_'."""
    safe_model = model.replace("/", "_")
    return _REPO_ROOT / "results" / f"{safe_model}_persona_reasoning.csv"


def write_csv_header(model: str) -> None:
    """Write the results CSV header (truncating any prior file)."""
    with results_csv_path(model).open("w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerow(
            ["username", "model", "chosen_number", "reason", "succeeded", "finish_reason"]
        )


def append_csv_row(model: str, decision: Decision) -> None:
    """Append one decision's row to the results CSV immediately."""
    succeeded = "true" if decision.success else "false"
    chosen = "" if decision.chosen_number is None else str(decision.chosen_number)
    finish = "" if decision.finish_reason is None else str(decision.finish_reason)
    with results_csv_path(model).open("a", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerow(
            [decision.username, model, chosen, decision.reason or "",
             succeeded, finish]
        )


def running_counts(decisions: list[Decision]) -> str:
    """Build a short 'n=count' summary of choices so far for progress lines."""
    counts = {n: 0 for n in range(11, 21)}
    for decision in decisions:
        if decision.chosen_number is not None:
            counts[decision.chosen_number] += 1
    parts = [f"{n}={counts[n]}" for n in range(11, 21) if counts[n]]
    return ", ".join(parts) if parts else "(none yet)"


def print_final_stats(decisions: list[Decision]) -> None:
    """Print 11-20 counts with percentages and reasons for distinct choices."""
    total = len(decisions)
    successes = sum(1 for d in decisions if d.success)
    failures = total - successes

    counts = {n: 0 for n in range(11, 21)}
    for decision in decisions:
        if decision.chosen_number is not None:
            counts[decision.chosen_number] += 1

    print("\nCounts (11-20):")
    for n in range(11, 21):
        pct = (counts[n] / successes * 100.0) if successes else 0.0
        print(f"  {n}: {counts[n]}  ({pct:.1f}% of {successes} successful)")
    print(f"\nTotal decisions: {total}")
    print(f"Successful: {successes}")
    print(f"Failures: {failures}")

    distinct: dict[int, Decision] = {}
    for decision in decisions:
        if decision.chosen_number is not None and decision.chosen_number not in distinct:
            distinct[decision.chosen_number] = decision
    sample = list(distinct.values())[:3]
    print(f"\nDistinct numbers chosen: {len(distinct)}")
    if len(distinct) < 2:
        print("(little or no variation in choices)")
    print("\nReasons for up to 3 runs with distinct choices:")
    for decision in sample:
        print(f"\n[{decision.username} -- chose {decision.chosen_number}]")
        print(decision.reason or "(no reason captured)")


async def main() -> None:
    """Run all persona decisions, stream each to CSV, print progress + stats."""
    parser = argparse.ArgumentParser(
        description="Run the 11-20 Money Request Game once per persona on LM Studio."
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Model name served by LM Studio (required, e.g. openai/gpt-oss-20b).",
    )
    parser.add_argument(
        "--personas",
        type=int,
        default=3,
        help="How many personas (usernames) to run, read from final_200_personas.csv.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print the full raw model response content after each decision.",
    )
    args = parser.parse_args()
    model = args.model

    if not lm_studio_reachable():
        print("LM Studio not reachable")
        sys.exit(1)

    usernames = load_usernames(args.personas)
    total = len(usernames)

    llm_client = LLMClient(build_llm_config(model))
    holder = attach_response_capture(llm_client)

    results_dir = _REPO_ROOT / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    write_csv_header(model)

    decisions: list[Decision] = []
    for index, username in enumerate(usernames, start=1):
        decision = await run_one_decision(username, model, llm_client, holder)
        decisions.append(decision)
        append_csv_row(model, decision)
        status = (
            f"chosen={decision.chosen_number}" if decision.success
            else f"FAILED ({decision.error})"
        )
        print(f"  [{username} {index}/{total}] {status}", flush=True)
        if args.verbose:
            print(
                f"  --- raw response: {holder.get('content')!r}",
                flush=True,
            )
        if index % _PROGRESS_EVERY == 0:
            print(
                f"  --- progress {index}/{total}: "
                f"{running_counts(decisions)} ---",
                flush=True,
            )

    print_final_stats(decisions)
    print(f"\nresults written to {results_csv_path(model)}")


if __name__ == "__main__":
    asyncio.run(main())
