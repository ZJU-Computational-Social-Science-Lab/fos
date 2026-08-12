"""
Play the 11-20 Money Request Game 30 times on DeepSeek with the reasoning
prompt but NO persona attached, writing each decision to
results_deepseek_reasoning_baseline.csv the moment it finishes.

What this does, in plain terms:
- Run the SAME 11-20 scenario (including the "respond with reason + amount"
  instruction) 30 times against DeepSeek's "deepseek-v4-flash" model,
  temperature 0.0 and max_tokens 4096.
- The ONLY difference from the persona reasoning run is that the agent's
  role_prompt is an empty string -- there is no persona text at all. So all 30
  runs receive an identical prompt; this is a baseline of 30 repeated runs.
- FOS validates only on the "amount" field; "reason" passes through as an extra
  parameter and is captured from action.parameters (with a fallback parse of the
  raw response content).
- Right after each decision finishes, append one row to
  results_deepseek_reasoning_baseline.csv with columns:
  run_number, model, chosen_number, reason, succeeded, finish_reason.
- If a single decision fails, it is recorded as failed and the run continues.
- At the end, print the count of each number from 11 to 20 with percentages,
  and the full reason text for up to 3 runs that chose distinct numbers.

The DeepSeek API key is read from the DEEPSEEK_API_KEY environment variable.
FOS does not surface finish_reason or raw content, so attach_response_capture()
wraps the OpenAI SDK's chat.completions.create call to record both.

Functions:
    build_payoff_matrix()        - build the 10x10 payoff matrix.
    build_game_config()          - build the GameConfig (with reasoning prompt).
    build_llm_config()           - build a DeepSeek LLMConfig.
    attach_response_capture()    - wrap the SDK to record finish_reason + content.
    extract_reason(content)      - pull the "reason" field out of raw JSON text.
    parse_chosen_number(value)   - validate/return the chosen number (11-20).
    run_one_decision(...)        - run one round, return choice + reason + meta.
    write_csv_header()           - write the results CSV header.
    append_csv_row(decision)     - append one decision's row immediately.
    running_counts(decisions)    - short count string for progress lines.
    print_final_stats(decisions) - counts, percentages, and distinct reasons.
    main()                       - run all decisions, stream CSV, print stats.
"""

import asyncio
import csv
import json
import os
import re
import sys
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
_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
_DEEPSEEK_MODEL = "deepseek-v4-flash"
_RUN_COUNT = 30
_RESULTS_CSV = _REPO_ROOT / "results_deepseek_reasoning_baseline.csv"
_PROGRESS_EVERY = 10


@dataclass
class Decision:
    """One baseline decision in the 11-20 game (no persona)."""

    run_number: int
    chosen_number: int | None
    reason: str
    action_name: str
    success: bool
    error: str | None
    finish_reason: str | None


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


def build_llm_config() -> LLMConfig:
    """Build a DeepSeek LLMConfig (OpenAI-compatible dialect)."""
    return LLMConfig(
        dialect="openai",
        base_url=_DEEPSEEK_BASE_URL,
        api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        model=_DEEPSEEK_MODEL,
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
    run_number: int, llm_client: LLMClient, holder: dict
) -> Decision:
    """Run one baseline round (no persona) of the 11-20 game on DeepSeek.

    role_prompt is an empty string, so every run receives an identical prompt.
    """
    game_config = build_game_config()
    llm_config = build_llm_config()

    agent = ExperimentAgent(
        name=f"baseline_run_{run_number}",
        properties={},
        llm_config=llm_config,
        role_prompt="",  # NO persona text -- the only change vs the persona run.
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
            run_number=run_number,
            chosen_number=parse_chosen_number(action.action_name),
            reason=reason,
            action_name=action.action_name,
            success=bool(action.success),
            error=getattr(action, "error", None),
            finish_reason=holder.get("finish_reason"),
        )
    except Exception as exc:
        return Decision(
            run_number=run_number,
            chosen_number=None,
            reason=extract_reason(holder.get("content")),
            action_name="",
            success=False,
            error=repr(exc),
            finish_reason=holder.get("finish_reason"),
        )


def write_csv_header() -> None:
    """Write the results CSV header (truncating any prior file)."""
    with _RESULTS_CSV.open("w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerow(
            ["run_number", "model", "chosen_number", "reason", "succeeded", "finish_reason"]
        )


def append_csv_row(decision: Decision) -> None:
    """Append one decision's row to the results CSV immediately."""
    succeeded = "true" if decision.success else "false"
    chosen = "" if decision.chosen_number is None else str(decision.chosen_number)
    finish = "" if decision.finish_reason is None else str(decision.finish_reason)
    with _RESULTS_CSV.open("a", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerow(
            [decision.run_number, _DEEPSEEK_MODEL, chosen, decision.reason or "",
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
        print(f"\n[run {decision.run_number} -- chose {decision.chosen_number}]")
        print(decision.reason or "(no reason captured)")


async def main() -> None:
    """Run all baseline decisions, stream each to CSV, print progress + stats."""
    if not os.getenv("DEEPSEEK_API_KEY", ""):
        print("DEEPSEEK_API_KEY not set")
        sys.exit(1)

    llm_client = LLMClient(build_llm_config())
    holder = attach_response_capture(llm_client)
    write_csv_header()

    decisions: list[Decision] = []
    for run_number in range(1, _RUN_COUNT + 1):
        decision = await run_one_decision(run_number, llm_client, holder)
        decisions.append(decision)
        append_csv_row(decision)
        status = (
            f"chosen={decision.chosen_number}" if decision.success
            else f"FAILED ({decision.error})"
        )
        print(f"  [run {run_number}/{_RUN_COUNT}] {status}", flush=True)
        if run_number % _PROGRESS_EVERY == 0:
            print(
                f"  --- progress {run_number}/{_RUN_COUNT}: "
                f"{running_counts(decisions)} ---",
                flush=True,
            )

    print_final_stats(decisions)
    print(f"\nresults written to {_RESULTS_CSV}")


if __name__ == "__main__":
    asyncio.run(main())
