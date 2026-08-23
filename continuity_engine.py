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

Slice 2 (checkpoint theme proposals): see ``continuity_confirm.py`` +
``story_notes`` ``PROPOSED-THEMES`` — plain-language Keep these
before ``add_active_thread``; ``set_last_checkpoint`` wired from eddy-note
preview. Not yet: stale demotion, conversational-offer narrowing, sediment,
externals.
"""

from __future__ import annotations

import os
import platform
import re
from datetime import date, datetime
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
# Past this, the carried checkpoint line has stopped pointing at anything.
CHECKPOINT_CARRY_MAX_AGE_DAYS = 30

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
        from core.models import RIVER_MODEL

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


# ─── Decay ───────────────────────────────────────────────────────────
#
# The alive layer had no decay because it had no automatic writer: every entry
# arrived by a practitioner pressing Keep, so every entry was assumed to mean
# something until removed by hand. Nobody ever removed one, and the layer went
# on reciting 17 July into every turn for the next three weeks.
#
# Once themes are promoted automatically the arithmetic inverts — roughly three
# per checkpoint — so decay is not a refinement here, it is the other half of
# the mechanism. A thread survives by being talked about again.
#
# Inferred threads are cheap and are meant to fall away; a confirmed one was
# deliberate and is given a long grace period, because "keep this in mind"
# should not need repeating every week to hold.
INFERRED_THREAD_TTL_DAYS = 7
CONFIRMED_THREAD_TTL_DAYS = 30
MAX_ACTIVE_THREADS = 7

# How many first-seen dates to remember for themes no longer on the shelf.
# A theme that falls off and comes back should say when the practitioner first
# raised it, not when it happened to resurface — "in motion since March" is
# what a person means by a live thread, and the alternative told them
# everything started this morning. The list of live threads is capped at 7 and
# turns over quickly; the origins outlive it deliberately, so the cap here is
# generous and the cost is a few hundred bytes of dates.
MAX_THREAD_ORIGINS = 200


def _remember_origin(data: dict[str, Any], tid: str, since: str) -> None:
    """Record when a theme was first raised, and keep the earliest answer.

    Never overwritten by a later date: the point of the record is the first
    one. Trimmed oldest-first when it outgrows its cap, which discards the
    origins least likely to be asked for again — a theme dormant since March
    is the one that has already survived longest without returning.
    """
    origins = data.setdefault("thread_origins", {})
    if not isinstance(origins, dict):
        origins = {}
        data["thread_origins"] = origins
    if not tid or not since:
        return
    kept = str(origins.get(tid) or "")
    if not kept or since < kept:
        origins[tid] = since
    if len(origins) > MAX_THREAD_ORIGINS:
        for stale, _ in sorted(origins.items(), key=lambda kv: str(kv[1]))[
            : len(origins) - MAX_THREAD_ORIGINS
        ]:
            origins.pop(stale, None)


def _thread_last_seen(thread: dict[str, Any]) -> str:
    """Newest date this thread was reinforced; ``since`` for legacy entries."""
    return str(thread.get("last_seen") or thread.get("since") or "").strip()


def prune_threads(
    threads: list[dict[str, Any]], now: datetime | None = None
) -> list[dict[str, Any]]:
    """Drop threads nothing has touched inside their TTL, newest first.

    Applied on **read** as well as on write. A layer that only prunes when
    written stays frozen exactly when it is most wrong — when nothing is
    writing it — which is the failure this replaces.
    """
    now = now or datetime.now().astimezone()
    today = now.date()
    kept: list[tuple[str, dict[str, Any]]] = []
    for t in threads:
        if not isinstance(t, dict):
            continue
        stamp = _thread_last_seen(t)
        ttl = (
            CONFIRMED_THREAD_TTL_DAYS
            if t.get("source") == "confirmed" or t.get("confirmed_by")
            else INFERRED_THREAD_TTL_DAYS
        )
        if not stamp:
            # No date at all: keep it. An undated entry is unmeasurable, and
            # dropping it would be inventing an age rather than reading one.
            kept.append(("", t))
            continue
        try:
            seen = date.fromisoformat(stamp)
        except ValueError:
            kept.append(("", t))
            continue
        if (today - seen).days <= ttl:
            kept.append((stamp, t))
    kept.sort(key=lambda pair: pair[0], reverse=True)
    return [t for _, t in kept[:MAX_ACTIVE_THREADS]]


def read_alive(
    practice_dir: str | os.PathLike, now: datetime | None = None
) -> dict[str, Any] | None:
    """Read the alive layer, pruning against ``now`` (default: wall-clock).

    ``now`` exists because pruning on read is otherwise unreachable from a
    caller that has its own clock. ``add_active_thread`` takes a ``now`` and
    then read back a layer aged against the real calendar, so a caller
    reasoning about a past moment — a test with a frozen clock, a backfill
    replaying July — silently lost every thread older than its TTL *measured
    from today*. One function, two clocks, and the disagreement only showed up
    on the day the calendar crossed the fixture's TTL.
    """
    path = alive_yaml_path(practice_dir)
    if not path.exists() or yaml is None:
        return None
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(loaded, dict):
        return None
    threads = loaded.get("active_threads")
    if isinstance(threads, list):
        loaded["active_threads"] = prune_threads(threads, now)
    return loaded


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


def list_active_threads(
    practice_dir: str | os.PathLike, now: datetime | None = None
) -> list[dict[str, Any]]:
    data = read_alive(practice_dir, now) or {}
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
    confirmed_by: str | None = None,
    source: str = "confirmed",
) -> dict[str, Any]:
    """Add (or refresh) an active thread. Idempotent on id; returns the thread.

    ``confirmed_by`` is the practitioner address of whoever agreed to carry
    this. In a shared space it is what keeps a theme one member confirmed from
    being recited into the other's eddies as though it were the room's own —
    the witness law (charter §3.3) applied to structured state rather than
    prose. Preserved on refresh, like ``since``: the thread belongs to whoever
    first put it in motion.

    ``source`` separates what the practice *noticed* from what a member
    *chose*. Inferred threads arrive on their own and expire quickly;
    confirming one upgrades it in place and buys it the long TTL. The upgrade
    is one-way — a member's choice is never demoted by a later inference.

    Every call refreshes ``last_seen``: a thread stays alive by being talked
    about again, which is the whole decay contract.

    ``since`` survives the thread. Decay drops a theme nothing has touched
    inside its TTL, so a theme with a slower cadence than its TTL used to come
    back as a brand-new thread dated today — and ``!fresh``, which prints
    *since <date>*, told the practitioner that something they had circled for
    months began this morning. ``thread_origins`` remembers the first date and
    re-arrival restores it. (Mage's call, 2026-08-08: what "in motion" means to
    a person is when they first raised it.) ``last_seen`` is untouched by this
    and stays the honest decay clock — the pair now says *since March, last
    week* rather than collapsing both into one date.
    """
    now = now or datetime.now().astimezone()
    data = read_alive(practice_dir, now) or _empty_alive(now)
    threads = data.setdefault("active_threads", [])
    origins = data.setdefault("thread_origins", {})
    if not isinstance(origins, dict):
        origins = {}
        data["thread_origins"] = origins
    tid = thread_id or _slug(label)
    for t in threads:
        if str(t.get("id")) == tid:
            t["label"] = label or t.get("label", tid)
            t["tone"] = tone
            t["since"] = t.get("since") or origins.get(tid) or now.strftime("%Y-%m-%d")
            t["last_seen"] = now.strftime("%Y-%m-%d")
            if source == "confirmed" or t.get("source") == "confirmed":
                t["source"] = "confirmed"
            else:
                t.setdefault("source", source)
            if confirmed_by and not t.get("confirmed_by"):
                t["confirmed_by"] = confirmed_by
            _remember_origin(data, tid, t["since"])
            data["updated_at"] = now.isoformat(timespec="seconds")
            write_alive(practice_dir, data)
            return t
    since = origins.get(tid) or now.strftime("%Y-%m-%d")
    thread = {
        "id": tid,
        "label": label or tid,
        "since": since,
        "last_seen": now.strftime("%Y-%m-%d"),
        "source": source,
        "tone": tone,
    }
    if confirmed_by:
        thread["confirmed_by"] = confirmed_by
    threads.append(thread)
    data["active_threads"] = prune_threads(threads, now)
    _remember_origin(data, tid, since)
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


def _is_multi_member_root(practice_dir: str | os.PathLike) -> bool:
    """True when this root is a shared space with more than one member.

    Fails **closed** (True → suppress) if membership cannot be resolved: the
    ownership law this guard serves requires resolution failure to withhold,
    not to fall back on ambient context. A registry-less vanilla install
    resolves cleanly to ``[]`` and keeps single-practitioner behaviour.
    """
    try:
        from mage import space_members_for_practice_dir

        return len(space_members_for_practice_dir(practice_dir)) > 1
    except Exception as exc:  # pragma: no cover — registry/import failure
        print(
            f"Carry guard: membership unresolved for {practice_dir} "
            f"({type(exc).__name__}: {exc}) — suppressing, failing closed"
        )
        return True


def set_last_checkpoint(
    practice_dir: str | os.PathLike, one_liner: str, now: datetime | None = None
) -> None:
    """Persist a plain-language checkpoint one-liner into current.yaml so the
    next eddy's packet can carry "where we left off" (§7.1 line 4).

    **Suppressed in multi-member roots (INT-047).** This line is written on
    every idle checkpoint, unconfirmed and model-authored. In a shared space it
    is one member's last moment recited to everyone as though it were the
    room's — the same collapse as INT-040, in the state that shapes every turn
    rather than in one note. Nothing carries into a shared room unconfirmed;
    what a space carries is confirmed themes, attributed to whoever confirmed
    them. See ``docs/design/carried-context-and-the-confirm-moment.md``.
    """
    text = (one_liner or "").strip()
    if not text:
        return
    if _is_multi_member_root(practice_dir):
        return
    data = read_current(practice_dir)
    if data is None:
        data = compose_current()
    data["last_checkpoint_one_liner"] = text
    # Stamp the carry itself, not the file. ``updated_at`` tracks the current
    # layer's recomposition and is rewritten on a debounce, so it cannot say
    # how old "where we left off" is.
    data["last_checkpoint_at"] = (now or datetime.now().astimezone()).isoformat(
        timespec="seconds"
    )
    if now is not None:
        data["updated_at"] = now.isoformat(timespec="seconds")
    write_current(practice_dir, data)


def _checkpoint_age_phrase(
    stamped_at: Any, now: datetime | None = None
) -> str | None:
    """Qualifier for the carried checkpoint line — ``None`` means drop it.

    "Where we left off" is a claim about *recency*. Six days on it is not
    false that this is where you left off; it is false to present it as
    though you just did. So age it in the copy rather than deleting warmth
    the practitioner may want after a gap — and drop it only once it has
    stopped being a pointer to anything.

    An unstamped line (written before this field existed) renders unqualified:
    silence is better than a fabricated age.
    """
    if not stamped_at:
        return ""
    try:
        then = datetime.fromisoformat(str(stamped_at))
    except (TypeError, ValueError):
        return ""
    now = now or datetime.now().astimezone()
    if then.tzinfo is None:
        then = then.astimezone()
    hours = (now - then).total_seconds() / 3600.0
    if hours < 0:
        return ""
    if hours > CHECKPOINT_CARRY_MAX_AGE_DAYS * 24:
        return None
    if hours < 2:
        return ""
    if hours < 24:
        n = int(hours)
        return f" ({n} hour{'s' if n != 1 else ''} ago)"
    days = int(hours // 24)
    if days == 1:
        return " (yesterday)"
    return f" ({days} days ago)"


# ─── Renderers (alive headers + scoped self-feed) ────────────────────


def render_alive_headers(
    alive: dict[str, Any] | None,
    max_threads: int = MAX_ALIVE_HEADERS,
    *,
    attribute: bool = False,
) -> str:
    """Plain-language "In motion:" line + optional intention line.

    Headers only (§7.1 composition order 2–3). Firewall: "in motion," never
    "active threads"/"knots"; "intention" is a practitioner-legible word.

    ``attribute`` names who confirmed each thread — set for multi-member roots,
    where an unattributed theme reads to every member as the room's own. It
    renders as a name, not a field: "(1) the birthday plan — Ana, active".
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
            who = str(t.get("confirmed_by") or "").strip() if attribute else ""
            bits = [b for b in (who, tone) if b]
            parts.append(f"({i}) {label} — {', '.join(bits)}" if bits else f"({i}) {label}")
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


ROOM_MEMORY_DAYS = 7
ROOM_MEMORY_MAX_ENTRIES = 5
# How many notes the selection may choose *from*. Bounds the read, and is the
# candidate set the packet records — selection quality is only measurable
# against what was on offer.
ROOM_MEMORY_CANDIDATE_CAP = 40
ROOM_MEMORY_CHAR_BUDGET = 5000
_ROOM_MEMORY_EXCERPT_CHARS = 700


def render_scope_block(
    practice_dir: str | os.PathLike,
    thread: dict[str, Any] | None,
    *,
    current_thread: str | None = None,
    max_notes: int = ROOM_MEMORY_MAX_ENTRIES,
    excerpt_chars: int = _ROOM_MEMORY_EXCERPT_CHARS,
    considered: list[dict[str, Any]] | None = None,
) -> str:
    """What this room has been about lately — read from its own eddy notes.

    This used to read ``sessions/*.md``, a genre retired 2026-07-15, and only
    ran when a practitioner used ``!focus`` — which no practitioner has ever
    used, in any root. A working reader aimed at a dead corpus, switched off by
    default, while the live corpus accumulated beside it. It now reads the eddy
    notes and runs on every turn.

    Two scopes, one reader: with a focused thread, entries are keyword-scored
    against its label; without one, plain recency. Nothing is promoted, nothing
    becomes standing state — if it is not in the window it is not in the room
    (``docs/design/what-a-shared-room-remembers.md`` §4).

    Attribution is inherited, not recomputed: post-witness-fix notes already
    name who said what. Honest when thin (§12.6) — and honest about reach: the
    only notes readable from here are this root's own.

    ``considered`` collects **the road not taken**: one record per candidate in
    the window, marked with whether it reached the prompt. A packet that logs
    only what was carried cannot distinguish a good selection from a lucky one,
    and the candidate set is not reconstructible after the fact once selection
    stops being "the most recent five" — the same way retroactive packet
    reconstruction ended when the alive layer was repaired. It costs a list
    while the selection is happening and cannot be recovered later.
    """
    from story_notes import collect_recent_eddy_entries

    candidates = collect_recent_eddy_entries(
        practice_dir=Path(practice_dir),
        since_days=ROOM_MEMORY_DAYS,
        exclude_thread=current_thread,
        limit=ROOM_MEMORY_CANDIDATE_CAP,
    )

    label = (thread or {}).get("label") or (thread or {}).get("id") or ""
    scores: dict[int, int] = {}
    if thread and candidates:
        keywords = _scope_keywords(thread)
        if keywords:
            for entry in candidates:
                haystack = (
                    f"{entry.title} {' '.join(entry.proposed_themes)} {entry.body}"
                ).lower()
                scores[id(entry)] = sum(haystack.count(kw) for kw in keywords)
            candidates.sort(
                key=lambda e: (scores[id(e)], e.timestamp),
                reverse=True,
            )

    # The window, then the cut — not the cut, then the window. Scoring used to
    # run against an already-truncated list, so a focused thread could only
    # reorder the five most recent notes and could never reach a sixth that
    # actually matched. Ranking after truncation is ranking nothing.
    entries = candidates[:max_notes]

    records = [
        {
            "thread": entry.thread,
            "title": entry.title or "a conversation",
            "when": entry.timestamp.isoformat(timespec="minutes"),
            "score": scores.get(id(entry)),
            "selected": False,
        }
        for entry in candidates
    ]
    if considered is not None:
        considered.extend(records)

    if not entries:
        if label:
            return (
                f'Focused on "{label}" right now — nothing else in this space '
                "has touched it recently; say what you actually recall or ask, "
                "don't invent.\n"
            )
        return (
            "Nothing else in this space has been written down recently. Say "
            "what you actually recall or ask — and if you are asked about a "
            "conversation somewhere else, say you cannot see it rather than "
            "reconstructing it: the only notes readable from here are this "
            "space's own.\n"
        )

    header = (
        f'Focused on "{label}" right now — what else this space has been about:'
        if label
        else "What this space has been about recently:"
    )
    lines = [header]
    budget = ROOM_MEMORY_CHAR_BUDGET
    for index, entry in enumerate(entries):
        excerpt = " ".join(_strip_frontmatter(entry.body).split())[:excerpt_chars]
        excerpt = excerpt.rstrip()
        if not excerpt:
            continue
        day = entry.timestamp.strftime("%b %d")
        title = entry.title or "a conversation"
        themes = ", ".join(entry.proposed_themes[:3])
        line = f"- [{day}] {title}: {excerpt}"
        if themes:
            line += f" (threads: {themes})"
        if len(line) > budget:
            break
        lines.append(line)
        budget -= len(line)
        # Marked here rather than at selection: an entry can still be dropped
        # by an empty excerpt or the char budget, and the record has to say
        # what reached the prompt, not what was intended to.
        records[index]["selected"] = True

    if len(lines) == 1:
        return ""
    lines.append(
        "Surface these only when they serve the reply, never as a recital. "
        "They are this space's own notes and the only ones readable from here."
    )
    return "\n".join(lines) + "\n"


def render_substrate_block(
    current_data: dict[str, Any],
    alive: dict[str, Any] | None = None,
    scope_block: str = "",
    *,
    attribute_threads: bool = False,
) -> str:
    """Compose the single holistic packet block (§7.1): current + alive headers
    + intention + last-checkpoint one-liner + conduct, then any scoped self-feed.
    """
    local = current_data.get("local", {})
    machine = current_data.get("machine", {})
    lines = [_SUBSTRATE_HEADER, f"{_when_line(local)}. {_run_line(machine)}."]

    # The alive layer no longer speaks to a turn.
    #
    # `what-a-shared-room-remembers.md` §4 replaced curated carry with
    # retrieval, and §9 settled it: nothing retrieved becomes state; if it is
    # not in the window it is not in the room. Room memory answers "what has
    # been said here lately" from the root's own eddy notes, every turn, and
    # answers it better than a compressed header line ever did.
    #
    # What remained here was the last mouth of the superseded design, and it
    # was the whole of the layer's live cost: every axis-B false carry the
    # 2026-08-05 audit found reached a practitioner through this line, and
    # every recital of internal topic labels did too. Decay would have made it
    # merely honest; removing it makes it silent, which is what the design
    # already decided.
    #
    # The layer keeps being written — see `add_active_thread` — because
    # recurrence over weeks is the one thing a seven-day retrieval window
    # cannot compute, and it is what an intention is made of. Its readers are
    # the relation gate at note-writing time and the intention offer. Neither
    # is a turn.
    headers = ""

    checkpoint = (current_data.get("last_checkpoint_one_liner") or "").strip()
    if checkpoint:
        age = _checkpoint_age_phrase(current_data.get("last_checkpoint_at"))
        if age is not None:
            lines.append(f"Last checkpoint{age}: {checkpoint}")

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
    current_thread: str | None = None,
    stale_minutes: float = DEFAULT_STALE_MINUTES,
    considered: list[dict[str, Any]] | None = None,
) -> str:
    """Seam entry for the shell: freshly compose the current layer, fold in the
    alive headers and the room's recent memory, return the single inject block.

    Room memory is **unconditional**. It used to render only when ``scope`` was
    set — that is, only under ``!focus``, a command no practitioner has ever
    used. Remembering the room is the system's job, not a thing to ask for.
    ``scope`` now narrows what is already there rather than switching it on.

    ``current_thread`` is the eddy being spoken in; its own notes are excluded,
    since that conversation is already present as history.

    Time is always fresh; the current.yaml write is debounced; the persisted
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
        # Carry the stamp with the line, or the age qualifier silently resets
        # to "just now" on every recomposition.
        if persisted.get("last_checkpoint_at"):
            data["last_checkpoint_at"] = persisted["last_checkpoint_at"]
    _persist_current_if_stale(practice_dir, data, stale_minutes)

    alive = read_alive(practice_dir)
    thread = find_active_thread(practice_dir, scope) if scope else None
    scope_block = render_scope_block(
        practice_dir, thread, current_thread=current_thread, considered=considered
    )
    return render_substrate_block(
        data,
        alive,
        scope_block,
        attribute_threads=_is_multi_member_root(practice_dir),
    )


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
