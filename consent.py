"""Consent — what the platform may do with a practitioner's record.

Destination artifacts: ``docs/design/consent-and-continuity.md`` (press release,
happy paths, criteria, abandon line). This module is the resolver only; the
asking surface and the delete sweep are later slices.

Three separate permissions, deliberately not one:

  ``self_continuity``   the system remembers this practitioner, for them.
                        Refusing means stateless inference — a real product and
                        a lesser one. This one *is* the feature.
  ``room_continuity``   this practitioner's material may be held in a shared
                        space's memory, where the other members see it resurface.
  ``operator_access``   the host may read this record to find defects and
                        evaluate the software. This serves the **host**, not the
                        practitioner, so refusing it must cost them nothing
                        (``consent-and-continuity.md`` C2). Never bundle it with
                        the other two: a consent that can be priced is not one.

**Fail-closed everywhere.** Absent record, unregistered root, unknown purpose,
unparseable answer — all deny. The allowlist discipline, not a blocklist: a
destination nobody thought of must land on "no" by default rather than slip
through. Same reasoning as the canary returning yellow rather than green when
its URL is unset.

**Unanimity for shared spaces.** A room's memory is gated on every member having
granted ``room_continuity`` — not on membership. Nobody is excluded from a room
for not answering; the room simply stays in the present until the last person
says yes. An eddy note is a *synthesis*, not a transcript, so retaining only the
consenting members' contributions is not actually available: a conversation with
one voice subtracted reads wrong, and the model reconstructs the missing side by
inference anyway. Exclusion at the seam is the only version that is true.

**Who has not answered is not disclosable.** ``room_status`` reports that a room
is ungated and never which member is outstanding — that is peer pressure with a
name attached. The pending question lives in that person's own river, where only
they see it.
"""

from __future__ import annotations

from typing import Any

SELF_CONTINUITY = "self_continuity"
ROOM_CONTINUITY = "room_continuity"
OPERATOR_ACCESS = "operator_access"

PURPOSES = (SELF_CONTINUITY, ROOM_CONTINUITY, OPERATOR_ACCESS)

# What a refusal asked us to do with material already on disk. Two values, not a
# boolean on the grant: "stop from here" and "stop and remove" are different
# intentions and the second cannot be undone, so a refusal that meant the first
# must never be executed as the second.
REMOVAL_KEEP = "keep"
REMOVAL_REMOVE = "remove"
REMOVALS = (REMOVAL_KEEP, REMOVAL_REMOVE)

# The consent record is the one artifact a "remove everything" answer does not
# reach: keeping the practitioner's words is the only way we know not to start
# again. The happy path says this out loud rather than assuming it
# (``consent-and-continuity.md`` §2.2), and the delete sweep reads this constant
# rather than re-deciding it.
DELETION_EXEMPT_KEYS = ("consent",)


class ConsentWithheld(Exception):
    """Raised by :func:`require` when a purpose is not granted."""

    def __init__(self, purpose: str, subject: str, reason: str) -> None:
        super().__init__(f"{purpose} not granted for {subject}: {reason}")
        self.purpose = purpose
        self.subject = subject
        self.reason = reason


def _registry() -> dict[str, Any]:
    import mage

    return mage.get_registry() or {}


def _entry_for_key(key: str, kind: str) -> dict[str, Any] | None:
    section = "mages" if kind == "mage" else "spaces"
    entry = (_registry().get(section) or {}).get(key)
    return entry if isinstance(entry, dict) else None


def record_for_key(key: str, kind: str = "mage") -> dict[str, Any] | None:
    """The raw consent block for a registry key, or ``None`` when absent."""
    entry = _entry_for_key(key, kind)
    if not entry:
        return None
    record = entry.get("consent")
    return record if isinstance(record, dict) else None


def _grant(record: dict[str, Any] | None, purpose: str) -> bool:
    """Fail-closed read of one grant. Only an explicit ``True`` is a yes."""
    if not record or purpose not in PURPOSES:
        return False
    grants = record.get("grants")
    if not isinstance(grants, dict):
        return False
    return grants.get(purpose) is True


def granted_by_key(key: str, purpose: str, kind: str = "mage") -> bool:
    """Has this registry key granted this purpose? Fail-closed."""
    if purpose not in PURPOSES:
        return False
    return _grant(record_for_key(key, kind), purpose)


def removal_choice(key: str) -> str:
    """What a refusal asked for: ``keep`` (default) or ``remove``.

    Defaults to ``keep`` on purpose. Deletion is the irreversible direction, so
    an ambiguous or missing answer must not be executed as removal — the
    conservative default here is the *opposite* of the conservative default on
    grants, and both are conservative in the same sense: never do the thing that
    cannot be taken back.
    """
    record = record_for_key(key)
    value = (record or {}).get("removal")
    return value if value in REMOVALS else REMOVAL_KEEP


def answered(key: str, kind: str = "mage") -> bool:
    """Has this key answered at all? An unanswered question is not a refusal."""
    record = record_for_key(key, kind)
    if not record:
        return False
    return bool(record.get("answered_at"))


def _resolve(practice_dir) -> tuple[str | None, str | None]:
    import mage

    return mage.registry_key_for_practice_dir(practice_dir)


def _space_members(practice_dir) -> list[str]:
    import mage

    return mage.space_members_for_practice_dir(practice_dir)


def may(purpose: str, practice_dir) -> bool:
    """May we do ``purpose`` with the record at ``practice_dir``? Fail-closed.

    For a space root, ``room_continuity`` requires **every** member to have
    granted it; any other purpose on a space root resolves against the space's
    own record.
    """
    if purpose not in PURPOSES:
        return False
    key, kind = _resolve(practice_dir)
    if not key:
        return False
    if kind == "space" and purpose == ROOM_CONTINUITY:
        members = _space_members(practice_dir)
        if not members:
            return False
        return all(granted_by_key(m, ROOM_CONTINUITY) for m in members)
    return granted_by_key(key, purpose, kind)


def require(purpose: str, practice_dir) -> None:
    """:func:`may`, as a gate. Raises :class:`ConsentWithheld` on refusal."""
    if may(purpose, practice_dir):
        return
    key, kind = _resolve(practice_dir)
    if not key:
        raise ConsentWithheld(purpose, str(practice_dir), "root is not registered")
    if purpose not in PURPOSES:
        raise ConsentWithheld(purpose, key, "unknown purpose")
    if kind == "space" and purpose == ROOM_CONTINUITY:
        raise ConsentWithheld(purpose, key, "not every member has agreed")
    reason = "no answer recorded" if not answered(key, kind) else "declined"
    raise ConsentWithheld(purpose, key, reason)


def room_status(practice_dir) -> dict[str, Any]:
    """Whether a room may keep memory — **without naming who is outstanding.**

    ``pending`` is a count, never a list of keys. A member must not be able to
    learn from the room who has not answered; that question lives in the other
    person's own river.
    """
    key, kind = _resolve(practice_dir)
    if not key or kind != "space":
        return {"registered": False, "remembering": False, "pending": 0}
    members = _space_members(practice_dir)
    pending = sum(1 for m in members if not granted_by_key(m, ROOM_CONTINUITY))
    return {
        "registered": True,
        "remembering": bool(members) and pending == 0,
        "pending": pending,
    }


def unanswered_members(practice_dir) -> list[str]:
    """Members who have not answered — for **delivering** the ask, not display.

    Deliberately separate from :func:`room_status` so that the surface a member
    sees and the list the delivery job needs cannot be reached through the same
    call by accident.
    """
    key, kind = _resolve(practice_dir)
    if not key or kind != "space":
        return []
    return [m for m in _space_members(practice_dir) if not answered(m)]


def _main(argv: list[str]) -> int:
    """``python consent.py <practice_dir> <purpose>`` — exit 0 granted, 1 not.

    A shell-consumable gate for read-side tooling that is not Python.
    """
    if len(argv) < 3:
        print(f"usage: consent.py <practice_dir> <{'|'.join(PURPOSES)}>")
        return 2
    practice_dir, purpose = argv[1], argv[2]
    try:
        require(purpose, practice_dir)
    except ConsentWithheld as e:
        print(f"denied: {e}")
        return 1
    print(f"granted: {purpose} for {practice_dir}")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(_main(sys.argv))
