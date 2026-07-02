"""Continuity Engine — the current + alive layers.

Shell infrastructure (not a model) that makes Turtle *conscious of* present
context: it writes ``state/current.yaml`` / ``state/alive.yaml`` under the
practice root and renders a hidden, shell-injected block so Turtle knows roughly
when it is, what it runs on, and what's in motion — without the practitioner
having to say so each eddy.

Slice 0 — the current layer (``docs/design/...`` §11):
  - Compose + persist clock, timezone, day-part, season, host label, inference
    locality, dialogue + river model ids; render a plain-language inject block.
  - Acceptance: Turtle answers "what day is it?" without being told (§12.1).

Slice 1 — the alive layer + narrowing (§11, §5.2, §7):
  - ``state/alive.yaml``: active threads (internal: "knots") → **headers only**
    in the holistic packet; intention headers fold in when intention files exist.
  - Narrowing: ``current.scope`` is set per-eddy (cross-process via
    ``state/scopes.yaml``) so ``!focus`` in the River process is visible to the
    Turtle process; a scope pulls **scoped self-feed** from session notes.
  - Acceptance: scoped eddy pulls deeper context on one topic; holistic stays
    thin; Turtle does not recite substrate unprompted or use internal jargon.

Design stances honored here:
  - **Hardware honesty (§3.2.3):** identity is read live from the running
    process — the resolved dialogue model for *this* turn and the actual host —
    not a hard-coded config string that can drift from reality.
  - **Vocabulary firewall (§4):** blocks use plain language only; the
    river-ecology terms (bedrock/sediment/alive/current/knot) never appear, so
    the model never learns to echo internal jargon back to the practitioner.
  - **Invisible, not opaque (§3.5):** blocks are background context, hidden from
    the channel by default, and cheap to inspect via this module's CLI.
  - **Per-eddy scope, not per-root:** narrowing one conversation must not narrow
    the others, so scope is keyed by channel id in ``scopes.yaml`` rather than
    living in the single per-root ``current.yaml`` field.

Not in Slice 1 (Slice 2+): checkpoint auto-proposals for active threads,
conversational-offer narrowing, sediment (durable recall), and externals.
"""

from __future__ import annotations

import os
import platform
import re
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - deployed turtleOS has PyYAML
    yaml = None

CURRENT_SCHEMA_VERSION = 1
ALIVE_SCHEMA_VERSION = 1
SCOPES_SCHEMA_VERSION = 1
DEFAULT_STALE_MINUTES = 15
MAX_ALIVE_HEADERS = 5

_SUBSTRATE_HEADER = "[Practice substrate — shell-injected, not a practitioner message]"
_CONDUCT_CURRENT = (
    "Stay oriented in time and place; surface these only when they serve "
    "the reply, never as a recital."
)
_CONDUCT_FULL = (
    "Stay oriented; surface time, place, or what's in motion only when they "
    "serve the reply — never as a recital, never naming internal layers."
)


# ─── Derivations (pure) ──────────────────────────────────────────────


def _day_part(hour: int) -> str:
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 21:
        return "evening"
    return "night"


def _season(month: int, southern: bool = False) -> str:
    """Meteorological season. Northern hemisphere by default; flip for southern."""
    northern = {
        12: "winter", 1: "winter", 2: "winter",
        3: "spring", 4: "spring", 5: "spring",
        6: "summer", 7: "summer", 8: "summer",
        9: "autumn", 10: "autumn", 11: "autumn",
    }
    season = northern[month]
    if southern:
        flip = {"winter": "summer", "summer": "winter",
                "spring": "autumn", "autumn": "spring"}
        season = flip[season]
    return season


def _inference_locality(dialogue_model: str, use_api: bool) -> str:
    if use_api:
        return "cloud"
    if dialogue_model.startswith("claude") or dialogue_model.startswith("gemini"):
        return "cloud"
    return "local"


def _host_label() -> str:
    """Live-read the running machine. ``CE_HOST_LABEL`` overrides with a friendly
    name (e.g. "Mac Mini M4 Pro"); otherwise the label reflects the actual host,
    never a hard-coded string that could lie about where Turtle is running."""
    override = os.environ.get("CE_HOST_LABEL", "").strip()
    if override:
        return override
    node = platform.node() or "unknown-host"
    tail = " ".join(p for p in (platform.system(), platform.machine()) if p)
    return f"{node} ({tail})" if tail else node


def _river_model_default() -> str:
    try:
        from models import RIVER_MODEL

        return RIVER_MODEL
    except Exception:
        return os.environ.get("RIVER_MODEL", "")


# ─── Compose (pure — no file I/O) ────────────────────────────────────


def compose_current(
    *,
    dialogue_model: str | None = None,
    river_model: str | None = None,
    use_api: bool = False,
    host_label: str | None = None,
    now: datetime | None = None,
    southern_hemisphere: bool | None = None,
) -> dict[str, Any]:
    """Compose the current-layer dict from live signals.

    ``dialogue_model`` should be the model that will actually answer this turn
    (the shell resolves it per-eddy), so the substrate reflects reality rather
    than a static default.
    """
    now = now or datetime.now().astimezone()
    tzname = getattr(now.tzinfo, "key", None) or now.tzname() or "local"
    dm = dialogue_model if dialogue_model is not None else os.environ.get("TURTLE_MODEL", "")
    rm = river_model if river_model is not None else _river_model_default()
    if southern_hemisphere is None:
        southern = os.environ.get("CE_SOUTHERN_HEMISPHERE", "").strip().lower() in (
            "1", "true", "yes",
        )
    else:
        southern = bool(southern_hemisphere)

    return {
        "version": CURRENT_SCHEMA_VERSION,
        "updated_at": now.isoformat(timespec="seconds"),
        "local": {
            "timezone": tzname,
            "weekday": now.strftime("%A"),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M"),
            "day_part": _day_part(now.hour),
            "season": _season(now.month, southern=southern),
        },
        "machine": {
            "host_label": host_label or _host_label(),
            "inference": _inference_locality(dm, use_api),
            "dialogue_model": dm,
            "river_model": rm,
        },
        # Slice 1+ fields (scope, alive headers, last-checkpoint one-liner) are
        # intentionally absent in Slice 0.
        "scope": None,
    }


def _when_line(local: dict[str, Any]) -> str:
    when = " ".join(p for p in (local.get("weekday", ""), local.get("day_part", "")) if p)
    when = when or "now"
    date = local.get("date", "")
    tz = local.get("timezone", "")
    season = local.get("season", "")
    line = when
    if date:
        line += f", {date}"
    if tz:
        line += f" ({tz})"
    if season:
        line += f" · {season}"
    return line


def _run_line(machine: dict[str, Any]) -> str:
    dm = machine.get("dialogue_model", "")
    host = machine.get("host_label", "")
    locality = "Local" if machine.get("inference") == "local" else "Cloud"
    line = f"{locality} inference"
    if dm:
        line += f": {dm}"
    if host:
        line += f" on {host}"
    return line


def render_current_block(data: dict[str, Any]) -> str:
    """Render the Slice 0 current-layer inject block (vocabulary firewall §4).

    Mirrors the design's prose example (§7.1): a labelled, non-practitioner
    block with a when-line and a machine-line, plus a one-line conduct nudge.
    Kept output-stable for callers that only want the current layer; the fuller
    packet (alive headers + scope) is composed by :func:`render_substrate_block`.
    """
    local = data.get("local", {})
    machine = data.get("machine", {})
    return (
        f"{_SUBSTRATE_HEADER}\n"
        f"{_when_line(local)}. {_run_line(machine)}.\n"
        f"{_CONDUCT_CURRENT}\n\n"
    )


# ─── Persistence (best-effort) ───────────────────────────────────────


def current_yaml_path(practice_dir: str | os.PathLike) -> Path:
    return Path(practice_dir) / "state" / "current.yaml"


def write_current(practice_dir: str | os.PathLike, data: dict[str, Any]) -> Path:
    if yaml is None:
        raise RuntimeError("PyYAML is required to write current.yaml")
    path = current_yaml_path(practice_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def read_current(practice_dir: str | os.PathLike) -> dict[str, Any] | None:
    path = current_yaml_path(practice_dir)
    if not path.exists() or yaml is None:
        return None
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return loaded if isinstance(loaded, dict) else None


def _age_minutes(data: dict[str, Any] | None, now: datetime | None = None) -> float | None:
    ts = (data or {}).get("updated_at")
    if not ts:
        return None
    try:
        parsed = datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None
    now = now or datetime.now().astimezone()
    if parsed.tzinfo is None:
        now = now.replace(tzinfo=None)
    return (now - parsed).total_seconds() / 60.0


def is_stale(
    data: dict[str, Any] | None,
    max_age_minutes: float = DEFAULT_STALE_MINUTES,
    now: datetime | None = None,
) -> bool:
    age = _age_minutes(data, now=now)
    return age is None or age >= max_age_minutes


# ─── Shell entry point ───────────────────────────────────────────────


def _persist_current_if_stale(
    practice_dir: str | os.PathLike,
    data: dict[str, Any],
    stale_minutes: float,
) -> None:
    """Debounced best-effort write: only when current.yaml is missing/stale."""
    try:
        existing = read_current(practice_dir)
        if existing is None or is_stale(existing, max_age_minutes=stale_minutes):
            write_current(practice_dir, data)
    except Exception as exc:  # persistence is best-effort; the inject still works
        print(f"CE current.yaml write skipped: {type(exc).__name__}: {exc}")


def refresh_and_render(
    practice_dir: str | os.PathLike,
    *,
    dialogue_model: str | None = None,
    river_model: str | None = None,
    use_api: bool = False,
    host_label: str | None = None,
    stale_minutes: float = DEFAULT_STALE_MINUTES,
) -> str:
    """Compose fresh current data, persist it when missing/stale, return the
    Slice 0 current-layer block only.

    The returned block is always freshly composed, so injected time is always
    accurate; the on-disk file write is debounced (only when missing or older
    than ``stale_minutes``) to avoid churn on every dialogue turn (design §8:
    "re-compose current if stale >15 min"). For the full packet (alive headers +
    scope), callers should use :func:`render_substrate_packet`.
    """
    data = compose_current(
        dialogue_model=dialogue_model,
        river_model=river_model,
        use_api=use_api,
        host_label=host_label,
    )
    _persist_current_if_stale(practice_dir, data, stale_minutes)
    return render_current_block(data)


# ─── Alive layer (active threads) ────────────────────────────────────


def alive_yaml_path(practice_dir: str | os.PathLike) -> Path:
    return Path(practice_dir) / "state" / "alive.yaml"


def _empty_alive(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now().astimezone()
    return {
        "version": ALIVE_SCHEMA_VERSION,
        "updated_at": now.isoformat(timespec="seconds"),
        "active_threads": [],
        "intention_snapshot": [],
    }


def read_alive(practice_dir: str | os.PathLike) -> dict[str, Any] | None:
    path = alive_yaml_path(practice_dir)
    if not path.exists() or yaml is None:
        return None
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return loaded if isinstance(loaded, dict) else None


def write_alive(practice_dir: str | os.PathLike, data: dict[str, Any]) -> Path:
    if yaml is None:
        raise RuntimeError("PyYAML is required to write alive.yaml")
    path = alive_yaml_path(practice_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def _slug(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", label.strip().lower()).strip("-")
    return slug or "thread"


def list_active_threads(practice_dir: str | os.PathLike) -> list[dict[str, Any]]:
    data = read_alive(practice_dir) or {}
    threads = data.get("active_threads")
    return list(threads) if isinstance(threads, list) else []


def find_active_thread(
    practice_dir: str | os.PathLike, query: str
) -> dict[str, Any] | None:
    """Resolve a thread by exact id, then id/label substring (case-insensitive)."""
    q = (query or "").strip().lower()
    if not q:
        return None
    threads = list_active_threads(practice_dir)
    for t in threads:
        if str(t.get("id", "")).lower() == q:
            return t
    for t in threads:
        hay = f"{t.get('id', '')} {t.get('label', '')}".lower()
        if q in hay:
            return t
    return None


def add_active_thread(
    practice_dir: str | os.PathLike,
    label: str,
    *,
    tone: str = "active",
    thread_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Add (or refresh) an active thread. Idempotent on id; returns the thread."""
    now = now or datetime.now().astimezone()
    data = read_alive(practice_dir) or _empty_alive(now)
    threads = data.setdefault("active_threads", [])
    tid = thread_id or _slug(label)
    for t in threads:
        if str(t.get("id")) == tid:
            t["label"] = label or t.get("label", tid)
            t["tone"] = tone
            t["since"] = t.get("since") or now.strftime("%Y-%m-%d")
            data["updated_at"] = now.isoformat(timespec="seconds")
            write_alive(practice_dir, data)
            return t
    thread = {
        "id": tid,
        "label": label or tid,
        "since": now.strftime("%Y-%m-%d"),
        "tone": tone,
    }
    threads.append(thread)
    data["updated_at"] = now.isoformat(timespec="seconds")
    write_alive(practice_dir, data)
    return thread


def remove_active_thread(practice_dir: str | os.PathLike, thread_id: str) -> bool:
    data = read_alive(practice_dir)
    if not data:
        return False
    threads = data.get("active_threads") or []
    kept = [t for t in threads if str(t.get("id")) != str(thread_id)]
    if len(kept) == len(threads):
        return False
    data["active_threads"] = kept
    data["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    write_alive(practice_dir, data)
    return True


# ─── Scope store (per-eddy, cross-process) ───────────────────────────


def scopes_yaml_path(practice_dir: str | os.PathLike) -> Path:
    return Path(practice_dir) / "state" / "scopes.yaml"


def read_scopes(practice_dir: str | os.PathLike) -> dict[str, Any]:
    path = scopes_yaml_path(practice_dir)
    if not path.exists() or yaml is None:
        return {"version": SCOPES_SCHEMA_VERSION, "eddies": {}}
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        loaded = None
    if not isinstance(loaded, dict):
        return {"version": SCOPES_SCHEMA_VERSION, "eddies": {}}
    loaded.setdefault("eddies", {})
    return loaded


def _write_scopes(practice_dir: str | os.PathLike, data: dict[str, Any]) -> Path:
    if yaml is None:
        raise RuntimeError("PyYAML is required to write scopes.yaml")
    path = scopes_yaml_path(practice_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def get_scope(practice_dir: str | os.PathLike, channel_id: str | int) -> str | None:
    eddies = read_scopes(practice_dir).get("eddies", {})
    entry = eddies.get(str(channel_id))
    if isinstance(entry, dict):
        return entry.get("thread")
    return entry if isinstance(entry, str) else None


def set_scope(
    practice_dir: str | os.PathLike,
    channel_id: str | int,
    thread_id: str,
    now: datetime | None = None,
) -> None:
    now = now or datetime.now().astimezone()
    data = read_scopes(practice_dir)
    data["eddies"][str(channel_id)] = {
        "thread": thread_id,
        "set_at": now.isoformat(timespec="seconds"),
    }
    _write_scopes(practice_dir, data)


def clear_scope(practice_dir: str | os.PathLike, channel_id: str | int) -> bool:
    data = read_scopes(practice_dir)
    if str(channel_id) in data["eddies"]:
        del data["eddies"][str(channel_id)]
        _write_scopes(practice_dir, data)
        return True
    return False


# ─── Checkpoint one-liner (written by checkpoint; read into packet) ──


def set_last_checkpoint(
    practice_dir: str | os.PathLike, one_liner: str, now: datetime | None = None
) -> None:
    """Persist a plain-language checkpoint one-liner into current.yaml so the
    next eddy's packet can carry "where we left off" (§7.1 line 4)."""
    text = (one_liner or "").strip()
    if not text:
        return
    data = read_current(practice_dir)
    if data is None:
        data = compose_current()
    data["last_checkpoint_one_liner"] = text
    if now is not None:
        data["updated_at"] = now.isoformat(timespec="seconds")
    write_current(practice_dir, data)


# ─── Renderers (alive headers + scoped self-feed) ────────────────────


def render_alive_headers(
    alive: dict[str, Any] | None, max_threads: int = MAX_ALIVE_HEADERS
) -> str:
    """Plain-language "In motion:" line + optional intention line.

    Headers only (§7.1 composition order 2–3). Firewall: "in motion," never
    "active threads"/"knots"; "intention" is a practitioner-legible word.
    """
    if not alive:
        return ""
    lines: list[str] = []
    threads = [t for t in (alive.get("active_threads") or []) if t.get("label")]
    if threads:
        parts = []
        for i, t in enumerate(threads[:max_threads], start=1):
            tone = t.get("tone")
            label = t["label"]
            parts.append(f"({i}) {label} — {tone}" if tone else f"({i}) {label}")
        lines.append("In motion: " + "; ".join(parts) + ".")
    intentions = [i for i in (alive.get("intention_snapshot") or []) if i.get("name")]
    if intentions:
        chunks = []
        for i in intentions:
            focus = i.get("current_focus") or i.get("phase")
            chunks.append(f"{i['name']} — {focus}" if focus else i["name"])
        lines.append("Intention: " + "; ".join(chunks) + ".")
    return "\n".join(lines)


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4 :]
    return text.lstrip()


def _scope_keywords(thread: dict[str, Any]) -> list[str]:
    raw = f"{thread.get('id', '')} {thread.get('label', '')}"
    words = re.split(r"[^a-z0-9]+", raw.lower())
    return sorted({w for w in words if len(w) >= 4})


def render_scope_block(
    practice_dir: str | os.PathLike,
    thread: dict[str, Any] | None,
    *,
    max_notes: int = 3,
    excerpt_chars: int = 320,
) -> str:
    """Scoped self-feed (§7.2): pull session notes matching the focused thread.

    Deterministic keyword/substring match over ``sessions/*.md`` (the documented
    v1 resolution; semantic is v2). Honest when thin (§12.6): if nothing matches,
    say so rather than fabricate. Firewall: "Focused on …", no layer names.
    """
    if not thread:
        return ""
    label = thread.get("label") or thread.get("id") or "this"
    sessions_dir = Path(practice_dir) / "sessions"
    keywords = _scope_keywords(thread)
    scored: list[tuple[int, float, str, str]] = []
    if keywords and sessions_dir.is_dir():
        for path in sessions_dir.glob("*.md"):
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            hay = (path.name + "\n" + content).lower()
            score = sum(hay.count(kw) for kw in keywords)
            if score > 0:
                mtime = path.stat().st_mtime
                scored.append((score, mtime, path.stem, content))
    if not scored:
        return (
            f'Focused on "{label}" right now — no saved notes match this yet; '
            "say what you actually recall or ask the practitioner, don't invent.\n"
        )
    scored.sort(key=lambda s: (s[0], s[1]), reverse=True)
    lines = [f'Focused on "{label}" right now — deeper context:']
    for _score, _mtime, stem, content in scored[:max_notes]:
        body = _strip_frontmatter(content)
        excerpt = " ".join(body.split())[:excerpt_chars].rstrip()
        lines.append(f"- {stem}: {excerpt}")
    return "\n".join(lines) + "\n"


def render_substrate_block(
    current_data: dict[str, Any],
    alive: dict[str, Any] | None = None,
    scope_block: str = "",
) -> str:
    """Compose the single holistic packet block (§7.1): current + alive headers
    + intention + last-checkpoint one-liner + conduct, then any scoped self-feed.
    """
    local = current_data.get("local", {})
    machine = current_data.get("machine", {})
    lines = [_SUBSTRATE_HEADER, f"{_when_line(local)}. {_run_line(machine)}."]

    headers = render_alive_headers(alive)
    if headers:
        lines.extend(headers.split("\n"))

    checkpoint = (current_data.get("last_checkpoint_one_liner") or "").strip()
    if checkpoint:
        lines.append(f"Last checkpoint: {checkpoint}")

    lines.append(_CONDUCT_FULL if headers else _CONDUCT_CURRENT)
    block = "\n".join(lines) + "\n\n"
    if scope_block:
        block += scope_block + "\n"
    return block


def render_substrate_packet(
    practice_dir: str | os.PathLike,
    *,
    dialogue_model: str | None = None,
    river_model: str | None = None,
    use_api: bool = False,
    host_label: str | None = None,
    scope: str | None = None,
    stale_minutes: float = DEFAULT_STALE_MINUTES,
) -> str:
    """Seam entry for the shell: freshly compose the current layer, fold in the
    alive headers and (if ``scope`` is set) the scoped self-feed, return the
    single inject block.

    ``scope`` is a thread id (resolved from ``scopes.yaml`` by the caller). Time
    is always fresh; the current.yaml write is debounced; the persisted
    checkpoint one-liner is carried forward so it survives the rewrite.
    """
    data = compose_current(
        dialogue_model=dialogue_model,
        river_model=river_model,
        use_api=use_api,
        host_label=host_label,
    )
    persisted = read_current(practice_dir) or {}
    if persisted.get("last_checkpoint_one_liner"):
        data["last_checkpoint_one_liner"] = persisted["last_checkpoint_one_liner"]
    _persist_current_if_stale(practice_dir, data, stale_minutes)

    alive = read_alive(practice_dir)
    scope_block = ""
    if scope:
        thread = find_active_thread(practice_dir, scope)
        scope_block = render_scope_block(practice_dir, thread)
    return render_substrate_block(data, alive, scope_block)


def _main(argv: list[str]) -> int:
    practice_dir = argv[1] if len(argv) > 1 else os.environ.get("PRACTICE_DIR", ".")
    data = compose_current()
    if yaml is not None:
        print("# composed current.yaml:")
        print(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
    print("# rendered inject block:")
    print(render_current_block(data))
    if "--write" in argv[2:]:
        print(f"# wrote {write_current(practice_dir, data)}")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(_main(sys.argv))
