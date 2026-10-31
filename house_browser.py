"""The house spirit's browser: one page, read as text.

It opens an address and returns the words. It does not click, type, or stay
signed in. A second address is a later open. A forge turn cannot open one.

The address is checked with the same rule as the house's other fetches
(`core.url_validate`). A name that resolves to a private address is not
resolved again here: that is the check the rest of the house already uses,
and a second resolver would be a different gate. A redirect is checked again,
because the first address can be public and the next one private.

The audit names the act, not the address. The session keeps the address and
the start of what was read, the same way it keeps any other tool.
"""

from __future__ import annotations

import re
import socket
import urllib.error
import urllib.request
from html.parser import HTMLParser

from core.url_validate import validate_fetch_url
from workshop_tools import OUTPUT_MAX, Refused, audit, current, forge_active, offered

TIMEOUT = 20
READ_MAX = 500_000
FORGE_HELD = "A forge spirit does not have the browser."
USER_AGENT = "turtleOS (house spirit)"

_TOOL = {
    "type": "function",
    "function": {
        "name": "house_browser",
        "description": (
            "Open one page and read its text. url is the address. "
            "This does not click, type, or stay signed in. "
            "A forge spirit cannot open a page."
        ),
        "parameters": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
}
NAMES = frozenset({"house_browser"})
_SKIP = {"script", "style", "noscript"}


def handles(name: str) -> bool:
    return name in NAMES


def tools_offered() -> list[dict]:
    return [_TOOL] if offered() else []


def channel_line(name: str, args: dict | None = None) -> str | None:
    """The host and the path. Never the query, and never the page."""
    if name not in NAMES:
        return None
    from urllib.parse import urlparse

    raw = str((args or {}).get("url") or "").strip()
    parsed = urlparse(raw)
    shown = (parsed.netloc + (parsed.path or "")).strip()
    if not shown:
        return "opened a page"
    if len(shown) > 120:
        shown = shown[:120] + "…"
    return f"opened `{shown}`"


def _allow(url: str) -> None:
    if validate_fetch_url(url):
        raise Refused("That page is not one to open.")


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in _SKIP:
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in _SKIP and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip and data:
            self.parts.append(data)


def _html_text(raw: str) -> str:
    parser = _Text()
    parser.feed(raw)
    parser.close()
    text = "".join(parser.parts)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class _Redirect(urllib.request.HTTPRedirectHandler):
    max_redirections = 5

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _allow(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _as_text(raw: bytes, content_type: str) -> str:
    kind = content_type.split(";", 1)[0].strip().lower()
    textual = kind.startswith("text/") or kind in {"application/xhtml+xml", "application/xml", "text/xml"}
    if kind and not textual:
        raise Refused("That page is not text.")
    text = raw.decode("utf-8", errors="replace")
    if "html" in kind or text.lstrip()[:9].lower().startswith(("<!doctype", "<html")):
        text = _html_text(text)
    return text.strip()


def _retrieve(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html, text/plain;q=0.9"},
        method="GET",
    )
    opener = urllib.request.build_opener(_Redirect)
    try:
        with opener.open(request, timeout=TIMEOUT) as response:
            final = response.geturl()
            _allow(final)
            content_type = response.headers.get("Content-Type", "")
            raw = response.read(READ_MAX + 1)
    except Refused:
        raise
    except urllib.error.HTTPError as exc:
        raise Refused(f"That page returned {exc.code}.") from exc
    except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
        raise Refused("That page did not open.") from exc
    if len(raw) > READ_MAX:
        raw = raw[:READ_MAX]
    text = _as_text(raw, content_type)
    if not text:
        raise Refused("That page had no text.")
    if len(text) > OUTPUT_MAX:
        text = text[:OUTPUT_MAX] + "\n… (cut)"
    return f"{final}\n\n{text}"


def _open(url: str) -> str:
    _allow(url)
    return _retrieve(url)


def call(name: str, arguments: dict | None = None) -> str:
    if name not in NAMES:
        return "That tool is not available."
    args = arguments if isinstance(arguments, dict) else {}
    _registry, _channel, person = current()
    if not offered():
        audit(person, name, "refused")
        return "Not in this room."
    if forge_active():
        audit(person, name, "refused")
        return FORGE_HELD
    try:
        url = str(args.get("url") or "").strip()
        if not url:
            raise Refused("Name the page.")
        body = _open(url)
    except Refused as exc:
        audit(person, name, "refused")
        return str(exc)
    except (OSError, ValueError):
        audit(person, name, "failed")
        return "That did not work."
    audit(person, name, "called")
    return body
