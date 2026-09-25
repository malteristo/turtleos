"""Eddy-note entry parsing — a leaf, on purpose.

The eddy note file format (front-matter per checkpoint entry, body after) is
read by the daily synthesiser, by room memory, by fresh-eyes, and by the
memory agent. It used to live in ``story_notes``, which sits inside the
runtime's mutual-dependency component (it imports the LLM, the registry, the
alive layer). Anything that wanted only to *read* notes had to join that
component to do so. This module imports yaml and the standard library and
nothing else, so a reader of notes can stay a leaf.

``story_notes`` re-exports these names; existing importers are unchanged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

EDDIES_SUBDIR = Path("story") / "eddies"


@dataclass
class EddyEntry:
    """One checkpoint entry from an eddy note file, ready for daily synthesis."""

    thread: str
    title: str
    trigger: str
    timestamp: datetime
    related_topics: list[str]
    body: str
    source_path: Path
    participants: list[str] = field(default_factory=list)
    proposed_themes: list[str] = field(default_factory=list)


_ENTRY_FRONT_RE = re.compile(r"---\n(.*?)---\n\n", re.S)


def parse_eddy_file_entries(content: str) -> list[tuple[dict, str]]:
    """Split an eddy note file into (front_matter, body) per checkpoint entry."""
    matches = list(_ENTRY_FRONT_RE.finditer(content))
    entries: list[tuple[dict, str]] = []
    for i, match in enumerate(matches):
        try:
            front = yaml.safe_load(match.group(1))
        except yaml.YAMLError:
            continue
        if not isinstance(front, dict):
            continue
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[match.end() : end].strip()
        entries.append((front, body))
    return entries


def entry_from_front(
    front: dict, body: str, source_path: Path, tz: ZoneInfo
) -> EddyEntry | None:
    timestamp_raw = front.get("timestamp")
    if not timestamp_raw:
        return None
    try:
        parsed_ts = datetime.fromisoformat(str(timestamp_raw).strip())
        if parsed_ts.tzinfo is None:
            parsed_ts = parsed_ts.replace(tzinfo=tz)
        else:
            parsed_ts = parsed_ts.astimezone(tz)
    except (TypeError, ValueError):
        return None

    topics = front.get("related-topics") or []
    if not isinstance(topics, list):
        topics = []
    related_topics = [str(t).strip() for t in topics if str(t).strip()]

    participants = front.get("participants") or []
    if not isinstance(participants, list):
        participants = []

    # Written on every checkpoint since the theme proposer shipped and, until
    # room memory read them, consumed by nothing. `related-topics` is the
    # field the schema advertises for this and it is empty in every entry on
    # the node; `proposed-themes` is the one that is actually populated.
    themes = front.get("proposed-themes") or []
    if not isinstance(themes, list):
        themes = []

    return EddyEntry(
        participants=[str(p).strip() for p in participants if str(p).strip()],
        proposed_themes=[str(t).strip() for t in themes if str(t).strip()],
        thread=str(front.get("thread") or "").strip(),
        title=str(front.get("title") or "").strip(),
        trigger=str(front.get("trigger") or "").strip(),
        timestamp=parsed_ts,
        related_topics=related_topics,
        body=body.strip(),
        source_path=source_path,
    )
