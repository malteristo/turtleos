"""turtleOS practice pulse — vitality scanner for river-entry and interoception."""

import os
import re
from datetime import datetime
from pathlib import Path

from mage import get_pd
from practice_io import read_safe, count_items, file_age_hours, format_age

RIVER_STATE_PATH = os.path.expanduser("~/turtleos/river_state.md")

PROPOSAL_ACTIVE_STATES = {"proposed", "accepted", "implementing", "review"}
PROPOSAL_INACTIVE_STATES = {"hold", "deployed", "released", "archived", "integrated"}
PROPOSAL_STATE_ALIASES = {
    "draft": "proposed",
    "awaiting resonance check": "proposed",
    "new": "proposed",
    "open": "proposed",
    "endorsed": "accepted",
    "approved": "accepted",
    "adopted": "deployed",
    "implemented": "deployed",
    "deployed": "deployed",
    "stabilized": "deployed",
    "closed": "released",
    "subsumed": "released",
    "rejected": "released",
    "superseded": "released",
    "incubating": "hold",
    "blocked": "hold",
}
PROPOSAL_STATE_DIRS = PROPOSAL_ACTIVE_STATES | PROPOSAL_INACTIVE_STATES


def _normalize_proposal_state(raw: str | None) -> str:
    if not raw:
        return "proposed"
    status = re.sub(r"[*_`]+", "", raw).strip().lower()
    status = status.split("—", 1)[0].strip()
    status = status.split("-", 1)[0].strip()
    status = status.split("(", 1)[0].strip()
    status = re.sub(r"[^a-z\s]", " ", status)
    status = re.sub(r"\s+", " ", status).strip()

    if status in PROPOSAL_ACTIVE_STATES or status in PROPOSAL_INACTIVE_STATES:
        return status
    for key, state in PROPOSAL_STATE_ALIASES.items():
        if key in status:
            return state
    if "phase" in status and "implemented" in status:
        return "deployed"
    return "proposed"


def _proposal_state_from_path(path: Path, proposals_dir: Path) -> str | None:
    try:
        rel = path.relative_to(proposals_dir)
    except ValueError:
        return None
    if len(rel.parts) <= 1:
        return None
    dirname = rel.parts[0].lower()
    if dirname in PROPOSAL_STATE_DIRS:
        return dirname
    return None


def _proposal_status_line(text: str) -> str | None:
    lines = text.splitlines()
    for line in lines[:12]:
        match = re.search(r"status\**\s*:?\s*(.+)$", line, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    first_line = lines[0] if lines else ""
    bracket = re.search(r"\[([^\]]+)\]", first_line)
    if bracket:
        return bracket.group(1).strip()
    return None


def _proposal_state(path: Path, proposals_dir: Path) -> str:
    state = _proposal_state_from_path(path, proposals_dir)
    if state:
        return state
    try:
        content = path.read_text(errors="ignore")
    except Exception:
        return "proposed"
    return _normalize_proposal_state(_proposal_status_line(content))


def _scan_proposals(proposals_dir: str) -> dict:
    base = Path(proposals_dir)
    counts = {state: 0 for state in sorted(PROPOSAL_ACTIVE_STATES | PROPOSAL_INACTIVE_STATES)}
    examples = {state: [] for state in counts}
    files_total = 0

    if not base.is_dir():
        return {
            "total": 0,
            "active": 0,
            "files_total": 0,
            "by_state": counts,
            "examples": examples,
        }

    for path in sorted(base.rglob("*.md")):
        if not path.is_file() or path.name.lower() == "readme.md":
            continue
        files_total += 1
        state = _proposal_state(path, base)
        counts[state] = counts.get(state, 0) + 1
        if len(examples.setdefault(state, [])) < 3:
            examples[state].append(str(path.relative_to(base)))

    active = sum(counts.get(state, 0) for state in PROPOSAL_ACTIVE_STATES)
    return {
        "total": active,
        "active": active,
        "files_total": files_total,
        "by_state": counts,
        "examples": examples,
    }


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

    # Proposals — count active lifecycle pressure, not historical sediment.
    pdir = os.path.join(pd, "proposals")
    pulse["proposals"] = _scan_proposals(pdir)

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
        attention = sorted(unharvested, key=_eddy_attention_score, reverse=True)
        pulse["threads_stale"] = {
            "count": len(stale),
            "unharvested": len(unharvested),
            "names": [t["name"] for t in attention[:5]],
            "attention": attention[:5],
        }
    except Exception:
        pulse["threads_stale"] = {"count": 0, "unharvested": 0, "names": [], "attention": []}

    pulse["texture"] = _classify_texture(pulse)
    return pulse


def _eddy_attention_score(thread: dict) -> float:
    name = thread.get("name", "").lower()
    score = min(thread.get("message_count", 0), 80)
    priority_terms = {
        "learnings": 90,
        "resonance": 70,
        "practice": 60,
        "discord": 55,
        "turtle": 35,
        "boom": 35,
    }
    for key, boost in priority_terms.items():
        if key in name:
            score += boost
            break
    score -= min(thread.get("age_days", 0), 60) * 0.4
    return score


def _top_attention_eddy(pulse) -> dict | None:
    attention = pulse.get("threads_stale", {}).get("attention") or []
    return attention[0] if attention else None


def _format_eddy_name(name: str) -> str:
    return name.replace("_", " ").strip()

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
    what = _find_live_threads(pulse)
    if not what:
        what = "Turtle is present; no single practice thread is strongly pulling."

    doorway = _practice_doorway(pulse)
    texture = _describe_texture(pulse)
    if doorway and texture:
        so_what = f"{texture} {doorway}"
    else:
        so_what = doorway or texture or "Nothing looks urgent; orientation is enough."

    now_what = _opening_gesture(pulse)
    if now_what.lower().startswith("suggested: "):
        now_what = now_what.split(":", 1)[1].strip()
    if not now_what:
        now_what = "no action needed yet; keep watching."

    lines = [
        f"What: {what}",
        f"So What: {so_what}",
        f"Now What: {now_what}",
    ]

    return "🐢 *enters the river*", "\n".join(lines)

def _find_live_threads(pulse):
    """Name the 1-2 things with energy right now."""
    hot = [i for i in pulse["intentions"] if i["age_hours"] < 48]

    if len(hot) >= 3:
        return f"{hot[0]['name']}, {hot[1]['name']}, and more — active on multiple fronts."
    elif len(hot) == 2:
        return f"{hot[0]['name']} and {hot[1]['name']} both moving."
    elif len(hot) == 1:
        return f"The {hot[0]['name']} thread is the live one."

    parts = []
    if pulse["sessions"]["count_recent"] > 0 and pulse["sessions"]["latest_age"] < 24:
        parts.append("recent conversation still warm")
    if pulse["notes"]["count_recent"] > 0:
        n = pulse["notes"]["recent"][0]
        parts.append(f"a note on {n['name']} crystallizing")

    if parts:
        return ". ".join(p.capitalize() if i == 0 else p for i, p in enumerate(parts)) + "."
    return None


def _practice_doorway(pulse) -> str:
    top_eddy = _top_attention_eddy(pulse)
    if top_eddy:
        name = _format_eddy_name(top_eddy["name"])
        return f"`{name}` may hold uncaptured resonance; review it before opening new threads."

    if pulse["boom"]["count"] >= 10:
        return f"boom has {pulse['boom']['count']} items; a sweep would turn raw material into usable surface."

    if pulse["proposals"]["total"] >= 10:
        return f"{pulse['proposals']['total']} proposals are waiting; choose one proposal to accept, revise, or close."

    if pulse["sessions"]["count_recent"] > 0:
        return "recent conversation is still warm; harvest one lesson before it becomes sediment."

    return "choose a thread, a sweep, or a quiet check-in."

def _describe_texture(pulse):
    phrases = {
        "executing": "Sessions and artifacts are moving together.",
        "accumulating": "Raw material is accumulating and wants a sweep.",
        "digesting": "The practice is digesting; look for what is ready to crystallize.",
        "stirring": "Several surfaces are active; choose one doorway.",
        "quiet": "The practice is quiet; begin with orientation rather than maintenance.",
    }
    return phrases.get(pulse["texture"], "")

def _opening_gesture(pulse):
    top_eddy = _top_attention_eddy(pulse)
    if top_eddy:
        name = _format_eddy_name(top_eddy["name"])
        return f"Suggested: ask `what resonance in {name} has not landed yet?`"
    if pulse["boom"]["count"] >= 10:
        return "Suggested: run a focused sweep before adding more raw material."
    if pulse["texture"] == "quiet" and pulse["sessions"]["latest_age"] > 72:
        return "Suggested: start with recall or name what brought you here."
    return "Suggested: pick the live thread, then harvest one concrete next step."

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
    curr_sig = _pulse_signature(pulse)
    prev_sig = _pulse_signature(prev_pulse) if prev_pulse else None

    if prev_sig and not _delta_significant(prev_sig, curr_sig):
        return []

    signals = []

    bc, ba = pulse["boom"]["count"], pulse["boom"]["age_hours"]
    if bc >= 20:
        signals.append(("🍝", f"Raw material is overflowing: {bc} boom items. Remedy: sweep before collecting more."))
    elif bc >= 10 and ba > 24:
        signals.append(("🍝", f"Boom is heavy: {bc} items, last touched {format_age(ba)} ago. Remedy: distill the top few."))

    top_eddy = _top_attention_eddy(pulse)
    ts = pulse["threads_stale"]
    if top_eddy:
        name = _format_eddy_name(top_eddy["name"])
        signals.append(("🔍", f"Uncaptured resonance risk: {ts['unharvested']} quiet eddies. Start with `{name}` ({top_eddy.get('message_count', 0)} msgs)."))
    elif ts["count"] > 0:
        signals.append(("🌊", f"{ts['count']} quiet eddies, all marked harvested. No action unless one feels alive again."))

    if pulse["proposals"]["total"] >= 20:
        signals.append(("📬", f"Proposal sediment: {pulse['proposals']['total']} files waiting. Remedy: accept, revise, or close one before adding more."))
    elif pulse["proposals"]["total"] >= 3:
        signals.append(("📬", f"{pulse['proposals']['total']} proposals waiting. Remedy: review one when the current thread pauses."))

    compass_age = pulse["compass"]["age_hours"]
    if compass_age != float("inf") and compass_age > 168:
        signals.append(("🧭", f"Compass is stale ({format_age(compass_age)}). Remedy: brief orientation refresh, not a full rewrite."))

    bright_age = pulse["bright"]["age_hours"]
    if bright_age != float("inf") and bright_age > 168:
        signals.append(("✨", f"Bright has not been touched in {format_age(bright_age)}. Remedy: promote one harvested pattern."))

    sa = pulse["sessions"]["latest_age"]
    if sa > 72 and sa != float("inf"):
        signals.append(("💭", f"Session continuity gap: no conversations in {format_age(sa)}. Remedy: recall before deep work."))
    elif sa == float("inf"):
        signals.append(("💭", "No session notes yet. Remedy: close the next meaningful exchange with release."))

    if pulse["texture"] == "quiet":
        signals.append(("💤", "Practice is quiet. Remedy: offer a doorway, not a nag."))

    return signals[:3]

def save_river_state(title, content):
    """Save what Turtle posted to the river, for context loop injection."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    state = f"*Last posted {timestamp}*\n\n**{title}**\n{content}\n"
    try:
        Path(RIVER_STATE_PATH).write_text(state)
    except Exception as e:
        print(f"River state save failed: {e}")
