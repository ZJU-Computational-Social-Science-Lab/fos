"""The MESL proxy scope and the fail-closed Claude/GPT route gate.

What this file does, in plain language:

- ``proxy_url`` reads the proxy address from the environment (either
  SIXGAME_CF_PROXY or its alias SIXGAME_MESL_PROXY).
- ``_opener_for`` decides, per host, whether a request goes through
  the proxy: only the three exact hosts in _PROXIED_HOSTS may ever be
  proxied; DeepSeek and everything else always go direct.
- ``check_route`` proves (without any billable call) that the proxy is
  set, answers TCP (raw socket evidence recorded), and can complete an
  HTTPS request to the target host; it also records which country the
  proxy exit is in (informational only).
- ``ensure_route_for_route`` is the pre-send gate: Cloudflare (family
  or unified chat), and OpenRouter model calls are REFUSED unless the
  route is proven — there is never a direct fallback.
"""

from __future__ import annotations

import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

#: Optional local MESL proxy (e.g. "http://127.0.0.1:7688") used ONLY
#: for the hosts in _PROXIED_HOSTS when the proxy variable is set;
#: every other host keeps the default direct path.  SIXGAME_CF_PROXY is
#: the original name and SIXGAME_MESL_PROXY is an accepted alias —
#: either one works, SIXGAME_CF_PROXY wins if both are set.
_CF_PROXY_ENV = "SIXGAME_CF_PROXY"
_CF_PROXY_ENV_ALIAS = "SIXGAME_MESL_PROXY"

#: The exact (case-insensitive) host set that may ever be proxied:
#: the Cloudflare API, the Cloudflare AI gateway, and OpenRouter.
#: Subdomain spoofs like "api.cloudflare.com.evil.com" never match.
_PROXIED_HOSTS = {
    "api.cloudflare.com",
    "gateway.ai.cloudflare.com",
    "openrouter.ai",
}

_CLOUDFLARE_HOST = "api.cloudflare.com"


def proxy_url() -> str:
    """The configured MESL proxy address, or "" if none is set."""
    import os

    return os.environ.get(_CF_PROXY_ENV) or os.environ.get(_CF_PROXY_ENV_ALIAS, "")


def _is_proxied_host(host: str) -> bool:
    """True only for an exact (case-insensitive) proxied-host match."""
    return host.lower() in _PROXIED_HOSTS


def _opener_for(host: str) -> urllib.request.OpenerDirector | None:
    """The opener to use for one host, or None for the default path.

    When the MESL proxy variable is set and the host is exactly one of
    the proxied hosts, return a dedicated opener that sends the request
    through that proxy.  Normal TLS verification is untouched.  Nothing
    is installed globally and no environment proxy variables are used.
    DeepSeek and every other host always take the direct path.
    """
    proxy = proxy_url()
    if not proxy or not _is_proxied_host(host):
        return None
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({"https": proxy, "http": proxy})
    )


@dataclass
class RouteCheck:
    """The result of one MESL route check for one target host.

    ``tcp_ok`` means a raw socket connection to the proxy itself
    succeeded (sock-level evidence: peer address recorded).  ``https_ok``
    means a non-billable HTTPS request reached the target host through
    the proxy.  ``egress_country`` is what cloudflare's trace endpoint
    reported for the proxy exit (informational only — recorded, never
    used to block).  ``ok`` is the fail-closed verdict.
    """

    host: str
    proxy_configured: bool
    tcp_ok: bool
    tcp_peer: str
    https_ok: bool
    https_status: int | None
    egress_country: str
    ok: bool
    reason: str


def _tcp_connect_to_proxy(timeout: float) -> tuple[bool, str]:
    """Try one raw TCP connection to the proxy; return (ok, peer)."""
    from urllib.parse import urlsplit

    parts = urlsplit(proxy_url())
    host = parts.hostname or ""
    port = parts.port or (443 if parts.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            return True, f"{sock.getpeername()[0]}:{sock.getpeername()[1]}"
    except OSError as exc:
        return False, f"unreachable ({exc})"


def _egress_country_via_proxy(timeout: float) -> str:
    """Ask cloudflare's trace endpoint (through the proxy) which country
    the exit is in.  Purely informational; "" if it cannot be read."""
    try:
        proxy = proxy_url()
        request = urllib.request.Request("https://www.cloudflare.com/cdn-cgi/trace")
        # The trace host is not itself a proxied API host, so build the
        # proxy opener explicitly — this MUST go through the proxy.
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"https": proxy, "http": proxy})
        )
        with opener.open(request, timeout=timeout) as response:
            text = response.read().decode("utf-8", "replace")
        for line in text.splitlines():
            if line.startswith("loc="):
                return line[4:].strip()
    except Exception:  # noqa: BLE001 - informational only, never fatal
        return ""
    return ""


class MeslUnavailableError(Exception):
    """The fail-closed gate refused a Claude/GPT call: the MESL proxy
    is not configured or not usable.  These calls are never retried
    over a direct connection."""


def check_route(host: str, timeout: float = 10.0) -> RouteCheck:
    """One non-billable MESL route check for one target host.

    Fails closed: ``ok`` is True only when the proxy variable is set,
    the proxy answers TCP, and a non-billable HTTPS request reaches the
    target host through it.  No model call is made or needed.
    """
    proxy = proxy_url()
    if not proxy:
        return RouteCheck(
            host, False, False, "", False, None, "", False, "proxy env not set"
        )
    if not _is_proxied_host(host):
        return RouteCheck(
            host,
            True,
            False,
            "",
            False,
            None,
            "",
            False,
            f"host {host!r} is never proxied",
        )
    tcp_ok, peer = _tcp_connect_to_proxy(timeout)
    if not tcp_ok:
        return RouteCheck(
            host, True, False, peer, False, None, "", False, "proxy TCP connect failed"
        )
    https_status: int | None = None
    try:
        request = urllib.request.Request(f"https://{host}/")
        opener = _opener_for(host)
        with opener.open(request, timeout=timeout) as response:
            https_status = response.status
    except urllib.error.HTTPError as exc:
        https_status = exc.code  # any HTTP answer proves the route works
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return RouteCheck(
            host,
            True,
            True,
            peer,
            False,
            None,
            _egress_country_via_proxy(timeout),
            False,
            f"HTTPS through proxy failed: {exc}",
        )
    return RouteCheck(
        host,
        True,
        True,
        peer,
        True,
        https_status,
        _egress_country_via_proxy(timeout),
        True,
        "proxy reachable, HTTPS answered",
    )


#: Per-host route-check cache: one process checks each host once; a run
#: re-checks only via --check-route or a fresh process.
_ROUTE_VERDICTS: dict[str, RouteCheck] = {}


def ensure_route_for_route(route: str) -> RouteCheck:
    """The fail-closed pre-send gate for Claude/GPT traffic.

    Cloudflare and OpenRouter routes may only be used through the MESL
    proxy.  If the proxy is not configured and verified usable, raise
    MeslUnavailableError — never fall back to a direct connection.
    DeepSeek ("direct") and the offline "dry" route pass through.
    """
    if route not in ("cloudflare", "cloudflare_chat", "openrouter"):
        return RouteCheck(
            "",
            True,
            True,
            "",
            True,
            None,
            "",
            True,
            "route bypasses the gate (deepseek/dry)",
        )
    host = "openrouter.ai" if route == "openrouter" else "api.cloudflare.com"
    verdict = _ROUTE_VERDICTS.get(host)
    if verdict is None:
        verdict = check_route(host)
        _ROUTE_VERDICTS[host] = verdict
    if not verdict.ok:
        raise MeslUnavailableError(
            f"refusing {route} call to {host}: MESL proxy unusable "
            f"({verdict.reason}) — no direct fallback is permitted"
        )
    return verdict
