"""Health room — board rules that must be able to fail.

Visibility is a claim: a planted extra viewer fails. Naming the best
current model is the job of the room, not a forbidden shape.
"""

from __future__ import annotations

from pathlib import Path

HEALTH_PICTURE_NAME = "health_model.md"
HEALTH_PICTURE_MAX_CHARS = 8000

# Old wall text. A planted reply that names a model must not be replaced
# with this. Kept so the test can fail if the wall returns.
HEALTH_DIAGNOSIS_FALLBACK = (
    "I almost named a diagnosis. That is not this room's job. "
    "The doctors decide. What I can hold is what has been observed, "
    "what is still unexplained, and which question would help the next appointment."
)


def load_health_picture(practice_dir: str | None, max_chars: int = HEALTH_PICTURE_MAX_CHARS) -> str:
    """Read the living picture from the health practice root.

    Empty when the file is missing — Turtle still talks; the board stays
    empty until someone brings documents. A planted file must appear in
    the health prompt (positive control in ``test_health_channel``).
    """
    if not practice_dir:
        return ""
    path = Path(practice_dir) / HEALTH_PICTURE_NAME
    if not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    if not text:
        return ""
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + "\n\n[... board truncated ...]"
    return (
        "## Current board\n\n"
        "This is the living picture on this household's hardware. "
        "Use it. Do not invent past it. When they bring a new observation "
        "(how a day felt, what a doctor said, a video, a noticing), treat "
        "it as intake for this board.\n\n"
        + text
    )


def vet_health_reply(text: str) -> str:
    """Pass the reply through.

    Dest 2026-09-16: naming the best current model is the job. The old
    wall replaced those replies. Do not put it back.
    """
    return text


def visibility_findings(
    *,
    everyone_denied: bool,
    viewer_ids: set[int],
    allowed_ids: set[int],
    viewing_role_ids: set[int] | None = None,
) -> list[str]:
    """Reasons this room is visible to the wrong people. Empty means ok.

    ``viewer_ids`` are members/bots who can view. ``allowed_ids`` are the
    two people plus the bots. A viewing role other than @everyone is a
    finding — roles expand the room.
    """
    findings: list[str] = []
    if not everyone_denied:
        findings.append("@everyone can view")
    unexpected = sorted(viewer_ids - allowed_ids)
    if unexpected:
        findings.append(f"unexpected viewers: {unexpected}")
    missing = sorted(allowed_ids - viewer_ids)
    if missing:
        findings.append(f"missing members: {missing}")
    extra_roles = sorted(viewing_role_ids or ())
    if extra_roles:
        findings.append(f"viewing roles: {extra_roles}")
    return findings


# Discord overwrite types. @everyone is a role (0) whose id equals the guild
# id. Sending it as a member (1) is the defect that left a live channel open.
OVERWRITE_ROLE = 0
OVERWRITE_MEMBER = 1
VIEW_CHANNEL = 1 << 10
SEND_MESSAGES = 1 << 11
MANAGE_CHANNELS = 1 << 4
MANAGE_MESSAGES = 1 << 13
CREATE_PUBLIC_THREADS = 1 << 15
READ_MESSAGE_HISTORY = 1 << 16
SEND_MESSAGES_IN_THREADS = 1 << 38

_MEMBER_ALLOW = (
    VIEW_CHANNEL
    | SEND_MESSAGES
    | READ_MESSAGE_HISTORY
    | CREATE_PUBLIC_THREADS
    | SEND_MESSAGES_IN_THREADS
)
_BOT_ALLOW = _MEMBER_ALLOW | MANAGE_CHANNELS | MANAGE_MESSAGES


def health_permission_overwrites(
    *,
    everyone_id: int,
    member_ids: list[int],
    bot_ids: list[int],
) -> list[dict]:
    """REST payload. @everyone must be type role or the deny does not land."""
    rows = [
        {
            "id": everyone_id,
            "type": OVERWRITE_ROLE,
            "allow": "0",
            "deny": str(VIEW_CHANNEL),
        }
    ]
    for uid in member_ids:
        rows.append(
            {
                "id": uid,
                "type": OVERWRITE_MEMBER,
                "allow": str(_MEMBER_ALLOW),
                "deny": "0",
            }
        )
    for uid in bot_ids:
        rows.append(
            {
                "id": uid,
                "type": OVERWRITE_MEMBER,
                "allow": str(_BOT_ALLOW),
                "deny": "0",
            }
        )
    return rows


def everyone_overwrite_is_role(rows: list[dict], everyone_id: int) -> bool:
    for row in rows:
        if int(row["id"]) == int(everyone_id):
            return int(row["type"]) == OVERWRITE_ROLE
    return False


def raw_everyone_denied(rows: list[dict], everyone_id: int) -> bool:
    """True when the REST payload denies view on the @everyone role."""
    for row in rows:
        if int(row["id"]) != int(everyone_id):
            continue
        if int(row.get("type", OVERWRITE_MEMBER)) != OVERWRITE_ROLE:
            return False
        deny = int(row.get("deny") or 0)
        return (deny & VIEW_CHANNEL) == VIEW_CHANNEL
    return False


def overwrite_denies_view(ow) -> bool:
    if getattr(ow, "view_channel", None) is False:
        return True
    pair = getattr(ow, "pair", None)
    if callable(pair):
        _allow, deny = pair()
        return bool(getattr(deny, "view_channel", False))
    return False


def overwrite_allows_view(ow) -> bool:
    if getattr(ow, "view_channel", None) is True:
        return True
    pair = getattr(ow, "pair", None)
    if callable(pair):
        allow, _deny = pair()
        return bool(getattr(allow, "view_channel", False))
    return False


def visibility_ok(
    *,
    everyone_denied: bool,
    viewer_ids: set[int],
    allowed_ids: set[int],
    viewing_role_ids: set[int] | None = None,
) -> bool:
    return not visibility_findings(
        everyone_denied=everyone_denied,
        viewer_ids=viewer_ids,
        allowed_ids=allowed_ids,
        viewing_role_ids=viewing_role_ids,
    )
