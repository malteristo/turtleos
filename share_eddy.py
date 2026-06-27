"""Share eddy — export and delivery (TURTLE_SPEC §15.6 Slice 1 + space Slice 3a)."""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import discord

from helpers import reload_history
from mage import get_mage_key, get_registry, set_practice_context_for_channel


@dataclass(frozen=True)
class ShareTarget:
    mage_key: str
    address: str
    discord_id: str
    channel_id: int


@dataclass(frozen=True)
class SpaceShareTarget:
    space_key: str
    address: str
    channel_id: int


def river_channel_for_mage(mage_key: str) -> int | None:
    """Parent river / hosted-river channel id for a mage registry key."""
    for ch_id_str, entry in get_registry().get("channels", {}).items():
        if not isinstance(entry, dict):
            continue
        if entry.get("mage") != mage_key:
            continue
        if entry.get("type") not in ("river", "hosted-river"):
            continue
        try:
            return int(ch_id_str)
        except (ValueError, TypeError):
            continue
    return None


def runtime_dir_for_mage(mage_key: str) -> str:
    mage = get_registry().get("mages", {}).get(mage_key, {})
    raw = mage.get("runtime_dir") or mage.get("practice_dir") or f"~/workshops/{mage_key}"
    return os.path.expanduser(raw)


def practice_dir_for_mage(mage_key: str) -> str:
    mage = get_registry().get("mages", {}).get(mage_key, {})
    raw = mage.get("practice_dir") or f"~/workshops/{mage_key}"
    return os.path.expanduser(raw)


def list_practitioner_targets(
    sender_mage_key: str,
    sender_discord_id: str | int,
) -> list[ShareTarget]:
    """Slice 1 picker: every other registered mage with a sovereign river channel."""
    sender_id = str(sender_discord_id)
    targets: list[ShareTarget] = []
    for mage_key, mage in get_registry().get("mages", {}).items():
        if mage_key == sender_mage_key:
            continue
        discord_id = mage.get("discord_id")
        if not discord_id or str(discord_id) == sender_id:
            continue
        channel_id = river_channel_for_mage(mage_key)
        if not channel_id:
            continue
        targets.append(
            ShareTarget(
                mage_key=mage_key,
                address=mage.get("address", mage_key.replace("_", " ").title()),
                discord_id=str(discord_id),
                channel_id=channel_id,
            )
        )
    return sorted(targets, key=lambda t: t.address.lower())


def runtime_dir_for_space(space_key: str) -> str:
    space = get_registry().get("spaces", {}).get(space_key, {})
    raw = space.get("runtime_dir") or space.get("practice_dir") or f"~/workshops/{space_key}"
    return os.path.expanduser(raw)


def shared_river_channel_for_space(space_key: str) -> int | None:
    """Parent shared-river channel id for a registry space key."""
    for ch_id_str, entry in get_registry().get("channels", {}).items():
        if not isinstance(entry, dict):
            continue
        if entry.get("type") != "shared-river":
            continue
        if entry.get("mage") != space_key:
            continue
        try:
            return int(ch_id_str)
        except (ValueError, TypeError):
            continue
    return None


def _sender_may_share_to_space(sender_mage_key: str, space: dict[str, Any]) -> bool:
    policy = space.get("share_policy", "members_only")
    members = space.get("members") or []
    if policy == "all_practitioners":
        return True
    if policy == "members_only":
        return sender_mage_key in members
    if isinstance(policy, dict):
        explicit = policy.get("explicit")
        if isinstance(explicit, list):
            return sender_mage_key in explicit
    if isinstance(policy, list):
        return sender_mage_key in policy
    return sender_mage_key in members


def list_space_targets(sender_mage_key: str) -> list[SpaceShareTarget]:
    """Slice 3a picker: registry spaces where sender satisfies share_policy."""
    targets: list[SpaceShareTarget] = []
    for space_key, space in get_registry().get("spaces", {}).items():
        if not isinstance(space, dict):
            continue
        if not _sender_may_share_to_space(sender_mage_key, space):
            continue
        channel_id = shared_river_channel_for_space(space_key)
        if not channel_id:
            continue
        address = (space.get("address") or space_key.replace("_", " ").title())[:100]
        targets.append(
            SpaceShareTarget(
                space_key=space_key,
                address=address,
                channel_id=channel_id,
            )
        )
    return sorted(targets, key=lambda t: t.address.lower())


def space_member_discord_ids(
    space_key: str,
    *,
    exclude_id: str | int | None = None,
) -> list[str]:
    """Discord user ids for space members (optional exclude — e.g. sharer)."""
    exclude = str(exclude_id) if exclude_id is not None else None
    space = get_registry().get("spaces", {}).get(space_key, {})
    ids: list[str] = []
    for member_key in space.get("members") or []:
        mage = get_registry().get("mages", {}).get(member_key, {})
        uid = mage.get("discord_id")
        if not uid:
            continue
        uid_str = str(uid)
        if exclude and uid_str == exclude:
            continue
        ids.append(uid_str)
    return ids


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


def resolve_eddy_thread_cfg(
    thread_id: int,
    parent_id: int | None,
    cfg: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Merge in-memory thread config with persisted share-eddy metadata."""
    if cfg and cfg.get("origin") in ("received", "shared"):
        return cfg
    disk = _received_eddy_notify_config(thread_id, parent_id)
    if disk and disk.get("origin") in ("received", "shared"):
        merged = dict(cfg or {})
        merged.update(disk)
        return merged
    return cfg


def received_eddy_context_lines(cfg: dict[str, Any]) -> list[str]:
    """Runtime scaffolding so Turtle continues with the recipient, not the sharer."""
    from mage import get_mage_name

    sharer = (cfg.get("from_sharer") or "another practitioner").strip()
    recipient = get_mage_name()
    return [
        f"- **Received eddy:** **{sharer}** shared their conversation with you. "
        f"You are with **{recipient}** now — **{sharer} is not in this thread**.",
        f"- **Shared history:** Turns labeled `[{sharer}]` are from the original eddy; "
        f"messages without that label are from **{recipient}**.",
        "- **Conduct:** Continue from the shared topic with **"
        f"{recipient}** as your practitioner. Do not welcome them as \"joining\" or "
        f"say \"we\" when you mean you and **{sharer}** — they are not here. "
        "Answer from the shared context; the recipient may explore, disagree, or take it elsewhere.",
    ]


def shared_eddy_context_lines(cfg: dict[str, Any]) -> list[str]:
    """Runtime scaffolding for space-tagged shared eddies."""
    sharer = (cfg.get("from_sharer") or "another practitioner").strip()
    space_label = (cfg.get("space_key") or "this space").replace("_", " ").title()
    return [
        f"- **Shared eddy:** **{sharer}** shared a conversation with **{space_label}**. "
        f"**{sharer} is not in this thread** unless they open it themselves.",
        f"- **Shared history:** Turns labeled `[{sharer}]` are from the original eddy; "
        "other messages are from space members who joined.",
        "- **Conduct:** Facilitate the shared topic for whoever is present. Do not welcome "
        f"**{sharer}** as if they are here — they may read later. Turtle-only opening "
        "content does not count as a member reply.",
    ]


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


def find_received_thread_for_share(runtime_dir: str, share_id: str) -> int | None:
    """Return thread id if this share was already continued (idempotent re-click)."""
    received = Path(runtime_dir) / "share" / "received"
    if not received.is_dir():
        return None
    for path in received.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if data.get("share_id") == share_id:
            try:
                return int(path.stem)
            except ValueError:
                continue
    return None


async def _fetch_thread(client: discord.Client, thread_id: int) -> discord.Thread | None:
    ch = client.get_channel(thread_id)
    if ch is None:
        try:
            ch = await client.fetch_channel(thread_id)
        except discord.HTTPException:
            return None
    return ch  # type: ignore[return-value]


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


def _share_dir(runtime_dir: str, sub: str) -> Path:
    path = Path(runtime_dir) / "share" / sub
    path.mkdir(parents=True, exist_ok=True)
    return path


def inbox_path(runtime_dir: str, share_id: str) -> Path:
    return _share_dir(runtime_dir, "inbox") / f"{share_id}.json"


def pending_path(runtime_dir: str, author_id: int, thread_id: int) -> Path:
    return _share_dir(runtime_dir, "pending") / f"{author_id}_{thread_id}.json"


def received_thread_path(runtime_dir: str, thread_id: int) -> Path:
    return _share_dir(runtime_dir, "received") / f"{thread_id}.json"


def save_received_thread_config(runtime_dir: str, thread_id: int, cfg: dict[str, Any]) -> None:
    """Persist share-eddy notify metadata for cross-process reads (River vs Turtle bots)."""
    payload = {
        "origin": cfg.get("origin"),
        "share_id": cfg.get("share_id"),
        "share_creator": cfg.get("share_creator"),
        "sharer_key": cfg.get("sharer_key"),
        "share_recipient_id": cfg.get("share_recipient_id"),
        "share_notify_pending": cfg.get("share_notify_pending", False),
        "topic": cfg.get("topic"),
        "from_sharer": cfg.get("from_sharer"),
        "space_key": cfg.get("space_key"),
    }
    received_thread_path(runtime_dir, thread_id).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_received_thread_config(runtime_dir: str, thread_id: int) -> dict[str, Any] | None:
    path = received_thread_path(runtime_dir, thread_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def mark_received_thread_notified(runtime_dir: str, thread_id: int) -> None:
    path = received_thread_path(runtime_dir, thread_id)
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        path.unlink(missing_ok=True)
        return
    if not isinstance(data, dict):
        path.unlink(missing_ok=True)
        return
    data["share_notify_pending"] = False
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_inbox_bundle(runtime_dir: str, bundle: dict[str, Any]) -> Path:
    path = inbox_path(runtime_dir, bundle["share_id"])
    path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_inbox_bundle(runtime_dir: str, share_id: str) -> dict[str, Any] | None:
    path = inbox_path(runtime_dir, share_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def write_pending_draft(runtime_dir: str, author_id: int, thread_id: int, draft: dict) -> None:
    pending_path(runtime_dir, author_id, thread_id).write_text(
        json.dumps(draft, ensure_ascii=False),
        encoding="utf-8",
    )


def load_pending_draft(runtime_dir: str, author_id: int, thread_id: int) -> dict | None:
    path = pending_path(runtime_dir, author_id, thread_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def clear_pending_draft(runtime_dir: str, author_id: int, thread_id: int) -> None:
    pending_path(runtime_dir, author_id, thread_id).unlink(missing_ok=True)


def _active_acts_path(runtime_dir: str) -> Path:
    return _share_dir(runtime_dir, ".") / "active_river_acts.json"


def _load_active_share_acts(runtime_dir: str) -> list[dict[str, Any]]:
    path = _active_acts_path(runtime_dir)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    acts = data.get("acts") if isinstance(data, dict) else data
    return acts if isinstance(acts, list) else []


def _save_active_share_acts(runtime_dir: str, acts: list[dict[str, Any]]) -> None:
    path = _active_acts_path(runtime_dir)
    path.write_text(json.dumps({"acts": acts}, ensure_ascii=False, indent=2), encoding="utf-8")


async def supersede_stale_share_acts(
    client: discord.Client,
    channel: discord.abc.Messageable,
    runtime_dir: str,
    *,
    keep_share_id: str,
    keep_message_id: int,
) -> None:
    """Track active share acts; only strip Continue when re-delivering the same share."""
    prior = _load_active_share_acts(runtime_dir)
    kept: list[dict[str, Any]] = []
    for act in prior:
        sid = act.get("share_id")
        mid = act.get("message_id")
        if sid == keep_share_id and mid:
            try:
                msg = await channel.fetch_message(int(mid))
                await msg.edit(view=None)
            except discord.HTTPException:
                pass
            continue
        if sid and sid != keep_share_id:
            kept.append(act)
    kept.append({"share_id": keep_share_id, "message_id": str(keep_message_id)})
    _save_active_share_acts(runtime_dir, kept)


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
    return discord.Embed(title="Confirm share", description=body[:4096], color=0xF1C40F)


async def maybe_post_share_rename_offer(
    thread: discord.Thread,
    draft: dict[str, Any],
    client: discord.Client,
    *,
    suggested: str | None = None,
) -> None:
    """Contextual opt-in rename in the source eddy when title lags the share label."""
    from eddy_flow_library import post_flow_rename_offer

    proposed = (suggested or draft.get("display_title") or "").strip()[:100]
    current = (draft.get("title") or thread.name or "").strip()
    if not proposed or proposed.lower() == current.lower():
        return
    parent_id = thread.parent_id or draft.get("parent_id")
    if not parent_id:
        return
    await post_flow_rename_offer(thread, thread.id, parent_id, proposed, client)


async def notify_sharer_first_peer_reply(
    message: discord.Message,
    cfg: dict[str, Any],
) -> None:
    """@ + River act in sharer's river when recipient first speaks in received eddy."""
    from bar_anchor import channel_for_client
    from river_handler import _append_chronicle, _river_client_for_channel
    from state import client as turtle_client

    sharer_key = cfg.get("sharer_key")
    sharer_id = cfg.get("share_creator")
    if not sharer_key or not sharer_id:
        return

    sharer_channel_id = river_channel_for_mage(sharer_key)
    if not sharer_channel_id:
        return

    label = (cfg.get("topic") or message.channel.name)[:100]
    peer = message.author.display_name
    jump = message.channel.jump_url if isinstance(message.channel, discord.Thread) else ""

    client = turtle_client
    channel = client.get_channel(sharer_channel_id)
    if channel is None:
        channel = await client.fetch_channel(sharer_channel_id)

    act_client = _river_client_for_channel(channel) or client
    ch = await channel_for_client(channel, act_client)

    mention = f"<@{sharer_id}>"
    embed = discord.Embed(
        description=(
            f"💬 **{peer}** replied in shared eddy **{label}**"
            + (f" · [open thread]({jump})" if jump else "")
        ),
        color=0x3498DB,
    )
    await ch.send(
        mention,
        embed=embed,
        allowed_mentions=discord.AllowedMentions(users=True),
    )

    sender_pd = practice_dir_for_mage(sharer_key)
    _append_chronicle(
        sender_pd,
        f"💬 {peer} replied in shared eddy · {label}",
        {"thread_id": str(message.channel.id), "jump_url": jump},
    )


def _received_eddy_notify_config(thread_id: int, parent_id: int | None) -> dict[str, Any] | None:
    """Load share-eddy notify config from in-memory or disk (split River/Turtle bots)."""
    from commands import thread_configs

    cfg = thread_configs.get(thread_id)
    if cfg and cfg.get("origin") in ("received", "shared"):
        return cfg
    if not parent_id:
        return None
    set_practice_context_for_channel(parent_id)
    from mage import get_runtime_dir

    return load_received_thread_config(get_runtime_dir(), thread_id)


def should_notify_sharer_on_first_peer_reply(
    cfg: dict[str, Any],
    author_id: str | int,
) -> bool:
    """True when this practitioner message should trigger sharer notify (received or shared)."""
    if not cfg.get("share_notify_pending"):
        return False
    origin = cfg.get("origin")
    aid = str(author_id)
    if origin == "received":
        return aid == str(cfg.get("share_recipient_id", ""))
    if origin == "shared":
        if aid == str(cfg.get("share_creator", "")):
            return False
        space_key = cfg.get("space_key")
        if space_key:
            members = space_member_discord_ids(space_key)
            if members and aid not in members:
                return False
        return True
    return False


async def maybe_notify_sharer_on_first_peer_reply(message: discord.Message) -> None:
    from commands import thread_configs
    from eddy_lifecycle_bar import is_practitioner_input

    if not isinstance(message.channel, discord.Thread):
        return
    if message.author.bot or not is_practitioner_input(message):
        return

    parent_id = message.channel.parent_id
    cfg = _received_eddy_notify_config(message.channel.id, parent_id)
    if not cfg or cfg.get("origin") not in ("received", "shared"):
        return
    if not should_notify_sharer_on_first_peer_reply(cfg, message.author.id):
        return

    cfg["share_notify_pending"] = False
    in_memory = thread_configs.get(message.channel.id)
    if in_memory is not None:
        in_memory["share_notify_pending"] = False
    runtime_dir = None
    if parent_id:
        set_practice_context_for_channel(parent_id)
        from mage import get_runtime_dir

        runtime_dir = get_runtime_dir()
        mark_received_thread_notified(runtime_dir, message.channel.id)

    try:
        await notify_sharer_first_peer_reply(message, cfg)
    except Exception as exc:
        cfg["share_notify_pending"] = True
        if in_memory is not None:
            in_memory["share_notify_pending"] = True
        if runtime_dir:
            save_received_thread_config(runtime_dir, message.channel.id, cfg)
        print(f"Share sharer notify failed: {type(exc).__name__}: {exc}")


async def deliver_practitioner_share(
    bundle: dict[str, Any],
    target: ShareTarget,
    *,
    client: discord.Client,
) -> discord.Message | None:
    """Post recipient @+River act and write inbox bundle."""
    from bar_anchor import channel_for_client
    from river_handler import _append_chronicle, _river_client_for_channel

    bundle = dict(bundle)
    bundle["recipient_mage_key"] = target.mage_key
    bundle["recipient_discord_id"] = target.discord_id
    bundle["recipient_channel_id"] = str(target.channel_id)

    recipient_runtime = runtime_dir_for_mage(target.mage_key)
    write_inbox_bundle(recipient_runtime, bundle)

    recipient_channel = client.get_channel(target.channel_id)
    if recipient_channel is None:
        recipient_channel = await client.fetch_channel(target.channel_id)

    act_client = _river_client_for_channel(recipient_channel) or client
    ch = await channel_for_client(recipient_channel, act_client)

    label = share_label(bundle)
    embed = build_received_share_embed(bundle)
    view = ShareContinueView(bundle["share_id"], target.channel_id)
    act_client.add_view(view)

    mention = f"<@{target.discord_id}>"
    msg = await ch.send(
        f"{mention} — tap **Continue** when you are ready to pick this up in your river.",
        embed=embed,
        view=view,
        allowed_mentions=discord.AllowedMentions(users=True),
    )

    await supersede_stale_share_acts(
        act_client,
        ch,
        recipient_runtime,
        keep_share_id=bundle["share_id"],
        keep_message_id=msg.id,
    )

    sender_pd = practice_dir_for_mage(bundle["sharer_key"])
    _append_chronicle(
        sender_pd,
        f"📤 Shared to {target.address}: \"{label}\"",
        {"share_id": bundle["share_id"], "target": target.mage_key},
    )
    return msg


async def materialize_space_shared_eddy(
    channel: discord.abc.GuildChannel,
    bundle: dict[str, Any],
    *,
    client: discord.Client,
) -> discord.Thread:
    """Create space-tagged shared eddy at confirm — sibling thread; digest stays in parent."""
    from commands import thread_configs
    from eddy_spawn import (
        add_users_to_thread,
        ensure_shared_river_parent_access,
        river_add_turtle_to_eddy,
    )
    from helpers import sync_history
    from mage import (
        get_channel_default_context,
        get_effective_attunement,
        get_thread_member_ids,
        set_practice_context_for_channel,
    )
    from thread_registry import register_thread
    from state import EDDY_TYPES, TURTLE_MODEL, dialogue_histories

    set_practice_context_for_channel(channel.id)
    from mage import get_runtime_dir

    runtime_dir = get_runtime_dir()
    label = share_label(bundle)
    eddy_archive = EDDY_TYPES.get("standard", {}).get("archive_minutes", 10080)
    channel_att = get_effective_attunement(channel.id)
    if channel_att == "native":
        model_id = TURTLE_MODEL
        use_api = False
        attunement = "native"
    else:
        from llm import resolve_model

        model_id, use_api = resolve_model("local")
        attunement = "semi"

    thread = await channel.create_thread(
        name=label[:100],
        auto_archive_duration=eddy_archive,
        type=discord.ChannelType.public_thread,
    )

    await river_add_turtle_to_eddy(thread)

    context_type = get_channel_default_context(channel.id) or bundle.get("space_key")
    thread_configs[thread.id] = {
        "model": model_id,
        "use_api": use_api,
        "attunement": attunement,
        "model_label": "local",
        "eddy_type": "standard",
        "context_type": context_type,
        "topic": label,
        "origin": "shared",
        "space_key": bundle.get("space_key"),
        "share_id": bundle.get("share_id"),
        "from_sharer": bundle.get("sharer_address", "someone"),
        "share_creator": bundle.get("sharer_id"),
        "sharer_key": bundle.get("sharer_key"),
        "share_notify_pending": True,
        "created": datetime.now(timezone.utc),
        "native_vanilla": channel_att == "native",
        "presence_posted": False,
    }

    history = filter_share_history(bundle.get("history") or [])
    sharer_address = bundle.get("sharer_address", "someone")
    history = label_shared_history(history, sharer_address)
    if history:
        dialogue_histories[thread.id] = list(history)
        sync_history(thread.id)

    await thread.send(embed=build_space_share_embed(bundle))
    await thread.send(
        f"-# 📤 From **{bundle.get('sharer_address', 'someone')}** · shared conversation ready — "
        "Turtle has the full thread; members can jump in when ready.",
        silent=True,
    )

    parent_name = channel.name if hasattr(channel, "name") else "river"
    register_thread(
        thread.id,
        label,
        parent_channel=parent_name,
        model="local",
        attunement=attunement,
        eddy_type="standard",
    )

    await ensure_shared_river_parent_access(channel)
    sharer_id = str(bundle.get("sharer_id", ""))
    member_ids = [
        uid
        for uid in get_thread_member_ids(channel.id)
        if str(uid) != sharer_id
    ]
    await add_users_to_thread(thread, member_ids)

    save_received_thread_config(runtime_dir, thread.id, thread_configs[thread.id])

    outbox = _share_dir(runtime_dir, "outbox") / f"{bundle.get('share_id')}.json"
    outbox.write_text(
        json.dumps(
            {
                **bundle,
                "shared_thread_id": str(thread.id),
                "space_key": bundle.get("space_key"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return thread


async def deliver_space_share(
    bundle: dict[str, Any],
    target: SpaceShareTarget,
    *,
    client: discord.Client,
) -> discord.Message | None:
    """Post space parent digest act, materialize shared eddy, notify members."""
    from bar_anchor import channel_for_client
    from river_handler import _append_chronicle, _river_client_for_channel

    bundle = dict(bundle)
    bundle["space_key"] = target.space_key
    bundle["target_kind"] = "space"

    space_channel = client.get_channel(target.channel_id)
    if space_channel is None:
        space_channel = await client.fetch_channel(target.channel_id)

    act_client = _river_client_for_channel(space_channel) or client
    if act_client is not client:
        resolved = act_client.get_channel(target.channel_id)
        if resolved is None:
            resolved = await act_client.fetch_channel(target.channel_id)
        space_channel = resolved

    set_practice_context_for_channel(target.channel_id)
    thread = await materialize_space_shared_eddy(
        space_channel,
        bundle,
        client=act_client,
    )

    ch = await channel_for_client(space_channel, act_client)

    label = share_label(bundle)
    embed = build_space_share_embed(bundle)
    if thread.jump_url:
        embed.add_field(name="Shared eddy", value=f"[Open thread]({thread.jump_url})", inline=False)

    member_ids = space_member_discord_ids(target.space_key, exclude_id=bundle.get("sharer_id"))
    mention = " ".join(f"<@{uid}>" for uid in member_ids)
    lead = (
        f"{mention} — **{bundle['sharer_address']}** shared **“{label}”** with **{target.address}**."
        if mention
        else f"**{bundle['sharer_address']}** shared **“{label}”** with **{target.address}**."
    )
    msg = await ch.send(
        lead,
        embed=embed,
        allowed_mentions=discord.AllowedMentions(users=True),
    )

    sender_pd = practice_dir_for_mage(bundle["sharer_key"])
    _append_chronicle(
        sender_pd,
        f'📤 Shared to {target.address}: "{label}"',
        {
            "share_id": bundle["share_id"],
            "target": target.space_key,
            "thread_id": str(thread.id),
            "jump_url": thread.jump_url,
        },
    )
    return msg


async def materialize_received_eddy(
    interaction: discord.Interaction,
    share_id: str,
    parent_channel_id: int,
) -> discord.Thread | None:
    """Open received eddy — sibling thread; river digest stays untouched.

    Uses channel.create_thread (not message.create_thread) so the digest act
    remains visible in the river on mobile. Digest is reposted inside the eddy.
    """
    from commands import thread_configs
    from eddy_spawn import river_add_turtle_to_eddy
    from helpers import sync_history
    from state import EDDY_TYPES, TURTLE_MODEL, dialogue_histories
    from thread_registry import register_thread

    set_practice_context_for_channel(parent_channel_id)
    from mage import get_runtime_dir

    runtime_dir = get_runtime_dir()
    bundle = load_inbox_bundle(runtime_dir, share_id)
    if not bundle:
        return None

    if str(interaction.user.id) != str(bundle.get("recipient_discord_id", "")):
        raise PermissionError("Only the recipient can continue this share.")

    label = share_label(bundle)
    eddy_archive = EDDY_TYPES.get("standard", {}).get("archive_minutes", 10080)

    existing_id = find_received_thread_for_share(runtime_dir, share_id)
    if existing_id:
        thread = await _fetch_thread(interaction.client, existing_id)
        if thread is not None:
            try:
                await thread.add_user(interaction.user)
            except discord.HTTPException:
                pass
            return thread

    channel = interaction.channel
    if channel is None or not hasattr(channel, "create_thread"):
        return None

    thread = await channel.create_thread(
        name=label[:100],
        auto_archive_duration=eddy_archive,
        type=discord.ChannelType.public_thread,
    )

    await river_add_turtle_to_eddy(thread)
    try:
        await thread.add_user(interaction.user)
    except discord.HTTPException:
        pass

    thread_configs[thread.id] = {
        "model": TURTLE_MODEL,
        "use_api": False,
        "attunement": "native",
        "model_label": "local",
        "eddy_type": "standard",
        "context_type": None,
        "topic": label,
        "origin": "received",
        "share_id": share_id,
        "from_sharer": bundle.get("sharer_address", "someone"),
        "share_creator": bundle.get("sharer_id"),
        "sharer_key": bundle.get("sharer_key"),
        "share_recipient_id": bundle.get("recipient_discord_id"),
        "share_notify_pending": True,
        "created": datetime.now(timezone.utc),
        "native_vanilla": True,
        "presence_posted": False,
    }

    history = filter_share_history(bundle.get("history") or [])
    sharer_address = bundle.get("sharer_address", "someone")
    history = label_shared_history(history, sharer_address)
    if history:
        dialogue_histories[thread.id] = list(history)
        sync_history(thread.id)

    await thread.send(embed=build_received_share_embed(bundle))
    await thread.send(
        f"-# 📥 From **{bundle.get('sharer_address', 'someone')}** · shared conversation ready — "
        "Turtle has the full thread; say hello when you want to continue.",
        silent=True,
    )

    parent_name = interaction.channel.name if interaction.channel else "river"
    register_thread(
        thread.id,
        label,
        parent_channel=parent_name,
        model="local",
        attunement="native",
        eddy_type="standard",
    )

    save_received_thread_config(runtime_dir, thread.id, thread_configs[thread.id])

    return thread


async def continue_received_share(
    interaction: discord.Interaction,
    share_id: str,
    parent_channel_id: int,
) -> discord.Thread | None:
    """Continue contract: thread chip on digest is success feedback; silent on happy path."""
    if interaction.channel and interaction.channel.id != parent_channel_id:
        await interaction.response.send_message("Wrong channel.", ephemeral=True)
        return None
    try:
        await interaction.response.defer(ephemeral=True)
        thread = await materialize_received_eddy(
            interaction,
            share_id,
            parent_channel_id,
        )
    except PermissionError as exc:
        await interaction.followup.send(str(exc), ephemeral=True)
        return None
    except Exception as exc:
        await interaction.followup.send(
            f"Could not open received eddy: {type(exc).__name__}: {exc}",
            ephemeral=True,
        )
        return None
    if not thread:
        return None
    try:
        await interaction.delete_original_response()
    except discord.HTTPException:
        pass
    return thread


class ShareTargetSelect(discord.ui.Select):
    def __init__(
        self,
        *,
        thread_id: int,
        author_id: int,
        targets: list[ShareTarget],
    ):
        options = [
            discord.SelectOption(
                label=t.address[:100],
                value=t.mage_key,
                description=f"Share to {t.address}"[:100],
            )
            for t in targets[:25]
        ]
        super().__init__(
            placeholder="Choose a practitioner…",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"share:select:{thread_id}:{author_id}",
        )
        self._thread_id = thread_id
        self._author_id = author_id
        self._targets = {t.mage_key: t for t in targets}

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self._author_id:
            await interaction.response.send_message(
                "Only the person who started Share can pick a recipient.",
                ephemeral=True,
            )
            return
        target = self._targets.get(self.values[0])
        if not target:
            await interaction.response.send_message("Unknown recipient.", ephemeral=True)
            return

        from mage import get_runtime_dir

        draft = load_pending_draft(get_runtime_dir(), self._author_id, self._thread_id)
        if not draft:
            await interaction.response.send_message(
                "Share session expired — run `!share` again.",
                ephemeral=True,
            )
            return
        draft["target_mage_key"] = target.mage_key
        draft["target_address"] = target.address
        draft["target_discord_id"] = target.discord_id
        draft["target_channel_id"] = target.channel_id
        draft["target_kind"] = "practitioner"
        draft["parent_id"] = interaction.channel.parent_id
        write_pending_draft(get_runtime_dir(), self._author_id, self._thread_id, draft)

        await interaction.response.defer()
        try:
            bundle = build_export_bundle(
                title=draft["title"],
                history=draft["history"],
                sharer_id=draft["sharer_id"],
                sharer_key=draft["sharer_key"],
                sharer_address=draft["sharer_address"],
                source_thread_id=draft["source_thread_id"],
                share_id=draft.get("share_id"),
            )
            bundle = await enrich_export_bundle(bundle)
        except Exception as exc:
            await interaction.followup.send(
                f"Could not summarize for share: {type(exc).__name__}: {exc}",
                ephemeral=True,
            )
            return

        draft["display_title"] = bundle["display_title"]
        draft["digest"] = bundle["digest"]
        write_pending_draft(get_runtime_dir(), self._author_id, self._thread_id, draft)

        preview = SharePreviewView(self._thread_id, self._author_id, target)
        embed = build_preview_embed(draft, target)
        try:
            if interaction.message:
                await interaction.message.edit(embed=embed, view=preview)
            else:
                await interaction.edit_original_response(embed=embed, view=preview)
        except discord.HTTPException as exc:
            print(f"Share preview edit failed: {type(exc).__name__}: {exc}")
            await interaction.followup.send(
                f"Could not show share preview: {exc}",
                ephemeral=True,
            )
            return

        if isinstance(interaction.channel, discord.Thread) and is_placeholder_eddy_title(
            draft.get("title", "")
        ):
            await maybe_post_share_rename_offer(interaction.channel, draft, interaction.client)


class ShareSpaceSelect(discord.ui.Select):
    def __init__(
        self,
        *,
        thread_id: int,
        author_id: int,
        targets: list[SpaceShareTarget],
    ):
        options = [
            discord.SelectOption(
                label=t.address[:100],
                value=t.space_key,
                description=f"Share to {t.address}"[:100],
            )
            for t in targets[:25]
        ]
        super().__init__(
            placeholder="Choose a space…",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"share:space:{thread_id}:{author_id}",
        )
        self._thread_id = thread_id
        self._author_id = author_id
        self._targets = {t.space_key: t for t in targets}

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self._author_id:
            await interaction.response.send_message(
                "Only the person who started Share can pick a space.",
                ephemeral=True,
            )
            return
        target = self._targets.get(self.values[0])
        if not target:
            await interaction.response.send_message("Unknown space.", ephemeral=True)
            return

        from mage import get_runtime_dir

        draft = load_pending_draft(get_runtime_dir(), self._author_id, self._thread_id)
        if not draft:
            await interaction.response.send_message(
                "Share session expired — run `!share` again.",
                ephemeral=True,
            )
            return
        draft["target_space_key"] = target.space_key
        draft["target_address"] = target.address
        draft["target_channel_id"] = target.channel_id
        draft["target_kind"] = "space"
        draft["parent_id"] = interaction.channel.parent_id
        write_pending_draft(get_runtime_dir(), self._author_id, self._thread_id, draft)

        await interaction.response.defer()
        try:
            bundle = build_export_bundle(
                title=draft["title"],
                history=draft["history"],
                sharer_id=draft["sharer_id"],
                sharer_key=draft["sharer_key"],
                sharer_address=draft["sharer_address"],
                source_thread_id=draft["source_thread_id"],
                share_id=draft.get("share_id"),
            )
            bundle = await enrich_export_bundle(bundle)
        except Exception as exc:
            await interaction.followup.send(
                f"Could not summarize for share: {type(exc).__name__}: {exc}",
                ephemeral=True,
            )
            return

        draft["display_title"] = bundle["display_title"]
        draft["digest"] = bundle["digest"]
        write_pending_draft(get_runtime_dir(), self._author_id, self._thread_id, draft)

        preview = SharePreviewView(self._thread_id, self._author_id, target)
        embed = build_preview_embed(draft, target)
        try:
            if interaction.message:
                await interaction.message.edit(embed=embed, view=preview)
            else:
                await interaction.edit_original_response(embed=embed, view=preview)
        except discord.HTTPException as exc:
            print(f"Share preview edit failed: {type(exc).__name__}: {exc}")
            await interaction.followup.send(
                f"Could not show share preview: {exc}",
                ephemeral=True,
            )
            return

        if isinstance(interaction.channel, discord.Thread) and is_placeholder_eddy_title(
            draft.get("title", "")
        ):
            await maybe_post_share_rename_offer(interaction.channel, draft, interaction.client)


class ShareEditModal(discord.ui.Modal, title="Edit share preview"):
    """Edit title and digest — submit to confirm; dismiss modal to cancel."""

    def __init__(
        self,
        thread_id: int,
        author_id: int,
        target: ShareTarget | SpaceShareTarget,
        display_title: str,
        digest: str,
    ):
        super().__init__()
        self._thread_id = thread_id
        self._author_id = author_id
        self._target = target
        self.title_input = discord.ui.TextInput(
            label="Title",
            default=display_title[:100],
            max_length=100,
            required=True,
        )
        self.digest_input = discord.ui.TextInput(
            label="Digest",
            style=discord.TextStyle.paragraph,
            default=digest[:500],
            max_length=500,
            required=True,
        )
        self.add_item(self.title_input)
        self.add_item(self.digest_input)

    async def on_submit(self, interaction: discord.Interaction):
        from mage import get_runtime_dir

        draft = load_pending_draft(get_runtime_dir(), self._author_id, self._thread_id)
        if not draft:
            await interaction.response.send_message(
                "Share session expired — run `!share` again.",
                ephemeral=True,
            )
            return

        draft["display_title"] = self.title_input.value.strip()[:100]
        draft["digest"] = self.digest_input.value.strip()[:500]
        write_pending_draft(get_runtime_dir(), self._author_id, self._thread_id, draft)

        preview = SharePreviewView(self._thread_id, self._author_id, self._target)
        embed = build_preview_embed(draft, self._target)
        try:
            await interaction.response.edit_message(embed=embed, view=preview)
        except discord.HTTPException as exc:
            await interaction.response.send_message(
                f"Could not update preview: {exc}",
                ephemeral=True,
            )
            return

        if isinstance(interaction.channel, discord.Thread):
            await maybe_post_share_rename_offer(
                interaction.channel,
                draft,
                interaction.client,
                suggested=draft["display_title"],
            )


class SharePreviewView(discord.ui.View):
    """Preview synthesized title/digest before send."""

    def __init__(
        self,
        thread_id: int,
        author_id: int,
        target: ShareTarget | SpaceShareTarget,
    ):
        super().__init__(timeout=600)
        self._thread_id = thread_id
        self._author_id = author_id
        self._target = target
        target_token = (
            f"s:{target.space_key}"
            if isinstance(target, SpaceShareTarget)
            else f"p:{target.mage_key}"
        )

        edit_btn = discord.ui.Button(
            label="Edit",
            style=discord.ButtonStyle.secondary,
            custom_id=f"share:edit:{thread_id}:{author_id}:{target_token}",
        )
        edit_btn.callback = self._on_edit
        cancel = discord.ui.Button(
            label="Cancel",
            style=discord.ButtonStyle.secondary,
            custom_id=f"share:cancel:{thread_id}:{author_id}",
        )
        cancel.callback = self._on_cancel
        share = discord.ui.Button(
            label="Share",
            style=discord.ButtonStyle.primary,
            emoji="📤",
            custom_id=f"share:send:{thread_id}:{author_id}:{target_token}",
        )
        share.callback = self._on_share
        self.add_item(edit_btn)
        self.add_item(cancel)
        self.add_item(share)

    async def _on_edit(self, interaction: discord.Interaction):
        if interaction.user.id != self._author_id:
            await interaction.response.send_message("Not your share.", ephemeral=True)
            return
        from mage import get_runtime_dir

        draft = load_pending_draft(get_runtime_dir(), self._author_id, self._thread_id)
        if not draft:
            await interaction.response.send_message(
                "Share session expired — run `!share` again.",
                ephemeral=True,
            )
            return
        modal = ShareEditModal(
            self._thread_id,
            self._author_id,
            self._target,
            draft.get("display_title") or draft.get("title", ""),
            draft.get("digest") or "",
        )
        await interaction.response.send_modal(modal)

    async def _on_cancel(self, interaction: discord.Interaction):
        if interaction.user.id != self._author_id:
            await interaction.response.send_message("Not your share.", ephemeral=True)
            return
        from mage import get_runtime_dir

        clear_pending_draft(get_runtime_dir(), self._author_id, self._thread_id)
        await interaction.response.edit_message(
            content="Share cancelled.",
            embed=None,
            view=None,
        )

    async def _on_share(self, interaction: discord.Interaction):
        if interaction.user.id != self._author_id:
            await interaction.response.send_message("Not your share.", ephemeral=True)
            return
        from mage import get_runtime_dir

        draft = load_pending_draft(get_runtime_dir(), self._author_id, self._thread_id)
        if not draft:
            await interaction.response.send_message(
                "Share session expired — run `!share` again.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()
        bundle = build_export_bundle_from_draft(draft)
        try:
            if isinstance(self._target, SpaceShareTarget):
                await deliver_space_share(bundle, self._target, client=interaction.client)
            else:
                await deliver_practitioner_share(bundle, self._target, client=interaction.client)
        except Exception as exc:
            await interaction.followup.send(
                f"Share failed: {type(exc).__name__}: {exc}",
                ephemeral=True,
            )
            return

        clear_pending_draft(get_runtime_dir(), self._author_id, self._thread_id)
        for child in self.children:
            child.disabled = True
        label = share_label(bundle)
        try:
            if interaction.message:
                await interaction.message.edit(
                    content=f"📤 Shared **“{label}”** with **{self._target.address}**.",
                    embed=None,
                    view=self,
                )
            else:
                await interaction.edit_original_response(
                    content=f"📤 Shared **“{label}”** with **{self._target.address}**.",
                    embed=None,
                    view=self,
                )
        except discord.HTTPException as exc:
            print(f"Share success edit failed: {type(exc).__name__}: {exc}")
            await interaction.followup.send(
                f"📤 Shared **“{label}”** with **{self._target.address}**.",
                ephemeral=True,
            )


class ShareConfirmView(SharePreviewView):
    """Backward-compatible alias for in-flight share messages."""


class SharePickerView(discord.ui.View):
    """Practitioners + Spaces sections (Slice 1 + 3a)."""

    def __init__(
        self,
        *,
        thread_id: int,
        author_id: int,
        targets: list[ShareTarget],
        space_targets: list[SpaceShareTarget] | None = None,
    ):
        super().__init__(timeout=600)
        if targets:
            self.add_item(
                ShareTargetSelect(thread_id=thread_id, author_id=author_id, targets=targets)
            )
        if space_targets:
            self.add_item(
                ShareSpaceSelect(
                    thread_id=thread_id,
                    author_id=author_id,
                    targets=space_targets,
                )
            )


class ShareContinueView(discord.ui.View):
    def __init__(self, share_id: str, parent_channel_id: int):
        super().__init__(timeout=None)
        self._share_id = share_id
        self._parent_channel_id = parent_channel_id
        btn = discord.ui.Button(
            label="Continue",
            style=discord.ButtonStyle.primary,
            emoji="▶️",
            custom_id=f"share:go:{share_id}:{parent_channel_id}",
        )
        btn.callback = self._on_continue
        self.add_item(btn)

    async def _on_continue(self, interaction: discord.Interaction):
        await continue_received_share(
            interaction,
            self._share_id,
            self._parent_channel_id,
        )


def get_share_bot_client(message: discord.Message | None = None):
    """Discord client for share views — River bot in split mode, else guild client."""
    from mage import river_bot_enabled

    if river_bot_enabled():
        from river_state import river_client

        if getattr(river_client, "is_ready", lambda: False)():
            return river_client
    if message is not None:
        channel = message.channel
        guild = getattr(channel, "guild", None)
        if guild is not None:
            return guild._state._get_client()
    from state import client as turtle_client

    return turtle_client


def register_persistent_share_views(client: discord.Client) -> None:
    """Re-register Continue buttons after restart (inbox bundles on disk)."""
    for mage_key in get_registry().get("mages", {}):
        runtime = runtime_dir_for_mage(mage_key)
        inbox_dir = Path(runtime) / "share" / "inbox"
        if not inbox_dir.is_dir():
            continue
        ch_id = river_channel_for_mage(mage_key)
        if not ch_id:
            continue
        for path in inbox_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            share_id = data.get("share_id") or path.stem
            if not share_id:
                continue
            view = ShareContinueView(share_id, ch_id)
            client.add_view(view)


async def cmd_share(message: discord.Message, args: list[str]) -> None:
    """Start Share eddy flow — picker + confirm (practitioner and space targets)."""
    if not isinstance(message.channel, discord.Thread):
        await message.reply(
            "Use `!share` inside an eddy to send this conversation to another practitioner or space.",
            mention_author=False,
        )
        return

    parent_id = message.channel.parent_id
    if not parent_id:
        await message.reply("Could not resolve parent river.", mention_author=False)
        return

    set_practice_context_for_channel(parent_id)
    from mage import get_mage_address, get_runtime_dir

    history = reload_history(message.channel.id)
    if len(history) < 2:
        await message.reply(
            "Need a little conversation first — share works once you and Turtle have exchanged a few messages.",
            mention_author=False,
        )
        return

    sender_key = get_mage_key()
    targets = list_practitioner_targets(sender_key, message.author.id)
    space_targets = list_space_targets(sender_key)
    if not targets and not space_targets:
        await message.reply(
            "No practitioners or spaces are registered to share with yet.",
            mention_author=False,
        )
        return

    title = message.channel.name or "shared eddy"
    share_id = uuid.uuid4().hex[:12]
    draft = {
        "share_id": share_id,
        "title": title,
        "history": history,
        "source_thread_id": message.channel.id,
        "sharer_id": str(message.author.id),
        "sharer_key": sender_key,
        "sharer_address": get_mage_address(),
    }
    write_pending_draft(get_runtime_dir(), message.author.id, message.channel.id, draft)

    try:
        from eddy_flow_library import dismiss_eddy_flow_library, dismiss_eddy_flow_library_bar

        await dismiss_eddy_flow_library_bar(message.channel)
        await dismiss_eddy_flow_library(message.channel, parent_id)
    except Exception as exc:
        print(f"Share flow bar dismiss failed: {type(exc).__name__}: {exc}")

    view = SharePickerView(
        thread_id=message.channel.id,
        author_id=message.author.id,
        targets=targets,
        space_targets=space_targets,
    )
    sections: list[str] = []
    if targets:
        names = ", ".join(t.address for t in targets[:6])
        sections.append(f"**Practitioners**\n{names}")
    if space_targets:
        space_names = ", ".join(t.address for t in space_targets[:6])
        sections.append(f"**Spaces**\n{space_names}")
    body = (
        "\n\n".join(sections)
        + "\n\nPick who should receive a digest. Practitioners get a **received eddy**; "
        "spaces get a **shared eddy** in the parent river. Your thread here stays unchanged."
    )
    embed = discord.Embed(
        title="Share eddy",
        description=body,
        color=0x3498DB,
    )
    await message.reply(embed=embed, view=view, mention_author=False)
    return "Share eddy picker opened — choose target and confirm."
