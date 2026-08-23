"""Shared URL validation for outbound fetches (SSRF hardening).

Used by link_read, content_fetch, and !fetch before any HTTP retrieval.
"""

from __future__ import annotations

import ipaddress
import struct
from urllib.parse import urlparse

_ALLOWED_SCHEMES = frozenset({"http", "https"})

_BLOCKED_HOSTS = frozenset(
    {
        "localhost",
        "metadata.google.internal",
        "metadata.goog",
        "metadata",
    }
)

_BLOCKED_HOST_SUFFIXES = (
    ".local",
    ".localhost",
    ".internal",
)


class SSRFBlockedError(ValueError):
    """Raised when a URL is not allowed for outbound fetch."""


def _blocked_ip_reason(host: str) -> str | None:
    try:
        addr = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return None
    if (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
    ):
        return f"blocked address {addr}"
    return None


def _blocked_numeric_host(host: str) -> str | None:
    if not host.isdigit():
        return None
    try:
        value = int(host)
    except ValueError:
        return None
    if value < 0 or value > 0xFFFFFFFF:
        return None
    try:
        addr = ipaddress.ip_address(struct.pack("!I", value))
    except (struct.error, ValueError, OverflowError):
        return None
    return _blocked_ip_reason(str(addr))


def validate_fetch_url(url: str) -> str | None:
    """Return an error string if the URL must not be fetched, else None."""
    raw = (url or "").strip()
    if not raw:
        return "empty URL"
    if len(raw) > 2048:
        return "URL too long"

    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").lower()
    if scheme not in _ALLOWED_SCHEMES:
        return f"unsupported scheme: {scheme or '(none)'}"

    if parsed.username or parsed.password:
        return "credentials in URL are not allowed"

    host = (parsed.hostname or "").lower().strip(".")
    if not host:
        return "missing hostname"

    if host in _BLOCKED_HOSTS or host == "169.254.169.254":
        return f"blocked host: {host}"

    if any(host.endswith(suffix) for suffix in _BLOCKED_HOST_SUFFIXES):
        return f"blocked host: {host}"

    for check in (_blocked_ip_reason, _blocked_numeric_host):
        reason = check(host)
        if reason:
            return reason

    return None


def assert_fetch_url_allowed(url: str) -> None:
    """Raise SSRFBlockedError when URL is not allowed."""
    reason = validate_fetch_url(url)
    if reason:
        raise SSRFBlockedError(reason)


async def ssrf_httpx_request_hook(request) -> None:
    """httpx event hook — validate each request URL (including redirects)."""
    assert_fetch_url_allowed(str(request.url))
