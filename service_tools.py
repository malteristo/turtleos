"""The tools of the services a person signed in to, offered room by room.

One place decides whether a tool is offered or runs: `room_connections.level`
for the room the turn is in, and a sign-in for the person who is asking. A tool
here reads. No tool here writes, and none sends mail; a write is a button, built
elsewhere. A call is checked again when it runs, so a tool that was listed in
another room cannot be called in this one.

Each service is a row in `SERVICE_TOOLS`. The room's ceiling for that service
is the row of the same name in `room_connections.SERVICES`, and
`tests/test_service_tools.py` fails when the two lists disagree.
See docs/design/channel-connections.md.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import google_connection as gc
import room_connections as rc

CALENDAR_API = "https://www.googleapis.com/calendar/v3"
_DESCRIPTION_MAX = 600
_EVENTS_MAX = 25
AUDIT_NAME = "outgoing_audit.jsonl"


def _get_json(url: str, token: str, params: dict | None = None) -> dict:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url)
    request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 - fixed https host
        return json.loads(response.read().decode("utf-8"))


# Planted by tests. Production reads Google.
_fetch: Callable[[str, str, dict | None], dict] = _get_json


def install_fetch(fetch: Callable[[str, str, dict | None], dict] | None) -> None:
    global _fetch
    _fetch = fetch or _get_json


def _spec(name: str, description: str, properties: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required or []},
        },
    }


CALENDAR_TOOLS = [
    _spec(
        "calendar_list_calendars",
        "List the calendars on the asker's own Google account, with the id of each.",
        {},
    ),
    _spec(
        "calendar_list_events",
        "List events on the asker's own Google calendar, soonest first. Give a window (RFC3339 times) "
        "when the question has one. The primary calendar is the default. Nothing is written.",
        {
            "calendar_id": {"type": "string", "description": "A calendar id from calendar_list_calendars. Default primary."},
            "time_min": {"type": "string", "description": "Start of the window, RFC3339, e.g. 2026-10-15T00:00:00+02:00."},
            "time_max": {"type": "string", "description": "End of the window, RFC3339."},
            "query": {"type": "string", "description": "Words to match in title, description, location or attendees."},
        },
    ),
    _spec(
        "calendar_get_event",
        "Read one event in full, by the id calendar_list_events gave.",
        {
            "event_id": {"type": "string"},
            "calendar_id": {"type": "string", "description": "Default primary."},
        },
        ["event_id"],
    ),
]

# service id -> (the tools it offers at `look`, the sign-in service name it needs)
SERVICE_TOOLS: dict[str, tuple[list[dict], str]] = {
    "calendar": (CALENDAR_TOOLS, "calendar"),
}


def _tool_name(spec: dict) -> str:
    return str((spec.get("function") or {}).get("name") or "")


def _owner(name: str) -> str | None:
    for service, (tools, _needs) in SERVICE_TOOLS.items():
        if any(_tool_name(t) == name for t in tools):
            return service
    return None


def handles(name: str) -> bool:
    return _owner(name) is not None


def _day(value: object) -> str:
    text = str(value or "")
    if (
        len(text) >= 10
        and text[4:5] == "-"
        and text[7:8] == "-"
        and text[:4].isdigit()
        and text[5:7].isdigit()
        and text[8:10].isdigit()
    ):
        return f"{text[8:10]}.{text[5:7]}"
    return ""


def _events_line(args: dict) -> str:
    """The day and the words he asked for. The event itself stays in the tool result."""
    which = " ".join(str(args.get("calendar_id") or "").split())
    query = " ".join(str(args.get("query") or "").split())
    if len(query) > 60:
        query = query[:59].rstrip() + "…"
    start, end = _day(args.get("time_min")), _day(args.get("time_max"))
    if start and end:
        window = f"{start}–{end}"
    elif start:
        window = f"from {start}"
    elif end:
        window = f"until {end}"
    else:
        window = ""
    line = "read the calendar"
    if which and which != "primary":
        shown = which if len(which) <= 40 else which[:39].rstrip() + "…"
        line += f" `{shown}`"
    if window:
        line += f" {window}"
    if query:
        line += f' for "{query}"'
    return line


def channel_line(name: str, args: dict | None = None) -> str | None:
    """What the channel says about one service call: the act and the object, never the result.

    A tool this module owns and does not name gets a line with no result either,
    so a new connection cannot reach the trace's result preview by being unnamed.
    """
    if not handles(name):
        return None
    args = args or {}
    if name == "calendar_list_calendars":
        return "read the calendars"
    if name == "calendar_list_events":
        return _events_line(args)
    if name == "calendar_get_event":
        return "read one event"
    return "read a connection"


def _context() -> tuple[dict, object, str, Path | None]:
    """The registry, the room, the asker and their runtime root, from the bound shell."""
    from outgoing_connections import _asker, _runtime_root, shell

    bound = shell()
    if bound is None:
        return {}, None, "", None
    try:
        registry = bound.registry()
    except Exception:
        registry = {}
    channel = None
    if bound.channel_id is not None:
        try:
            channel = bound.channel_id()
        except Exception:
            channel = None
    return registry, channel, _asker(), _runtime_root()


def _answers(service: str) -> bool:
    registry, channel, person, root = _context()
    if channel is None or not person or root is None:
        return False
    if rc.level(service, registry=registry, channel_id=channel, person=person, root=root) == "off":
        return False
    info = gc.signed_in(person, root)
    return bool(info and SERVICE_TOOLS[service][1] in info["services"])


def tools_offered() -> list[dict]:
    """The tools this room, this asker, may be given. Empty when nothing is switched on."""
    offered: list[dict] = []
    for service, (tools, _needs) in SERVICE_TOOLS.items():
        if _answers(service):
            offered.extend(tools)
    return offered


def _audit(root: Path | None, person: str, service: str, operation: str, decision: str) -> None:
    if root is None:
        return
    path = root / "state" / AUDIT_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "person": person,
            "service": service,
            "operation": operation,
            "decision": decision,
        },
        ensure_ascii=False,
    )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def call(name: str, arguments: dict | None = None, *, http: gc.Http | None = None) -> str:
    """Run one tool. Checked again here, in this room, for this asker."""
    service = _owner(name)
    if service is None:
        return "That tool is not available."
    _registry, _channel, person, root = _context()
    header = f"[{service.title()} — {person}'s]" if person else f"[{service.title()}]"
    if not _answers(service):
        _audit(root, person, service, name, "refused")
        return f"{header}\nNot in this room."
    try:
        token = gc.access_token(person, root, http)
    except gc.NeedsSignin:
        _audit(root, person, service, name, "unsigned")
        return f"{header}\nGoogle needs you to sign in again. Say so, and the person can do it from `!mcp`."
    except gc.SigninError as exc:
        _audit(root, person, service, name, "unavailable")
        return f"{header}\n{exc}"
    try:
        body = _calendar(name, arguments if isinstance(arguments, dict) else {}, token)
    except urllib.error.HTTPError as exc:
        _audit(root, person, service, name, "unavailable")
        return f"{header}\nGoogle answered {exc.code}."
    except Exception:
        _audit(root, person, service, name, "unavailable")
        return f"{header}\nGoogle could not be read."
    _audit(root, person, service, name, "called")
    return f"{header}\n{body}"


def _when(block: dict | None) -> str:
    block = block or {}
    return str(block.get("dateTime") or block.get("date") or "")


def _event_line(event: dict) -> str:
    title = str(event.get("summary") or "(no title)")
    where = str(event.get("location") or "").strip()
    line = f"- {_when(event.get('start'))} → {_when(event.get('end'))}  {title}"
    if where:
        line += f"  @ {where}"
    if event.get("id"):
        line += f"  [id {event['id']}]"
    return line


def _calendar(name: str, args: dict, token: str) -> str:
    if name == "calendar_list_calendars":
        data = _fetch(f"{CALENDAR_API}/users/me/calendarList", token, None)
        rows = [f"- {c.get('summary', '')}  [id {c.get('id', '')}]" for c in data.get("items") or []]
        return "\n".join(rows) or "No calendars."
    calendar = urllib.parse.quote(str(args.get("calendar_id") or "primary"), safe="")
    if name == "calendar_list_events":
        params = {"singleEvents": "true", "orderBy": "startTime", "maxResults": str(_EVENTS_MAX)}
        for ours, theirs in (("time_min", "timeMin"), ("time_max", "timeMax"), ("query", "q")):
            if str(args.get(ours) or "").strip():
                params[theirs] = str(args[ours]).strip()
        data = _fetch(f"{CALENDAR_API}/calendars/{calendar}/events", token, params)
        rows = [_event_line(e) for e in data.get("items") or []]
        return "\n".join(rows) or "Nothing on the calendar in that window."
    if name == "calendar_get_event":
        event_id = urllib.parse.quote(str(args.get("event_id") or ""), safe="")
        if not event_id:
            return "An event needs its id."
        e = _fetch(f"{CALENDAR_API}/calendars/{calendar}/events/{event_id}", token, None)
        text = _event_line(e)
        detail = str(e.get("description") or "").strip()
        if detail:
            text += "\n" + detail[:_DESCRIPTION_MAX]
        return text
    return "That tool is not available."
