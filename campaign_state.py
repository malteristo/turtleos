"""Event-backed asynchronous campaign state for team member lanes."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from core.atomic_io import atomic_write_json, atomic_write_text, file_lock
from governed_state import append_jsonl
from team_federation import record_activity_event
from thread_registry import get_thread_team_lane


def record_turn(
    practice_dir: str | Path,
    *,
    primitive,
    actor: str,
    thread_id: str | int,
    player_text: str,
    turtle_text: str,
    scene_boundary: str | None = None,
    semantic_reducer: Callable[[dict, dict], dict] | None = None,
) -> dict:
    """Persist raw exchange first, then reduce it into disposable views.

    A reducer failure is itself recorded and never removes the source exchange.
    """
    lane = get_thread_team_lane(thread_id)
    if lane is None:
        raise ValueError("campaign turn needs a registered member lane")
    if lane.get("lane_owner") != actor:
        raise PermissionError("only the lane owner can record a campaign turn")
    if primitive is None or not primitive.has("member_lanes"):
        raise PermissionError("campaign lane capability is unavailable")
    root = Path(practice_dir)
    activity_id = str(lane["activity_id"])
    now = _now()
    event = {
        "schema": 1,
        "kind": "campaign_turn",
        "activity_id": activity_id,
        "lane_id": str(thread_id),
        "actor": actor,
        "character": lane.get("lane_character"),
        "player_text": str(player_text or "").strip(),
        "turtle_text": str(turtle_text or "").strip(),
        "scene_boundary": str(scene_boundary or "").strip() or None,
        "at": now,
    }
    event["event_id"] = _event_id(event)
    with file_lock(root / "campaign" / "transaction"):
        append_jsonl(root, "campaign/events.jsonl", event)
        state = _read_state(root)
        state = _reduce_raw_turn(state, event)
        reducer_status = "deterministic"
        if semantic_reducer is not None:
            try:
                state = semantic_reducer(dict(state), dict(event))
                reducer_status = "semantic"
            except Exception as exc:
                reducer_status = "pending"
                append_jsonl(
                    root,
                    "campaign/reducer-failures.jsonl",
                    {
                        "event_id": event["event_id"],
                        "at": _now(),
                        "error": f"{type(exc).__name__}: {exc}",
                    },
                )
        state["last_reducer_status"] = reducer_status
        _write_views(root, state)
    summary = _summary(event)
    activity_event = record_activity_event(
        root,
        primitive=primitive,
        actor=actor,
        activity_id=activity_id,
        lane_id=thread_id,
        summary=summary,
        event_kind="campaign_turn",
        source_eddy=thread_id,
        payload={"campaign_event_id": event["event_id"]},
    )
    return {
        "event": event,
        "activity_event": activity_event,
        "state": state,
        "reducer_status": reducer_status,
    }


def seed_from_prologue(
    practice_dir: str | Path,
    *,
    primitive,
    activity_id: str,
    source_thread_id: str | int,
    checkpoint_text: str,
    world: str,
    current_scene: str,
    member_states: dict[str, str],
) -> dict:
    """Preserve the old table as source and derive explicit initial views."""
    root = Path(practice_dir)
    if primitive is None or not primitive.has("shared_work"):
        raise PermissionError("team campaign state is unavailable")
    unknown = set(member_states) - set(primitive.members)
    if unknown:
        raise PermissionError(
            f"member state contains non-team member(s): {', '.join(sorted(unknown))}"
        )
    source = root / "campaign" / "prologue" / f"{source_thread_id}.md"
    checkpoint_text = str(checkpoint_text or "")
    if source.exists() and source.read_text(encoding="utf-8") != checkpoint_text:
        raise FileExistsError("prologue source already exists with different content")
    for existing in _read_events(root):
        if (
            existing.get("kind") == "campaign_migration"
            and existing.get("activity_id") == str(activity_id)
            and existing.get("source_thread_id") == str(source_thread_id)
        ):
            return {
                "source": str(source),
                "event": existing,
                "state": rebuild_views(root),
            }
    atomic_write_text(source, checkpoint_text)
    event = {
        "schema": 1,
        "kind": "campaign_migration",
        "activity_id": str(activity_id),
        "source_thread_id": str(source_thread_id),
        "source": str(source.relative_to(root)),
        "world": str(world or "").strip(),
        "current_scene": str(current_scene or "").strip(),
        "member_states": {
            member: str(text or "").strip()
            for member, text in member_states.items()
        },
        "at": _now(),
    }
    event["event_id"] = _event_id(event)
    with file_lock(root / "campaign" / "transaction"):
        append_jsonl(root, "campaign/events.jsonl", event)
        state = _reduce_migration(event)
        state["event_count"] = len(_read_events(root))
        _write_views(root, state)
    return {"source": str(source), "event": event, "state": state}


def render_context(
    practice_dir: str | Path,
    *,
    thread_id: str | int,
    actor: str | None,
) -> str:
    """Load shared world plus only the current member's character state."""
    lane = get_thread_team_lane(thread_id)
    if lane is None or actor != lane.get("lane_owner"):
        return ""
    state = _read_state(Path(practice_dir))
    if not state:
        return (
            "## Campaign State\n"
            "- No authoritative campaign state exists yet. Preserve the player's "
            "turn as an event; do not invent a lost history."
        )
    member = (state.get("members") or {}).get(actor) or {}
    lines = [
        "## Authoritative Campaign State",
        f"- **World:** {state.get('world') or 'Not yet reduced.'}",
        f"- **Current scene:** {state.get('current_scene') or 'Not yet reduced.'}",
        f"- **Your character state:** {member.get('state') or 'No private character state recorded.'}",
        f"- **Last durable event:** {state.get('last_event_id') or 'none'}",
        "- Advance this lane independently. Use unseen sibling developments only "
        "when they matter here; narrate the effect in-world rather than announcing a sync.",
        "- Never reveal another member's character-knowledge file.",
    ]
    return "\n".join(lines)


_SCENE_BOUNDARY_RE = re.compile(
    r"\s*\[\[campaign-scene:\s*(.+?)\s*\]\]\s*$",
    re.IGNORECASE | re.DOTALL,
)


def extract_scene_boundary(reply: str) -> tuple[str, str | None]:
    """Strip the flow's hidden scene-boundary declaration from Discord prose."""
    match = _SCENE_BOUNDARY_RE.search(str(reply or ""))
    if not match:
        return str(reply or ""), None
    summary = " ".join(match.group(1).split()).strip()[:1200]
    return str(reply or "")[: match.start()].rstrip(), summary or None


def rebuild_views(practice_dir: str | Path) -> dict:
    """Rebuild deterministic campaign views from the source event stream."""
    root = Path(practice_dir)
    state: dict = {}
    for event in _read_events(root):
        if event.get("kind") == "campaign_migration":
            state = _reduce_migration(event)
        elif event.get("kind") == "campaign_turn":
            state = _reduce_raw_turn(state, event)
    if state:
        state["event_count"] = len(_read_events(root))
        _write_views(root, state)
    return state


def _reduce_raw_turn(state: dict, event: dict) -> dict:
    state = dict(state or {})
    members = {
        str(key): dict(value)
        for key, value in (state.get("members") or {}).items()
    }
    actor = str(event["actor"])
    member = members.get(actor, {"member": actor})
    member.update(
        {
            "last_action": event.get("player_text"),
            "last_narration": event.get("turtle_text"),
            "last_event_id": event.get("event_id"),
            "updated_at": event.get("at"),
        }
    )
    members[actor] = member
    state.update(
        {
            "schema": 1,
            "activity_id": event.get("activity_id"),
            "members": members,
            "current_scene": (
                event.get("scene_boundary") or event.get("turtle_text")
            ),
            "last_event_id": event.get("event_id"),
            "last_event_at": event.get("at"),
            "event_count": int(state.get("event_count") or 0) + 1,
        }
    )
    return state


def _reduce_migration(event: dict) -> dict:
    source = str(event.get("source") or "")
    return {
        "schema": 1,
        "activity_id": event.get("activity_id"),
        "world": event.get("world") or "",
        "current_scene": event.get("current_scene") or "",
        "source": source,
        "members": {
            member: {
                "member": member,
                "state": text,
                "source": source,
                "last_event_id": event.get("event_id"),
            }
            for member, text in (event.get("member_states") or {}).items()
        },
        "last_event_id": event.get("event_id"),
        "last_event_at": event.get("at"),
        "last_reducer_status": "migration",
        "event_count": 1,
    }


def _write_views(root: Path, state: dict) -> None:
    atomic_write_json(root / "campaign" / "state.json", state, indent=2)
    source = state.get("source") or "campaign/events.jsonl"
    world = state.get("world") or "*Not yet reduced.*"
    scene = state.get("current_scene") or "*Not yet reduced.*"
    atomic_write_text(
        root / "campaign" / "world.md",
        f"# Campaign world\n\n{world}\n\n_Source: {source}_\n",
    )
    atomic_write_text(
        root / "campaign" / "current_scene.md",
        f"# Current scene\n\n{scene}\n\n"
        f"_Last durable event: {state.get('last_event_id') or 'none'}_\n",
    )
    for member, row in (state.get("members") or {}).items():
        body = row.get("state") or row.get("last_narration") or "*No state yet.*"
        atomic_write_text(
            root / "campaign" / "player_state" / f"{member}.md",
            f"# {member} — campaign state\n\n{body}\n\n"
            f"_Last durable event: {row.get('last_event_id') or 'none'}_\n",
        )
    latest = (
        "# Campaign checkpoint\n\n"
        f"**Activity:** {state.get('activity_id') or 'unknown'}\n"
        f"**Last event:** {state.get('last_event_id') or 'none'}\n"
        f"**Reducer:** {state.get('last_reducer_status') or 'deterministic'}\n\n"
        f"{scene}\n"
    )
    atomic_write_text(root / "campaign" / "checkpoints" / "latest.md", latest)


def _read_state(root: Path) -> dict:
    path = root / "campaign" / "state.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _read_events(root: Path) -> list[dict]:
    path = root / "campaign" / "events.jsonl"
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
        except json.JSONDecodeError:
            continue
    return rows


def _summary(event: dict) -> str:
    player = " ".join(str(event.get("player_text") or "").split())
    turtle = " ".join(str(event.get("turtle_text") or "").split())
    return f"{player[:500]} → {turtle[:900]}".strip(" →")


def _event_id(event: dict) -> str:
    canonical = json.dumps(event, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
