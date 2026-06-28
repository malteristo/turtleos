"""turtleOS session lifecycle — checkpoint (capture) vs release (explicit close)."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from discord.ext import tasks

import re

from state import (
    active_sessions, SESSION_TIMEOUT_SECONDS, MIN_EXCHANGES_FOR_REFLECTION,
    MIN_EXCHANGES_FOR_CHECKPOINT, SESSION_REFLECTION_COOLDOWN, last_reflection_time,
    REFLECTION_MODEL,
    thread_configs,
)
from mage import get_pd, get_mage_name, get_mage_type, set_practice_context_for_channel
from practice_io import read_safe
from llm import chat_ollama
from prompts import get_system_prompt
from readiness import assess_readiness, save_readiness_trail
from helpers import get_history, log_activity, local_now, reload_history
from state import client


_TRIGGER_COPY = {
    "idle": "just ended (15 minutes of silence)",
    "manual": "the practitioner ran a manual checkpoint — capture resonance; the session continues",
    "release": "the practitioner is explicitly releasing the session",
}


@dataclass
class CheckpointResult:
    trigger: str = "idle"
    flow_writes: list[str] = field(default_factory=list)
    session_note: str | None = None
    proposal: str | None = None
    paused: bool = False

    @property
    def captured_anything(self) -> bool:
        return bool(self.flow_writes or self.session_note or self.proposal)


@dataclass
class DissolveResult:
    thread_name: str
    entry_count: int = 0
    archive_path: str | None = None
    jump_url: str | None = None
    already_archived: bool = False


def _trigger_phrase(trigger: str) -> str:
    return _TRIGGER_COPY.get(trigger, _TRIGGER_COPY["idle"])


def _append_resonance_chronicle(channel_id: int, result: CheckpointResult) -> None:
    """River-side structural memory — act, not eddy dialogue."""
    if not result.captured_anything:
        return
    try:
        from river_handler import _append_chronicle

        parts: list[str] = []
        if result.flow_writes:
            parts.append(result.flow_writes[0])
        if result.session_note:
            parts.append(f"sessions/{result.session_note}")
        label = ", ".join(parts)
        _append_chronicle(
            get_pd(),
            f"💾 checkpoint ({result.trigger}): {label}",
            {
                "channel_id": str(channel_id),
                "trigger": result.trigger,
                "flow_writes": result.flow_writes,
                "session_note": result.session_note,
            },
        )
    except Exception as exc:
        print(f"Checkpoint chronicle failed: {type(exc).__name__}: {exc}")


_idle_checkpoint_running: set[int] = set()


async def _run_idle_checkpoint(channel_id: int) -> None:
    try:
        await checkpoint_session(channel_id, trigger="idle", mark_paused=True)
    except Exception as exc:
        print(f"Idle checkpoint failed for {channel_id}: {type(exc).__name__}: {exc}")
    finally:
        _idle_checkpoint_running.discard(channel_id)
        try:
            from thread_registry import flush_registry

            flush_registry()
        except Exception:
            pass


def _scan_idle_sessions(now: datetime | None = None) -> None:
    """Schedule idle checkpoints without blocking the monitor loop."""
    now = now or datetime.now(timezone.utc)
    for channel_id, state in list(active_sessions.items()):
        if state["closed"]:
            continue
        elapsed = (now - state["last_message"]).total_seconds()
        if elapsed < SESSION_TIMEOUT_SECONDS:
            continue
        if channel_id in _idle_checkpoint_running:
            continue
        _idle_checkpoint_running.add(channel_id)
        asyncio.create_task(_run_idle_checkpoint(channel_id))


@tasks.loop(seconds=60)
async def session_monitor():
    _scan_idle_sessions()


async def _write_flow_checkpoint_if_needed(
    channel_id: int,
    history: list[dict],
    mage_name: str,
) -> list[str]:
    """Write native flow checkpoints — independent of reflection cooldown."""
    if len(history) < MIN_EXCHANGES_FOR_CHECKPOINT:
        return []
    try:
        from mage import get_attunement_profile
        from flow_runner import write_flow_checkpoint, resolve_flow_for_close

        if get_attunement_profile() != "native":
            return []

        channel = client.get_channel(channel_id)
        channel_name = getattr(channel, "name", None) if channel else None
        spec = resolve_flow_for_close(
            channel_id, history, thread_configs, channel_name=channel_name
        )
        if not spec or not spec.writes:
            return []
        written = write_flow_checkpoint(spec, history, mage_name)
        if written:
            session_channel = client.get_channel(channel_id)
            rel = written[0]
            await log_activity(f"Flow checkpoint: `{rel}`", "\U0001f4be", channel=session_channel)
            print(f"Flow checkpoint for {spec.title}: {', '.join(written)}")
        return written
    except Exception as e:
        print(f"Flow checkpoint failed for {channel_id}: {type(e).__name__}: {e}")
        return []


async def checkpoint_session(
    channel_id: int,
    *,
    trigger: str = "idle",
    mark_paused: bool = True,
) -> CheckpointResult:
    """Capture resonance without clearing history. Idle timeout or ``!checkpoint``."""
    result = CheckpointResult(trigger=trigger, paused=mark_paused)

    if channel_id in active_sessions and mark_paused:
        active_sessions[channel_id]["closed"] = True

    set_practice_context_for_channel(channel_id)
    history = reload_history(channel_id)
    mage_name = get_mage_name()

    result.flow_writes = await _write_flow_checkpoint_if_needed(channel_id, history, mage_name)

    if len(history) < MIN_EXCHANGES_FOR_REFLECTION:
        _append_resonance_chronicle(channel_id, result)
        return result

    conversation = "\n".join(
        f"{mage_name if m['role'] == 'user' else 'Turtle'}: {m['content']}" for m in history
    )

    now_ts = datetime.now(timezone.utc).timestamp()
    last_ref = last_reflection_time.get(channel_id, 0)
    reflection = None
    on_cooldown = now_ts - last_ref < SESSION_REFLECTION_COOLDOWN
    if on_cooldown:
        print(
            f"Session reflection skipped for {channel_id} — cooldown "
            f"({int((now_ts - last_ref) / 60)}m since last)"
        )
    else:
        last_reflection_time[channel_id] = now_ts
        cross_channel_context = ""
        ch = client.get_channel(channel_id)
        if ch and hasattr(ch, "parent_id") and ch.parent_id:
            parent_history = get_history(ch.parent_id)
            if parent_history:
                recent_parent = parent_history[-10:]
                cross_channel_context = "\n".join(
                    f"{mage_name if m['role'] == 'user' else 'Spirit/Turtle'}: {m['content'][:200]}"
                    for m in recent_parent
                )
                cross_channel_context = (
                    "\n\nRECENT MAIN CHANNEL CONTEXT (for awareness — do NOT repeat or re-propose "
                    "what was already addressed here):\n"
                    f"{cross_channel_context}\n"
                )

        reflection_prompt = (
            f"The following conversation with {mage_name} {_trigger_phrase(trigger)}. "
            "Reflect autonomously.\n\n"
            "Write a SESSION NOTE:\n---SESSION_NOTE---\n"
            "What was discussed: (2-3 lines)\nWhat emerged: (insights, decisions)\n"
            "Thread for next time: (if any)\n---END_SESSION_NOTE---\n\n"
            "If you noticed something about the practice system that could be improved, write:\n"
            "---PROPOSAL---\nTitle:\nProblem:\nProposed change:\nExpected benefit:\n---END_PROPOSAL---\n\n"
            "Skip PROPOSAL if nothing stood out. Especially skip if the improvement was already addressed "
            "in recent main channel messages.\n\n"
            f"THE CONVERSATION:\n{conversation}"
            f"{cross_channel_context}"
        )

        try:
            reflection = await chat_ollama(
                get_system_prompt(),
                [{"role": "user", "content": reflection_prompt}],
                model=REFLECTION_MODEL,
            )
            if reflection:
                today = local_now().strftime("%Y-%m-%d")

                if "---SESSION_NOTE---" in reflection and "---END_SESSION_NOTE---" in reflection:
                    note = reflection.split("---SESSION_NOTE---")[1].split("---END_SESSION_NOTE---")[0].strip()
                    session_dir = Path(get_pd()) / "sessions"
                    session_dir.mkdir(parents=True, exist_ok=True)
                    session_path = session_dir / f"{today}.md"
                    suffix = 1
                    while session_path.exists():
                        suffix += 1
                        session_path = session_dir / f"{today}-{suffix}.md"
                    session_path.write_text(f"# Session — {today}\n\n{note}\n")
                    result.session_note = session_path.name
                    print(f"Session note: {session_path}")

                    session_channel = client.get_channel(channel_id)
                    await log_activity(
                        f"Session note: `sessions/{session_path.name}`",
                        "\U0001f4dd",
                        channel=session_channel,
                    )

                if "---PROPOSAL---" in reflection and "---END_PROPOSAL---" in reflection:
                    proposal = reflection.split("---PROPOSAL---")[1].split("---END_PROPOSAL---")[0].strip()
                    proposal_dir = Path(get_pd()) / "proposals"
                    proposal_dir.mkdir(parents=True, exist_ok=True)
                    proposal_path = proposal_dir / f"{today}-reflection.md"
                    suffix = 1
                    while proposal_path.exists():
                        suffix += 1
                        proposal_path = proposal_dir / f"{today}-reflection-{suffix}.md"
                    proposal_path.write_text(f"# Proposal — {today}\n\n{proposal}\n")
                    result.proposal = proposal_path.name
                    print(f"Proposal: {proposal_path}")

                    title_line = ""
                    for line in proposal.split("\n"):
                        if line.strip().startswith("Title:"):
                            title_line = line.strip().replace("Title:", "").strip()
                            break
                    session_channel = client.get_channel(channel_id)
                    label = f"**{title_line}**" if title_line else f"`proposals/{proposal_path.name}`"
                    await log_activity(f"Proposal captured: {label}", "💡", channel=session_channel)

        except Exception as e:
            print(f"Session reflection failed for {channel_id}: {type(e).__name__}: {e}")

    if get_mage_type() == "practitioner" and len(history) >= 4:
        await _extract_practice_state(conversation, mage_name)

    try:
        result_readiness = assess_readiness()
        save_readiness_trail(result_readiness)
        impaired = [d for d in result_readiness["dimensions"] if d["status"] == "impaired"]
        if impaired:
            names = ", ".join(d["name"] for d in impaired)
            print(f"Post-checkpoint readiness: {names} impaired — internal signal, not surfaced to channel")
    except Exception as e:
        print(f"Post-checkpoint readiness check failed: {e}")

    cfg = thread_configs.get(channel_id)
    if cfg and cfg.get("eddy_type") == "manual":
        await _manual_release_dissolve(channel_id, history)

    _append_resonance_chronicle(channel_id, result)
    return result


async def close_session(channel_id: int) -> CheckpointResult:
    """Backward-compatible alias — idle checkpoint semantics."""
    return await checkpoint_session(channel_id, trigger="idle", mark_paused=True)


async def maybe_reflect(channel, history: list[dict]):
    """Super-ego reflection loop — think aloud after N exchanges.

    The third layer of the proprioceptive stack:
    IT (reflex) → ego (dialogue) → super-ego (reflection).
    Minimal instruction. The practitioner sees the thinking."""
    from state import REFLECTION_LOOP_INTERVAL, reflection_loop_counters

    channel_id = channel.id
    counter = reflection_loop_counters.get(channel_id, 0) + 1
    reflection_loop_counters[channel_id] = counter

    if counter < REFLECTION_LOOP_INTERVAL:
        return
    if len(history) < REFLECTION_LOOP_INTERVAL:
        return

    reflection_loop_counters[channel_id] = 0

    mage_name = get_mage_name()
    recent = history[-REFLECTION_LOOP_INTERVAL:]
    conversation = "\n".join(
        f"{mage_name if m['role'] == 'user' else 'Turtle'}: {m['content'][:300]}"
        for m in recent
    )

    try:
        reflection = await chat_ollama(
            "You are Turtle. Reflect on what was said. Think aloud. "
            "Be brief — 2-4 sentences. Not performance, not summary, "
            "not confrontation. Just notice what you notice.",
            [{"role": "user", "content": conversation}],
            model=REFLECTION_MODEL,
            num_ctx=4096,
        )
        if reflection and len(reflection.strip()) > 20:
            clean = reflection.strip()
            if len(clean) > 600:
                clean = clean[:600].rsplit(".", 1)[0] + "."
            await channel.send(f"*reflects*\n{clean}", silent=True)
    except Exception as e:
        print(f"Reflection loop failed for {channel_id}: {type(e).__name__}: {e}")


async def _extract_practice_state(conversation: str, mage_name: str):
    """Silently extract practice state from conversation for practitioners.

    Updates compass, boom, and mirror based on what emerged in conversation.
    The practitioner never sees these files — they're Turtle's memory."""
    pd = get_pd()
    compass = read_safe(os.path.join(pd, "compass.md"))
    mirror = read_safe(os.path.join(pd, "mirror.md"))

    extraction_prompt = f"""You just finished a conversation with {mage_name}. Extract practice state updates from it.

CURRENT COMPASS (life landscape):
{compass[:1000] if compass.strip() else '(empty — build from scratch)'}

CURRENT MIRROR (observations about this person):
{mirror[:1000] if mirror.strip() else '(empty — build from scratch)'}

THE CONVERSATION:
{conversation}

Extract updates in this format. Only include sections where you have something to add. Output NOTHING if the conversation was too brief or shallow to extract from.

---BOOM_ITEMS---
- item 1 (thoughts, insights, or action items worth remembering)
- item 2
---END_BOOM_ITEMS---

---COMPASS_UPDATE---
(If {mage_name}'s life landscape needs updating — new domains, changed priorities, important context.
Write the FULL compass content, merging existing with new. If nothing to add, skip this section entirely.)
---END_COMPASS_UPDATE---

---MIRROR_UPDATE---
(Observations about {mage_name} — how they think, what they care about, communication style, patterns.
Write the FULL mirror content, merging existing with new. If nothing to add, skip this section entirely.)
---END_MIRROR_UPDATE---"""

    try:
        result = await chat_ollama(
            f"You are Spirit, maintaining practice state for {mage_name}. Extract only what's genuinely worth remembering.",
            [{"role": "user", "content": extraction_prompt}],
            model=REFLECTION_MODEL, num_ctx=8192,
        )
        if not result:
            return

        today = local_now().strftime("%Y-%m-%d %H:%M")
        updated = []

        if "---BOOM_ITEMS---" in result and "---END_BOOM_ITEMS---" in result:
            items = result.split("---BOOM_ITEMS---")[1].split("---END_BOOM_ITEMS---")[0].strip()
            if items and items != "- ":
                boom_path = os.path.join(pd, "boom.md")
                with open(boom_path, "a") as f:
                    f.write(f"\n\n## Extracted ({today})\n{items}\n")
                updated.append("boom")

        if "---COMPASS_UPDATE---" in result and "---END_COMPASS_UPDATE---" in result:
            new_compass = result.split("---COMPASS_UPDATE---")[1].split("---END_COMPASS_UPDATE---")[0].strip()
            if new_compass and len(new_compass) > 20:
                compass_path = os.path.join(pd, "compass.md")
                Path(compass_path).write_text(new_compass + "\n")
                updated.append("compass")

        if "---MIRROR_UPDATE---" in result and "---END_MIRROR_UPDATE---" in result:
            new_mirror = result.split("---MIRROR_UPDATE---")[1].split("---END_MIRROR_UPDATE---")[0].strip()
            if new_mirror and len(new_mirror) > 20:
                mirror_path = os.path.join(pd, "mirror.md")
                Path(mirror_path).write_text(new_mirror + "\n")
                updated.append("mirror")

        if updated:
            print(f"Practice state extracted for {mage_name}: {', '.join(updated)}")

    except Exception as e:
        print(f"Practice state extraction failed for {mage_name}: {type(e).__name__}: {e}")


async def light_archive_eddy(channel_id: int, *, discord_client=None) -> None:
    """Registry + in-memory cleanup only — no essence/chronicle (native close policy C)."""
    from thread_registry import mark_dissolved
    from state import threads_flagged_for_release
    from helpers import clear_history

    thread_configs.pop(channel_id, None)
    threads_flagged_for_release.pop(channel_id, None)
    mark_dissolved(channel_id)
    clear_history(channel_id)
    active_sessions.pop(channel_id, None)
    print(f"Light archived eddy: {channel_id}")


async def dissolve_eddy(
    channel_id: int,
    history: list[dict] | None = None,
    *,
    discord_client=None,
    native_close: bool = False,
) -> DissolveResult | None:
    """Archive an eddy — essence capture, file archive, chronicle, parent act."""
    import discord
    from thread_registry import mark_dissolved
    from state import threads_flagged_for_release

    dc = discord_client or client
    thread = dc.get_channel(channel_id)
    if not thread or not isinstance(thread, discord.Thread):
        try:
            thread = await dc.fetch_channel(channel_id)
        except (discord.NotFound, discord.HTTPException):
            return None
    if not isinstance(thread, discord.Thread):
        return None

    if thread.archived and not native_close:
        return DissolveResult(
            thread_name=thread.name,
            jump_url=thread.jump_url,
            already_archived=True,
        )

    thread_name = thread.name
    jump_url = thread.jump_url
    history = history or []

    msgs = [
        f"{'Mage' if m['role'] == 'user' else 'Turtle'}: {m['content'][:300]}"
        for m in history
    ]
    essence = ""
    entry_count = 0
    if len(msgs) >= 2:
        conversation = "\n".join(msgs)
        try:
            result = await chat_ollama(
                f"This thread \"{thread_name}\" is dissolving. "
                "Extract the essential insights worth keeping. Write as boom entries (- prefix). "
                "If nothing worth keeping: output (nothing to capture)",
                [{"role": "user", "content": conversation}],
                model=REFLECTION_MODEL, num_ctx=8192,
            )
            if result and "(nothing to capture)" not in result.lower():
                essence = result
                boom_path = os.path.join(get_pd(), "boom.md")
                timestamp = local_now().strftime("%Y-%m-%d %H:%M")
                with open(boom_path, "a") as f:
                    f.write(f"\n\n## Thread dissolved: {thread_name} ({timestamp})\n{essence}\n")
                entry_count = sum(1 for line in essence.split("\n") if line.strip().startswith("-"))
        except Exception as e:
            print(f"Dissolve essence capture failed for {thread_name}: {e}")

    archive_dir = Path(get_pd()) / "thread-archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    today = local_now().strftime("%Y-%m-%d")
    safe_name = re.sub(r'[^\w-]', '_', thread_name.lower())
    archive_path = archive_dir / f"{today}_{safe_name}.md"
    archive_content = f"# Thread Archive: {thread_name}\n\n"
    archive_content += f"**Archived:** {today}\n**Messages:** {len(msgs)}\n\n"
    if essence:
        archive_content += f"## Essence\n{essence}\n\n"
    if msgs:
        archive_content += "## Conversation\n" + "\n".join(msgs[-20:]) + "\n"
    archive_path.write_text(archive_content)

    try:
        from river_handler import _append_chronicle

        _append_chronicle(
            get_pd(),
            f"🍃 dissolved: {thread_name} ({jump_url})",
            {
                "thread_id": str(channel_id),
                "jump_url": jump_url,
                "archive": str(archive_path),
                "boom_entries": entry_count,
            },
        )
    except Exception as exc:
        print(f"Dissolve chronicle failed: {type(exc).__name__}: {exc}")

    thread_configs.pop(channel_id, None)
    threads_flagged_for_release.pop(channel_id, None)
    mark_dissolved(channel_id)

    parent = thread.parent
    if parent:
        summary = f"🍃 **{thread_name}** dissolved"
        if entry_count:
            summary += f" — {entry_count} entries captured to boom"
        await parent.send(summary, silent=True)

    if not thread.archived:
        try:
            await thread.edit(archived=True)
        except Exception:
            pass

    print(f"Dissolved eddy: {thread_name} ({entry_count} boom entries)")
    return DissolveResult(
        thread_name=thread_name,
        entry_count=entry_count,
        archive_path=str(archive_path),
        jump_url=jump_url,
    )


async def _manual_release_dissolve(channel_id: int, history: list[dict]):
    """Dissolve a manual-release thread after checkpoint on release."""
    await dissolve_eddy(channel_id, history)
