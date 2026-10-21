"""Offline tests for the Cloudflare auth verdict in route_check.py.

What this file does: proves, without any network access, that the auth
verdict trusts the account-scoped token verify (and never fails just
because the user-scope verify returns 401), that a non-active
account-scope verify fails the verdict, and that a unified-billing 503
still fails even when the token is active.
"""

from __future__ import annotations

from typing import Any

import pytest

from sixgame import route_check


def _mock_cf_get(
    responses: dict[str, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Replace _cf_get so each path prefix returns a canned response."""

    def fake(path: str, timeout: float) -> dict[str, Any]:
        for suffix, response in responses.items():
            if path.endswith(suffix):
                return response
        raise AssertionError(f"unexpected path probed: {path}")

    monkeypatch.setattr(route_check, "_cf_get", fake)


def test_account_scoped_token_with_user_scope_401_is_not_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A valid account-scoped token must pass even though the user-scope
    verify endpoint returns 401 for it."""
    _mock_cf_get(
        {
            "/user/tokens/verify": {
                "status": 401,
                "body": {"success": False, "code": 1000},
            },
            "/ai-gateways": {"status": 404, "body": {}},
            "/tokens/verify": {
                "status": 200,
                "body": {"success": True, "result": {"status": "active"}},
            },
            "/ai/models/search": {
                "status": 200,
                "body": {"success": True, "result": []},
            },
            "/ai-gateway/run": {"status": 404, "body": {}},
        },
        monkeypatch,
    )
    verdict = route_check.check_cloudflare_auth()
    assert verdict["auth_ok"] is True
    assert verdict["account_verify_active"] is True
    assert verdict["account_scoped_verify_status"] == 200
    assert verdict["user_scoped_verify_status"] == 401
    assert verdict["workers_ai_read_status"] == 200


def test_account_scope_verify_non_active_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the account-scope verify says the token is not active, auth must fail."""
    _mock_cf_get(
        {
            "/ai-gateways": {"status": 404, "body": {}},
            "/ai/models/search": {
                "status": 200,
                "body": {"success": True, "result": []},
            },
            "/tokens/verify": {"status": 401, "body": {"success": False}},
            "/ai-gateway/run": {"status": 404, "body": {}},
        },
        monkeypatch,
    )
    verdict = route_check.check_cloudflare_auth()
    assert verdict["auth_ok"] is False
    assert verdict["account_verify_active"] is False


def test_unified_503_still_fails_when_token_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An active token does not rescue a Cloudflare-side 503 on the
    unified-billing endpoint."""
    _mock_cf_get(
        {
            "/ai-gateways": {"status": 404, "body": {}},
            "/ai/models/search": {
                "status": 200,
                "body": {"success": True, "result": []},
            },
            "/tokens/verify": {
                "status": 200,
                "body": {"success": True, "result": {"status": "active"}},
            },
            "/ai-gateway/run": {"status": 503, "body": {}},
        },
        monkeypatch,
    )
    verdict = route_check.check_cloudflare_auth()
    assert verdict["auth_ok"] is False
    assert verdict["unified_billing_503"] is True
    assert "503" in verdict["reason"]
