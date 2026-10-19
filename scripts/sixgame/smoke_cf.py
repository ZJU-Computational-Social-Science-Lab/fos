"""Cloudflare compatibility smoke test (task 2705).

This script runs exactly six pre-approved test calls against the
Cloudflare AI gateway and saves what happened for each one. It answers
one question: which Cloudflare route (endpoint) accepts our settings —
especially "temperature 1.0" — for each model family?

What each function does:
- ``build_calls``: describes the six calls (route, model, settings).
- ``send_one``: sends one call and records the status, the exact error
  text if it failed, token counts, and the stop reason.
- ``summarize``: prints a small human-readable table of the results.
- ``main``: runs all six calls, writes results/cf_smoke/
  cf_smoke_results.json, and prints the table.

Credentials come from the environment only and are never printed.
No retries beyond the transport's backoff policy; 4xx never retried.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from sixgame.transport import (
    CLOUDFLARE_BASE,
    PROVIDER_REQUIRED_MAX_TOKENS,
    TransportTimeout,
    _require_env,
)

RESULTS_PATH = Path("results/cf_smoke/cf_smoke_results.json")

#: A short neutral prompt; large enough that answers are not truncated.
PROMPT = (
    "Pick an integer from 11 to 20 and reply with exactly one JSON "
    'object: {"choice": <your integer>}.'
)

_TIMEOUT_SECONDS = 300


def _headers() -> dict[str, str]:
    """Authorization headers built from environment credentials."""
    return {
        "Authorization": f"Bearer {_require_env('CLOUDFLARE_API_TOKEN')}",
        "Content-Type": "application/json",
    }


def _url(account: str, route: str) -> str:
    """The full endpoint for one Cloudflare AI route."""
    return f"{CLOUDFLARE_BASE}/{account}/{route}"


def _post_json(url: str, payload: dict) -> tuple[int, dict, dict[str, str]]:
    """POST one JSON body; return (status, parsed body, response headers).

    Raises TransportTimeout on network failure. HTTP errors are returned
    to the caller (the error body is part of the record we must keep).
    """
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=_headers(),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8")
            return response.status, _parse(body), dict(response.headers.items())
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return exc.code, _parse(raw), dict(exc.headers.items())
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise TransportTimeout(f"request to {url} failed: {exc}") from exc


def _parse(raw: str) -> dict:
    """Parse a response body, returning {} when it is not valid JSON."""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"_raw": raw}
    return parsed if isinstance(parsed, dict) else {"_raw": raw}


def build_calls() -> list[dict[str, Any]]:
    """The six approved calls, in order, with their exact wire bodies."""
    openai_input = [{"role": "user", "content": PROMPT}]
    chat_messages = [{"role": "user", "content": PROMPT}]
    gpt = "openai/gpt-5.6-luna"
    claude = "anthropic/claude-sonnet-5"
    responses_route = "ai/v1/responses"
    chat_route = "ai/v1/chat/completions"
    messages_route = "ai/v1/messages"
    return [
        {
            "id": "S1",
            "route": responses_route,
            "model": gpt,
            "settings": {"temperature": 1.0, "reasoning": {"enabled": False}},
            "body": {
                "model": gpt,
                "input": openai_input,
                "temperature": 1.0,
                "reasoning": {"enabled": False},
                "max_output_tokens": PROVIDER_REQUIRED_MAX_TOKENS,
            },
        },
        {
            "id": "S2",
            "route": responses_route,
            "model": gpt,
            "settings": {"temperature": 1.0},
            "body": {
                "model": gpt,
                "input": openai_input,
                "temperature": 1.0,
                "max_output_tokens": PROVIDER_REQUIRED_MAX_TOKENS,
            },
            "expect": "400 (negative control)",
        },
        {
            "id": "S3",
            "route": chat_route,
            "model": gpt,
            "settings": {"temperature": 1.0},
            "body": {
                "model": gpt,
                "messages": chat_messages,
                "temperature": 1.0,
                "max_tokens": PROVIDER_REQUIRED_MAX_TOKENS,
            },
        },
        {
            "id": "S4",
            "route": chat_route,
            "model": claude,
            "settings": {"temperature": 1.0},
            "body": {
                "model": claude,
                "messages": chat_messages,
                "temperature": 1.0,
                "max_tokens": PROVIDER_REQUIRED_MAX_TOKENS,
            },
        },
        {
            "id": "S5",
            "route": messages_route,
            "model": claude,
            "settings": {"temperature": 1.0},
            "body": {
                "model": claude,
                "messages": chat_messages,
                "temperature": 1.0,
                "max_tokens": PROVIDER_REQUIRED_MAX_TOKENS,
            },
            "expect": "400 (negative control)",
        },
        {
            "id": "S6",
            "route": responses_route,
            "model": gpt,
            "settings": {
                "temperature": 1.0,
                "seed": 42,
                "reasoning": {"enabled": False},
            },
            "body": {
                "model": gpt,
                "input": openai_input,
                "temperature": 1.0,
                "seed": 42,
                "reasoning": {"enabled": False},
                "max_output_tokens": PROVIDER_REQUIRED_MAX_TOKENS,
            },
        },
    ]


def _extract_usage(body: dict) -> dict:
    """Pull token counts out of any of the three response shapes."""
    usage = body.get("usage") or {}
    return {
        key: usage.get(key)
        for key in (
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "input_tokens",
            "output_tokens",
        )
        if usage.get(key) is not None
    }


def _extract_finish(body: dict) -> str | None:
    """Pull the stop reason out of any of the three response shapes."""
    if body.get("choices"):
        return body["choices"][0].get("finish_reason")
    if "stop_reason" in body:
        return body["stop_reason"]
    return body.get("status")


def send_one(call: dict, account: str, sleep=time.sleep) -> dict:
    """Send one call and build its full record (never prints credentials)."""
    record: dict[str, Any] = {
        "id": call["id"],
        "route": call["route"],
        "model": call["model"],
        "sent_settings": call["settings"],
        "expect": call.get("expect"),
    }
    attempt = 0
    while True:
        try:
            status, body, headers = _post_json(
                _url(account, call["route"]), call["body"]
            )
            break
        except TransportTimeout as exc:
            attempt += 1
            if attempt >= 4:
                record["outcome"] = "timeout"
                record["error"] = str(exc)
                return record
            sleep(min(2.0 ** (attempt - 1), 30))
    record["http_status"] = status
    record["cf_aig_cache_status"] = headers.get("cf-aig-cache-status")
    record["response_body"] = body
    record["finish_reason"] = _extract_finish(body)
    record["usage"] = _extract_usage(body)
    if 200 <= status < 300:
        record["outcome"] = "accepted"
    else:
        record["outcome"] = f"rejected_{status}"
        record["error_verbatim"] = json.dumps(body)[:2000]
    return record


def summarize(records: list[dict]) -> str:
    """A small human-readable table of the six outcomes."""
    lines = [
        f"{'id':4} {'route':24} {'model':28} {'status':7} {'outcome':14} finish",
    ]
    for r in records:
        lines.append(
            f"{r['id']:4} {r['route']:24} {r['model']:28} "
            f"{str(r.get('http_status', '-')):7} {r.get('outcome', '-'):14} "
            f"{str(r.get('finish_reason'))}"
        )
    return "\n".join(lines)


def main() -> int:
    """Run the six calls, save the full records, print the summary."""
    account = _require_env("CLOUDFLARE_ACCOUNT_ID")
    records = [send_one(call, account) for call in build_calls()]
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(summarize(records))
    print(f"\nfull records: {RESULTS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
