# This file takes the K=20 temperature samples behind every numeric
# answer. One sample is one ordinary chat call: the exact same system and
# user messages the choice path uses, a short generation window, the
# study temperature, and top-logprobs requested so the first generated
# token's candidate list is kept for audit. The raw reply text is what
# gets stored — scoring.py's parse_numeric / parse_multi_numeric do the
# parsing later — so a sample is never silently re-asked or cleaned up.
# Like the proven first-token pipeline, no seed is sent: each sample is a
# fresh server-side draw at temperature 1.0.

import time
from typing import Callable

from logprob_scoring import (
    _loads,
    _post_json,
    _reply_content,
    _server_root,
    _token_positions,
)

from twin2k10 import config


def sample_payload(model_id: str, messages: list[dict]) -> dict:
    """One numeric-sample request body (same call shape as the pipeline).

    temperature is the study's fixed temperature; max_tokens is the
    numeric generation window; logprobs are requested so the first
    generated token's top-k comes back for the record's audit fields.
    """
    return {
        "model": model_id,
        "messages": messages,
        "temperature": config.TEMPERATURE,
        "max_tokens": config.NUMERIC_MAX_TOKENS,
        "logprobs": True,
        "top_logprobs": config.TOP_K,
    }


def extract_sample(data: dict) -> tuple[str, list]:
    """One sample reply's (generated text, first-token top-k candidates).

    The text is what parse_numeric / parse_multi_numeric will read; the
    top-k of the first generated position is the audit trail that proves
    the model actually answered (and what the preflight emptiness check
    inspects). Both come back empty when the reply is unreadable.
    """
    text = _reply_content(data)
    positions = _token_positions(data)
    top_k = positions[0][2] if positions else []
    return text, top_k


def make_numeric_sampler(base_url: str, model_id: str,
                         post: Callable = _post_json,
                         timeout: float = 120.0) -> Callable:
    """Build the K-sample callable for one model: messages -> samples.

    The returned function takes the chat messages and returns ONE dict:
    samples (the K raw reply texts, in draw order), first_top_logprobs
    (the first sample's first-token top-k for audit), calls_failed (how
    many of the K calls errored or came back unreadable) and elapsed
    seconds. A failed call contributes an empty text — which parse_numeric
    will turn into None — instead of killing the leg; nothing is retried
    or re-drawn behind the caller's back.
    """
    root = _server_root(base_url)

    def sampler(messages: list[dict]) -> dict:
        started = time.monotonic()
        samples: list[str] = []
        first_top_logprobs: list = []
        calls_failed = 0
        errors: list[str] = []
        for _sample_number in range(config.NUMERIC_SAMPLES_K):
            payload = sample_payload(model_id, messages)
            try:
                status, body = post(f"{root}/v1/chat/completions", payload,
                                    timeout)
            except OSError as exc:
                calls_failed += 1
                errors.append(f"{type(exc).__name__}: {exc}")
                samples.append("")
                continue
            data = _loads(body) if status == 200 else {}
            if status != 200 or not data:
                calls_failed += 1
                errors.append(f"HTTP {status}" if status != 200
                              else "unreadable reply body")
            text, top_k = extract_sample(data if isinstance(data, dict)
                                         else {})
            samples.append(text)
            if not first_top_logprobs:
                first_top_logprobs = top_k
        return {
            "samples": samples,
            "first_top_logprobs": first_top_logprobs,
            "calls_failed": calls_failed,
            "errors": errors,
            "elapsed_seconds": time.monotonic() - started,
        }

    return sampler


def samples_payload(raw: dict) -> dict:
    """The record-ready fragment one sampler result turns into.

    Numeric (single-answer) and multi-row items share the raw sampling
    result; this keeps their record fields in one place: the raw sample
    texts, the per-call failure count, the first sample's top-logprob
    audit list, and the error strings (empty when every call succeeded).
    """
    return {
        "samples": list(raw["samples"]),
        "first_top_logprobs": raw["first_top_logprobs"],
        "calls_failed": int(raw["calls_failed"]),
        "errors": list(raw["errors"]),
        "elapsed_seconds": float(raw["elapsed_seconds"]),
    }
