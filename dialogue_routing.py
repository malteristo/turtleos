"""Practice dialogue routing — enqueue path and native starter guards.

Slice 1 of discord_bot.py decomposition (2026-07-10).
Re-exported from discord_bot for backward compatibility.
"""

from __future__ import annotations

import discord

from mage import resolve_dialogue_channel_id
from prompts import uses_native_turtle_prompt


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
) -> None:
    """Enqueue a practitioner message for serialized dialogue handling."""
    from dialogue_queue import enqueue_dialogue

    if dialogue_handler is None:
        import dialogue_turn

        dialogue_handler = dialogue_turn.handle_dialogue
    if after_turn is None:
        after_turn = touch_flow_library_after_dialogue

    ch = getattr(message.channel, "name", message.channel.id)
    preview = (message.content or "")[:120]
    if not preview.strip() and getattr(message, "message_snapshots", None):
        preview = "[forwarded message]"
    print(f"Turtle inbound [{ch}]: {preview!r}")
    await enqueue_dialogue(message, dialogue_handler, after_turn=after_turn)


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
