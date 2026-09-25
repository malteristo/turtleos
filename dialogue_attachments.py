"""Dialogue attachment pipeline — gather, forward chain, display names.

Slice 4 of discord_bot.py decomposition (2026-07-10).
Re-exported from discord_bot for backward compatibility.
"""

from __future__ import annotations

from pathlib import Path

import discord

from content_fetch import extract_attachments
import state


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
        channel = await state.client.fetch_channel(channel_id)
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


async def intake_primitive_attachments(
    message,
    parent_channel_id,
    *,
    practice_dir: str,
    actor: str,
) -> tuple[list, str]:
    """Persist/process direct uploads for a source-intake primitive.

    Returns intake results and bounded local extraction context. The caller must
    not pass these sensitive bytes to the generic vision pipeline.
    """
    from core.offload import run_blocking
    from practice_sources import intake_attachment, process_source

    raw = list(getattr(message, "attachments", None) or [])
    if not raw:
        return [], ""

    results = []
    context_blocks = []
    for attachment in raw:
        filename = getattr(attachment, "filename", "attachment")
        card = await _post_intake_status(message.channel, filename, "Saving")
        saved = await intake_attachment(
            practice_dir,
            attachment,
            actor=actor,
            channel_id=parent_channel_id,
            message_id=message.id,
        )
        await _edit_intake_status(card, filename, saved.status, saved.detail)
        result = saved
        if saved.status == "Saved" and saved.source_id:
            await _edit_intake_status(card, filename, "Reading", "local processing")
            result = await run_blocking(
                process_source,
                practice_dir,
                saved.source_id,
                timeout=900,
                name=f"source-{saved.source_id}",
            )
            await _edit_intake_status(card, filename, result.status, result.detail)
        results.append(result)
        if result.manifest:
            context_blocks.append(_manifest_context(practice_dir, result.manifest))
    return results, "\n\n".join(block for block in context_blocks if block)[:12_000]


async def _post_intake_status(channel, filename: str, status: str):
    try:
        return await channel.send(embed=_intake_embed(filename, status, ""))
    except Exception as exc:
        print(f"Source intake status post failed: {type(exc).__name__}: {exc}")
        return None


async def _edit_intake_status(card, filename: str, status: str, detail: str) -> None:
    if card is None:
        return
    try:
        await card.edit(embed=_intake_embed(filename, status, detail))
    except Exception as exc:
        print(f"Source intake status edit failed: {type(exc).__name__}: {exc}")


def _intake_embed(filename: str, status: str, detail: str):
    colors = {
        "Saved": 0x4B8BBE,
        "Reading": 0xD9A441,
        "Ready": 0x4E9F6E,
        "Stored": 0x4B8BBE,
        "Duplicate": 0x7D7D7D,
        "Needs review": 0xD9822B,
        "Failed": 0xB33A3A,
        "Saving": 0xD9A441,
    }
    description = f"**{status}**"
    if detail:
        description += f"\n{detail[:500]}"
    return discord.Embed(
        title=f"Record intake · {filename[:180]}",
        description=description,
        color=colors.get(status, 0x7D7D7D),
    )


def _manifest_context(practice_dir: str, manifest: dict) -> str:
    status = manifest.get("status")
    label = (
        f"[Locally held record source: {manifest.get('filename')} · "
        f"source:{manifest.get('source_id')} · status:{status}]"
    )
    if status != "Ready":
        return label + "\nDo not turn this source into a record fact yet."
    pages = []
    root = Path(practice_dir)
    for item in (manifest.get("extracts") or [])[:8]:
        if item.get("needs_review"):
            continue
        path = root / str(item.get("path") or "")
        if not path.is_file():
            continue
        body = path.read_text(encoding="utf-8", errors="replace")[:3000]
        pages.append(
            f"[{manifest.get('filename')} · p. {item.get('page')} · "
            f"source:{manifest.get('source_id')}]\n{body}"
        )
    return label + ("\n\n" + "\n\n".join(pages) if pages else "")
