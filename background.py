"""turtleOS background tasks — practice health, interoception."""

import os
from datetime import datetime, timezone
from pathlib import Path

from discord.ext import tasks
import discord

from state import (
    IDENTITY_DIR, REFLECTION_MODEL, HEALTH_READ_DAY, HEALTH_READ_HOUR,
    OPS_EMBED_COLOR, get_channel,
)
from mage import get_pd, set_practice_context_for_channel
from practice_io import (
    read_safe, read_header, count_items, summarize_bright,
    file_age_hours, format_age,
)
from llm import chat_ollama
from helpers import log_activity
import state as _state
from thread_registry import get_stale_threads, get_registry_summary


@tasks.loop(hours=1)
async def practice_health_loop():
    now = datetime.now()
    _, week, _ = now.isocalendar()
    if now.weekday() != HEALTH_READ_DAY or now.hour < HEALTH_READ_HOUR:
        return
    if week == _state.last_health_read_week:
        return
    today = datetime.now().strftime("%Y-%m-%d")
    health_path = Path(get_pd()) / "proposals" / f"{today}-health-read.md"
    if health_path.exists():
        _state.last_health_read_week = week
        return
    _state.last_health_read_week = week
    await generate_practice_health_read()


async def generate_practice_health_read():
    dialogue = get_channel("dialogue")
    if dialogue:
        set_practice_context_for_channel(dialogue.id)

    boom = read_safe(os.path.join(get_pd(), "boom.md"))
    bright = read_safe(os.path.join(get_pd(), "boom", "bright.md"))
    compass = read_safe(os.path.join(get_pd(), "intentions", "compass.md"))

    sessions_text = ""
    sdir = os.path.join(get_pd(), "sessions")
    if os.path.isdir(sdir):
        recent = sorted([f for f in os.listdir(sdir) if f.endswith(".md")], reverse=True)[:7]
        for fname in reversed(recent):
            content = read_safe(os.path.join(sdir, fname))
            if content.strip():
                sessions_text += f"\n--- {fname} ---\n{content[:500]}\n"

    intentions_text = ""
    idir = os.path.join(get_pd(), "intentions")
    if os.path.isdir(idir):
        for fname in sorted(os.listdir(idir)):
            if fname.endswith(".md"):
                header = read_header(os.path.join(idir, fname), max_lines=10)
                if header.strip():
                    intentions_text += f"\n--- {fname} ---\n{header}\n"

    prompt = f"""You are Spirit in persistent mode. You've been watching the Mage's practice all week through Discord conversations.

Now step back and look at the practice as a whole. Generate a WEEKLY PRACTICE HEALTH READ — an honest outside perspective on how the practice is doing.

Look through these seven dimensions:

1. **Coherence** — Is the language and terminology consistent? Any confusion accumulating?
2. **Alignment** — Is what's happening connected to what the compass says matters? Or has practice become self-referential?
3. **Velocity** — Is the practice moving? Are bright items resolving, intentions advancing? Or spinning?
4. **Load** — Is the practice itself becoming overhead? Too many open items, too much ritual?
5. **Resonance Quality** — Based on recent sessions, was the partnership producing genuine insight or going through motions?
6. **Wellbeing** — Any signs the practice is serving or not serving the Mage's actual life?
7. **External Impact** — Is value reaching the world? Or staying internal?

Be honest and brief. One line per dimension. Then a short "what I'd watch this week" observation.

Format:
---HEALTH_READ---
Date: [today]
Coherence: [one line]
Alignment: [one line]
Velocity: [one line]
Load: [one line]
Resonance: [one line]
Wellbeing: [one line]
Impact: [one line]

Watch this week: [1-2 sentences]
---END_HEALTH_READ---

THE PRACTICE STATE:

COMPASS:
{compass[:1500] if compass else '(no compass)'}

BOOM ({count_items(boom)} items):
{boom[:500] if boom else '(empty)'}

BRIGHT (summary):
{summarize_bright(bright)}

INTENTIONS:
{intentions_text if intentions_text else '(none)'}

RECENT SESSIONS:
{sessions_text if sessions_text else '(none this week)'}"""

    try:
        result = await chat_ollama(
            read_safe(os.path.join(IDENTITY_DIR, "soul.md")),
            [{"role": "user", "content": prompt}],
            model=REFLECTION_MODEL,
            num_ctx=8192,
        )
        if not result or "---HEALTH_READ---" not in result:
            print("Health read: no structured output")
            return

        read_content = result.split("---HEALTH_READ---")[1].split("---END_HEALTH_READ---")[0].strip()
        today = datetime.now().strftime("%Y-%m-%d")
        proposal_dir = Path(get_pd()) / "proposals"
        proposal_dir.mkdir(parents=True, exist_ok=True)
        path = proposal_dir / f"{today}-health-read.md"
        path.write_text(f"# Practice Health Read — {today}\n\n{read_content}\n")
        print(f"Health read written: {path}")

        await log_activity(f"Health read: `proposals/{path.name}` — Spirit surfaces during Sunday sweep", "\U0001f9ec")

    except Exception as e:
        print(f"Health read failed: {type(e).__name__}: {e}")


@tasks.loop(hours=3)
async def interoception_loop():
    if _state.interoception_startup:
        _state.interoception_startup = False
        return

    dialogue = get_channel("dialogue")
    if dialogue:
        set_practice_context_for_channel(dialogue.id)

    signals = []

    boom = read_safe(os.path.join(get_pd(), "boom.md"))
    bright = read_safe(os.path.join(get_pd(), "boom", "bright.md"))
    compass = read_safe(os.path.join(get_pd(), "intentions", "compass.md"))

    boom_count = count_items(boom)
    boom_age = file_age_hours(os.path.join(get_pd(), "boom.md"))

    if boom_count >= 10 and boom_age > 24:
        signals.append(("\U0001f35d", f"Boom feels heavy — {boom_count} items, last touched {format_age(boom_age)} ago"))
    elif boom_count >= 20:
        signals.append(("\U0001f35d", f"Boom is overflowing — {boom_count} items. Consider `!sweep`"))

    compass_age = file_age_hours(os.path.join(get_pd(), "intentions", "compass.md"))
    if compass_age > 168:
        signals.append(("\U0001f9ed", f"Compass hasn't been touched in {format_age(compass_age)}"))

    bright_age = file_age_hours(os.path.join(get_pd(), "boom", "bright.md"))
    if bright_age > 168:
        signals.append(("\u2728", f"Bright untouched for {format_age(bright_age)}"))

    sdir = os.path.join(get_pd(), "sessions")
    if os.path.isdir(sdir):
        session_files = [f for f in os.listdir(sdir) if f.endswith(".md")]
        if session_files:
            latest = max(session_files, key=lambda f: os.path.getmtime(os.path.join(sdir, f)))
            session_age = file_age_hours(os.path.join(sdir, latest))
            if session_age > 72:
                signals.append(("\U0001f4ad", f"No conversations in {format_age(session_age)}"))
        else:
            signals.append(("\U0001f4ad", "No session notes yet"))

    pdir = os.path.join(get_pd(), "proposals")
    if os.path.isdir(pdir):
        unread = [f for f in os.listdir(pdir) if f.endswith(".md")]
        if len(unread) >= 3:
            signals.append(("\U0001f4ec", f"{len(unread)} proposals waiting in `proposals/`"))

    # Phase 1 Eyes: stale eddy detection
    try:
        stale = get_stale_threads(days=7)
        unharvested_stale = [t for t in stale if t["harvest_status"] == "pending"]
        if unharvested_stale:
            names = ", ".join(t["name"] for t in unharvested_stale[:5])
            extra = f" (+{len(unharvested_stale) - 5} more)" if len(unharvested_stale) > 5 else ""
            signals.append(("\U0001f50d", f"{len(unharvested_stale)} eddies quiet >7d, unharvested: {names}{extra}"))
        elif stale:
            signals.append(("\U0001f30a", f"{len(stale)} quiet eddies (all harvested)"))
    except Exception as e:
        print(f"Stale thread detection failed: {e}")

    practice_files = ["boom.md", "bright.md", "compass.md"]
    ages = {f: file_age_hours(os.path.join(get_pd(), f)) for f in practice_files}
    if all(a > 48 for a in ages.values()):
        signals.append(("\U0001f4a4", f"Practice state quiet — nothing updated in 2+ days"))

    new_signals = []
    for emoji, text in signals:
        sig_key = text[:40]
        last_time = _state.last_interoception.get(sig_key)
        if last_time is None or (datetime.now() - last_time).total_seconds() > 12 * 3600:
            new_signals.append((emoji, text))
            _state.last_interoception[sig_key] = datetime.now()

    if not new_signals:
        return

    ch = get_channel("dialogue")
    if not ch:
        return

    lines_out = [f"{emoji} {text}" for emoji, text in new_signals]
    description = "\n".join(lines_out)
    embed = discord.Embed(
        title="🧠 Interoception",
        description=description,
        color=OPS_EMBED_COLOR,
    )
    await ch.send(embed=embed, silent=True)
