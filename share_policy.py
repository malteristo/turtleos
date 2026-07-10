"""Share eddy policy — context scaffolding, mention gate, dissolve authority (TURTLE_SPEC §15.6)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import discord

from mage import get_registry, set_practice_context_for_channel
from share_storage import load_received_thread_config
from share_targets import mage_is_space_member, mage_key_for_discord_id


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
        f"- **Dissolve:** Only **{sharer}** (who shared this conversation) may dissolve this "
        "received eddy; the recipient may checkpoint/release per normal eddy law.",
    ]


def shared_eddy_source_for_thread(
    thread_id: int,
    parent_id: int | None,
    cfg: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Return share metadata when thread is a space-tagged shared eddy."""
    from commands import thread_configs

    merged = resolve_eddy_thread_cfg(
        thread_id,
        parent_id,
        cfg if cfg is not None else thread_configs.get(thread_id),
    )
    if not merged or merged.get("origin") != "shared":
        return None
    space_key = merged.get("space_key")
    if not space_key:
        return None
    return merged


def share_dissolve_denial_message(cfg: dict[str, Any]) -> str:
    """User-facing reason when dissolve is reserved for the share creator."""
    sharer = (cfg.get("from_sharer") or "the sharer").strip()
    origin = cfg.get("origin")
    if origin == "received":
        return (
            f"Only **{sharer}** can dissolve this received eddy — they shared it with you. "
            "You can still checkpoint or release anytime."
        )
    space_label = (cfg.get("space_key") or "this space").replace("_", " ").title()
    if sharer_is_space_member(cfg):
        return (
            f"Only **{sharer}** can dissolve this shared eddy — they shared it into **{space_label}**. "
            "You can still checkpoint or release anytime."
        )
    return (
        f"Only **{sharer}** can dissolve this shared eddy by default — they shared into **{space_label}** "
        f"without being a **{space_label}** member (they may open it from the notify in their own river). "
        "Space members can dissolve when the sharer is not in this space."
    )


def sharer_is_space_member(cfg: dict[str, Any]) -> bool:
    """True when share_creator's mage key is in the space registry members list."""
    space_key = cfg.get("space_key")
    sharer_key = cfg.get("sharer_key")
    if not space_key or not sharer_key:
        return False
    space = get_registry().get("spaces", {}).get(space_key, {})
    return sharer_key in (space.get("members") or [])


def space_member_addresses(space_key: str) -> list[str]:
    """Display names for registry space members."""
    space = get_registry().get("spaces", {}).get(space_key, {})
    labels: list[str] = []
    for member_key in space.get("members") or []:
        mage = get_registry().get("mages", {}).get(member_key, {})
        labels.append(mage.get("address", member_key.replace("_", " ").title()))
    return labels


def shared_eddy_context_lines(
    cfg: dict[str, Any],
    *,
    speaker_display: str | None = None,
    speaker_mage_key: str | None = None,
) -> list[str]:
    """Runtime scaffolding for space-tagged shared eddies (visibility + conduct)."""
    sharer = (cfg.get("from_sharer") or "another practitioner").strip()
    space_key = cfg.get("space_key") or "this space"
    space_label = str(space_key).replace("_", " ").title()
    member_labels = space_member_addresses(str(space_key)) if cfg.get("space_key") else []
    sharer_in_space = sharer_is_space_member(cfg)

    lines = [
        f"- **Shared eddy:** **{sharer}** shared a private conversation into **{space_label}**. "
        "**You are Turtle** — you carried the transcript; **you did not initiate the share.**",
    ]
    if member_labels:
        lines.append(f"- **Space members (registry):** {', '.join(member_labels)}")

    if sharer_in_space:
        lines.append(
            f"- **Sharer visibility:** **{sharer}** is a **{space_label}** member — they can see "
            f"the parent channel and may open this thread. Replies here (e.g. \"thanks for sharing\") "
            f"may be meant for **{sharer}**, not for you."
        )
    else:
        lines.append(
            f"- **Sharer visibility:** **{sharer}** is **not** a **{space_label}** member — they "
            "were not auto-added. They learn of conversation via a notify act in **their own river** "
            "when a space member first replies; they do not watch this channel by default."
        )

    if speaker_display:
        speaker_line = f"- **Speaking now:** **{speaker_display}**"
        if speaker_mage_key:
            speaker_line += f" ({speaker_mage_key})"
        lines.append(speaker_line)

    lines.extend(
        [
            f"- **Shared history:** Turns labeled `[{sharer}]` are from the original eddy; "
            "other messages are from space members in this thread.",
            "- **Conduct:** Facilitate for whoever is present. Do not welcome "
            f"**{sharer}** as if they are here unless they have joined. "
            f"When someone thanks for sharing, that thanks is to **{sharer}** — do **not** reply "
            "\"you're welcome\" as if you shared; acknowledge warmly without taking credit.",
            "- **Boundaries:** Messages in this thread are visible to space members in Discord. "
            "Do not treat this as a private 1:1 with the speaker alone.",
            "- **Response policy:** Mention-gated — you only speak when @mentioned, replied to, "
            "or explicitly invoked (e.g. \"hey Turtle\"). Peer-to-peer lines (thanks to the sharer, "
            "@another member) are witness-only; do not reply to those.",
            "- **Dissolve:** Only **"
            f"{sharer}** (who shared into this space) may dissolve when they are a **{space_label}** "
            "member; if they shared from outside the space, any **space member** may dissolve instead. "
            "Others may checkpoint/release per normal eddy law.",
        ]
    )
    return lines


@dataclass(frozen=True)
class SharedEddyResponseDecision:
    respond: bool
    reason: str


def _message_guild(message: discord.Message):
    channel = message.channel
    guild = getattr(channel, "guild", None)
    if guild is not None:
        return guild
    parent = getattr(channel, "parent", None)
    return getattr(parent, "guild", None) if parent is not None else None


def _turtle_user_id_for_message(message: discord.Message) -> int | None:
    from eddy_spawn import resolve_turtle_bot_user_id

    return resolve_turtle_bot_user_id(_message_guild(message))


def message_mentions_turtle(message: discord.Message) -> bool:
    turtle_id = _turtle_user_id_for_message(message)
    if not turtle_id:
        return False
    return any(getattr(user, "id", None) == turtle_id for user in (message.mentions or []))


def message_mentions_other_humans(message: discord.Message) -> bool:
    """True when @mentions include a non-Turtle user (peer-directed)."""
    turtle_id = _turtle_user_id_for_message(message)
    for user in message.mentions or []:
        uid = getattr(user, "id", None)
        if turtle_id and uid == turtle_id:
            continue
        if getattr(user, "bot", False):
            continue
        return True
    return False


def message_is_reply_to_turtle(message: discord.Message) -> bool:
    from eddy_spawn import is_turtle_bot_message

    ref = getattr(message, "reference", None)
    if not ref:
        return False
    resolved = getattr(ref, "resolved", None) or getattr(ref, "cached_message", None)
    if resolved is None:
        return False
    return is_turtle_bot_message(resolved)


_EXPLICIT_TURTLE_INVOKE_RE = re.compile(
    r"(?i)(?:^|[\s,.:;!\?])(?:hey\s+)?turtle(?:[\s,.:;!\?]|$)"
)
_PEER_THANKS_RE = re.compile(
    r"(?i)\b(thanks|thank you|danke)\b.{0,30}\b(sharing|teilen|geteilt)\b"
)


def content_explicitly_invokes_turtle(content: str) -> bool:
    text = (content or "").strip()
    if not text:
        return False
    return bool(_EXPLICIT_TURTLE_INVOKE_RE.search(f" {text} "))


def content_looks_like_peer_thanks(content: str) -> bool:
    text = (content or "").strip()
    if not text:
        return False
    if _PEER_THANKS_RE.search(text):
        return True
    if re.search(r"(?i)^thanks\b", text) and "turtle" not in text.lower():
        return True
    return False


def shared_eddy_response_decision(
    message: discord.Message,
    content: str,
) -> SharedEddyResponseDecision:
    """Mention-gated response policy for shared eddies (Slice 3f)."""
    if message_mentions_turtle(message):
        return SharedEddyResponseDecision(True, "mention_turtle")
    if message_is_reply_to_turtle(message):
        return SharedEddyResponseDecision(True, "reply_to_turtle")
    if content_explicitly_invokes_turtle(content):
        return SharedEddyResponseDecision(True, "explicit_invoke")
    if message_mentions_other_humans(message):
        return SharedEddyResponseDecision(False, "mention_peer")
    if content_looks_like_peer_thanks(content):
        return SharedEddyResponseDecision(False, "peer_thanks")
    return SharedEddyResponseDecision(False, "mention_gated_default")


@dataclass(frozen=True)
class ShareDissolveDecision:
    allowed: bool
    reason: str | None = None


def check_share_dissolve_authority(
    thread_id: int,
    parent_id: int | None,
    actor_discord_id: str | int,
    cfg: dict[str, Any] | None = None,
) -> ShareDissolveDecision:
    """Only share_creator may dissolve received/shared eddies created by Share (Slice 3d)."""
    from commands import thread_configs

    merged = resolve_eddy_thread_cfg(
        thread_id,
        parent_id,
        cfg if cfg is not None else thread_configs.get(thread_id),
    )
    if not merged or merged.get("origin") not in ("received", "shared"):
        return ShareDissolveDecision(True)
    creator = merged.get("share_creator")
    if not creator:
        return ShareDissolveDecision(True)
    if str(actor_discord_id) == str(creator):
        return ShareDissolveDecision(True)
    if merged.get("origin") == "shared":
        space_key = merged.get("space_key")
        actor_key = mage_key_for_discord_id(actor_discord_id)
        if (
            space_key
            and actor_key
            and not sharer_is_space_member(merged)
            and mage_is_space_member(actor_key, str(space_key))
        ):
            return ShareDissolveDecision(True)
    if merged.get("origin") == "received":
        return ShareDissolveDecision(False, share_dissolve_denial_message(merged))
    return ShareDissolveDecision(False, share_dissolve_denial_message(merged))


async def append_shared_eddy_witness_turn(message: discord.Message, content: str) -> None:
    """Record a peer message in history without generating a Turtle reply."""
    from helpers import get_history, reload_history, sync_history
    from state import MAX_DIALOGUE_HISTORY

    channel_id = message.channel.id
    history = get_history(channel_id)
    if not history and isinstance(message.channel, discord.Thread):
        reload_history(channel_id)
        history = get_history(channel_id)

    user_entry = f"[{message.author.display_name}]: {(content or '').strip()}"
    history.append({"role": "user", "content": user_entry})
    if len(history) > MAX_DIALOGUE_HISTORY:
        history.pop(0)
    sync_history(channel_id)


async def maybe_skip_shared_eddy_dialogue(
    message: discord.Message,
    content: str,
) -> SharedEddyResponseDecision | None:
    """Return a pass decision when Turtle should stay silent; None to continue dialogue."""
    if not isinstance(message.channel, discord.Thread):
        return None
    from commands import thread_configs

    parent_id = message.channel.parent_id
    cfg = resolve_eddy_thread_cfg(
        message.channel.id,
        parent_id,
        thread_configs.get(message.channel.id),
    )
    if not cfg or cfg.get("origin") != "shared":
        return None
    decision = shared_eddy_response_decision(message, content)
    if decision.respond:
        return None
    await append_shared_eddy_witness_turn(message, content)
    return decision
