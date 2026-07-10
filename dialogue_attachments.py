"""Dialogue attachment pipeline — gather, forward chain, display names.

Slice 4 of discord_bot.py decomposition (2026-07-10).
Re-exported from discord_bot for backward compatibility.
"""

from __future__ import annotations

from content_fetch import extract_attachments
from state import client


def attachment_display_names(raw_attachments) -> str:
    names = []
    for att in raw_attachments[:5]:
        ct = getattr(att, "content_type", None) or "unknown"
        names.append(f"{getattr(att, 'filename', 'attachment')} ({ct})")
    return ", ".join(names)


async def gather_dialogue_attachments(message):
    """Collect downloadable attachments from the message or its reply parent."""
    raw_attachments = list(message.attachments or [])
    source_label = ""

    ref = getattr(message, "reference", None)
    if not raw_attachments and ref:
        ref_msg = getattr(ref, "resolved", None)
        if ref_msg is None and ref.message_id:
            try:
                ref_msg = await message.channel.fetch_message(ref.message_id)
            except Exception as e:
                print(f"Reply parent fetch failed: {e}")
                ref_msg = None
        if ref_msg and ref_msg.attachments:
            raw_attachments = list(ref_msg.attachments)
            source_label = "reply parent"

    if not raw_attachments:
        return [], [], "", raw_attachments, source_label

    class _AttachmentCarrier:
        attachments = raw_attachments

    extracted = await extract_attachments(_AttachmentCarrier())
    names = [fn for _, _, fn in extracted]
    note_parts = []
    if names:
        prefix = " [attached"
        if source_label:
            prefix += f" from {source_label}"
        note_parts.append(f"{prefix}: {', '.join(names)}]")
    unsupported = [
        att.filename
        for att in raw_attachments
        if att.filename not in names
    ]
    if unsupported:
        note_parts.append(f" [unsupported attachment: {', '.join(unsupported)}]")
    return extracted, names, "".join(note_parts), raw_attachments, source_label


async def attachments_from_forward_chain(source_ref: tuple) -> tuple[list, list[str], str]:
    """When a partial forward hides attachments, walk reply parent of the source message."""
    _guild_id, channel_id, message_id = source_ref
    try:
        channel = await client.fetch_channel(channel_id)
        source_message = await channel.fetch_message(message_id)
        candidates = [source_message]
        ref = getattr(source_message, "reference", None)
        if ref and ref.message_id:
            try:
                candidates.append(await channel.fetch_message(ref.message_id))
            except Exception as e:
                print(f"Forward chain parent fetch failed: {e}")
        for candidate in candidates:
            if not candidate.attachments:
                continue

            class _AttachmentCarrier:
                attachments = list(candidate.attachments)

            extracted = await extract_attachments(_AttachmentCarrier())
            if extracted:
                names = [fn for _, _, fn in extracted]
                label = "forward source" if candidate.id == source_message.id else "forward trigger"
                return extracted, names, f" [attached from {label}: {', '.join(names)}]"
    except Exception as e:
        print(f"Forward chain attachment fetch failed: {e}")
    return [], [], ""
