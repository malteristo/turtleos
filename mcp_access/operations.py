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
        Operation("host_status", content=False),
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
    ),
    "operator-health": ("capabilities", "host_status"),
}


def snapshot_for(profile: str) -> list[str]:
    if profile not in PROFILES:
        raise ValueError(f"unknown profile: {profile}")
    return [name for name in PROFILES[profile] if name in OPERATIONS]
