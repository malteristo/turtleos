"""Discord Gateway → turtleOS state reconciliation (Tier 2/3).

Event adapters keep native UI actions consistent with blessed-command pipelines.
See docs/chapters/design-discord-native-ui-reconciliation.md.
"""

from __future__ import annotations

from typing import Any

import discord

from mage import is_registered_parent_channel

# Minimum messages for full dissolve on native close (policy C).
_FULL_DISSOLVE_MESSAGE_THRESHOLD = 2


def _registry_entry(thread_id: int) -> dict | None:
    from thread_registry import load_registry

    return load_registry()["threads"].get(str(thread_id))


def _message_count_for_thread(thread_id: int, entry: dict | None, history: list[dict]) -> int:
    registry_count = entry.get("message_count", 0) if entry else 0
    return max(len(history), registry_count)


async def _load_history_for_thread(thread: discord.Thread) -> list[dict]:
    from helpers import load_thread_history, reload_history

    history = reload_history(thread.id)
    if len(history) >= _FULL_DISSOLVE_MESSAGE_THRESHOLD:
        return history
    return await load_thread_history(thread)


async def handle_thread_archive_transition(
    before: discord.Thread,
    after: discord.Thread,
    *,
    discord_client,
) -> dict[str, Any] | None:
    """Policy C: full dissolve for registered threads with substance; else light archive."""
    if before.archived or not after.archived:
        return None

    parent_id = after.parent_id or 0
    if not is_registered_parent_channel(parent_id):
        return None

    entry = _registry_entry(after.id)
    if entry and entry.get("harvest_status") == "dissolved":
        return {"skipped": "already_dissolved", "thread_id": after.id}

    history = await _load_history_for_thread(after)
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


async def handle_thread_update(before: discord.Thread, after: discord.Thread, *, discord_client) -> None:
    """Rename sync + lifecycle transitions from native Discord UI."""
    parent_id = after.parent_id or 0
    if not is_registered_parent_channel(parent_id):
        return

    if before.name != after.name:
        from thread_registry import update_thread_name

        try:
            update_thread_name(after.id, after.name)
            print(f"Thread renamed: {before.name} -> {after.name}")
        except Exception as exc:
            print(f"Thread rename registry update failed: {exc}")

    if not before.archived and after.archived:
        try:
            outcome = await handle_thread_archive_transition(
                before, after, discord_client=discord_client
            )
            if outcome and not outcome.get("skipped"):
                kind = "full dissolve" if outcome.get("full_dissolve") else "light archive"
                print(f"Native thread close reconciled ({kind}): {after.name} ({after.id})")
        except Exception as exc:
            print(f"Native thread archive reconcile failed for {after.id}: {exc}")

    if not before.locked and after.locked:
        print(f"Thread locked via Discord UI: {after.name} ({after.id})")


def _cleanup_eddy_memory(thread_id: int) -> None:
    """Drop in-memory harness state for an eddy (thread delete path)."""
    from helpers import clear_history
    from state import active_sessions, thread_configs, threads_flagged_for_release

    thread_configs.pop(thread_id, None)
    threads_flagged_for_release.pop(thread_id, None)
    clear_history(thread_id)
    active_sessions.pop(thread_id, None)


async def handle_thread_delete(thread: discord.Thread, *, discord_client) -> dict[str, Any]:
    """S2: native thread delete → registry + memory cleanup; activity log on parent."""
    parent_id = thread.parent_id or 0
    if not is_registered_parent_channel(parent_id):
        return {"skipped": "unregistered_parent", "thread_id": thread.id}

    entry = _registry_entry(thread.id)
    if not entry:
        _cleanup_eddy_memory(thread.id)
        return {"skipped": "not_in_registry", "thread_id": thread.id}

    from helpers import log_activity, reload_history
    from thread_registry import remove_thread

    history_len = len(reload_history(thread.id))
    thread_name = thread.name
    was_dissolved = entry.get("harvest_status") == "dissolved"

    _cleanup_eddy_memory(thread.id)
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


async def handle_guild_channel_delete(channel: discord.abc.GuildChannel, *, discord_client) -> dict[str, Any]:
    """S2: native channel/category delete → orphan registry entry + ops notice."""
    from mage import get_registry, reload_mage_registry
    from space_provisioning import mark_channel_orphaned

    ch_id_str = str(channel.id)
    registry = get_registry()
    entry = registry.get("channels", {}).get(ch_id_str)
    if not isinstance(entry, dict):
        return {"skipped": "unregistered_channel", "channel_id": channel.id}

    ch_type = entry.get("type", "unknown")
    mage_key = entry.get("mage", "?")
    ch_name = getattr(channel, "name", ch_id_str)

    if entry.get("orphaned"):
        return {"skipped": "already_orphaned", "channel_id": channel.id}

    mark_channel_orphaned(registry, ch_id_str, reason="discord_deleted")
    reload_mage_registry()

    from helpers import log_activity

    label = f"#{ch_name}" if hasattr(channel, "name") else ch_name
    msg = (
        f"Discord deleted registered channel {label} (`{ch_id_str}`) "
        f"type `{ch_type}` mage `{mage_key}` — registry marked orphaned; workshop kept"
    )
    try:
        await log_activity(msg, "\u26a0\ufe0f")
    except Exception as exc:
        print(f"log_activity for channel delete failed: {exc}")

    print(f"Channel delete reconciled: {label} ({ch_id_str})")
    return {
        "channel_orphaned": True,
        "channel_id": channel.id,
        "channel_type": ch_type,
        "mage": mage_key,
    }


async def ensure_dissolved_threads_archived(discord_client, parent_channel_id: int) -> None:
    """Re-archive dissolved eddies that resurfaced (e.g. after bot restart unarchive)."""
    from thread_registry import load_registry

    registry = load_registry()
    for tid, info in registry["threads"].items():
        if info.get("harvest_status") != "dissolved":
            continue
        try:
            thread_id = int(tid)
        except (TypeError, ValueError):
            continue
        thread = discord_client.get_channel(thread_id)
        if thread is None:
            try:
                thread = await discord_client.fetch_channel(thread_id)
            except (discord.NotFound, discord.HTTPException):
                continue
        if not isinstance(thread, discord.Thread):
            continue
        if thread.parent_id != parent_channel_id:
            continue
        if thread.archived:
            continue
        try:
            await thread.edit(archived=True)
            print(f"Re-archived dissolved thread: {thread.name} ({thread_id})")
        except Exception as exc:
            print(f"Re-archive failed for {thread_id}: {exc}")
