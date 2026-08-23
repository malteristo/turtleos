"""Prepared-eddy sidecar — disposition stage status the registry must not own.

A prepared eddy pairs a Discord thread with a shared workspace. The bot's
thread registry is an in-memory cache that overwrites out-of-process writes, so
status lives here. Disposition is the return path the open half never had:

    open → ready → harvested

``open``      interview live; checkpoint may refresh the workspace
``ready``     determination recorded; Spirit harvests into bright / destinations
``harvested`` folded into the practice; workspace is history

Ordinary ``!dissolve`` on a prepared eddy marks ``ready`` and cools — it does
not LLM-essence into thread-archive. That would capture conversation and miss
the determination the surface was built to hold.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

SIDECAR = "thread-state/prepared_eddies.yaml"
DETERMINATION = "## Determination"
OPEN = "open"
READY = "ready"
HARVESTED = "harvested"
ABANDONED = "abandoned"

_DETERMINATION_BODY = re.compile(
    rf"^{re.escape(DETERMINATION)}\s*\n+(.*?)(?=\n## |\Z)",
    re.MULTILINE | re.DOTALL,
)


def sidecar_path(runtime_dir: str | Path) -> Path:
    return Path(runtime_dir) / SIDECAR


def load_sidecar(runtime_dir: str | Path) -> dict[str, Any]:
    path = sidecar_path(runtime_dir)
    if not path.is_file():
        return {"prepared": {}}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data.get("prepared"), dict):
        data["prepared"] = {}
    return data


def save_sidecar(runtime_dir: str | Path, data: dict[str, Any]) -> Path:
    path = sidecar_path(runtime_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    return path


def entry_for(runtime_dir: str | Path, thread_id: int) -> dict[str, Any] | None:
    entry = load_sidecar(runtime_dir).get("prepared", {}).get(str(thread_id))
    return entry if isinstance(entry, dict) else None


def disposition_of(runtime_dir: str | Path, thread_id: int) -> str | None:
    entry = entry_for(runtime_dir, thread_id)
    if not entry:
        return None
    raw = entry.get("disposition", OPEN)
    return raw if isinstance(raw, str) else OPEN


def surface_of(runtime_dir: str | Path, thread_id: int) -> str | None:
    entry = entry_for(runtime_dir, thread_id)
    if not entry:
        return None
    surface = entry.get("surface")
    if not isinstance(surface, str) or not surface.endswith(".md"):
        return None
    # Refuse absolute paths — same class as workspace_refresh.
    if surface.startswith("/") or ".." in Path(surface).parts:
        return None
    return surface


def list_by_disposition(runtime_dir: str | Path, disposition: str) -> list[tuple[str, dict]]:
    prepared = load_sidecar(runtime_dir).get("prepared") or {}
    out = []
    for tid, entry in prepared.items():
        if isinstance(entry, dict) and entry.get("disposition") == disposition:
            out.append((str(tid), entry))
    return out


def read_determination(text: str) -> str | None:
    match = _DETERMINATION_BODY.search(text or "")
    if not match:
        return None
    body = match.group(1).strip()
    return body or None


def ensure_determination(text: str, determination: str) -> str:
    """Insert or replace ## Determination. Leaves the rest of the file alone."""
    body = (determination or "").strip()
    if not body:
        raise ValueError("determination must not be empty")
    block = f"{DETERMINATION}\n\n{body}\n"
    if _DETERMINATION_BODY.search(text):
        return _DETERMINATION_BODY.sub(lambda _: block.rstrip() + "\n\n", text, count=1)
    # Prefer after Live state; else append.
    live = "## Live state"
    if live in text:
        head, rest = text.split(live, 1)
        match = re.search(r"^## ", rest[1:], re.MULTILINE)
        cut = match.start() + 1 if match else len(rest)
        return head + live + rest[:cut].rstrip() + "\n\n" + block + "\n" + rest[cut:].lstrip()
    return text.rstrip() + "\n\n" + block


def mark_ready(
    runtime_dir: str | Path,
    thread_id: int,
    *,
    determination: str,
    practice_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Write determination into the workspace and set disposition ready.

    Raises ValueError when the thread is not prepared, already harvested, or
    the workspace file is missing.
    """
    data = load_sidecar(runtime_dir)
    entry = data["prepared"].get(str(thread_id))
    if not isinstance(entry, dict):
        raise ValueError(f"thread {thread_id} is not a prepared eddy")
    current = entry.get("disposition", OPEN)
    if current == HARVESTED:
        raise ValueError(f"thread {thread_id} is already harvested")
    if current == ABANDONED:
        raise ValueError(f"thread {thread_id} was abandoned")

    surface = entry.get("surface")
    if not isinstance(surface, str) or not surface.endswith(".md"):
        raise ValueError(f"thread {thread_id} has no markdown surface")

    root = Path(practice_dir) if practice_dir is not None else Path(runtime_dir)
    workspace = root / surface
    if not workspace.is_file():
        raise ValueError(f"workspace missing: {surface}")

    text = workspace.read_text(encoding="utf-8")
    workspace.write_text(ensure_determination(text, determination), encoding="utf-8")

    one_liner = determination.strip().splitlines()[0].strip()
    if len(one_liner) > 240:
        one_liner = one_liner[:237].rstrip() + "..."

    entry["disposition"] = READY
    entry["ready_at"] = datetime.now(timezone.utc).isoformat()
    entry["determination_one_liner"] = one_liner
    data["prepared"][str(thread_id)] = entry
    save_sidecar(runtime_dir, data)
    return entry


def mark_harvested(runtime_dir: str | Path, thread_id: int) -> dict[str, Any]:
    data = load_sidecar(runtime_dir)
    entry = data["prepared"].get(str(thread_id))
    if not isinstance(entry, dict):
        raise ValueError(f"thread {thread_id} is not a prepared eddy")
    if entry.get("disposition") != READY:
        raise ValueError(
            f"thread {thread_id} disposition is {entry.get('disposition')!r}, want ready"
        )
    entry["disposition"] = HARVESTED
    entry["harvested_at"] = datetime.now(timezone.utc).isoformat()
    data["prepared"][str(thread_id)] = entry
    save_sidecar(runtime_dir, data)
    return entry
