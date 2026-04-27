"""turtleOS Thread Registry — persistent, queryable thread state.

Phase 1 Eyes: Turtle knows its river.
Tracks all eddies (threads) with lifecycle state, enabling stale detection,
harvest tracking, and river stewardship.
"""

import os
from datetime import datetime, timezone
from pathlib import Path

import yaml

from mage import get_runtime_dir


def _registry_path() -> Path:
    return Path(get_runtime_dir()) / "thread-state" / "registry.yaml"


def load_registry() -> dict:
    path = _registry_path()
    if not path.exists():
        return {"threads": {}, "last_backfill": None, "last_updated": None}
    try:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        if "threads" not in data:
            data["threads"] = {}
        return data
    except Exception as e:
        print(f"Registry load failed: {e}")
        return {"threads": {}, "last_backfill": None, "last_updated": None}


def save_registry(registry: dict):
    path = _registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    registry["last_updated"] = datetime.now(timezone.utc).isoformat()
    try:
        with open(path, "w") as f:
            yaml.dump(registry, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    except Exception as e:
        print(f"Registry save failed: {e}")


def register_thread(thread_id: int, name: str, parent_channel: str = "",
                    model: str = "default", attunement: str = "semi",
                    context_type: str | None = None, eddy_type: str = "fast",
                    created: str | None = None, message_count: int = 0):
    registry = load_registry()
    tid = str(thread_id)
    now = datetime.now(timezone.utc).isoformat()

    if tid not in registry["threads"]:
        registry["threads"][tid] = {
            "name": name,
            "parent_channel": parent_channel,
            "created": created or now,
            "last_activity": now,
            "message_count": message_count,
            "model": model,
            "attunement": attunement,
            "context_type": context_type,
            "eddy_type": eddy_type,
            "harvest_status": "pending",
        }
    else:
        entry = registry["threads"][tid]
        entry["name"] = name
        if message_count > entry.get("message_count", 0):
            entry["message_count"] = message_count

    save_registry(registry)
    return registry["threads"][tid]


def update_thread_activity(thread_id: int, increment_messages: bool = True):
    registry = load_registry()
    tid = str(thread_id)
    if tid not in registry["threads"]:
        return
    entry = registry["threads"][tid]
    entry["last_activity"] = datetime.now(timezone.utc).isoformat()
    if increment_messages:
        entry["message_count"] = entry.get("message_count", 0) + 1
    save_registry(registry)


def update_thread_name(thread_id: int, new_name: str):
    registry = load_registry()
    tid = str(thread_id)
    if tid in registry["threads"]:
        registry["threads"][tid]["name"] = new_name
        save_registry(registry)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _age_label(dt: datetime | None, now: datetime | None = None) -> str:
    if not dt:
        return "unknown"
    now = now or datetime.now(timezone.utc)
    seconds = max(0, int((now - dt).total_seconds()))
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"


def thread_activity_status(info: dict, now: datetime | None = None) -> str:
    if info.get("harvest_status") == "dissolved":
        return "dissolved"
    now = now or datetime.now(timezone.utc)
    last_dt = _parse_dt(info.get("last_activity"))
    if not last_dt:
        return "unknown"
    age_days = (now - last_dt).total_seconds() / 86400
    if age_days < 2:
        return "active"
    if age_days < 7:
        return "quiet"
    return "stale"


def format_thread_awareness_line(thread_id: str, info: dict, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    created = _age_label(_parse_dt(info.get("created")), now)
    last = _age_label(_parse_dt(info.get("last_activity")), now)
    status = thread_activity_status(info, now)
    model = info.get("model") or "default"
    attunement = info.get("attunement") or "semi"
    eddy = info.get("eddy_type") or "fast"
    messages = info.get("message_count", 0)
    return (
        f"- **{info.get('name', 'unknown')}** — `{model}` / `{attunement}` · "
        f"`{eddy}` · status:{status} · created:{created} ago · last:{last} ago · "
        f"messages:{messages} · id:{thread_id}"
    )


def get_thread_awareness(thread_id: int | str) -> str:
    registry = load_registry()
    info = registry.get("threads", {}).get(str(thread_id))
    if not info:
        return "not in registry yet"
    return format_thread_awareness_line(str(thread_id), info).lstrip("- ")


def _topic_tokens(text: str) -> set[str]:
    import re
    stop = {"the", "and", "for", "with", "from", "this", "that", "agent", "thread"}
    return {
        tok
        for tok in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(tok) >= 3 and tok not in stop
    }


def get_related_thread_awareness(thread_name: str, current_thread_id: int | str | None = None, limit: int = 5) -> str:
    """Return related registry entries for the current topic, including stale predecessors."""
    tokens = _topic_tokens(thread_name)
    if not tokens:
        return ""

    registry = load_registry()
    now = datetime.now(timezone.utc)
    related = []
    current = str(current_thread_id) if current_thread_id is not None else None
    for tid, info in registry.get("threads", {}).items():
        if tid == current or info.get("harvest_status") == "dissolved":
            continue
        other_tokens = _topic_tokens(info.get("name", ""))
        score = len(tokens & other_tokens)
        if score == 0:
            continue
        status_priority = {"active": 0, "quiet": 1, "stale": 2, "unknown": 3}.get(thread_activity_status(info, now), 4)
        last = _parse_dt(info.get("last_activity")) or datetime.fromtimestamp(0, tz=timezone.utc)
        related.append((score, -status_priority, last.timestamp(), tid, info))

    if not related:
        return ""

    related.sort(reverse=True)
    lines = ["**Related registered threads:**"]
    for _, _, _, tid, info in related[:limit]:
        lines.append(format_thread_awareness_line(tid, info, now))
    return "\n".join(lines)


def build_live_thread_summary(limit: int = 12) -> str:
    """Registry-backed thread summary for prompt injection."""
    registry = load_registry()
    threads = registry.get("threads", {})
    if not threads:
        return "**Active threads:** none in registry"

    now = datetime.now(timezone.utc)
    visible = []
    for tid, info in threads.items():
        if info.get("harvest_status") == "dissolved":
            continue
        status = thread_activity_status(info, now)
        priority = {"active": 0, "quiet": 1, "stale": 2, "unknown": 3}.get(status, 4)
        last = _parse_dt(info.get("last_activity")) or datetime.fromtimestamp(0, tz=timezone.utc)
        visible.append((priority, -last.timestamp(), tid, info))

    if not visible:
        return "**Active threads:** none (all dissolved)"

    visible.sort()
    lines = ["**Discord thread state (live registry):**"]
    for _, _, tid, info in visible[:limit]:
        lines.append(format_thread_awareness_line(tid, info, now))
    if len(visible) > limit:
        lines.append(f"- ... {len(visible) - limit} more registered threads")
    lines.append("")
    lines.append("Before recommending a new thread, check this list for related active/quiet threads and offer continuation when appropriate.")
    return "\n".join(lines)


def mark_harvested(thread_id: int):
    registry = load_registry()
    tid = str(thread_id)
    if tid in registry["threads"]:
        registry["threads"][tid]["harvest_status"] = "harvested"
        save_registry(registry)


def mark_dissolved(thread_id: int):
    registry = load_registry()
    tid = str(thread_id)
    if tid in registry["threads"]:
        registry["threads"][tid]["harvest_status"] = "dissolved"
        save_registry(registry)


def remove_thread(thread_id: int):
    registry = load_registry()
    tid = str(thread_id)
    if tid in registry["threads"]:
        del registry["threads"][tid]
        save_registry(registry)


def get_stale_threads(days: int = 7) -> list[dict]:
    registry = load_registry()
    stale = []
    now = datetime.now(timezone.utc)

    for tid, info in registry["threads"].items():
        if info.get("harvest_status") == "dissolved":
            continue
        last = info.get("last_activity")
        if not last:
            continue
        try:
            last_dt = datetime.fromisoformat(last)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            age_days = (now - last_dt).total_seconds() / 86400
            if age_days >= days:
                stale.append({
                    "id": tid,
                    "name": info.get("name", "unknown"),
                    "last_activity": last,
                    "age_days": round(age_days, 1),
                    "harvest_status": info.get("harvest_status", "pending"),
                    "message_count": info.get("message_count", 0),
                })
        except (ValueError, TypeError):
            continue

    return sorted(stale, key=lambda x: x["age_days"], reverse=True)


def get_registry_summary() -> str:
    registry = load_registry()
    threads = registry.get("threads", {})
    if not threads:
        return "No threads in registry."

    total = len(threads)
    now = datetime.now(timezone.utc)
    active_7d = 0
    stale_7d = 0
    unharvested = 0
    dissolved = 0

    for info in threads.values():
        if info.get("harvest_status") == "dissolved":
            dissolved += 1
            continue
        last = info.get("last_activity")
        if last:
            try:
                last_dt = datetime.fromisoformat(last)
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                age_days = (now - last_dt).total_seconds() / 86400
                if age_days < 7:
                    active_7d += 1
                else:
                    stale_7d += 1
            except (ValueError, TypeError):
                pass
        if info.get("harvest_status") == "pending":
            unharvested += 1

    return (
        f"**Eddies:** {total} total · "
        f"**Active (7d):** {active_7d} · "
        f"**Quiet (>7d):** {stale_7d} · "
        f"**Unharvested:** {unharvested}"
    )


async def backfill_from_discord(guild, parent_channels: list[int] | None = None):
    """One-time scan of all active Discord threads to populate the registry."""
    registry = load_registry()
    threads = await guild.active_threads()
    added = 0
    updated = 0

    for t in threads:
        if parent_channels and t.parent_id not in parent_channels:
            continue

        tid = str(t.id)
        parent_name = t.parent.name if t.parent else "unknown"
        created = t.created_at.isoformat() if t.created_at else None
        msg_count = getattr(t, "message_count", 0) or 0

        if tid not in registry["threads"]:
            registry["threads"][tid] = {
                "name": t.name,
                "parent_channel": parent_name,
                "created": created,
                "last_activity": (t.archive_timestamp or t.created_at or datetime.now(timezone.utc)).isoformat(),
                "message_count": msg_count,
                "model": "default",
                "attunement": "semi",
                "context_type": None,
                "eddy_type": "fast",
                "harvest_status": "pending",
            }
            added += 1
        else:
            entry = registry["threads"][tid]
            entry["name"] = t.name
            if msg_count > entry.get("message_count", 0):
                entry["message_count"] = msg_count
            updated += 1

    registry["last_backfill"] = datetime.now(timezone.utc).isoformat()
    save_registry(registry)
    return added, updated
