"""Member-owned eddies inside a readable shared team channel."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass

from thread_registry import (
    get_thread_team_lane,
    team_activity_threads,
    update_thread_team_lane,
)


_current_eddy_ctx: ContextVar[int | None] = ContextVar(
    "team_current_eddy", default=None
)


@dataclass(frozen=True)
class LaneGate:
    allowed: bool
    activity_id: str | None = None
    owner: str | None = None
    reason: str | None = None


def bind_current_eddy(thread_id: int | None) -> None:
    """Carry source-eddy provenance through the current async tool loop."""
    _current_eddy_ctx.set(thread_id)


def get_current_eddy_id() -> int | None:
    return _current_eddy_ctx.get()


def register_lane(
    thread_id: int,
    *,
    activity_id: str,
    owner: str,
    role: str | None = None,
    character: str | None = None,
    siblings: tuple[int | str, ...] = (),
) -> dict:
    if not activity_id.strip() or not owner.strip():
        raise ValueError("team lane needs an activity id and owner")
    return update_thread_team_lane(
        thread_id,
        activity_id=activity_id,
        lane_owner=owner,
        lane_role=role,
        lane_character=character,
        sibling_lane_ids=siblings,
    )


def gate_lane_turn(
    thread_id: int | str,
    *,
    actor: str | None,
    primitive,
) -> LaneGate:
    """Allow only the lane owner to advance state; peeking stays unrestricted."""
    lane = get_thread_team_lane(thread_id)
    if lane is None:
        return LaneGate(True)
    activity_id = str(lane.get("activity_id") or "")
    owner = str(lane.get("lane_owner") or "")
    if primitive is None or not primitive.has("member_lanes"):
        return LaneGate(
            False,
            activity_id=activity_id,
            owner=owner,
            reason="member-lane capability is unavailable",
        )
    if not actor or actor not in primitive.members:
        return LaneGate(
            False,
            activity_id=activity_id,
            owner=owner,
            reason="speaker is not a registered team member",
        )
    if actor != owner:
        return LaneGate(
            False,
            activity_id=activity_id,
            owner=owner,
            reason=f"this is {owner}'s member lane",
        )
    return LaneGate(True, activity_id=activity_id, owner=owner)


def lane_context(thread_id: int | str) -> str:
    lane = get_thread_team_lane(thread_id)
    if lane is None:
        return ""
    activity_id = str(lane.get("activity_id") or "")
    owner = str(lane.get("lane_owner") or "")
    siblings = team_activity_threads(activity_id)
    sibling_labels = [
        f"{entry.get('lane_owner')} (eddy {other_id})"
        for other_id, entry in siblings.items()
        if str(other_id) != str(thread_id)
    ]
    lines = [
        "## Member Lane",
        f"- **Activity:** {activity_id}",
        f"- **Lane owner:** {owner}",
        "- **Write boundary:** only the lane owner advances this eddy; other members "
        "may read it and work in their own lane.",
    ]
    if lane.get("lane_character"):
        lines.append(f"- **Character / role:** {lane['lane_character']}")
    if sibling_labels:
        lines.append(f"- **Sibling lanes:** {', '.join(sibling_labels)}")
    return "\n".join(lines)
