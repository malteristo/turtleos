"""Dialogue runtime environment — thread cards, runtime blocks, source trace.

Slice 5 of discord_bot.py decomposition (2026-07-10).
Re-exported from discord_bot for backward compatibility.
"""

from __future__ import annotations

import os
import re

import discord

from helpers import local_now
from mage import (
    _resolve_mage_from_author,
    address_for_mage_key,
    channel_is_shared_space,
    get_current_channel_primitive,
    get_mage_key,
    get_mage_name,
    get_registry,
)
from practice_io import get_thread_state_dir, read_thread_state
from state import (
    DIALOGUE_MODEL,
    EDDY_DEFAULT,
    EDDY_TYPES,
    REFLECTION_MODEL,
    TURTLE_MODEL,
    USE_API,
    threads_flagged_for_release,
)
from thread_registry import get_related_thread_awareness, get_thread_awareness


def thread_card_excerpt(value: str, limit: int = 700) -> str:
    text = re.sub(r"\s+", " ", (value or "")).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + " ..."


def _append_river_window_line(lines: list[str], message) -> None:
    """Fail-soft: Turtle sees a count, never a recital of names."""
    try:
        from datetime import datetime, timezone

        channel = message.channel
        if not isinstance(channel, discord.Thread) or channel.parent is None:
            return
        parent = channel.parent
        threads = getattr(parent, "threads", None)
        if not isinstance(threads, (list, tuple)):
            return
        from cmd_threads import collect_five_state_thread_records
        from river_display import river_window_line
        from thread_registry import load_registry

        records = collect_five_state_thread_records(
            list(threads),
            load_registry().get("threads", {}),
            parent_name=getattr(parent, "name", None),
            parent_id=getattr(parent, "id", None),
            show_all=False,
            now=datetime.now(timezone.utc),
        )
        line = river_window_line(records, parent_name=getattr(parent, "name", None))
        if line:
            lines.append(line)
    except Exception:
        return


def build_runtime_env(message, cfg):
    channel = message.channel
    mage_name = get_mage_name()
    mage_key = get_mage_key()

    is_thread = isinstance(channel, discord.Thread)
    if is_thread:
        parent = channel.parent
        channel_name = parent.name if parent else "(unknown)"
        thread_name = channel.name
    else:
        channel_name = channel.name if hasattr(channel, "name") else "(DM)"
        thread_name = None

    if cfg:
        model = cfg.get("model_label", cfg.get("model", "unknown"))
        attunement = cfg.get("attunement", "semi")
    else:
        model = DIALOGUE_MODEL if USE_API else REFLECTION_MODEL
        attunement = "orchestrator"

    lines = [
        "## Runtime Environment",
        f"- **Channel:** #{channel_name}",
    ]
    if thread_name:
        awareness = get_thread_awareness(channel.id)
        lines.append(f"- **Current thread:** {thread_name} ({awareness})")
        thread_card = read_thread_state(thread_name)
        if thread_card:
            lines.append("")
            lines.append("## Current Thread Card")
            lines.append(thread_card)
        related = get_related_thread_awareness(thread_name, current_thread_id=channel.id)
        if related:
            lines.append("")
            lines.append(related)
        lines.append(
            "- **Thread-state rule:** This is the conversation you are currently inside. "
            "Do not recommend creating a new thread for this same topic; continue here or "
            "reference related threads from the live registry."
        )
        lines.append(
            "- **Externalized persistence rule:** Treat the thread card as your durable memory "
            "for this eddy. Use it quietly; do not announce context limits unless they "
            "materially affect the conversation."
        )
    lines.append(f"- **Mage:** {mage_name}")
    lines.append(f"- **Model:** {model}")
    lines.append(f"- **Attunement:** {attunement}")

    primitive = get_current_channel_primitive()
    if primitive and primitive.base == "shared":
        lines.append(f"- **Message from:** {message.author.display_name}")
        space = get_registry().get("spaces", {}).get(mage_key, {})
        members = space.get("members", [])
        if members:
            lines.append(f"- **Space members:** {', '.join(m.capitalize() for m in members)}")

        lines.append("")
        lines.append(
            "**Context boundary:** This shared room may read only its own practice root. "
            "Never load or infer a member's private workspace, compass, or private-room "
            "memory. Private material enters only through an explicit member share."
        )
    elif thread_name and cfg and cfg.get("attunement") == "raw":
        lines.append("")
        lines.append(
            "**Context boundary:** Raw attunement. "
            "Be direct and focused on the topic at hand."
        )

    _append_river_window_line(lines, message)
    return "\n".join(lines) + "\n\n"


def build_native_runtime_env(message, cfg, history: list[dict] | None = None):
    """Minimal runtime block for vanilla native eddies."""
    channel = message.channel
    parent = channel.parent if isinstance(channel, discord.Thread) else None
    channel_name = parent.name if parent else (channel.name if hasattr(channel, "name") else "(DM)")
    thread_name = channel.name if isinstance(channel, discord.Thread) else None
    history = history or []

    lines = [
        "## Eddy Context",
        f"- **River channel:** #{channel_name}",
    ]
    if thread_name:
        lines.append(f"- **Eddy:** {thread_name}")
        prior_user_turns = sum(1 for m in history if m.get("role") == "user")
        if prior_user_turns > 1:
            lines.append(
                "- **Resume:** This thread has prior conversation in your working history — "
                "continue naturally from where you left off. Do not ask them to recap or claim "
                "you lack earlier messages in this eddy."
            )
        thread_card = read_thread_state(thread_name)
        if thread_card:
            lines.append("")
            lines.append("## Thread continuity")
            lines.append(thread_card)
    if isinstance(channel, discord.Thread):
        from share_eddy import (
            received_eddy_context_lines,
            resolve_eddy_thread_cfg,
            shared_eddy_context_lines,
        )

        parent_id = channel.parent_id
        cfg = resolve_eddy_thread_cfg(channel.id, parent_id, cfg)
        if cfg and cfg.get("origin") == "received":
            lines.extend(received_eddy_context_lines(cfg))
        elif cfg and cfg.get("origin") == "shared":
            speaker_key, _ = _resolve_mage_from_author(message.author)
            lines.extend(
                shared_eddy_context_lines(
                    cfg,
                    speaker_display=message.author.display_name,
                    speaker_mage_key=speaker_key,
                )
            )
    if (cfg or {}).get("blank_eddy") or (cfg or {}).get("awaiting_title"):
        lines.append(
            "- **Entry:** Blank eddy — the practitioner's first message is what they brought; "
            "engage it directly (not a UI test unless they clearly mean Discord)."
        )
    # INT-051: ordinary multi-member river eddies (not only share-origin) must
    # name the speaking member by registry address. ``Practitioner: Family``
    # left only the Discord handle prefix; handles ≠ addresses, and the model
    # defaulted to the host name from soul.md (live 2026-08-02).
    parent_id = getattr(channel, "parent_id", None) if isinstance(channel, discord.Thread) else None
    registry_id = parent_id if parent_id is not None else getattr(channel, "id", None)
    multi_member = bool(registry_id is not None and channel_is_shared_space(registry_id))
    if cfg and cfg.get("origin") == "shared":
        space_label = (cfg.get("space_key") or get_mage_name() or "space").replace("_", " ").title()
        lines.append(f"- **Space:** {space_label} (multi-member shared river)")
    elif multi_member:
        space_label = (get_mage_key() or get_mage_name() or "space").replace("_", " ").title()
        lines.append(f"- **Space:** {space_label} (multi-member shared river)")
        speaker_key, _ = _resolve_mage_from_author(message.author)
        display = getattr(message.author, "display_name", None) or getattr(
            message.author, "name", None
        ) or "unknown"
        if speaker_key:
            address = address_for_mage_key(speaker_key)
            lines.append(
                f"- **Speaking now:** **{address}** ({speaker_key}) "
                f"[discord: {display}]"
            )
            lines.append(
                f"- **Address:** Speak to **{address}** by that name. "
                "The Discord handle is not their practice name; "
                "never address them as another space member."
            )
        else:
            lines.append(f"- **Speaking now:** {display} (unregistered in this space)")
            lines.append(
                "- **Address:** Use only the name shown above; "
                "do not invent another member's name."
            )
    else:
        lines.append(f"- **Practitioner:** {get_mage_name()}")
    lines.append(f"- **Model:** {TURTLE_MODEL} (local Turtle)")
    flow_id = (cfg or {}).get("context_type")
    if flow_id:
        lines.append(f"- **Flow:** {flow_id}")
    primitive = get_current_channel_primitive()
    if primitive and primitive.has("shared_work"):
        from mage import get_pd
        from team_federation import render_intersections
        from team_lanes import lane_context
        from team_state import render_context

        actor, _ = _resolve_mage_from_author(message.author)
        lane_block = lane_context(channel.id) if isinstance(channel, discord.Thread) else ""
        lines.extend(["", render_context(get_pd(), actor)])
        if lane_block:
            lines.extend(["", lane_block])
            if flow_id == "dnd_dm":
                from campaign_state import render_context as render_campaign_context

                campaign = render_campaign_context(
                    get_pd(),
                    thread_id=channel.id,
                    actor=actor,
                )
                if campaign:
                    lines.extend(["", campaign])
            intersections = render_intersections(
                get_pd(),
                thread_id=channel.id,
                actor=actor,
            )
            if intersections:
                lines.extend(["", intersections])
    lines.append("")
    _append_river_window_line(lines, message)
    return "\n".join(lines) + "\n\n"


def build_source_trace(source_flags: list[str]) -> str:
    """Compact visible epistemic trace for context injected before the reply."""
    seen = []
    for flag in source_flags:
        if flag and flag not in seen:
            seen.append(flag)
    if not seen:
        return ""
    return "Sources: " + "; ".join(seen)


async def update_thread_state(thread: discord.Thread, cfg: dict | None, history: list[dict]):
    """Write the thread card Turtle will return to on future context windows."""
    os.makedirs(get_thread_state_dir(), exist_ok=True)
    safe_name = re.sub(r"[^\w\-]", "_", thread.name.lower())
    state_path = os.path.join(get_thread_state_dir(), f"{safe_name}.md")

    model_label = (cfg or {}).get("model_label", "default")
    attunement = (cfg or {}).get("attunement", "semi")
    msg_count = len(history)
    now = local_now().strftime("%Y-%m-%d %H:%M")

    last_user = ""
    last_assistant = ""
    for m in reversed(history):
        if m["role"] == "assistant" and not last_assistant:
            last_assistant = thread_card_excerpt(m["content"])
        elif m["role"] == "user" and not last_user:
            last_user = thread_card_excerpt(m["content"])
        if last_user and last_assistant:
            break

    eddy_type = cfg.get("eddy_type", EDDY_DEFAULT) if cfg else EDDY_DEFAULT
    eddy_info = EDDY_TYPES.get(eddy_type, EDDY_TYPES[EDDY_DEFAULT])
    flagged = threads_flagged_for_release.get(thread.id)
    flag_line = f"\n**Flagged for release:** {flagged['reason']}\n" if flagged else ""

    continuity = "Return by reading this card before simulating memory."
    if last_user:
        continuity = "Resume from the last practitioner move and update this card after the next meaningful reply."

    content = (
        f"# Thread Card: {thread.name}\n\n"
        f"**Thread ID:** {thread.id}\n"
        f"**Config:** `{model_label}` / `{attunement}`\n"
        f"**Eddy:** {eddy_info['emoji']} `{eddy_type}` ({eddy_info['days'] or '∞'}d)\n"
        f"**Messages in working history:** {msg_count}\n"
        f"**Last active:** {now}\n"
        f"**Continuity cue:** {continuity}\n"
        f"{flag_line}\n"
        "## Last Practitioner Move\n"
        f"{last_user or '(none captured yet)'}\n\n"
        "## Last Turtle Move\n"
        f"{last_assistant or '(none captured yet)'}\n\n"
        "## Return Rule\n"
        "Use this card as externalized persistence: check it before continuing the thread, "
        "then overwrite it with the newest durable state after the exchange.\n"
    )

    try:
        with open(state_path, "w") as f:
            f.write(content)
    except Exception as e:
        print(f"Thread card write failed for {thread.name}: {e}")
