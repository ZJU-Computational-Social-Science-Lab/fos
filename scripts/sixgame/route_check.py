"""Route and authentication checks that never cost money.

What this file does, in plain language:

- ``check_all_routes`` checks, for each host a Claude/GPT call might
  use, that the MESL proxy is set, answers, and can reach the host
  over HTTPS.  It records the raw socket address of the proxy as
  evidence.  It never calls a model.
- ``check_cloudflare_auth`` asks Cloudflare (through the proxy) whether
  the API token is valid and whether the unified-billing endpoint
  answers.  This is about *model authentication*, which is a separate
  question from whether the network route works — the two are never
  merged into one verdict.
- ``write_route_report`` saves both results as JSON under the data
  root so a batch run can be preceded by a re-runnable evidence file.

No billable API call happens in this file.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:  # works both as a package module and run from the scripts directory
    from sixgame import mesl as transport
except ImportError:  # pragma: no cover - direct execution layout
    from . import mesl as transport  # type: ignore[no-redef]

#: The hosts a Claude/GPT call may legally use; all three are checked.
_CHECK_HOSTS = (
    "api.cloudflare.com",
    "gateway.ai.cloudflare.com",
    "openrouter.ai",
)


def check_all_routes(timeout: float = 10.0) -> list[transport.RouteCheck]:
    """Check the MESL route for every Claude/GPT host (non-billable)."""
    return [transport.check_route(host, timeout) for host in _CHECK_HOSTS]


def _cf_get(path: str, timeout: float) -> dict[str, Any]:
    """One authenticated GET to the Cloudflare API through the proxy.

    Returns a small dict with the status and parsed body.  The token is
    read from the environment at call time and never appears in the
    result.
    """
    import os
    import urllib.error
    import urllib.request

    token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    url = f"https://api.cloudflare.com/client/v4{path.format(account=account)}"
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    opener = transport._opener_for("api.cloudflare.com")
    open_fn = opener.open if opener is not None else urllib.request.urlopen
    try:
        with open_fn(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", "replace")
            return {"status": response.status, "body": _safe_json(body)}
    except urllib.error.HTTPError as exc:
        return {
            "status": exc.code,
            "body": _safe_json(exc.read().decode("utf-8", "replace")),
        }


def _safe_json(text: str) -> Any:
    """Parse JSON text, or return the raw text if it is not JSON."""
    try:
        return json.loads(text)
    except ValueError:
        return text[:300]


def check_cloudflare_auth(timeout: float = 15.0) -> dict[str, Any]:
    """Two non-billable Cloudflare auth checks, kept separate from the
    MESL route verdict:

    - gateway list (``/accounts/{id}/ai-gateway/ai-gateways``): proves
      the token is valid at all.
    - bare unified endpoint GET: proves whether the unified-billing
      route answers (a 503 here is a Cloudflare-side blocker, not a
      network problem).

    BYOK key configuration may be unverifiable via this API; that is
    stated in the verdict rather than guessed.
    """
    gateways = _cf_get("/accounts/{account}/ai-gateway/ai-gateways", timeout)
    unified = _cf_get("/accounts/{account}/ai-gateway/run", timeout)
    # Authoritative probe: account-scoped verify. An account-scoped
    # (``cfat_``) token is active even though the user-scope endpoint
    # rejects it, so only THIS probe decides the verdict.
    account_verify = _cf_get("/accounts/{account}/tokens/verify", timeout)
    account_body = account_verify.get("body")
    account_verify_active = (
        account_verify.get("status") == 200
        and isinstance(account_body, dict)
        and account_body.get("success") is True
        and isinstance(account_body.get("result"), dict)
        and account_body["result"].get("status") == "active"
    )
    # Informational only: user-scope verify (401 is expected for
    # account-scoped tokens and never fails the verdict).
    user_verify = _cf_get("/user/tokens/verify", timeout)
    # Non-billable read probe: proves the token can read Workers AI.
    workers_ai_read = _cf_get("/accounts/{account}/ai/models/search", timeout)
    unified_status = unified["status"]
    byok = (
        "not verifiable via this API endpoint — BYOK configuration "
        "cannot be confirmed or denied here"
    )
    verdict = {
        "account_scoped_verify_status": account_verify.get("status"),
        "account_verify_active": account_verify_active,
        "user_scoped_verify_status": user_verify.get("status"),
        "workers_ai_read_status": workers_ai_read.get("status"),
        "gateway_list_status": gateways["status"],
        "unified_billing_status": unified_status,
        "unified_billing_503": unified_status == 503,
        "byok": byok,
        "auth_ok": account_verify_active and unified_status != 503,
        "note": (
            "MESL connectivity and model authentication are separate "
            "verdicts; this verdict covers auth only. The user-scope "
            "verify is informational: a 401 there is expected for "
            "account-scoped tokens."
        ),
    }
    if not account_verify_active:
        verdict["reason"] = (
            f"account-scope token verify returned "
            f"{account_verify.get('status')} — token not active at "
            "account scope (gateway list status "
            f"{gateways['status']} may also reflect the bad token or an "
            "endpoint-path mismatch)"
        )
    elif unified_status == 503:
        verdict["reason"] = (
            "unified billing endpoint returns 503 — Cloudflare route "
            "blocked for model calls; OpenRouter is the alternative "
            "requiring the user's explicit route approval"
        )
    else:
        verdict["reason"] = "token valid and unified endpoint answered"
    return verdict


def write_route_report(
    data_root: Path,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """Run both checks and save one JSON evidence file under the data
    root.  Returns the same report it saved."""
    routes = check_all_routes(timeout)
    report: dict[str, Any] = {
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "routes": [vars(check) for check in routes],
        "mesl_ok": all(check.ok for check in routes),
        "cloudflare_auth": check_cloudflare_auth(timeout),
    }
    out_dir = data_root / "route_checks"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "route_check.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["saved_to"] = str(out_path)
    return report
