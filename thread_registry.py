"""turtleOS Thread Registry — persistent, queryable thread state.

Phase 1 Eyes: Turtle knows its river.
Tracks all eddies (threads) with lifecycle state, enabling stale detection,
harvest tracking, and river stewardship.
"""

import os
from datetime import datetime, timezone
from pathlib import Path

import yaml

from mage import get_pd


def _registry_path() -> Path:
    return Path(get_pd()) / "thread-state" / "registry.yaml"


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
