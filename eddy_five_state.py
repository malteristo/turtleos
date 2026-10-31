"""Five practitioner names for eddy state.

Step 2 of the 2026-09-13 register: collapse Discord thread facts and the
registry harvest flags onto live / resting / kept / sealed / gone.

No new Discord state. No agent loop. A name with two sources that disagree
is a bug in the mapper, not a sixth name.
"""

from __future__ import annotations

from typing import Any

FIVE_STATES = ("gone", "sealed", "kept", "resting", "live")
SECTION_CAP = 12

# Priority: first match wins. A dissolved home is gone, not kept.
_GONE = "gone"
_SEALED = "sealed"
_KEPT = "kept"
_RESTING = "resting"
_LIVE = "live"


def eddy_five_state(
    info: dict[str, Any] | None = None,
    *,
    discord_archived: bool = False,
    discord_locked: bool = False,
    is_home: bool = False,
) -> str:
    """Map product facts the tree already has onto one of the five names.

    ``info`` is a ``thread_registry`` row. Discord flags are the live thread
    object when a reader has one; registry ``locked`` and ``harvest_status``
    cover the case with no Discord handle.
    """
    row = info or {}
    if row.get("harvest_status") == "dissolved":
        return _GONE
    if discord_locked or row.get("locked"):
        return _SEALED
    if is_home or row.get("continuity") == "keep":
        return _KEPT
    if row.get("harvest_status") == "cooled" or discord_archived:
        return _RESTING
    return _LIVE
