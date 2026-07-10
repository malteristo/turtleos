"""Practice message dispatch — on_message branch tree for practice channels.

Slice 6 of discord_bot.py decomposition (2026-07-10).
Called from discord_bot.on_message.
"""

from __future__ import annotations

import discord

from commands import dispatch_direct_command
from craft_intake import is_craft_intake_channel, schedule_craft_intake
from dialogue_routing import route_practice_dialogue, should_skip_native_starter
from eddy_spawn import handle_intake_message, is_intake_thread
from founder_keys import try_founder_key_entry
from mage import (
    _get_channel_type,
    is_practice_channel,
    maybe_reload_mage_registry,
    river_bot_enabled,
    set_practice_context,
    turtle_handles_native_river,
    uses_native_river,
    resolve_dialogue_channel_id,
)
from prompts import uses_native_turtle_prompt
from river_keys import try_river_key_claim
from state import SPIRIT_BOT_ID, _processed_messages, client, get_channel_lock


async def dispatch_incoming_message(message: discord.Message) -> None:
    """Route an incoming Discord message through the practice-channel branch tree."""
    if message.author == client.user:
        return

    if message.type not in (discord.MessageType.default, discord.MessageType.reply) and not getattr(
        message, "message_snapshots", None
    ):
        return

    maybe_reload_mage_registry()
    set_practice_context(message)

    if message.author.bot:
        if message.author.id == SPIRIT_BOT_ID and is_practice_channel(message):
            pass  # Spirit (dyad partner) — process like a practitioner message
        elif client.user in message.mentions and is_practice_channel(message):
            await route_practice_dialogue(message)
            return
        else:
            return

    if isinstance(message.channel, discord.Thread) and uses_native_turtle_prompt(
        resolve_dialogue_channel_id(message)
    ):
        if await should_skip_native_starter(message):
            return

    if not is_practice_channel(message):
        return

    # Split-bot: River owns all turtle-talk `!` commands (acts, not Turtle prose)
    if message.content.strip().startswith("!") and river_bot_enabled():
        return

    if await dispatch_direct_command(message):
        return

    if message.id in _processed_messages:
        print(f"Skipping duplicate message {message.id}")
        return
    _processed_messages.append(message.id)

    if await try_founder_key_entry(message):
        return

    if (
        not isinstance(message.channel, discord.Thread)
        and _get_channel_type(message.channel.id) == "unclaimed-river"
    ):
        lock = get_channel_lock(message.channel.id)
        async with lock:
            if await try_river_key_claim(message, client):
                return
        return

    if is_intake_thread(message.channel) and not message.content.strip().startswith("!"):
        lock = get_channel_lock(message.channel.id)
        async with lock:
            await handle_intake_message(message)
        return

    if river_bot_enabled() and uses_native_river(message):
        return

    if turtle_handles_native_river(message):
        from river_handler import handle_river_message

        lock = get_channel_lock(message.channel.id)
        async with lock:
            await handle_river_message(message)
        return

    if (
        isinstance(message.channel, discord.Thread)
        and message.channel.parent_id
        and not river_bot_enabled()
    ):
        from eddy_spawn import is_awaiting_flow_intake, is_awaiting_title
        from river_handler import handle_eddy_first_message

        if is_awaiting_flow_intake(message.channel.id, message.channel.parent_id):
            return
        if is_awaiting_title(message.channel.id, message.channel.parent_id):
            lock = get_channel_lock(message.channel.id)
            async with lock:
                await handle_eddy_first_message(message)
                if message.id in _processed_messages:
                    return
                _processed_messages.append(message.id)
            await route_practice_dialogue(message)
            return

    lock = get_channel_lock(message.channel.id)
    async with lock:
        if is_craft_intake_channel(message):
            await schedule_craft_intake(message, client)
            return

    await route_practice_dialogue(message)
