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
from pathlib import Path
from typing import Any, Iterator

# Slice 1 allowlist — expand deliberately.
ALLOWED_ACTIONS = frozenset({"checkpoint", "save"})

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

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "action": self.action,
            "practitioner_message_id": int(self.practitioner_message_id),
        }
        if self.url:
            payload["url"] = self.url
        if self.reason:
            payload["reason"] = self.reason[:240]
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
    aliases = {"fetch": "save", "checkpoint": "checkpoint", "save": "save"}
    mapped = aliases.get(raw)
    if mapped in ALLOWED_ACTIONS:
        return mapped
    return None


def validate_offer_args(action: str, *, url: str | None = None) -> tuple[str | None, str | None]:
    """Return (normalized_action, error). error is None when valid."""
    kind = normalize_action(action)
    if not kind:
        return None, f"action must be one of: {', '.join(sorted(ALLOWED_ACTIONS))}"
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
) -> ActOfferIntent:
    """Turtle process: write one pending offer for this eddy (overwrites prior)."""
    kind, err = validate_offer_args(action, url=url)
    if err or not kind:
        raise ValueError(err or "invalid offer")
    intent = ActOfferIntent(
        action=kind,
        practitioner_message_id=int(practitioner_message_id),
        url=(url or "").strip() if kind == "save" else None,
        reason=(reason or "").strip(),
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


def propose_act_offer_from_tool(
    action: str,
    *,
    url: str | None = None,
    reason: str = "",
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
        )
    except ValueError as exc:
        return f"Offer rejected: {exc}"
    detail = intent.action
    if intent.url:
        detail = f"{intent.action} {intent.url}"
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
    )
    if err or not kind:
        return None
    return ActOfferIntent(
        action=kind,
        practitioner_message_id=int(practitioner_message_id),
        url=(str(data["url"]).strip() if kind == "save" and data.get("url") else None),
        reason=str(data.get("reason") or "")[:240],
    )


def clear_act_offer_signal(channel_id: int | None = None) -> None:
    """Test helper — drop pending act offers."""
    if channel_id is None:
        for path in _signals_dir().glob("*.json"):
            path.unlink(missing_ok=True)
        return
    _path_for(channel_id).unlink(missing_ok=True)


def parse_act_offer_trailer(reply: str) -> tuple[str, str | None, str | None]:
    """Extract trailer from reply text.

    Returns (cleaned_reply, action, url). action/url are None when absent or invalid.
    """
    if not reply:
        return reply, None, None
    match = None
    for candidate in _TRAILER_RE.finditer(reply):
        match = candidate
    if not match:
        return reply, None, None
    body = (match.group("body") or "").strip()
    # Forms: "checkpoint" | "save https://…" | "save url=https://…"
    parts = body.split(None, 1)
    action_raw = parts[0] if parts else ""
    rest = parts[1].strip() if len(parts) > 1 else ""
    url = None
    if rest.lower().startswith("url="):
        url = rest[4:].strip().strip("'\"")
    elif rest:
        url = rest.strip().strip("'\"")
    kind, err = validate_offer_args(action_raw, url=url)
    cleaned = (reply[: match.start()] + reply[match.end() :]).rstrip()
    if err or not kind:
        return cleaned, None, None
    return cleaned, kind, url if kind == "save" else None


def extract_and_propose_from_reply(
    reply: str,
    channel_id: int,
    practitioner_message_id: int,
) -> tuple[str, ActOfferIntent | None]:
    """Strip trailer from reply; write signal when valid. For local (no-tools) models."""
    cleaned, action, url = parse_act_offer_trailer(reply)
    if not action:
        return cleaned, None
    try:
        intent = propose_act_offer(
            channel_id,
            practitioner_message_id,
            action,
            url=url,
        )
    except ValueError:
        return cleaned, None
    return cleaned, intent
