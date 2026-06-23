#!/usr/bin/env python3
"""Standalone JSON reliability test for llama.cpp models.

This script tests each of the 5 llama.cpp models with JSON-mode prompts
to measure how reliably they produce valid JSON. It loads each model,
sends 20 prompts requesting a structured JSON response, parses the
output, and reports the failure rate. Any model with >20% parse failures
is flagged.

Functions:
    _http_post(url, body)         — Send an HTTP POST with JSON body and
                                    return the decoded response dict.
    _http_get(url)                — Send an HTTP GET and return the decoded
                                    response dict.
    load_model(name, base_url)    — Load a model via POST /models/load,
                                    polling until status is "loaded".
    unload_model(name, base_url)  — Unload a model via POST /models/unload.
    chat_completion(model, prompt, base_url) — Send a JSON-mode chat
                                    completion request and return the content.
    try_parse_json(content)       — Attempt to parse a string as JSON,
                                    returning the result or None with a
                                    snippet for diagnostics.
    test_model(model_name)        — Run N prompts against one model and
                                    return success/failure counts.
    main()                        — Test all 5 models and print a summary.

Usage:
    python scripts/test_json_reliability.py

Requires:
    Python 3, stdlib only (json, time, urllib.request, socket).
    llama-server must be running at http://localhost:8080 with --models-dir.
"""

from __future__ import annotations

import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# ── Configuration ──────────────────────────────────────────────────────────────

BASE_URL = "http://localhost:8080"
ROUTER_BASE = BASE_URL  # No /v1 suffix — router endpoints are at root
CHAT_URL = f"{BASE_URL}/v1/chat/completions"
MODELS_URL = f"{ROUTER_BASE}/models"
LOAD_URL = f"{ROUTER_BASE}/models/load"
UNLOAD_URL = f"{ROUTER_BASE}/models/unload"

# The 5 GGUF filenames (router names) to test
MODELS = [
    "gpt-oss-20b",
    "gemma-4-26b-a4b",
    "qwen3.6-35b-a3b",
    "gemma4-26b-a4b-uncensored",
    "qwen3.6-35b-a3b-uncensored",
]

N_PROMPTS = 20
TEMPERATURE = 0.7
MAX_TOKENS = 4096
POLL_INTERVAL = 2.0
LOAD_TIMEOUT = 300.0
HTTP_TIMEOUT = 60  # seconds per HTTP request


# ── HTTP helpers ───────────────────────────────────────────────────────────────


def _http_post(url: str, body: dict) -> dict | None:
    """Send an HTTP POST with a JSON body and return the decoded JSON response.

    Args:
        url:    The target URL.
        body:   A dict that will be serialised as JSON.

    Returns:
        The parsed JSON response dict, or None on network/HTTP errors.
    """
    data = json.dumps(body).encode("utf-8")
    req = Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except HTTPError as exc:
        # Return a minimal dict so callers can inspect status + body
        try:
            err_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            err_body = ""
        return {"_error": True, "code": exc.code, "body": err_body}
    except (URLError, TimeoutError, OSError) as exc:
        print(f"      Network error: {exc}")
        return None


def _http_get(url: str) -> dict | None:
    """Send an HTTP GET and return the decoded JSON response.

    Args:
        url: The target URL.

    Returns:
        The parsed JSON response dict, or None on failure.
    """
    req = Request(url, headers={"Accept": "application/json"}, method="GET")
    try:
        with urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        print(f"      GET failed: {exc}")
        return None


# ── Model lifecycle ────────────────────────────────────────────────────────────


def load_model(name: str) -> bool:
    """Load a model into llama.cpp's router and wait until status is 'loaded'.

    Posts to /models/load, then polls GET /models every 2 s until the
    model's status.value is 'loaded'.  Timeouts after LOAD_TIMEOUT seconds.

    Args:
        name: The router model name (GGUF filename without .gguf).

    Returns:
        True if the model loaded successfully, False otherwise.
    """
    print(f"  Loading '{name}' ... ", end="", flush=True)

    # Step 1: POST /models/load
    result = _http_post(LOAD_URL, {"model": name})
    if result is None:
        print("FAIL (network error)")
        return False

    if result.get("_error"):
        code = result.get("code", 0)
        body = result.get("body", "")
        if code == 400 and "already running" in body:
            print("already running ... ", end="", flush=True)
        else:
            print(f"load returned {code}: {body[:100]}")
            return False
    else:
        print("load accepted ... ", end="", flush=True)

    # Step 2: Poll GET /models until loaded
    start = time.monotonic()
    deadline = start + LOAD_TIMEOUT

    while time.monotonic() < deadline:
        resp = _http_get(MODELS_URL)
        if resp is not None:
            models_list = resp.get("data", [])
            for m in models_list:
                if not isinstance(m, dict):
                    continue
                m_id = m.get("id", "")
                if m_id != name:
                    continue
                m_status = m.get("status", {})
                if isinstance(m_status, dict):
                    status_val = m_status.get("value", "") or m_status.get("status", "")
                else:
                    status_val = str(m_status)

                if status_val == "loaded":
                    elapsed = time.monotonic() - start
                    print(f"loaded ({elapsed:.1f}s)")
                    return True
                elif status_val == "error":
                    print("status=error")
                    return False
        time.sleep(POLL_INTERVAL)

    elapsed = time.monotonic() - start
    print(f"timed out after {elapsed:.0f}s")
    return False


def unload_model(name: str) -> None:
    """Unload a model from the router, ignoring any errors.

    Args:
        name: The router model name to unload.
    """
    _http_post(UNLOAD_URL, {"model": name})


# ── Chat completion ────────────────────────────────────────────────────────────


def chat_completion(model: str, prompt: str) -> str:
    """Send a JSON-mode chat completion and return the response content.

    Uses ``response_format: {"type": "json_object"}``.  Returns the
    raw content string, or an empty string on failure.

    Args:
        model:  The router model name.
        prompt: The user message content.

    Returns:
        The assistant's response content, or empty string on failure.
    """
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "response_format": {"type": "json_object"},
    }
    result = _http_post(CHAT_URL, body)
    if result is None:
        return ""
    if result.get("_error"):
        return ""
    try:
        content = result["choices"][0]["message"]["content"]
        return content or ""
    except (KeyError, IndexError, TypeError):
        return ""


# ── JSON parsing ───────────────────────────────────────────────────────────────


def try_parse_json(content: str) -> tuple[dict | None, str]:
    """Try to parse a string as JSON.

    Args:
        content: The raw response content.

    Returns:
        A tuple of (parsed dict or None, snippet for diagnostics).
        The snippet is the first 200 characters of content, or a
        descriptive message if content is empty.
    """
    if not content or not content.strip():
        return None, "(empty response)"
    try:
        parsed = json.loads(content)
        return parsed, ""
    except json.JSONDecodeError as exc:
        snippet = content[:200].replace("\n", " ").strip()
        return None, f"Parse error: {exc.msg} | snippet: {snippet}"


# ── Single-model test ─────────────────────────────────────────────────────────


def test_model(model_name: str) -> tuple[int, int, list[str]]:
    """Run N_PROMPTS JSON-mode prompts against a model.

    Each prompt asks for a structured JSON object describing an agent
    profile.  The response is parsed as JSON.  Parse failures and
    empty responses are counted as failures.

    Args:
        model_name: The router model name to test.

    Returns:
        A tuple of (success_count, failure_count, failure_snippets).
        failure_snippets contains up to 3 truncated failure examples.
    """
    print(f"  Running {N_PROMPTS} JSON prompts ...")
    successes = 0
    failures = 0
    failure_snippets: list[str] = []

    for i in range(1, N_PROMPTS + 1):
        prompt = (
            "Generate a JSON object describing an agent profile. "
            "Include the following fields: name (string), age (integer, 20-80), "
            "occupation (string), and personality_traits (array of 3 strings). "
            "Return ONLY valid JSON, no other text."
        )
        content = chat_completion(model_name, prompt)
        parsed, snippet = try_parse_json(content)

        if parsed is not None:
            successes += 1
            print(f"    [{i:2d}/{N_PROMPTS}] ✓ valid JSON", flush=True)
        else:
            failures += 1
            msg = f"    [{i:2d}/{N_PROMPTS}] ✗ {snippet}"
            print(msg, flush=True)
            if len(failure_snippets) < 3:
                failure_snippets.append(msg)

    return successes, failures, failure_snippets


# ── Main ───────────────────────────────────────────────────────────────────────


def main() -> None:
    """Test all 5 models for JSON reliability and print a summary report.

    For each model:
      1. Load via POST /models/load + poll until loaded.
      2. Send N_PROMPTS JSON-mode chat completions.
      3. Count parse successes and failures.
      4. Unload the model.

    After all models are tested, print a summary with pass/fail per model
    and an overall verdict.
    """
    print("=" * 60)
    print("  JSON Reliability Test — llama.cpp models")
    print(f"  Server: {BASE_URL}")
    print(f"  Models: {', '.join(MODELS)}")
    print(f"  Prompts per model: {N_PROMPTS}")
    print("=" * 60)

    results: dict[str, dict] = {}
    flagged: list[str] = []
    passed: list[str] = []

    for model_name in MODELS:
        print(f"\n── Model: {model_name} ──")

        if not load_model(model_name):
            print(f"  ⚠ Skipping {model_name} — could not load")
            results[model_name] = {
                "successes": 0,
                "failures": N_PROMPTS,
                "failure_rate": 100.0,
                "flagged": True,
                "snippets": ["(model could not be loaded)"],
            }
            flagged.append(model_name)
            continue

        successes, failures, snippets = test_model(model_name)
        unload_model(model_name)

        total = successes + failures
        failure_rate = (failures / total * 100) if total > 0 else 100.0
        is_flagged = failure_rate > 20.0
        flag_label = " ⚠️ FLAGGED" if is_flagged else ""

        if is_flagged:
            flagged.append(model_name)
        else:
            passed.append(model_name)

        results[model_name] = {
            "successes": successes,
            "failures": failures,
            "failure_rate": failure_rate,
            "flagged": is_flagged,
            "snippets": snippets,
        }

        print(
            f"  Result: {successes}/{total} valid JSON"
            f"  ({failure_rate:.1f}% failure){flag_label}"
        )

    # ── Summary report ─────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print("  SUMMARY REPORT")
    print(f"{'=' * 60}")

    for model_name in MODELS:
        r = results[model_name]
        flag = " ⚠️ FLAGGED" if r["flagged"] else ""
        print(f"\n  {model_name}")
        print(f"    Valid JSON:  {r['successes']}/{r['successes'] + r['failures']}")
        print(f"    Failure:     {r['failure_rate']:.1f}%{flag}")
        if r["snippets"]:
            for s in r["snippets"]:
                print(f"    {s}")

    print()
    if passed:
        print(f"  ✅ Passed (<20% failure): {', '.join(passed)}")
    if flagged:
        print(f"  ❌ Flagged (>20% failure): {', '.join(flagged)}")

    print(f"\n  Overall: {'ALL CLEAR' if not flagged else 'ISSUES FOUND'}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
