"""Governed, attributed state for every shared-work channel.

The team preset owns policy; this module supplies the reusable mechanism.
Source events are append-only. ``team/current.json`` and ``team/current.md``
are disposable views rebuilt from that ledger.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.atomic_io import atomic_write_json, atomic_write_text, file_lock
from governed_state import (
    append_jsonl,
    create_proposal,
    pending_proposals as _pending_proposals,
    transact_proposal,
)


PROPOSABLE_KINDS = frozenset(
    {"horizon", "member_front", "commitment", "task", "decision"}
)
DIRECT_KINDS = frozenset({"contribution", "artifact", "intersection", "progress"})
FRONT_RELATIONS = frozenset({"advance", "explore", "support", "challenge", "paused"})
TERMINAL = frozenset({"applied", "rejected"})


def propose_change(
    practice_dir: str | Path,
    *,
    primitive,
    actor: str,
    kind: str,
    payload: dict,
    source_eddy: str | int | None = None,
    explicit: bool = False,
) -> dict:
    """Propose team state with confirmation scoped to the affected members."""
    _require_team_member(primitive, actor)
    kind = str(kind or "").strip()
    if kind not in PROPOSABLE_KINDS:
        raise ValueError(f"unsupported team proposal kind: {kind}")
    clean = _validate_payload(kind, payload, primitive.members, actor)
    required = _required_confirmers(kind, clean, primitive.members, actor)
    now = _now()
    proposal = create_proposal(
        practice_dir,
        "team",
        {
            "schema": 1,
            "primitive": primitive.name,
            "kind": kind,
            "actor": actor,
            "actor_role": primitive.role_for(actor),
            "payload": clean,
            "required_confirmers": required,
            "confirmations": [],
            "source_eddy": str(source_eddy) if source_eddy is not None else None,
            "created_at": now,
            "status": "pending",
        },
    )
    if explicit and required == [actor]:
        return decide_change(
            practice_dir,
            proposal["proposal_id"],
            primitive=primitive,
            actor=actor,
            decision="confirm",
        )
    return proposal


def decide_change(
    practice_dir: str | Path,
    proposal_id: str,
    *,
    primitive,
    actor: str,
    decision: str,
) -> dict:
    """Confirm or reject a proposal without speaking for another member."""
    _require_team_member(primitive, actor)
    if decision not in {"confirm", "reject"}:
        raise ValueError("decision must be confirm or reject")
    root = Path(practice_dir)

    def mutate(proposal: dict) -> dict:
        required = tuple(str(value) for value in proposal.get("required_confirmers") or ())
        if actor not in required:
            if decision == "reject" and actor == proposal.get("actor"):
                pass  # a proposer may withdraw their own still-pending proposal
            else:
                raise PermissionError("actor cannot decide this team proposal")
        if decision == "reject":
            proposal["status"] = "rejected"
            proposal["decided_by"] = actor
            proposal["decided_at"] = _now()
            return proposal

        confirmations = list(dict.fromkeys(proposal.get("confirmations") or []))
        if actor not in confirmations:
            confirmations.append(actor)
        proposal["confirmations"] = confirmations
        if set(required).issubset(confirmations):
            event = _proposal_event(proposal)
            append_jsonl(root, "team/events.jsonl", event)
            proposal["status"] = "applied"
            proposal["decided_by"] = confirmations
            proposal["decided_at"] = _now()
            rebuild_views(root)
        return proposal

    return transact_proposal(
        root,
        "team",
        proposal_id,
        mutate=mutate,
        status_key="status",
        terminal_statuses=TERMINAL,
        log_relative="team/changes.jsonl",
        log_event=_change_event,
    )


def record_event(
    practice_dir: str | Path,
    *,
    primitive,
    actor: str,
    kind: str,
    payload: dict,
    source_eddy: str | int | None = None,
) -> dict:
    """Record an explicit member contribution that grants no new authority."""
    _require_team_member(primitive, actor)
    kind = str(kind or "").strip()
    if kind not in DIRECT_KINDS:
        raise ValueError(f"unsupported direct team event kind: {kind}")
    now = _now()
    event = {
        "schema": 1,
        "kind": kind,
        "actor": actor,
        "actor_role": primitive.role_for(actor),
        "payload": dict(payload or {}),
        "source_eddy": str(source_eddy) if source_eddy is not None else None,
        "at": now,
    }
    event["event_id"] = _content_id(event)
    append_jsonl(Path(practice_dir), "team/events.jsonl", event)
    return {"event": event, "state": rebuild_views(practice_dir)}


def pending_proposals(practice_dir: str | Path) -> list[dict]:
    return _pending_proposals(practice_dir, "team", status_key="status")


def rebuild_views(practice_dir: str | Path) -> dict:
    """Rebuild the current JSON and Markdown views from attributed source events."""
    root = Path(practice_dir)
    with file_lock(root / "team" / "rebuild"):
        events = _read_events(root)
        state = _empty_state()
        seen: set[str] = set()
        for event in events:
            event_id = str(event.get("event_id") or "")
            if event_id and event_id in seen:
                continue
            if event_id:
                seen.add(event_id)
            _reduce(state, event)
        state["event_count"] = len(seen)
        state["rebuilt_at"] = _now()
        atomic_write_json(root / "team" / "current.json", state, indent=2)
        atomic_write_text(root / "team" / "current.md", render_state(state))
        return state


def read_state(practice_dir: str | Path) -> dict:
    path = Path(practice_dir) / "team" / "current.json"
    if not path.is_file():
        return rebuild_views(practice_dir)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return rebuild_views(practice_dir)


def render_context(practice_dir: str | Path, actor: str | None = None) -> str:
    """Bounded turn-time team context; never reads a member's private root."""
    state = read_state(practice_dir)
    lines = ["## Shared Team State"]
    horizon = state.get("horizon")
    lines.append(
        f"- **Shared horizon:** {horizon.get('text')}"
        if isinstance(horizon, dict) and horizon.get("text")
        else "- **Shared horizon:** not yet confirmed"
    )
    if actor:
        front = (state.get("fronts") or {}).get(actor)
        if front:
            lines.append(
                f"- **Your front:** [{front.get('relation', 'explore')}] "
                f"{front.get('text') or front.get('subgoal') or 'open'}"
            )
        else:
            lines.append("- **Your front:** not yet confirmed")
    tasks = list((state.get("tasks") or {}).values())
    open_tasks = [row for row in tasks if row.get("status", "open") != "done"]
    if open_tasks:
        lines.append("- **Open tasks:** " + "; ".join(
            str(row.get("text") or row.get("title") or row.get("id"))
            for row in open_tasks[-5:]
        ))
    intersections = list((state.get("intersections") or {}).values())
    if intersections:
        lines.append("- **Intersection candidates:** " + "; ".join(
            str(row.get("text") or row.get("summary") or row.get("id"))
            for row in intersections[-5:]
        ))
    lines.append(
        "- **Authority:** suggestions are not decisions; members confirm their own "
        "fronts and commitments, and team-wide horizons require every active member."
    )
    return "\n".join(lines)


def render_state(state: dict) -> str:
    """Practitioner-readable team board generated from the event ledger."""
    lines = ["# Team state", ""]
    horizon = state.get("horizon")
    lines.extend(
        [
            "## Shared horizon",
            "",
            str(horizon.get("text")) if isinstance(horizon, dict) and horizon.get("text")
            else "*Not yet confirmed.*",
            "",
            "## Member fronts",
            "",
        ]
    )
    fronts = state.get("fronts") or {}
    if fronts:
        for member, front in sorted(fronts.items()):
            lines.append(
                f"- **{member}:** [{front.get('relation', 'explore')}] "
                f"{front.get('text') or front.get('subgoal') or 'open'}"
            )
    else:
        lines.append("*No confirmed member fronts.*")
    for title, key in (
        ("Commitments", "commitments"),
        ("Tasks", "tasks"),
        ("Decisions", "decisions"),
        ("Artifacts", "artifacts"),
        ("Intersections", "intersections"),
    ):
        lines.extend(["", f"## {title}", ""])
        values = list((state.get(key) or {}).values())
        if not values:
            lines.append("*None.*")
            continue
        for row in values[-20:]:
            label = row.get("text") or row.get("title") or row.get("summary") or row.get("id")
            owner = row.get("owner") or row.get("actor")
            suffix = f" — {owner}" if owner else ""
            lines.append(f"- {label}{suffix}")
    lines.extend(["", f"_Rebuilt from {state.get('event_count', 0)} attributed events._", ""])
    return "\n".join(lines)


def rehydrate_registry_views(registry: dict) -> int:
    """Rebuild every active team view selected by the resolved contract."""
    from channel_primitives import resolve_primitive

    rebuilt = 0
    for channel_id, entry in (registry.get("channels") or {}).items():
        primitive = resolve_primitive(registry, channel_id)
        if primitive is None or not primitive.has("shared_work"):
            continue
        key = str((entry or {}).get("mage") or "")
        space = (registry.get("spaces") or {}).get(key) or {}
        path = os.path.expanduser(str(space.get("practice_dir") or ""))
        if path:
            rebuild_views(path)
            rebuilt += 1
    return rebuilt


def _required_confirmers(
    kind: str,
    payload: dict,
    members: tuple[str, ...],
    actor: str,
) -> list[str]:
    if kind == "horizon":
        return list(members)
    if kind == "member_front":
        return [str(payload["member"])]
    if kind == "commitment":
        owners = payload.get("owners") or [payload.get("owner") or actor]
        return list(dict.fromkeys(str(value) for value in owners))
    if kind == "decision":
        affected = payload.get("affected_members") or list(members)
        return list(dict.fromkeys(str(value) for value in affected))
    if kind == "task" and payload.get("owner"):
        return [str(payload["owner"])]
    return [actor]


def _validate_payload(
    kind: str,
    payload: dict,
    members: tuple[str, ...],
    actor: str,
) -> dict:
    clean = dict(payload or {})
    member_set = set(members)
    if kind == "horizon" and not str(clean.get("text") or "").strip():
        raise ValueError("a shared horizon needs text")
    if kind == "member_front":
        member = str(clean.get("member") or actor)
        if member not in member_set:
            raise PermissionError("member front target is not in this team")
        relation = str(clean.get("relation") or "explore")
        if relation not in FRONT_RELATIONS:
            raise ValueError(f"invalid front relation: {relation}")
        clean["member"] = member
        clean["relation"] = relation
    for field in ("owner",):
        if clean.get(field) and str(clean[field]) not in member_set:
            raise PermissionError(f"{field} is not in this team")
    for field in ("owners", "affected_members"):
        values = [str(value) for value in (clean.get(field) or [])]
        if any(value not in member_set for value in values):
            raise PermissionError(f"{field} contains a non-member")
        if values:
            clean[field] = values
    return clean


def _require_team_member(primitive, actor: str) -> None:
    if primitive is None or not primitive.has("shared_work"):
        raise PermissionError("shared team state is unavailable")
    if actor not in primitive.members:
        raise PermissionError("actor is not a member of this team")


def _proposal_event(proposal: dict) -> dict:
    return {
        "schema": 1,
        "event_id": proposal["proposal_id"],
        "kind": proposal["kind"],
        "actor": proposal.get("actor"),
        "actor_role": proposal.get("actor_role"),
        "payload": proposal.get("payload") or {},
        "source_eddy": proposal.get("source_eddy"),
        "at": proposal.get("decided_at") or _now(),
        "confirmations": proposal.get("confirmations") or [],
    }


def _change_event(proposal: dict) -> dict:
    return {
        "proposal_id": proposal["proposal_id"],
        "status": proposal["status"],
        "actor": proposal.get("decided_by"),
        "at": proposal.get("decided_at"),
        "kind": proposal.get("kind"),
    }


def _read_events(root: Path) -> list[dict]:
    path = root / "team" / "events.jsonl"
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


def _empty_state() -> dict:
    return {
        "schema": 1,
        "horizon": None,
        "fronts": {},
        "commitments": {},
        "tasks": {},
        "decisions": {},
        "artifacts": {},
        "intersections": {},
        "contributions": [],
        "event_count": 0,
    }


def _reduce(state: dict, event: dict) -> None:
    kind = str(event.get("kind") or "")
    payload = dict(event.get("payload") or {})
    payload.setdefault("actor", event.get("actor"))
    payload.setdefault("at", event.get("at"))
    payload.setdefault("source_eddy", event.get("source_eddy"))
    event_id = str(event.get("event_id") or _content_id(event))
    if kind == "horizon":
        state["horizon"] = payload
    elif kind == "member_front":
        state["fronts"][str(payload.get("member"))] = payload
    elif kind in {"commitment", "task", "decision", "artifact", "intersection"}:
        key = str(payload.get("id") or event_id)
        state[f"{kind}s"][key] = payload
    elif kind in {"contribution", "progress"}:
        state["contributions"].append(payload)


def _content_id(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
