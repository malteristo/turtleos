"""Session lifecycle commands — checkpoint, release, dissolve (TURTLE_SPEC §8.4, §9.2)."""

from __future__ import annotations

import os

import discord

from helpers import clear_history, get_history, reload_history
from mage import get_mage_name, get_pd, is_practice_channel
from practice_io import count_items, read_safe
from state import MIN_EXCHANGES_FOR_CHECKPOINT, active_sessions


async def cmd_checkpoint(message):
    channel_id = message.channel.id
    history = reload_history(channel_id)
    if len(history) < MIN_EXCHANGES_FOR_CHECKPOINT:
        await message.reply(
            "Not enough conversation to checkpoint yet.",
            mention_author=False,
        )
        return

    from sessions import checkpoint_session

    result = await checkpoint_session(channel_id, trigger="manual", mark_paused=False)

    if not result.captured_anything:
        await message.reply(
            "Checkpoint ran — nothing new met the save threshold.",
            mention_author=False,
        )
        return

    lines: list[str] = []
    if result.flow_writes:
        lines.append(f"**Flow:** `{result.flow_writes[0]}`")
    if result.session_note:
        lines.append(f"**Session note:** `sessions/{result.session_note}`")
    if result.proposal:
        lines.append(f"**Proposal:** `proposals/{result.proposal}`")

    embed = discord.Embed(
        title="Checkpoint saved",
        description="\n".join(lines),
        color=0x5865F2,
    )
    embed.set_footer(text="History kept — continue when ready, or !release to close.")
    await message.reply(embed=embed, mention_author=False)


async def cmd_release(message):
    channel_id = message.channel.id
    history = reload_history(channel_id)
    if len(history) < 2:
        await message.reply("Not enough conversation to release. Just go — rest well.", mention_author=False)
        return

    await message.reply("Closing session...", mention_author=False)
    from sessions import checkpoint_session

    result = await checkpoint_session(channel_id, trigger="release", mark_paused=True)

    clear_history(channel_id)
    active_sessions.pop(channel_id, None)

    embed = discord.Embed(title="Session Released", color=0x2ECC71)
    lines: list[str] = ["Conversation history cleared."]
    if result.flow_writes:
        lines.insert(0, f"**Flow:** `{result.flow_writes[0]}`")
    if result.session_note:
        lines.insert(0, f"**Session note:** `sessions/{result.session_note}`")
    if result.proposal:
        lines.insert(0, f"**Proposal:** `proposals/{result.proposal}`")
    if not result.captured_anything:
        lines.insert(0, "No new resonance captured this release.")
    embed.description = "\n".join(lines) + f"\n\nRest well, {get_mage_name()}."

    boom = read_safe(os.path.join(get_pd(), "boom.md"))
    boom_count = count_items(boom)
    if boom_count > 0:
        embed.add_field(
            name="Note",
            value=f"Boom has **{boom_count}** items. Consider `!sweep` before you go.",
            inline=False,
        )

    await message.reply(embed=embed, mention_author=False)


async def cmd_dissolve(message, args):
    """Archive eddy — essence, file archive, chronicle. Distinct from !release."""
    if not isinstance(message.channel, discord.Thread):
        await message.reply(
            "Use `!dissolve` inside an eddy thread to archive it.",
            mention_author=False,
        )
        return
    if not is_practice_channel(message):
        await message.reply("Use `!dissolve` in your practice eddies.", mention_author=False)
        return

    channel_id = message.channel.id
    history = reload_history(channel_id)
    from_lifecycle_bar = getattr(message, "from_lifecycle_bar", False)
    discord_client = getattr(message, "discord_client", None)

    if not from_lifecycle_bar:
        await message.reply("Dissolving eddy…", mention_author=False)

    from sessions import dissolve_eddy

    result = await dissolve_eddy(channel_id, history, discord_client=discord_client)
    if not result:
        await message.reply("Could not dissolve — thread not found.", mention_author=False)
        return

    clear_history(channel_id)
    active_sessions.pop(channel_id, None)

    lines = [f"**{result.thread_name}** archived."]
    if result.already_archived:
        lines = [f"**{result.thread_name}** is archived — still readable in Discord's thread list."]
    elif result.entry_count:
        lines.append(f"{result.entry_count} entries captured to boom.")
    if result.jump_url and not result.already_archived:
        lines.append(f"Chronicle: {result.jump_url}")
    embed = discord.Embed(
        title="Eddy archived" if result.already_archived else "Eddy dissolved",
        description="\n".join(lines),
        color=0x2ECC71,
    )
    await message.reply(embed=embed, mention_author=False)
