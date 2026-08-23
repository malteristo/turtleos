"""turtleOS background tasks — reminders, canary, daily notes."""

import os
from datetime import datetime

from discord.ext import tasks
import discord

from state import OPS_EMBED_COLOR, get_channel
from mage import get_pd
from practice_io import read_safe, file_age_hours
from practice_freshness import evaluate_freshness, canary_detail
import state as _state
import urllib.request


@tasks.loop(hours=1)
async def practice_health_loop():
    """Retired 2026-08-02 — weekly LLM health-read essays were status theater.

    Practice health is arrival / `. maintenance`, not a scheduled proposal spore.
    Loop kept as a no-op import surface; discord_bot no longer starts it.
    """
    return


@tasks.loop(hours=1)
async def daily_note_loop():
    """Scheduled daily-note synthesis after DAILY_NOTE_HOUR (issue 040)."""
    from story_daily import run_scheduled_daily_note

    await run_scheduled_daily_note()


@tasks.loop(hours=3)
async def interoception_loop():
    """Retired — pulse/interoception removed with magic-attuned Appendix A."""
    return


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

    await _check_practice_invitation()


async def _check_practice_invitation():
    """Evaluate practice state and send the highest-priority invitation."""
    from datetime import datetime, timedelta
    from mage import suppress_turtle_river_voice

    if suppress_turtle_river_voice():
        return

    today = datetime.now().strftime("%Y-%m-%d")

    # Check global cooldown — only one invitation per day
    if _state.last_invitation_date == today:
        return

    pd = get_pd()

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

    state_age = file_age_hours(os.path.join(pd, "state", "current.yaml"))

    # Evaluate invitations in priority order
    candidates = []

    # 1. Return invitation (highest priority — practitioner hasn't been around)
    if session_age > 72:
        candidates.append(("return", "Haven't heard from you in a few days. No agenda — just here if you want to think out loud."))

    # 2. Session thread follow-up
    if last_session_thread and session_age > 24 and session_age < 168:
        candidates.append(("thread", f"Last time we talked, there was a thread: *{last_session_thread[:120]}* — still pulling?"))

    # 3. Stale continuity state
    if state_age > 336 and state_age != float("inf"):
        weeks = int(state_age / 168)
        candidates.append(("state", f"It's been {weeks} weeks since state/current was updated — want to checkpoint what's alive?"))

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
    _state.canary_freshness = None
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
        "daily_note": daily_note_loop.is_running(),
        "daily_reminders": daily_reminders_loop.is_running(),
    }
    dead_loops = [name for name, alive in loop_status.items() if not alive]
    checks["loops"] = len(dead_loops) == 0

    # 3. Practice state fresh (topology-aware — native uses state/current.yaml)
    pd = get_pd()
    _freshness = evaluate_freshness(pd)
    checks["practice_freshness"] = _freshness.passed
    _state.canary_freshness = _freshness

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
                    # Attempt self-healing before alerting
                    from core.self_heal import check_and_heal
                    heal_result = await check_and_heal(check_name)
                    if heal_result and heal_result[0]:
                        print(f"Health canary: {check_name} self-healed — {heal_result[1]}")
                        _state.canary_consecutive_failures[check_name] = 0
                        continue
                    detail = _canary_detail(
                        check_name, dead_loops, getattr(_state, "canary_freshness", None)
                    )
                    if heal_result:
                        detail += f" (self-heal attempted: {heal_result[1]})"
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


def _canary_detail(check_name, dead_loops, freshness_result=None):
    """Generate human-readable detail for a canary failure."""
    if check_name == "ollama":
        return "Ollama not responding — local model inference is down"
    elif check_name == "loops":
        return f"Background loops stopped: {', '.join(dead_loops)}"
    elif check_name == "practice_freshness":
        if freshness_result is not None:
            return canary_detail(freshness_result)
        return "Practice state stale"
    elif check_name == "file_io":
        return "File read/write test failed — filesystem may be read-only or full"
    elif check_name == "discord":
        return "Discord connection unhealthy — bot may need restart"
    return f"{check_name} check failed"
