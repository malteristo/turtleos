"""The X server behind the door.

Speaks the hosted MCP bridge. The app login stays in the bridge's own store.
This file does not decide who may be offered the connection, and it does not
name that tool. A write-shaped tool is never selected.
"""

from __future__ import annotations

import base64
import json
import os
import re
import select
import shutil
import subprocess
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

APP = "tos-mcp"
MCP_URL = "https://api.x.com/mcp"
CALL_TIMEOUT = 25
FETCH_TIMEOUT = 8
FETCH_LIMIT = 100_000

_STATUS = re.compile(
    r"(?:x|twitter)\.com/(?:[^/\s]+/status|i/web/status)/(\d+)",
    re.I,
)
_ARTICLE = re.compile(
    r"(?:x|twitter)\.com/(?:i/articles|i/article|[^/\s]+/article)/(\d+)",
    re.I,
)
_X_HOSTS = {
    "x.com",
    "www.x.com",
    "twitter.com",
    "www.twitter.com",
    "mobile.twitter.com",
    "pic.twitter.com",
    "pbs.twimg.com",
    "video.twimg.com",
    "t.co",
}
_WRITE_MARKERS = (
    "create",
    "delete",
    "remove",
    "destroy",
    "add",
    "like",
    "repost",
    "publish",
    "follow",
    "mute",
    "block",
    "send",
    "mark_",
)


def resolve_xurl(found: str | None, local: Path) -> str:
    """The bridge binary. A launchd service does not have ~/.local/bin on its path."""
    if found:
        return found
    if local.is_file() and os.access(local, os.X_OK):
        return str(local)
    return "xurl"


def clear_command(account: str, binary: str = "xurl") -> list[str]:
    """Drop one account's login. Never every login on the machine."""
    account = (account or "").strip().lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9_]{1,15}", account):
        raise ValueError("A sign-in needs an account name.")
    return [binary, "--app", APP, "auth", "clear", "--oauth2-username", account]


def clear_login(account: str) -> bool:
    """True when that account's login is gone. The output is not kept."""
    binary = resolve_xurl(shutil.which("xurl"), Path.home() / ".local" / "bin" / "xurl")
    command = clear_command(account, binary)
    if "--all" in command:
        return False
    try:
        finished = subprocess.run(command, capture_output=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return finished.returncode == 0


def command_for(account: str) -> list[str]:
    """The bridge command. The account is an argument, never a secret."""
    binary = resolve_xurl(shutil.which("xurl"), Path.home() / ".local" / "bin" / "xurl")
    return [binary, "--app", APP, "-u", account, "mcp", MCP_URL]


def _is_write(name: str) -> bool:
    lowered = name.lower().replace("-", "_")
    return any(marker in lowered for marker in _WRITE_MARKERS)


def _is_me(name: str) -> bool:
    lowered = name.lower().replace("-", "_")
    return lowered in {"get_me", "get_users_me", "whoami", "find_my_user"} or lowered.endswith("_me") or "users_me" in lowered


def choose_tools(tools: list[dict]) -> dict[str, dict]:
    """Read tools only. A write is not a candidate, even when it is the only match."""
    reads = [tool for tool in tools if tool.get("name") and not _is_write(str(tool["name"]))]
    chosen: dict[str, dict] = {}
    me = [tool for tool in reads if _is_me(str(tool["name"]))]
    if me:
        chosen["me"] = me[0]
    search = [
        tool
        for tool in reads
        if "search" in str(tool["name"]).lower()
        and any(word in str(tool["name"]).lower() for word in ("post", "tweet"))
        and "user" not in str(tool["name"]).lower()
    ]
    recent = [tool for tool in search if "recent" in str(tool["name"]).lower()]
    if recent or search:
        chosen["search"] = (recent or search)[0]
    bookmarks = [tool for tool in reads if "bookmark" in str(tool["name"]).lower()]
    if bookmarks:
        chosen["bookmarks"] = bookmarks[0]
    articles = [tool for tool in reads if "article" in str(tool["name"]).lower()]
    if articles:
        chosen["article"] = articles[0]
    opens = []
    for tool in reads:
        name = str(tool["name"]).lower()
        if "search" in name or "bookmark" in name or "count" in name or "article" in name:
            continue
        if any(word in name for word in ("tweet", "post")) and any(
            word in name for word in ("get", "lookup", "find", "fetch")
        ):
            opens.append(tool)
    if opens:
        # A batch lookup is listed first and returns the title. The one-post
        # lookup is the read that carries the article body.
        one = [
            tool
            for tool in opens
            if str(tool["name"]).lower().endswith("_by_id")
            or (
                "id" in ((tool.get("inputSchema") or {}).get("properties") or {})
                and "ids" not in ((tool.get("inputSchema") or {}).get("properties") or {})
            )
        ]
        chosen["open"] = (one or opens)[0]
    return chosen


def fill_args(schema: dict, *, id: str = "", query: str = "", url: str = "") -> dict:
    props = schema.get("properties") or {}
    if not isinstance(props, dict):
        props = {}
    out: dict = {}

    def put(key: str, value: str) -> None:
        if key not in props or value == "":
            return
        spec = props.get(key) or {}
        filled: object = value
        if isinstance(spec, dict) and spec.get("type") == "array":
            filled = [value]
        out[key] = filled

    put("ids", id)
    put("id", id)
    put("tweet_id", id)
    put("post_id", id)
    put("query", query)
    put("q", query)
    put("url", url)
    if "expansions" in props:
        # cover_media is what makes the hosted tool return article.plain_text
        # instead of the title alone. attachments.media_keys is the picture.
        out["expansions"] = "referenced_tweets.id,attachments.media_keys,article.cover_media"
    if "media.fields" in props:
        out["media.fields"] = "url,preview_image_url,type,alt_text,width,height,duration_ms"
    fields = "article,entities,note_tweet,referenced_tweets,text"
    if "tweet.fields" in props:
        out["tweet.fields"] = fields
    if "post.fields" in props:
        out["post.fields"] = fields
        # The tool lists this as post.fields. Asking only under that name
        # returns an article title. The body arrives with tweet.fields.
        out["tweet.fields"] = fields
    if "max_results" in props and query:
        spec = props.get("max_results") or {}
        out["max_results"] = 10 if isinstance(spec, dict) and spec.get("type") == "integer" else "10"
    return out


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def _url_items(tweet: dict) -> list[dict]:
    items: list[dict] = []
    groups = [tweet.get("entities")]
    article = tweet.get("article")
    if isinstance(article, dict):
        groups.append(article.get("entities"))
    for group in groups:
        if not isinstance(group, dict):
            continue
        urls = group.get("urls")
        if isinstance(urls, list):
            items.extend(item for item in urls if isinstance(item, dict))
    return items


def _offers(tweet: dict) -> list[str]:
    found: list[str] = []
    for item in _url_items(tweet):
        expanded = str(item.get("unwound_url") or item.get("expanded_url") or "")
        if not expanded or _host(expanded) in _X_HOSTS or expanded in found:
            continue
        found.append(expanded)
    return found


def _text(tweet: dict) -> str:
    note = tweet.get("note_tweet") or {}
    article = tweet.get("article") or {}
    if not isinstance(note, dict):
        note = {}
    if not isinstance(article, dict):
        article = {}
    body = str(article.get("plain_text") or article.get("text") or "")
    if body:
        title = str(article.get("title") or "").strip()
        if title and title not in body:
            return f"{title}\n\n{body}"
        return body
    return str(note.get("text") or tweet.get("text") or "")


def _as_tweet(payload: dict) -> tuple[dict, dict]:
    data = payload.get("data")
    includes = payload.get("includes") if isinstance(payload.get("includes"), dict) else {}
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0], includes
    if isinstance(data, dict):
        return data, includes
    if payload.get("text") or payload.get("id"):
        return payload, includes
    return {}, includes


def _nested(tweet: dict, includes: dict) -> dict | None:
    refs = [
        ref
        for ref in (tweet.get("referenced_tweets") or [])
        if isinstance(ref, dict) and ref.get("type") in {"quoted", "replied_to"}
    ]
    if not refs:
        return None
    wanted = str(refs[0].get("id") or "")
    for item in includes.get("tweets") or []:
        if isinstance(item, dict) and str(item.get("id") or "") == wanted:
            return {
                "text": _text(item),
                "offers": _offers(item),
                "relation": str(refs[0].get("type") or ""),
            }
    return None


def to_open(payload: dict, link: str) -> dict:
    tweet, includes = _as_tweet(payload if isinstance(payload, dict) else {})
    article = tweet.get("article") if isinstance(tweet.get("article"), dict) else {}
    is_article = bool(article.get("plain_text") or article.get("text")) or bool(_ARTICLE.search(link or ""))
    opened = {"kind": "article" if is_article else "post", "text": _text(tweet), "offers": _offers(tweet)}
    nested = _nested(tweet, includes)
    if nested and not is_article:
        opened["nested"] = nested
    return opened


def to_posts(payload: dict) -> list[dict]:
    data = payload.get("data") if isinstance(payload, dict) else None
    rows = data if isinstance(data, list) else []
    posts = []
    for tweet in rows:
        if not isinstance(tweet, dict):
            continue
        text = _text(tweet)
        if not text:
            continue
        posts.append({"id": str(tweet.get("id") or ""), "title": text[:120], "text": text})
    return posts


def to_bookmarks(payload: dict, person: str) -> list[dict]:
    return [
        {"person": person, "id": post["id"], "title": post["title"][:40], "text": post["text"]}
        for post in to_posts(payload)
    ]


_IMAGE_HOSTS = {"pbs.twimg.com", "video.twimg.com"}
_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
_IMAGE_MAX = 4_000_000


def _image_host(url: str) -> bool:
    return (urlparse(url).hostname or "").lower() in _IMAGE_HOSTS


def views_in(payload: dict) -> list[dict]:
    """Pictures on the post. A video contributes its preview frame. Other hosts are not pictures."""
    if isinstance(payload, dict) and isinstance(payload.get("result"), dict):
        payload = payload["result"]
    includes = payload.get("includes") if isinstance(payload, dict) else None
    media = includes.get("media") if isinstance(includes, dict) else None
    if not isinstance(media, list):
        return []
    found: list[dict] = []
    for item in media:
        if len(found) >= 4:
            break
        if not isinstance(item, dict):
            continue
        kind = str(item.get("type") or "")
        if kind == "photo":
            url = str(item.get("url") or "")
            shown = "photo"
        elif kind in {"video", "animated_gif"}:
            url = str(item.get("preview_image_url") or "")
            shown = "video" if kind == "video" else "photo"
        else:
            continue
        if not _image_host(url):
            continue
        found.append({"url": url, "kind": shown})
    return found


def views_in_text(text: str) -> list[dict]:
    """The views inside a fetched block. A page that is not that block has none."""
    start = (text or "").find("{")
    if start < 0:
        return []
    try:
        payload, _ = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, dict):
        return []
    return views_in(payload)


def fetch_views(views: list[dict]) -> list[dict]:
    """The bytes for this turn. A host that is not the picture host is not fetched."""
    out: list[dict] = []
    for view in views or []:
        if not isinstance(view, dict):
            continue
        loaded = _fetch_image(str(view.get("url") or ""))
        if loaded is None:
            continue
        media_type, data = loaded
        out.append({"kind": view.get("kind") or "photo", "media_type": media_type, "data": data})
    return out


def _fetch_image(url: str) -> tuple[str, str] | None:
    if not _image_host(url):
        return None
    request = urllib.request.Request(url, headers={"User-Agent": "turtle"})
    with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT) as response:
        if not _image_host(response.geturl()):
            return None
        media_type = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if media_type not in _IMAGE_TYPES:
            return None
        raw = response.read(_IMAGE_MAX + 1)
    if not raw or len(raw) > _IMAGE_MAX:
        return None
    return media_type, base64.b64encode(raw).decode("ascii")


def offers_for(payload: dict) -> list[str]:
    """Links that leave X. They are named. They are not fetched."""
    if not isinstance(payload, dict):
        return []
    found: list[str] = []

    def take(tweet: dict) -> None:
        for url in _offers(tweet):
            if url not in found:
                found.append(url)

    data = payload.get("data")
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                take(item)
    elif isinstance(data, dict):
        take(data)
    includes = payload.get("includes") if isinstance(payload.get("includes"), dict) else {}
    for item in includes.get("tweets") or []:
        if isinstance(item, dict):
            take(item)
    return found


def _opens_a_post(name: str) -> bool:
    """The post-body fields belong to opening a post. An account or a bookmark list rejects them."""
    lowered = name.lower().replace("-", "_")
    if any(word in lowered for word in ("search", "bookmark", "count")):
        return False
    if lowered.endswith("_me") or "users_me" in lowered or lowered.startswith("get_user"):
        return False
    return any(word in lowered for word in ("tweet", "post")) and any(
        word in lowered for word in ("get", "lookup", "find", "fetch")
    )


def _with_read_fields(schema: dict, arguments: dict) -> dict:
    """A call that names a post still asks for the body and the nested post.

    The model may pass only an id. The field the tool lists is not the field
    that carries the article, so those fields are filled when the schema has them.
    A value the model already set, other than those fields, is kept.
    """
    merged = dict(arguments)
    ident = arguments.get("id") or arguments.get("ids") or arguments.get("tweet_id") or arguments.get("post_id") or ""
    if isinstance(ident, list):
        ident = str(ident[0]) if ident else ""
    query = str(arguments.get("query") or arguments.get("q") or "")
    url = str(arguments.get("url") or "")
    defaults = fill_args(
        schema if isinstance(schema, dict) else {},
        id=str(ident),
        query=query,
        url=url,
    )
    for key in ("expansions", "tweet.fields", "post.fields"):
        if key in defaults:
            merged[key] = defaults[key]
    for key, value in defaults.items():
        merged.setdefault(key, value)
    return merged


def _user_id(payload: dict) -> str:
    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, dict) and data.get("id"):
        return str(data["id"])
    if isinstance(payload, dict) and payload.get("id"):
        return str(payload["id"])
    return ""


def _content_json(result: dict) -> dict:
    for block in (result or {}).get("content") or []:
        if not isinstance(block, dict):
            continue
        text = block.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return {"text": text}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def status_id(link: str) -> str:
    match = _STATUS.search(link or "")
    return match.group(1) if match else ""


def article_id(link: str) -> str:
    match = _ARTICLE.search(link or "")
    return match.group(1) if match else ""


class ScriptedTransport:
    """A stand-in bridge. Tests plant the replies. Nothing is opened."""

    def __init__(self, results: dict):
        self.results = results
        self.sent: list[dict] = []
        self.closed = False

    def exchange(self, message: dict, *, wait: bool, timeout: float) -> dict | None:
        del timeout
        self.sent.append(message)
        if not wait:
            return None
        method = str(message.get("method") or "")
        result = self.results[method]
        if method == "tools/call" and callable(result):
            result = result(message)
        return {"jsonrpc": "2.0", "id": message.get("id"), "result": result}

    def close(self) -> None:
        self.closed = True


class ProcessTransport:
    """One bridge process. Stderr is drained and never returned."""

    def __init__(self, command: list[str]):
        self.proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._drain = threading.Thread(target=self._read_err, name="x-bridge-err", daemon=True)
        self._drain.start()

    def _read_err(self) -> None:
        stderr = self.proc.stderr
        if stderr is None:
            return
        for _line in stderr:
            pass

    def exchange(self, message: dict, *, wait: bool, timeout: float) -> dict | None:
        stdin = self.proc.stdin
        stdout = self.proc.stdout
        if stdin is None or stdout is None:
            raise RuntimeError("X is not ready")
        stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        stdin.flush()
        if not wait:
            return None
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("X did not answer")
            ready, _, _ = select.select([stdout], [], [], remaining)
            if not ready:
                raise TimeoutError("X did not answer")
            line = stdout.readline()
            if not line:
                raise RuntimeError("X closed")
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("id") == message.get("id"):
                return obj

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.kill()
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass


class McpSession:
    def __init__(self, transport):
        self.transport = transport
        self._id = 0

    def start(self) -> str:
        """The server's own manual, when it sends one. An empty string is not one."""
        result = self._rpc(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "turtle", "version": "0"},
            },
        )
        self._rpc("notifications/initialized", notify=True)
        if isinstance(result, dict):
            return str(result.get("instructions") or "")
        return ""

    def tools(self) -> list[dict]:
        result = self._rpc("tools/list")
        tools = result.get("tools") if isinstance(result, dict) else None
        return [tool for tool in tools or [] if isinstance(tool, dict)]

    def call(self, name: str, arguments: dict) -> dict:
        result = self._rpc("tools/call", {"name": name, "arguments": arguments})
        return _content_json(result if isinstance(result, dict) else {})

    def _rpc(self, method: str, params: dict | None = None, *, notify: bool = False) -> dict:
        message: dict = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        if not notify:
            self._id += 1
            message["id"] = self._id
        reply = self.transport.exchange(message, wait=not notify, timeout=CALL_TIMEOUT)
        if notify:
            return {}
        if not isinstance(reply, dict) or reply.get("error"):
            raise RuntimeError("X refused the call")
        result = reply.get("result")
        return result if isinstance(result, dict) else {}


class XServer:
    """Reads through the bridge. Writes are not among the tools it will call."""

    def __init__(self, account: str, opener: Callable | None = None, fetch: Callable[[str], str] | None = None):
        self.account = account
        self._opener = opener or (lambda: ProcessTransport(command_for(account)))
        self._fetch = fetch or _fetch_url
        self.last_catalog: dict | None = None

    def open_payload(self, link: str) -> dict:
        """The object the server returned for this link. Not a sentence about it."""
        article = article_id(link)
        status = status_id(link)
        if article:
            return self._run("article", id=article, url=link)
        if status:
            return self._run("open", id=status, url=link)
        return {}

    def call_named(self, name: str, arguments: dict) -> dict:
        """One tool the server listed. A write is not called."""
        if _is_write(name):
            raise RuntimeError("refused")
        arguments = arguments if isinstance(arguments, dict) else {}
        transport = self._opener()
        try:
            session = McpSession(transport)
            tools = self._remember(session)
            schema: dict = {}
            known = False
            for tool in tools:
                if str(tool.get("name") or "") == name:
                    known = True
                    raw = tool.get("inputSchema")
                    schema = raw if isinstance(raw, dict) else {}
                    break
            if not known:
                raise RuntimeError("X refused the call")
            # Those fields make a post read return the article. The same keys
            # on an account or bookmark call are rejected.
            if _opens_a_post(name):
                arguments = _with_read_fields(schema, arguments)
            return session.call(name, arguments)
        finally:
            transport.close()

    def probe(self) -> None:
        """The server's tool list and manual. No post is read."""
        transport = self._opener()
        try:
            session = McpSession(transport)
            self._remember(session)
        finally:
            transport.close()

    def _remember(self, session: McpSession) -> list[dict]:
        instructions = session.start()
        tools = session.tools()
        self.last_catalog = {"instructions": instructions, "tools": tools}
        return tools

    def open_link(self, link: str) -> dict:
        article = article_id(link)
        status = status_id(link)
        if article:
            payload = self._run("article", id=article, url=link)
            opened = to_open(payload, link)
            opened["kind"] = "article"
            return opened
        if not status:
            return {"kind": "post", "text": ""}
        return to_open(self._run("open", id=status, url=link), link)

    def search(self, query: str) -> list[dict]:
        return to_posts(self._run("search", query=query))

    def bookmarks(self, person: str) -> list[dict]:
        return to_bookmarks(self._bookmarks(person), person)

    def fetch_url(self, url: str) -> str:
        parsed = urllib.parse.urlparse(url or "")
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return "That link cannot be read."
        return self._fetch(url)

    def _bookmarks(self, person: str) -> dict:
        del person
        transport = self._opener()
        try:
            session = McpSession(transport)
            chosen = choose_tools(self._remember(session))
            tool = chosen.get("bookmarks")
            if not tool:
                raise RuntimeError("X refused the call")
            schema = tool.get("inputSchema") or {}
            props = schema.get("properties") or {}
            user_id = ""
            if isinstance(props, dict) and "id" in props and "me" in chosen:
                user_id = _user_id(session.call(chosen["me"]["name"], {}))
            return session.call(tool["name"], fill_args(schema if isinstance(schema, dict) else {}, id=user_id))
        finally:
            transport.close()

    def _run(self, purpose: str, *, id: str = "", query: str = "", url: str = "") -> dict:
        transport = self._opener()
        try:
            session = McpSession(transport)
            chosen = choose_tools(self._remember(session))
            tool = chosen.get(purpose)
            if not tool:
                raise RuntimeError("X refused the call")
            schema = tool.get("inputSchema") or {}
            arguments = fill_args(schema if isinstance(schema, dict) else {}, id=id, query=query, url=url)
            return session.call(tool["name"], arguments)
        finally:
            transport.close()


def _fetch_url(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "turtle"})
    with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT) as response:
        raw = response.read(FETCH_LIMIT)
    return raw.decode("utf-8", errors="replace")
