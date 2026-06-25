"""Cross-process signal: Turtle finished a dialogue turn (split-bot D3 + flow library)."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def _signals_dir() -> Path:
    from mage import get_runtime_dir

    path = Path(get_runtime_dir()) / "signals" / "turtle-turn"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _path_for(channel_id: int) -> Path:
    return _signals_dir() / f"{channel_id}.json"


def mark_turtle_turn_complete(channel_id: int, practitioner_message_id: int) -> None:
    """Turtle process: practitioner turn handled (prose sent or turn ended)."""
    path = _path_for(channel_id)
    payload = json.dumps(
        {"practitioner_message_id": int(practitioner_message_id)},
        ensure_ascii=False,
    )
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


def consume_turtle_turn_complete(
    channel_id: int,
    practitioner_message_id: int,
) -> bool:
    """River process: True when Turtle finished the matching practitioner turn."""
    path = _path_for(channel_id)
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        path.unlink(missing_ok=True)
        return False
    if not isinstance(data, dict):
        path.unlink(missing_ok=True)
        return False
    if int(data.get("practitioner_message_id", 0)) != int(practitioner_message_id):
        return False
    path.unlink(missing_ok=True)
    return True


def clear_turtle_turn_signal(channel_id: int | None = None) -> None:
    """Test helper — drop pending turn signals."""
    if channel_id is None:
        for path in _signals_dir().glob("*.json"):
            path.unlink(missing_ok=True)
        return
    _path_for(channel_id).unlink(missing_ok=True)
