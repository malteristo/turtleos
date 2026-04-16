"""turtleOS practice pulse — vitality scanner for river-entry and interoception."""

import os
import re
from datetime import datetime
from pathlib import Path

from mage import get_pd
from practice_io import read_safe, count_items, file_age_hours, format_age

RIVER_STATE_PATH = os.path.expanduser("~/turtleos/river_state.md")


def scan_pulse(pd=None):
    """Scan practice surfaces and return structured vitality picture."""
    pd = pd or get_pd()
    pulse = {}

    # Sessions
    sdir = os.path.join(pd, "sessions")
    recent_sessions = []
    if os.path.isdir(sdir):
        files = sorted(
            [f for f in os.listdir(sdir) if f.endswith(".md")],
            key=lambda f: os.path.getmtime(os.path.join(sdir, f)),
            reverse=True,
        )
        for f in files[:5]:
            age = file_age_hours(os.path.join(sdir, f))
            if age < 72:
                recent_sessions.append({"name": f, "age_hours": age})
    pulse["sessions"] = {
        "recent": recent_sessions,
        "count_recent": len(recent_sessions),
        "latest_age": recent_sessions[0]["age_hours"] if recent_sessions else float("inf"),
    }

    # Proposals
    pdir = os.path.join(pd, "proposals")
    proposal_count = 0
    if os.path.isdir(pdir):
        proposal_count = len([
            f for f in os.listdir(pdir)
            if f.endswith(".md") and os.path.isfile(os.path.join(pdir, f))
        ])
    pulse["proposals"] = {"total": proposal_count}

    # Notes
    ndir = os.path.join(pd, "notes")
    recent_notes = []
    if os.path.isdir(ndir):
        files = sorted(
            [f for f in os.listdir(ndir) if f.endswith(".md")],
            key=lambda f: os.path.getmtime(os.path.join(ndir, f)),
            reverse=True,
        )
        for f in files[:3]:
            age = file_age_hours(os.path.join(ndir, f))
            if age < 72:
                name = f.replace(".md", "").replace("_", " ")
                if name.startswith("on "):
                    name = name[3:]
                recent_notes.append({"name": name, "age_hours": age})
    pulse["notes"] = {"recent": recent_notes, "count_recent": len(recent_notes)}

    # Boom
    boom_path = os.path.join(pd, "boom.md")
    pulse["boom"] = {
        "count": count_items(read_safe(boom_path)),
        "age_hours": file_age_hours(boom_path),
    }

    # Bright
    bright_path = os.path.join(pd, "boom", "bright.md")
    pulse["bright"] = {
        "count": count_items(read_safe(bright_path)),
        "age_hours": file_age_hours(bright_path),
    }

    # Compass
    pulse["compass"] = {
        "age_hours": file_age_hours(os.path.join(pd, "intentions", "compass.md")),
    }

    # Intentions — recently touched
    idir = os.path.join(pd, "intentions", "active")
    active_intentions = []
    if os.path.isdir(idir):
        for f in os.listdir(idir):
            if f.endswith(".md"):
                age = file_age_hours(os.path.join(idir, f))
                name = f.replace(".md", "").replace("_", " ").replace("-", " ")
                active_intentions.append({"name": name, "age_hours": age})
        active_intentions.sort(key=lambda x: x["age_hours"])
    pulse["intentions"] = active_intentions

    # Stale threads
    try:
        from thread_registry import get_stale_threads
        stale = get_stale_threads(days=7)
        unharvested = [t for t in stale if t["harvest_status"] == "pending"]
        pulse["threads_stale"] = {
            "count": len(stale),
            "unharvested": len(unharvested),
            "names": [t["name"] for t in unharvested[:5]],
        }
    except Exception:
        pulse["threads_stale"] = {"count": 0, "unharvested": 0, "names": []}

    # Signal drip
    drip_path = os.path.join(pd, "outfacing", "drip-state.md")
    drip_content = read_safe(drip_path)
    if drip_content:
        pending = re.findall(r"\|\s*(\d+)\s*\|\s*pending\s*\|", drip_content)
        all_nums = re.findall(r"\|\s*(\d+)\s*\|\s*(?:posted|pending)\s*\|", drip_content)
        total = max(int(n) for n in all_nums) if all_nums else 0
        pulse["drip"] = {
            "pending": len(pending),
            "next": int(pending[0]) if pending else None,
            "total": total,
        }
    else:
        pulse["drip"] = None

    pulse["texture"] = _classify_texture(pulse)
    return pulse


def _classify_texture(pulse):
    """Classify practice texture from signals."""
    boom_active = pulse["boom"]["age_hours"] < 24
    sessions_active = pulse["sessions"]["count_recent"] > 0
    notes_active = pulse["notes"]["count_recent"] > 0

    if sessions_active and notes_active:
        return "executing"
    if boom_active and not sessions_active:
        return "accumulating"
    if notes_active and not boom_active:
        return "digesting"
    if sessions_active:
        return "stirring"
    if not any([boom_active, sessions_active, notes_active]):
        return "quiet"
    return "stirring"


def compose_river_entry(pulse, thread_count=0):
    """Compose the river-entry narrative from pulse data.

    Three beats: live thread, quality of current, opening gesture.
    Returns (title, description) for a Discord embed.
    """
    lines = []

    live = _find_live_threads(pulse)
    if live:
        lines.append(live)

    texture = _describe_texture(pulse)
    if texture:
        lines.append(texture)

    lines.append(_opening_gesture(pulse))

    return "\U0001f422 *enters the river*", "\n".join(lines)


def _find_live_threads(pulse):
    """Name the 1-2 things with energy right now."""
    hot = [i for i in pulse["intentions"] if i["age_hours"] < 48]

    if len(hot) >= 3:
        return f"{hot[0]['name']}, {hot[1]['name']}, and more — active on multiple fronts."
    elif len(hot) == 2:
        frag = f"{hot[0]['name']} and {hot[1]['name']} both moving."
        if pulse["drip"] and pulse["drip"]["pending"]:
            d = pulse["drip"]
            frag += f" Signal pipeline at tweet {d['next']}/{d['total']}."
        return frag
    elif len(hot) == 1:
        frag = hot[0]["name"]
        if pulse["drip"] and pulse["drip"]["pending"]:
            d = pulse["drip"]
            return f"{frag} is the live thread. Signal pipeline at tweet {d['next']}/{d['total']}."
        return f"The {frag} thread is the live one."

    parts = []
    if pulse["drip"] and pulse["drip"]["pending"]:
        d = pulse["drip"]
        parts.append(f"Signal pipeline at tweet {d['next']}/{d['total']}")
    if pulse["sessions"]["count_recent"] > 0 and pulse["sessions"]["latest_age"] < 24:
        parts.append("recent conversation still warm")
    if pulse["notes"]["count_recent"] > 0:
        n = pulse["notes"]["recent"][0]
        parts.append(f"a note on {n['name']} crystallizing")

    if parts:
        return ". ".join(p.capitalize() if i == 0 else p for i, p in enumerate(parts)) + "."
    return None


def _describe_texture(pulse):
    """Describe quality of the current — texture, not gauges."""
    t = pulse["texture"]
    extras = []

    if pulse["boom"]["count"] >= 5:
        extras.append(f"boom has {pulse['boom']['count']} items")
    if pulse["drip"] and pulse["drip"]["pending"] and not any(
        i["age_hours"] < 48 for i in pulse["intentions"]
    ):
        extras.append("signal pipeline mid-drip")
    if pulse["proposals"]["total"] >= 10:
        extras.append(f"{pulse['proposals']['total']} proposals waiting")
    if pulse["threads_stale"]["unharvested"] > 0:
        extras.append(f"{pulse["threads_stale"]["unharvested"]} {"eddy" if pulse["threads_stale"]["unharvested"] == 1 else "eddies"} unharvested")

    phrases = {
        "executing": "Sessions and artifacts moving together.",
        "accumulating": "Boom accumulating \u2014 something percolating.",
        "digesting": "Digestion mode \u2014 crystallizing without new input.",
        "stirring": "Things stirring across surfaces.",
        "quiet": "Practice has been quiet.",
    }

    base = phrases.get(t, "")
    if extras:
        return base + " " + " \u00b7 ".join(extras[:2])
    return base


def _opening_gesture(pulse):
    """Calibrated opening based on what's perceived."""
    if pulse["texture"] == "quiet" and pulse["sessions"]["latest_age"] > 72:
        return "*what brought you to the river?*"
    stale = pulse["threads_stale"]
    if stale["unharvested"] > 0 and stale["names"]:
        return f"*{stale['names'][0]} has been quiet \u2014 sitting or stalled?*"
    if pulse["texture"] == "accumulating":
        return "*what wants to surface?*"
    return "*what's moving?*"


def _pulse_signature(pulse):
    """Extract comparable dimensions from pulse for delta detection."""
    return {
        "boom_count": pulse["boom"]["count"],
        "boom_stale": pulse["boom"]["age_hours"] > 24,
        "bright_stale": pulse["bright"]["age_hours"] > 168,
        "compass_stale": pulse["compass"]["age_hours"] > 168,
        "session_gap": pulse["sessions"]["latest_age"] > 72,
        "proposals": pulse["proposals"]["total"],
        "eddies_unharvested": pulse["threads_stale"]["unharvested"],
        "eddies_quiet": pulse["threads_stale"]["count"],
        "texture": pulse["texture"],
    }


def _delta_significant(prev_sig, curr_sig):
    """Check if the change between pulse signatures is worth reporting."""
    if prev_sig is None:
        return True

    for key in ("boom_stale", "bright_stale", "compass_stale", "session_gap"):
        if prev_sig.get(key) != curr_sig.get(key):
            return True

    if prev_sig.get("texture") != curr_sig.get("texture"):
        return True

    boom_prev, boom_curr = prev_sig.get("boom_count", 0), curr_sig.get("boom_count", 0)
    if (boom_prev < 10 and boom_curr >= 10) or (boom_prev < 20 and boom_curr >= 20):
        return True

    prop_prev, prop_curr = prev_sig.get("proposals", 0), curr_sig.get("proposals", 0)
    if abs(prop_curr - prop_prev) >= 3:
        return True

    eddy_prev = prev_sig.get("eddies_unharvested", 0)
    eddy_curr = curr_sig.get("eddies_unharvested", 0)
    if abs(eddy_curr - eddy_prev) >= 3:
        return True

    return False


def compose_interoception(pulse, prev_pulse=None):
    """Compose interoception signals from pulse data.

    Delta-aware: if prev_pulse is provided, only signals meaningful changes.
    Returns list of (emoji, text) tuples.
    """
    curr_sig = _pulse_signature(pulse)
    prev_sig = _pulse_signature(prev_pulse) if prev_pulse else None

    if prev_sig and not _delta_significant(prev_sig, curr_sig):
        return []

    signals = []

    bc, ba = pulse["boom"]["count"], pulse["boom"]["age_hours"]
    if bc >= 10 and ba > 24:
        signals.append(("\U0001f35d", f"Boom feels heavy \u2014 {bc} items, last touched {format_age(ba)} ago"))
    elif bc >= 20:
        signals.append(("\U0001f35d", f"Boom is overflowing \u2014 {bc} items. Consider `!sweep`"))

    if pulse["compass"]["age_hours"] > 168:
        signals.append(("\U0001f9ed", f"Compass hasn't been touched in {format_age(pulse['compass']['age_hours'])}"))

    if pulse["bright"]["age_hours"] > 168:
        signals.append(("\u2728", f"Bright untouched for {format_age(pulse['bright']['age_hours'])}"))

    sa = pulse["sessions"]["latest_age"]
    if sa > 72 and sa != float("inf"):
        signals.append(("\U0001f4ad", f"No conversations in {format_age(sa)}"))
    elif sa == float("inf"):
        signals.append(("\U0001f4ad", "No session notes yet"))

    if pulse["proposals"]["total"] >= 3:
        signals.append(("\U0001f4ec", f"{pulse['proposals']['total']} proposals in `proposals/`"))

    ts = pulse["threads_stale"]
    if ts["unharvested"] > 0:
        names = ", ".join(ts["names"][:5])
        extra = f" (+{ts['unharvested'] - 5} more)" if ts["unharvested"] > 5 else ""
        signals.append(("\U0001f50d", f"{ts['unharvested']} eddies quiet >7d, unharvested: {names}{extra}"))
    elif ts["count"] > 0:
        signals.append(("\U0001f30a", f"{ts['count']} quiet eddies (all harvested)"))

    if pulse["texture"] == "quiet":
        signals.append(("\U0001f4a4", "Practice state quiet \u2014 nothing updated in 2+ days"))

    return signals




def save_river_state(title, content):
    """Save what Turtle posted to the river, for context loop injection."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    state = f"*Last posted {timestamp}*\n\n**{title}**\n{content}\n"
    try:
        Path(RIVER_STATE_PATH).write_text(state)
    except Exception as e:
        print(f"River state save failed: {e}")
