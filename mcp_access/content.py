"""Readers over a source's own files. Paths are confined to the source root."""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from mcp_access.registry import KIND_SUBJECT, Source
from story_entries import entry_from_front, parse_eddy_file_entries

_NOTE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,200}$")
HEALTH_PICTURE = "health_model.md"
SNIPPET = 240


def _tz() -> ZoneInfo:
    return ZoneInfo(os.environ.get("PRACTICE_TIMEZONE", "Europe/Berlin"))


def _eddies(source: Source) -> Path:
    return source.root / "story" / "eddies"


def available(source: Source) -> bool:
    return source.root.is_dir()


def list_notes(source: Source) -> list[dict]:
    """One row per note file: id, title, last entry time. Newest first."""
    d = _eddies(source)
    if not d.is_dir():
        return []
    rows = []
    for path in d.glob("*.md"):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        entries = [
            e
            for front, body in parse_eddy_file_entries(text)
            if (e := entry_from_front(front, body, path, _tz())) is not None
        ]
        if not entries:
            continue
        last = max(entries, key=lambda e: e.timestamp)
        rows.append({"id": path.stem, "title": last.title, "last": last.timestamp.isoformat()})
    rows.sort(key=lambda r: r["last"], reverse=True)
    return rows


def read_note(source: Source, note_id: str) -> str | None:
    if not _NOTE_ID.match(note_id or ""):
        return None
    base = _eddies(source).resolve()
    path = (base / f"{note_id}.md").resolve()
    if path.parent != base or not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def read_health_picture(source: Source) -> str | None:
    if source.kind != KIND_SUBJECT:
        return None
    path = source.root / HEALTH_PICTURE
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def search(sources: list[Source], query: str, limit: int = 20) -> list[dict]:
    needle = (query or "").strip().lower()
    if not needle:
        return []
    hits: list[dict] = []
    for source in sources:
        for row in list_notes(source):
            text = read_note(source, row["id"]) or ""
            i = text.lower().find(needle)
            if i >= 0:
                hits.append(
                    {
                        "ref": f"turtleos://room/{source.id}/note/{row['id']}",
                        "title": row["title"],
                        "last": row["last"],
                        "snippet": _snippet(text, i, len(needle)),
                    }
                )
        picture = read_health_picture(source)
        if picture:
            i = picture.lower().find(needle)
            if i >= 0:
                hits.append(
                    {
                        "ref": f"turtleos://health/{source.id}/picture",
                        "title": "health picture",
                        "last": _mtime(source.root / HEALTH_PICTURE),
                        "snippet": _snippet(picture, i, len(needle)),
                    }
                )
    hits.sort(key=lambda h: h["last"] or "", reverse=True)
    return hits[:limit]


def _snippet(text: str, i: int, n: int) -> str:
    start = max(0, i - SNIPPET // 2)
    return " ".join(text[start : i + n + SNIPPET // 2].split())


def _mtime(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
    except OSError:
        return None


def brief(sources: list[Source], *, expires: str, refused_since_brief: int) -> str:
    """The system's own account of what this connection reaches. Honest when broken."""
    lines = ["# turtleOS brief", ""]
    if not sources:
        lines.append("This connection reaches no sources.")
    for source in sources:
        label = "health (you are the subject)" if source.kind == KIND_SUBJECT else "private room"
        lines.append(f"## {source.id} — {label}")
        if not available(source):
            lines.append("- **unavailable:** this source's folder is missing on the host.")
            lines.append("")
            continue
        notes = list_notes(source)
        if notes:
            lines.append(f"- last activity: {notes[0]['last']}")
            lines.append("- recent conversations:")
            lines.extend(f"  - {n['title'] or n['id']} ({n['last'][:10]})" for n in notes[:5])
        else:
            lines.append("- no conversation notes yet")
        if source.kind == KIND_SUBJECT:
            has_picture = (source.root / HEALTH_PICTURE).is_file()
            lines.append(f"- health picture: {'present' if has_picture else 'none yet'}")
        lines.append("")
    lines.append("## Integrity")
    lines.append(f"- this grant expires: {expires}")
    if refused_since_brief:
        lines.append(f"- **refused calls since the last brief: {refused_since_brief}**")
    else:
        lines.append("- refused calls since the last brief: 0")
    lines.append(
        "- whatever you read here is sent to the model your client uses; that is your choice."
    )
    return "\n".join(lines)
