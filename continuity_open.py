"""Continuity at eddy-open — load-path record plus the first exchange.

The inject packet (``turn_packet``) answers what a turn prepended. This file
answers two different questions: which twine dimensions the load path could
see, and what the first practitioner / Turtle pair was.

It does not score catch-up. That judgment is later, over the pair.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

DIMENSIONS = ("character", "relation", "context", "thread")

# Notes written before the writer shipped are not obligated.
RECORD_REQUIRED_AFTER = datetime(2026, 9, 13, 20, 0, tzinfo=timezone(timedelta(hours=2)))

_THREAD_RE = re.compile(r"^thread:\s*['\"]?(\d+)", re.MULTILINE)
_STAMP_RE = re.compile(r"^timestamp:\s*['\"]([^'\"]+)", re.MULTILINE)

_MIRROR_REL = "mirror.md"
_RESONANCE_REL = "resonance.md"


def record_path(practice_dir: str | Path, eddy_id: int | str) -> Path:
    return Path(practice_dir) / "state" / "continuity" / f"{eddy_id}.md"


def _nonempty(path: Path) -> bool:
    try:
        return path.is_file() and bool(path.read_text(encoding="utf-8").strip())
    except OSError:
        return False


def dimension_loads(practice_dir: str | Path, *, thread_loaded: bool) -> dict[str, str]:
    """What the load path can see. Not a claim that Turtle used the content.

    Character and relation follow ``prompts.build_discord_prompt`` (root
    ``mirror.md`` / ``resonance.md``). Context uses the same reader as the
    prompt (``practitioner_context``). Thread is the substrate packet.
    """
    from practitioner_context import practitioner_context_loaded

    root = Path(practice_dir)
    character = _nonempty(root / _MIRROR_REL)
    relation = _nonempty(root / _RESONANCE_REL)
    context = practitioner_context_loaded(root)
    return {
        "character": "loaded" if character else "not loaded",
        "relation": "loaded" if relation else "not loaded",
        "context": "loaded" if context else "not loaded — file absent",
        "thread": "loaded" if thread_loaded else "not loaded",
    }


def build_open_markdown(
    eddy_id: int | str,
    *,
    dimensions: dict[str, str],
    practitioner_text: str,
    turtle_text: str,
    recorded_at: datetime | None = None,
) -> str:
    when = (recorded_at or datetime.now().astimezone()).isoformat(timespec="seconds")
    lines = [
        "# Continuity at eddy-open",
        "",
        "Load path at first turn, plus the first exchange.",
        "Catch-up is not scored here.",
        "",
        f"Opened: {when}",
        f"Eddy: `{eddy_id}`",
        "",
        "## Dimensions loaded",
        "",
    ]
    for name in DIMENSIONS:
        lines.append(f"- {name}: {dimensions.get(name, 'not loaded')}")
    lines.extend(
        [
            "",
            "## First exchange",
            "",
            "### Practitioner",
            "",
            (practitioner_text or "").strip() or "(empty)",
            "",
            "### Turtle",
            "",
            (turtle_text or "").strip() or "(empty)",
            "",
        ]
    )
    return "\n".join(lines)


def persist_first_exchange(
    practice_dir: str | Path,
    eddy_id: int | str,
    *,
    practitioner_text: str,
    turtle_text: str,
    thread_loaded: bool,
    recorded_at: datetime | None = None,
) -> Path | None:
    """Write once. Later turns leave the first pair alone."""
    root = Path(practice_dir)
    if not root.is_dir():
        return None
    path = record_path(root, eddy_id)
    if path.is_file():
        return path
    body = build_open_markdown(
        eddy_id,
        dimensions=dimension_loads(root, thread_loaded=thread_loaded),
        practitioner_text=practitioner_text,
        turtle_text=turtle_text,
        recorded_at=recorded_at,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _note_stamp(text: str) -> datetime | None:
    match = _STAMP_RE.search(text)
    if not match:
        return None
    raw = match.group(1).strip()
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def completed_eddies_missing_record(
    practice_dir: str | Path,
    *,
    since: datetime = RECORD_REQUIRED_AFTER,
) -> list[str]:
    """Eddy notes after ``since`` that have no open record.

    An empty result is not evidence the writer runs — plant a note without a
    record and this must return that id.
    """
    notes = Path(practice_dir) / "story" / "eddies"
    if not notes.is_dir():
        return []
    missing: list[str] = []
    for path in sorted(notes.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        thread = _THREAD_RE.search(text)
        stamp = _note_stamp(text)
        if thread is None or stamp is None:
            continue
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=since.tzinfo)
        if stamp < since:
            continue
        eddy_id = thread.group(1)
        if not record_path(practice_dir, eddy_id).is_file():
            missing.append(eddy_id)
    return missing
