"""The door for an outgoing personal connection.

One module resolves the sign-in and decides where the connection is offered.
The tool list asks `connection_tools`. It does not decide. A second file that
names the tool is an offer site, and the exempt list is empty on purpose:
asking is not a second offer, so `tos_tools` must not contain the tool name.

The server behind the door is injected. A missing sign-in does not call the
server. A sign-in is a file naming the person and their X account, with no
secret in it; the secret stays in the X login on that machine. The audit line
records the person,
the service, the operation, and the decision. It is not the guest door's file,
and it does not hold what came back.
"""

from __future__ import annotations

import json
import re
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

@dataclass(frozen=True)
class Shell:
    """What this door needs to know about the room it is asked from.

    The shell (a bot) hands these in at startup (`outgoing_connect_ui.
    register_outgoing_views`), so this module does not import `mage`, the
    practice's widest coupling (issue 053). Each is a callable and not a value:
    who is asking, and which runtime they stand in, change with every turn.
    """

    registry: Callable[[], dict]
    actor_key: Callable[[], str | None]
    runtime_dir: Callable[[], str | None]
    runtime_dirs: Callable[[], list[str]]
    # The registered room the turn is in. None where the shell cannot say, and then the
    # attunement alone decides, as it did before rooms had a switch.
    channel_id: Callable[[], object] | None = None


_shell: Shell | None = None
_told_unbound = False


def bind(shell: Shell | None) -> None:
    global _shell
    _shell = shell


def shell() -> Shell | None:
    """The bound shell. Asked for while unbound, it says so once: an unbound door
    refuses everyone as 'nobody is signed in', and that must not look like a fact."""
    global _told_unbound
    if _shell is None and not _told_unbound:
        _told_unbound = True
        print("Outgoing connections used before a shell was bound — nobody is signed in as far as this door can see.")
    return _shell


TOOL_NAME = "x_connection"
SERVICE = "X"
AUDIT_NAME = "outgoing_audit.jsonl"
GUEST_AUDIT_NAME = "mcp_audit.jsonl"
SIGNIN_NAME = "x-account.json"
PAUSE_NAME = "x-paused.json"
CATALOG_NAME = "x-mcp-catalog.json"
CATALOG_MAX_AGE = 24 * 60 * 60
HEALTH_NAME = "x-health.json"
HEALTH_EVERY = 30 * 60
_HEALTH_KEYS = frozenset({"person", "status", "checked", "tries", "raised"})
_MANUAL_MAX = 4000
_ACCOUNT = re.compile(r"^[A-Za-z0-9_]{1,15}$")
_SIGNIN_KEYS = frozenset({"person", "account"})
_PAUSE_KEYS = frozenset({"person"})

# Decided empty. A file other than this one that names the tool is a second offer.
EXEMPT_OFFER_SITES: frozenset[str] = frozenset()

_SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "tests",
    # Scratch copy of the public subset. Kept between publishes. Not a second door.
    ".publish-worktree",
}


class RefusingServer:
    """Called only by a bug. A missing sign-in must not reach a server."""

    def open_link(self, link: str) -> dict:
        raise AssertionError(f"open_link without a sign-in: {link}")

    def fetch_url(self, url: str) -> str:
        raise AssertionError(f"fetch_url without a sign-in: {url}")

    def search(self, query: str) -> list[dict]:
        raise AssertionError(f"search without a sign-in: {query}")

    def bookmarks(self, person: str) -> list[dict]:
        raise AssertionError(f"bookmarks without a sign-in: {person}")


ANSWERS_IN = "craft"  # the one room X answers in; the `!mcp` list names it from this same value


def connection_offered(attunement: str) -> bool:
    """Craft only, and only where the person has not switched it off.

    A tool in every room is how a family conversation reaches it. The ceiling is
    `room_connections`; the attunement stays as the first gate for a shell that
    cannot name its room."""
    if attunement != ANSWERS_IN:
        return False
    bound = shell()
    if bound is None or bound.channel_id is None:
        return True
    try:
        channel = bound.channel_id()
    except Exception:
        return False
    if channel is None:
        return True
    from room_connections import level

    try:
        registry = bound.registry()
    except Exception:
        return False
    return level("x", registry=registry, channel_id=channel, person=_asker(), root=_runtime_root()) != "off"


# The server's list for this process. None means "read the file if the runtime has one."
_installed: dict | None = None


def install_catalog(catalog: dict | None) -> None:
    """Tests plant the server's list. Production loads it from the runtime."""
    global _installed
    _installed = catalog


def catalog_path(root: Path) -> Path:
    return root / "state" / CATALOG_NAME


def _read_catalog_file(root: Path) -> dict | None:
    path = catalog_path(root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    if not isinstance(data, dict):
        return None
    tools = data.get("tools")
    if not isinstance(tools, list):
        return None
    return {
        "instructions": str(data.get("instructions") or ""),
        "tools": [tool for tool in tools if isinstance(tool, dict) and tool.get("name")],
    }


def load_catalog() -> dict:
    if _installed is not None:
        tools = _installed.get("tools") if isinstance(_installed, dict) else None
        return {
            "instructions": str((_installed or {}).get("instructions") or ""),
            "tools": [tool for tool in (tools or []) if isinstance(tool, dict) and tool.get("name")],
        }
    root = _runtime_root()
    if root is None:
        return {"instructions": "", "tools": []}
    return _read_catalog_file(root) or {"instructions": "", "tools": []}


def publish_catalog(catalog: dict, root: Path | None) -> None:
    """Remember the server's list. A call result is not part of it."""
    tools = [
        tool
        for tool in (catalog.get("tools") or [])
        if isinstance(tool, dict) and tool.get("name")
    ]
    kept = {"instructions": str(catalog.get("instructions") or ""), "tools": tools}
    install_catalog(kept)
    if root is None:
        return
    path = catalog_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(kept, ensure_ascii=False) + "\n", encoding="utf-8")
    path.chmod(0o600)


def _keep_catalog(server: object, root: Path | None) -> None:
    catalog = getattr(server, "last_catalog", None)
    if isinstance(catalog, dict) and catalog.get("tools"):
        publish_catalog(catalog, root)


def refresh_catalog_if_due() -> None:
    """Ask the server for its list when this machine does not have a fresh one.

    The list is the server's own description of this sign-in. It is not a post.
    A turn that already wrote the list this day does not ask again.
    """
    person = _asker()
    root = _runtime_root()
    if not person or root is None:
        return
    account = account_for(person, root)
    if not account or paused_for(person, root):
        return
    path = catalog_path(root)
    try:
        fresh = path.is_file() and (time.time() - path.stat().st_mtime) < CATALOG_MAX_AGE
    except OSError:
        fresh = False
    if fresh:
        existing = _read_catalog_file(root)
        if existing and _installed is None:
            install_catalog(existing)
        return
    try:
        from outgoing_x import XServer

        server = XServer(account)
        server.probe()
    except Exception:
        return
    _keep_catalog(server, root)


def _function_spec(tool: dict) -> dict:
    schema = tool.get("inputSchema") if isinstance(tool.get("inputSchema"), dict) else {
        "type": "object",
        "properties": {},
    }
    description = str(tool.get("description") or "").strip() or str(tool.get("name") or "")
    return {
        "type": "function",
        "function": {
            "name": str(tool["name"]),
            "description": description,
            "parameters": schema,
        },
    }


def _writable(name: str) -> bool:
    from outgoing_x import _is_write

    return _is_write(name)


def handles_tool(name: str) -> bool:
    """True for a tool the server listed, including a write the offer left off."""
    if not name or name == TOOL_NAME:
        return False
    return any(str(tool.get("name") or "") == name for tool in load_catalog().get("tools") or [])


def connection_tools(attunement: str) -> list[dict]:
    """The server's read tools, in the server's words. A write is not offered."""
    if not connection_offered(attunement) or asker_is_paused():
        return []
    offered = []
    for tool in load_catalog().get("tools") or []:
        name = str(tool.get("name") or "")
        if not name or _writable(name):
            continue
        offered.append(_function_spec(tool))
    return offered


def connection_preamble(attunement: str) -> str:
    """The manual `initialize` returned. No manual, no paragraph."""
    if not connection_offered(attunement):
        return ""
    if asker_is_paused():
        return "X is paused."
    text = str(load_catalog().get("instructions") or "").strip()
    if len(text) > _MANUAL_MAX:
        text = text[:_MANUAL_MAX]
    return text


def channel_line(name: str) -> str | None:
    """What the channel says about one X call. Not the tool's name, not its result."""
    if not handles_tool(name):
        return None
    if _writable(name):
        return "X refused a write"
    lowered = name.lower().replace("-", "_")
    if "search" in lowered:
        return "searched X"
    if "bookmark" in lowered:
        return "read bookmarks on X"
    if lowered.endswith("_me") or "users_me" in lowered:
        return "checked the X account"
    if "article" in lowered:
        return "read an article on X"
    return "read X"


def tool_log_line(name: str, result: str) -> str:
    """The process log names the call. An X result is a length, not the object."""
    if handles_tool(name):
        return f"{name} -> {len(result or '')} chars"
    return f"{name} -> {result}"


def offer_sites(root: Path) -> list[str]:
    """Files other than this module that name the tool.

    ``MISSING_DOOR`` when this module is absent, which is the tree before the door.
    The exempt list is applied and is empty, so an exempt name would still be
    reported if one were added without a reason. Tests are not offer sites.
    """
    root = root.resolve()
    door = root / Path(__file__).name
    if not door.is_file():
        return ["MISSING_DOOR"]
    hits: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if path.resolve() == door:
            continue
        rel = path.relative_to(root).as_posix()
        if rel in EXEMPT_OFFER_SITES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if TOOL_NAME in text:
            hits.append(rel)
    return hits


def files_containing(root: Path, phrase: str) -> list[str]:
    """Durable files under root whose text contains phrase. The eddy result is not a file."""
    if not root.exists():
        return []
    found: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        if phrase in text:
            found.append(path.relative_to(root).as_posix())
    return found


def is_summary(text: str, titles: list[str]) -> bool:
    """A summary names the planted titles. A list of identifiers is not one."""
    if not text.startswith("Recent relevant posts:"):
        return False
    if not titles:
        return False
    return all(title in text for title in titles)


def summarize(posts: list[dict]) -> str:
    titles = [str(post.get("title") or "").strip() for post in posts]
    titles = [title for title in titles if title]
    if not titles:
        return ""
    lines = ["Recent relevant posts:"]
    lines.extend(f"- {title}" for title in titles)
    return "\n".join(lines)


class Door:
    """One sign-in per person. Rooms share it. Another person is another lookup."""

    def __init__(self, audit_root: Path | None, server: object | None = None):
        self.audit_root = audit_root
        self.server = server if server is not None else RefusingServer()
        self._secrets: dict[str, str] = {}

    def sign_in(self, person: str, secret: str) -> None:
        """Replace nothing else. A second room does not store a second secret."""
        self._secrets[person] = secret

    def resolve(self, person: str) -> str | None:
        return self._secrets.get(person)

    def call(self, *, person: str, room: str, operation: str, arguments: dict | None = None) -> str:
        arguments = dict(arguments or {})
        operation = (operation or "").strip().lower()
        secret = self.resolve(person)
        header = f"[{SERVICE} — {person}'s]" if person else f"[{SERVICE} — unsigned]"

        if operation in {"write", "post", "calendar"}:
            self._audit(person, operation, "refused")
            return self._channel(person, header, "Refused.")

        if not secret:
            self._audit(person, operation or "open", "unsigned")
            return self._channel(person, header, "You have not signed in to X.")

        if operation == "search" and not str(arguments.get("query") or "").strip():
            self._audit(person, "search", "refused")
            return self._channel(person, header, "A search needs an ask.")

        body = self._perform(person, operation, arguments)
        self._audit(person, operation or "open", "called")
        return self._channel(person, header, body)

    def _perform(self, person: str, operation: str, arguments: dict) -> str:
        server = self.server
        if operation == "accept_offer":
            url = str(arguments.get("url") or "")
            return str(server.fetch_url(url))
        if operation == "search":
            posts = list(server.search(str(arguments.get("query") or "")))
            return summarize(posts)
        if operation == "bookmarks":
            rows = [
                row
                for row in server.bookmarks(person)
                if str(row.get("person") or "") == person
            ]
            return _render_bookmarks(rows, arguments)
        opened = server.open_link(str(arguments.get("link") or ""))
        return _render_open(opened)

    def _channel(self, person: str, header: str, body: str) -> str:
        text = f"{header}\n{body}" if body else header
        secret = self._secrets.get(person) or ""
        if secret:
            text = text.replace(secret, "[secret]")
        return text

    def _audit(self, person: str, operation: str, decision: str) -> None:
        if self.audit_root is None:
            return
        path = self.audit_root / "state" / AUDIT_NAME
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "person": person,
                "service": SERVICE,
                "operation": operation,
                "decision": decision,
            },
            ensure_ascii=False,
        )
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def _render_open(opened: dict) -> str:
    parts: list[str] = []
    text = str(opened.get("text") or "")
    nested = opened.get("nested")
    if isinstance(nested, dict) and str(nested.get("text") or "").strip():
        relation = str(nested.get("relation") or "")
        if relation == "quoted":
            label = "Quoted post"
        elif relation == "replied_to":
            label = "The post it replies to"
        else:
            label = "Nested post"
        # An unlabeled second block was read as a quote inside the first post.
        parts.append(f"Post:\n{text}")
        parts.append(f"{label}:\n{nested.get('text')}")
        parts.extend(_offer_lines(nested))
    else:
        parts.append(text)
    parts.extend(_offer_lines(opened))
    return "\n".join(part for part in parts if part)


def _offer_lines(obj: dict) -> list[str]:
    return [f"Offer: {url}" for url in (obj.get("offers") or [])]


def _about(row: dict, topic: str) -> bool:
    """A bookmark matches a topic by the label the fixture set, or by its text."""
    if not topic:
        return False
    if str(row.get("topic") or "") == topic:
        return True
    blob = f"{row.get('title') or ''} {row.get('text') or ''}".casefold()
    return topic.casefold() in blob


def _render_bookmarks(rows: list[dict], arguments: dict) -> str:
    which = str(arguments.get("which") or "all")
    if which == "topic":
        topic = str(arguments.get("topic") or "").strip()
        rows = [row for row in rows if _about(row, topic)]
    elif which == "one":
        wanted = str(arguments.get("bookmark_id") or "")
        rows = [row for row in rows if str(row.get("id") or "") == wanted]
    if not rows:
        return "Bookmarks:\nnone"
    lines = ["Bookmarks:"]
    for row in rows:
        lines.append(f"- {row.get('title')}: {row.get('text')}")
    return "\n".join(lines)


def unsigned_call(arguments: dict | None = None) -> str:
    """No asker. It does not call a server."""
    arguments = arguments if isinstance(arguments, dict) else {}
    operation = str(arguments.get("operation") or "open")
    return Door(None, RefusingServer()).call(
        person="",
        room="craft",
        operation=operation,
        arguments=arguments,
    )


def signin_path(root: Path) -> Path:
    return root / "state" / SIGNIN_NAME


def write_account(root: Path, person: str, account: str) -> None:
    """Record who signed in. The X secret is not this file."""
    person = (person or "").strip()
    account = (account or "").strip().lstrip("@")
    if not person or not _ACCOUNT.match(account):
        raise ValueError("A sign-in needs a person and their X account name.")
    path = signin_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"person": person, "account": account}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    path.chmod(0o600)


def pause_path(root: Path) -> Path:
    return root / "state" / PAUSE_NAME


def paused_for(person: str, root: Path | None) -> bool:
    """True only for this person's pause file. Any other field is not a pause."""
    if not person or root is None:
        return False
    path = pause_path(root)
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return False
    if not isinstance(data, dict) or set(data) != _PAUSE_KEYS:
        return False
    return data.get("person") == person


def set_paused(root: Path, person: str, paused: bool) -> None:
    """Pause keeps the sign-in. It is a separate file, so a secret cannot ride in either."""
    person = (person or "").strip()
    if not person:
        raise ValueError("A pause needs a person.")
    path = pause_path(root)
    if not paused:
        if paused_for(person, root):
            path.unlink()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"person": person}, ensure_ascii=False) + "\n", encoding="utf-8")
    path.chmod(0o600)


def asker_is_paused() -> bool:
    return paused_for(_asker(), _runtime_root())


def connection_list(person: str, root: Path | None, *, now: datetime | None = None) -> str:
    """The table the asker sees. The account name is not in it, and neither is a post."""
    status = _status_cell(person, root, now or datetime.now(timezone.utc))
    table = _connection_table(status)
    if not account_for(person, root):
        return (
            table
            + "\nThe browser on the machine finishes a sign-in. A key is not typed here."
        )
    return table


def _connection_table(status: str) -> str:
    rows = (
        ("Connection", "Status", "What it is"),
        ("X", status, f"Posts, bookmarks, and search, on your sign-in. Answers in {ANSWERS_IN}."),
    )
    widths = [max(len(row[i]) for row in rows) for i in range(3)]
    lines = ["Going out", "```"]
    for index, row in enumerate(rows):
        lines.append("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)).rstrip())
        if index == 0:
            lines.append("  ".join("-" * widths[i] for i in range(3)))
    lines.append("```")
    return "\n".join(lines)


def _status_cell(person: str, root: Path | None, now: datetime) -> str:
    if root is None or not account_for(person, root):
        return "not signed in"
    if paused_for(person, root):
        return "paused"
    health = health_for(person, root)
    if not health:
        return "not checked yet"
    if health["status"] == "down":
        return "not answering"
    return "ready, " + _ago(health["checked"], now)


def _ago(checked: str, now: datetime) -> str:
    try:
        then = datetime.fromisoformat(checked)
    except ValueError:
        return "checked"
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    seconds = max(0, int((now - then).total_seconds()))
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    return f"{seconds // 86400}d ago"


def health_path(root: Path) -> Path:
    return root / "state" / HEALTH_NAME


def health_for(person: str, root: Path | None) -> dict | None:
    """The last check. Any other field means there is no check."""
    if not person or root is None:
        return None
    path = health_path(root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    if not isinstance(data, dict) or set(data) != _HEALTH_KEYS:
        return None
    if data.get("person") != person:
        return None
    if data.get("status") not in {"ready", "down"}:
        return None
    if not isinstance(data.get("tries"), int) or data["tries"] < 0:
        return None
    if not isinstance(data.get("raised"), bool):
        return None
    if not isinstance(data.get("checked"), str):
        return None
    return data


def _write_health(root: Path, person: str, *, status: str, tries: int, raised: bool, now: datetime) -> None:
    path = health_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "person": person,
        "status": status,
        "checked": now.isoformat(),
        "tries": tries,
        "raised": raised,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    path.chmod(0o600)


def _age_seconds(health: dict, now: datetime) -> float | None:
    try:
        then = datetime.fromisoformat(str(health.get("checked") or ""))
    except ValueError:
        return None
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    return (now - then).total_seconds()


def _probe_ok(account: str, probe) -> bool:
    try:
        if probe is None:
            from outgoing_x import XServer

            XServer(account).probe()
        else:
            probe(account)
        return True
    except Exception:
        return False


def health_step(
    person: str,
    root: Path,
    *,
    quiet: bool,
    probe=None,
    now: datetime | None = None,
) -> str | None:
    """Check the login, or try it again once the room is quiet.

    A steady check does not read a post. A failure waits for quiet before the
    retry. The sentence comes back only when the house should hear it.
    """
    account = account_for(person, root)
    if not account or paused_for(person, root):
        return None
    now = now or datetime.now(timezone.utc)
    current = health_for(person, root)
    age = _age_seconds(current, now) if current else None
    waiting = bool(current and current["status"] == "down" and current["tries"] == 1 and not current["raised"])
    if waiting and not quiet:
        if age is not None and age >= HEALTH_EVERY:
            _write_health(root, person, status="down", tries=1, raised=True, now=now)
            return "X is not answering. There has not been a quiet moment to try again."
        return None
    recovering = bool(current and current["status"] == "down" and current["raised"])
    if recovering and (not quiet or (age is not None and age < HEALTH_EVERY)):
        return None
    if current and current["status"] == "ready" and age is not None and age < HEALTH_EVERY:
        return None
    return _check_login(person, root, account, current, probe, now)


def _check_login(person, root, account, current, probe, now: datetime) -> str | None:
    ok = _probe_ok(account, probe)
    door = Door(root, RefusingServer())
    door._audit(person, "test", "called" if ok else "refused")
    if ok:
        was_raised = bool(current and current.get("raised"))
        _write_health(root, person, status="ready", tries=0, raised=False, now=now)
        return "X is answering again." if was_raised else None
    tries = (current["tries"] if current and current["status"] == "down" else 0) + 1
    if tries >= 2:
        _write_health(root, person, status="down", tries=tries, raised=True, now=now)
        return "X is not answering. I tried again once the room was quiet, and it still did not."
    _write_health(root, person, status="down", tries=tries, raised=False, now=now)
    return None


def signed_in_people(roots: list[Path]) -> list[tuple[str, Path]]:
    found: list[tuple[str, Path]] = []
    for root in roots:
        path = signin_path(root)
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeError):
            continue
        if not isinstance(data, dict) or set(data) != _SIGNIN_KEYS:
            continue
        person = str(data.get("person") or "")
        if account_for(person, root):
            found.append((person, root))
    return found


def tend_outgoing(
    *,
    roots: list[Path] | None = None,
    quiet: bool | None = None,
    probe=None,
    now: datetime | None = None,
) -> str | None:
    """River's check. The sentence is for the main channel, and only when it changed."""
    if roots is None:
        bound = shell()
        roots = [Path(path) for path in bound.runtime_dirs()] if bound else []
    if quiet is None:
        try:
            from scripts.deploy_guard import assess

            quiet = bool(assess().get("quiet"))
        except Exception:
            quiet = False
    notes = []
    for person, root in signed_in_people(roots):
        note = health_step(person, root, quiet=bool(quiet), probe=probe, now=now)
        if note:
            notes.append(note)
    return "\n".join(notes) or None


def connection_status(person: str, root: Path | None) -> str:
    if not account_for(person, root):
        return "unsigned"
    if paused_for(person, root):
        return "paused"
    return "ready"


def service_state(person: str, root: Path | None) -> tuple[str, str | None]:
    """X's state in one word, and when River last checked it. For the `!mcp` card.

    One of unsigned, paused, unchecked, down, ready. The check time is None unless a check exists.
    """
    if not account_for(person, root):
        return "unsigned", None
    if paused_for(person, root):
        return "paused", None
    health = health_for(person, root)
    if not health:
        return "unchecked", None
    if health["status"] == "down":
        return "down", health["checked"]
    return "ready", health["checked"]


def private_action(
    person: str,
    root: Path,
    action: str,
    *,
    clear=None,
    probe=None,
) -> str:
    """The private reply for one press. A remove asks once. Nothing here is a post."""
    action = (action or "").strip()
    if action == "remove":
        if not account_for(person, root):
            return connection_list(person, root)
        return "Remove X? The sign-in goes."
    if action == "remove-no":
        return connection_list(person, root)
    if action == "remove-yes":
        return remove_signin(root, person, clear=clear)
    if action == "pause":
        if not account_for(person, root):
            return connection_list(person, root)
        set_paused(root, person, not paused_for(person, root))
        return connection_list(person, root)
    if action == "test":
        return test_connection(person, root, probe)
    return connection_list(person, root)


def test_connection(person: str, root: Path, probe) -> str:
    """Asks whether the login answers. The reply is that fact, never what came back."""
    account = account_for(person, root)
    if not account:
        return "You have not signed in to X."
    if paused_for(person, root):
        Door(root, RefusingServer())._audit(person, "test", "paused")
        return "X is paused."
    try:
        if probe is None:
            from outgoing_x import XServer

            XServer(account).probe()
        else:
            probe(account)
    except Exception:
        Door(root, RefusingServer())._audit(person, "test", "refused")
        return "X did not respond."
    Door(root, RefusingServer())._audit(person, "test", "called")
    return "X responded."


def remove_signin(root: Path, person: str, *, clear=None) -> str:
    """Drop this person's sign-in record, then their login on the machine."""
    account = account_for(person, root)
    path = signin_path(root)
    if account and path.is_file():
        path.unlink()
    set_paused(root, person, False)
    if not account:
        return "You have not signed in to X."
    cleared = True
    if clear is not None:
        try:
            cleared = bool(clear(account))
        except Exception:
            cleared = False
    Door(root, RefusingServer())._audit(person, "remove", "called" if cleared else "refused")
    if cleared:
        return "X is removed."
    return "The sign-in record is gone. The login on this machine could not be cleared."


def account_for(person: str, root: Path | None) -> str | None:
    """The account name, or nothing. A file that holds any other field is refused."""
    if not person or root is None:
        return None
    path = signin_path(root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    if not isinstance(data, dict) or set(data) != _SIGNIN_KEYS:
        return None
    if data.get("person") != person:
        return None
    account = str(data.get("account") or "").strip()
    if not _ACCOUNT.match(account):
        return None
    return account


def _asker() -> str:
    bound = shell()
    if bound is None:
        return ""
    try:
        return bound.actor_key() or ""
    except Exception:
        return ""


def _runtime_root() -> Path | None:
    bound = shell()
    if bound is None:
        return None
    try:
        raw = bound.runtime_dir()
    except Exception:
        return None
    return Path(raw) if raw else None


def _object_body(payload: object) -> str:
    """The server's object. Links that leave X are named beside it and not fetched."""
    from outgoing_x import offers_for

    if not isinstance(payload, dict):
        payload = {}
    offers = offers_for(payload)
    shown: object = {"result": payload, "offers": offers} if offers else payload
    return json.dumps(shown, ensure_ascii=False)


def live_call(
    arguments: dict | None = None,
    *,
    tool: str | None = None,
    person: str | None = None,
    root: Path | None = None,
    server: object | None = None,
) -> str:
    """The tool path. No sign-in for this asker does not call a server."""
    arguments = arguments if isinstance(arguments, dict) else {}
    operation = (tool or str(arguments.get("operation") or "open")).strip()
    if person is None:
        person = _asker()
    person = person or ""
    if root is None and person:
        root = _runtime_root()
    account = account_for(person, root)
    header = f"[{SERVICE} — {person}'s]" if person else f"[{SERVICE} — unsigned]"
    if tool and _writable(tool):
        door = Door(root, RefusingServer())
        if person:
            door.sign_in(person, secrets.token_hex(16))
        door._audit(person, tool, "refused")
        return door._channel(person, header, "Refused.")
    if not account:
        return Door(None, RefusingServer()).call(
            person=person,
            room="craft",
            operation=operation if not tool else "open",
            arguments=arguments,
        )
    if paused_for(person, root):
        door = Door(root, RefusingServer())
        door._audit(person, operation or "open", "paused")
        return door._channel(person, header, "X is paused.")
    if server is None:
        from outgoing_x import XServer

        server = XServer(account)
    door = Door(root, server)
    # A marker so the channel redacts it if it ever appears. Not the X secret.
    door.sign_in(person, secrets.token_hex(16))
    try:
        if tool:
            payload = server.call_named(tool, arguments)  # type: ignore[attr-defined]
            _keep_catalog(server, root)
            door._audit(person, tool, "called")
            return door._channel(person, header, _object_body(payload))
        if operation == "open" and hasattr(server, "open_payload"):
            payload = server.open_payload(str(arguments.get("link") or ""))  # type: ignore[attr-defined]
            _keep_catalog(server, root)
            door._audit(person, "open", "called")
            return door._channel(person, header, _object_body(payload))
        return door.call(person=person, room="craft", operation=operation, arguments=arguments)
    except Exception:
        door._audit(person, operation or "open", "refused")
        return door._channel(person, header, "X could not be read.")
