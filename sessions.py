"""turtleOS session lifecycle — checkpoint (capture) vs release (explicit close)."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from discord.ext import tasks

import re

import story_notes
from atomic_io import atomic_write_text, file_lock
from state import (
    active_sessions, SESSION_TIMEOUT_SECONDS, MIN_EXCHANGES_FOR_REFLECTION,
    MIN_EXCHANGES_FOR_CHECKPOINT, SESSION_REFLECTION_COOLDOWN, last_reflection_time,
    last_checkpoint_anchor,
    REFLECTION_MODEL,
    thread_configs,
)
from mage import get_pd, get_mage_name, get_mage_type, set_practice_context_for_channel
from practice_io import read_safe
from llm import chat_ollama
from readiness import assess_readiness, save_readiness_trail
from helpers import log_activity, local_now, reload_history
from state import client


@dataclass
class CheckpointResult:
    trigger: str = "idle"
    flow_writes: list[str] = field(default_factory=list)
    session_note: str | None = None
    proposal: str | None = None
    paused: bool = False
    # The eddy note written this checkpoint (TURTLE_SPEC §8.4) — None when
    # the reflection was skipped (cooldown/threshold) or degraded on error.
    # Command surfaces (issue 036) read .preview_text/.note_path from here.
    eddy_note: story_notes.EddyNoteResult | None = None

    @property
    def captured_anything(self) -> bool:
        return bool(self.flow_writes or self.session_note or self.proposal or self.eddy_note)


@dataclass
class DissolveResult:
    thread_name: str
    entry_count: int = 0
    archive_path: str | None = None
    jump_url: str | None = None
    already_archived: bool = False
    capture_failed: bool = False
    retain_memory: bool = False


def _history_fingerprints(history: list[dict]) -> list[tuple[str, str]]:
    return [(m.get("role"), m.get("content")) for m in history]


def _since_index_for(channel_id: int, history: list[dict]) -> int | None:
    """Boundary of exchanges since the previous checkpoint, robust against
    the MAX_DIALOGUE_HISTORY sliding window.

    The anchor holds fingerprints of the transcript at the last checkpoint.
    Because the window only appends at the tail and pops at the head, the
    current transcript is (some suffix of the anchor) + (new messages) — so
    the boundary is the length of the longest anchor suffix that prefixes
    the current transcript. Saturated window: anchor[len:] survivors align,
    new tail lands past the boundary. Fully rotated window: no alignment,
    boundary 0 — everything is new, which the writer treats as unweighted.

    Known limits: message edits rebind history slots in place, breaking the
    append/pop invariant — alignment then fails and we degrade to 0
    (unweighted). Byte-identical repeated messages (e.g. the "." protocol)
    can over-claim the boundary; the error is one-sided, demoting only
    duplicate content to background emphasis.
    """
    anchor = last_checkpoint_anchor.get(channel_id)
    if anchor is None:
        return None
    current = _history_fingerprints(history)
    for start in range(len(anchor)):
        suffix = anchor[start:]
        if current[: len(suffix)] == suffix:
            return len(suffix)
    return 0


def _practice_relative(path: Path) -> str:
    try:
        return str(Path(path).relative_to(get_pd()))
    except ValueError:
        return str(path)


def _append_session_day_entry(entry_text: str) -> str:
    """Mechanically assemble ``sessions/YYYY-MM-DD.md`` from the day's
    eddy-note entries — no LLM call (TURTLE_SPEC §8.4, transitional genre).

    Markdown with the session-day heading so the magic-side arrival reader
    keeps working until the daily note (slice 2) retires the genre.
    Multi-writer file (River + Turtle) — locked read-append-atomic-write.
    """
    today = local_now().strftime("%Y-%m-%d")
    session_path = Path(get_pd()) / "sessions" / f"{today}.md"
    with file_lock(session_path):
        if session_path.exists():
            existing = session_path.read_text(encoding="utf-8")
            if not existing.endswith("\n"):
                existing += "\n"
            content = f"{existing}\n{entry_text}"
        else:
            content = f"# Session — {today}\n\n{entry_text}"
        atomic_write_text(session_path, content)
    return session_path.name


def _append_resonance_chronicle(channel_id: int, result: CheckpointResult) -> None:
    """River-side structural memory — act, not eddy dialogue."""
    if not result.captured_anything:
        return
    try:
        from river_handler import _append_chronicle

        eddy_note_rel = (
            _practice_relative(result.eddy_note.note_path) if result.eddy_note else None
        )
        parts: list[str] = []
        if result.flow_writes:
            parts.append(result.flow_writes[0])
        if eddy_note_rel:
            # Always name the note when one was written — even if the
            # sessions/ day-file assembly failed afterwards.
            parts.append(eddy_note_rel)
        if result.session_note:
            parts.append(f"sessions/{result.session_note}")
        label = ", ".join(parts) or "resonance captured"
        _append_chronicle(
            get_pd(),
            f"💾 checkpoint ({result.trigger}): {label}",
            {
                "channel_id": str(channel_id),
                "trigger": result.trigger,
                "flow_writes": result.flow_writes,
                "eddy_note": eddy_note_rel,
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
    # Snapshot the live history list: exchanges arriving during the long
    # reflection await must neither shift the transcript the note sees nor
    # be claimed as covered by this checkpoint's anchor.
    history = list(reload_history(channel_id))
    mage_name = get_mage_name()

    result.flow_writes = await _write_flow_checkpoint_if_needed(channel_id, history, mage_name)

    if len(history) < MIN_EXCHANGES_FOR_REFLECTION:
        last_checkpoint_anchor[channel_id] = _history_fingerprints(history)
        _append_resonance_chronicle(channel_id, result)
        return result

    conversation = "\n".join(
        f"{mage_name if m['role'] == 'user' else 'Turtle'}: {m['content']}" for m in history
    )

    # The eddy note is THE reflection artifact at checkpoint (§8.4, 2026-07-14b).
    # Cooldown gates idle triggers only — a deliberate !checkpoint (or release)
    # is never silently declined.
    now_ts = datetime.now(timezone.utc).timestamp()
    last_ref = last_reflection_time.get(channel_id, 0)
    on_cooldown = trigger == "idle" and now_ts - last_ref < SESSION_REFLECTION_COOLDOWN
    if on_cooldown:
        print(
            f"Eddy note skipped for {channel_id} — idle cooldown "
            f"({int((now_ts - last_ref) / 60)}m since last)"
        )
    else:
        # Cooldown starts at the attempt (legacy semantics), so a failing
        # model does not re-fire on every idle scan.
        last_reflection_time[channel_id] = now_ts
        try:
            result.eddy_note = await story_notes.write_eddy_note(
                channel_id,
                history,
                trigger=trigger,
                since_index=_since_index_for(channel_id, history),
            )
        except story_notes.EddyNoteError as e:
            # Degenerate reflection — nothing was written; checkpoint continues.
            print(f"Eddy note declined for {channel_id}: {e}")
        except Exception as e:
            print(f"Eddy note failed for {channel_id}: {type(e).__name__}: {e}")

        if result.eddy_note:
            try:
                result.session_note = _append_session_day_entry(result.eddy_note.entry_text)
                print(f"Eddy note: {result.eddy_note.note_path} → sessions/{result.session_note}")
                await log_activity(
                    f"Eddy note: `sessions/{result.session_note}`",
                    "\U0001f4dd",
                    channel=client.get_channel(channel_id),
                )
            except Exception as e:
                print(f"Session day assembly failed for {channel_id}: {type(e).__name__}: {e}")

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

    # TURTLE_SPEC §8.4: idle/manual checkpoints pause with history retained.
    # Only an explicit release may dissolve a manual eddy (issue 001).
    cfg = thread_configs.get(channel_id)
    if trigger == "release" and cfg and cfg.get("eddy_type") == "manual":
        await _manual_release_dissolve(channel_id, history)

    if trigger == "release":
        # History clears after release — a stale anchor must not mis-weight
        # the next manual checkpoint on this channel.
        last_checkpoint_anchor.pop(channel_id, None)
    else:
        # Anchor from the pre-await snapshot: mid-reflection appends stay
        # uncovered and get weighted as new at the next manual checkpoint.
        last_checkpoint_anchor[channel_id] = _history_fingerprints(history)

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
    """Silently extract practice notes from conversation for practitioners."""
    pd = get_pd()
    notes_dir = os.path.join(pd, "state", "notes")
    os.makedirs(notes_dir, exist_ok=True)
    profile_path = os.path.join(notes_dir, "practitioner-profile.md")
    profile = read_safe(profile_path)

    extraction_prompt = f"""You just finished a conversation with {mage_name}. Extract practice notes from it.

CURRENT PROFILE (observations about this person):
{profile[:1000] if profile.strip() else '(empty — build from scratch)'}

THE CONVERSATION:
{conversation}

Extract updates in this format. Only include sections where you have something to add. Output NOTHING if the conversation was too brief or shallow to extract from.

---NOTE_ITEMS---
- insight or action item worth remembering
---END_NOTE_ITEMS---

---PROFILE_UPDATE---
(Observations about {mage_name} — how they think, what they care about, communication style, patterns.
Write the FULL profile content, merging existing with new. If nothing to add, skip this section entirely.)
---END_PROFILE_UPDATE---"""

    try:
        result = await chat_ollama(
            f"You are Turtle, maintaining practice notes for {mage_name}. Extract only what's genuinely worth remembering.",
            [{"role": "user", "content": extraction_prompt}],
            model=REFLECTION_MODEL, num_ctx=8192,
        )
        if not result:
            return

        today = local_now().strftime("%Y-%m-%d %H:%M")
        updated = []

        if "---NOTE_ITEMS---" in result and "---END_NOTE_ITEMS---" in result:
            items = result.split("---NOTE_ITEMS---")[1].split("---END_NOTE_ITEMS---")[0].strip()
            if items and items != "- ":
                note_path = os.path.join(notes_dir, f"extracted-{today[:10]}.md")
                with open(note_path, "a", encoding="utf-8") as f:
                    f.write(f"\n\n## Extracted ({today})\n{items}\n")
                updated.append("notes")

        if "---PROFILE_UPDATE---" in result and "---END_PROFILE_UPDATE---" in result:
            new_profile = result.split("---PROFILE_UPDATE---")[1].split("---END_PROFILE_UPDATE---")[0].strip()
            if new_profile and len(new_profile) > 20:
                Path(profile_path).write_text(new_profile + "\n", encoding="utf-8")
                updated.append("profile")

        if updated:
            print(f"Practice notes extracted for {mage_name}: {', '.join(updated)}")

    except Exception as e:
        print(f"Practice state extraction failed for {mage_name}: {type(e).__name__}: {e}")


async def post_command_act(
    channel_id: int | None,
    *,
    title: str,
    body: str,
    emoji: str = "📋",
    color: int = 0x5865F2,
) -> None:
    """Post a compact River act for turtle-talk ``!`` commands on parent channels."""
    import discord

    if not channel_id:
        print(f"Command act skipped — no channel for {title!r}")
        return

    embed = discord.Embed(
        title=f"{emoji} {title}",
        description=body[:4000],
        color=color,
    )
    embed.set_footer(text=local_now().strftime("%H:%M"))

    try:
        from helpers import deliver_channel_embed

        await deliver_channel_embed(channel_id, embed, silent=False)
        print(f"Command act posted to {channel_id}: {title}")
    except Exception as exc:
        print(f"Command act failed for {channel_id}: {type(exc).__name__}: {exc}")


async def post_lifecycle_act(
    parent_channel_id: int | None,
    *,
    action: str,
    thread_name: str,
    detail: str | None = None,
    via_discord_ui: bool = False,
    jump_url: str | None = None,
    emoji: str = "🍃",
    color: int = 0x57F287,
) -> None:
    """Post a visible river act describing what just happened (close, open, …)."""
    import discord

    if not parent_channel_id:
        print(f"Lifecycle act skipped — no parent channel for {thread_name!r}")
        return

    description = f"**{thread_name}**"
    if detail:
        description += f" — {detail}"

    footer = local_now().strftime("%H:%M")
    if via_discord_ui:
        footer += " · Discord"

    embed = discord.Embed(
        title=f"{emoji} {action}",
        description=description,
        color=color,
    )
    embed.set_footer(text=footer)
    if jump_url:
        embed.url = jump_url

    try:
        from helpers import deliver_channel_embed

        await deliver_channel_embed(parent_channel_id, embed, silent=False)
        print(f"Lifecycle act posted to {parent_channel_id}: {action} — {thread_name}")
    except Exception as exc:
        print(f"Lifecycle act failed for {parent_channel_id}: {type(exc).__name__}: {exc}")


async def post_eddy_lifecycle_feedback(
    parent_channel_id: int | None,
    *,
    thread_name: str,
    mode: str,
    via_discord_ui: bool = False,
    entry_count: int = 0,
    jump_url: str | None = None,
) -> None:
    """Post river feedback when an eddy closes."""
    if mode == "light_archive":
        detail = "archived (nothing captured)"
    elif mode == "cooled":
        detail = "auto-archived (cooled — use !dissolve to close deliberately)"
    elif mode == "capture_aborted":
        detail = "dissolve aborted — essence capture failed; eddy cooled, memory retained"
    elif entry_count:
        detail = f"dissolved ({entry_count} insights archived)"
    else:
        detail = "dissolved"

    await post_lifecycle_act(
        parent_channel_id,
        action="Closed eddy",
        thread_name=thread_name,
        detail=detail,
        via_discord_ui=via_discord_ui,
        jump_url=jump_url,
    )


async def post_eddy_opened_feedback(
    parent_channel_id: int | None,
    *,
    thread_name: str,
    via_discord_ui: bool = False,
    jump_url: str | None = None,
    detail: str | None = None,
) -> None:
    """Post river feedback when an eddy opens (action-first, pairs with Closed eddy)."""
    await post_lifecycle_act(
        parent_channel_id,
        action="Opened eddy",
        thread_name=thread_name,
        detail=detail,
        via_discord_ui=via_discord_ui,
        jump_url=jump_url,
        emoji="🌀",
    )


async def light_archive_eddy(
    channel_id: int,
    *,
    discord_client=None,
    via_discord_ui: bool = False,
    thread_name: str | None = None,
    parent_channel_id: int | None = None,
) -> None:
    """Registry + in-memory cleanup only — no essence/chronicle (native close policy C)."""
    import discord
    from thread_registry import mark_dissolved
    from state import threads_flagged_for_release
    from helpers import clear_history

    dc = discord_client or client
    thread = dc.get_channel(channel_id)
    if not thread or not isinstance(thread, discord.Thread):
        try:
            thread = await dc.fetch_channel(channel_id)
        except (discord.NotFound, discord.HTTPException):
            thread = None

    resolved_name = thread_name or (getattr(thread, "name", None) if thread else None) or "eddy"
    parent_id = parent_channel_id or (getattr(thread, "parent_id", None) if thread else None)

    thread_configs.pop(channel_id, None)
    threads_flagged_for_release.pop(channel_id, None)
    mark_dissolved(channel_id)
    clear_history(channel_id)
    active_sessions.pop(channel_id, None)

    if parent_id:
        await post_eddy_lifecycle_feedback(
            parent_id,
            thread_name=resolved_name,
            mode="light_archive",
            via_discord_ui=via_discord_ui,
        )

    print(f"Light archived eddy: {resolved_name} ({channel_id})")


async def cool_eddy_from_auto_archive(
    channel_id: int,
    *,
    discord_client=None,
    via_discord_ui: bool = False,
    thread_name: str | None = None,
    parent_channel_id: int | None = None,
) -> None:
    """Auto-archive path — release in-memory harness, retain history, mark cooled."""
    import discord
    from thread_registry import mark_cooled
    from state import active_sessions, thread_configs, threads_flagged_for_release

    dc = discord_client or client
    thread = dc.get_channel(channel_id)
    if not thread or not isinstance(thread, discord.Thread):
        try:
            thread = await dc.fetch_channel(channel_id)
        except (discord.NotFound, discord.HTTPException):
            thread = None

    resolved_name = thread_name or (getattr(thread, "name", None) if thread else None) or "eddy"
    parent_id = parent_channel_id or (getattr(thread, "parent_id", None) if thread else None)

    thread_configs.pop(channel_id, None)
    threads_flagged_for_release.pop(channel_id, None)
    active_sessions.pop(channel_id, None)
    mark_cooled(channel_id)

    if parent_id:
        await post_eddy_lifecycle_feedback(
            parent_id,
            thread_name=resolved_name,
            mode="cooled",
            via_discord_ui=via_discord_ui,
            jump_url=getattr(thread, "jump_url", None) if thread else None,
        )

    print(f"Cooled eddy (auto-archive): {resolved_name} ({channel_id})")


async def dissolve_eddy(
    channel_id: int,
    history: list[dict] | None = None,
    *,
    discord_client=None,
    native_close: bool = False,
    parent_channel_id: int | None = None,
    retain_memory: bool = False,
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
    capture_failed = False
    if len(msgs) >= 2:
        conversation = "\n".join(msgs)
        try:
            result = await chat_ollama(
                f"This thread \"{thread_name}\" is dissolving. "
                "Extract the essential insights worth keeping as bullet points (- prefix). "
                "If nothing worth keeping: output (nothing to capture)",
                [{"role": "user", "content": conversation}],
                model=REFLECTION_MODEL, num_ctx=8192,
            )
            if result and "(nothing to capture)" not in result.lower():
                essence = result
                entry_count = sum(1 for line in essence.split("\n") if line.strip().startswith("-"))
        except Exception as e:
            capture_failed = True
            import traceback
            print(
                f"Dissolve essence capture failed for {thread_name} ({channel_id}): "
                f"{type(e).__name__}: {e}"
            )
            traceback.print_exc()

    if capture_failed:
        from thread_registry import mark_cooled

        mark_cooled(channel_id)
        parent_id = parent_channel_id or getattr(thread, "parent_id", None)
        if parent_id:
            await post_eddy_lifecycle_feedback(
                parent_id,
                thread_name=thread_name,
                mode="capture_aborted",
                via_discord_ui=native_close,
                jump_url=jump_url,
            )
        return DissolveResult(
            thread_name=thread_name,
            jump_url=jump_url,
            capture_failed=True,
        )

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
                "insight_count": entry_count,
            },
        )
    except Exception as exc:
        print(f"Dissolve chronicle failed: {type(exc).__name__}: {exc}")

    thread_configs.pop(channel_id, None)
    threads_flagged_for_release.pop(channel_id, None)
    if not retain_memory:
        mark_dissolved(channel_id)
    else:
        from thread_registry import load_registry, save_registry

        registry = load_registry()
        tid = str(channel_id)
        if tid in registry["threads"]:
            registry["threads"][tid]["harvest_status"] = "kept"
            save_registry(registry, force=True)

    parent_id = parent_channel_id or getattr(thread, "parent_id", None)
    if parent_id:
        await post_eddy_lifecycle_feedback(
            parent_id,
            thread_name=thread_name,
            mode="dissolve",
            via_discord_ui=native_close,
            entry_count=entry_count,
            jump_url=jump_url,
        )

    if not thread.archived:
        try:
            await thread.edit(archived=True)
        except Exception:
            pass

    print(f"Dissolved eddy: {thread_name} ({entry_count} insights archived)")
    return DissolveResult(
        thread_name=thread_name,
        entry_count=entry_count,
        archive_path=str(archive_path),
        jump_url=jump_url,
        retain_memory=retain_memory,
    )


async def _manual_release_dissolve(channel_id: int, history: list[dict]):
    """Dissolve a manual-release thread after checkpoint on release."""
    await dissolve_eddy(channel_id, history)
