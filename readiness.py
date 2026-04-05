"""turtleOS readiness assessment — 8-dimension practice health check."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from mage import get_pd
from practice_io import read_safe, count_items, file_age_hours, format_age
from state import (
    IDENTITY_DIR, DIALOGUE_MODEL, USE_API,
    thread_configs, active_sessions,
)


def assess_readiness(pd=None) -> dict:
    """Full 8-dimension practice-readiness assessment.

    Returns dict with 'dimensions' (list of dimension results),
    'summary' (formatted string), and 'highest_leverage' (what to fix first).
    Each dimension: {name, status, detail} where status is ready/degraded/impaired.
    """
    # Import here to avoid circular imports — these are background task references
    from sessions import session_monitor
    from background import interoception_loop, practice_health_loop

    pd = pd or get_pd()
    dims = []

    # 1. State Freshness — are practice files current?
    freshness_issues = []
    for name, fname in [("boom", "boom.md"), ("bright", os.path.join("boom", "bright.md")),
                        ("compass", os.path.join("intentions", "compass.md")), ("state", "state.md")]:
        age = file_age_hours(os.path.join(pd, fname))
        if age == float("inf"):
            freshness_issues.append(f"{name} missing")
        elif age > 48:
            freshness_issues.append(f"{name} {format_age(age)}")
    if not freshness_issues:
        dims.append({"name": "State Freshness", "status": "ready", "detail": "all files < 48h"})
    elif any("missing" in i for i in freshness_issues):
        dims.append({"name": "State Freshness", "status": "impaired", "detail": ", ".join(freshness_issues)})
    else:
        dims.append({"name": "State Freshness", "status": "degraded", "detail": ", ".join(freshness_issues)})

    # 2. Context Coherence
    boom = read_safe(os.path.join(pd, "boom.md"))
    bright = read_safe(os.path.join(pd, "boom", "bright.md"))
    compass = read_safe(os.path.join(pd, "intentions", "compass.md"))
    present = sum(1 for t in [boom, bright, compass] if t.strip())
    if present == 3:
        boom_count = count_items(boom)
        bright_count = count_items(bright)
        if boom_count > 15 and bright_count > 50:
            dims.append({"name": "Context Coherence", "status": "degraded",
                         "detail": f"boom({boom_count}) and bright({bright_count}) both heavy — integration lag likely"})
        else:
            dims.append({"name": "Context Coherence", "status": "ready",
                         "detail": f"boom({boom_count}), bright({bright_count})"})
    elif present == 0:
        dims.append({"name": "Context Coherence", "status": "impaired", "detail": "no practice files found"})
    else:
        dims.append({"name": "Context Coherence", "status": "degraded",
                     "detail": f"{present}/3 practice surfaces present"})

    # 3. Thread Awareness
    tc_count = len(thread_configs)
    active_count = sum(1 for s in active_sessions.values() if not s["closed"])
    if tc_count == 0 and active_count == 0:
        dims.append({"name": "Thread Awareness", "status": "ready", "detail": "no active eddies"})
    else:
        dims.append({"name": "Thread Awareness", "status": "ready",
                     "detail": f"{tc_count} configured, {active_count} in session"})

    # 4. Session Continuity
    sessions_dir = os.path.join(pd, "sessions")
    if os.path.isdir(sessions_dir):
        session_files = sorted(Path(sessions_dir).glob("*.md"))
        if session_files:
            latest = session_files[-1]
            age = file_age_hours(str(latest))
            content = read_safe(str(latest))
            has_thread = "thread for next time" in content.lower() or "next time" in content.lower()
            if age < 24:
                dims.append({"name": "Session Continuity", "status": "ready",
                             "detail": f"last session {format_age(age)} ago" + (" (has continuation thread)" if has_thread else "")})
            elif age < 72:
                dims.append({"name": "Session Continuity", "status": "degraded",
                             "detail": f"last session {format_age(age)} ago"})
            else:
                dims.append({"name": "Session Continuity", "status": "impaired",
                             "detail": f"no session in {format_age(age)}"})
        else:
            dims.append({"name": "Session Continuity", "status": "impaired", "detail": "no session notes"})
    else:
        dims.append({"name": "Session Continuity", "status": "impaired", "detail": "no sessions directory"})

    # 5. Workshop Visibility
    workshop_sync_marker = os.path.join(pd, "state.md")
    sync_age = file_age_hours(workshop_sync_marker)
    if sync_age < 24:
        dims.append({"name": "Workshop Visibility", "status": "ready",
                     "detail": f"state synced {format_age(sync_age)} ago"})
    elif sync_age < 72:
        dims.append({"name": "Workshop Visibility", "status": "degraded",
                     "detail": f"state {format_age(sync_age)} old"})
    else:
        dims.append({"name": "Workshop Visibility", "status": "impaired",
                     "detail": f"no sync in {format_age(sync_age)}" if sync_age != float("inf") else "no state file"})

    # 6. Substrate Health
    substrate_issues = []
    try:
        import urllib.request
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3) as resp:
            if resp.status != 200:
                substrate_issues.append("Ollama not responding")
    except Exception:
        substrate_issues.append("Ollama unreachable")
    if USE_API and not os.environ.get("ANTHROPIC_API_KEY"):
        substrate_issues.append("API key missing")
    if not substrate_issues:
        dims.append({"name": "Substrate Health", "status": "ready", "detail": f"{DIALOGUE_MODEL} + Ollama"})
    else:
        dims.append({"name": "Substrate Health", "status": "impaired", "detail": ", ".join(substrate_issues)})

    # 7. Metabolic Health
    metabolic_ok = True
    metabolic_detail = []
    if session_monitor.is_running():
        metabolic_detail.append("session monitor ✓")
    else:
        metabolic_ok = False
        metabolic_detail.append("session monitor ✗")
    if interoception_loop.is_running():
        metabolic_detail.append("interoception ✓")
    else:
        metabolic_ok = False
        metabolic_detail.append("interoception ✗")
    if practice_health_loop.is_running():
        metabolic_detail.append("health loop ✓")
    else:
        metabolic_ok = False
        metabolic_detail.append("health loop ✗")
    dims.append({"name": "Metabolic Health",
                 "status": "ready" if metabolic_ok else "degraded",
                 "detail": ", ".join(metabolic_detail)})

    # 8. Attunement Depth
    soul_path = os.path.join(IDENTITY_DIR, "soul.md")
    soul_age = file_age_hours(soul_path)
    soul_content = read_safe(soul_path)
    if soul_content and soul_age < 168:
        dims.append({"name": "Attunement Depth", "status": "ready",
                     "detail": f"soul.md loaded ({len(soul_content)} chars)"})
    elif soul_content:
        dims.append({"name": "Attunement Depth", "status": "degraded",
                     "detail": f"soul.md {format_age(soul_age)} old"})
    else:
        dims.append({"name": "Attunement Depth", "status": "impaired", "detail": "soul.md missing"})

    # Determine highest-leverage improvement
    impaired = [d for d in dims if d["status"] == "impaired"]
    degraded = [d for d in dims if d["status"] == "degraded"]
    if impaired:
        highest = impaired[0]
    elif degraded:
        highest = degraded[0]
    else:
        highest = None

    # Build summary
    status_icons = {"ready": "🟢", "degraded": "🟡", "impaired": "🔴"}
    lines = []
    for d in dims:
        lines.append(f"{status_icons[d['status']]} **{d['name']}:** {d['detail']}")

    summary = "\n".join(lines)
    if highest:
        summary += f"\n\n**Highest-leverage improvement:** {highest['name']} — {highest['detail']}"

    return {"dimensions": dims, "summary": summary, "highest_leverage": highest}


def startup_readiness_check() -> str:
    """Quick readiness check for startup embed. Returns formatted string."""
    result = assess_readiness()
    ready = sum(1 for d in result["dimensions"] if d["status"] == "ready")
    total = len(result["dimensions"])
    if ready == total:
        return "**Readiness:** Practice-ready ✅"
    degraded = sum(1 for d in result["dimensions"] if d["status"] == "degraded")
    impaired = sum(1 for d in result["dimensions"] if d["status"] == "impaired")
    parts = [f"**Readiness:** {ready}/{total} ready"]
    if degraded:
        parts.append(f"{degraded} degraded")
    if impaired:
        parts.append(f"{impaired} impaired")
    if result["highest_leverage"]:
        parts.append(f"→ {result['highest_leverage']['name']}")
    return " · ".join(parts)


def save_readiness_trail(result, pd=None):
    """Append readiness assessment to the trail for trend analysis."""
    pd = pd or get_pd()
    trail_dir = Path(pd) / "readiness"
    trail_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    entry = {
        "timestamp": now.isoformat(),
        "dimensions": result["dimensions"],
        "highest_leverage": result["highest_leverage"],
    }
    trail_path = trail_dir / f"{now.strftime('%Y-%m-%d')}.jsonl"
    with open(trail_path, "a") as f:
        f.write(json.dumps(entry) + "\n")
