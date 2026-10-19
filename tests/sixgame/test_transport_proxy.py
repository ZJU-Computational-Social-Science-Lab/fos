"""Tests that the optional SIXGAME_CF_PROXY routes only Cloudflare
traffic through a dedicated proxy opener, and everything else directly.

All tests are offline — no network access happens.  Each test checks
which opener (or default urlopen) the transport would use, and what
proxy mapping that opener carries.
"""

from __future__ import annotations

import urllib.request

import pytest

from scripts.sixgame import transport


CF_URL = (
    "https://api.cloudflare.com/client/v4/accounts/acct/ai/v1/messages"
)
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
PROXY = "http://127.0.0.1:7688"


@pytest.fixture(autouse=True)
def _no_real_network(monkeypatch):
    """Fail loudly if any test tries to touch the real network."""
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("default urlopen must not be reached here")
        ),
    )


def _proxy_mapping_of(opener: urllib.request.OpenerDirector) -> dict | None:
    """The proxy mapping carried by the opener's ProxyHandler, if any."""
    for handler in opener.handlers:
        if isinstance(handler, urllib.request.ProxyHandler):
            return handler.proxies
    return None


def test_cloudflare_url_goes_through_proxy_opener_when_env_set(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SIXGAME_CF_PROXY", PROXY)
    opener = transport._opener_for("api.cloudflare.com")
    assert opener is not None
    assert _proxy_mapping_of(opener) == {"https": PROXY, "http": PROXY}


def test_deepseek_and_openrouter_keep_default_path_when_env_set(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SIXGAME_CF_PROXY", PROXY)
    assert transport._opener_for("api.deepseek.com") is None
    assert transport._opener_for("openrouter.ai") is None


def test_env_unset_behaviour_unchanged_for_all_hosts(monkeypatch) -> None:
    monkeypatch.delenv("SIXGAME_CF_PROXY", raising=False)
    monkeypatch.setenv("SIXGAME_CF_PROXY", "")
    for host in ("api.cloudflare.com", "api.deepseek.com", "openrouter.ai"):
        assert transport._opener_for(host) is None


def test_subdomain_trick_is_not_matched(monkeypatch) -> None:
    monkeypatch.setenv("SIXGAME_CF_PROXY", PROXY)
    assert transport._opener_for("api.cloudflare.com.evil.com") is None


def test_hostname_match_is_case_insensitive(monkeypatch) -> None:
    monkeypatch.setenv("SIXGAME_CF_PROXY", PROXY)
    assert transport._opener_for("API.CLOUDFLARE.COM") is not None
    assert _proxy_mapping_of(
        transport._opener_for("API.CLOUDFLARE.COM")
    ) == {"https": PROXY, "http": PROXY}


def test_post_json_uses_proxy_opener_for_cloudflare(monkeypatch) -> None:
    """The real call-site: with env set, a CF POST goes through the
    proxy opener's open(), not the default urlopen."""
    monkeypatch.setenv("SIXGAME_CF_PROXY", PROXY)
    opened_with: list[object] = []

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        status = 200

        def read(self):
            return b"{}"

    def fake_open(self, request, timeout=None):
        opened_with.append(self)
        return _FakeResponse()

    monkeypatch.setattr(
        urllib.request.OpenerDirector, "open", fake_open, raising=True
    )
    response = transport._post_json(
        CF_URL, {}, {"Authorization": "Bearer x"}, 5
    )
    assert response.status_code == 200
    assert len(opened_with) == 1
    assert _proxy_mapping_of(opened_with[0]) == {
        "https": PROXY,
        "http": PROXY,
    }


def test_post_json_uses_default_urlopen_for_deepseek(monkeypatch) -> None:
    """With env set, a DeepSeek POST still uses the default urlopen."""
    monkeypatch.setenv("SIXGAME_CF_PROXY", PROXY)

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        status = 200

        def read(self):
            return b"{}"

    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda request, timeout=None: _FakeResponse(),
    )
    response = transport._post_json(
        DEEPSEEK_URL, {}, {"Authorization": "Bearer x"}, 5
    )
    assert response.status_code == 200


def test_post_json_uses_default_urlopen_when_env_unset(monkeypatch) -> None:
    """Without the env var, a CF POST uses the default urlopen (today's
    behaviour, unchanged)."""
    monkeypatch.delenv("SIXGAME_CF_PROXY", raising=False)

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        status = 200

        def read(self):
            return b"{}"

    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda request, timeout=None: _FakeResponse(),
    )
    response = transport._post_json(
        CF_URL, {}, {"Authorization": "Bearer x"}, 5
    )
    assert response.status_code == 200
