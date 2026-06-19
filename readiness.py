"""turtleOS readiness assessment — 9-dimension practice health check."""

import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from mage import get_pd, get_runtime_dir
from practice_io import read_safe, count_items, file_age_hours, format_age
from state import (
    IDENTITY_DIR, DIALOGUE_MODEL, TURTLE_MODEL, RIVER_MODEL, USE_API,
    thread_configs, active_sessions,
)


def _resolve_default_pd():
    """Resolve practice dir from registry for background contexts where
    message-based context isn't set."""
    pd = get_pd()
    if pd and os.path.exists(os.path.join(pd, "boom", "bright.md")):
        return pd
    try:
        from mage import _load_mage_registry
        registry = _load_mage_registry()
        default_key = registry.get("default_mage")
        mages = registry.get("mages", {})
        primary = mages.get(default_key, {}) if default_key else next(
            (mage for mage in mages.values() if mage.get("primary")),
            next(iter(mages.values()), {}),
        )
        if primary and primary.get("practice_dir"):
            resolved = os.path.expanduser(primary["practice_dir"])
            if os.path.isdir(resolved):
                return resolved
    except Exception:
        pass
    return pd


def assess_readiness(pd=None) -> dict:
    """Full 8-dimension practice-readiness assessment.

    Returns dict with 'dimensions' (list of dimension results),
    'summary' (formatted string), and 'highest_leverage' (what to fix first).
    Each dimension: {name, status, detail} where status is ready/degraded/impaired.
    """
    # Import here to avoid circular imports — these are background task references
    from sessions import session_monitor
    from background import interoception_loop, practice_health_loop, daily_reminders_loop, health_canary_loop

    pd = pd or _resolve_default_pd()
    dims = []

    # 1. State Freshness — are practice files current?
    freshness_issues = []
    for name, fname in [("boom", "boom.md"), ("bright", os.path.join("boom", "bright.md")),
                        ("compass", os.path.join("intentions", "compass.md"))]:
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

    # 5. Workshop Visibility — check if LiveSync mirror is reachable via practice files
    sync_markers = [("boom", "boom.md"), ("compass", os.path.join("intentions", "compass.md"))]
    sync_ages = []
    for name, fname in sync_markers:
        age = file_age_hours(os.path.join(pd, fname))
        if age != float("inf"):
            sync_ages.append((name, age))
    if sync_ages:
        freshest_name, freshest_age = min(sync_ages, key=lambda x: x[1])
        if freshest_age < 24:
            dims.append({"name": "Workshop Visibility", "status": "ready",
                         "detail": f"workshop synced ({freshest_name} {format_age(freshest_age)} ago)"})
        elif freshest_age < 72:
            dims.append({"name": "Workshop Visibility", "status": "degraded",
                         "detail": f"workshop {format_age(freshest_age)} old"})
        else:
            dims.append({"name": "Workshop Visibility", "status": "impaired",
                         "detail": f"workshop stale ({format_age(freshest_age)})"})
    else:
        dims.append({"name": "Workshop Visibility", "status": "impaired",
                     "detail": "no practice files reachable"})

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
        dims.append({
            "name": "Substrate Health",
            "status": "ready",
            "detail": f"River `{RIVER_MODEL}` · Turtle `{DIALOGUE_MODEL if USE_API else TURTLE_MODEL}` + Ollama",
        })
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
    if daily_reminders_loop.is_running():
        metabolic_detail.append("reminders ✓")
    else:
        metabolic_ok = False
        metabolic_detail.append("reminders ✗")
    if health_canary_loop.is_running():
        metabolic_detail.append("canary ✓")
    else:
        metabolic_ok = False
        metabolic_detail.append("canary ✗")
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

    # 9. Content Reach — can we fetch content from external platforms?
    reach_result = _check_content_reach()
    dims.append(reach_result)

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
    pd = pd or get_runtime_dir()
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


def _check_content_reach() -> dict:
    """Check CLI tool availability and credential health for content fetching.
    Synchronous check (no network calls) — just tool presence and credential validity."""
    from content_fetch import _cli_path

    tools = {}
    issues = []
    warnings = []

    # Twitter: check tool + env vars
    twitter_cli = _cli_path("twitter")
    twitter_token = os.environ.get("TWITTER_AUTH_TOKEN", "")
    twitter_ct0 = os.environ.get("TWITTER_CT0", "")
    if twitter_cli and twitter_token and twitter_ct0:
        tools["twitter"] = "ready"
    elif twitter_cli and (not twitter_token or not twitter_ct0):
        tools["twitter"] = "no cookies"
        issues.append("Twitter: cookies missing")
    else:
        tools["twitter"] = "not installed"
        issues.append("Twitter: twitter-cli missing")

    # Reddit: check tool + credential file + JWT expiry
    rdt_cli = _cli_path("rdt")
    rdt_cred = Path.home() / ".config" / "rdt-cli" / "credential.json"
    if rdt_cli and rdt_cred.exists():
        try:
            cred_data = json.loads(rdt_cred.read_text())
            session_cookie = cred_data.get("cookies", {}).get("reddit_session", "")
            if session_cookie:
                days_left = _jwt_days_remaining(session_cookie)
                if days_left is not None:
                    if days_left < 0:
                        tools["reddit"] = "expired"
                        issues.append(f"Reddit: cookie expired {abs(days_left)}d ago")
                    elif days_left < 14:
                        tools["reddit"] = "expiring soon"
                        warnings.append(f"Reddit: cookie expires in {days_left}d")
                    else:
                        tools["reddit"] = f"ready ({days_left}d left)"
                else:
                    tools["reddit"] = "ready"
            else:
                tools["reddit"] = "no cookie"
                issues.append("Reddit: session cookie empty")
        except Exception:
            tools["reddit"] = "cred file corrupt"
            issues.append("Reddit: credential file unreadable")
    elif rdt_cli:
        tools["reddit"] = "no credentials"
        issues.append("Reddit: run rdt login or provide cookie")
    else:
        tools["reddit"] = "not installed"
        issues.append("Reddit: rdt-cli missing")

    # YouTube: check tool (no auth needed)
    ytdlp = _cli_path("yt-dlp")
    if ytdlp:
        tools["youtube"] = "ready"
    else:
        tools["youtube"] = "degraded"
        warnings.append("YouTube: yt-dlp missing (transcript API only)")

    # Build dimension result
    detail_parts = [f"{platform}: {status}" for platform, status in tools.items()]
    detail = ", ".join(detail_parts)

    if issues:
        if any("expired" in i or "missing" in i for i in issues):
            return {"name": "Content Reach", "status": "impaired", "detail": detail}
        return {"name": "Content Reach", "status": "degraded", "detail": detail}
    elif warnings:
        return {"name": "Content Reach", "status": "degraded", "detail": detail}
    return {"name": "Content Reach", "status": "ready", "detail": detail}


def _jwt_days_remaining(token: str) -> int | None:
    """Extract days until expiration from a JWT. Returns None if not a JWT."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload = parts[1]
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += "=" * padding
        decoded = base64.urlsafe_b64decode(payload)
        data = json.loads(decoded)
        exp = data.get("exp")
        if exp is None:
            return None
        now = datetime.now(timezone.utc).timestamp()
        return int((exp - now) / 86400)
    except Exception:
        return None


def check_content_reach_detail() -> str:
    """Detailed content reach report for care rituals and diagnostics.
    Returns a formatted string with tool versions, credential status, and recommendations."""
    from content_fetch import _cli_path

    lines = ["**Content Reach Diagnostic**", ""]

    # Twitter
    twitter_cli = _cli_path("twitter")
    if twitter_cli:
        lines.append(f"🐦 **Twitter:** twitter-cli installed at `{twitter_cli}`")
        token = os.environ.get("TWITTER_AUTH_TOKEN", "")
        ct0 = os.environ.get("TWITTER_CT0", "")
        if token and ct0:
            lines.append(f"   Auth: cookie configured (token: ...{token[-8:]})")
        else:
            lines.append("   ⚠️ Auth: TWITTER_AUTH_TOKEN and/or TWITTER_CT0 missing from environment")
            lines.append("   → Ask the Mage to extract cookies from browser DevTools")
    else:
        lines.append("🐦 **Twitter:** ❌ twitter-cli not installed")
        lines.append("   → `pip install twitter-cli`")

    lines.append("")

    # Reddit
    rdt = _cli_path("rdt")
    rdt_cred = Path.home() / ".config" / "rdt-cli" / "credential.json"
    if rdt:
        lines.append(f"📖 **Reddit:** rdt-cli installed at `{rdt}`")
        if rdt_cred.exists():
            try:
                cred = json.loads(rdt_cred.read_text())
                session = cred.get("cookies", {}).get("reddit_session", "")
                if session:
                    days = _jwt_days_remaining(session)
                    if days is not None:
                        if days < 0:
                            lines.append(f"   🔴 Cookie EXPIRED {abs(days)} days ago")
                            lines.append("   → Ask the Mage: extract reddit_session cookie from browser")
                        elif days < 14:
                            lines.append(f"   🟡 Cookie expires in {days} days — renewal needed soon")
                            lines.append("   → Ask the Mage before it expires")
                        else:
                            lines.append(f"   Auth: session valid ({days} days remaining)")
                    else:
                        lines.append("   Auth: session cookie present (no expiry detected)")
                else:
                    lines.append("   ⚠️ Credential file exists but session cookie empty")
            except Exception as e:
                lines.append(f"   ⚠️ Could not read credential file: {e}")
        else:
            lines.append("   ⚠️ No credentials configured")
            lines.append("   → Ask the Mage: extract reddit_session cookie from browser")
    else:
        lines.append("📖 **Reddit:** ❌ rdt-cli not installed")
        lines.append("   → `pip install rdt-cli`")

    lines.append("")

    # YouTube
    yt = _cli_path("yt-dlp")
    if yt:
        lines.append(f"📺 **YouTube:** yt-dlp installed at `{yt}`")
        lines.append("   Auth: none needed (public content)")
    else:
        lines.append("📺 **YouTube:** ⚠️ yt-dlp not installed (using transcript API only)")
        lines.append("   → `pip install yt-dlp`")

    lines.append("")
    lines.append("*Content reach is checked automatically in readiness assessment.*")
    lines.append("*Cookie renewal requires the Mage — Turtle will alert when expiration approaches.*")

    return "\n".join(lines)
