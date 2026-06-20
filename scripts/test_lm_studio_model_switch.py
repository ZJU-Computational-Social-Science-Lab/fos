#!/usr/bin/env python3
"""Standalone test script that reliably switches between models on LM Studio.

Uses state-polling via /api/v0/models to verify each model is loaded before
sending chat requests. Runs 3 full cycles of switching between two models
(MODEL_A -> MODEL_B -> MODEL_A ...) to prove the pattern works before
integration into the FOS runner.

Functions:
    get_model_state()       — Query LM Studio's /api/v0/models and return a
                              {model_id: state} dict.
    wait_for_model(name)    — Poll get_model_state() until the named model
                              shows state="loaded", with a timeout.
    send_chat_request(...)  — Send an OpenAI-compatible chat completion request
                              and return the assistant's response text.
    warmup_model(name)      — Wait for a model to load, then send a warmup
                              request to ready it for inference.
    main()                  — Orchestrate 3 full switch cycles and report
                              pass/fail counts.

Requirements:
    pip install requests
"""

import json
import logging
import sys
import time

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_URL = "http://127.0.0.1:1234"
MODELS_URL = f"{BASE_URL}/api/v0/models"
CHAT_URL = f"{BASE_URL}/v1/chat/completions"
MODEL_A = "openai/gpt-oss-20b"
MODEL_B = "qwen/qwen3.6-35b-a3b"
MAX_POLL_SECONDS = 120
POLL_INTERVAL = 2.0

# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------


def get_model_state() -> dict[str, str]:
    """Query LM Studio's /api/v0/models endpoint and return a model-to-state dict.

    The expected response shape is::

        {"data": [{"id": "model-name", "state": "loaded"}, ...]}

    Returns:
        A dictionary mapping each model ID to its current state string.
        Returns an empty dict on connection/HTTP errors.
    """
    try:
        resp = requests.get(MODELS_URL, timeout=10)
        resp.raise_for_status()
        payload = resp.json()
        data = payload.get("data", [])
        return {entry["id"]: entry.get("state", "unknown") for entry in data}
    except (requests.ConnectionError, requests.Timeout) as exc:
        logging.warning("Connection error fetching model state: %s", exc)
        return {}
    except requests.HTTPError as exc:
        logging.warning("HTTP error fetching model state: %s", exc)
        return {}
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logging.warning("Unexpected response format from /api/v0/models: %s", exc)
        return {}


def wait_for_model(model_name: str) -> bool:
    """Poll get_model_state() until *model_name* reports state="loaded".

    Logs every poll attempt with the current state of the target model.
    Returns True if the model is loaded within MAX_POLL_SECONDS, False
    otherwise (timeout or unreachable server).
    """
    deadline = time.monotonic() + MAX_POLL_SECONDS
    logging.info("Waiting for model '%s' to load (timeout: %ds)...", model_name, MAX_POLL_SECONDS)

    while True:
        state = get_model_state()
        current = state.get(model_name, "not_found")
        logging.info("Poll — model '%s' state: %s", model_name, current)

        if current == "loaded":
            logging.info("Model '%s' is loaded and ready.", model_name)
            return True

        if time.monotonic() >= deadline:
            logging.error("Timed out waiting for model '%s' to load.", model_name)
            return False

        time.sleep(POLL_INTERVAL)


def send_chat_request(
    model_name: str,
    prompt: str,
    json_mode: bool = True,
) -> str | None:
    """Send an OpenAI-compatible chat completion to LM Studio.

    When *json_mode* is True, the request includes a ``response_format``
    constraint of ``{"type": "json_object"}``.  LM Studio / llama.cpp
    servers reject ``json_object`` and require ``json_schema`` or
    ``text``, so on a 400 with that error we automatically retry once
    without ``response_format`` and prepend a JSON-only instruction.

    Args:
        model_name:  The model ID to use for inference.
        prompt:      The user message content.
        json_mode:   Whether to request a structured JSON response.

    Returns:
        The assistant's message content string, or None on failure.
    """
    messages = [{"role": "user", "content": prompt}]

    body: dict = {
        "model": model_name,
        "messages": messages,
        "max_tokens": 256,
    }

    if json_mode:
        body["response_format"] = {"type": "json_object"}

    try:
        resp = requests.post(CHAT_URL, json=body, timeout=60)
        resp.raise_for_status()
        payload = resp.json()
        content = payload["choices"][0]["message"]["content"]
        if content and content.strip():
            return content
        # Empty response — fall through to fallback if json_mode
        if not json_mode:
            return ""
    except requests.HTTPError as exc:
        err_text = resp.text if 'resp' in dir() else ""
        msg = str(exc)
        # LM Studio / llama.cpp reject "json_object" — retry without it
        if json_mode and ("json_object" in err_text or "json_schema" in err_text or "json_object" in msg or "json_schema" in msg):
            logging.info("json_object rejected by server — retrying without response_format")
        else:
            logging.error("HTTP error during chat request (%s): %s", resp.status_code if 'resp' in dir() else "?", exc)
            return None
    except (requests.ConnectionError, requests.Timeout) as exc:
        logging.error("Connection error during chat request: %s", exc)
        return None
    except (json.JSONDecodeError, KeyError, TypeError, IndexError) as exc:
        logging.error("Unexpected chat response format: %s", exc)
        return None

    # ── Fallback: retry without response_format ──────────────
    if not json_mode:
        return None
    logging.info("Retrying without response_format (json_mode fallback)...")
    body.pop("response_format", None)
    body["messages"][0]["content"] = (
        "IMPORTANT: You MUST respond with ONLY valid JSON, no other text. "
        + prompt
    )
    body["max_tokens"] = max(body.get("max_tokens", 256), 512)
    try:
        resp = requests.post(CHAT_URL, json=body, timeout=60)
        resp.raise_for_status()
        payload = resp.json()
        content = payload["choices"][0]["message"]["content"]
        return content
    except Exception as exc:
        logging.error("Fallback chat request also failed: %s", exc)
        return None


def warmup_model(model_name: str) -> bool:
    """Wait for a model to load, then send warmup requests until one succeeds.

    LM Studio reports ``state="loaded"`` as soon as model weights are in
    memory, but the inference engine may need several requests before it
    produces non-empty output.  We retry up to 5 times with a 3-second
    pause between attempts.

    Returns:
        True if the model loaded and at least one warmup request returned
        a non-empty response.
    """
    if not wait_for_model(model_name):
        return False

    warmup_prompt = 'Say hello in JSON format: {"greeting": "..."}'
    max_warmup_attempts = 5

    for attempt in range(1, max_warmup_attempts + 1):
        logging.info(
            "Sending warmup request with json_mode=True (attempt %d/%d)",
            attempt, max_warmup_attempts,
        )
        response = send_chat_request(model_name, warmup_prompt, json_mode=True)

        if response is not None and response.strip():
            logging.info("Warmup successful — response: %s", response[:200])
            return True

        if attempt < max_warmup_attempts:
            logging.warning(
                "Warmup attempt %d returned empty — retrying in 3s...", attempt
            )
            time.sleep(3.0)
        else:
            logging.warning(
                "All %d warmup attempts returned empty", max_warmup_attempts
            )

    return False


def main() -> None:
    """Run 3 full switch cycles between MODEL_A and MODEL_B.

    Each cycle switches A→B→A. With 3 cycles that is 6 switches total.
    Every switch waits for the target model, sends a warmup request
    (json_mode=True), and then sends a real verification request.

    A summary report is printed at the end.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logging.info(
        "Starting LM Studio model switch test: %d cycle(s) | %s <-> %s",
        3, MODEL_A, MODEL_B,
    )

    models = [MODEL_A, MODEL_B]
    passes = 0
    total = 0

    for cycle in range(1, 4):
        # Each cycle: A→B→A, starting with the *second* model in the pair
        # so the first switch is always between distinct models.
        for i in range(2):
            old = models[i % 2]
            new = models[(i + 1) % 2]
            total += 1

            logging.info("=" * 60)
            logging.info(
                "SWITCHING [cycle %d / switch %d]: %s -> %s",
                cycle, total, old, new,
            )

            if not warmup_model(new):
                logging.error("FAIL — warmup for '%s' failed.", new)
                continue

            # Real verification request
            real_prompt = "Return a JSON object with a single key 'status' set to 'ok'"
            real_response = send_chat_request(new, real_prompt, json_mode=True)

            if real_response is not None and real_response.strip():
                logging.info("PASS — real request response: %s", real_response[:200])
                passes += 1
            else:
                logging.error("FAIL — real request for '%s' returned empty.", new)

    # Summary
    logging.info("=" * 60)
    logging.info(
        "SUMMARY — passes: %d / %d (%.1f%%)",
        passes, total,
        (passes / total * 100) if total > 0 else 0.0,
    )
    print(f"\nSUMMARY: {passes}/{total} passes ({passes / total * 100:.1f}%)")


if __name__ == "__main__":
    main()
