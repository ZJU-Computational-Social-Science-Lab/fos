"""Offline tests for the unified Cloudflare chat-completions route.

What this file does: proves, without any network access, that the
``cloudflare_chat`` route sends temperature 1.0 and the model id in a
standard chat-completions body, passes the raw chat-completions answer
through unchanged, refuses to run without credentials, and is covered
by the MESL fail-closed gate (no proxy = refusal, never a direct send).
"""

from __future__ import annotations

import pytest

import transport as t


def test_cloudflare_chat_body_keeps_temperature_and_model():
    """The unified route honours temperature 1.0 (unlike the family routes)."""
    body = t.build_cloudflare_chat_body(
        {
            "model": "anthropic/claude-sonnet-5",
            "messages": [{"role": "user", "content": "hi"}],
            "temperature": 1.0,
        }
    )
    assert body["temperature"] == 1.0
    assert body["model"] == "anthropic/claude-sonnet-5"
    assert body["messages"] == [{"role": "user", "content": "hi"}]
    assert "max_tokens" not in body  # no cap unless the caller sends one


def test_cloudflare_chat_body_honours_explicit_max_tokens():
    body = t.build_cloudflare_chat_body(
        {
            "model": "openai/gpt-5.6-luna",
            "messages": [{"role": "user", "content": "hi"}],
            "temperature": 1.0,
            "max_tokens": 40000,
        }
    )
    assert body["max_tokens"] == 40000


def test_cloudflare_chat_passes_chat_completions_response_through():
    """The unified route already answers in chat-completions shape."""
    raw = t.normalize_cloudflare_chat(
        {
            "model": "claude-sonnet-5",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "OK"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 16, "completion_tokens": 1},
        }
    )
    assert raw["choices"][0]["message"]["content"] == "OK"
    assert raw["choices"][0]["finish_reason"] == "stop"
    assert raw["usage"] == {"prompt_tokens": 16, "completion_tokens": 1}


def test_cloudflare_chat_refuses_unexpected_response_shape():
    with pytest.raises(t.TransportError):
        t.normalize_cloudflare_chat({"error": {"message": "no choices here"}})


def test_cloudflare_chat_route_in_fail_closed_gate(monkeypatch):
    """The MESL gate must treat cloudflare_chat like cloudflare: the
    verdict comes from the api.cloudflare.com host check, never a bypass."""
    checked = {}

    def fake_check_route(host, timeout=10.0):
        checked["host"] = host
        return t.RouteCheck(
            host, True, True, "127.0.0.1:7688", True, 403, "fake ok", True, "fake ok"
        )

    import sixgame.mesl as mesl

    monkeypatch.setattr(mesl, "check_route", fake_check_route)
    monkeypatch.setattr(mesl, "_ROUTE_VERDICTS", {})
    verdict = mesl.ensure_route_for_route("cloudflare_chat")
    assert verdict.ok is True
    assert checked["host"] == "api.cloudflare.com"


def test_cloudflare_chat_route_refused_without_proxy(monkeypatch):
    import sixgame.mesl as mesl

    def failing_check(host, timeout=10.0):
        return t.RouteCheck(
            host, True, True, "", False, None, "proxy down", False, "proxy down"
        )

    monkeypatch.setattr(mesl, "check_route", failing_check)
    monkeypatch.setattr(mesl, "_ROUTE_VERDICTS", {})
    with pytest.raises(mesl.MeslUnavailableError):
        mesl.ensure_route_for_route("cloudflare_chat")


def test_call_with_retry_uses_cloudflare_chat_transport(monkeypatch):
    """call_with_retry dispatches the cloudflare_chat route through the
    registered transport (gate passes, fake transport returns canned 200)."""
    import transport as t

    monkeypatch.setattr(
        t,
        "ensure_route_for_route",
        lambda route: t.RouteCheck(
            "api.cloudflare.com", True, True, "", True, 200, "ok", True, "ok"
        ),
    )
    sent = {}

    def fake_transport(payload):
        sent.update(payload)
        return t.RawResponse(200, {"choices": []})

    monkeypatch.setitem(t._ROUTES, "cloudflare_chat", fake_transport)
    response = t.call_with_retry(
        {"model": "anthropic/claude-sonnet-5", "messages": [], "temperature": 1.0},
        "anthropic/claude-sonnet-5",
        "cloudflare_chat",
    )
    assert response.status_code == 200
    assert sent["temperature"] == 1.0
