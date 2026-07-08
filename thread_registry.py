"""turtleOS Thread Registry — persistent, queryable thread state.

Phase 1 Eyes: Turtle knows its river.
Tracks all eddies (threads) with lifecycle state, enabling stale detection,
harvest tracking, and river stewardship.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

from mage import get_runtime_dir

_REGISTRY_CACHE: dict | None = None
_LAST_PERSIST_MONO: float = 0.0
_SAVE_DEBOUNCE_S = 2.0


def _registry_path() -> Path:
    return Path(get_runtime_dir()) / "thread-state" / "registry.yaml"


def _default_registry() -> dict:
    return {"threads": {}, "last_backfill": None, "last_updated": None}


def load_registry() -> dict:
    global _REGISTRY_CACHE
    if _REGISTRY_CACHE is not None:
        return _REGISTRY_CACHE
    path = _registry_path()
    if not path.exists():
        _REGISTRY_CACHE = _default_registry()
        return _REGISTRY_CACHE
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if "threads" not in data:
            data["threads"] = {}
        _REGISTRY_CACHE = data
        return _REGISTRY_CACHE
    except Exception as e:
        print(f"Registry load failed: {e}")
        _REGISTRY_CACHE = _default_registry()
        return _REGISTRY_CACHE


def _persist_registry(registry: dict) -> None:
    path = _registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = yaml.dump(
        registry,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )
    fd, tmp_path = None, None
    try:
        fd, tmp_path = _mkstemp_in(path.parent)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            fd = None
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
        tmp_path = None
    except Exception as e:
        print(f"Registry save failed: {e}")
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        raise
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass


def _mkstemp_in(directory: Path) -> tuple[int, str]:
    import tempfile

    return tempfile.mkstemp(dir=directory, suffix=".tmp")


def save_registry(registry: dict, *, force: bool = False) -> None:
    global _REGISTRY_CACHE, _LAST_PERSIST_MONO
    registry["last_updated"] = datetime.now(timezone.utc).isoformat()
    _REGISTRY_CACHE = registry
    now = time.monotonic()
    if force or (now - _LAST_PERSIST_MONO) >= _SAVE_DEBOUNCE_S:
        try:
            _persist_registry(registry)
            _LAST_PERSIST_MONO = now
        except Exception:
            if not force:
                return
            try:
                _persist_registry(registry)
                _LAST_PERSIST_MONO = time.monotonic()
            except Exception as retry_exc:
                print(f"Registry save retry failed: {retry_exc}")


def flush_registry() -> None:
    """Persist cached registry immediately (debounce flush / shutdown)."""
    global _LAST_PERSIST_MONO
    if _REGISTRY_CACHE is None:
        return
    try:
        _persist_registry(_REGISTRY_CACHE)
        _LAST_PERSIST_MONO = time.monotonic()
    except Exception as e:
        print(f"Registry flush failed: {e}")


def clear_registry_cache_for_tests() -> None:
    global _REGISTRY_CACHE, _LAST_PERSIST_MONO
    _REGISTRY_CACHE = None
    _LAST_PERSIST_MONO = 0.0


def register_thread(thread_id: int, name: str, parent_channel: str = "",
                    model: str = "default", attunement: str = "semi",
                    context_type: str | None = None, eddy_type: str = "fast",
                    created: str | None = None, message_count: int = 0):
    registry = load_registry()
    tid = str(thread_id)
    now = datetime.now(timezone.utc).isoformat()
    is_new = tid not in registry["threads"]

    if is_new:
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

    save_registry(registry, force=is_new)
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
        save_registry(registry, force=True)


def update_thread_context_type(thread_id: int, context_type: str | None) -> None:
    if not context_type:
        return
    registry = load_registry()
    tid = str(thread_id)
    if tid not in registry["threads"]:
        return
    registry["threads"][tid]["context_type"] = context_type
    save_registry(registry)


CONTINUITY_DEFAULT = "default"
CONTINUITY_KEEP = "keep"
CONTINUITY_IGNORE = "ignore"
_VALID_CONTINUITY = {CONTINUITY_DEFAULT, CONTINUITY_KEEP, CONTINUITY_IGNORE}


def get_thread_continuity(thread_id: int | str) -> str:
    registry = load_registry()
    entry = registry.get("threads", {}).get(str(thread_id))
    if not entry:
        return CONTINUITY_DEFAULT
    value = entry.get("continuity", CONTINUITY_DEFAULT)
    return value if value in _VALID_CONTINUITY else CONTINUITY_DEFAULT


def update_thread_continuity(thread_id: int, continuity: str) -> None:
    if continuity not in _VALID_CONTINUITY:
        raise ValueError(f"invalid continuity: {continuity}")
    registry = load_registry()
    tid = str(thread_id)
    if tid not in registry["threads"]:
        register_thread(thread_id, name="unknown")
        registry = load_registry()
    entry = registry["threads"][tid]
    if continuity == CONTINUITY_DEFAULT:
        entry.pop("continuity", None)
    else:
        entry["continuity"] = continuity
    save_registry(registry, force=True)


def is_eddy_cooled(thread_id: int | str) -> bool:
    registry = load_registry()
    entry = registry.get("threads", {}).get(str(thread_id))
    return bool(entry and entry.get("harvest_status") == "cooled")


def mark_cooled(thread_id: int) -> None:
    registry = load_registry()
    tid = str(thread_id)
    if tid not in registry["threads"]:
        return
    entry = registry["threads"][tid]
    entry["harvest_status"] = "cooled"
    entry["auto_archived_at"] = datetime.now(timezone.utc).isoformat()
    save_registry(registry, force=True)


def clear_cooled_status(thread_id: int) -> None:
    """Clear cooled state when a practitioner resumes an auto-archived eddy."""
    registry = load_registry()
    tid = str(thread_id)
    if tid not in registry["threads"]:
        return
    entry = registry["threads"][tid]
    if entry.get("harvest_status") != "cooled":
        return
    entry["harvest_status"] = "pending"
    entry.pop("auto_archived_at", None)
    save_registry(registry, force=True)


def update_thread_locked(thread_id: int, locked: bool) -> None:
    """Sync Discord Lock Thread state into registry."""
    registry = load_registry()
    tid = str(thread_id)
    if tid not in registry["threads"]:
        return
    entry = registry["threads"][tid]
    if locked:
        entry["locked"] = True
        entry["locked_at"] = datetime.now(timezone.utc).isoformat()
    else:
        entry.pop("locked", None)
        entry.pop("locked_at", None)
    save_registry(registry, force=True)


def is_eddy_locked(thread_id: int, *, discord_locked: bool = False) -> bool:
    """True when Discord or registry marks this eddy locked (read-only pause)."""
    if discord_locked:
        return True
    registry = load_registry()
    entry = registry.get("threads", {}).get(str(thread_id))
    return bool(entry and entry.get("locked"))


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
    if info.get("harvest_status") == "cooled":
        return "cooled"
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
    lock_tag = " · 🔒locked" if info.get("locked") else ""
    continuity = info.get("continuity", CONTINUITY_DEFAULT)
    continuity_tag = ""
    if continuity == CONTINUITY_KEEP:
        continuity_tag = " · 📌keep"
    elif continuity == CONTINUITY_IGNORE:
        continuity_tag = " · 🚫ignore"
    cooled_tag = " · 🧊cooled" if status == "cooled" else ""
    return (
        f"- **{info.get('name', 'unknown')}** — `{model}` / `{attunement}` · "
        f"`{eddy}` · status:{status} · created:{created} ago · last:{last} ago · "
        f"messages:{messages}{lock_tag}{continuity_tag}{cooled_tag} · id:{thread_id}"
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
        save_registry(registry, force=True)


def mark_dissolved(thread_id: int):
    registry = load_registry()
    tid = str(thread_id)
    if tid in registry["threads"]:
        registry["threads"][tid]["harvest_status"] = "dissolved"
        save_registry(registry, force=True)


def is_dissolved(thread_id: int | str) -> bool:
    """True when registry marks this eddy as dissolved (closed)."""
    registry = load_registry()
    entry = registry["threads"].get(str(thread_id))
    return bool(entry and entry.get("harvest_status") == "dissolved")


def remove_thread(thread_id: int):
    registry = load_registry()
    tid = str(thread_id)
    if tid in registry["threads"]:
        del registry["threads"][tid]
        save_registry(registry, force=True)


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
            if getattr(t, "locked", False):
                entry["locked"] = True
            elif entry.get("locked"):
                entry.pop("locked", None)
                entry.pop("locked_at", None)
            updated += 1

    registry["last_backfill"] = datetime.now(timezone.utc).isoformat()
    save_registry(registry, force=True)
    return added, updated
