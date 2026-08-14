"""
Run the 11-20 Money Request Game once per persona under prompt condition 1 or 2
on one of three models, saving every decision immediately to
results/{model}_cond{condition}.jsonl and results/{model}_cond{condition}.csv
so a crash never loses finished records.

What it does:
- Read the first --personas usernames from final_200_personas.csv and load each
  persona's text from personas/{username}.txt.
- Build the full 5-section prompt manually as ONE user message. The two
  conditions differ only in Section 1 (full persona text vs "You are
  {username}."), Section 2 (plain question vs reason instruction added), and
  Section 5 (amount-only JSON vs reason+amount JSON). Sections 3 and 4 are
  identical for both conditions.
- Send it to deepseek-v4-flash (api.deepseek.com, DEEPSEEK_API_KEY),
  anthropic/claude-sonnet-5, or openai/gpt-5.6-luna (openrouter.ai,
  OPENROUTER_API_KEY) at temperature 0.0 with NO token limit.
- Parse amount/reason (first "{" to last "}" as JSON), reasoning_content,
  reasoning_tokens (usage.completion_tokens_details.reasoning_tokens),
  finish_reason, raw content, elapsed seconds, succeeded (amount in 11..20),
  error.
- Append each record to the JSONL and CSV files right away (CSV header once).
- Print per-record progress (username i/N amount=.. rt=.. ..s, flush=True) and
  a final summary (reason-present count, chosen-number distribution,
  reasoning-token min/max/mean, error count).

Functions (each documented at its def):
    load_usernames, load_persona_text - read usernames / persona files.
    build_section_1..5, build_prompt - build the 5 prompt sections.
    endpoint_for, api_key_for       - API URL and key for a model.
    post_decision                   - send one prompt to the model.
    parse_raw_content               - amount/reason from raw answer JSON.
    build_record, run_one           - response->record; full decision.
    results_jsonl_path, results_csv_path - output file paths.
    ensure_csv_header, append_jsonl_record, append_csv_record - incremental save.
    print_stats                     - final summary for the run.
    main()                          - CLI entry point.
"""

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TEMPERATURE = 0.0
_TIMEOUT_SECONDS = 300

# model name -> (API URL, environment variable holding the API key)
_MODEL_ENDPOINTS = {
    "deepseek-v4-flash": (
        "https://api.deepseek.com/chat/completions",
        "DEEPSEEK_API_KEY",
    ),
    "anthropic/claude-sonnet-5": (
        "https://openrouter.ai/api/v1/chat/completions",
        "OPENROUTER_API_KEY",
    ),
    "openai/gpt-5.6-luna": (
        "https://openrouter.ai/api/v1/chat/completions",
        "OPENROUTER_API_KEY",
    ),
}

_JSONL_KEYS = [
    "username",
    "model",
    "chosen_number",
    "reason",
    "reasoning_tokens",
    "reasoning_content",
    "finish_reason",
    "raw_content",
    "elapsed_seconds",
    "succeeded",
    "error",
]
# CSV has the same columns as JSONL minus the three not requested there.
_CSV_COLUMNS = [
    key
    for key in _JSONL_KEYS
    if key not in ("reasoning_content", "raw_content", "error")
]

# The 11-20 game text shared by both conditions (condition 2 appends the reason
# instruction after this).
_GAME_TEXT = (
    "You and another player are playing a game in which each player requests an amount of money. "
    "The amount must be (an integer) between 11 and 20 shekels. Each player will receive the amount he requests. "
    "A player will receive an additional amount of 20 shekels if he asks for exactly one shekel less than the other player.\n\n"
    "What amount of money would you request?"
)
# The reason instruction appended to the game text only in condition 2.
_REASON_INSTRUCTION = (
    "\nWhat amount of money would you request? Think as the person you are -- at the strategic level you just identified.\n"
    "What amount of money would you request? (must be an integer between 11 and 20)\n\n"
    "Respond with ONLY JSON containing two fields, in this order:\n"
    '{"reason": "explain what kind of thinker you are based on your data, what you expect the other player to do, and why you chose this number", '
    '"amount": <number>}'
)


@dataclass
class DecisionRecord:
    """One persona's decision in the 11-20 game under one condition."""

    username: str
    model: str
    chosen_number: int | None
    reason: str
    reasoning_tokens: int | None
    reasoning_content: str | None
    finish_reason: str | None
    raw_content: str | None
    elapsed_seconds: float
    succeeded: bool
    error: str | None

    def to_jsonl_dict(self) -> dict:
        """Return this record as a dict with the exact JSONL key order."""
        return {
            "username": self.username,
            "model": self.model,
            "chosen_number": self.chosen_number,
            "reason": self.reason,
            "reasoning_tokens": self.reasoning_tokens,
            "reasoning_content": self.reasoning_content,
            "finish_reason": self.finish_reason,
            "raw_content": self.raw_content,
            "elapsed_seconds": self.elapsed_seconds,
            "succeeded": self.succeeded,
            "error": self.error,
        }

    def to_csv_row(self) -> list[str]:
        """Return this record as one CSV row (strings only)."""
        return [
            self.username,
            self.model,
            "" if self.chosen_number is None else str(self.chosen_number),
            self.reason,
            "" if self.reasoning_tokens is None else str(self.reasoning_tokens),
            "" if self.finish_reason is None else str(self.finish_reason),
            f"{self.elapsed_seconds:.3f}",
            "true" if self.succeeded else "false",
        ]


def load_usernames(path: Path, n: int) -> list[str]:
    """Read the first n usernames from final_200_personas.csv."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines[:n]]


def load_persona_text(path: Path) -> str:
    """Read one persona file from the personas/ directory as a string."""
    return path.read_text(encoding="utf-8")


def build_section_1(condition: int, username: str, persona_text: str) -> str:
    """Section 1 (persona embedding); cond 2 names only, cond 1 embeds the file."""
    if condition == 2:
        return f"=== EMBODY THIS PERSON ===\nYou are {username}."
    return f"=== EMBODY THIS PERSON ===\n{persona_text}"


def build_section_2(condition: int) -> str:
    """Section 2 (game scenario); cond 2 appends the reason instruction."""
    if condition == 2:
        return _GAME_TEXT + _REASON_INSTRUCTION
    return _GAME_TEXT


def build_section_3() -> str:
    """Section 3 (available actions), identical for both conditions."""
    return "## Your Action\nChoose a value from 11 to 20."


def build_section_4() -> str:
    """Section 4 (context), identical for both conditions."""
    return "## Context\nThis is the first round - no previous context."


def build_section_5(condition: int) -> str:
    """Section 5 (JSON output requirement); cond 2 wants reason+amount JSON."""
    if condition == 2:
        return (
            "## Your Response\n"
            "Choose a number from 11 to 20.\n"
            'Respond with ONLY JSON: {"reason": <text>, "amount": <number>}'
        )
    return (
        "## Your Response\n"
        "Choose a number from 11 to 20.\n"
        'Respond with ONLY JSON: {"amount": <number>}\n\n'
        "No markdown. No explanation. Only JSON."
    )


def build_prompt(condition: int, username: str, persona_text: str) -> str:
    """Assemble the five sections into one full prompt string."""
    return (
        f"{build_section_1(condition, username, persona_text)}\n"
        "=== SECTION 2: SCENARIO ===\n\n"
        f"## Scenario\n{build_section_2(condition)}\n"
        "=== SECTION 3: AVAILABLE ACTIONS ===\n\n"
        f"{build_section_3()}\n"
        "=== SECTION 4: CONTEXT ===\n\n"
        f"{build_section_4()}\n"
        "=== SECTION 5: JSON OUTPUT REQUIREMENT ===\n"
        f"{build_section_5(condition)}"
    )


def endpoint_for(model: str) -> tuple[str, str]:
    """The API URL and key environment variable for one model."""
    return _MODEL_ENDPOINTS[model]


def api_key_for(model: str) -> str:
    """The API key for one model, read from its environment variable."""
    _, env_var = endpoint_for(model)
    return os.environ.get(env_var, "")


def post_decision(
    model: str, url: str, api_key: str, prompt: str
) -> tuple[dict, float]:
    """Send one prompt to the model and return the response and elapsed time.

    The request deliberately carries no token limit so reasoning is not cut off.
    """
    payload = {
        "model": model,
        "temperature": _TEMPERATURE,
        "messages": [{"role": "user", "content": prompt}],
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    start = time.perf_counter()
    with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
        raw = response.read().decode("utf-8")
    elapsed = time.perf_counter() - start
    return json.loads(raw), elapsed


def parse_raw_content(raw_content: str | None) -> tuple[int | None, str]:
    """Pull the amount and reason out of the model's raw answer text.

    Finds the first "{" and last "}" in the text and parses that blob as JSON.
    Returns (amount or None, reason or ""); a missing reason becomes "".
    """
    if not raw_content:
        return None, ""
    start = raw_content.find("{")
    end = raw_content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None, ""
    try:
        obj = json.loads(raw_content[start : end + 1])
    except (json.JSONDecodeError, ValueError):
        return None, ""
    if not isinstance(obj, dict):
        return None, ""
    try:
        amount = int(obj.get("amount"))
    except (TypeError, ValueError):
        amount = None
    reason = obj.get("reason")
    if not isinstance(reason, str):
        reason = "" if reason is None else str(reason)
    return amount, reason


def build_record(
    username: str,
    model: str,
    response: dict,
    elapsed: float,
    error: str | None,
) -> DecisionRecord:
    """Turn one API response into a decision record (error => failed record).

    When error is not None the response is ignored and the record carries the
    error message with succeeded=False.
    """
    record = DecisionRecord(
        username, model, None, "", None, None, None, None, elapsed, False, error
    )
    if error is not None:
        return record
    try:
        choice = response["choices"][0]
        message = choice["message"]
        raw_content = message.get("content")
        chosen_number, reason = parse_raw_content(raw_content)
        details = response.get("usage", {}).get("completion_tokens_details", {})
        record.chosen_number = chosen_number
        record.reason = reason
        record.reasoning_content = message.get("reasoning_content")
        record.reasoning_tokens = details.get("reasoning_tokens")
        record.finish_reason = choice.get("finish_reason")
        record.raw_content = raw_content
        record.succeeded = chosen_number is not None and 11 <= chosen_number <= 20
    except (KeyError, IndexError, TypeError, AttributeError, ValueError) as exc:
        record.error = str(exc)
    return record


def run_one(
    username: str,
    model: str,
    condition: int,
    persona_text: str,
    api_key: str,
) -> DecisionRecord:
    """Run one full decision: build prompt, call the model, parse the answer.

    Never raises: any failure becomes a record with succeeded=False and the
    error message filled in.
    """
    prompt = build_prompt(condition, username, persona_text)
    url, _ = endpoint_for(model)
    start = time.perf_counter()
    try:
        response, elapsed = post_decision(model, url, api_key, prompt)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        elapsed = time.perf_counter() - start
        return build_record(username, model, {}, elapsed, str(exc))
    return build_record(username, model, response, elapsed, None)


def results_jsonl_path(model: str, condition: int) -> Path:
    """The results JSONL path for one model+condition (results/..._condN.jsonl)."""
    return _REPO_ROOT / "results" / f"{model.replace('/', '_')}_cond{condition}.jsonl"


def results_csv_path(model: str, condition: int) -> Path:
    """The results CSV path for one model+condition (results/..._condN.csv)."""
    return _REPO_ROOT / "results" / f"{model.replace('/', '_')}_cond{condition}.csv"


def ensure_csv_header(path: Path) -> None:
    """Write the CSV header only when the file is new or empty (never repeated)."""
    if path.exists() and path.stat().st_size > 0:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerow(_CSV_COLUMNS)


def append_jsonl_record(path: Path, record: DecisionRecord) -> None:
    """Append one record as a JSON object to the JSONL file immediately."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record.to_jsonl_dict(), ensure_ascii=False) + "\n")


def append_csv_record(path: Path, record: DecisionRecord) -> None:
    """Append one record's row to the CSV file immediately."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerow(record.to_csv_row())


def print_stats(records: list[DecisionRecord]) -> None:
    """Print the final summary: reason count, distribution, tokens, errors."""
    total = len(records)
    with_reason = sum(1 for record in records if record.reason)
    errors = sum(1 for record in records if record.error)
    distribution = Counter(
        record.chosen_number for record in records if record.chosen_number is not None
    )
    token_counts = [
        record.reasoning_tokens
        for record in records
        if record.reasoning_tokens is not None
    ]
    print(f"\nTotal records: {total}")
    print(f"Reason present: {with_reason}")
    dist = ", ".join(f"{n}={c}" for n, c in sorted(distribution.items())) or "(none)"
    print(f"Chosen-number distribution: {dist}")
    if token_counts:
        print(
            f"Reasoning tokens: min={min(token_counts)} "
            f"max={max(token_counts)} "
            f"mean={sum(token_counts) / len(token_counts):.1f}"
        )
    else:
        print("Reasoning tokens: (none reported)")
    print(f"Errors: {errors}")


def main() -> None:
    """Run all decisions, save each result right away, print progress and stats."""
    parser = argparse.ArgumentParser(
        description=(
            "Run the 11-20 Money Request Game for personas under prompt "
            "condition 1 or 2 on one model."
        )
    )
    parser.add_argument(
        "--model",
        required=True,
        choices=list(_MODEL_ENDPOINTS),
        help="Model to query: deepseek-v4-flash, anthropic/claude-sonnet-5, "
        "or openai/gpt-5.6-luna.",
    )
    parser.add_argument(
        "--condition",
        required=True,
        choices=["1", "2"],
        help="Prompt condition: 1 (no reason instruction) or 2 (with reason "
        "instruction).",
    )
    parser.add_argument(
        "--personas",
        type=int,
        default=20,
        help="How many personas (usernames) to run, read from "
        "final_200_personas.csv (default: 20).",
    )
    args = parser.parse_args()

    condition = int(args.condition)
    model = args.model
    api_key = api_key_for(model)
    if not api_key:
        _, env_var = endpoint_for(model)
        print(f"{env_var} not set")
        sys.exit(1)

    personas_csv = _REPO_ROOT / "final_200_personas.csv"
    personas_dir = _REPO_ROOT / "personas"
    if not personas_csv.exists():
        print(f"final_200_personas.csv not found at {personas_csv}")
        sys.exit(1)
    if not personas_dir.exists():
        print(f"personas directory not found at {personas_dir}")
        sys.exit(1)

    usernames = load_usernames(personas_csv, args.personas)
    total = len(usernames)

    jsonl_path = results_jsonl_path(model, condition)
    csv_path = results_csv_path(model, condition)
    ensure_csv_header(csv_path)

    records: list[DecisionRecord] = []
    for index, username in enumerate(usernames, start=1):
        persona_path = personas_dir / f"{username}.txt"
        if not persona_path.exists():
            record = DecisionRecord(
                username,
                model,
                None,
                "",
                None,
                None,
                None,
                None,
                0.0,
                False,
                f"missing persona file {persona_path.name}",
            )
        else:
            record = run_one(
                username, model, condition, load_persona_text(persona_path), api_key
            )
        records.append(record)
        append_jsonl_record(jsonl_path, record)
        append_csv_record(csv_path, record)
        amount = record.chosen_number if record.chosen_number is not None else "FAILED"
        print(
            f"{record.username} {index}/{total} amount={amount} "
            f"rt={record.reasoning_tokens} {record.elapsed_seconds:.2f}s",
            flush=True,
        )
    print_stats(records)


if __name__ == "__main__":
    main()
