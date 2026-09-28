"""River's heartbeat — the house chores that keep turtleOS and Discord in step.

River acts on events; events get missed (a bot was down, a rename landed in
the other process, someone edited Discord by hand). The heartbeat is the
second way in: one loop, a list of chores, each on its own interval. Every
run is recorded in ``house/river_heartbeat.json`` so the Turtle bot's health
canary can tell when River stopped beating (``heartbeat_is_fresh``).

This module is the engine and the pure parts, with no house imports;
``river_bot._house_chores`` names the chores and wires them to the house.

Chores that change something only change the registry toward what Discord
already shows, or re-apply access the registry already grants. Anything that
would rename, create or archive a member's channel stays an explicit admin
act; the heartbeat reports it instead, and only when the report changes.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from cloud_fallback import house_dir

HEARTBEAT_FILE = "river_heartbeat.json"
TICK_SECONDS = 30
# A beat older than this means the loop is gone, not slow: the longest
# chore interval is hours, but every tick rewrites the file.
STALE_AFTER_SECONDS = 15 * 60


@dataclass(frozen=True)
class Chore:
    name: str
    every_seconds: int
    run: Callable[[Any], Awaitable[str | None]]
    """Returns a one-line summary of what changed, or None when nothing did."""
    first_after: int = 0
    """Seconds after the loop starts before the first run (for work startup already did)."""


# ── state file ──────────────────────────────────────────────────


def _path():
    return house_dir() / HEARTBEAT_FILE


def read_state() -> dict:
    try:
        data = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_state(state: dict) -> None:
    path = house_dir(create=True) / HEARTBEAT_FILE
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def heartbeat_is_fresh(now: float | None = None) -> bool:
    beat = read_state().get("beat")
    if not isinstance(beat, (int, float)):
        return False
    return ((now or time.time()) - beat) < STALE_AFTER_SECONDS


# ── chores ──────────────────────────────────────────────────────


def record_discord_state(
    registry: dict, live: dict[str, tuple[str, str | None]], homes: set[str]
) -> list[str]:
    """Write Discord's current names and categories into registry rows. Returns what changed.

    ``live`` maps channel id → (name, category name or None) for channels
    Discord still has; ``homes`` are the home-channel ids, whose registry
    ``name`` follows too. A channel missing from ``live`` is left alone; the
    house check reports orphans.
    """
    changed: list[str] = []
    for ch_id, entry in (registry.get("channels") or {}).items():
        if not isinstance(entry, dict) or entry.get("archived") or entry.get("orphaned"):
            continue
        if str(ch_id) not in live:
            continue
        name, category = live[str(ch_id)]
        notes = []
        if entry.get("discord_name") != name:
            entry["discord_name"] = name
            notes.append(f"name `#{name}`")
        if str(ch_id) in homes and entry.get("name") != name:
            entry["name"] = name
        if entry.get("discord_category") != category:
            if category is None:
                entry.pop("discord_category", None)
            else:
                entry["discord_category"] = category
            notes.append(f"category `{category or 'none'}`")
        if notes:
            changed.append(f"`{entry.get('mage', ch_id)}`: " + ", ".join(notes))
    return changed


def live_channels(client) -> dict[str, tuple[str, str | None]]:
    live: dict[str, tuple[str, str | None]] = {}
    for guild in getattr(client, "guilds", []) or []:
        for channel in getattr(guild, "channels", []) or []:
            category = getattr(channel, "category", None)
            live[str(channel.id)] = (channel.name, getattr(category, "name", None))
    return live


def report_if_changed(lines: list[str]) -> str | None:
    """House-check report text when the findings differ from the last one posted, else None."""
    digest = hashlib.sha256("\n".join(sorted(lines)).encode()).hexdigest()[:16]
    state = read_state()
    if state.get("house_check_digest") == digest:
        return None
    state["house_check_digest"] = digest
    _write_state(state)
    if not lines:
        return "House check clear — what was reported before is resolved."
    return "House check —\n" + "\n".join(lines)


# ── the loop ────────────────────────────────────────────────────


async def tick(
    client, chores: list[Chore], *, now: float | None = None, started: float | None = None, report=None
) -> dict:
    """Run every chore that is due; record each run. Returns the state written."""
    now = now or time.time()
    started = started if started is not None else now
    state = read_state()
    state["beat"] = now
    _write_state(state)
    runs = state.setdefault("chores", {})
    for chore in chores:
        last = (runs.get(chore.name) or {}).get("at")
        if chore.first_after and (last is None or float(last) < started):
            if now - started < chore.first_after:
                continue
        elif last is not None and now - float(last) < chore.every_seconds:
            continue
        row: dict[str, Any] = {"at": now}
        try:
            summary = await chore.run(client)
            row["ok"] = True
            if summary:
                row["last_change"] = summary[:500]
                if report is not None:
                    await report(summary)
        except Exception as exc:
            row["ok"] = False
            row["error"] = f"{type(exc).__name__}: {exc}"[:300]
            print(f"River heartbeat chore {chore.name} failed: {row['error']}")
        runs[chore.name] = {**(runs.get(chore.name) or {}), **row}
        state = {**read_state(), "chores": runs}
    state["beat"] = now
    _write_state(state)
    return state


async def run_forever(client, chores: list[Chore], report) -> None:
    started = time.time()
    while True:
        try:
            await tick(client, chores, started=started, report=report)
        except Exception as exc:
            print(f"River heartbeat tick failed: {type(exc).__name__}: {exc}")
        await asyncio.sleep(TICK_SECONDS)
