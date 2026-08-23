"""Read-only survey of registered channels and eddies.

Wraps ``mage.get_registry`` and ``thread_registry.load_registry``. Does not
read the alive layer. Per-channel last-activity is not on the mage registry, so
``include_quiet`` is accepted and ignored — quietness is an eddy property
(``survey_eddies``), not a channel one. That is decided, not deferred: joining
on Discord channel name would guess, and the thread registry does not store
parent channel ids.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

ACTIVE_WITHIN_DAYS = 7.0


def survey_space(
    registry: dict[str, Any] | None = None,
    *,
    include_quiet: bool = False,
) -> list[dict[str, Any]]:
    """One row per registered channel. Empty only when the registry is empty.

    Callers that already import ``mage`` pass ``get_registry()``. This module
    does not import ``mage`` — that hub does not need another edge.
    """
    del include_quiet  # see module docstring
    registry = registry or {}
    channels = registry.get("channels") or {}
    spaces = registry.get("spaces") or {}
    rows: list[dict[str, Any]] = []
    for channel_id, entry in channels.items():
        info = entry if isinstance(entry, dict) else {}
        mage_key = info.get("mage")
        member_count = _member_count(mage_key, registry, spaces)
        rows.append(
            {
                "channel_id": str(channel_id),
                "type": info.get("type") or "",
                "attunement": info.get("attunement") or "",
                "mage": mage_key or "",
                "description": info.get("description") or "",
                "member_count": member_count,
            }
        )
    return rows


def survey_eddies(
    *,
    channel_id: str | None = None,
    status: str = "all",
) -> list[dict[str, Any]]:
    """One row per known eddy. Empty only when the thread registry is empty."""
    from thread_registry import load_registry

    threads = (load_registry() or {}).get("threads") or {}
    now = datetime.now(timezone.utc)
    wanted = (status or "all").strip().lower()
    needle = (channel_id or "").strip()
    rows: list[dict[str, Any]] = []
    for tid, info in threads.items():
        entry = info if isinstance(info, dict) else {}
        parent = str(entry.get("parent_channel") or "")
        if needle and needle not in (tid, parent):
            continue
        row_status = _eddy_status(entry, now)
        if wanted != "all" and row_status != wanted:
            continue
        age = _age_days(entry.get("last_activity"), now)
        rows.append(
            {
                "id": str(tid),
                "name": entry.get("name") or "",
                "parent_channel": parent,
                "status": row_status,
                "age_days": age,
                "message_count": int(entry.get("message_count") or 0),
                "last_activity": entry.get("last_activity") or "",
            }
        )
    return rows


def _member_count(mage_key: Any, registry: dict, spaces: dict) -> int:
    if not mage_key:
        return 0
    key = str(mage_key)
    space = spaces.get(key)
    if isinstance(space, dict):
        members = space.get("members") or []
        return len(members) if isinstance(members, list) else 0
    mages = registry.get("mages") or {}
    if key in mages:
        return 1
    return 0


def _age_days(last: Any, now: datetime) -> float | None:
    if not last:
        return None
    try:
        stamp = datetime.fromisoformat(str(last))
    except (TypeError, ValueError):
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return round((now - stamp).total_seconds() / 86400, 1)


def _eddy_status(entry: dict[str, Any], now: datetime) -> str:
    harvest = str(entry.get("harvest_status") or "")
    if harvest in ("dissolved", "cooled"):
        return "cooled"
    age = _age_days(entry.get("last_activity"), now)
    if age is None:
        return "quiet"
    if age < ACTIVE_WITHIN_DAYS:
        return "active"
    return "quiet"
