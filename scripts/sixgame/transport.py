"""Network transport for the sixgame experiment.

This file knows how to send one prompt to one model and hand back a
normalized answer, and nothing else:

- ``direct_deepseek`` talks to api.deepseek.com (key from DEEPSEEK_API_KEY).
- ``openrouter_transport`` talks to openrouter.ai (key from
  OPENROUTER_API_KEY).
- ``CloudflareTransport`` is ported from the LLM_Search_Experiment
  harness (``_CloudflareRealTransport``): the model family picks the
  Cloudflare route (anthropic -> ai/v1/messages, openai ->
  ai/v1/responses), anthropic bodies hard-require max_tokens (filled
  with PROVIDER_REQUIRED_MAX_TOKENS = 32768 when the caller sends none),
  and the openai family pins reasoning off via {"effort": "none"}.
- ``call_with_retry`` wraps any of the above: 429 / 5xx / timeouts are
  retried with capped exponential backoff; 4xx failures are recorded,
  never retried.

Keys are read from the environment at call time only, and are never
logged, printed, or put in any record.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable

try:  # works both as a package module and run from the scripts directory
    from sixgame import mesl as _mesl

    MeslUnavailableError = _mesl.MeslUnavailableError  # noqa: F401 (re-export)
    RouteCheck = _mesl.RouteCheck  # noqa: F401 (re-export)
    _opener_for = _mesl._opener_for  # noqa: F401 (re-export)
    check_route = _mesl.check_route  # noqa: F401 (re-export)
    ensure_route_for_route = _mesl.ensure_route_for_route
    proxy_url = _mesl.proxy_url  # noqa: F401 (re-export)
except ImportError:  # pragma: no cover - direct execution layout
    from mesl import (  # type: ignore[no-redef]
        MeslUnavailableError as MeslUnavailableError,
        RouteCheck as RouteCheck,
        _opener_for as _opener_for,
        check_route as check_route,
        ensure_route_for_route as ensure_route_for_route,
        proxy_url as proxy_url,
    )

CLOUDFLARE_API_TOKEN = "CLOUDFLARE_API_TOKEN"
CLOUDFLARE_ACCOUNT_ID = "CLOUDFLARE_ACCOUNT_ID"
CLOUDFLARE_BASE = "https://api.cloudflare.com/client/v4/accounts"
CLOUDFLARE_ROUTES = {
    "anthropic": "ai/v1/messages",
    "openai": "ai/v1/responses",
}

#: The anthropic-style wire requirement (NOT an experiment cap): an
#: anthropic /ai/v1/messages body hard-requires max_tokens, so a no-cap
#: request sends this value for natural completion headroom.
PROVIDER_REQUIRED_MAX_TOKENS = 32768

#: Retry policy: 429 and 5xx (and timeouts) retried with exponential
#: backoff sleep(min(2**attempt, 30)) for at most 4 total attempts.
_MAX_ATTEMPTS = 4
_BACKOFF_CAP_SECONDS = 30

_TIMEOUT_SECONDS = 300

#: Live-request capture (task 2739): the direct DeepSeek route records
#: each final serialized request body here before sending, so a live run
#: can be verified against the exact bytes that went over the wire.
#: Flushed by the runner to captured_requests.jsonl; never contains keys.
LIVE_CAPTURED: list[dict] = []


class TransportError(Exception):
    """A request failed at the HTTP level (status carried when known)."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class TransportTimeout(TransportError):
    """The request timed out."""


def is_retryable(exc: BaseException) -> bool:
    """True for 429, any 5xx, and timeouts — the retryable classes."""
    if isinstance(exc, TransportTimeout):
        return True
    if isinstance(exc, TransportError):
        code = exc.status_code
        return code == 429 or (code is not None and code >= 500)
    return False


@dataclass
class RawResponse:
    """One finished HTTP exchange, already parsed where possible."""

    status_code: int
    body: dict


def _post_json(
    url: str, payload: dict, headers: dict[str, str], timeout: int
) -> RawResponse:
    """POST one JSON payload; raise TransportError/TransportTimeout on failure."""
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    host = urllib.parse.urlsplit(url).hostname or ""
    opener = _opener_for(host)
    try:
        open_fn = opener.open if opener is not None else urllib.request.urlopen
        with open_fn(request, timeout=timeout) as response:
            return RawResponse(response.status, json.loads(response.read()))
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read())
        except Exception:
            body = {}
        raise TransportError(
            f"HTTP {exc.code} from {url}: {json.dumps(body)[:300]}", exc.code
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise TransportTimeout(f"request to {url} failed: {exc}") from exc


def direct_deepseek(payload: dict) -> RawResponse:
    """Send one chat-completions payload to DeepSeek's direct API.

    Temperature is honoured; no token cap is sent unless the payload
    carries one.
    """
    key = _require_env("DEEPSEEK_API_KEY")
    body = {
        "model": payload["model"],
        "messages": payload["messages"],
        "temperature": payload.get("temperature", 1.0),
    }
    if "max_tokens" in payload:
        body["max_tokens"] = payload["max_tokens"]
    LIVE_CAPTURED.append(body)
    return _post_json(
        "https://api.deepseek.com/chat/completions",
        body,
        {"Authorization": f"Bearer {key}"},
        _TIMEOUT_SECONDS,
    )


def openrouter_transport(payload: dict) -> RawResponse:
    """Send one chat-completions payload to OpenRouter.

    Temperature is honoured; no token cap is sent unless the payload
    carries one.
    """
    key = _require_env("OPENROUTER_API_KEY")
    body = {
        "model": payload["model"],
        "messages": payload["messages"],
        "temperature": payload.get("temperature", 1.0),
    }
    if "max_tokens" in payload:
        body["max_tokens"] = payload["max_tokens"]
    return _post_json(
        "https://openrouter.ai/api/v1/chat/completions",
        body,
        {"Authorization": f"Bearer {key}"},
        _TIMEOUT_SECONDS,
    )


def _require_env(name: str) -> str:
    """Read one credential from the environment; refuse to run without it."""
    import os

    value = os.environ.get(name, "")
    if not value:
        raise TransportError(f"{name} is not set — refusing to run a model call")
    return value


class CloudflareTransport:
    """Ported Cloudflare Workers-AI transport (see module docstring).

    ``session_post`` is the injectable network seam (tests pass a fake;
    production uses a requests.Session).  It must behave like
    ``session.post(url, headers=..., json=...)`` and return an object
    with ``status_code`` and a ``json()`` method.
    """

    _STOP_MAPS = {
        "anthropic": {
            "end_turn": "stop",
            "stop_sequence": "stop",
            "max_tokens": "length",
        },
        "openai": {"completed": "stop", "incomplete": "length"},
    }

    def __init__(
        self,
        model_id: str,
        session_post: Callable[..., object] | None = None,
    ) -> None:
        self.model_id = model_id
        family = model_id.split("/", 1)[0]
        if family not in CLOUDFLARE_ROUTES:
            raise TransportError(
                f"no Cloudflare route for model {model_id!r} — family must "
                f"be one of {sorted(CLOUDFLARE_ROUTES)}"
            )
        self.family = family
        self._session_post = session_post

    # ---------------- wire-body builders (pure) ---------------- #
    def build_body(self, payload: dict) -> dict:
        """Derive the family-specific Cloudflare wire body from a payload."""
        if self.family == "anthropic":
            return self._body_anthropic(payload)
        return self._body_openai(payload)

    def _body_anthropic(self, payload: dict) -> dict:
        messages = payload["messages"]
        system_parts = [
            m.get("content", "") for m in messages if m.get("role") == "system"
        ]
        body = {
            "model": self.model_id,
            # temperature/seed hard-400 on this route: omitted, never null.
            "max_tokens": payload.get("max_tokens", PROVIDER_REQUIRED_MAX_TOKENS),
            "messages": [dict(m) for m in messages if m.get("role") != "system"],
        }
        if system_parts:
            body["system"] = "\n\n".join(system_parts)
        return body

    def _body_openai(self, payload: dict) -> dict:
        body = {
            "model": self.model_id,
            "input": [
                {"role": m.get("role"), "content": m.get("content")}
                for m in payload["messages"]
            ],
            **(
                {"max_output_tokens": payload["max_tokens"]}
                if "max_tokens" in payload
                else {}
            ),
            # The only reasoning-off encoding this gateway accepts.
            "reasoning": {"effort": "none"},
        }
        return body

    # ---------------- response normalizer ---------------- #
    def normalize(self, body: dict) -> dict:
        """Normalize the family response into chat-completions shape."""
        if self.family == "anthropic":
            return self._normalize_anthropic(body)
        return self._normalize_openai(body)

    def _normalize_anthropic(self, body: dict) -> dict:
        blocks = body.get("content") or []
        text = "".join(
            b.get("text", "")
            for b in blocks
            if isinstance(b, dict) and b.get("type") == "text"
        )
        stop = body.get("stop_reason")
        finish = self._STOP_MAPS["anthropic"].get(stop, stop or "")
        return self._choice_envelope(body, text, finish)

    def _normalize_openai(self, body: dict) -> dict:
        texts = []
        for item in body.get("output") or []:
            if not isinstance(item, dict):
                continue
            for piece in item.get("content") or []:
                if isinstance(piece, dict) and isinstance(piece.get("text"), str):
                    texts.append(piece["text"])
        status = body.get("status")
        finish = self._STOP_MAPS["openai"].get(status, status or "")
        return self._choice_envelope(body, "".join(texts), finish)

    def _choice_envelope(self, body: dict, text: str, finish: str) -> dict:
        usage = body.get("usage") or {}
        usage_map = {}
        for key, value in (
            ("input_tokens", "prompt_tokens"),
            ("output_tokens", "completion_tokens"),
        ):
            if key in usage:
                usage_map[value] = usage[key]
        return {
            "model": body.get("model", self.model_id),
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": finish,
                }
            ],
            "usage": usage_map,
        }

    # ---------------- one round trip ---------------- #
    def __call__(self, payload: dict) -> RawResponse:
        token = _require_env(CLOUDFLARE_API_TOKEN)
        account = _require_env(CLOUDFLARE_ACCOUNT_ID)
        url = f"{CLOUDFLARE_BASE}/{account}/{CLOUDFLARE_ROUTES[self.family]}"
        headers = {"Authorization": f"Bearer {token}"}
        body = self.build_body(payload)
        try:
            if self._session_post is not None:
                raw = self._session_post(url, headers=headers, json=body)
                status = raw.status_code
                parsed = raw.json()
            else:
                import requests

                resp = requests.post(url, headers=headers, json=body, timeout=120)
                status = resp.status_code
                parsed = resp.json() if status < 300 or resp.text else {}
        except (TimeoutError, OSError) as exc:
            raise TransportTimeout(f"cloudflare request failed: {exc}") from exc
        if 200 <= status < 300:
            return RawResponse(status, self.normalize(parsed))
        raise TransportError(
            f"HTTP {status} from Cloudflare: {json.dumps(parsed)[:300]}",
            status,
        )


#: model name -> route name (the per-model route map; SCIENTIFIC_DESIGN
#: section 2 — routes must honour temperature 1.0).
DEFAULT_ROUTE_MAP: dict[str, str] = {
    "deepseek-v4-flash": "direct",
    "anthropic/claude-sonnet-5": "openrouter",
    "openai/gpt-5.6-luna": "openrouter",
}

#: Requests captured by the dry transport (module-level so the runner can
#: flush them to captured_requests.jsonl after a dry run). No network.
DRY_CAPTURED: list[dict] = []


def _dry_content_for(payload: dict) -> str:
    """A canned answer valid for the request's game: the amount is picked
    inside the range the prompt itself states (11-20, 31-40, ...)."""
    import re

    prompt = payload["messages"][0]["content"]
    match = re.search(r"Choose a value from (\d+) to (\d+)\.", prompt)
    amount = int(match.group(1)) if match else 15
    return json.dumps(
        {
            "reason": "dry-run canned answer",
            "amount": amount,
            "report": 4,
            "action": "A1",
            "recognised": True,
            "answer": "I recognise the 11-20 game; people typically request 15.",
        }
    )


def dry_transport(payload: dict) -> RawResponse:
    """An offline stand-in for a real transport: captures the exact
    serialized payload and returns a canned 200 chat-completions body.
    Never touches the network and needs no credentials."""
    DRY_CAPTURED.append(json.loads(json.dumps(payload)))
    content = _dry_content_for(payload)
    body = {
        "model": payload["model"],
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": len(payload["messages"][0]["content"]) // 4,
            "completion_tokens": 40,
        },
    }
    return RawResponse(200, body)


def route_for(model: str, route_map: dict[str, str] | None = None) -> str:
    """The route name for one model (defaults to DEFAULT_ROUTE_MAP)."""
    return (route_map or DEFAULT_ROUTE_MAP).get(
        model, DEFAULT_ROUTE_MAP.get(model, "openrouter")
    )


def call_with_retry(
    payload: dict,
    model: str,
    route: str,
    sleep: Callable[[float], None] = time.sleep,
) -> RawResponse:
    """Send one request, retrying 429/5xx/timeouts with capped backoff.

    4xx failures raise immediately (recorded by the caller, never
    retried).  After the final attempt the last error propagates.
    """
    # Fail-closed gate (task 2767): Claude/GPT routes must go through a
    # verified MESL proxy before the first byte is sent. DeepSeek and
    # dry routes pass through unchanged. The gate raises (never falls
    # back to a direct connection) and is retried no further.
    ensure_route_for_route(route)
    last_error: BaseException | None = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            if route == "cloudflare":
                return CloudflareTransport(model)(payload)
            transport = _ROUTES[route]
            if transport is None:
                raise TransportError(f"route {route!r} not usable")
            return transport(payload)
        except BaseException as exc:  # noqa: BLE001 - re-raised below
            if not isinstance(exc, (TransportError, TransportTimeout)):
                raise
            last_error = exc
            if not is_retryable(exc) or attempt == _MAX_ATTEMPTS - 1:
                raise
            sleep(min(2.0**attempt, _BACKOFF_CAP_SECONDS))
    raise last_error  # pragma: no cover - loop always returns or raises


#: Final route table. Defined after dry_transport so the offline mock can
#: be referenced by name (the dry route never touches the network).
_ROUTES = {
    "direct": direct_deepseek,
    "openrouter": openrouter_transport,
    "cloudflare": None,  # built per model id in call_with_retry
    "dry": dry_transport,  # offline mock: captures payloads, canned 200
}
