"""The coding-delegate key: set from a modal, never shown to Spirit.

The house already has an Anthropic key for Spirit's own turns. This one is
separate: a spend-capped key the practitioner pastes once, for Pi (or the next
adapter) to spend. It lives in the house directory, mode 0600, next to the
other secrets the card and the channel never read.

Spirit's tool may ask whether it is set. `load_key` is for the driver that
starts a session, and is not a tool. A test plants a key and fails if the
status file, the tool result, or a modal reply carry it.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

MIN_LEN = 20
MAX_LEN = 400
KEY_NAME = "key"
STATUS_NAME = "status.json"
SET_REPLY = "The key is set. Spirit does not see it."
REFUSED = "That did not look like a key."

_pending = False


class Refused(ValueError):
    """A sentence the person can read. Never the value they typed."""


def house_dir() -> Path:
    override = os.environ.get("TURTLEOS_HOUSE_DIR")
    return Path(override) if override else Path(__file__).resolve().parent / "house"


def store_dir(root: Path | None = None) -> Path:
    return (root if root is not None else house_dir()) / "delegate"


def key_path(root: Path | None = None) -> Path:
    return store_dir(root) / KEY_NAME


def status_path(root: Path | None = None) -> Path:
    return store_dir(root) / STATUS_NAME


def _write_private(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.chmod(0o600)
    tmp.replace(path)


def put_key(raw: str, root: Path | None = None) -> None:
    key = (raw or "").strip()
    if not key or any(ch.isspace() for ch in key) or not (MIN_LEN <= len(key) <= MAX_LEN):
        raise Refused(REFUSED)
    _write_private(key_path(root), key + "\n")
    _write_private(
        status_path(root),
        json.dumps(
            {"set": True, "set_at": datetime.now(timezone.utc).isoformat(timespec="seconds")},
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
    )


def accept_key(raw: str, root: Path | None = None) -> str:
    put_key(raw, root)
    return SET_REPLY


def key_is_set(root: Path | None = None) -> bool:
    path = key_path(root)
    try:
        return path.is_file() and path.stat().st_size > 1
    except OSError:
        return False


def status(root: Path | None = None) -> dict:
    """What a card or a tool may say. A file with any other field is refused."""
    if not key_is_set(root):
        return {"set": False}
    try:
        data = json.loads(status_path(root).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {"set": True}
    if not isinstance(data, dict) or set(data) - {"set", "set_at"} or data.get("set") is not True:
        return {"set": True}
    return {"set": True, "set_at": data.get("set_at")}


def load_key(root: Path | None = None) -> str:
    """The key itself. Only the driver that starts a session may call this."""
    if not key_is_set(root):
        raise Refused("The coding-delegate key is not set.")
    return key_path(root).read_text(encoding="utf-8").strip()


def clear_key(root: Path | None = None) -> None:
    for path in (key_path(root), status_path(root)):
        try:
            path.unlink()
        except OSError:
            pass


def mark_offer() -> None:
    global _pending
    _pending = True


def take_offer() -> bool:
    global _pending
    ready, _pending = _pending, False
    return ready
