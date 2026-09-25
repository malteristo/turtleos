"""Spoken requests in the parent river become displays, not prose.

The harness fulfills the act with the same collectors the bang commands use.
The small River model may also emit these act types; parse_display_request is
the path that does not wait on a classify round-trip.
"""

from __future__ import annotations

import re
from typing import Any

from eddy_five_state import FIVE_STATES, SECTION_CAP

WINDOW_DAYS = 5

# Acts that draw in the parent. Anything else in a craft room files intake.
DISPLAY_ACT_TYPES = frozenset(
    {
        "show_threads",
        "show_waiting",
        "show_channel_menu",
        "offer_flow_menu",
        "offer_flow",
        "present_artifacts",
        "error",
    }
)


def settle_parent_acts(
    acts: list[dict[str, Any]] | None,
    *,
    craft: bool,
) -> list[dict[str, Any]]:
    """Craft's default act is file intake. A display wins."""
    settled = [a for a in (acts or []) if isinstance(a, dict) and a.get("type")]
    kinds = {a.get("type") for a in settled}
    if craft and not (kinds & DISPLAY_ACT_TYPES):
        return [{"type": "file_intake"}]
    return settled

_MENTION = re.compile(r"^<@!?\d+>\s*")
_RIVER_ADDR = re.compile(r"^river[,:]?\s+", re.I)
_DAYS = re.compile(
    r"(?:last|past|previous)\s+(\d+)\s+days?|"
    r"last\s+week|"
    r"today|"
    r"last\s+24\s+hours?",
    re.I,
)


def strip_river_address(text: str) -> str:
    text = (text or "").strip()
    text = _MENTION.sub("", text)
    text = _RIVER_ADDR.sub("", text)
    return text.strip()


def parse_days_window(text: str) -> int | None:
    match = _DAYS.search(text or "")
    if not match:
        return None
    if match.group(1):
        days = int(match.group(1))
        return days if days > 0 else None
    token = match.group(0).lower()
    if "week" in token:
        return 7
    if "today" in token or "24" in token:
        return 1
    return None


def parse_display_request(text: str) -> dict[str, Any] | None:
    """Deterministic display acts. None means fall through to the River model."""
    body = strip_river_address(text).lower()
    if not body:
        return None
    if _wants_channel_menu(body):
        return {"type": "show_channel_menu"}
    if _wants_waiting(body):
        return {"type": "show_waiting"}
    if _wants_threads(body):
        return {"type": "show_threads", "days": parse_days_window(body)}
    return None


def _wants_waiting(body: str) -> bool:
    if "waiting" in body:
        return True
    if "where is the heat" in body or "where's the heat" in body:
        return True
    return "ready" in body and "session" in body


def _wants_threads(body: str) -> bool:
    if "thread" not in body and "eddy" not in body:
        return False
    return any(verb in body for verb in ("show", "list", "see", "what", "which"))


def _wants_channel_menu(body: str) -> bool:
    if "channel menu" in body or "channel controls" in body:
        return True
    if "controls" in body and "channel" in body:
        return True
    return body in {
        "what can i do here",
        "what can i do here?",
        "change the channel",
        "channel menu",
        "channel controls",
    }


def likely_thread_action(state: str) -> str:
    """One next act per state. Gone has none."""
    if state == "gone":
        return ""
    return "Open"


def filter_records_by_days(
    records: list[dict[str, Any]],
    days: int | None,
) -> list[dict[str, Any]]:
    if days is None:
        return records
    limit = days * 86400
    return [row for row in records if row.get("age_seconds", 1e18) <= limit]


def thread_jump_url(guild_id: int | str | None, thread_id: int | str | None) -> str:
    if guild_id is None or thread_id is None:
        return ""
    return f"https://discord.com/channels/{guild_id}/{thread_id}"


# One Discord button row. The list in the embed is the glance; these jump.
BUTTON_ROW = 5


def thread_button_specs(
    records: list[dict[str, Any]],
    *,
    guild_id: int | str | None,
    cap: int = BUTTON_ROW,
) -> list[dict[str, str]]:
    """Name-only jump links, same order as the list. No 'Open ·' prefix."""
    specs: list[dict[str, str]] = []
    for row in records[:cap]:
        action = likely_thread_action(row.get("state") or "")
        url = thread_jump_url(guild_id, row.get("thread_id"))
        if not action or not url:
            continue
        name = (row.get("name") or "eddy").strip() or "eddy"
        label = name if len(name) <= 80 else name[:77] + "…"
        specs.append({"label": label, "url": url, "action": action})
    return specs


def compose_thread_glance_body(
    records: list[dict[str, Any]],
    *,
    cap: int = SECTION_CAP,
) -> str:
    """One list, sidebar order. Title already holds the counts."""
    live = [row for row in records if row.get("state") == "live"]
    other = [row for row in records if row.get("state") and row.get("state") != "live"]
    lines = [row.get("line") or row.get("name") or "" for row in live[:cap]]
    omitted = max(0, len(live) - cap)
    if omitted:
        lines.append(f"… and {omitted} more in the sidebar")
    parked = sum(1 for row in other if row.get("state") == "resting")
    gone = sum(1 for row in other if row.get("state") == "gone")
    kept = sum(1 for row in other if row.get("state") in {"kept", "sealed"})
    extras = []
    if kept:
        extras.append(f"{kept} kept")
    if parked:
        extras.append(f"{parked} parked")
    if gone:
        extras.append(f"{gone} gone")
    if extras:
        lines.append("")
        lines.append(" · ".join(extras))
    return "\n".join(line for line in lines if line is not None).strip()


def waiting_title(records: list[dict[str, Any]]) -> str:
    n = len(records)
    return "Waiting — none" if n == 0 else f"Waiting — {n}"


def compose_waiting_body(
    records: list[dict[str, Any]],
    *,
    cap: int = SECTION_CAP,
) -> str:
    """One list. Whose move is the modifier. Acted and cold stay off."""
    if not records:
        return "Nothing is waiting for a session or a word."
    lines = [row.get("line") or row.get("name") or "" for row in records[:cap]]
    omitted = max(0, len(records) - cap)
    if omitted:
        lines.append(f"… and {omitted} more waiting")
    return "\n".join(line for line in lines if line).strip()


def threads_title(grouped: dict[str, list[str]], days: int | None) -> str:
    from eddy_five_state import five_state_title

    title = five_state_title(grouped)
    if days is None:
        return title
    if title.endswith("none"):
        return f"Eddies — none in the last {days}d"
    return f"{title} · last {days}d"


def river_window_counts(
    records: list[dict[str, Any]],
    days: int | None = WINDOW_DAYS,
) -> dict[str, int]:
    filtered = filter_records_by_days(records, days)
    counts = {name: 0 for name in FIVE_STATES}
    for row in filtered:
        state = row.get("state")
        if state in counts:
            counts[state] += 1
    return counts


def river_window_line(
    records: list[dict[str, Any]],
    days: int | None = WINDOW_DAYS,
    *,
    parent_name: str | None = None,
) -> str:
    """One line for Turtle. Counts only — names would be a recital."""
    counts = river_window_counts(records, days)
    live = counts["live"]
    window = f"the last {days} days" if days else "view"
    river = f"#{parent_name}" if parent_name else "This river"
    return (
        f"{river}: {live} live in {window}. "
        "survey_eddies opens the list. Do not recite it."
    )


CONTROL_LABELS = {
    "new_eddy": "new eddy",
    "threads": "threads",
    "artifacts": "artifacts",
}


def channel_menu_specs(controls: tuple[str, ...] | list[str]) -> list[dict[str, str]]:
    specs = []
    for key in controls:
        label = CONTROL_LABELS.get(key)
        if label:
            specs.append({"id": key, "label": label})
    return specs
