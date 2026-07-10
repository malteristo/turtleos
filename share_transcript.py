"""Share eddy transcript shaping and export bundles (TURTLE_SPEC §15.6)."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

import discord

from share_targets import ShareTarget, SpaceShareTarget


def filter_share_history(history: list[dict]) -> list[dict]:
    """Drop platform act digests and bare ``!`` commands from share export."""
    cleaned: list[dict] = []
    for entry in history:
        if not isinstance(entry, dict):
            continue
        content = (entry.get("content") or "").strip()
        if content.startswith("[Act: !"):
            continue
        if entry.get("role") == "user" and content.startswith("!"):
            continue
        cleaned.append(entry)
    return cleaned


def _transcript_from_history(history: list[dict]) -> str:
    lines: list[str] = []
    for entry in history:
        role = entry.get("role")
        content = (entry.get("content") or "").strip()
        if not content:
            continue
        label = "Mage" if role == "user" else "Turtle"
        lines.append(f"{label}: {content}")
    return "\n".join(lines)


def label_shared_history(history: list[dict], sharer_address: str) -> list[dict]:
    """Prefix sharer turns so the recipient is not read as the same speaker."""
    tag = (sharer_address or "Sharer").strip()
    prefix = f"[{tag}]: "
    labeled: list[dict] = []
    for entry in history:
        row = dict(entry)
        if row.get("role") == "user":
            content = (row.get("content") or "").strip()
            if content and not re.match(r"^\[[^\]]+\]: ", content):
                row["content"] = prefix + content
        labeled.append(row)
    return labeled


def is_placeholder_eddy_title(title: str) -> bool:
    """True when Discord thread name is not a useful handoff label."""
    t = (title or "").strip().lower()
    if not t:
        return True
    placeholders = {
        "new eddy",
        "blank eddy",
        "new thread",
        "intake",
        "vortex",
        "thread",
        "received eddy",
    }
    if t in placeholders:
        return True
    if t.startswith("hello to turtle"):
        return True
    # Sentence pasted as title, not a short label
    if len(t) > 55 or t.count(" ") >= 8:
        return True
    return False


def build_digest(title: str, history: list[dict]) -> str:
    """2–4 line digest for river act (sync fallback — no model required)."""
    user_bits = [
        (m.get("content") or "").strip()
        for m in history
        if m.get("role") == "user" and (m.get("content") or "").strip()
    ]
    assistant_bits = [
        (m.get("content") or "").strip()
        for m in history
        if m.get("role") == "assistant" and (m.get("content") or "").strip()
    ]
    parts: list[str] = []
    if user_bits:
        parts.append(user_bits[-1][:220])
    if assistant_bits:
        parts.append(assistant_bits[-1][:220])
    if not parts:
        return title[:400]
    body = "\n".join(parts[:3])
    if len(body) > 380:
        body = body[:377] + "…"
    return body


async def synthesize_share_metadata(
    title: str,
    history: list[dict],
) -> tuple[str, str]:
    """LLM summary for river handoff — (display_title, digest). Sync fallback on failure."""
    filtered = filter_share_history(history)
    transcript = _transcript_from_history(filtered)
    if len(transcript) < 40:
        display = title[:100]
        return display, build_digest(display, filtered)

    display_title = title[:100]
    if is_placeholder_eddy_title(title):
        try:
            from eddy_spawn import generate_topic

            generated = await generate_topic(transcript[:2000])
            if generated and not is_placeholder_eddy_title(generated):
                display_title = generated[:100]
        except Exception as exc:
            print(f"Share title synthesis failed: {type(exc).__name__}: {exc}")

    from llm import chat_ollama
    from state import REFLECTION_MODEL

    prompt = (
        "You write share digests for async handoff between practitioners.\n"
        "Given a conversation excerpt, write ONLY 2-4 short lines summarizing:\n"
        "- what the conversation is about (concrete — party logistics, health, planning, etc.)\n"
        "- what question, plan, or tension is alive\n"
        "Use the same language as the conversation. No markdown headers. No speaker labels.\n"
        "Do not quote long passages verbatim."
    )
    try:
        result = await chat_ollama(
            prompt,
            [{"role": "user", "content": f"Topic hint: {display_title}\n\n{transcript[:4500]}"}],
            model=REFLECTION_MODEL,
            num_ctx=8192,
            think=False,
        )
        digest = (result or "").strip()
        if digest and len(digest) > 20:
            if len(digest) > 500:
                digest = digest[:497] + "…"
            return display_title, digest
    except Exception as exc:
        print(f"Share digest synthesis failed: {type(exc).__name__}: {exc}")

    return display_title, build_digest(display_title, filtered)


async def enrich_export_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    """Add synthesized display_title + digest before delivery."""
    enriched = dict(bundle)
    display_title, digest = await synthesize_share_metadata(
        enriched.get("title", ""),
        enriched.get("history") or [],
    )
    enriched["display_title"] = display_title
    enriched["digest"] = digest
    return enriched


def share_label(bundle: dict[str, Any]) -> str:
    return (bundle.get("display_title") or bundle.get("title") or "shared eddy")[:100]


def build_received_share_embed(bundle: dict[str, Any]) -> discord.Embed:
    label = share_label(bundle)
    return discord.Embed(
        title=f"📥 {bundle['sharer_address']} shared a conversation",
        description=f"**{label}**\n\n{bundle['digest']}",
        color=0x3498DB,
    )


def build_space_share_embed(bundle: dict[str, Any]) -> discord.Embed:
    label = share_label(bundle)
    return discord.Embed(
        title=f"📤 {bundle['sharer_address']} shared a conversation",
        description=f"**{label}**\n\n{bundle['digest']}",
        color=0x3498DB,
    )


def build_export_bundle(
    *,
    title: str,
    history: list[dict],
    sharer_id: str | int,
    sharer_key: str,
    sharer_address: str,
    source_thread_id: int,
    share_id: str | None = None,
) -> dict[str, Any]:
    """Export bundle for practitioner share (source eddy unchanged)."""
    history = filter_share_history(history)
    sid = share_id or uuid.uuid4().hex[:12]
    transcript = _transcript_from_history(history)
    digest = build_digest(title, history)
    return {
        "share_id": sid,
        "title": title[:100],
        "display_title": title[:100],
        "digest": digest,
        "transcript": transcript,
        "history": list(history),
        "source_thread_id": str(source_thread_id),
        "sharer_id": str(sharer_id),
        "sharer_key": sharer_key,
        "sharer_address": sharer_address,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def build_export_bundle_from_draft(draft: dict[str, Any]) -> dict[str, Any]:
    bundle = build_export_bundle(
        title=draft["title"],
        history=draft["history"],
        sharer_id=draft["sharer_id"],
        sharer_key=draft["sharer_key"],
        sharer_address=draft["sharer_address"],
        source_thread_id=draft["source_thread_id"],
        share_id=draft.get("share_id"),
    )
    if draft.get("display_title"):
        bundle["display_title"] = draft["display_title"][:100]
    if draft.get("digest"):
        bundle["digest"] = draft["digest"][:500]
    if draft.get("transparency_space_key"):
        bundle["transparency_space_key"] = draft["transparency_space_key"]
    if draft.get("source_origin"):
        bundle["source_origin"] = draft["source_origin"]
    return bundle


def build_preview_embed(draft: dict[str, Any], target: ShareTarget | SpaceShareTarget) -> discord.Embed:
    label = (draft.get("display_title") or draft.get("title") or "this eddy")[:100]
    digest = (draft.get("digest") or "").strip()
    if isinstance(target, SpaceShareTarget):
        body = (
            f"Share **“{label}”** with **{target.address}**?\n\n"
            f"{digest}\n\n"
            "Space members get a digest in the parent river and a **shared eddy** opens "
            "immediately. You are not added to the thread until you choose to open it."
        )
    else:
        body = (
            f"Share **“{label}”** with **{target.address}**?\n\n"
            f"{digest}\n\n"
            "They get this digest in their river and can open a **received eddy** when ready. "
            "Your original eddy stays unchanged."
        )
        if draft.get("transparency_space_key"):
            space_label = str(draft["transparency_space_key"]).replace("_", " ").title()
            body += (
                f"\n\nA **transparency act** will post in **{space_label}** naming you and "
                f"**{target.address}** (digest only — not their private continuation)."
            )
    return discord.Embed(title="Confirm share", description=body[:4096], color=0xF1C40F)


def build_reshare_transparency_embed(
    bundle: dict[str, Any],
    target: ShareTarget,
) -> discord.Embed:
    label = share_label(bundle)
    actor = bundle.get("sharer_address", "Someone")
    digest = (bundle.get("digest") or "").strip()
    body = f"**{actor}** shared this conversation with **{target.address}** · **“{label}”**"
    if digest:
        body += f"\n\n{digest}"
    return discord.Embed(
        title="Re-shared to practitioner",
        description=body[:4096],
        color=0x95A5A6,
    )
