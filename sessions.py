"""turtleOS session lifecycle — timeout monitoring, reflection, session notes."""

import os
from datetime import datetime, timezone
from pathlib import Path

from discord.ext import tasks

from state import (
    active_sessions, SESSION_TIMEOUT_SECONDS, MIN_EXCHANGES_FOR_REFLECTION,
    SESSION_REFLECTION_COOLDOWN, last_reflection_time,
    IDENTITY_DIR, REFLECTION_MODEL,
)
from mage import get_pd, get_mage_name, get_mage_type, set_practice_context_for_channel
from practice_io import read_safe
from llm import chat_ollama
from prompts import get_system_prompt
from readiness import assess_readiness, save_readiness_trail
from helpers import get_history, log_activity, split_message, local_now
from outfacing import evaluate_outfacing_signal, save_signal_drafts, MIN_EXCHANGES_FOR_SIGNAL
from state import client


@tasks.loop(seconds=60)
async def session_monitor():
    now = datetime.now(timezone.utc)
    for channel_id, state in list(active_sessions.items()):
        if state["closed"]:
            continue
        elapsed = (now - state["last_message"]).total_seconds()
        if elapsed >= SESSION_TIMEOUT_SECONDS:
            await close_session(channel_id)


async def close_session(channel_id: int):
    active_sessions[channel_id]["closed"] = True
    set_practice_context_for_channel(channel_id)
    history = get_history(channel_id)
    if len(history) < MIN_EXCHANGES_FOR_REFLECTION:
        return

    now_ts = datetime.now(timezone.utc).timestamp()
    last_ref = last_reflection_time.get(channel_id, 0)
    if now_ts - last_ref < SESSION_REFLECTION_COOLDOWN:
        print(f"Session reflection skipped for {channel_id} — cooldown ({int((now_ts - last_ref) / 60)}m since last)")
        return
    last_reflection_time[channel_id] = now_ts

    mage_name = get_mage_name()
    conversation = "\n".join(
        f"{mage_name if m['role'] == 'user' else 'Turtle'}: {m['content']}" for m in history
    )
    # Cross-channel awareness: when reflecting on a thread, include
    # recent parent-channel messages so the reflection model knows
    # what Spirit/others said in the main channel.
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
                f"\n\nRECENT MAIN CHANNEL CONTEXT (for awareness — do NOT repeat or re-propose what was already addressed here):\n{cross_channel_context}\n"
            )

    reflection_prompt = (
        f"The following conversation with {mage_name} just ended (15 minutes of silence). "
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
        reflection = await chat_ollama(get_system_prompt(),
                                         [{"role": "user", "content": reflection_prompt}],
                                         model=REFLECTION_MODEL)
        if not reflection:
            return

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
            print(f"Session note: {session_path}")

            session_channel = client.get_channel(channel_id)
            await log_activity(f"Session note: `sessions/{session_path.name}`", "\U0001f4dd", channel=session_channel)

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

    # ── Outfacing signal evaluation (Mage channel only) ──
    if get_mage_type() != "practitioner" and len(history) >= MIN_EXCHANGES_FOR_SIGNAL:
        try:
            signals = await evaluate_outfacing_signal(conversation, reflection)
            if signals:
                paths = save_signal_drafts(signals)
                if paths:
                    session_channel = client.get_channel(channel_id)
                    count = len(paths)
                    label = f"{count} signal draft{'s' if count > 1 else ''}"
                    drafts_rel = "outfacing/drafts/signals"
                    await log_activity(
                        f"Outfacing: {label} in `{drafts_rel}/`",
                        "📡", channel=session_channel,
                    )
        except Exception as e:
            print(f"Outfacing signal evaluation failed: {type(e).__name__}: {e}")

    # ── Silent practice state extraction (especially valuable for practitioners) ──
    if get_mage_type() == "practitioner" and len(history) >= 4:
        await _extract_practice_state(conversation, mage_name)

    try:
        result = assess_readiness()
        save_readiness_trail(result)
        impaired = [d for d in result["dimensions"] if d["status"] == "impaired"]
        if impaired:
            session_channel = client.get_channel(channel_id)
            if session_channel:
                names = ", ".join(d["name"] for d in impaired)
                # Route to internal log, not channel — practitioner cannot act on this (016 principle)
                print(f"Post-session readiness: {names} impaired — internal signal, not surfaced to channel")
    except Exception as e:
        print(f"Post-session readiness check failed: {e}")



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
