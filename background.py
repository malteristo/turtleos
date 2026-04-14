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
import urllib.request
import json as _json
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
        unread = [f for f in os.listdir(pdir)
                  if f.endswith(".md") and os.path.isfile(os.path.join(pdir, f))]
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


import re as _re


@tasks.loop(hours=1)
async def daily_reminders_loop():
    """Practice reminders — proactive daily nudges."""
    now = datetime.now()
    if now.hour < _state.REMINDER_HOUR_START or now.hour > _state.REMINDER_HOUR_END:
        return
    today = now.strftime("%Y-%m-%d")
    if _state.last_reminder_date == today:
        return
    _state.last_reminder_date = today

    await _check_signal_drip()
    await _check_practice_invitation()


async def _check_signal_drip():
    """Check for pending signal drip and offer next tweet."""
    drip_path = os.path.join(get_pd(), "outfacing", "drip-state.md")
    content = read_safe(drip_path)
    if not content:
        return

    pending = _re.findall(r"\|\s*(\d+)\s*\|\s*pending\s*\|", content)
    if not pending:
        return
    next_num = int(pending[0])

    total_matches = _re.findall(r"\|\s*(\d+)\s*\|\s*(?:posted|pending)\s*\|", content)
    total = max(int(n) for n in total_matches) if total_matches else 18

    thread = _state.client.get_channel(_state.SIGNAL_DRIP_THREAD_ID)
    if not thread:
        print(f"Signal drip: thread {_state.SIGNAL_DRIP_THREAD_ID} not found")
        return

    tweet_text = None
    try:
        async for msg in thread.history(limit=100):
            if f"Tweet {next_num}/{total}" in msg.content and "Turtle Story" in msg.content:
                parts = msg.content.split("\n\n", 1)
                tweet_text = parts[1].strip() if len(parts) > 1 else None
                break
    except Exception as e:
        print(f"Signal drip: thread history search failed: {e}")
        return

    if not tweet_text:
        print(f"Signal drip: Tweet {next_num} text not found in thread")
        return

    embed = discord.Embed(
        title=f"\U0001f422 Tweet {next_num}/{total}",
        description=f"{tweet_text}\n\n*Relay to @turtle_of_magic. `!drip done` when posted.*",
        color=OPS_EMBED_COLOR,
    )
    await thread.send(embed=embed, silent=True)
    print(f"Signal drip: Tweet {next_num}/{total} reminder sent")


async def _check_practice_invitation():
    """Evaluate practice state and send the highest-priority invitation."""
    from datetime import datetime, timedelta

    today = datetime.now().strftime("%Y-%m-%d")

    # Check global cooldown — only one invitation per day
    if _state.last_invitation_date == today:
        return

    pd = get_pd()

    # Read practice state
    boom = read_safe(os.path.join(pd, "boom.md"))
    compass = read_safe(os.path.join(pd, "intentions", "compass.md"))
    bright = read_safe(os.path.join(pd, "boom", "bright.md"))

    boom_count = count_items(boom)
    boom_age = file_age_hours(os.path.join(pd, "boom.md"))
    compass_age = file_age_hours(os.path.join(pd, "intentions", "compass.md"))

    # Find latest session
    sdir = os.path.join(pd, "sessions")
    session_age = float("inf")
    last_session_thread = None
    if os.path.isdir(sdir):
        session_files = [f for f in os.listdir(sdir) if f.endswith(".md")]
        if session_files:
            latest = max(session_files, key=lambda f: os.path.getmtime(os.path.join(sdir, f)))
            session_age = file_age_hours(os.path.join(sdir, latest))
            session_content = read_safe(os.path.join(sdir, latest))
            for line in session_content.split("\n"):
                if "thread" in line.lower() and ("next" in line.lower() or "follow" in line.lower()):
                    last_session_thread = line.strip().lstrip("- *#").strip()
                    break

    # Find stale intentions
    stale_intentions = []
    idir = os.path.join(pd, "intentions", "active")
    if os.path.isdir(idir):
        for fname in os.listdir(idir):
            if fname.endswith(".md"):
                iage = file_age_hours(os.path.join(idir, fname))
                if iage > 336:  # 14 days
                    name = fname.replace(".md", "").replace("-", " ").replace("_", " ")
                    stale_intentions.append((name, iage))

    # Evaluate invitations in priority order
    candidates = []

    # 1. Return invitation (highest priority — practitioner hasn't been around)
    if session_age > 72:
        candidates.append(("return", "Haven't heard from you in a few days. No agenda — just here if you want to think out loud."))

    # 2. Session thread follow-up
    if last_session_thread and session_age > 24 and session_age < 168:
        candidates.append(("thread", f"Last time we talked, there was a thread: *{last_session_thread[:120]}* — still pulling?"))

    # 3. Boom sweep invitation
    if boom_count >= 5 and boom_age > 72:
        candidates.append(("boom", f"Your boom has been accumulating — {boom_count} items, some from {format_age(boom_age)} ago. I can see threads forming. Want to sweep together?"))

    # 4. Compass reflection
    if compass_age > 336 and compass.strip():  # 14 days
        weeks = int(compass_age / 168)
        candidates.append(("compass", f"It\'s been {weeks} weeks since we looked at your compass. Your intentions have been active — want to check if the compass still points true?"))

    # 5. Intention check-in
    if stale_intentions and session_age < 72:
        name, iage = stale_intentions[0]
        candidates.append(("intention", f"*{name}* has been quiet for {format_age(iage)} while you\'ve been active elsewhere. Still alive? Sometimes intentions complete silently."))

    if not candidates:
        return

    # Apply per-type cooldown (7 days)
    now = datetime.now()
    filtered = []
    for inv_type, message in candidates:
        last_sent = _state.invitation_cooldowns.get(inv_type)
        if last_sent:
            try:
                last_dt = datetime.strptime(last_sent, "%Y-%m-%d")
                if (now - last_dt).days < _state.INVITATION_COOLDOWN_DAYS:
                    continue
            except ValueError:
                pass
        filtered.append((inv_type, message))

    if not filtered:
        return

    # Send highest-priority invitation
    inv_type, message = filtered[0]

    ch = get_channel("dialogue")
    if not ch:
        return

    embed = discord.Embed(
        title="\U0001f331 Practice Invitation",
        description=message,
        color=OPS_EMBED_COLOR,
    )
    try:
        await ch.send(embed=embed, silent=True)
        _state.last_invitation_date = today
        _state.last_invitation_type = inv_type
        _state.invitation_cooldowns[inv_type] = today
        print(f"Practice invitation sent: {inv_type}")
    except Exception as e:
        print(f"Practice invitation failed: {e}")


@tasks.loop(minutes=30)
async def health_canary_loop():
    """INT-027: Detect 'alive but not home' degradation."""
    checks = {}

    # 1. Ollama reachable?
    try:
        req = urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5)
        if req.status == 200:
            checks["ollama"] = True
        else:
            checks["ollama"] = False
    except Exception:
        checks["ollama"] = False

    # 2. Background loops alive?
    from sessions import session_monitor
    loop_status = {
        "session_monitor": session_monitor.is_running(),
        "interoception": interoception_loop.is_running(),
        "health_loop": practice_health_loop.is_running(),
        "daily_reminders": daily_reminders_loop.is_running(),
    }
    dead_loops = [name for name, alive in loop_status.items() if not alive]
    checks["loops"] = len(dead_loops) == 0

    # 3. LiveSync: workshop files reachable and not ancient?
    pd = get_pd()
    boom_age = file_age_hours(os.path.join(pd, "boom.md"))
    compass_age = file_age_hours(os.path.join(pd, "intentions", "compass.md"))
    checks["livesync"] = boom_age < 168 and compass_age < 168  # 7 days

    # 4. Tool primitives functional?
    test_path = os.path.join(pd, ".canary_test")
    try:
        with open(test_path, "w") as f:
            f.write("canary")
        with open(test_path) as f:
            result = f.read()
        os.remove(test_path)
        checks["file_io"] = result == "canary"
    except Exception:
        checks["file_io"] = False

    # 5. Discord connection healthy?
    checks["discord"] = _state.client.is_ready() and not _state.client.is_closed()

    # Evaluate results
    now = datetime.now()
    alerts = []

    for check_name, passed in checks.items():
        if passed:
            _state.canary_consecutive_failures[check_name] = 0
        else:
            prev = _state.canary_consecutive_failures.get(check_name, 0)
            _state.canary_consecutive_failures[check_name] = prev + 1

            if prev + 1 >= _state.CANARY_ALERT_THRESHOLD:
                last_alert = _state.canary_last_alert.get(check_name)
                should_alert = True
                if last_alert:
                    try:
                        last_dt = datetime.strptime(last_alert, "%Y-%m-%d %H:%M")
                        if (now - last_dt).total_seconds() < _state.CANARY_ALERT_COOLDOWN_HOURS * 3600:
                            should_alert = False
                    except ValueError:
                        pass

                if should_alert:
                    detail = _canary_detail(check_name, dead_loops, boom_age, compass_age)
                    alerts.append((check_name, detail))
                    _state.canary_last_alert[check_name] = now.strftime("%Y-%m-%d %H:%M")

    if not alerts:
        return

    ch = get_channel("dialogue")
    if not ch:
        return

    lines = []
    for check_name, detail in alerts:
        lines.append(f"\u26a0\ufe0f **{check_name}**: {detail}")

    embed = discord.Embed(
        title="\U0001f6a8 Health Canary — INT-027",
        description="\n".join(lines),
        color=0xE74C3C,
    )
    try:
        await ch.send(embed=embed, silent=True)
        print(f"Health canary alert: {', '.join(c for c, _ in alerts)}")
    except Exception as e:
        print(f"Health canary alert failed: {e}")


def _canary_detail(check_name, dead_loops, boom_age, compass_age):
    """Generate human-readable detail for a canary failure."""
    if check_name == "ollama":
        return "Ollama not responding — local model inference is down"
    elif check_name == "loops":
        return f"Background loops stopped: {', '.join(dead_loops)}"
    elif check_name == "livesync":
        return f"Workshop files stale (boom: {format_age(boom_age)}, compass: {format_age(compass_age)}) — LiveSync may be down"
    elif check_name == "file_io":
        return "File read/write test failed — filesystem may be read-only or full"
    elif check_name == "discord":
        return "Discord connection unhealthy — bot may need restart"
    return f"{check_name} check failed"
