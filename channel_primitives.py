"""Validated channel contracts: Channel + Turtle + River + Practice.

The registry may still contain legacy ``type`` rows.  This module is the
compatibility seam: callers resolve one complete primitive instead of growing
another channel-type conditional.  Primitive declarations describe policy;
state remains in the owning practice root.

A registry row may choose a named preset and, where that preset permits it,
one topology variant.  It may not compose memory, data policy, authority, and
capabilities independently: unsupported combinations fail closed.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping


@dataclass(frozen=True)
class ChannelPrimitive:
    name: str
    base: str
    allowed_bases: frozenset[str]
    attunement: str
    memory_boundary: str
    parent_owner: str
    parent_posture: str
    data_policy: str
    capabilities: frozenset[str]
    eddy_parent: bool = True
    lifecycle_bar: bool = True
    channel_id: str | None = None
    practice_key: str | None = None
    subject: str | None = None
    steward: str | None = None
    coordinator: str | None = None
    members: tuple[str, ...] = ()
    parent_controls: tuple[str, ...] = ("new_eddy",)

    def has(self, capability: str) -> bool:
        return capability in self.capabilities

    def role_for(self, member_key: str | None) -> str | None:
        if not member_key:
            return None
        if member_key == self.subject:
            return "subject"
        if member_key == self.steward:
            return "steward"
        if member_key == self.coordinator:
            return "coordinator"
        if member_key in self.members:
            return "member"
        return None

    def has_role(self, member_key: str | None, role: str) -> bool:
        """Role predicates do not force responsibilities into one label."""
        if not member_key:
            return False
        if role == "subject":
            return member_key == self.subject
        if role == "steward":
            return member_key == self.steward
        if role == "coordinator":
            return member_key == self.coordinator
        if role == "member":
            return member_key in self.members
        if role == "owner":
            return member_key == self.subject
        if role == "support":
            return member_key == self.steward
        return False


_DEFINITIONS: dict[str, ChannelPrimitive] = {
    "private": ChannelPrimitive(
        name="private",
        base="solo",
        allowed_bases=frozenset({"solo"}),
        attunement="native",
        memory_boundary="personal_plus_shared",
        parent_owner="river",
        parent_posture="ambient",
        data_policy="standard_local",
        capabilities=frozenset({"dialogue", "story", "artifacts"}),
        parent_controls=("new_eddy", "threads", "artifacts"),
    ),
    "shared": ChannelPrimitive(
        name="shared",
        base="shared",
        allowed_bases=frozenset({"shared"}),
        attunement="native",
        memory_boundary="own_root",
        parent_owner="river",
        parent_posture="ambient",
        data_policy="shared_local",
        capabilities=frozenset(
            {"dialogue", "story", "artifacts", "sharing", "dates"}
        ),
        parent_controls=("new_eddy", "threads", "artifacts"),
    ),
    "craft": ChannelPrimitive(
        name="craft",
        base="solo",
        allowed_bases=frozenset({"solo"}),
        attunement="craft",
        memory_boundary="personal_without_shared",
        parent_owner="river",
        parent_posture="deterministic_intake",
        data_policy="operator_local",
        capabilities=frozenset(
            {
                "dialogue",
                "story",
                "artifacts",
                "craft_intake",
                "source_inspection",
                "craft_readiness",
            }
        ),
        lifecycle_bar=False,
        parent_controls=("new_eddy", "threads", "artifacts"),
    ),
    "partnership": ChannelPrimitive(
        name="partnership",
        base="shared",
        allowed_bases=frozenset({"shared"}),
        attunement="native",
        memory_boundary="own_root",
        parent_owner="river",
        parent_posture="ambient",
        data_policy="shared_local",
        capabilities=frozenset(
            {
                "dialogue",
                "story",
                "artifacts",
                "sharing",
                "dates",
                "attributed_memory",
            }
        ),
        parent_controls=("new_eddy", "threads", "artifacts"),
    ),
    "health": ChannelPrimitive(
        name="health",
        base="shared",
        allowed_bases=frozenset({"solo", "shared"}),
        attunement="health",
        memory_boundary="isolated",
        parent_owner="river",
        parent_posture="governed_intake",
        data_policy="sensitive_local",
        capabilities=frozenset(
            {
                "dialogue",
                "story",
                "source_intake",
                "corpus_retrieval",
                "governed_record",
                "appointment_prep",
            }
        ),
        lifecycle_bar=False,
        parent_controls=("new_eddy",),
    ),
    "team": ChannelPrimitive(
        name="team",
        base="shared",
        allowed_bases=frozenset({"shared"}),
        attunement="native",
        memory_boundary="own_root",
        parent_owner="river",
        parent_posture="operational",
        data_policy="shared_local",
        capabilities=frozenset(
            {
                "dialogue",
                "story",
                "artifacts",
                "sharing",
                "attributed_memory",
                "shared_work",
                "goal_state",
                "member_lanes",
                "task_state",
                "decision_state",
                "artifact_state",
                "intersection_state",
                "coordination",
            }
        ),
        parent_controls=("new_eddy", "threads", "artifacts"),
    ),
}

_TYPE_TO_PRIMITIVE = {
    "river": "private",
    "hosted-river": "private",
    "unclaimed-river": "private",
    "shared": "shared",
    "shared-river": "shared",
    "craft": "craft",
    "health": "health",
    "partnership": "partnership",
    "team": "team",
}


def primitive_definition(name: str) -> ChannelPrimitive | None:
    """Return an immutable base declaration, or ``None`` for unknown names."""
    return _DEFINITIONS.get((name or "").strip().lower())


def resolve_primitive(
    registry: Mapping[str, Any], channel_id: int | str
) -> ChannelPrimitive | None:
    """Resolve a registered parent channel to one complete primitive.

    Explicit ``primitive`` wins.  Legacy ``type`` remains a compatibility
    adapter.  Unknown declarations fail closed instead of inheriting a wider
    capability set.
    """
    entry = (registry.get("channels") or {}).get(str(channel_id))
    if not isinstance(entry, Mapping) or entry.get("archived") or entry.get("orphaned"):
        return None
    name = str(entry.get("primitive") or "").strip().lower()
    if not name:
        name = _TYPE_TO_PRIMITIVE.get(str(entry.get("type") or "").strip().lower(), "")
    base = primitive_definition(name)
    if base is None:
        return None

    space_key = str(entry.get("mage") or "")
    space_entry = (registry.get("spaces") or {}).get(space_key)
    has_space = isinstance(space_entry, Mapping)
    space = space_entry if has_space else {}
    mage = (registry.get("mages") or {}).get(space_key)
    if not isinstance(mage, Mapping):
        mage = {}

    requested_base = str(entry.get("base") or "").strip().lower()
    if requested_base:
        resolved_base = requested_base
    elif name == "health" and mage and not has_space:
        resolved_base = "solo"
    else:
        resolved_base = base.base

    # Health state lives on the space when one exists — including a
    # one-member solo instance. Otherwise solo would inherit the
    # personal mage practice_dir.
    if name == "health" and has_space:
        owner = space
    else:
        owner = space if resolved_base == "shared" else mage
    members = tuple(str(value) for value in (owner.get("members") or ()))
    if resolved_base == "solo" and not members and space_key:
        members = (space_key,)
    subject = _clean_role(owner.get("subject") or entry.get("subject"))
    steward = _clean_role(owner.get("steward") or entry.get("steward"))
    coordinator = _clean_role(
        owner.get("coordinator") or entry.get("coordinator")
    )

    # Legacy shared-health rows predate roles. Preserve service while making
    # their migration deterministic. A solo health instance needs no steward.
    if name == "health" and members and not entry.get("primitive"):
        subject = subject or (
            members[1]
            if resolved_base == "shared" and len(members) > 1
            else members[0]
        )
        if resolved_base == "shared":
            steward = steward or next(
                (member for member in members if member != subject), None
            )

    resolved = replace(
        base,
        base=resolved_base,
        eddy_parent=(
            False
            if str(entry.get("type") or "").strip().lower() == "unclaimed-river"
            else base.eddy_parent
        ),
        channel_id=str(channel_id),
        practice_key=space_key or None,
        subject=subject,
        steward=steward,
        coordinator=coordinator,
        members=members,
        memory_boundary=str(owner.get("memory") or base.memory_boundary),
    )
    return resolved if primitive_is_valid(resolved) else None


def primitive_is_valid(primitive: ChannelPrimitive) -> bool:
    """Fail closed when topology, memory, or authority is incoherent."""
    if primitive.base not in primitive.allowed_bases:
        return False
    expected_memory = _DEFINITIONS[primitive.name].memory_boundary
    if primitive.memory_boundary != expected_memory:
        return False
    if primitive.parent_owner not in {"river", "practice"}:
        return False
    if primitive.name == "partnership":
        return bool(
            primitive.base == "shared"
            and primitive.memory_boundary == "own_root"
            and (not primitive.members or len(primitive.members) == 2)
        )
    if primitive.name == "team":
        return bool(
            primitive.base == "shared"
            and primitive.memory_boundary == "own_root"
            and (not primitive.members or len(primitive.members) >= 2)
            and primitive.coordinator in primitive.members
        )
    if primitive.name == "health":
        return bool(
            primitive.memory_boundary == "isolated"
            and primitive.data_policy == "sensitive_local"
            and primitive.subject in primitive.members
            and (
                primitive.steward is None
                or primitive.steward in primitive.members
            )
        )
    return True


def assign_health_support(space: dict[str, Any], *, actor: str, support: str) -> dict[str, Any]:
    """Only the health owner (subject) may name support (steward).

    Practitioner names: owner / support. Registry keys stay subject / steward.
    A second person's health is a second health instance, not a second steward
    on this one.
    """
    if not isinstance(space, dict):
        raise TypeError("health space must be a mapping")
    owner = _clean_role(space.get("subject"))
    members = {str(value) for value in (space.get("members") or ())}
    support_key = _clean_role(support)
    if not owner:
        raise PermissionError("health space has no owner")
    if actor != owner:
        raise PermissionError("only the health owner can assign support")
    if not support_key or support_key not in members:
        raise ValueError("support must already be a member of the health space")
    if support_key == owner:
        raise ValueError("owner and support must be different people")
    updated = dict(space)
    updated["steward"] = support_key
    return updated


def _clean_role(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None
