"""Discord Gateway → turtleOS state reconciliation (Tier 2/3).

Thin facade over runtime/adapters — keeps discord_bot imports stable.
See docs/chapters/design-discord-native-ui-reconciliation.md.
"""

from __future__ import annotations

from typing import Any

import discord

from runtime.adapters.lifecycle import (
    cleanup_eddy_memory as _cleanup_eddy_memory,
    close_eddy,
    close_eddy_from_archive_transition,
    open_eddy,
    reconcile_thread_delete,
    reconcile_thread_lock_transition,
    _load_history_for_thread,
    _registry_entry,
)
from runtime.adapters.structural import (
    _channel_binding_hint,
    expect_channel_registry_binding,
    reconcile_channel_create,
    reconcile_channel_delete,
    reconcile_channel_update,
)
from mage import is_registered_parent_channel

# Re-export for tests and blessed-path hooks.
__all__ = [
    "expect_channel_registry_binding",
    "handle_thread_open",
    "handle_thread_archive_transition",
    "handle_thread_update",
    "handle_thread_delete",
    "handle_guild_channel_delete",
    "handle_guild_channel_create",
    "handle_guild_channel_update",
    "ensure_dissolved_threads_archived",
    "close_eddy",
]

handle_thread_archive_transition = close_eddy_from_archive_transition
handle_thread_open = open_eddy
handle_thread_delete = reconcile_thread_delete
handle_guild_channel_create = reconcile_channel_create
handle_guild_channel_update = reconcile_channel_update
handle_guild_channel_delete = reconcile_channel_delete


async def handle_thread_update(before: discord.Thread, after: discord.Thread, *, discord_client) -> None:
    """Rename sync + lifecycle transitions from native Discord UI."""
    from thread_registry import update_thread_name

    parent_id = after.parent_id or 0
    if not is_registered_parent_channel(parent_id):
        return

    if before.name != after.name:
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
                if outcome.get("full_dissolve"):
                    kind = "full dissolve"
                elif outcome.get("cooled"):
                    kind = "cooled"
                elif outcome.get("purged"):
                    kind = "ignore purge"
                else:
                    kind = "light archive"
                print(f"Native thread close reconciled ({kind}): {after.name} ({after.id})")
        except Exception as exc:
            print(f"Native thread archive reconcile failed for {after.id}: {exc}")

    if before.archived and not after.archived:
        try:
            from thread_registry import clear_cooled_status

            clear_cooled_status(after.id)
            print(f"Eddy resumed from archive: {after.name} ({after.id})")
        except Exception as exc:
            print(f"Cooled status clear failed for {after.id}: {exc}")

    if before.locked != after.locked:
        try:
            outcome = await reconcile_thread_lock_transition(
                before, after, discord_client=discord_client
            )
            if outcome:
                state = "locked" if outcome.get("locked") else "unlocked"
                print(f"Native thread lock reconciled ({state}): {after.name} ({after.id})")
        except Exception as exc:
            print(f"Native thread lock reconcile failed for {after.id}: {exc}")


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
