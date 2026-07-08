"""Session lifecycle commands — checkpoint, release, dissolve (TURTLE_SPEC §8.4, §9.2)."""

from __future__ import annotations

import os

import discord

from artifact_viewer import mark_artifacts_ui_unlocked, shelf_title_for_path
from artifact_presenter import ArtifactSurface, checkpoint_open_path, reply_artifact_surface
from helpers import clear_history, get_history, reload_history
from mage import get_mage_name, get_pd, is_practice_channel
from practice_io import count_items, read_safe
from state import MIN_EXCHANGES_FOR_CHECKPOINT, MIN_EXCHANGES_FOR_REFLECTION, active_sessions


def _short_history_message(history: list[dict], *, action: str) -> str:
    n = len(history)
    need = MIN_EXCHANGES_FOR_CHECKPOINT
    return (
        f"Not enough conversation to {action} yet "
        f"({n}/{need} exchanges on the shared dialogue store)."
    )


def _nothing_captured_message(history: list[dict]) -> str:
    n = len(history)
    if n < MIN_EXCHANGES_FOR_REFLECTION:
        return (
            f"Checkpoint ran — {n} exchange(s) saved; session notes need at least "
            f"{MIN_EXCHANGES_FOR_REFLECTION}. Keep talking, then checkpoint again."
        )
    return (
        "Checkpoint ran — nothing new met the save threshold "
        "(reflection cooldown or model produced no note)."
    )


async def cmd_checkpoint(message):
    channel_id = message.channel.id
    history = reload_history(channel_id)
    if len(history) < MIN_EXCHANGES_FOR_CHECKPOINT:
        await message.reply(
            _short_history_message(history, action="checkpoint"),
            mention_author=False,
        )
        return

    ack = await message.reply(
        embed=discord.Embed(
            title="Checkpointing…",
            description="Saving flow state and writing your session note — usually 1–2 minutes.",
            color=0x5865F2,
        ),
        mention_author=False,
    )

    from sessions import checkpoint_session

    result = await checkpoint_session(channel_id, trigger="manual", mark_paused=False)

    if not result.captured_anything:
        await ack.edit(content=_nothing_captured_message(history))
        return

    mark_artifacts_ui_unlocked("checkpoint")

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
    open_path = checkpoint_open_path(
        session_note=result.session_note,
        flow_write=result.flow_writes[0] if result.flow_writes else None,
    )
    surface = ArtifactSurface(
        template_id="post_checkpoint_open" if open_path else "post_checkpoint_none",
        embed=embed,
        open_actions=[("Open", f"!read {open_path}")] if open_path else [],
    )
    try:
        await ack.delete()
    except discord.HTTPException:
        pass
    await reply_artifact_surface(message, surface)


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

    if result.captured_anything:
        mark_artifacts_ui_unlocked("checkpoint")

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
    open_path = checkpoint_open_path(
        session_note=result.session_note,
        flow_write=result.flow_writes[0] if result.flow_writes else None,
    )
    if open_path:
        embed.add_field(
            name="Artifacts",
            value=f"Saved to **{shelf_title_for_path(open_path)}**",
            inline=False,
        )

    boom = read_safe(os.path.join(get_pd(), "boom.md"))
    boom_count = count_items(boom)
    if boom_count > 0:
        embed.add_field(
            name="Note",
            value=f"Boom has **{boom_count}** items. Consider `!sweep` before you go.",
            inline=False,
        )

    await reply_artifact_surface(
        message,
        ArtifactSurface(
            template_id="post_release_open" if open_path else "post_release_none",
            embed=embed,
            open_actions=[("Open", f"!read {open_path}")] if open_path else [],
        ),
    )


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

    from share_eddy import check_share_dissolve_authority

    dissolve_auth = check_share_dissolve_authority(
        message.channel.id,
        message.channel.parent_id,
        message.author.id,
    )
    if not dissolve_auth.allowed:
        await message.reply(dissolve_auth.reason or "You cannot dissolve this eddy.", mention_author=False)
        return

    channel_id = message.channel.id
    history = reload_history(channel_id)
    from_lifecycle_bar = getattr(message, "from_lifecycle_bar", False)
    discord_client = getattr(message, "discord_client", None)

    if not from_lifecycle_bar:
        await message.reply("Dissolving eddy…", mention_author=False)

    from runtime.adapters.lifecycle import close_eddy

    source = "lifecycle_bar" if from_lifecycle_bar else "command"
    result = await close_eddy(
        channel_id,
        history,
        source=source,
        discord_client=discord_client,
        parent_channel_id=message.channel.parent_id,
    )
    if not result:
        await message.reply("Could not dissolve — thread not found.", mention_author=False)
        return

    if not result.capture_failed and not result.retain_memory:
        clear_history(channel_id)
        active_sessions.pop(channel_id, None)

    lines = [f"**{result.thread_name}** archived."]
    if result.capture_failed:
        lines = [
            f"**{result.thread_name}** — dissolve aborted (essence capture failed).",
            "Eddy cooled; memory retained. Try again with `!dissolve`.",
        ]
    elif result.already_archived:
        lines = [f"**{result.thread_name}** is archived — still readable in Discord's thread list."]
    elif result.entry_count:
        lines.append(f"{result.entry_count} entries captured to boom.")
    if result.retain_memory and not result.capture_failed:
        lines.append("Memory retained (📌 keep).")
    if result.jump_url and not result.already_archived and not result.capture_failed:
        lines.append(f"Chronicle: {result.jump_url}")
    embed = discord.Embed(
        title=(
            "Eddy cooled"
            if result.capture_failed
            else ("Eddy archived" if result.already_archived else "Eddy dissolved")
        ),
        description="\n".join(lines),
        color=0x2ECC71,
    )
    await message.reply(embed=embed, mention_author=False)


async def cmd_keep(message, args):
    """Mark eddy continuity: keep — memory retained on deliberate close."""
    if not isinstance(message.channel, discord.Thread):
        await message.reply("Use `!keep` inside an eddy thread.", mention_author=False)
        return
    if not is_practice_channel(message):
        await message.reply("Use `!keep` in your practice eddies.", mention_author=False)
        return

    from thread_registry import CONTINUITY_KEEP, update_thread_continuity

    update_thread_continuity(message.channel.id, CONTINUITY_KEEP)
    await message.reply(
        "📌 **Keep** — this eddy will retain memory on deliberate close. "
        "Auto-archive will cool it without dissolving.",
        mention_author=False,
    )


async def cmd_ignore(message, args):
    """Mark eddy continuity: ignore — purge on confirm, no trace kept."""
    if not isinstance(message.channel, discord.Thread):
        await message.reply("Use `!ignore` inside an eddy thread.", mention_author=False)
        return
    if not is_practice_channel(message):
        await message.reply("Use `!ignore` in your practice eddies.", mention_author=False)
        return

    from state import pending_ignore_confirm
    from thread_registry import CONTINUITY_IGNORE, update_thread_continuity
    from runtime.adapters.lifecycle import purge_ignored_eddy

    key = (message.author.id, message.channel.id)
    if args and args[0] in ("--confirm", "confirm"):
        if not pending_ignore_confirm.pop(key, False):
            await message.reply(
                "No pending ignore. Run `!ignore` first.",
                mention_author=False,
            )
            return
        update_thread_continuity(message.channel.id, CONTINUITY_IGNORE)
        await purge_ignored_eddy(
            message.channel.id,
            discord_client=getattr(message, "discord_client", None),
            parent_channel_id=message.channel.parent_id,
            thread_name=message.channel.name,
        )
        await message.reply(
            "🚫 **Ignored** — eddy purged from Turtle memory. "
            "Workshop copies (if synced) need Mage-side deletion.",
            mention_author=False,
        )
        return

    pending_ignore_confirm[key] = True
    await message.reply(
        "This eddy will leave **no trace** in Turtle memory. "
        "Confirm with `!ignore confirm`.",
        mention_author=False,
    )
