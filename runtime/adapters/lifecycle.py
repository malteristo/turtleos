"""Tier-3 eddy lifecycle adapters — shared pipelines for commands and Gateway events.

Command paths (!dissolve, lifecycle bar, admin space close) and native Discord UI
(archive transition) converge here before calling sessions.dissolve_eddy / light_archive_eddy.
See docs/chapters/design-discord-native-ui-reconciliation.md (S4).
"""

from __future__ import annotations

from typing import Any, Literal

import discord

import mage

EddyCloseSource = Literal["command", "native_ui", "admin", "lifecycle_bar"]

# Policy C: full dissolve when registered + substantive (native close only).
_FULL_DISSOLVE_MESSAGE_THRESHOLD = 2


def _registry_entry(thread_id: int) -> dict | None:
    from thread_registry import load_registry

    return load_registry()["threads"].get(str(thread_id))


def is_eddy_already_dissolved(thread_id: int) -> bool:
    entry = _registry_entry(thread_id)
    return bool(entry and entry.get("harvest_status") == "dissolved")


def _message_count_for_thread(thread_id: int, entry: dict | None, history: list[dict]) -> int:
    registry_count = entry.get("message_count", 0) if entry else 0
    return max(len(history), registry_count)


async def _load_history_for_thread(thread: discord.Thread) -> list[dict]:
    from helpers import load_thread_history, reload_history

    history = reload_history(thread.id)
    if len(history) >= _FULL_DISSOLVE_MESSAGE_THRESHOLD:
        return history
    return await load_thread_history(thread)


def cleanup_eddy_memory(thread_id: int) -> None:
    """Drop in-memory harness state for an eddy (thread delete path)."""
    from helpers import clear_history
    from state import active_sessions, thread_configs, threads_flagged_for_release

    thread_configs.pop(thread_id, None)
    threads_flagged_for_release.pop(thread_id, None)
    clear_history(thread_id)
    active_sessions.pop(thread_id, None)


async def close_eddy(
    thread_id: int,
    history: list[dict] | None,
    *,
    source: EddyCloseSource,
    discord_client,
    parent_channel_id: int | None = None,
):
    """Blessed-command adapter — full dissolve pipeline (not policy C)."""
    if source == "native_ui":
        raise ValueError("native_ui closes use close_eddy_from_archive_transition")

    if is_eddy_already_dissolved(thread_id):
        from sessions import DissolveResult

        thread_name = "eddy"
        jump_url = ""
        if discord_client is not None:
            thread = discord_client.get_channel(thread_id)
            if thread is None:
                try:
                    thread = await discord_client.fetch_channel(thread_id)
                except Exception:
                    thread = None
            if thread is not None and hasattr(thread, "name"):
                thread_name = thread.name
                jump_url = getattr(thread, "jump_url", "") or ""
        entry = _registry_entry(thread_id)
        if entry and entry.get("thread_name"):
            thread_name = entry["thread_name"]
        return DissolveResult(
            thread_name=thread_name,
            jump_url=jump_url,
            already_archived=True,
        )

    from sessions import dissolve_eddy

    return await dissolve_eddy(
        thread_id,
        history,
        discord_client=discord_client,
        native_close=False,
        parent_channel_id=parent_channel_id,
    )


async def close_eddy_from_archive_transition(
    before: discord.Thread,
    after: discord.Thread,
    *,
    discord_client,
) -> dict[str, Any] | None:
    """Native UI adapter — policy C on archive transition."""
    if before.archived or not after.archived:
        return None

    parent_id = after.parent_id or 0
    if not mage.is_registered_parent_channel(parent_id):
        return None

    if is_eddy_already_dissolved(after.id):
        return {"skipped": "already_dissolved", "thread_id": after.id}

    history = await _load_history_for_thread(after)
    entry = _registry_entry(after.id)
    msg_count = _message_count_for_thread(after.id, entry, history)

    if entry and msg_count >= _FULL_DISSOLVE_MESSAGE_THRESHOLD:
        from sessions import dissolve_eddy
        from state import active_sessions
        from helpers import clear_history

        result = await dissolve_eddy(
            after.id,
            history,
            discord_client=discord_client,
            native_close=True,
            parent_channel_id=parent_id,
        )
        if result:
            clear_history(after.id)
            active_sessions.pop(after.id, None)
        return {"full_dissolve": True, "result": result, "thread_id": after.id}

    from sessions import light_archive_eddy

    await light_archive_eddy(
        after.id,
        discord_client=discord_client,
        via_discord_ui=True,
        thread_name=after.name,
        parent_channel_id=parent_id,
    )
    return {"light_archive": True, "thread_id": after.id}


def _is_system_eddy_name(name: str) -> bool:
    from eddy_spawn import SYSTEM_EDDY_NAMES

    normalized = (name or "").strip().lower()
    return normalized in {n.lower() for n in SYSTEM_EDDY_NAMES}


async def open_eddy(
    thread: discord.Thread,
    *,
    discord_client,
    pending: dict | None = None,
) -> dict[str, Any] | None:
    """Post action-first Opened eddy act on parent river."""
    parent_id = thread.parent_id or 0
    if not mage.is_registered_parent_channel(parent_id):
        return None
    if _is_system_eddy_name(thread.name):
        return {"skipped": "system_eddy", "thread_id": thread.id}

    from sessions import post_eddy_opened_feedback

    via_discord_ui = pending is None
    detail = None
    if pending and pending.get("context_type"):
        detail = f"flow `{pending['context_type']}`"

    await post_eddy_opened_feedback(
        parent_id,
        thread_name=thread.name,
        via_discord_ui=via_discord_ui,
        jump_url=getattr(thread, "jump_url", None),
        detail=detail,
    )
    return {"opened_act": True, "thread_id": thread.id, "via_discord_ui": via_discord_ui}


async def reconcile_thread_lock_transition(
    before: discord.Thread,
    after: discord.Thread,
    *,
    discord_client,
) -> dict[str, Any] | None:
    """Native UI lock/unlock → registry sync + parent river act."""
    if before.locked == after.locked:
        return None

    parent_id = after.parent_id or 0
    if not mage.is_registered_parent_channel(parent_id):
        return None

    from thread_registry import update_thread_locked

    update_thread_locked(after.id, after.locked)

    from sessions import post_lifecycle_act

    if after.locked:
        await post_lifecycle_act(
            parent_id,
            action="Locked eddy",
            thread_name=after.name,
            detail="read-only until unlocked",
            via_discord_ui=True,
            jump_url=getattr(after, "jump_url", None) or "",
            emoji="\U0001f512",
        )
    else:
        await post_lifecycle_act(
            parent_id,
            action="Unlocked eddy",
            thread_name=after.name,
            detail=None,
            via_discord_ui=True,
            jump_url=getattr(after, "jump_url", None) or "",
            emoji="\U0001f513",
        )

    return {"locked": after.locked, "thread_id": after.id, "parent_channel_id": parent_id}


async def reconcile_thread_delete(thread: discord.Thread, *, discord_client) -> dict[str, Any]:
    """S2: native thread delete → registry + memory cleanup."""
    parent_id = thread.parent_id or 0
    if not mage.is_registered_parent_channel(parent_id):
        return {"skipped": "unregistered_parent", "thread_id": thread.id}

    entry = _registry_entry(thread.id)
    if not entry:
        cleanup_eddy_memory(thread.id)
        return {"skipped": "not_in_registry", "thread_id": thread.id}

    from helpers import log_activity, reload_history
    from thread_registry import remove_thread

    history_len = len(reload_history(thread.id))
    thread_name = thread.name
    was_dissolved = entry.get("harvest_status") == "dissolved"

    cleanup_eddy_memory(thread.id)
    remove_thread(thread.id)

    detail = f"**{thread_name}** removed in Discord"
    if history_len and not was_dissolved:
        detail += f" ({history_len} cached messages — Close preferred over Delete for essence capture)"
    try:
        parent = discord_client.get_channel(parent_id)
        if parent is None:
            parent = await discord_client.fetch_channel(parent_id)
        await log_activity(f"Deleted eddy: {detail}", "\U0001f5d1\ufe0f", channel=parent)
    except Exception as exc:
        print(f"log_activity for thread delete failed: {exc}")

    return {
        "thread_deleted": True,
        "thread_id": thread.id,
        "parent_channel_id": parent_id,
        "history_len": history_len,
    }
