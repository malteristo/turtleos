"""Practice dialogue routing — enqueue path and native starter guards.

Slice 1 of discord_bot.py decomposition (2026-07-10).
Re-exported from discord_bot for backward compatibility.
"""

from __future__ import annotations

import asyncio
from collections import deque

import discord

from mage import resolve_dialogue_channel_id
from prompts import uses_native_turtle_prompt

# One Discord message is one Turtle turn. The first-eddy handoff exists
# because split-bot Turtle sometimes never sees MESSAGE_CREATE. When it
# already did, the watcher must not enqueue the same id again (2026-09-13).
_ROUTED_CAP = 256
_routed_ids: deque[int] = deque()
_routed_set: set[int] = set()


def _as_message_id(message_id: object) -> int | None:
    try:
        return int(message_id)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def already_inbound(message_id: object) -> bool:
    mid = _as_message_id(message_id)
    return mid is not None and mid in _routed_set


def claim_inbound(message_id: object) -> bool:
    """True the first time this message id is claimed in this process."""
    mid = _as_message_id(message_id)
    if mid is None:
        return True
    if mid in _routed_set:
        return False
    _routed_ids.append(mid)
    _routed_set.add(mid)
    if len(_routed_ids) > _ROUTED_CAP:
        _routed_set.discard(_routed_ids.popleft())
    return True


def reset_inbound_claims() -> None:
    """Test seam — production never clears mid-process."""
    _routed_ids.clear()
    _routed_set.clear()


async def touch_flow_library_after_dialogue(message: discord.Message) -> None:
    if isinstance(message.channel, discord.Thread):
        from mage import river_bot_enabled

        if river_bot_enabled():
            from river_turn_signal import mark_turtle_turn_complete

            mark_turtle_turn_complete(message.channel.id, message.id)


async def route_practice_dialogue(
    message: discord.Message,
    *,
    dialogue_handler=None,
    after_turn=None,
) -> bool:
    """Enqueue a practitioner message for serialized dialogue handling."""
    from dialogue_queue import enqueue_dialogue

    if dialogue_handler is None:
        import dialogue_turn

        dialogue_handler = dialogue_turn.handle_dialogue
    if after_turn is None:
        after_turn = touch_flow_library_after_dialogue

    mid = getattr(message, "id", None)
    if mid is not None and not claim_inbound(mid):
        print(f"Turtle inbound skipped — already routed ({mid})")
        return False
    ch = getattr(message.channel, "name", message.channel.id)
    preview = (message.content or "")[:120]
    if not preview.strip() and getattr(message, "message_snapshots", None):
        preview = "[forwarded message]"
    print(f"Turtle inbound [{ch}]: {preview!r}")
    await enqueue_dialogue(message, dialogue_handler, after_turn=after_turn)
    return True


async def process_first_eddy_handoff(client, payload: dict) -> bool:
    """Fetch the practitioner message and enqueue Turtle dialogue.

    Leave the file when Turtle cannot see the thread yet so the next poll
    retries. Drop the file when the message itself is gone.
    """
    from first_eddy_handoff import pop_first_eddy_handoff
    from mage import set_practice_context_for_channel

    thread_id = int(payload["thread_id"])
    parent_id = int(payload["parent_id"])
    message_id = int(payload["message_id"])
    runtime_dir = payload["_runtime_dir"]

    set_practice_context_for_channel(parent_id)

    thread = client.get_channel(thread_id)
    if thread is None:
        try:
            thread = await client.fetch_channel(thread_id)
        except Exception as exc:
            print(
                f"First eddy handoff: thread {thread_id} not visible yet "
                f"({type(exc).__name__}: {exc})"
            )
            return False

    if getattr(client, "user", None):
        try:
            await thread.fetch_member(client.user.id)
        except Exception:
            return False

    try:
        message = await thread.fetch_message(message_id)
    except Exception as exc:
        print(
            f"First eddy handoff: message {message_id} gone in {thread_id} "
            f"({type(exc).__name__}: {exc})"
        )
        pop_first_eddy_handoff(thread_id, runtime_dir=runtime_dir)
        return False

    if pop_first_eddy_handoff(thread_id, runtime_dir=runtime_dir) is None:
        return False

    if already_inbound(message_id):
        print(
            f"First eddy handoff skipped — inbound already has {message_id} "
            f"in {thread_id}"
        )
        return True

    routed = await route_practice_dialogue(message)
    if routed is False:
        print(
            f"First eddy handoff skipped — inbound already has {message_id} "
            f"in {thread_id}"
        )
        return True
    print(f"First eddy handoff routed: thread={thread_id} message={message_id}")
    return True


async def first_eddy_handoff_watcher(client) -> None:
    """Poll for River-written first-message dialogue requests (split-bot)."""
    from first_eddy_handoff import list_first_eddy_handoffs
    from mage import list_registered_runtime_dirs

    while True:
        try:
            for payload in list_first_eddy_handoffs(list_registered_runtime_dirs()):
                await process_first_eddy_handoff(client, payload)
        except Exception as exc:
            print(f"First eddy handoff watcher error: {type(exc).__name__}: {exc}")
        await asyncio.sleep(0.5)


def start_first_eddy_handoff_watcher(client) -> asyncio.Task:
    return asyncio.create_task(first_eddy_handoff_watcher(client))


async def should_skip_native_starter(message: discord.Message) -> bool:
    """Skip the thread starter message on native eddies (River owns first touch)."""
    if not isinstance(message.channel, discord.Thread):
        return False
    if not uses_native_turtle_prompt(resolve_dialogue_channel_id(message)):
        return False
    try:
        starter = message.channel.starter_message
        if starter is None:
            starter = await message.channel.fetch_start_message()
        return bool(starter and message.id == starter.id)
    except Exception:
        return False
