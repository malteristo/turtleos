"""Discord permalink read-for-dialogue — visible trace + inject (D2 acceptance)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import discord

from link_read import _COLOR_FAIL, _COLOR_OK, _COLOR_READING

DISCORD_MESSAGE_LINK_RE = re.compile(
    r"https?://(?:ptb\.|canary\.)?discord(?:app)?\.com/channels/(\d+)/(\d+)/(\d+)"
)

DISCORD_REF_INJECT_LABEL = "Read Discord message"
MAX_REFS_PER_MESSAGE = 3
DIALOGUE_INJECT_MAX = 6000


@dataclass
class DiscordRefResult:
    guild_id: int
    channel_id: int
    message_id: int
    ok: bool
    content: str = ""
    char_count: int = 0
    author: str | None = None
    permalink: str = ""
    error: str | None = None
    attempts: list[str] = field(default_factory=list)


def extract_discord_message_refs(text: str) -> list[tuple[int, int, int]]:
    refs: list[tuple[int, int, int]] = []
    seen: set[tuple[int, int, int]] = set()
    for match in DISCORD_MESSAGE_LINK_RE.finditer(text or ""):
        guild_id, channel_id, message_id = (int(part) for part in match.groups())
        key = (guild_id, channel_id, message_id)
        if key not in seen:
            seen.add(key)
            refs.append(key)
    return refs


def permalink_for(guild_id: int, channel_id: int, message_id: int) -> str:
    return f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"


def format_dereferenced_message(source_message, *, label: str) -> str:
    """Structured block for Turtle inject — shared with craft intake."""
    content = (source_message.content or "").strip()
    parts = [f"[{label}] channel_id={source_message.channel.id} message_id={source_message.id}"]
    author = getattr(source_message.author, "display_name", None) or source_message.author.name
    parts.append(f"author: {author}")
    created = getattr(source_message, "created_at", None)
    if created:
        parts.append(f"created: {created.isoformat()}")
    if content:
        parts.append(f"content:\n{content}")
    attachment_lines = []
    for att in (getattr(source_message, "attachments", None) or [])[:5]:
        name = getattr(att, "filename", "attachment")
        content_type = getattr(att, "content_type", None) or "unknown"
        url = getattr(att, "url", None)
        line = f"{name} ({content_type})"
        if url:
            line += f" {url}"
        attachment_lines.append(line)
    if attachment_lines:
        parts.append("attachments:\n" + "\n".join(f"- {line}" for line in attachment_lines))
    if len(parts) <= 3:
        parts.append("no readable text content")
    return "\n".join(parts)


async def fetch_one_discord_ref(
    client,
    guild_id: int,
    channel_id: int,
    message_id: int,
    *,
    label: str = DISCORD_REF_INJECT_LABEL,
) -> DiscordRefResult:
    link = permalink_for(guild_id, channel_id, message_id)
    try:
        channel = await client.fetch_channel(channel_id)
        source_message = await channel.fetch_message(message_id)
        block = format_dereferenced_message(source_message, label=label)
        author = getattr(source_message.author, "display_name", None) or source_message.author.name
        return DiscordRefResult(
            guild_id=guild_id,
            channel_id=channel_id,
            message_id=message_id,
            ok=True,
            content=block,
            char_count=len(block),
            author=author,
            permalink=link,
        )
    except Exception as exc:
        return DiscordRefResult(
            guild_id=guild_id,
            channel_id=channel_id,
            message_id=message_id,
            ok=False,
            permalink=link,
            error=f"{type(exc).__name__}: {exc}",
            attempts=[f"fetch_message: {type(exc).__name__}"],
        )


async def fetch_discord_message_context(
    client,
    refs: list[tuple[int, int, int]],
    *,
    label: str = DISCORD_REF_INJECT_LABEL,
    limit: int = MAX_REFS_PER_MESSAGE,
) -> tuple[str, int]:
    """Fetch refs without timeline embed — craft intake and legacy callers."""
    results = []
    for guild_id, channel_id, message_id in refs[:limit]:
        results.append(
            await fetch_one_discord_ref(
                client, guild_id, channel_id, message_id, label=label
            )
        )
    return format_discord_refs_for_dialogue(results), sum(1 for r in results if r.ok)


def format_discord_ref_for_dialogue(result: DiscordRefResult) -> str:
    header = f"[{DISCORD_REF_INJECT_LABEL}] {result.permalink}"
    if result.ok and result.content:
        excerpt = result.content[:DIALOGUE_INJECT_MAX]
        if len(result.content) > DIALOGUE_INJECT_MAX:
            body = (
                f"{excerpt}\n\n"
                f"[Note: truncated to {DIALOGUE_INJECT_MAX:,} chars for this turn; "
                f"full message was {result.char_count:,} chars.]"
            )
        else:
            body = excerpt
        return f"{header}\n{body}"
    err = result.error or "unknown error"
    return (
        f"{header}\n"
        f"[Could not read linked message: {err}]\n"
        f"[Paste the relevant text or check bot access to that channel/thread.]"
    )


def format_discord_refs_for_dialogue(results: list[DiscordRefResult]) -> str:
    if not results:
        return ""
    return "\n\n---\n\n".join(format_discord_ref_for_dialogue(r) for r in results)


async def post_discord_ref_status(
    channel: discord.abc.Messageable,
    refs: list[tuple[int, int, int]],
) -> discord.Message | None:
    if not refs:
        return None
    guild_id, channel_id, message_id = refs[0]
    embed = discord.Embed(
        title="💬 Reading Discord message…",
        description=f"`…/{message_id}`",
        color=_COLOR_READING,
    )
    if len(refs) > 1:
        embed.set_footer(text=f"+ {len(refs) - 1} more link(s)")
    try:
        return await channel.send(embed=embed, silent=True)
    except discord.HTTPException as exc:
        print(f"Discord ref status post failed: {exc}")
        return None


def _status_embed_single(result: DiscordRefResult) -> discord.Embed:
    if result.ok:
        lines = [
            f"**{result.char_count:,} chars** from **{result.author or 'unknown'}**",
            "_This is what Turtle read — not Discord's link preview._",
        ]
        return discord.Embed(
            title="💬 Read Discord message",
            description="\n".join(lines),
            color=_COLOR_OK,
        )
    err = (result.error or "unknown")[:900]
    return discord.Embed(
        title="💬 Couldn't read Discord message",
        description=(
            f"**Link:** {result.permalink}\n"
            f"**Error:** {err}\n\n"
            "Check bot access to that channel/thread or paste the text directly."
        ),
        color=_COLOR_FAIL,
    )


def _status_embed_multi(results: list[DiscordRefResult]) -> discord.Embed:
    ok = sum(1 for r in results if r.ok)
    lines = []
    for result in results:
        if result.ok:
            lines.append(
                f"✓ **{result.author or 'message'}** · {result.char_count:,} chars · "
                f"`…/{result.message_id}`"
            )
        else:
            lines.append(f"✗ `…/{result.message_id}` · read failed")
    color = _COLOR_OK if ok == len(results) else (_COLOR_FAIL if ok == 0 else _COLOR_READING)
    return discord.Embed(
        title=f"💬 Read {ok}/{len(results)} Discord message(s)",
        description="\n".join(lines),
        color=color,
    )


async def edit_discord_ref_status(
    status_msg: discord.Message | None,
    results: list[DiscordRefResult],
) -> None:
    if not status_msg or not results:
        return
    embed = _status_embed_single(results[0]) if len(results) == 1 else _status_embed_multi(results)
    try:
        await status_msg.edit(embed=embed)
    except discord.HTTPException as exc:
        print(f"Discord ref status edit failed: {exc}")


async def fetch_discord_refs_with_status(
    channel: discord.abc.Messageable,
    client,
    refs: list[tuple[int, int, int]],
    *,
    label: str = DISCORD_REF_INJECT_LABEL,
) -> tuple[list[DiscordRefResult], str]:
    """Visible Reading→Read embed + dialogue inject block."""
    if not refs:
        return [], ""
    limited = refs[:MAX_REFS_PER_MESSAGE]
    status_msg = await post_discord_ref_status(channel, limited)
    results: list[DiscordRefResult] = []
    async with channel.typing():
        for guild_id, ch_id, msg_id in limited:
            results.append(
                await fetch_one_discord_ref(client, guild_id, ch_id, msg_id, label=label)
            )
        await edit_discord_ref_status(status_msg, results)
    return results, format_discord_refs_for_dialogue(results)
