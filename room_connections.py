"""Which service answers in which room: the house's ceiling and the person's switch.

A service answers in a room only when both agree. The house sets the ceiling for
each kind of room, in this file. The person switches a service on inside that
ceiling, one room at a time, and the choice is a file in their runtime root.
A choice above the ceiling is refused when it is made and ignored when it is
read, so a hand-edited file cannot widen a room.

This module knows no service's tools and no sign-in. It answers one question,
``level``: off, look, or act. The door for a service asks it and decides nothing
itself. See docs/design/channel-connections.md.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

LEVELS = ("off", "look", "act")  # ordered: a higher index is wider
CHOICES_NAME = "connection-rooms.json"

# The channel `type` values in mage_registry.yaml that a ceiling may name.
# `health` and `shared-river` are never in a ceiling: see the test that reads
# every service against every type.
ROOM_TYPES = frozenset({"river", "hosted-river", "craft", "shared-river", "health"})
NEVER_ANSWER_IN = frozenset({"health", "shared-river"})


@dataclass(frozen=True)
class Service:
    id: str
    label: str
    ceiling: Mapping[str, str]  # room type -> widest level the house allows there
    default: Mapping[str, str]  # room type -> level when the person has not chosen


SERVICES: dict[str, Service] = {
    # X answers in craft and reads only. Its writes are not offered (`outgoing_connections._writable`).
    "x": Service(id="x", label="X", ceiling={"craft": "look"}, default={"craft": "look"}),
    # Calendar reads in a person's own home and in craft. On by default only in a home, where
    # a new sign-in is first used; craft is switched on by the person.
    "calendar": Service(
        id="calendar",
        label="Calendar",
        ceiling={"river": "look", "hosted-river": "look", "craft": "look"},
        default={"river": "look", "hosted-river": "look"},
    ),
}


class Forbidden(ValueError):
    """A choice wider than the house allows in that room."""


def _rank(level: str) -> int:
    return LEVELS.index(level) if level in LEVELS else 0


def room_type(registry: dict | None, channel_id) -> str | None:
    """The registry's type for a channel, or None when the channel is not registered."""
    if channel_id is None:
        return None
    entry = ((registry or {}).get("channels") or {}).get(str(channel_id))
    if not isinstance(entry, dict):
        return None
    kind = str(entry.get("type") or "")
    return kind if kind in ROOM_TYPES else None


def owner_of(registry: dict | None, channel_id) -> str | None:
    """Who the registry says the room belongs to. A room with no owner has none."""
    entry = ((registry or {}).get("channels") or {}).get(str(channel_id)) if channel_id is not None else None
    owner = entry.get("mage") if isinstance(entry, dict) else None
    return str(owner) if owner else None


def ceiling(service: Service, room: str | None) -> str:
    if room is None or room in NEVER_ANSWER_IN:
        return "off"
    return service.ceiling.get(room, "off")


def choices_path(root: Path) -> Path:
    return root / "state" / CHOICES_NAME


def _read(root: Path | None) -> dict:
    if root is None:
        return {}
    path = choices_path(root)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {}
    return data if isinstance(data, dict) else {}


def chosen(root: Path | None, person: str, service_id: str, channel_id) -> str | None:
    """The person's own choice for one room, or None when they have not made one."""
    if not person or channel_id is None:
        return None
    person_rows = _read(root).get(person)
    if not isinstance(person_rows, dict):
        return None
    rooms = person_rows.get(service_id)
    if not isinstance(rooms, dict):
        return None
    value = rooms.get(str(channel_id))
    return value if value in LEVELS else None


def level(
    service_id: str,
    *,
    registry: dict | None,
    channel_id,
    person: str,
    root: Path | None,
) -> str:
    """off, look or act: the narrower of the house's ceiling and the person's choice."""
    service = SERVICES.get(service_id)
    if service is None:
        return "off"
    room = room_type(registry, channel_id)
    top = ceiling(service, room)
    if top == "off":
        return "off"
    # A sign-in is the person's own. Asked in someone else's room, it is not used there:
    # that room's owner would be reading the answer.
    if owner_of(registry, channel_id) != person:
        return "off"
    pick = chosen(root, person, service_id, channel_id)
    if pick is None:
        pick = service.default.get(room or "", "off")
    return LEVELS[min(_rank(top), _rank(pick))]


def choose(
    root: Path,
    person: str,
    service_id: str,
    channel_id,
    wanted: str,
    *,
    registry: dict | None,
) -> str:
    """Record the person's choice. Refuses what the house does not allow in that room."""
    service = SERVICES.get(service_id)
    if service is None:
        raise Forbidden("That service is not one this house offers.")
    if wanted not in LEVELS:
        raise ValueError("A room is off, look, or act.")
    if not (person or "").strip() or channel_id is None:
        raise ValueError("A choice needs a person and a room.")
    top = ceiling(service, room_type(registry, channel_id))
    if _rank(wanted) > _rank(top) or owner_of(registry, channel_id) != person:
        raise Forbidden("This room does not take that.")
    data = _read(root)
    rows = data.setdefault(person, {}).setdefault(service_id, {})
    rows[str(channel_id)] = wanted
    path = choices_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)
    return wanted


def rooms_for(service_id: str, person: str, registry: dict | None) -> list[tuple[str, str]]:
    """The person's own rooms where the house lets this service answer at all, as (id, name).

    A shared room is never the person's own here, whatever the registry's owner field says:
    its ceiling is off, so it is not listed."""
    service = SERVICES.get(service_id)
    if service is None or not person:
        return []
    rooms: list[tuple[str, str]] = []
    for channel_id, entry in ((registry or {}).get("channels") or {}).items():
        if not isinstance(entry, dict) or entry.get("mage") != person:
            continue
        if ceiling(service, room_type(registry, channel_id)) == "off":
            continue
        rooms.append((str(channel_id), str(entry.get("discord_name") or entry.get("name") or channel_id)))
    return sorted(rooms, key=lambda row: row[1])
