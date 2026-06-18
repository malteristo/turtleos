#!/usr/bin/env python3
"""turtleOS Shell — Spirit's persistent interface

Modular architecture (2026-03-29 refactor):
  state.py — shared state, config, client
  mage.py — multi-mage registry, practice directory resolution
  practice_io.py — file I/O utilities
  llm.py — LLM backends (Anthropic, Gemini, Ollama)
  tos_tools.py — 9 practice file tools + execution
  triage.py — message classification (sub-2B local model)
  readiness.py — 8-dimension practice health assessment
  prompts.py — system prompt builders (identity + practice state)
  helpers.py — shared utilities (history, logging, message splitting)
  sessions.py — session lifecycle (timeout, reflection, notes)
  background.py — background tasks (health, interoception)
  commands.py — 28 commands, views, control panel, dispatch

This file: event handlers, handle_dialogue, main().
"""

import asyncio
import os
import json
import re
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

import discord


# ─── Load .env ────────────────────────────────────────────────────

def load_env(env_path=None):
    path = env_path or os.environ.get("DOTENV_PATH", ".env")
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

load_env()

# ─── Module Imports ───────────────────────────────────────────────

from state import (
    client, CHANNELS, OPS_EMBED_COLOR, EMBED_COLORS, _processed_messages,
    get_channel_lock, get_channel,
    IDENTITY_DIR, DIALOGUE_MODEL, REFLECTION_MODEL, TRIAGE_MODEL, USE_API, TURTLE_MODEL,
    HAS_GEMINI, GOOGLE_API_KEY,
    MAX_DIALOGUE_HISTORY, EDDY_DEFAULT,
    dialogue_histories, active_sessions,
    KNOWN_MODELS,
    thread_configs, absorbed_contexts,
    EDDY_TYPES, EDDY_DEFAULT, threads_flagged_for_release,
)

from mage import (
    get_pd, get_mage_name, get_mage_key,
    set_practice_context, set_practice_context_for_channel,
    is_practice_channel, is_registered_parent_channel,
    get_registry, _resolve_mage_from_author,
    get_thread_member_ids, uses_native_river, river_bot_enabled, turtle_handles_native_river,
    suppress_turtle_river_voice, get_attunement_profile,
)

from practice_io import (
    read_safe, count_items,
    file_age_hours, format_age, load_intentions_list,
    get_thread_state_dir, read_thread_state,
)

from thread_registry import (
    register_thread, update_thread_activity,
    backfill_from_discord, get_registry_summary,
    get_related_thread_awareness, get_thread_awareness,
)

from llm import (
    chat_anthropic_with_model, chat_gemini, chat_ollama, chat_ollama_with_tools,
)

from tos_tools import TOS_TOOLS, execute_tos_tool, build_tool_report

from triage import triage_message, prewarm_triage

from prompts import (
    get_system_prompt, get_thread_prompt, build_thread_summary,
    get_native_eddy_prompt, uses_native_turtle_prompt,
)

from readiness import startup_readiness_check

from helpers import (
    local_now, get_history, log_activity, split_message,
    load_thread_history, summarize_thread_context,
    preprocess_attachments,
)

from sessions import session_monitor, checkpoint_session, close_session, maybe_reflect
from boom_thread import handle_boom_thread_message
from eddy_spawn import (
    should_offer_eddy, make_eddy_spawn_view, handle_eddy_spawn_interaction,
    is_intake_thread, handle_intake_message, generate_topic, ensure_native_presence,
)
from intake_server import start_intake_server
from proprioceptor import prepare_context_brief
from background import practice_health_loop, interoception_loop, daily_reminders_loop, health_canary_loop
from founder_keys import try_founder_key_entry

from commands import (
    try_direct_command, DIRECT_COMMANDS, ControlPanelView, LinkFetchView,
    ThreadConfigView, send_with_actions,
)

from content_fetch import (
    extract_urls as _extract_urls,
    fetch_url_content as _fetch_url_content,
    process_urls as _process_urls,
    extract_attachments as _extract_attachments,
)

# Boom thread fetched content cache (message.id -> content string)
_boom_fetched_content = {}


_CONTEXTUAL_ACTION_COMMANDS = {
    "status", "diagnose", "sync", "sweep", "recall", "release",
    "boom", "propose", "thread", "new", "threads", "eddy-check", "fetch",
    "absorb", "absorbed", "forget", "readiness", "signals", "load",
}
_CONTEXTUAL_COMMAND_RE = re.compile(r"`(![A-Za-z][\w-]*(?:\s+[^`]+)?)`")
_RECOMMENDATION_CUE_RE = re.compile(
    r"\b(?:want me to|should i|would you like (?:me to )?|i(?:'d| would) recommend(?: running)?|try(?: running)?|you could run)\b",
    re.IGNORECASE,
)
_PLAIN_COMMAND_RE = re.compile(
    r"!(?:boom convert|boom thread|boom add|eddy-check|readiness|diagnose|threads|recall|release|signals|absorb|absorbed|forget|sweep|propose|status|bright|compass|intentions|fetch|thread|sync|load|boom|new)"
    r"(?:\s+[^.\n`»]+)?",
    re.IGNORECASE,
)
_DISCORD_MESSAGE_LINK_RE = re.compile(r"https?://(?:ptb\.|canary\.)?discord(?:app)?\.com/channels/(\d+)/(\d+)/(\d+)")


def _contextual_action_label(command: str) -> str:
    body = command.strip().lstrip("!")
    cmd = body.split(None, 1)[0].lower() if body else ""
    rest = body.split(None, 1)[1] if " " in body else ""

    if cmd == "thread":
        match = re.search(r'"([^"]+)"', rest)
        topic = match.group(1) if match else rest.split("--", 1)[0].strip()
        return f"Create thread: {topic[:42]}" if topic else "Create thread"
    if cmd == "new":
        return "Open eddy"
    if cmd == "boom":
        rest_lower = rest.lower()
        if rest_lower.startswith("convert"):
            return "Run boom convert"
        if rest_lower.startswith("thread"):
            return "Boom thread"
        if rest_lower.startswith("add"):
            return "Add to boom"
    labels = {
        "status": "Show status",
        "diagnose": "Run diagnose",
        "sync": "Check sync",
        "sweep": "Sweep boom",
        "recall": "Recall",
        "release": "Release session",
        "boom": "Show boom",
        "propose": "Capture proposal",
        "threads": "Show threads",
        "eddy-check": "Check eddies",
        "fetch": "Fetch link",
        "absorb": "Absorb thread",
        "absorbed": "Show absorbed",
        "forget": "Forget context",
        "readiness": "Assess readiness",
        "signals": "Review signals",
        "load": "Load context",
    }
    return labels.get(cmd, f"Run !{cmd}")


def _recommendation_tail(reply: str) -> str:
    """Paragraph most likely to hold a local recommendation (skip trace/footer lines)."""
    paragraphs = []
    for block in reply.split("\n\n"):
        block = block.strip()
        if not block or block.startswith("-#"):
            continue
        paragraphs.append(block)
    if paragraphs:
        return paragraphs[-1]
    lines = [ln for ln in reply.splitlines() if ln.strip() and not ln.strip().startswith("-#")]
    return "\n".join(lines[-6:])


def _trim_contextual_command(command: str) -> str:
    """Keep only the invocable prefix — drop trailing prose after the command."""
    text = command.strip().rstrip("?.!,;:")
    text = text.lstrip("!")
    if not text:
        return "!"
    parts = text.split()
    cmd = parts[0].lower()
    if cmd == "boom" and len(parts) >= 2:
        sub = parts[1].lower()
        if sub in ("convert", "thread", "add"):
            if sub in ("convert",):
                return "!boom convert"
            return "!" + " ".join(parts)
    if cmd == "thread":
        return "!" + " ".join(parts)
    if cmd in ("absorb", "fetch", "load", "forget", "propose", "new") and len(parts) > 1:
        return "!" + " ".join(parts)
    return "!" + parts[0].lower()


def _append_contextual_action(actions: list, seen: set, command: str) -> None:
    command = _trim_contextual_command(command)
    cmd = command.lstrip("!").split(None, 1)[0].lower()
    if cmd not in _CONTEXTUAL_ACTION_COMMANDS:
        return
    key = command.lower()
    if key in seen:
        return
    seen.add(key)
    actions.append((_contextual_action_label(command), command))


def _extract_contextual_actions(reply: str) -> list[tuple[str, str]]:
    # Find direct commands Turtle recommended so the shell can attach buttons.
    actions = []
    seen = set()
    for match in _CONTEXTUAL_COMMAND_RE.finditer(reply):
        _append_contextual_action(actions, seen, match.group(1).strip())

    # Phase 2: natural-language recommendations often cite !commands without backticks.
    tail = _recommendation_tail(reply)
    if _RECOMMENDATION_CUE_RE.search(tail):
        for match in _PLAIN_COMMAND_RE.finditer(tail):
            _append_contextual_action(actions, seen, match.group(0).strip())

    # More than three command mentions is usually help text, not a local recommendation.
    if len(actions) > 3:
        return []
    return actions


# ─── handle_dialogue ─────────────────────────────────────────────

def _build_runtime_env(message, cfg):
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
        lines.append("- **Thread-state rule:** This is the conversation you are currently inside. Do not recommend creating a new thread for this same topic; continue here or reference related threads from the live registry.")
        lines.append("- **Externalized persistence rule:** Treat the thread card as your durable memory for this eddy. Use it quietly; do not announce context limits unless they materially affect the conversation.")
    lines.append(f"- **Mage:** {mage_name}")
    lines.append(f"- **Model:** {model}")
    lines.append(f"- **Attunement:** {attunement}")

    if mage_key == "family":
        lines.append(f"- **Message from:** {message.author.display_name}")
        space = get_registry().get("spaces", {}).get("family", {})
        members = space.get("members", [])
        if members:
            lines.append(f"- **Space members:** {', '.join(m.capitalize() for m in members)}")

        speaking_mage, personal_pd = _resolve_mage_from_author(message.author)
        if speaking_mage and personal_pd:
            lines.append(f"- **Speaking mage workspace:** {personal_pd}")
            compass_path = os.path.join(personal_pd, "compass.md")
            if os.path.exists(compass_path):
                compass = read_safe(compass_path)
                if compass.strip():
                    lines.append("")
                    lines.append(f"**{speaking_mage.capitalize()}'s personal compass** (from their sovereign workspace):")
                    lines.append(compass[:3000])

        lines.append("")
        lines.append("**Context:** Shared family space. Keep responses accessible and warm. "
                      "You have access to the speaking member's personal practice state "
                      "via their workspace above. Reference it naturally when relevant. "
                      "Each member's data is sovereign — only share what the speaker asks about.")
    elif thread_name and cfg and cfg.get("attunement") == "raw":
        lines.append("")
        lines.append("**Context boundary:** Raw attunement. "
                      "Be direct and focused on the topic at hand.")

    return "\n".join(lines) + "\n\n"


async def _retire_legacy_river_chrome(channel) -> int:
    """Remove pinned Spirit Control Panel and other magic-era river chrome (native mode)."""
    if not channel:
        return 0
    removed = 0
    targets: list[discord.Message] = []
    seen_ids: set[int] = set()

    def _is_control_panel(msg: discord.Message) -> bool:
        if msg.author != client.user:
            return False
        for embed in msg.embeds or []:
            title = embed.title or ""
            if title.startswith("\U0001f3ae") or "Spirit Control Panel" in title:
                return True
        return False

    try:
        async for msg in channel.pins():
            if _is_control_panel(msg) and msg.id not in seen_ids:
                targets.append(msg)
                seen_ids.add(msg.id)
    except discord.HTTPException:
        pass
    try:
        async for msg in channel.history(limit=40):
            if _is_control_panel(msg) and msg.id not in seen_ids:
                targets.append(msg)
                seen_ids.add(msg.id)
    except discord.HTTPException:
        pass

    for msg in targets:
        try:
            await msg.unpin()
        except discord.HTTPException:
            pass
        try:
            await msg.delete()
            removed += 1
        except discord.HTTPException as exc:
            print(f"Control panel delete failed ({msg.id}): {exc}")
    if removed:
        print(f"Retired {removed} legacy control panel(s) in #{getattr(channel, 'name', channel.id)}")
    return removed


def _build_native_runtime_env(message, cfg):
    """Minimal runtime block for vanilla native eddies."""
    channel = message.channel
    parent = channel.parent if isinstance(channel, discord.Thread) else None
    channel_name = parent.name if parent else (channel.name if hasattr(channel, "name") else "(DM)")
    thread_name = channel.name if isinstance(channel, discord.Thread) else None

    lines = [
        "## Eddy Context",
        f"- **River channel:** #{channel_name}",
    ]
    if thread_name:
        lines.append(f"- **Eddy:** {thread_name}")
    if (cfg or {}).get("blank_eddy") or (cfg or {}).get("awaiting_title"):
        lines.append(
            "- **Entry:** Blank eddy — the practitioner's first message is what they brought; "
            "engage it directly (not a UI test unless they clearly mean Discord)."
        )
    lines.append(f"- **Practitioner:** {get_mage_name()}")
    lines.append(f"- **Model:** {TURTLE_MODEL} (local Turtle)")
    flow_id = (cfg or {}).get("context_type")
    if flow_id:
        lines.append(f"- **Flow:** {flow_id}")
    lines.append("")
    return "\n".join(lines) + "\n\n"


def _build_source_trace(source_flags: list[str]) -> str:
    """Compact visible epistemic trace for context injected before the reply."""
    seen = []
    for flag in source_flags:
        if flag and flag not in seen:
            seen.append(flag)
    if not seen:
        return ""
    return "Sources: " + "; ".join(seen)


async def _update_thread_state(thread: discord.Thread, cfg: dict | None, history: list[dict]):
    """Write the thread card Turtle will return to on future context windows."""
    os.makedirs(get_thread_state_dir(), exist_ok=True)
    safe_name = re.sub(r'[^\w\-]', '_', thread.name.lower())
    state_path = os.path.join(get_thread_state_dir(), f"{safe_name}.md")

    model_label = cfg["model_label"] if cfg else "default"
    attunement = cfg["attunement"] if cfg else "semi"
    msg_count = len(history)
    now = local_now().strftime("%Y-%m-%d %H:%M")

    last_user = ""
    last_assistant = ""
    for m in reversed(history):
        if m["role"] == "assistant" and not last_assistant:
            last_assistant = _thread_card_excerpt(m["content"])
        elif m["role"] == "user" and not last_user:
            last_user = _thread_card_excerpt(m["content"])
        if last_user and last_assistant:
            break

    eddy_type = cfg.get("eddy_type", EDDY_DEFAULT) if cfg else EDDY_DEFAULT
    eddy_info = EDDY_TYPES.get(eddy_type, EDDY_TYPES[EDDY_DEFAULT])
    flagged = threads_flagged_for_release.get(thread.id)
    flag_line = f"\n**Flagged for release:** {flagged['reason']}\n" if flagged else ""

    continuity = "Return by reading this card before simulating memory."
    if last_user:
        continuity = "Resume from the last user move and update this card after the next meaningful reply."

    content = (
        f"# Thread Card: {thread.name}\n\n"
        f"**Thread ID:** {thread.id}\n"
        f"**Config:** `{model_label}` / `{attunement}`\n"
        f"**Eddy:** {eddy_info['emoji']} `{eddy_type}` ({eddy_info['days'] or '∞'}d)\n"
        f"**Messages in working history:** {msg_count}\n"
        f"**Last active:** {now}\n"
        f"**Continuity cue:** {continuity}\n"
        f"{flag_line}\n"
        "## Last User Move\n"
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


def _thread_card_excerpt(value: str, limit: int = 700) -> str:
    text = re.sub(r"\s+", " ", (value or "")).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + " ..."


def _summarize_message_snapshot(snapshot, index: int) -> str:
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


def _snapshot_has_readable_content(snapshot) -> bool:
    if (getattr(snapshot, "content", "") or "").strip():
        return True
    embeds = getattr(snapshot, "embeds", []) or []
    if any((getattr(embed, "title", None) or getattr(embed, "description", None)) for embed in embeds):
        return True
    return bool(getattr(snapshot, "attachments", []) or [])


def _forward_source_ref(message) -> tuple[int | None, int, int] | None:
    snapshots = getattr(message, "message_snapshots", None) or []
    if not snapshots:
        return None
    ref = getattr(message, "reference", None)
    channel_id = getattr(ref, "channel_id", None)
    message_id = getattr(ref, "message_id", None)
    if not channel_id or not message_id:
        return None
    return getattr(ref, "guild_id", None), int(channel_id), int(message_id)


def _extract_forwarded_context(message) -> str:
    snapshots = getattr(message, "message_snapshots", None) or []
    if not snapshots:
        return ""
    blocks = [_summarize_message_snapshot(snapshot, idx) for idx, snapshot in enumerate(snapshots, 1)]
    source_ref = _forward_source_ref(message)
    if source_ref:
        guild_id, channel_id, message_id = source_ref
        ref_bits = []
        if guild_id:
            ref_bits.append(f"guild_id={guild_id}")
        ref_bits.append(f"channel_id={channel_id}")
        ref_bits.append(f"message_id={message_id}")
        blocks.append("[Forward source] " + " ".join(ref_bits))
    return "\n\n".join(blocks)


def _visible_message_content(message) -> tuple[str, str]:
    content = message.content or ""
    forwarded_context = _extract_forwarded_context(message)
    if forwarded_context:
        if content.strip():
            return f"{content}\n\n{forwarded_context}", forwarded_context
        return forwarded_context, forwarded_context
    return content, ""


def _extract_discord_message_refs(text: str) -> list[tuple[int | None, int, int]]:
    refs = []
    seen = set()
    for match in _DISCORD_MESSAGE_LINK_RE.finditer(text or ""):
        guild_id, channel_id, message_id = (int(part) for part in match.groups())
        key = (guild_id, channel_id, message_id)
        if key not in seen:
            seen.add(key)
            refs.append(key)
    return refs


def _forwarded_snapshot_is_partial(message) -> bool:
    snapshots = getattr(message, "message_snapshots", None) or []
    return bool(snapshots) and not all(_snapshot_has_readable_content(snapshot) for snapshot in snapshots)


def _format_dereferenced_message(source_message, *, label: str) -> str:
    content = (source_message.content or "").strip()
    parts = [f"[{label}] channel_id={source_message.channel.id} message_id={source_message.id}"]
    author = getattr(source_message.author, "display_name", None) or source_message.author.name
    parts.append(f"author: {author}")
    created = getattr(source_message, "created_at", None)
    if created:
        parts.append(f"created: {created.isoformat()}")
    if content:
        parts.append(f"content:\n{content}")
    forwarded = _extract_forwarded_context(source_message)
    if forwarded:
        parts.append(forwarded)
    if len(parts) <= 3:
        parts.append("no readable text content")
    return "\n".join(parts)


async def _fetch_discord_message_context(refs: list[tuple[int | None, int, int]], *, label: str, limit: int = 3) -> tuple[str, int]:
    blocks = []
    for _guild_id, channel_id, message_id in refs[:limit]:
        try:
            channel = await client.fetch_channel(channel_id)
            source_message = await channel.fetch_message(message_id)
            blocks.append(_format_dereferenced_message(source_message, label=label))
        except Exception as e:
            blocks.append(
                f"[{label} unavailable] channel_id={channel_id} message_id={message_id} "
                f"error={type(e).__name__}: {e}"
            )
    return "\n\n".join(blocks), len(blocks)


async def handle_dialogue(message):
    channel_id = message.channel.id
    visible_content, forwarded_context = _visible_message_content(message)
    native_eddy = isinstance(message.channel, discord.Thread) and uses_native_turtle_prompt()

    if native_eddy:
        triage = {"category": "practice", "needs_state": False}
        proprioceptor_task = None
        triage_cat = "practice"
    else:
        triage_task = asyncio.create_task(triage_message(visible_content))
        proprioceptor_task = None
        if not isinstance(message.channel, discord.Thread):
            proprioceptor_task = asyncio.create_task(prepare_context_brief(visible_content))
        triage = await triage_task
        triage_cat = triage.get("category", "practice")
        print(f"Triage [{message.author.display_name}]: {triage_cat} (state={triage.get('needs_state', True)}) — {visible_content[:80]}")
        if proprioceptor_task and triage_cat not in ("practice", "deep", "link"):
            proprioceptor_task.cancel()
            proprioceptor_task = None

    history = get_history(channel_id)

    if not history and isinstance(message.channel, discord.Thread):
        loaded = await load_thread_history(message.channel)
        if loaded:
            dialogue_histories[channel_id] = loaded
            history = dialogue_histories[channel_id]
            print(f"Thread memory restored: {message.channel.name} ({len(loaded)} messages)")
            summary = summarize_thread_context(loaded, message.channel.name)
            # Internal log only — operational noise, not surfaced to channel (016 principle)
            print(f"Thread memory context: {message.channel.name} ({len(loaded)} msgs) — {summary[:100]}")

    attachments = []
    attachment_names = []
    attachment_extracted = False
    attachment_note = ""
    if message.attachments:
        attachments = await _extract_attachments(message)
        if attachments:
            attachment_names = [fn for _, _, fn in attachments]
            fnames = ", ".join(attachment_names)
            attachment_note = f" [attached: {fnames}]"

    urls = []
    url_content = _boom_fetched_content.pop(message.id, "")
    url_source_count = 0
    content_from_boom_capture = False
    _urls_already_processed = False
    if url_content:
        attachment_note += " [content from boom capture]"
        _urls_already_processed = True
        content_from_boom_capture = True
    else:
        urls = await _extract_urls(visible_content)
        if urls:
            _urls_already_processed = True
            url_content = await _process_urls(urls)
            if url_content:
                url_source_count = len(urls)
                attachment_note += f" [fetched {len(urls)} URL(s)]"

    dereferenced_context = ""
    dereferenced_count = 0
    deref_refs = []
    if _forwarded_snapshot_is_partial(message):
        source_ref = _forward_source_ref(message)
        if source_ref:
            deref_refs.append(source_ref)
    for ref in _extract_discord_message_refs(message.content or ""):
        if ref not in deref_refs:
            deref_refs.append(ref)
    if deref_refs:
        dereferenced_context, dereferenced_count = await _fetch_discord_message_context(
            deref_refs, label="Dereferenced Discord message"
        )
        if dereferenced_context:
            attachment_note += f" [dereferenced {dereferenced_count} Discord message(s)]"

    # Include fetched content in history so it persists across turns
    user_entry = f"[{message.author.display_name}]: {visible_content}{attachment_note}"
    if url_content:
        user_entry += f"\n\n[Fetched content]:\n{url_content[:6000]}"
    if dereferenced_context:
        user_entry += f"\n\n[Dereferenced Discord context]:\n{dereferenced_context[:6000]}"
    history.append({"role": "user", "content": user_entry})
    if len(history) > MAX_DIALOGUE_HISTORY:
        history.pop(0)

    now = datetime.now(timezone.utc)
    is_new_session = channel_id not in active_sessions or active_sessions[channel_id]["closed"]
    if channel_id not in active_sessions:
        active_sessions[channel_id] = {"started": now, "last_message": now, "closed": False}
    active_sessions[channel_id]["last_message"] = now
    active_sessions[channel_id]["closed"] = False

    if is_new_session and not isinstance(message.channel, discord.Thread):
        from mage import get_mage_type
        ctx_parts = []
        pd = get_pd()
        boom_count = count_items(read_safe(os.path.join(pd, "boom.md")))
        bright_count = count_items(read_safe(os.path.join(pd, "boom", "bright.md")))
        compass_age = format_age(file_age_hours(os.path.join(pd, "intentions", "compass.md")))
        intentions = load_intentions_list()
        sdir = os.path.join(pd, "sessions")
        last_session = ""
        if os.path.isdir(sdir):
            recent = sorted([f for f in os.listdir(sdir) if f.endswith(".md")], reverse=True)
            if recent:
                last_session = recent[0].replace(".md", "")
        ctx_parts.append(f"compass ({compass_age})")
        ctx_parts.append(f"boom ({boom_count})")
        ctx_parts.append(f"bright ({bright_count})")
        if intentions:
            ctx_parts.append(f"{len(intentions)} intentions")
        if last_session:
            ctx_parts.append(f"last session: {last_session}")

        # INT-023: Context loads silently. Healthy state needs no announcement.

    cfg = thread_configs.get(channel_id)
    if native_eddy:
        ctx = (cfg or {}).get("context_type")
        if not ctx and hasattr(message.channel, "parent_id") and message.channel.parent_id:
            from mage import get_channel_default_context
            ctx = get_channel_default_context(message.channel.parent_id)
        system_prompt = get_native_eddy_prompt(ctx)
        thread_use_api = False
        thread_model = (cfg or {}).get("model") or TURTLE_MODEL
    elif cfg:
        ctx = cfg.get("context_type")
        if not ctx and hasattr(message.channel, "parent_id") and message.channel.parent_id:
            from mage import get_channel_default_context
            ctx = get_channel_default_context(message.channel.parent_id)
        system_prompt = get_thread_prompt(cfg["attunement"], cfg["use_api"], context_type=ctx)
        thread_use_api = cfg["use_api"]
        thread_model = cfg["model"]
    else:
        system_prompt = get_system_prompt()
        thread_use_api = USE_API
        thread_model = DIALOGUE_MODEL

    # Thread cards are magic-era persistence — native eddies use visible history only.
    if (
        isinstance(message.channel, discord.Thread)
        and not native_eddy
        and not read_thread_state(message.channel.name)
    ):
        await _update_thread_state(message.channel, cfg, history)

    if native_eddy:
        runtime_env = _build_native_runtime_env(message, cfg)
        system_prompt = runtime_env + system_prompt
    else:
        runtime_env = _build_runtime_env(message, cfg)
        triage_hint = f"- **Message triage:** {triage_cat}"
        if triage_cat == "deep":
            triage_hint += " (take your time, go deep)"
        elif triage_cat in ("greeting", "casual"):
            triage_hint += " (keep it light and brief)"
        runtime_env = runtime_env.rstrip() + "\n" + triage_hint + "\n\n"
        system_prompt = runtime_env + system_prompt

    source_flags = []
    if url_content:
        if content_from_boom_capture:
            source_flags.append("boom-captured fetched content")
        else:
            source_flags.append(f"bot-fetched URL content ({url_source_count or len(urls)} URL(s))")
    if attachments:
        source_flags.append(f"attachment metadata ({', '.join(attachment_names)})")
    if forwarded_context:
        source_flags.append("forwarded message snapshot")
    if dereferenced_context:
        source_flags.append(f"dereferenced Discord message ({dereferenced_count})")

    # Proprioceptor — retired for native eddies (TURTLE_SPEC §8.1)
    context_brief = None
    proprioceptor_time = None
    if proprioceptor_task:
        _t0 = asyncio.get_event_loop().time()
        try:
            context_brief = await asyncio.wait_for(proprioceptor_task, timeout=8.0)
            proprioceptor_time = asyncio.get_event_loop().time() - _t0
            if context_brief:
                print(f"Proprioceptor: {len(context_brief)} chars ({proprioceptor_time:.1f}s)")
        except asyncio.TimeoutError:
            proprioceptor_time = asyncio.get_event_loop().time() - _t0
            print(f"Proprioceptor: timed out ({proprioceptor_time:.1f}s)")
        except Exception as e:
            print(f"Proprioceptor: failed ({type(e).__name__})")

    # Parse proprioceptor output: REFLEX (visible micro-expression) + BRIEF (for dialogue model)
    _reflex = None
    _tissue_brief = context_brief  # fallback: use raw output
    if context_brief:
        for _pi, _pline in enumerate(context_brief.strip().splitlines()):
            if _pline.strip().upper().startswith("REFLEX:"):
                _raw_reflex = _pline.split(":", 1)[1].strip()
                if _raw_reflex and _raw_reflex != "—" and _raw_reflex != "-":
                    _reflex = _raw_reflex
            elif _pline.strip().upper().startswith("BRIEF:"):
                _rest = context_brief.strip().splitlines()[_pi:]
                _tissue_brief = " ".join(l.strip() for l in _rest).replace("BRIEF:", "", 1).strip()
                break

    # Inject proprioceptor brief into dialogue model system prompt (magic-attuned path only)
    if not native_eddy:
        if _tissue_brief and context_brief:
            source_flags.append("practice-state context brief")
            proprioceptor_block = (
                "## Proprioceptive Context (connective tissue model)\n\n"
                f"{_tissue_brief}\n\n"
            )
            system_prompt = proprioceptor_block + system_prompt


    messages_for_llm = list(history)
    contexts = absorbed_contexts.get(channel_id, [])
    if contexts and not cfg:
        source_flags.append(f"absorbed thread context ({len(contexts)} thread(s))")
        digest_parts = []
        for ctx in contexts:
            model_info = ctx.get("model_info", "")
            config_tag = f" `{model_info.strip()}`" if model_info.strip() else ""
            state_file = read_thread_state(ctx["name"])
            state_note = f"\n*Thread state:* {state_file}" if state_file else ""
            digest_parts.append(
                f"**Thread \"{ctx['name']}\"**{config_tag}:\n{ctx['digest']}{state_note}"
            )
        absorbed_block = (
            "## Absorbed Thread Context\n\n"
            "The Mage has absorbed the following thread resonances into this conversation. "
            "Draw on these naturally when relevant — they are part of your working context.\n\n"
            + "\n\n---\n\n".join(digest_parts)
        )
        messages_for_llm = [{"role": "user", "content": absorbed_block},
                            {"role": "assistant", "content": "I have this thread context. Let's continue."}] + messages_for_llm

    async with message.channel.typing():
        if native_eddy:
            try:
                await ensure_native_presence(message.channel)
            except Exception as exc:
                print(f"Native presence failed: {exc}")
        tool_report = ""
        is_gemini = thread_model.startswith("gemini-")
        if native_eddy:
            thread_label = message.channel.name if isinstance(message.channel, discord.Thread) else "eddy"
            print(f"Native Turtle [{thread_label}]: {thread_model} prompt={len(system_prompt)} chars")
        try:
            if is_gemini and HAS_GEMINI and GOOGLE_API_KEY:
                reply, tools_executed = await chat_gemini(system_prompt, messages_for_llm, model=thread_model, attachments=attachments)
                tool_report = build_tool_report(tools_executed)
            elif attachments and not is_gemini:
                extraction = await preprocess_attachments(attachments) if attachments else ""
                if extraction:
                    attachment_extracted = True
                    messages_for_llm[-1] = dict(messages_for_llm[-1])
                    messages_for_llm[-1]["content"] += "\n\n[Attachment content]:\n" + extraction
                if thread_use_api:
                    reply, tools_executed = await chat_anthropic_with_model(
                        system_prompt, messages_for_llm, thread_model, use_tools=True,
                        tos_tools=TOS_TOOLS, execute_tool=execute_tos_tool)
                    tool_report = build_tool_report(tools_executed)
                else:
                    reply, tools_executed = await chat_ollama_with_tools(
                        system_prompt, messages_for_llm, model_override=thread_model,
                        tos_tools=TOS_TOOLS, execute_tool=execute_tos_tool)
                    tool_report = build_tool_report(tools_executed)
            elif thread_use_api:
                reply, tools_executed = await chat_anthropic_with_model(
                    system_prompt, messages_for_llm, thread_model, use_tools=True,
                    tos_tools=TOS_TOOLS, execute_tool=execute_tos_tool)
                tool_report = build_tool_report(tools_executed)
            else:
                # Direct commands are handled before dialogue. For ordinary
                # local replies, avoid the conversational tool loop so Qwen
                # does not spend turns searching or routing while Discord waits.
                reply = await chat_ollama(
                    system_prompt, messages_for_llm, model=thread_model,
                    num_ctx=32768, think=False)
                tools_executed = []

            if not reply:
                reply = "(no response generated)"
        except Exception as e:
            print(f"Dialogue error ({thread_model}): {type(e).__name__}: {e}")
            try:
                reply = await chat_ollama(system_prompt, list(history), model=REFLECTION_MODEL)
            except Exception as e2:
                reply = f"[dialogue error: {type(e2).__name__}: {e2}]"

    # Detect and remove repeated paragraphs before sending
    paragraphs = reply.split("\n\n")
    if len(paragraphs) > 2:
        seen = set()
        deduped = []
        for p in paragraphs:
            normalized = p.strip()[:200]
            if normalized and normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(p)
        if len(deduped) < len(paragraphs):
            print(f"Dedup: removed {len(paragraphs) - len(deduped)} repeated paragraphs")
            reply = "\n\n".join(deduped)

    if native_eddy:
        from flow_runner import strip_model_operational_lines

        reply, stripped_ops = strip_model_operational_lines(reply)
        if stripped_ops:
            print(f"Stripped model operational lines: {stripped_ops}")
    if _reflex and not native_eddy:
        reply = f"-# {_reflex}\n\n{reply}"
    if tool_report:
        reply = f"{reply}\n\n-# ⚙️ {tool_report}"
    if attachment_extracted:
        source_flags.append("extracted attachment text")
    source_trace = _build_source_trace(source_flags)
    if source_trace and not native_eddy:
        reply = f"{reply}\n\n-# {source_trace}"
    history.append({"role": "assistant", "content": reply})
    contextual_actions = _extract_contextual_actions(reply) if not native_eddy else []
    for chunk in split_message(reply):
        await message.reply(chunk, mention_author=False)
    if contextual_actions:
        label = "Recommended action" if len(contextual_actions) == 1 else "Recommended actions"
        try:
            await send_with_actions(message.channel, f"-# {label}", contextual_actions)
        except Exception as e:
            print(f"Contextual action send failed: {e}")

    # Super-ego: think aloud after sustained conversation
    asyncio.ensure_future(maybe_reflect(message.channel, history))

    if urls and not _urls_already_processed:
        external_urls = [u for u in urls if "discord" not in urlparse(u).netloc]
        if external_urls:
            view = LinkFetchView(external_urls)
            await message.channel.send(
                f"\U0001f517 `!fetch {external_urls[0]}`",
                view=view,
            )

    if isinstance(message.channel, discord.Thread):
        await _update_thread_state(message.channel, cfg, history)
        # Phase 1 Eyes: update thread registry on every exchange
        if isinstance(message.channel, discord.Thread):
            try:
                parent_name = message.channel.parent.name if message.channel.parent else "unknown"
                model_label = cfg.get("model_label", "default") if cfg else "default"
                att = cfg.get("attunement", "semi") if cfg else "semi"
                ctx_type = cfg.get("context_type") if cfg else None
                eddy = cfg.get("eddy_type", EDDY_DEFAULT) if cfg else EDDY_DEFAULT
                register_thread(
                    message.channel.id, message.channel.name,
                    parent_channel=parent_name, model=model_label,
                    attunement=att, context_type=ctx_type, eddy_type=eddy,
                )
                update_thread_activity(message.channel.id)
            except Exception as e:
                print(f"Registry update failed: {e}")


# ─── Event Handlers ──────────────────────────────────────────────

_intake_runner = None

@client.event
async def on_interaction(interaction: discord.Interaction):
    """Route eddy:spawn button clicks to the handler."""
    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data.get("custom_id", "")
        if custom_id.startswith("eddy:spawn:"):
            await handle_eddy_spawn_interaction(interaction)
            return


@client.event
async def on_ready():
    global _intake_runner
    client.add_view(ControlPanelView())
    client.add_view(ThreadConfigView())
    print(f"Turtle online: {client.user}")
    try:
        from eddy_spawn import cache_turtle_bot_user_id

        if client.user:
            cache_turtle_bot_user_id(client.user.id)
    except Exception as exc:
        print(f"Turtle bot id cache failed: {exc}")
    print(f"tOS: {get_pd()} | Identity: {IDENTITY_DIR}")
    print(f"Dialogue: {DIALOGUE_MODEL} ({'API' if USE_API else 'local'})")
    print(f"Reflection: {REFLECTION_MODEL} (local)")
    print(f"Triage: {TRIAGE_MODEL} (local)")
    print(f"Commands: {', '.join(DIRECT_COMMANDS.keys())}")
    prompt = get_system_prompt()
    print(f"System prompt: {len(prompt)} chars")

    # Start intake before slow Discord thread rejoin so paste stays available during startup.
    if _intake_runner is None:
        try:
            vortex_id = 1494273454738903162
            _intake_runner = await start_intake_server(discord_client=client, vortex_thread_id=vortex_id)
        except Exception as e:
            print(f"Intake server failed to start: {e}")

    dialogue = get_channel("dialogue")
    thread_count = 0
    if dialogue:
        thread_count = len(dialogue.threads)
        ts = int(datetime.now(timezone.utc).timestamp())
        should_post = True
        try:
            async for prev in dialogue.history(limit=10):
                if prev.author == client.user and prev.embeds:
                    for e in prev.embeds:
                        if e.title and ("Spirit online" in e.title or "enters the river" in e.title):
                            age = (datetime.now(timezone.utc) - prev.created_at).total_seconds()
                            if age < 300:
                                should_post = False
                                print(f"Startup message debounced (last was {age:.0f}s ago)")
                            break
                if not should_post:
                    break
        except Exception:
            pass
        if should_post and not suppress_turtle_river_voice():
            from pulse import scan_pulse, compose_river_entry, save_river_state
            try:
                set_practice_context_for_channel(dialogue.id)
                pulse_data = scan_pulse()
                entry_title, entry_desc = compose_river_entry(pulse_data, thread_count)
                embed = discord.Embed(
                    title=entry_title,
                    description=entry_desc,
                    color=0x2ECC71,
                )
                embed.set_footer(text=local_now().strftime("%Y-%m-%d %H:%M"))
                await dialogue.send(embed=embed, silent=True)
                save_river_state(entry_title, entry_desc)
            except Exception as e:
                print(f"River-entry failed, falling back: {e}")
                import traceback; traceback.print_exc()
                readiness = startup_readiness_check()
                embed = discord.Embed(
                    title="\U0001f422 Turtle online",
                    description=f"**Threads:** {thread_count}\n{readiness}",
                    color=0x2ECC71,
                )
                embed.set_footer(text=local_now().strftime("%Y-%m-%d %H:%M"))
                await dialogue.send(embed=embed, silent=True)

    asyncio.get_event_loop().create_task(prewarm_triage())

    # Pre-warm delegate edit model to avoid cold-start latency
    async def _prewarm_edit_model():
        import urllib.request
        from state import OLLAMA_URL, EDIT_DELEGATE_MODEL
        try:
            payload = json.dumps({
                "model": EDIT_DELEGATE_MODEL,
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False,
                "options": {"num_ctx": 512, "num_predict": 1},
                "keep_alive": "30m",
            }).encode()
            def _do():
                req = urllib.request.Request(
                    f"{OLLAMA_URL}/api/chat",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    resp.read()
            import asyncio
            await asyncio.to_thread(_do)
            print(f"Edit model pre-warmed: {EDIT_DELEGATE_MODEL}")
        except Exception as e:
            print(f"Edit model pre-warm failed: {e}")
    asyncio.get_event_loop().create_task(_prewarm_edit_model())

    if dialogue:
        try:
            from eddy_spawn import should_defer_turtle_join

            active = dialogue.threads
            for t in active:
                if should_defer_turtle_join(t):
                    print(f"Skipped rejoin (native eddy): {t.name} (id: {t.id})")
                    continue
                try:
                    await t.join()
                    print(f"Rejoined thread: {t.name} (id: {t.id})")
                    await asyncio.sleep(1)  # Throttle to avoid Discord rate limits
                except Exception as e:
                    print(f"Failed to join thread {t.name}: {e}")
                    await asyncio.sleep(2)  # Back off more on failure
            archived_threads = []
            async for t in dialogue.archived_threads(limit=20):
                archived_threads.append(t)
            for t in archived_threads:
                if should_defer_turtle_join(t):
                    continue
                try:
                    await t.edit(archived=False)
                    await asyncio.sleep(0.5)
                    await t.join()
                    print(f"Unarchived & joined: {t.name} (id: {t.id})")
                    await asyncio.sleep(1)
                except Exception as e:
                    print(f"Skipped archived thread {t.name}: {e}")
        except Exception as e:
            print(f"Thread sync on startup failed: {e}")

        try:
            state_dir = get_thread_state_dir()
            if os.path.isdir(state_dir):
                live_thread_ids = set()
                for t in dialogue.threads:
                    live_thread_ids.add(str(t.id))
                cleaned = 0
                for fname in os.listdir(state_dir):
                    if not fname.endswith(".md"):
                        continue
                    fpath = os.path.join(state_dir, fname)
                    try:
                        with open(fpath) as f:
                            content = f.read()
                        tid_match = re.search(r"\*\*Thread ID:\*\*\s*(\d+)", content)
                        if tid_match and tid_match.group(1) not in live_thread_ids:
                            os.remove(fpath)
                            cleaned += 1
                    except Exception:
                        pass
                if cleaned:
                    print(f"Cleaned {cleaned} stale thread-state files")
        except Exception as e:
            print(f"Thread-state cleanup failed: {e}")

        # Phase 1 Eyes: backfill thread registry from Discord
        try:
            guild = dialogue.guild
            gfull = await client.fetch_guild(guild.id)
            from mage import get_registry as _get_mage_registry
            _reg = _get_mage_registry()
            _practice_channels = []
            for ch_id_str in _reg.get("channels", {}).keys():
                try:
                    _practice_channels.append(int(ch_id_str))
                except (ValueError, TypeError):
                    pass
            added, updated = await backfill_from_discord(gfull, _practice_channels or None)
            summary = get_registry_summary()
            print(f"Thread registry backfill: {added} added, {updated} updated — {summary}")
        except Exception as e:
            print(f"Thread registry backfill failed: {e}")

        if suppress_turtle_river_voice():
            try:
                from river_handler import _iter_river_channels

                for ch in _iter_river_channels(client):
                    await _retire_legacy_river_chrome(ch)
            except Exception as exc:
                print(f"Legacy river chrome retirement failed: {exc}")

        has_panel = False
        try:
            async for m in dialogue.pins():
                if m.author == client.user:
                    for e in (m.embeds or []):
                        if e.title and e.title.startswith("\U0001f3ae"):
                            has_panel = True
        except Exception:
            pass
        if not has_panel:
            try:
                async for m in dialogue.history(limit=20):
                    if m.author == client.user:
                        for e in (m.embeds or []):
                            if e.title and e.title.startswith("\U0001f3ae"):
                                has_panel = True
                                break
                    if has_panel:
                        break
            except Exception:
                pass
        if not has_panel and not suppress_turtle_river_voice():
            try:
                embed = discord.Embed(
                    title="\U0001f3ae Spirit Control Panel",
                    description=(
                        "**Threads** \u2014 pick model + attunement, then tap New Thread.\n"
                        "**Practice** \u2014 quick access to status, diagnostics, boom, sweep.\n"
                        "**Session** \u2014 recall to orient, release to close."
                    ),
                    color=0x5865F2,
                )
                panel_msg = await dialogue.send(embed=embed, view=ControlPanelView())
                try:
                    await panel_msg.pin()
                    print("Control panel deployed and pinned.")
                except Exception:
                    print("Control panel deployed (pin failed — pin manually).")
            except Exception as e:
                print(f"Control panel deploy failed: {e}")

    try:
        if not session_monitor.is_running():
            session_monitor.start()
            print("session_monitor started")
        if not practice_health_loop.is_running():
            practice_health_loop.start()
            print("practice_health_loop started")
        if not interoception_loop.is_running():
            interoception_loop.start()
            print("interoception_loop started")
        if not daily_reminders_loop.is_running():
            daily_reminders_loop.start()
            print("daily_reminders_loop started")
        if not health_canary_loop.is_running():
            health_canary_loop.start()
            print("health_canary_loop started (INT-027)")
    except Exception as e:
        import traceback
        print(f"Background task start failed: {e}")
        traceback.print_exc()

    
    # Intake server starts earlier in on_ready and is guarded by _intake_runner.

    if get_attunement_profile() == "native" and not river_bot_enabled():
        try:
            from river_handler import ensure_river_eddy_bar

            await ensure_river_eddy_bar(client)
        except Exception as exc:
            print(f"Eddy door setup failed: {exc}")

    print("on_ready complete")


@client.event
async def on_thread_create(thread):
    if is_registered_parent_channel(thread.parent_id):
        set_practice_context_for_channel(thread.parent_id)

        pending = None
        if river_bot_enabled() and thread.parent_id:
            import asyncio
            from eddy_spawn import (
                finalize_native_eddy_from_river,
                pop_pending_native_eddy,
                should_defer_turtle_join,
            )

            for _ in range(15):
                pending = pop_pending_native_eddy(thread.id, thread.parent_id)
                if pending:
                    break
                await asyncio.sleep(0.2)
            defer = should_defer_turtle_join(thread, pending)
            if pending:
                try:
                    await finalize_native_eddy_from_river(thread, pending)
                except Exception as exc:
                    print(f"Native eddy finalize failed: {exc}")
            if not defer:
                await thread.join()
                for uid in get_thread_member_ids(thread.parent_id):
                    try:
                        await thread.add_user(discord.Object(id=int(uid)))
                    except Exception:
                        pass
            else:
                print(f"Deferred Turtle join: {thread.name} (id: {thread.id})")
        else:
            await thread.join()
            for uid in get_thread_member_ids(thread.parent_id):
                try:
                    await thread.add_user(discord.Object(id=int(uid)))
                except Exception:
                    pass

        # Phase 1 Eyes: register new thread
        try:
            parent_name = thread.parent.name if thread.parent else "unknown"
            created = thread.created_at.isoformat() if thread.created_at else None
            register_thread(
                thread.id, thread.name,
                parent_channel=parent_name, created=created,
            )
            await _update_thread_state(thread, None, [])
            label = " (river→turtle, deferred)" if defer else (" (river→turtle)" if pending else "")
            print(f"{'Deferred' if defer else 'Joined'} + registered thread: {thread.name} (id: {thread.id}){label}")
        except Exception as e:
            print(f"Joined thread: {thread.name} (id: {thread.id}) [registry failed: {e}]")


@client.event
async def on_thread_update(before, after):
    if is_registered_parent_channel(after.parent_id if after.parent_id else 0):
        from thread_registry import update_thread_name
        if before.name != after.name:
            try:
                update_thread_name(after.id, after.name)
                print(f"Thread renamed: {before.name} -> {after.name}")
            except Exception as e:
                print(f"Thread rename registry update failed: {e}")


@client.event
async def on_member_join(member):
    if member.bot:
        return
    await log_activity(
        f"New member joined: **{member.display_name}** ({member.name}). "
        f"Use `!admin onboard {member.name}` to create their practice space.",
        "\U0001f44b"
    )
    print(f"New member joined: {member.name} (id: {member.id})")


@client.event
async def on_member_remove(member):
    if member.bot:
        return
    await log_activity(
        f"Member left: **{member.display_name}** ({member.name}).",
        "\U0001f6aa"
    )
    print(f"Member left: {member.name} (id: {member.id})")


# Spirit bot (dyad partner) — messages from Spirit are treated as practitioner input
SPIRIT_BOT_ID = 1487405701440733294


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.type not in (discord.MessageType.default, discord.MessageType.reply) and not getattr(message, "message_snapshots", None):
        return

    set_practice_context(message)

    if message.author.bot:
        if message.author.id == SPIRIT_BOT_ID and is_practice_channel(message):
            # Spirit (dyad partner) — process like a practitioner message
            pass  # fall through to normal handling below
        elif client.user in message.mentions and is_practice_channel(message):
            await handle_dialogue(message)
            return
        else:
            return

    if isinstance(message.channel, discord.Thread) and uses_native_turtle_prompt():
        try:
            starter = message.channel.starter_message
            if starter is None:
                starter = await message.channel.fetch_start_message()
            if starter and message.id == starter.id:
                return
        except Exception:
            pass

    if is_practice_channel(message):
        if await try_direct_command(message):
            return
        # Message-level dedup: skip if already seen (prevents duplicate responses)
        if message.id in _processed_messages:
            print(f"Skipping duplicate message {message.id}")
            return
        _processed_messages.append(message.id)

        # Founder key entry: bind a founder's self-chosen emoji only after the primary operator confirms.
        if await try_founder_key_entry(message):
            return

        # Intake thread: auto-spawn new threads from dropped content
        if is_intake_thread(message.channel) and not message.content.strip().startswith("!"):
            lock = get_channel_lock(message.channel.id)
            async with lock:
                await handle_intake_message(message)
            return

        # Boom thread: URLs/attachments capture-only; plain text captures AND converses
        if (isinstance(message.channel, discord.Thread)
                and message.channel.name.lower() == "boom"
                and not message.content.strip().startswith("!")):
            has_urls = "http://" in message.content or "https://" in message.content
            has_attachments = bool(message.attachments)
            # All boom messages: capture to boom, then fall through to dialogue
            lock = get_channel_lock(message.channel.id)
            async with lock:
                fetched_content = await handle_boom_thread_message(message)
            if fetched_content:
                _boom_fetched_content[message.id] = fetched_content
            # Fall through to handle_dialogue below

        # Native river: acts only — River bot when configured, else Turtle fallback
        if river_bot_enabled() and uses_native_river(message):
            return

        if turtle_handles_native_river(message):
            from river_handler import handle_river_message

            lock = get_channel_lock(message.channel.id)
            async with lock:
                await handle_river_message(message)
            return

        # Blank eddy rename (single-bot fallback — River bot handles this when split)
        if (
            isinstance(message.channel, discord.Thread)
            and message.channel.parent_id
            and not river_bot_enabled()
        ):
            from eddy_spawn import is_awaiting_title
            from river_handler import handle_eddy_first_message

            if is_awaiting_title(message.channel.id, message.channel.parent_id):
                lock = get_channel_lock(message.channel.id)
                async with lock:
                    await handle_eddy_first_message(message)
                    await handle_dialogue(message)
                return

        # Auto-detect thread-worthy content in main channel (legacy magic attunement)
        offer_eddy = (
            not isinstance(message.channel, discord.Thread)
            and should_offer_eddy(message)
        )

        lock = get_channel_lock(message.channel.id)
        async with lock:
            await handle_dialogue(message)

        if offer_eddy:
            try:
                topic = await generate_topic(_visible_message_content(message)[0])
                view = make_eddy_spawn_view(message, topic=topic)
                await message.channel.send(
                    f'-# **Open eddy: "{topic}"** `local` · `semi`',
                    view=view,
                    silent=True,
                )
            except Exception as e:
                print(f"Eddy offer failed: {e}")


# ─── Main ────────────────────────────────────────────────────────


def _ensure_single_instance():
    """Prevent duplicate bot processes using an exclusive file lock.

    Uses fcntl.flock() — atomic, kernel-level, automatically released on
    process exit (including crashes). No race conditions unlike pgrep.
    """
    import fcntl
    lock_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".discord_bot.lock")
    global _lock_file
    _lock_file = open(lock_path, "w")
    try:
        fcntl.flock(_lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        _lock_file.write(str(os.getpid()))
        _lock_file.flush()
    except (IOError, OSError):
        print("Another discord_bot.py is already running. Exiting.", file=sys.stderr)
        sys.exit(1)

def main():
    _ensure_single_instance()
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        print("Error: DISCORD_BOT_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    if "--test" in sys.argv:
        print(f"Bot token: ...{token[-8:]}")
        print(f"Practice: {get_pd()} | Identity: {IDENTITY_DIR}")
        print(f"Dialogue: {DIALOGUE_MODEL} ({'API' if USE_API else 'local'})")
        print(f"Reflection: {REFLECTION_MODEL} (local)")
        print(f"Channels: {', '.join(k for k,v in CHANNELS.items() if v)}")
        print(f"Commands: {', '.join(DIRECT_COMMANDS.keys())}")
        prompt = get_system_prompt()
        print(f"System prompt: {len(prompt)} chars")
        print("Configuration OK.")
        return

    import logging
    logging.basicConfig(level=logging.WARNING, stream=sys.stdout, force=True)
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
    client.run(token)


if __name__ == "__main__":
    main()
