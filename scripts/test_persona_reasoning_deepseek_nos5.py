"""
Re-run the 11-20 Money Request Game on the DeepSeek model, reusing the exact
prompts that FOS previously sent (logged in llm_traffic.jsonl) but with the
"=== SECTION 5" JSON-output-requirement block stripped out of each prompt.

This is a direct API re-run: it talks to DeepSeek with urllib.request and does
not use the ExperimentRunner or FOS prompt builders at all.

What this does, in plain terms:
- Read llm_traffic.jsonl (in the repo root) line by line and keep the entries
  whose model is "deepseek-v4-flash" and whose message content contains the
  phrase "two fields" (these are the 11-20 reasoning prompts; exactly 20 of
  them), in the order they appear in the file.
- For every kept entry, cut the prompt at the "=== SECTION 5" marker so the
  model no longer sees the strict "respond with ONLY JSON" requirement, and
  keep the role unchanged.
- Send each stripped prompt to https://api.deepseek.com/chat/completions one at
  a time with temperature 0.0 and no token cap, using the DEEPSEEK_API_KEY
  environment variable. Measure how long each call took with
  time.perf_counter().
- For each response, record the username, model, the raw answer text, the
  parsed chosen number (amount) and reason, the reasoning content and token
  count, the finish reason, the elapsed time, whether the chosen number was
  between 11 and 20, and the error message if the call failed.
- Save the results INCREMENTALLY: the moment one decision finishes, one record
  is APPENDED to the JSONL file and one row is APPENDED to the CSV file, so a
  crash never loses the records that already finished.
  - JSONL: results/deepseek-v4-flash_nos5.jsonl (one JSON object per decision,
    non-ASCII kept as-is).
  - CSV:   results/deepseek-v4-flash_nos5.csv (header written once, one row per
    decision).
- Print progress per record (username, index/total, amount, reasoning tokens,
  elapsed seconds, flush=True) and a final summary (how many records had a
  non-empty reason, the chosen-number distribution, the reasoning-token
  min/max/mean, and how many errors occurred).

Functions:
    load_traffic_entries(path) - read the traffic log, keep the DeepSeek
                                 "two fields" entries in file order.
    strip_section_5(messages)  - cut every message's content at the
                                 "=== SECTION 5" marker, keep the role.
    extract_username(content)  - pull the "You are <name>." username out of an
                                 original prompt.
    post_decision(messages, api_key)
                               - send one stripped prompt to DeepSeek, return
                                 the parsed response and elapsed time.
    parse_raw_content(raw_content)
                               - pull the amount and reason out of the model's
                                 raw answer text.
    build_record(entry, response, elapsed, error)
                               - turn one API response into a decision record.
    run_one(entry, api_key)    - run one full decision (strip, call, parse)
                                 with error handling.
    results_jsonl_path()       - the results JSONL path (fixed for DeepSeek).
    results_csv_path()         - the results CSV path (fixed for DeepSeek).
    ensure_csv_header()        - write the CSV header only if the file is new
                                 or empty.
    append_jsonl_record(record)- append one record to the JSONL file.
    append_csv_record(record)  - append one record's row to the CSV file.
    print_stats(records)       - print the final summary for the run.
    main()                     - run all decisions, saving each result right
                                 away.
"""

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
_API_URL = "https://api.deepseek.com/chat/completions"
_SECTION_5_MARKER = "=== SECTION 5"
_TWO_FIELDS_PHRASE = "two fields"
_MODEL = "deepseek-v4-flash"
_TEMPERATURE = 0.0
_TIMEOUT_SECONDS = 300
_USERNAME_PATTERN = re.compile(r"You are ([A-Za-z0-9_\-]+)\.")

_CSV_COLUMNS = [
    "username",
    "model",
    "chosen_number",
    "reason",
    "reasoning_tokens",
    "finish_reason",
    "elapsed_seconds",
    "succeeded",
]
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
    jsonl_keys: tuple[str, ...] = field(default=tuple(_JSONL_KEYS), init=False)

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
    """Read the traffic log and keep the DeepSeek "two fields" entries.

    An entry is kept when its model is deepseek-v4-flash and its joined message
    content contains the phrase "two fields". Entries keep their file order.
    """
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
            if entry.get("model") != _MODEL:
                continue
            content = " ".join(
                str(message.get("content", ""))
                for message in entry.get("messages", [])
                if isinstance(message.get("content"), str)
            )
            if _TWO_FIELDS_PHRASE in content:
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


def post_decision(messages: list[dict], api_key: str) -> tuple[dict, float]:
    """Send one stripped prompt to DeepSeek and return the response and time.

    Returns (response_dict, elapsed_seconds). Raises on network or HTTP errors.
    The request deliberately carries no token cap so reasoning is not cut off.
    """
    body = json.dumps(
        {
            "model": _MODEL,
            "temperature": _TEMPERATURE,
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
    with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
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
    original_content = ""
    for message in entry.get("messages", []):
        if isinstance(message.get("content"), str):
            original_content = message["content"]
            break
    username = extract_username(original_content)
    if error is not None:
        return DecisionRecord(
            username=username,
            model=_MODEL,
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
        reasoning_content = message.get("reasoning_content")
        usage = response.get("usage", {})
        details = usage.get("completion_tokens_details", {})
        reasoning_tokens = details.get("reasoning_tokens")
        finish_reason = choice.get("finish_reason")
        succeeded = chosen_number is not None and 11 <= chosen_number <= 20
    except (KeyError, IndexError, TypeError, AttributeError, ValueError) as exc:
        return DecisionRecord(
            username=username,
            model=_MODEL,
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
        model=_MODEL,
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
    """Run one full decision: strip section 5, call DeepSeek, parse the answer.

    Never raises: any failure becomes a record with succeeded=False and the
    error message filled in.
    """
    stripped_messages = strip_section_5(entry.get("messages", []))
    start = time.perf_counter()
    try:
        response, elapsed = post_decision(stripped_messages, api_key)
    except Exception as exc:
        elapsed = time.perf_counter() - start
        return build_record(entry, {}, elapsed, str(exc))
    return build_record(entry, response, elapsed, None)


def results_jsonl_path() -> Path:
    """The results JSONL path (results/deepseek-v4-flash_nos5.jsonl)."""
    return _REPO_ROOT / "results" / f"{_MODEL}_nos5.jsonl"


def results_csv_path() -> Path:
    """The results CSV path (results/deepseek-v4-flash_nos5.csv)."""
    return _REPO_ROOT / "results" / f"{_MODEL}_nos5.csv"


def ensure_csv_header() -> None:
    """Write the CSV header only when the file is new or empty.

    The header is never repeated on later appends, so a resumed run keeps a
    single header at the top of the file.
    """
    path = results_csv_path()
    if path.exists() and path.stat().st_size > 0:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerow(_CSV_COLUMNS)


def append_jsonl_record(record: DecisionRecord) -> None:
    """Append one record as a JSON object to the JSONL file immediately."""
    path = results_jsonl_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record.to_jsonl_dict(), ensure_ascii=False) + "\n")


def append_csv_record(record: DecisionRecord) -> None:
    """Append one record's row to the CSV file immediately."""
    path = results_csv_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerow(record.to_csv_row())


def print_stats(records: list[DecisionRecord]) -> None:
    """Print the final summary: reason count, distribution, tokens, errors."""
    total = len(records)
    succeeded = sum(1 for record in records if record.succeeded)
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
    print(f"Succeeded: {succeeded}")
    print(f"Reason present: {with_reason}")
    print(
        "Chosen-number distribution: "
        + (
            ", ".join(f"{n}={count}" for n, count in sorted(distribution.items()))
            or "(none)"
        )
    )
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
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        print("DEEPSEEK_API_KEY not set")
        sys.exit(1)
    if not _TRAFFIC_PATH.exists():
        print(f"llm_traffic.jsonl not found at {_TRAFFIC_PATH}")
        sys.exit(1)

    entries = load_traffic_entries(_TRAFFIC_PATH)
    if not entries:
        print(
            f"no {_MODEL} entries with '{_TWO_FIELDS_PHRASE}' found in llm_traffic.jsonl"
        )
        sys.exit(1)

    ensure_csv_header()
    records: list[DecisionRecord] = []
    total = len(entries)
    for index, entry in enumerate(entries, start=1):
        record = run_one(entry, api_key)
        records.append(record)
        append_jsonl_record(record)
        append_csv_record(record)
        amount = record.chosen_number if record.chosen_number is not None else "FAILED"
        print(
            f"{record.username} {index}/{total} amount={amount} "
            f"rt={record.reasoning_tokens} {record.elapsed_seconds:.2f}s",
            flush=True,
        )
    print_stats(records)


if __name__ == "__main__":
    main()
