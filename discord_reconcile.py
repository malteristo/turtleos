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
        )
        if result:
            clear_history(after.id)
            active_sessions.pop(after.id, None)
        return {"full_dissolve": True, "result": result, "thread_id": after.id}

    from sessions import light_archive_eddy

    await light_archive_eddy(after.id, discord_client=discord_client)
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
