"""Craft Turtle intake — coalesce forwards, gather evidence, register backlog."""

from __future__ import annotations

import asyncio
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

CRAFT_COALESCE_SECONDS = 5.0
CRAFT_BACKLOG = "craft/backlog.md"
CRAFT_INTAKE_DIR = "craft/intake"

_buffers: dict[tuple[int, int], dict] = {}


def is_craft_intake_channel(message) -> bool:
    from mage import resolve_dialogue_channel_id, uses_craft_surface

    if getattr(message.author, "bot", False):
        return False
    return uses_craft_surface(resolve_dialogue_channel_id(message))


def _buffer_key(message) -> tuple[int, int]:
    return message.channel.id, message.author.id


def _slugify(text: str, max_len: int = 48) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    if not slug:
        slug = "craft-friction"
    return slug[:max_len].strip("-")


def merge_craft_messages(messages) -> dict:
    """Merge one or more Discord messages into a single intake payload."""
    parts: list[str] = []
    forward_blocks: list[str] = []
    message_ids: list[int] = []
    author_note = ""

    for msg in messages:
        message_ids.append(msg.id)
        from discord_bot import _extract_forwarded_context, _visible_message_content

        visible, forwarded = _visible_message_content(msg)
        user_text = (msg.content or "").strip()
        if user_text:
            parts.append(user_text)
        if forwarded and forwarded not in forward_blocks:
            forward_blocks.append(forwarded)
        if not author_note:
            author = getattr(msg.author, "display_name", None) or msg.author.name
            author_note = author

    merged_user = "\n\n".join(p for p in parts if p).strip()
    merged_forward = "\n\n".join(forward_blocks).strip()
    if merged_user and merged_forward:
        merged_text = f"{merged_user}\n\n{merged_forward}"
    else:
        merged_text = merged_user or merged_forward

    return {
        "messages": messages,
        "message_ids": message_ids,
        "author": author_note,
        "merged_user": merged_user,
        "merged_forward": merged_forward,
        "merged_text": merged_text,
    }


async def _format_message_line(message, *, max_content: int = 220) -> str:
    author = getattr(message.author, "display_name", None) or message.author.name
    created = message.created_at.strftime("%Y-%m-%d %H:%M UTC") if message.created_at else "?"
    content = (message.content or "").strip().replace("\n", " ")
    if len(content) > max_content:
        content = content[: max_content - 3] + "..."
    bits = [f"{created} **{author}**"]
    if content:
        bits.append(content)
    if message.attachments:
        bits.append(
            "attachments: "
            + ", ".join(f"{a.filename} ({a.content_type or 'unknown'})" for a in message.attachments[:3])
        )
    for embed in message.embeds[:2]:
        if embed.url:
            bits.append(f"embed: {embed.url}")
    return " — ".join(bits)


async def _gather_origin_thread_context(
    client,
    channel_id: int,
    source_message_id: int,
    *,
    history_limit: int = 15,
) -> dict:
    """Deref forward source and scan origin thread/eddy for URLs, triggers, and errors."""
    from discord_bot import _format_dereferenced_message

    out: dict = {
        "origin_channel_id": channel_id,
        "origin_channel_name": None,
        "origin_parent_name": None,
        "source_message_block": "",
        "trigger_message_block": "",
        "thread_excerpt": [],
        "urls_seen": [],
    }
    try:
        channel = await client.fetch_channel(channel_id)
    except Exception as exc:
        out["source_message_block"] = f"Could not fetch origin channel {channel_id}: {type(exc).__name__}: {exc}"
        return out

    out["origin_channel_name"] = getattr(channel, "name", None)
    parent = getattr(channel, "parent", None)
    if parent is not None:
        out["origin_parent_name"] = getattr(parent, "name", None)

    try:
        source_message = await channel.fetch_message(source_message_id)
        out["source_message_block"] = _format_dereferenced_message(
            source_message, label="Forwarded source (Turtle reply)"
        )
        ref = source_message.reference
        if ref and ref.message_id:
            try:
                trigger = await channel.fetch_message(ref.message_id)
                out["trigger_message_block"] = _format_dereferenced_message(
                    trigger, label="Trigger message (practitioner / command)"
                )
                for embed in trigger.embeds:
                    if embed.url and embed.url not in out["urls_seen"]:
                        out["urls_seen"].append(embed.url)
                for token in re.findall(r"https?://\S+", trigger.content or ""):
                    if token not in out["urls_seen"]:
                        out["urls_seen"].append(token.rstrip(">.,)"))
            except Exception as exc:
                out["trigger_message_block"] = (
                    f"Trigger message `{ref.message_id}` unavailable: {type(exc).__name__}: {exc}"
                )
    except Exception as exc:
        out["source_message_block"] = (
            f"Source message `{source_message_id}` unavailable: {type(exc).__name__}: {exc}"
        )

    try:
        async for message in channel.history(limit=history_limit):
            line = await _format_message_line(message)
            lower = (message.content or "").lower()
            if (
                "http" in lower
                or "!fetch" in lower
                or "could not fetch" in lower
                or "nameerror" in lower
                or "didn't load" in lower
                or "didn’t load" in lower
                or "hiccup" in lower
                or message.attachments
            ):
                out["thread_excerpt"].append(line)
            for embed in message.embeds:
                if embed.url and embed.url not in out["urls_seen"]:
                    out["urls_seen"].append(embed.url)
    except Exception as exc:
        out["thread_excerpt"].append(f"Thread history unavailable: {type(exc).__name__}: {exc}")

    out["thread_excerpt"].reverse()
    return out


async def gather_craft_evidence(messages, client) -> dict:
    """Collect deterministic context from turtleOS / Discord for an intake."""
    from discord_bot import (
        _extract_discord_message_refs,
        _fetch_discord_message_context,
        _forward_source_ref,
    )

    merged = merge_craft_messages(messages)
    primary = messages[-1]

    visibility: list[str] = []
    if merged["merged_forward"]:
        visibility.append("forwarded snapshot text present")
    else:
        visibility.append("no forwarded snapshot on intake message(s)")

    deref_refs: list[tuple[int | None, int, int]] = []
    for msg in messages:
        source_ref = _forward_source_ref(msg)
        if source_ref and source_ref not in deref_refs:
            deref_refs.append(source_ref)
        for ref in _extract_discord_message_refs(msg.content or ""):
            if ref not in deref_refs:
                deref_refs.append(ref)

    dereferenced_context = ""
    dereferenced_count = 0
    source_attachments: list[str] = []
    origin_contexts: list[dict] = []

    if deref_refs:
        dereferenced_context, dereferenced_count = await _fetch_discord_message_context(
            deref_refs, label="Source message"
        )
        for guild_id, channel_id, message_id in deref_refs[:3]:
            origin = await _gather_origin_thread_context(client, channel_id, message_id)
            origin_contexts.append(origin)
            try:
                channel = await client.fetch_channel(channel_id)
                source_message = await channel.fetch_message(message_id)
                for att in (source_message.attachments or [])[:5]:
                    source_attachments.append(
                        f"{att.filename} ({att.content_type or 'unknown'})"
                    )
            except Exception as exc:
                source_attachments.append(f"fetch failed for {message_id}: {type(exc).__name__}")

    if dereferenced_count:
        visibility.append(f"dereferenced {dereferenced_count} source message(s)")
    elif deref_refs:
        visibility.append("origin thread inspected via forward source ref")
    else:
        visibility.append("no forward source reference to dereference")

    if origin_contexts:
        first = origin_contexts[0]
        if first.get("origin_channel_name"):
            parent = first.get("origin_parent_name")
            label = first["origin_channel_name"]
            if parent:
                visibility.append(f"origin eddy: #{parent} → **{label}** (channel `{first['origin_channel_id']}`)")
            else:
                visibility.append(f"origin channel: **{label}** (`{first['origin_channel_id']}`)")
        if first.get("urls_seen"):
            visibility.append(f"URLs in thread: {len(first['urls_seen'])} captured")
        if first.get("trigger_message_block"):
            visibility.append("trigger message (reply parent) captured")
        if first.get("thread_excerpt"):
            visibility.append(f"thread excerpt: {len(first['thread_excerpt'])} relevant line(s)")

    snapshot_attachment_gaps: list[str] = []
    for msg in messages:
        snapshots = getattr(msg, "message_snapshots", None) or []
        for idx, snapshot in enumerate(snapshots, 1):
            attachments = getattr(snapshot, "attachments", []) or []
            if not attachments:
                snapshot_attachment_gaps.append(f"forward snapshot {idx}: no attachments in snapshot")

    if source_attachments:
        visibility.append(f"source message attachments: {', '.join(source_attachments)}")
    elif any(getattr(s, "attachments", None) for msg in messages for s in (getattr(msg, "message_snapshots", None) or [])):
        visibility.append("attachments visible in forward snapshot")
    elif snapshot_attachment_gaps:
        visibility.append("original attachments not visible in forward (text-only snapshot)")

    channel_label = getattr(primary.channel, "name", str(primary.channel.id))
    thread_parent = getattr(primary.channel, "parent_id", None)

    return {
        **merged,
        "channel_label": channel_label,
        "thread_parent_id": thread_parent,
        "visibility": visibility,
        "dereferenced_context": dereferenced_context,
        "deref_refs": deref_refs,
        "origin_contexts": origin_contexts,
        "source_attachments": source_attachments,
        "snapshot_attachment_gaps": snapshot_attachment_gaps,
        "registered_at": datetime.now(timezone.utc),
    }


def _intake_id(evidence: dict) -> str:
    basis = "-".join(str(mid) for mid in evidence["message_ids"])
    digest = hashlib.sha1(basis.encode()).hexdigest()[:6]
    day = evidence["registered_at"].strftime("%Y-%m-%d")
    title_basis = evidence["merged_user"] or evidence["merged_forward"] or "craft-friction"
    return f"{day}-{_slugify(title_basis.splitlines()[0][:80])}-{digest}"


def _title_from_evidence(evidence: dict) -> str:
    if evidence["merged_user"]:
        first = evidence["merged_user"].splitlines()[0].strip()
        if len(first) > 120:
            return first[:117] + "..."
        return first
    if evidence["merged_forward"]:
        for line in evidence["merged_forward"].splitlines():
            if line.startswith("content:"):
                text = line[len("content:") :].strip()
                if text:
                    return text[:120]
    return "Craft friction intake"


def _craft_root() -> Path:
    from mage import get_pd

    return Path(get_pd())


def _ensure_backlog(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Craft Backlog\n\n"
        "Queue for the next turtleOS chapter. Craft Turtle appends here on intake; "
        "Spirit on Forge harvests at chapter start.\n\n"
        "## Open\n\n",
        encoding="utf-8",
    )


def write_craft_intake(evidence: dict) -> tuple[str, str]:
    """Write intake artifact and append backlog entry. Returns (intake_rel, intake_id)."""
    intake_id = _intake_id(evidence)
    title = _title_from_evidence(evidence)
    root = _craft_root()
    intake_dir = root / CRAFT_INTAKE_DIR
    intake_dir.mkdir(parents=True, exist_ok=True)
    intake_path = intake_dir / f"{intake_id}.md"
    intake_rel = f"{CRAFT_INTAKE_DIR}/{intake_id}.md"

    lines = [
        f"# Craft Intake — {title}",
        "",
        f"**Intake ID:** `{intake_id}`",
        f"**Registered:** {evidence['registered_at'].isoformat()}",
        f"**Author:** {evidence['author']}",
        f"**Channel:** #{evidence['channel_label']}",
        f"**Discord message IDs:** {', '.join(str(mid) for mid in evidence['message_ids'])}",
        "",
        "## Mage report",
        "",
        evidence["merged_user"] or "_(no separate comment — forward only)_",
        "",
        "## Forwarded context",
        "",
        evidence["merged_forward"] or "_(none)_",
        "",
        "## Source visibility",
        "",
    ]
    for item in evidence["visibility"]:
        lines.append(f"- {item}")
    if evidence["snapshot_attachment_gaps"]:
        lines.append("")
        lines.append("### Snapshot gaps")
        for gap in evidence["snapshot_attachment_gaps"]:
            lines.append(f"- {gap}")

    if evidence["dereferenced_context"]:
        lines.extend(["", "## Dereferenced source", "", evidence["dereferenced_context"]])

    if evidence["deref_refs"]:
        lines.extend(["", "## Source references", ""])
        for guild_id, channel_id, message_id in evidence["deref_refs"]:
            lines.append(
                f"- guild={guild_id} channel={channel_id} message={message_id}"
            )

    for origin in evidence.get("origin_contexts") or []:
        name = origin.get("origin_channel_name") or "unknown"
        ch_id = origin.get("origin_channel_id")
        parent = origin.get("origin_parent_name")
        lines.extend(["", "## Origin eddy", ""])
        if parent:
            lines.append(f"- **River:** #{parent}")
        lines.append(f"- **Thread:** {name}")
        lines.append(f"- **Channel ID:** `{ch_id}` (Discord thread — Spirit can `discord_ops.py read {ch_id}`)")
        if origin.get("urls_seen"):
            lines.extend(["", "### URLs seen in thread", ""])
            for url in origin["urls_seen"]:
                lines.append(f"- {url}")
        if origin.get("trigger_message_block"):
            lines.extend(["", "## Trigger message", "", origin["trigger_message_block"]])
        if origin.get("source_message_block"):
            lines.extend(["", "## Forwarded source (live)", "", origin["source_message_block"]])
        if origin.get("thread_excerpt"):
            lines.extend(["", "## Origin thread excerpt", ""])
            for line in origin["thread_excerpt"]:
                lines.append(f"- {line}")

    lines.extend(
        [
            "",
            "## For Spirit",
            "",
            "Practice impairment and classification are for Forge to confirm during the "
            "next turtleOS chapter. This file preserves evidence gathered at intake time.",
            "",
        ]
    )

    intake_path.write_text("\n".join(lines), encoding="utf-8")

    backlog_path = root / CRAFT_BACKLOG
    _ensure_backlog(backlog_path)
    ref_bits = []
    if evidence["deref_refs"]:
        _g, ch, mid = evidence["deref_refs"][0]
        ref_bits.append(f"source message `{mid}` in channel `{ch}`")
    ref_bits.append(f"intake `{intake_rel}`")
    entry = (
        f"- [{intake_id}] **{title}** — "
        f"{'; '.join(ref_bits)}. "
        f"Visibility: {'; '.join(evidence['visibility'][:3])}.\n"
    )
    with backlog_path.open("a", encoding="utf-8") as handle:
        handle.write(entry)

    return intake_rel, intake_id


def format_craft_ack(evidence: dict, intake_rel: str, intake_id: str) -> str:
    title = _title_from_evidence(evidence)
    visibility = "; ".join(evidence["visibility"][:4]) or "no extra context gathered"
    gathered: list[str] = []
    if evidence["merged_forward"]:
        gathered.append("forwarded snapshot")
    if evidence["dereferenced_context"]:
        gathered.append("dereferenced source message")
    if evidence.get("origin_contexts"):
        oc = evidence["origin_contexts"][0]
        if oc.get("origin_channel_name"):
            gathered.append(f"origin eddy `{oc['origin_channel_name']}`")
        if oc.get("thread_excerpt"):
            gathered.append(f"thread excerpt ({len(oc['thread_excerpt'])} lines)")
    if evidence["source_attachments"]:
        gathered.append(f"source attachments ({len(evidence['source_attachments'])})")
    if evidence["merged_user"]:
        gathered.append("your comment")
    if len(evidence["message_ids"]) > 1:
        gathered.append(f"coalesced {len(evidence['message_ids'])} Discord messages")

    gathered_text = ", ".join(gathered) if gathered else "message text only"

    return (
        f"**Registered** — {title}\n\n"
        f"**Source visibility:** {visibility}\n"
        f"**Gathered:** {gathered_text}\n"
        f"**Intake:** `{intake_rel}`\n"
        f"**Backlog:** `{CRAFT_BACKLOG}`\n\n"
        f"Issue `{intake_id}` is queued for the next turtleOS chapter. "
        f"Spirit on Forge can pick it up from the backlog when you open that arc."
    )


async def process_craft_intake(messages, client) -> str:
    evidence = await gather_craft_evidence(messages, client)
    intake_rel, intake_id = write_craft_intake(evidence)
    return format_craft_ack(evidence, intake_rel, intake_id)


async def _flush_craft_buffer(key: tuple[int, int], client) -> None:
    await asyncio.sleep(CRAFT_COALESCE_SECONDS)
    buf = _buffers.pop(key, None)
    if not buf or not buf.get("messages"):
        return
    messages = buf["messages"]
    try:
        from helpers import split_message

        ack = await process_craft_intake(messages, client)
        channel = messages[-1].channel
        for chunk in split_message(ack):
            await channel.send(chunk)
        print(
            f"Craft intake registered: {len(messages)} message(s) "
            f"from {messages[-1].author.display_name} in #{getattr(channel, 'name', channel.id)}"
        )
    except Exception as exc:
        print(f"Craft intake failed: {type(exc).__name__}: {exc}")
        try:
            await messages[-1].channel.send(
                f"Craft intake failed to register ({type(exc).__name__}). "
                "Spirit can still investigate manually."
            )
        except Exception:
            pass


async def schedule_craft_intake(message, client) -> None:
    """Buffer craft-channel messages; flush one intake after coalesce window."""
    key = _buffer_key(message)
    buf = _buffers.get(key)
    if not buf:
        buf = {"messages": [], "task": None}
    buf["messages"].append(message)
    task = buf.get("task")
    if task and not task.done():
        task.cancel()
    buf["task"] = asyncio.create_task(_flush_craft_buffer(key, client))
    _buffers[key] = buf
