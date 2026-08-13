"""
Re-run the 11-20 Money Request Game on two OpenRouter models, reusing the exact
prompts that FOS previously sent (logged in llm_traffic.jsonl) but with the
"=== SECTION 5" JSON-output-requirement block stripped out of each prompt.

This is a direct API re-run: it talks to OpenRouter with urllib.request and does
not use the ExperimentRunner or FOS prompt builders at all.

What this does, in plain terms:
- Read llm_traffic.jsonl (in the repo root) line by line and keep the entries
  whose model is "anthropic/claude-sonnet-5" or "openai/gpt-5.6-luna" in the
  order they appear in the file (20 of each).
- For every kept entry, cut the prompt at the "=== SECTION 5" marker so the
  model no longer sees the strict "respond with ONLY JSON" requirement, and
  keep the role unchanged.
- Send each stripped prompt to https://openrouter.ai/api/v1/chat/completions
  one at a time with temperature 0.0 and max_tokens 16384, using the
  OPENROUTER_API_KEY environment variable. Measure how long each call took
  with time.perf_counter().
- For each response, record the username, model, the raw answer text, the
  parsed chosen number (amount) and reason, the reasoning content and token
  count, the finish reason, the elapsed time, whether the chosen number was
  between 11 and 20, and the error message if the call failed.
- Save the results per model:
  - JSONL: results/{model_with_slashes_replaced_by_underscores}_nos5.jsonl
    (one JSON object per decision, non-ASCII kept as-is).
  - CSV:   results/{model_with_slashes_replaced_by_underscores}_nos5.csv
    (header written once, one row per decision).
- For each model, print the total number of records, how many succeeded, how
  many had a non-empty reason, and the distribution of chosen numbers.

Functions:
    load_traffic_entries(path)      - read the traffic log, keep the two target
                                      models' entries in file order.
    strip_section_5(messages)       - cut every message's content at the
                                      "=== SECTION 5" marker, keep the role.
    extract_username(content)       - pull the "You are <name>." username out of
                                      an original prompt.
    post_decision(model, messages, api_key)
                                   - send one stripped prompt to OpenRouter,
                                      return the parsed response and elapsed time.
    parse_raw_content(raw_content)  - pull the amount and reason out of the
                                      model's raw answer text.
    build_record(entry, response, elapsed, error)
                                   - turn one API response into a decision record.
    run_one(entry, api_key)         - run one full decision (strip, call, parse)
                                      with error handling.
    results_jsonl_path(model)       - the results JSONL path for one model.
    results_csv_path(model)         - the results CSV path for one model.
    write_jsonl(model, records)     - append one model's records to its JSONL file.
    write_csv(model, records)       - write one model's records to its CSV file
                                      (header once, one row per decision).
    print_stats(model, records)     - print counts and the chosen-number
                                      distribution for one model.
    main()                          - run all decisions and write the results.
"""

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.request
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TRAFFIC_PATH = _REPO_ROOT / "llm_traffic.jsonl"
_API_URL = "https://openrouter.ai/api/v1/chat/completions"
_SECTION_5_MARKER = "=== SECTION 5"
_TARGET_MODELS = ("anthropic/claude-sonnet-5", "openai/gpt-5.6-luna")
_MAX_TOKENS = 16384
_TEMPERATURE = 0.0
_USERNAME_PATTERN = re.compile(r"You are ([A-Za-z0-9_\-]+)\.")


@dataclass
class DecisionRecord:
    """One persona's decision in the 11-20 game (no-section-5 re-run)."""

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
    jsonl_keys: tuple[str, ...] = field(
        default=(
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
        ),
        init=False,
    )

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


def load_traffic_entries(path: Path) -> list[dict]:
    """Read the traffic log and keep the two target models' entries in file order."""
    entries: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("model") in _TARGET_MODELS:
                entries.append(entry)
    return entries


def strip_section_5(messages: list[dict]) -> list[dict]:
    """Cut every message's content at the "=== SECTION 5" marker, keep the role.

    A message whose content is not a string or does not contain the marker is
    left untouched. The returned list is new; the input is not modified.
    """
    stripped: list[dict] = []
    for message in messages:
        content = message.get("content")
        if isinstance(content, str) and _SECTION_5_MARKER in content:
            content = content.split(_SECTION_5_MARKER)[0].rstrip()
        stripped.append({"role": message.get("role"), "content": content})
    return stripped


def extract_username(content: str) -> str:
    """Pull the "You are <name>." username out of an original prompt."""
    match = _USERNAME_PATTERN.search(content)
    return match.group(1) if match else ""


def post_decision(model: str, messages: list[dict], api_key: str) -> tuple[dict, float]:
    """Send one stripped prompt to OpenRouter and return the response and time.

    Returns (response_dict, elapsed_seconds). Raises on network or HTTP errors.
    """
    body = json.dumps(
        {
            "model": model,
            "temperature": _TEMPERATURE,
            "max_tokens": _MAX_TOKENS,
            "messages": messages,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        _API_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    start = time.perf_counter()
    with urllib.request.urlopen(request, timeout=180) as response:
        payload = response.read().decode("utf-8")
    elapsed = time.perf_counter() - start
    return json.loads(payload), elapsed


def parse_raw_content(raw_content: str | None) -> tuple[int | None, str]:
    """Pull the amount and reason out of the model's raw answer text.

    Finds the first "{" and last "}" in the text and parses that blob as JSON.
    Returns (amount or None, reason or ""). A missing reason becomes "".
    """
    if not raw_content:
        return None, ""
    start = raw_content.find("{")
    end = raw_content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None, ""
    blob = raw_content[start : end + 1]
    try:
        obj = json.loads(blob)
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
    entry: dict,
    response: dict,
    elapsed: float,
    error: str | None,
) -> DecisionRecord:
    """Turn one API response into a decision record.

    When error is not None the response is ignored and the record carries the
    error message with succeeded=False.
    """
    model = entry["model"]
    original_content = ""
    for message in entry.get("messages", []):
        if isinstance(message.get("content"), str):
            original_content = message["content"]
            break
    username = extract_username(original_content)
    if error is not None:
        return DecisionRecord(
            username=username,
            model=model,
            chosen_number=None,
            reason="",
            reasoning_tokens=None,
            reasoning_content=None,
            finish_reason=None,
            raw_content=None,
            elapsed_seconds=elapsed,
            succeeded=False,
            error=error,
        )
    try:
        choice = response["choices"][0]
        message = choice["message"]
        raw_content = message.get("content")
        chosen_number, reason = parse_raw_content(raw_content)
        reasoning = message.get("reasoning")
        reasoning_content = (
            reasoning.get("reasoning_content")
            if isinstance(reasoning, dict)
            else None
        )
        usage = response.get("usage", {})
        details = usage.get("completion_tokens_details", {})
        reasoning_tokens = details.get("reasoning_tokens")
        finish_reason = choice.get("finish_reason")
        succeeded = chosen_number is not None and 11 <= chosen_number <= 20
    except (KeyError, IndexError, TypeError, AttributeError, ValueError) as exc:
        return DecisionRecord(
            username=username,
            model=model,
            chosen_number=None,
            reason="",
            reasoning_tokens=None,
            reasoning_content=None,
            finish_reason=None,
            raw_content=None,
            elapsed_seconds=elapsed,
            succeeded=False,
            error=str(exc),
        )
    return DecisionRecord(
        username=username,
        model=model,
        chosen_number=chosen_number,
        reason=reason,
        reasoning_tokens=reasoning_tokens,
        reasoning_content=reasoning_content,
        finish_reason=finish_reason,
        raw_content=raw_content,
        elapsed_seconds=elapsed,
        succeeded=succeeded,
        error=None,
    )


def run_one(entry: dict, api_key: str) -> DecisionRecord:
    """Run one full decision: strip section 5, call OpenRouter, parse the answer.

    Never raises: any failure becomes a record with succeeded=False and the
    error message filled in.
    """
    stripped_messages = strip_section_5(entry.get("messages", []))
    start = time.perf_counter()
    try:
        response, elapsed = post_decision(entry["model"], stripped_messages, api_key)
    except Exception as exc:
        elapsed = time.perf_counter() - start
        return build_record(entry, {}, elapsed, str(exc))
    return build_record(entry, response, elapsed, None)


def results_jsonl_path(model: str) -> Path:
    """The results JSONL path for one model (results/{model}_nos5.jsonl)."""
    sanitized = model.replace("/", "_")
    return _REPO_ROOT / "results" / f"{sanitized}_nos5.jsonl"


def results_csv_path(model: str) -> Path:
    """The results CSV path for one model (results/{model}_nos5.csv)."""
    sanitized = model.replace("/", "_")
    return _REPO_ROOT / "results" / f"{sanitized}_nos5.csv"


def write_jsonl(model: str, records: list[DecisionRecord]) -> None:
    """Append one model's records to its JSONL file."""
    path = results_jsonl_path(model)
    with path.open("a", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record.to_jsonl_dict(), ensure_ascii=False) + "\n")


def write_csv(model: str, records: list[DecisionRecord]) -> None:
    """Write one model's records to its CSV file (header once, one row each)."""
    path = results_csv_path(model)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "username",
                "model",
                "chosen_number",
                "reason",
                "reasoning_tokens",
                "finish_reason",
                "elapsed_seconds",
                "succeeded",
            ]
        )
        for record in records:
            writer.writerow(record.to_csv_row())


def print_stats(model: str, records: list[DecisionRecord]) -> None:
    """Print counts and the chosen-number distribution for one model."""
    total = len(records)
    succeeded = sum(1 for record in records if record.succeeded)
    with_reason = sum(1 for record in records if record.reason)
    distribution = Counter(
        record.chosen_number for record in records if record.chosen_number is not None
    )
    print(f"\nModel: {model}")
    print(f"  total records: {total}")
    print(f"  succeeded: {succeeded}")
    print(f"  reason present: {with_reason}")
    print(
        "  chosen_number distribution: "
        + (", ".join(f"{n}={count}" for n, count in sorted(distribution.items())) or "(none)")
    )


def main() -> None:
    """Run all decisions for both models, write results, print stats."""
    parser = argparse.ArgumentParser(
        description="Re-run the 11-20 game prompts on OpenRouter models without "
        "the SECTION 5 block."
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Run only this model (e.g. openai/gpt-5.6-luna). "
        "Omit to run all target models.",
    )
    args = parser.parse_args()

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        print("OPENROUTER_API_KEY not set")
        sys.exit(1)
    if not _TRAFFIC_PATH.exists():
        print(f"llm_traffic.jsonl not found at {_TRAFFIC_PATH}")
        sys.exit(1)

    entries = load_traffic_entries(_TRAFFIC_PATH)
    results_dir = _REPO_ROOT / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    models: tuple[str, ...] = _TARGET_MODELS
    if args.model is not None:
        if args.model not in _TARGET_MODELS:
            print(f"unknown model {args.model!r}; expected one of {_TARGET_MODELS}")
            sys.exit(1)
        models = (args.model,)

    for model in models:
        model_entries = [entry for entry in entries if entry["model"] == model]
        records: list[DecisionRecord] = []
        for index, entry in enumerate(model_entries, start=1):
            record = run_one(entry, api_key)
            records.append(record)
            status = (
                f"chosen={record.chosen_number}"
                if record.succeeded
                else f"FAILED ({record.error})"
            )
            print(
                f"  [{record.username} {index}/{len(model_entries)}] "
                f"{status} ({record.elapsed_seconds:.2f}s)",
                flush=True,
            )
        write_jsonl(model, records)
        write_csv(model, records)
        print_stats(model, records)


if __name__ == "__main__":
    main()
