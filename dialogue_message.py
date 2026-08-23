"""Dialogue message surface — visible content, forwards, permalink refs.

Slice 2 of discord_bot.py decomposition (2026-07-10).
Re-exported from discord_bot for backward compatibility.
"""

from __future__ import annotations


def summarize_message_snapshot(snapshot, index: int) -> str:
    parts = [f"[Forwarded message {index}]"]
    created = getattr(snapshot, "created_at", None)
    if created:
        parts.append(f"created: {created.isoformat()}")
    msg_type = getattr(snapshot, "type", None)
    if msg_type:
        parts.append(f"type: {msg_type}")

    content = (getattr(snapshot, "content", "") or "").strip()
    if content:
        parts.append(f"content:\n{content}")

    embeds = getattr(snapshot, "embeds", []) or []
    if embeds:
        embed_lines = []
        for embed in embeds[:3]:
            bits = []
            if getattr(embed, "title", None):
                bits.append(f"title={embed.title}")
            if getattr(embed, "url", None):
                bits.append(f"url={embed.url}")
            if getattr(embed, "description", None):
                bits.append(f"description={embed.description[:500]}")
            if bits:
                embed_lines.append("; ".join(bits))
        if embed_lines:
            parts.append("embeds:\n" + "\n".join(f"- {line}" for line in embed_lines))

    attachments = getattr(snapshot, "attachments", []) or []
    if attachments:
        attachment_lines = []
        for att in attachments[:5]:
            name = getattr(att, "filename", "attachment")
            content_type = getattr(att, "content_type", None) or "unknown type"
            url = getattr(att, "url", None)
            attachment_lines.append(f"{name} ({content_type})" + (f" {url}" if url else ""))
        parts.append("attachments:\n" + "\n".join(f"- {line}" for line in attachment_lines))

    if len(parts) == 1:
        parts.append("no readable content in snapshot")
    return "\n".join(parts)


def snapshot_has_readable_content(snapshot) -> bool:
    if (getattr(snapshot, "content", "") or "").strip():
        return True
    embeds = getattr(snapshot, "embeds", []) or []
    if any((getattr(embed, "title", None) or getattr(embed, "description", None)) for embed in embeds):
        return True
    return bool(getattr(snapshot, "attachments", []) or [])


def forward_source_ref(message) -> tuple[int | None, int, int] | None:
    snapshots = getattr(message, "message_snapshots", None) or []
    if not snapshots:
        return None
    ref = getattr(message, "reference", None)
    channel_id = getattr(ref, "channel_id", None)
    message_id = getattr(ref, "message_id", None)
    if not channel_id or not message_id:
        return None
    return getattr(ref, "guild_id", None), int(channel_id), int(message_id)


def extract_forwarded_context(message) -> str:
    snapshots = getattr(message, "message_snapshots", None) or []
    if not snapshots:
        return ""
    blocks = [
        summarize_message_snapshot(snapshot, idx)
        for idx, snapshot in enumerate(snapshots, 1)
    ]
    source_ref = forward_source_ref(message)
    if source_ref:
        guild_id, channel_id, message_id = source_ref
        ref_bits = []
        if guild_id:
            ref_bits.append(f"guild_id={guild_id}")
        ref_bits.append(f"channel_id={channel_id}")
        ref_bits.append(f"message_id={message_id}")
        blocks.append("[Forward source] " + " ".join(ref_bits))
    return "\n\n".join(blocks)


def visible_message_content(message) -> tuple[str, str]:
    content = message.content or ""
    forwarded_context = extract_forwarded_context(message)
    if forwarded_context:
        if content.strip():
            return f"{content}\n\n{forwarded_context}", forwarded_context
        return forwarded_context, forwarded_context
    return content, ""


def extract_discord_message_refs(text: str) -> list[tuple[int | None, int, int]]:
    from discord_ref_read import extract_discord_message_refs

    return extract_discord_message_refs(text)


def forwarded_snapshot_is_partial(message) -> bool:
    snapshots = getattr(message, "message_snapshots", None) or []
    return bool(snapshots) and not all(
        snapshot_has_readable_content(snapshot) for snapshot in snapshots
    )


def format_dereferenced_message(source_message, *, label: str) -> str:
    from discord_ref_read import format_dereferenced_message

    block = format_dereferenced_message(source_message, label=label)
    forwarded = extract_forwarded_context(source_message)
    if forwarded:
        block = f"{block}\n{forwarded}"
    return block


async def fetch_discord_message_context(
    refs: list[tuple[int | None, int, int]],
    *,
    label: str,
    limit: int = 3,
) -> tuple[str, int]:
    from discord_ref_read import fetch_discord_message_context as _fetch
    from state import client

    normalized = [(g or 0, c, m) for g, c, m in refs]
    return await _fetch(client, normalized, label=label, limit=limit)
