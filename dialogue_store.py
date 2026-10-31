"""Shared dialogue history for split-bot mode (Turtle writes, River reads on lifecycle acts)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from core.atomic_io import atomic_write_json
from state import MAX_DIALOGUE_HISTORY


def _dialogue_dir() -> Path:
    from mage import get_runtime_dir

    path = Path(get_runtime_dir()) / "dialogue"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _path_for(channel_id: int) -> Path:
    return _dialogue_dir() / f"{channel_id}.json"


def shared_dialogue_enabled() -> bool:
    try:
        from mage import river_bot_enabled

        return river_bot_enabled()
    except Exception:
        return False


def read_shared(channel_id: int) -> list[dict] | None:
    path = _path_for(channel_id)
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, list):
            return None
        return [entry for entry in data if isinstance(entry, dict)]
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return None


def write_shared(channel_id: int, history: list[dict]) -> None:
    trimmed = history[-MAX_DIALOGUE_HISTORY:] if len(history) > MAX_DIALOGUE_HISTORY else list(history)
    atomic_write_json(_path_for(channel_id), trimmed, ensure_ascii=False, indent=0)


def _lock_path(channel_id: int) -> Path:
    return _dialogue_dir() / f"{channel_id}.lock"


def begin_turn(channel_id: int) -> None:
    """A living process holds this file for the whole turn.

    The deploy guard treats a lock whose process is alive as a turn in flight,
    so the quiet gap can be the restart itself and not a half hour of silence.
    A failure here does not stop the turn: the guard then has only the file's age.
    """
    try:
        _lock_path(channel_id).write_text(str(os.getpid()), encoding="utf-8")
    except OSError:
        pass


def end_turn(channel_id: int) -> None:
    try:
        _lock_path(channel_id).unlink(missing_ok=True)
    except OSError:
        pass


def clear_shared(channel_id: int) -> None:
    path = _path_for(channel_id)
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
