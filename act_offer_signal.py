"""Cross-process signal: Turtle proposes a River contextual act offer (split-bot).

Turtle writes; River validates allowlist and posts the button row.
Never parse Turtle prose for ``!`` — this file is the only Turtle→River offer channel.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterator

# Expand deliberately. `keep_date` is how a date said in words becomes a kept date
# (2026-10-14): Turtle understands the sentence, River draws the confirm button.
# `keep` and `ignore` are the same move for an eddy: "keep this one" and "do not
# remember this one" said in words, instead of typed `!keep` / `!ignore`.
ALLOWED_ACTIONS = frozenset({"checkpoint", "save", "keep_date", "keep", "ignore"})
KEEP_DATE_RECURRENCES = frozenset({"none", "yearly"})
KEEP_DATE_TITLE_MAX = 120

_URL_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)

# Trailer in Turtle reply (stripped before Discord). Not visible prose for River to parse.
_TRAILER_RE = re.compile(
    r"^\s*\[\[act-offer:\s*(?P<body>[^\]]+)\]\]\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Set for the duration of a Turtle dialogue tool loop (channel + practitioner msg).
_active_context: dict[str, int] | None = None


@dataclass(frozen=True)
class ActOfferIntent:
    action: str
    practitioner_message_id: int
    url: str | None = None
    reason: str = ""
    title: str | None = None
    when: str | None = None  # ISO date, keep_date only
    recurrence: str = "none"
    birth_year: int | None = None  # a birthday's birth year buys "turns N" on the reminder

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "action": self.action,
            "practitioner_message_id": int(self.practitioner_message_id),
        }
        if self.url:
            payload["url"] = self.url
        if self.reason:
            payload["reason"] = self.reason[:240]
        if self.action == "keep_date":
            payload["title"] = self.title
            payload["when"] = self.when
            payload["recurrence"] = self.recurrence
            if self.birth_year:
                payload["birth_year"] = self.birth_year
        return payload


def _signals_dir() -> Path:
    from mage import get_runtime_dir

    path = Path(get_runtime_dir()) / "signals" / "act-offers"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _path_for(channel_id: int) -> Path:
    return _signals_dir() / f"{channel_id}.json"


@contextmanager
def act_offer_turn_context(channel_id: int, practitioner_message_id: int) -> Iterator[None]:
    """Bind channel + practitioner message for offer_river_act tool calls."""
    global _active_context
    previous = _active_context
    _active_context = {
        "channel_id": int(channel_id),
        "practitioner_message_id": int(practitioner_message_id),
    }
    try:
        yield
    finally:
        _active_context = previous


def active_offer_context() -> dict[str, int] | None:
    return _active_context


def normalize_action(action: str) -> str | None:
    raw = (action or "").strip().lower()
    aliases = {
        "fetch": "save",
        "checkpoint": "checkpoint",
        "save": "save",
        "keep_date": "keep_date",
        "date": "keep_date",
        "keep": "keep",
        "ignore": "ignore",
    }
    mapped = aliases.get(raw)
    if mapped in ALLOWED_ACTIONS:
        return mapped
    return None


def validate_offer_args(
    action: str,
    *,
    url: str | None = None,
    title: str | None = None,
    when: str | None = None,
    recurrence: str | None = None,
    birth_year: Any = None,
) -> tuple[str | None, str | None]:
    """Return (normalized_action, error). error is None when valid."""
    kind = normalize_action(action)
    if not kind:
        return None, f"action must be one of: {', '.join(sorted(ALLOWED_ACTIONS))}"
    if kind == "keep_date":
        if not (title or "").strip():
            return None, "keep_date requires a title (what the date is)"
        try:
            date.fromisoformat((when or "").strip())
        except ValueError:
            return None, "keep_date requires `when` as an ISO date, YYYY-MM-DD"
        if (recurrence or "none").strip().lower() not in KEEP_DATE_RECURRENCES:
            return None, "keep_date recurrence must be 'none' or 'yearly'"
        if birth_year not in (None, ""):
            try:
                year = int(birth_year)
            except (TypeError, ValueError):
                return None, "keep_date birth_year must be a year"
            if not 1900 <= year <= date.today().year:
                return None, "keep_date birth_year must be a plausible year"
        return kind, None
    if kind == "save":
        u = (url or "").strip()
        if not u or not _URL_RE.match(u):
            return None, "save requires a valid http(s) url"
        return kind, None
    return kind, None


def propose_act_offer(
    channel_id: int,
    practitioner_message_id: int,
    action: str,
    *,
    url: str | None = None,
    reason: str = "",
    title: str | None = None,
    when: str | None = None,
    recurrence: str | None = None,
    birth_year: Any = None,
) -> ActOfferIntent:
    """Turtle process: write one pending offer for this eddy (overwrites prior)."""
    kind, err = validate_offer_args(
        action, url=url, title=title, when=when, recurrence=recurrence, birth_year=birth_year
    )
    if err or not kind:
        raise ValueError(err or "invalid offer")
    intent = ActOfferIntent(
        action=kind,
        practitioner_message_id=int(practitioner_message_id),
        url=(url or "").strip() if kind == "save" else None,
        reason=(reason or "").strip(),
        **_date_fields(kind, title, when, recurrence, birth_year),
    )
    path = _path_for(channel_id)
    payload = json.dumps(intent.to_payload(), ensure_ascii=False)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass
    return intent


def _date_fields(kind: str, title, when, recurrence, birth_year=None) -> dict[str, Any]:
    if kind != "keep_date":
        return {}
    return {
        "birth_year": int(birth_year) if birth_year not in (None, "") else None,
        "title": " ".join(str(title).split())[:KEEP_DATE_TITLE_MAX],
        "when": str(when).strip(),
        "recurrence": (recurrence or "none").strip().lower(),
    }


def propose_act_offer_from_tool(
    action: str,
    *,
    url: str | None = None,
    reason: str = "",
    title: str | None = None,
    when: str | None = None,
    recurrence: str | None = None,
    birth_year: Any = None,
) -> str:
    """Tool entry — uses act_offer_turn_context. Returns practitioner-facing status."""
    ctx = active_offer_context()
    if not ctx:
        return "Cannot offer a River act outside an active eddy dialogue turn."
    try:
        intent = propose_act_offer(
            ctx["channel_id"],
            ctx["practitioner_message_id"],
            action,
            url=url,
            reason=reason,
            title=title,
            when=when,
            recurrence=recurrence,
            birth_year=birth_year,
        )
    except ValueError as exc:
        return f"Offer rejected: {exc}"
    detail = intent.action
    if intent.url:
        detail = f"{intent.action} {intent.url}"
    if intent.action == "keep_date":
        detail = f"keep_date {intent.when} {intent.title}"
    return (
        f"Queued River act offer ({detail}). "
        "River will post a button after this reply — do not claim the button already appeared."
    )


def consume_act_offer(
    channel_id: int,
    practitioner_message_id: int,
) -> ActOfferIntent | None:
    """River process: take pending offer for this practitioner turn, if any."""
    path = _path_for(channel_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        path.unlink(missing_ok=True)
        return None
    if not isinstance(data, dict):
        path.unlink(missing_ok=True)
        return None
    if int(data.get("practitioner_message_id", 0)) != int(practitioner_message_id):
        return None
    path.unlink(missing_ok=True)
    kind, err = validate_offer_args(
        str(data.get("action", "")),
        url=data.get("url"),
        title=data.get("title"),
        when=data.get("when"),
        recurrence=data.get("recurrence"),
        birth_year=data.get("birth_year"),
    )
    if err or not kind:
        return None
    return ActOfferIntent(
        action=kind,
        practitioner_message_id=int(practitioner_message_id),
        url=(str(data["url"]).strip() if kind == "save" and data.get("url") else None),
        reason=str(data.get("reason") or "")[:240],
        **_date_fields(
            kind, data.get("title"), data.get("when"), data.get("recurrence"), data.get("birth_year")
        ),
    )


def clear_act_offer_signal(channel_id: int | None = None) -> None:
    """Test helper — drop pending act offers."""
    if channel_id is None:
        for path in _signals_dir().glob("*.json"):
            path.unlink(missing_ok=True)
        return
    _path_for(channel_id).unlink(missing_ok=True)


def parse_act_offer_trailer(reply: str) -> tuple[str, str | None, dict[str, Any] | None]:
    """Extract trailer from reply text.

    Returns (cleaned_reply, action, fields). fields is None when absent or invalid;
    for `save` it holds `url`, for `keep_date` it holds `when`, `recurrence`, `title`.

    Forms: ``checkpoint`` | ``save https://…`` | ``keep_date 2026-11-03 yearly Anna's birthday``
    (the recurrence word is optional).
    """
    if not reply:
        return reply, None, None
    match = None
    for candidate in _TRAILER_RE.finditer(reply):
        match = candidate
    if not match:
        return reply, None, None
    body = (match.group("body") or "").strip()
    parts = body.split(None, 1)
    action_raw = parts[0] if parts else ""
    rest = parts[1].strip() if len(parts) > 1 else ""
    cleaned = (reply[: match.start()] + reply[match.end() :]).rstrip()
    kind = normalize_action(action_raw)
    if kind == "keep_date":
        words = rest.split(None, 2)
        when = words[0] if words else ""
        recurrence = "none"
        title = " ".join(words[1:])
        if len(words) > 1 and words[1].lower() in KEEP_DATE_RECURRENCES:
            recurrence = words[1].lower()
            title = words[2] if len(words) > 2 else ""
        _, err = validate_offer_args(kind, title=title, when=when, recurrence=recurrence)
        if err:
            return cleaned, None, None
        return cleaned, kind, {"when": when, "recurrence": recurrence, "title": title}
    url = None
    if rest.lower().startswith("url="):
        url = rest[4:].strip().strip("'\"")
    elif rest:
        url = rest.strip().strip("'\"")
    kind, err = validate_offer_args(action_raw, url=url)
    if err or not kind:
        return cleaned, None, None
    return cleaned, kind, ({"url": url} if kind == "save" else {})


def extract_and_propose_from_reply(
    reply: str,
    channel_id: int,
    practitioner_message_id: int,
) -> tuple[str, ActOfferIntent | None]:
    """Strip trailer from reply; write signal when valid. For local (no-tools) models."""
    cleaned, action, fields = parse_act_offer_trailer(reply)
    if not action:
        return cleaned, None
    try:
        intent = propose_act_offer(channel_id, practitioner_message_id, action, **(fields or {}))
    except ValueError:
        return cleaned, None
    return cleaned, intent
