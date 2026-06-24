"""Discord permalink read-for-dialogue — visible trace + inject (D2 / D2b acceptance)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import AsyncIterator

import discord

from link_read import _COLOR_FAIL, _COLOR_OK, _COLOR_READING

DISCORD_MESSAGE_LINK_RE = re.compile(
    r"https?://(?:ptb\.|canary\.)?discord(?:app)?\.com/channels/(\d+)/(\d+)/(\d+)"
)
DISCORD_THREAD_ONLY_LINK_RE = re.compile(
    r"https?://(?:ptb\.|canary\.)?discord(?:app)?\.com/channels/(\d+)/(\d+)(?:\?[^\s]*)?(?=\s|$|[^\d/])"
)

DISCORD_REF_INJECT_LABEL = "Read Discord message"
DISCORD_THREAD_REF_LABEL = "Read Discord thread"
MAX_REFS_PER_MESSAGE = 3
DIALOGUE_INJECT_MAX = 6000
THREAD_HISTORY_MAX_MESSAGES = 40
THREAD_LINE_MAX = 600


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
    scope: str = "message"  # message | thread
    message_count: int = 1
    thread_name: str | None = None


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


def extract_discord_thread_only_refs(text: str) -> list[tuple[int, int]]:
    """Thread permalinks without message id — channels/{guild}/{thread_id}."""
    refs: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    message_channels = {(g, c) for g, c, _ in extract_discord_message_refs(text or "")}
    for match in DISCORD_THREAD_ONLY_LINK_RE.finditer(text or ""):
        guild_id, thread_id = (int(part) for part in match.groups())
        key = (guild_id, thread_id)
        if key in seen or key in message_channels:
            continue
        seen.add(key)
        refs.append(key)
    return refs


def extract_all_discord_refs(text: str) -> list[tuple[int, int, int | None]]:
    """Message refs first, then thread-only refs (message_id=None)."""
    out: list[tuple[int, int, int | None]] = [
        (g, c, m) for g, c, m in extract_discord_message_refs(text)
    ]
    seen_channels = {(g, c) for g, c, _ in out}
    for guild_id, thread_id in extract_discord_thread_only_refs(text):
        if (guild_id, thread_id) not in seen_channels:
            out.append((guild_id, thread_id, None))
            seen_channels.add((guild_id, thread_id))
    return out


def permalink_for(guild_id: int, channel_id: int, message_id: int | None = None) -> str:
    if message_id:
        return f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"
    return f"https://discord.com/channels/{guild_id}/{channel_id}"


def _is_thread_channel(channel) -> bool:
    if isinstance(channel, discord.Thread):
        return True
    return getattr(channel, "type", None) in (
        discord.ChannelType.public_thread,
        discord.ChannelType.private_thread,
        discord.ChannelType.news_thread,
    )


def _author_label(message) -> str:
    if getattr(message.author, "bot", False):
        return "Turtle"
    return getattr(message.author, "display_name", None) or message.author.name


def _message_line(message, *, max_len: int = THREAD_LINE_MAX) -> str:
    content = (message.content or "").strip()
    if not content and getattr(message, "attachments", None):
        content = f"(attachment: {message.attachments[0].filename})"
    if not content:
        return ""
    return f"{_author_label(message)}: {content[:max_len]}"


async def _iter_thread_messages(thread, *, limit: int) -> AsyncIterator:
    async for msg in thread.history(limit=limit, oldest_first=True):
        yield msg


async def _collect_thread_lines(thread, *, limit: int = THREAD_HISTORY_MAX_MESSAGES) -> list[str]:
    lines: list[str] = []
    async for msg in _iter_thread_messages(thread, limit=limit):
        line = _message_line(msg)
        if line:
            lines.append(line)
    return lines


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


def format_thread_context_block(
    *,
    thread_name: str | None,
    lines: list[str],
    permalink: str,
    anchor_message_id: int | None = None,
) -> str:
    header = f"[{DISCORD_THREAD_REF_LABEL}] {permalink}"
    if thread_name:
        header += f"\nthread: {thread_name}"
    if anchor_message_id:
        header += f"\nanchor_message_id: {anchor_message_id}"
    body = "\n\n".join(lines)
    return f"{header}\nmessages ({len(lines)}):\n{body}"


def _inject_label(result: DiscordRefResult) -> str:
    return DISCORD_THREAD_REF_LABEL if result.scope == "thread" else DISCORD_REF_INJECT_LABEL


async def fetch_one_discord_thread(
    client,
    guild_id: int,
    thread_id: int,
    *,
    anchor_message_id: int | None = None,
) -> DiscordRefResult:
    link = permalink_for(guild_id, thread_id, anchor_message_id)
    try:
        channel = await client.fetch_channel(thread_id)
        if not _is_thread_channel(channel):
            raise ValueError(f"channel {thread_id} is not a thread")
        lines = await _collect_thread_lines(channel)
        if not lines:
            raise ValueError("thread has no readable messages")
        block = format_thread_context_block(
            thread_name=getattr(channel, "name", None),
            lines=lines,
            permalink=link,
            anchor_message_id=anchor_message_id,
        )
        return DiscordRefResult(
            guild_id=guild_id,
            channel_id=thread_id,
            message_id=anchor_message_id or 0,
            ok=True,
            content=block,
            char_count=len(block),
            permalink=link,
            scope="thread",
            message_count=len(lines),
            thread_name=getattr(channel, "name", None),
        )
    except Exception as exc:
        return DiscordRefResult(
            guild_id=guild_id,
            channel_id=thread_id,
            message_id=anchor_message_id or 0,
            ok=False,
            permalink=link,
            error=f"{type(exc).__name__}: {exc}",
            attempts=[f"fetch_thread: {type(exc).__name__}"],
            scope="thread",
        )


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
        thread = channel if _is_thread_channel(channel) else None
        if thread is None and _is_thread_channel(getattr(source_message, "channel", None)):
            thread = source_message.channel

        if thread is not None:
            lines = await _collect_thread_lines(thread)
            if len(lines) > 1:
                block = format_thread_context_block(
                    thread_name=getattr(thread, "name", None),
                    lines=lines,
                    permalink=link,
                    anchor_message_id=message_id,
                )
                return DiscordRefResult(
                    guild_id=guild_id,
                    channel_id=channel_id,
                    message_id=message_id,
                    ok=True,
                    content=block,
                    char_count=len(block),
                    author=_author_label(source_message),
                    permalink=link,
                    scope="thread",
                    message_count=len(lines),
                    thread_name=getattr(thread, "name", None),
                )

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
            scope="message",
            message_count=1,
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
    header = f"[{_inject_label(result)}] {result.permalink}"
    if result.ok and result.content:
        excerpt = result.content[:DIALOGUE_INJECT_MAX]
        if len(result.content) > DIALOGUE_INJECT_MAX:
            body = (
                f"{excerpt}\n\n"
                f"[Note: truncated to {DIALOGUE_INJECT_MAX:,} chars for this turn; "
                f"full extract was {result.char_count:,} chars"
            )
            if result.scope == "thread":
                body += f" from {result.message_count} messages"
            body += ".]"
        else:
            body = excerpt
        return f"{header}\n{body}"
    err = result.error or "unknown error"
    return (
        f"{header}\n"
        f"[Could not read linked Discord context: {err}]\n"
        f"[Paste the relevant text or check bot access to that channel/thread.]"
    )


def format_discord_refs_for_dialogue(results: list[DiscordRefResult]) -> str:
    if not results:
        return ""
    return "\n\n---\n\n".join(format_discord_ref_for_dialogue(r) for r in results)


async def post_discord_ref_status(
    channel: discord.abc.Messageable,
    targets: list[tuple[int, int, int | None]],
) -> discord.Message | None:
    if not targets:
        return None
    guild_id, channel_id, message_id = targets[0]
    thread_only = message_id is None
    embed = discord.Embed(
        title="💬 Reading Discord thread…" if thread_only else "💬 Reading Discord message…",
        description=f"`…/{channel_id}`" if thread_only else f"`…/{message_id}`",
        color=_COLOR_READING,
    )
    if len(targets) > 1:
        embed.set_footer(text=f"+ {len(targets) - 1} more link(s)")
    try:
        return await channel.send(embed=embed, silent=True)
    except discord.HTTPException as exc:
        print(f"Discord ref status post failed: {exc}")
        return None


def _status_embed_single(result: DiscordRefResult) -> discord.Embed:
    if result.ok:
        if result.scope == "thread":
            lines = [
                f"**{result.message_count} messages** · **{result.char_count:,} chars** in context",
                "_This is what Turtle read — not Discord's link preview._",
            ]
            title = "💬 Read Discord thread"
        else:
            lines = [
                f"**{result.char_count:,} chars** from **{result.author or 'unknown'}**",
                "_This is what Turtle read — not Discord's link preview._",
            ]
            title = "💬 Read Discord message"
        if result.thread_name:
            lines.insert(0, f"**#{result.thread_name}**")
        return discord.Embed(title=title, description="\n".join(lines), color=_COLOR_OK)
    err = (result.error or "unknown")[:900]
    return discord.Embed(
        title="💬 Couldn't read Discord link",
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
            if result.scope == "thread":
                lines.append(
                    f"✓ **{result.thread_name or 'thread'}** · "
                    f"{result.message_count} msgs · {result.char_count:,} chars"
                )
            else:
                lines.append(
                    f"✓ **{result.author or 'message'}** · {result.char_count:,} chars · "
                    f"`…/{result.message_id}`"
                )
        else:
            lines.append(f"✗ `{result.permalink}` · read failed")
    color = _COLOR_OK if ok == len(results) else (_COLOR_FAIL if ok == 0 else _COLOR_READING)
    return discord.Embed(
        title=f"💬 Read {ok}/{len(results)} Discord link(s)",
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


async def _fetch_one_target(
    client,
    guild_id: int,
    channel_id: int,
    message_id: int | None,
    *,
    label: str,
) -> DiscordRefResult:
    if message_id is None:
        return await fetch_one_discord_thread(client, guild_id, channel_id)
    return await fetch_one_discord_ref(
        client, guild_id, channel_id, message_id, label=label
    )


async def fetch_discord_refs_with_status(
    channel: discord.abc.Messageable,
    client,
    refs: list[tuple[int, int, int]],
    *,
    label: str = DISCORD_REF_INJECT_LABEL,
) -> tuple[list[DiscordRefResult], str]:
    """Visible Reading→Read embed + dialogue inject block (message permalinks)."""
    targets = [(g, c, m) for g, c, m in refs]
    return await _fetch_targets_with_status(channel, client, targets, label=label)


async def fetch_all_discord_refs_with_status(
    channel: discord.abc.Messageable,
    client,
    text: str,
    *,
    label: str = DISCORD_REF_INJECT_LABEL,
) -> tuple[list[DiscordRefResult], str]:
    """Message + thread-only permalinks from practitioner text."""
    targets = extract_all_discord_refs(text)[:MAX_REFS_PER_MESSAGE]
    return await _fetch_targets_with_status(channel, client, targets, label=label)


async def _fetch_targets_with_status(
    channel: discord.abc.Messageable,
    client,
    targets: list[tuple[int, int, int | None]],
    *,
    label: str,
) -> tuple[list[DiscordRefResult], str]:
    if not targets:
        return [], ""
    status_msg = await post_discord_ref_status(channel, targets)
    results: list[DiscordRefResult] = []
    async with channel.typing():
        for guild_id, ch_id, msg_id in targets:
            results.append(
                await _fetch_one_target(client, guild_id, ch_id, msg_id, label=label)
            )
        await edit_discord_ref_status(status_msg, results)
    return results, format_discord_refs_for_dialogue(results)
