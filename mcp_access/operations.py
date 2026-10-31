"""Operations and profiles. A profile grants authority; the surface follows it."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Operation:
    name: str
    content: bool
    write: bool = False


OPERATIONS: dict[str, Operation] = {
    op.name: op
    for op in (
        Operation("capabilities", content=False),
        Operation("brief", content=True),
        Operation("list_notes", content=True),
        Operation("read_note", content=True),
        Operation("read_health_picture", content=True),
        Operation("search", content=True),
        Operation("list_documents", content=True),
        Operation("read_document", content=True),
        Operation("host_status", content=False),
        Operation("workshop_read", content=True),
        Operation("workshop_search", content=True),
        # The forge spirit's one write. It opens or continues a magic session.
        # It does not edit the workshop, and a reader grant never receives it.
        Operation("spirit_speak", content=False, write=True),
    )
}

PROFILES: dict[str, tuple[str, ...]] = {
    "reader": (
        "capabilities",
        "brief",
        "list_notes",
        "read_note",
        "read_health_picture",
        "search",
        "list_documents",
        "read_document",
    ),
    "operator-health": ("capabilities", "host_status"),
    # The owner's workshop (their practice repository), read at its head. A
    # separate profile on purpose: `reader` grants, old and new, never reach it.
    "workshop-reader": ("capabilities", "brief", "workshop_read", "workshop_search"),
    # One connection for the owner: rooms, health and the workshop. Born with
    # nothing open; the card in the home channel opens each thing. `reader` and
    # `workshop-reader` stay, so a grant made for one family does not widen.
    "house": (
        "capabilities",
        "brief",
        "list_notes",
        "read_note",
        "read_health_picture",
        "search",
        "list_documents",
        "read_document",
        "workshop_read",
        "workshop_search",
        "spirit_speak",
    ),
}

# What each content operation makes reachable. A source of a kind the grant has
# no operation for is not shown to it at all (Session.__post_init__).
ROOM_OPERATIONS = frozenset(
    {"list_notes", "read_note", "read_health_picture", "search", "list_documents", "read_document"}
)
WORKSHOP_OPERATIONS = frozenset({"workshop_read", "workshop_search"})


def snapshot_for(profile: str) -> list[str]:
    if profile not in PROFILES:
        raise ValueError(f"unknown profile: {profile}")
    return [name for name in PROFILES[profile] if name in OPERATIONS]
