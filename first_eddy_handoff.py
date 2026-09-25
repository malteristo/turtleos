"""River → Turtle file for the first message in a blank eddy.

Split-bot rule: River cannot call Turtle dialogue. Turtle is not a thread
member when that first message arrives, so the Turtle process never sees
MESSAGE_CREATE. This module is the file only — no mage, no Discord, no
dialogue. River writes; Turtle's watcher (dialogue_routing) fetches and
routes. Same shape as flow-bootstrap.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


HANDOFF_SUBDIR = "first-eddy-handoff"


def _handoff_dir(runtime_dir: str) -> Path:
    path = Path(runtime_dir) / "thread-state" / HANDOFF_SUBDIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_first_eddy_handoff(
    thread_id: int,
    parent_id: int,
    message_id: int,
    *,
    runtime_dir: str,
) -> Path:
    path = _handoff_dir(runtime_dir) / f"{int(thread_id)}.json"
    payload = {
        "thread_id": int(thread_id),
        "parent_id": int(parent_id),
        "message_id": int(message_id),
        "requested_at": datetime.now(timezone.utc).isoformat(),
    }
    text = json.dumps(payload, ensure_ascii=False)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass
    return path


def pop_first_eddy_handoff(
    thread_id: int,
    *,
    runtime_dir: str,
) -> dict | None:
    path = _handoff_dir(runtime_dir) / f"{int(thread_id)}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = None
    path.unlink(missing_ok=True)
    return data if isinstance(data, dict) else None


def list_first_eddy_handoffs(runtime_dirs: list[str]) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for runtime_dir in runtime_dirs:
        if runtime_dir in seen:
            continue
        seen.add(runtime_dir)
        handoff_dir = _handoff_dir(runtime_dir)
        for path in sorted(handoff_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and data.get("thread_id"):
                payload = dict(data)
                payload["_runtime_dir"] = runtime_dir
                out.append(payload)
    return out


def request_first_eddy_dialogue(message, *, runtime_dir: str) -> Path:
    """River: after rename + add Turtle, ask Turtle to answer this message."""
    thread = message.channel
    return write_first_eddy_handoff(
        thread.id, thread.parent_id, message.id, runtime_dir=runtime_dir
    )


def maybe_request_first_eddy_dialogue(
    message, *, renamed: bool, runtime_dir: str
) -> Path | None:
    if not renamed:
        return None
    return request_first_eddy_dialogue(message, runtime_dir=runtime_dir)
