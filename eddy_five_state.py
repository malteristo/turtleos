"""Five practitioner names for eddy state.

Step 2 of the 2026-09-13 register: collapse Discord thread facts and the
registry harvest flags onto live / resting / kept / sealed / gone.

No new Discord state. No agent loop. A name with two sources that disagree
is a bug in the mapper, not a sixth name.
"""

from __future__ import annotations

from typing import Any

FIVE_STATES = ("gone", "sealed", "kept", "resting", "live")

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


def group_lines_by_five_state(
    items: list[tuple[str, str]],
) -> dict[str, list[str]]:
    """Order-preserving buckets. Unknown names fall into live so a typo is visible."""
    grouped = {name: [] for name in FIVE_STATES}
    for state, line in items:
        grouped[state if state in grouped else _LIVE].append(line)
    return grouped


# Attention order: what you might open, then what is parked.
_FIT_ORDER = ("live", "kept", "sealed", "resting", "gone")
# Default glance lists these; parked states are a count until --all.
_GLANCE_LIST = ("live", "kept", "sealed")
SECTION_CAP = 12
# Discord embed description hard limit. A list that cannot post is not a list.
EMBED_DESCRIPTION_LIMIT = 4096
FIELD_VALUE_LIMIT = 1024


def five_state_title(grouped: dict[str, list[str]]) -> str:
    bits = [f"{len(grouped[name])} {name}" for name in _FIT_ORDER if grouped[name]]
    return "Eddies — " + " · ".join(bits) if bits else "Eddies — none"


def _section_header(name: str, count: int) -> str:
    return f"**{name} · {count}**"


def render_five_state_sections(grouped: dict[str, list[str]]) -> str:
    parts: list[str] = []
    for name in _FIT_ORDER:
        rows = grouped[name]
        if not rows:
            continue
        parts.append(_section_header(name, len(rows)))
        parts.extend(rows)
    return "\n".join(parts)


def _collapse_label(name: str) -> str:
    return "parked" if name == "resting" else "closed"


def _fit_rows(
    rows: list[str],
    *,
    cap: int,
    limit: int,
) -> list[str]:
    """Name rows up to ``cap``, then a leftover line, always inside ``limit``."""
    if limit < 16:
        raise ValueError("limit too small to name a row")
    chunks: list[str] = []
    used = 0

    def _append(text: str) -> bool:
        nonlocal used
        extra = len(text) + (1 if chunks else 0)
        if used + extra > limit:
            return False
        chunks.append(text)
        used += extra
        return True

    budget = min(len(rows), cap)
    shown = 0
    for i, row in enumerate(rows[:budget]):
        rest_after = len(rows) - i - 1
        extra = len(row) + (1 if chunks else 0)
        reserve = 0
        if rest_after:
            reserve = 1 + len(f"… and {rest_after} more")
        if used + extra + reserve > limit:
            omitted = len(rows) - shown
            more = f"… and {omitted} more"
            if not _append(more) and shown == 0:
                break
            break
        _append(row)
        shown += 1
    else:
        omitted = len(rows) - shown
        if omitted:
            _append(f"… and {omitted} more")
    return chunks


def fit_embed_description(
    grouped: dict[str, list[str]],
    *,
    expand: bool = False,
    cap: int = SECTION_CAP,
    limit: int = EMBED_DESCRIPTION_LIMIT,
) -> str:
    """Render a glance (or an inventory) that always fits ``limit``.

    Counts stay in the title. Default view lists live / kept / sealed and
    collapses resting / gone to a count. ``expand`` is ``!threads --all``.
    """
    if limit < 32:
        raise ValueError("limit too small to name a section")
    chunks: list[str] = []
    used = 0

    def _append(text: str) -> bool:
        nonlocal used
        extra = len(text) + (1 if chunks else 0)
        if used + extra > limit:
            return False
        chunks.append(text)
        used += extra
        return True

    remaining = limit
    for name in _FIT_ORDER:
        rows = grouped.get(name) or []
        if not rows:
            continue
        header = _section_header(name, len(rows))
        if not _append(header):
            break
        remaining = limit - used
        if not expand and name not in _GLANCE_LIST:
            _append(_collapse_label(name))
            continue
        body_limit = max(remaining - 1, 16)
        for line in _fit_rows(rows, cap=cap, limit=body_limit):
            if not _append(line):
                break
    return "\n".join(chunks)


def five_state_fields(
    grouped: dict[str, list[str]],
    *,
    expand: bool = False,
    cap: int = SECTION_CAP,
) -> list[tuple[str, str]]:
    """Discord embed fields: one per state that has rows. Glance collapses parked."""
    fields: list[tuple[str, str]] = []
    for name in _FIT_ORDER:
        rows = grouped.get(name) or []
        if not rows:
            continue
        label = f"{name} · {len(rows)}"
        if not expand and name not in _GLANCE_LIST:
            fields.append((label, _collapse_label(name)))
            continue
        value = "\n".join(_fit_rows(rows, cap=cap, limit=FIELD_VALUE_LIMIT))
        fields.append((label, value or _collapse_label(name)))
    return fields
