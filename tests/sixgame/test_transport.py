"""Tests for the ported Cloudflare transport and the retry policy.

All tests are offline: the network seam is a fake, and the retry policy
is exercised by making the fake fail a few times before succeeding.
"""

import pytest

import transport as t


class FakeSessionResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


def test_anthropic_body_omits_temperature_and_fills_max_tokens():
    cf = t.CloudflareTransport("anthropic/claude-sonnet-5")
    body = cf.build_body(
        {
            "model": "anthropic/claude-sonnet-5",
            "messages": [{"role": "user", "content": "hi"}],
            "temperature": 1.0,
        }
    )
    assert "temperature" not in body
    assert body["max_tokens"] == t.PROVIDER_REQUIRED_MAX_TOKENS
    assert body["messages"] == [{"role": "user", "content": "hi"}]


def test_anthropic_body_honours_explicit_max_tokens():
    cf = t.CloudflareTransport("anthropic/claude-sonnet-5")
    body = cf.build_body(
        {
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 40000,
        }
    )
    assert body["max_tokens"] == 40000


def test_openai_body_uses_responses_shape_and_pins_reasoning_off():
    cf = t.CloudflareTransport("openai/gpt-5.6-luna")
    body = cf.build_body(
        {
            "model": "openai/gpt-5.6-luna",
            "messages": [{"role": "user", "content": "hi"}],
            "temperature": 1.0,
        }
    )
    assert body["input"] == [{"role": "user", "content": "hi"}]
    assert body["reasoning"] == {"effort": "none"}
    assert "max_output_tokens" not in body  # no cap unless the caller sends one


def test_normalization_returns_chat_completions_shape():
    cf = t.CloudflareTransport("anthropic/claude-sonnet-5")
    normalized = cf.normalize(
        {
            "content": [{"type": "text", "text": "hello"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 5, "output_tokens": 2},
        }
    )
    assert normalized["choices"][0]["message"]["content"] == "hello"
    assert normalized["choices"][0]["finish_reason"] == "stop"
    assert normalized["usage"] == {"prompt_tokens": 5, "completion_tokens": 2}


def test_openai_status_maps_incomplete_to_length():
    cf = t.CloudflareTransport("openai/gpt-5.6-luna")
    normalized = cf.normalize(
        {
            "output": [{"content": [{"type": "text", "text": "partial"}]}],
            "status": "incomplete",
            "usage": {},
        }
    )
    assert normalized["choices"][0]["finish_reason"] == "length"


def test_unknown_model_family_refused():
    with pytest.raises(t.TransportError):
        t.CloudflareTransport("meta-llama/foo")


def test_missing_credentials_refused_before_network(monkeypatch):
    monkeypatch.delenv(t.CLOUDFLARE_API_TOKEN, raising=False)
    monkeypatch.delenv(t.CLOUDFLARE_ACCOUNT_ID, raising=False)
    cf = t.CloudflareTransport("anthropic/claude-sonnet-5")
    with pytest.raises(t.TransportError) as excinfo:
        cf({})
    assert t.CLOUDFLARE_API_TOKEN in str(excinfo.value)


def test_retry_on_429_then_success(monkeypatch):
    sleeps = []
    attempts = {"n": 0}

    def flaky(payload):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise t.TransportError("HTTP 429", 429)
        return t.RawResponse(200, {"ok": True})

    monkeypatch.setitem(t._ROUTES, "direct", flaky)
    response = t.call_with_retry({}, "m", "direct", sleep=sleeps.append)
    assert attempts["n"] == 3
    assert len(sleeps) == 2  # two backoffs before the third attempt
    assert response.status_code == 200


def test_no_retry_on_4xx(monkeypatch):
    attempts = {"n": 0}

    def bad_request(payload):
        attempts["n"] += 1
        raise t.TransportError("HTTP 400", 400)

    monkeypatch.setitem(t._ROUTES, "direct", bad_request)
    with pytest.raises(t.TransportError):
        t.call_with_retry({}, "m", "direct", sleep=lambda _s: None)
    assert attempts["n"] == 1


def test_backoff_is_capped(monkeypatch):
    sleeps = []

    def always_429(payload):
        raise t.TransportError("HTTP 429", 429)

    monkeypatch.setitem(t._ROUTES, "direct", always_429)
    with pytest.raises(t.TransportError):
        t.call_with_retry({}, "m", "direct", sleep=sleeps.append)
    assert max(sleeps) <= t._BACKOFF_CAP_SECONDS
    assert len(sleeps) == t._MAX_ATTEMPTS - 1


def test_route_map_defaults():
    assert t.route_for("deepseek-v4-flash") == "direct"
    assert t.route_for("anthropic/claude-sonnet-5") == "openrouter"


def test_cost_usd_reported_from_prices():
    prices = {"m": {"prompt_per_mtok": 1.0, "completion_per_mtok": 2.0}}
    cost = t.__name__ and __import__("runner").cost_usd(
        "m", 1_000_000, 1_000_000, prices
    )
    assert cost == 3.0
    assert __import__("runner").cost_usd("m", None, 10, prices) is None
