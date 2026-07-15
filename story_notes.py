"""Eddy note writer — the story layer's smallest unit (TURTLE_SPEC §6.5, §8.4).

At checkpoint, one reflection-class LLM call turns an eddy's conversation
into a short practitioner-facing note: what the conversation held, and —
only when something genuinely connects — how it relates to the threads and
intentions alive for the practitioner. No forced relations: when nothing
alive connects, the note says what the conversation held and stops.

One file per eddy under the practice root story surface
(``story/eddies/<thread-id>-<slug>.md``); each checkpoint appends a dated
entry with front matter (thread id, title, trigger, timestamp, related
topics). All writes go through the atomic primitive (issue 033); file
discovery and the read-append-write cycle are held under a per-eddy
``file_lock`` keyed on the channel id, so River and Turtle cannot
interleave entries or fork the note file on concurrent first checkpoints.

Degenerate model output (the chat_ollama no-response sentinel, too-short
replies, an empty held section) raises :class:`EddyNoteError` before any
write — the checkpoint caller decides how to degrade.

Relations read state surfaces only — the alive layer and the practitioner's
intention files under the same practice root — never other eddies'
transcripts. The composer layer enforces honesty a second time: a relation
the model names is kept only when it points at something actually alive.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from atomic_io import atomic_write_text, file_lock
from continuity_engine import read_alive
from helpers import local_now
from llm import chat_ollama
from mage import get_mage_name, get_pd, set_practice_context_for_channel
from state import REFLECTION_MODEL

EDDIES_SUBDIR = Path("story") / "eddies"

_HELD = "---HELD---"
_RELATION = "---RELATION---"
_TOPICS = "---RELATED-TOPICS---"
_END = "---END---"

_SYSTEM_PROMPT = (
    "You write short notes that tell a practitioner's story back to them. "
    "You will see one conversation they had, and sometimes a list of threads "
    "and intentions currently in motion for them.\n\n"
    "Write in plain, warm, everyday language. Never use internal or technical "
    "vocabulary — no system terms, no layer names. Say \"this conversation\", "
    "\"your thread about X\", \"your intention to X\".\n\n"
    "Answer in exactly this structure:\n"
    f"{_HELD}\n"
    "2-5 sentences: what this conversation held — what was talked about, what "
    "emerged, what was decided or left open.\n"
    f"{_RELATION}\n"
    "ONE sentence naming how this conversation connects to something in motion "
    "for the practitioner — ONLY if a genuine connection exists. Never force a "
    "relation: if nothing in motion truly connects, write exactly: none\n"
    f"{_TOPICS}\n"
    "The items from the in-motion list that the relation points at, one per "
    "line prefixed with \"- \". If you wrote none above, write exactly: none\n"
    f"{_END}"
)


_NO_RESPONSE_SENTINEL = "(no response generated)"
_MIN_REPLY_CHARS = 20  # legacy session-note floor: len(reflection.strip()) > 20


class EddyNoteError(RuntimeError):
    """The reflection produced no usable note — nothing was written.

    Raised before any file write when the model returns the chat_ollama
    no-response sentinel, a degenerate too-short reply, or an empty
    what-the-eddy-held section. The caller (issue 035) decides how to degrade.
    """


@dataclass
class EddyNoteResult:
    note_path: Path
    entry_text: str
    preview_text: str


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


_ENTRY_FRONT_RE = re.compile(r"---\n(.*?)---\n\n", re.S)


async def write_eddy_note(
    channel_id: int,
    history: list[dict],
    *,
    trigger: str,
    since_index: int | None = None,
) -> EddyNoteResult:
    """Write (or append to) the eddy's story note and return it with a preview.

    ``trigger == "manual"`` weights the reflection toward
    ``history[since_index:]`` — the exchanges since the last checkpoint.
    """
    set_practice_context_for_channel(channel_id)
    practice_dir = Path(get_pd())
    mage_name = get_mage_name()

    alive_items = _alive_items(practice_dir)
    prompt = _build_prompt(history, mage_name, alive_items, trigger, since_index)

    raw = await chat_ollama(
        _SYSTEM_PROMPT,
        [{"role": "user", "content": prompt}],
        model=REFLECTION_MODEL,
        num_ctx=8192,
        think=False,
    )

    # Quality floor (M1): chat_ollama never returns empty — it substitutes a
    # literal sentinel — so gate on the sentinel and on degenerate length
    # before anything can reach the practitioner-facing note file.
    reply = (raw or "").strip()
    if reply == _NO_RESPONSE_SENTINEL or len(reply) <= _MIN_REPLY_CHARS:
        raise EddyNoteError(f"reflection reply failed the quality floor: {reply[:80]!r}")

    held, relation, topics = _parse_response(reply)
    if not held.strip():
        raise EddyNoteError("reflection reply had an empty what-the-eddy-held section")
    relation, topics = _validate_relation(relation, topics, alive_items)

    title = _resolve_thread_title(channel_id)
    entry_text = _compose_entry(channel_id, title, trigger, held, relation, topics)

    # Per-eddy lock (keyed on channel id) held across discovery + append so
    # two concurrent first checkpoints cannot fork the eddy's note file.
    eddies_dir = practice_dir / EDDIES_SUBDIR
    with file_lock(eddies_dir / str(channel_id)):
        note_path = _note_path(practice_dir, channel_id, title)
        _append_entry(note_path, entry_text)

    return EddyNoteResult(
        note_path=note_path,
        entry_text=entry_text,
        preview_text=_compose_preview(held, relation),
    )


# ─── Alive context (read-only, same practice root) ───────────────────


def _alive_items(practice_dir: Path) -> list[str]:
    """Plain-language labels of what's in motion: alive threads, alive-layer
    intention snapshot, and intention files under the practice root."""
    items: list[str] = []
    alive = read_alive(practice_dir) or {}
    for t in alive.get("active_threads") or []:
        label = (t.get("label") or t.get("id") or "").strip() if isinstance(t, dict) else ""
        if label:
            items.append(label)
    for i in alive.get("intention_snapshot") or []:
        name = (i.get("name") or "").strip() if isinstance(i, dict) else ""
        if name:
            items.append(name)
    intentions_dir = practice_dir / "intentions"
    if intentions_dir.is_dir():
        for f in sorted(intentions_dir.glob("*.md")):
            items.append(f.stem.replace("-", " ").replace("_", " ").strip())
    seen: set[str] = set()
    unique = []
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


# ─── Prompt ──────────────────────────────────────────────────────────


def _transcript(history: list[dict], mage_name: str) -> str:
    return "\n".join(
        f"{mage_name if m.get('role') == 'user' else 'Turtle'}: {m.get('content', '')}"
        for m in history
    )


def _build_prompt(
    history: list[dict],
    mage_name: str,
    alive_items: list[str],
    trigger: str,
    since_index: int | None,
) -> str:
    parts: list[str] = []

    if alive_items:
        listing = "\n".join(f"- {item}" for item in alive_items)
        parts.append(
            "WHAT'S ALIVE FOR THE PRACTITIONER (threads and intentions in "
            "motion — relate ONLY to these, and only when the connection is "
            f"genuine):\n{listing}"
        )
    else:
        parts.append(
            "Nothing is currently listed as in motion for the practitioner — "
            "describe what the conversation held and stop; do not invent a "
            "connection."
        )

    weighted = (
        trigger == "manual"
        and since_index is not None
        and 0 < since_index < len(history)
    )
    if weighted:
        parts.append(
            "EARLIER IN THIS CONVERSATION (background only — do not center "
            f"the note on this):\n{_transcript(history[:since_index], mage_name)}"
        )
        parts.append(
            "SINCE THE LAST CHECKPOINT (the practitioner deliberately asked "
            "to capture now — write the note mainly about these exchanges):\n"
            f"{_transcript(history[since_index:], mage_name)}"
        )
    else:
        parts.append(f"THE CONVERSATION:\n{_transcript(history, mage_name)}")

    return "\n\n".join(parts)


# ─── Response parsing + honesty gate ─────────────────────────────────


def _section(raw: str, start: str, end: str) -> str | None:
    if start not in raw:
        return None
    body = raw.split(start, 1)[1]
    if end in body:
        body = body.split(end, 1)[0]
    return body.strip()


def _parse_response(raw: str) -> tuple[str, str | None, list[str]]:
    held = _section(raw, _HELD, _RELATION)
    if held is None:
        # Sentinels missing — degrade to treating the whole reply as the note.
        return raw.strip(), None, []

    relation = _section(raw, _RELATION, _TOPICS) or ""
    if relation.strip().lower() in ("", "none", "none."):
        relation = None

    topics: list[str] = []
    topics_body = _section(raw, _TOPICS, _END) or ""
    for line in topics_body.splitlines():
        line = line.strip().lstrip("-").strip()
        if line and line.lower() not in ("none", "none."):
            topics.append(line)
    return held, relation, topics


def _normalize_words(text: str) -> set[str]:
    """Lowercase, hyphens/underscores → spaces, strip punctuation, word set."""
    text = text.lower().replace("-", " ").replace("_", " ")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return set(text.split())


def _topic_matches_alive(topic: str, alive_item: str) -> bool:
    """Exact match or whole-word containment either way after normalization:
    'the health thread' matches alive 'health'; 'healthcare' does not."""
    topic_words = _normalize_words(topic)
    alive_words = _normalize_words(alive_item)
    if not topic_words or not alive_words:
        return False
    return alive_words <= topic_words or topic_words <= alive_words


def _validate_relation(
    relation: str | None, topics: list[str], alive_items: list[str]
) -> tuple[str | None, list[str]]:
    """Composer-layer honesty gate: a relation survives only when it points at
    something actually alive. Empty alive layer → no relation, ever.

    Surviving topics are emitted under their canonical alive-item names so
    downstream grouping (slice 2) matches the alive set. When some topics were
    dropped, the relation sentence must reference a survivor to be kept —
    otherwise the whole relation goes and the note stays descriptive."""
    if not alive_items or relation is None:
        return None, []

    kept: list[tuple[str, str]] = []  # (model's raw topic, canonical alive name)
    for topic in topics:
        for alive in alive_items:
            if _topic_matches_alive(topic, alive):
                if all(alive != canonical for _, canonical in kept):
                    kept.append((topic, alive))
                break
    if not kept:
        return None, []

    if len(kept) < len(topics):
        sentence_words = _normalize_words(relation)
        referenced = any(
            _normalize_words(canonical) <= sentence_words
            or _normalize_words(raw) <= sentence_words
            for raw, canonical in kept
        )
        if not referenced:
            return None, []

    return relation, [canonical for _, canonical in kept]


# ─── Note composition + storage ──────────────────────────────────────


def _slug(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (title or "").strip().lower()).strip("-")
    return slug or "eddy"


def _resolve_thread_title(channel_id: int) -> str:
    """Thread title from the registry, falling back to the live channel name."""
    try:
        from thread_registry import load_registry

        info = load_registry().get("threads", {}).get(str(channel_id))
        if info and info.get("name"):
            return str(info["name"])
    except Exception:
        pass
    try:
        from state import client

        channel = client.get_channel(channel_id)
        name = getattr(channel, "name", None)
        if name:
            return str(name)
    except Exception:
        pass
    return "eddy"


def _note_path(practice_dir: Path, channel_id: int, title: str) -> Path:
    """One file per eddy: reuse the existing note when present (survives
    retitles), otherwise name it from the current title."""
    eddies_dir = practice_dir / EDDIES_SUBDIR
    existing = sorted(eddies_dir.glob(f"{channel_id}-*.md"))
    if existing:
        return existing[0]
    return eddies_dir / f"{channel_id}-{_slug(title)}.md"


def _compose_entry(
    channel_id: int,
    title: str,
    trigger: str,
    held: str,
    relation: str | None,
    topics: list[str],
) -> str:
    fields = {
        "thread": str(channel_id),
        "title": title,
        "trigger": trigger,
        "timestamp": local_now().isoformat(timespec="seconds"),
        "related-topics": topics,
    }
    dumped = yaml.safe_dump(
        fields, sort_keys=False, allow_unicode=True, default_flow_style=None
    ).strip()
    front_matter = f"---\n{dumped}\n---"
    body = held.strip()
    if relation:
        body += f"\n\n{relation.strip()}"
    return f"{front_matter}\n\n{body}\n"


def _append_entry(note_path: Path, entry_text: str) -> None:
    """Read-append-write; the write itself is atomic. The caller holds the
    per-eddy ``file_lock`` across discovery and this append."""
    existing = ""
    if note_path.exists():
        existing = note_path.read_text(encoding="utf-8")
        if existing and not existing.endswith("\n"):
            existing += "\n"
        existing += "\n"
    atomic_write_text(note_path, existing + entry_text)


_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def _first_sentences(text: str, count: int = 2) -> str:
    flat = " ".join(text.split())
    sentences = _SENTENCE_END.split(flat)
    return " ".join(sentences[:count]).strip()


def _compose_preview(held: str, relation: str | None) -> str:
    """First sentences for the checkpoint reply surface (issue 036) — the
    relational sentence leads when present."""
    if relation:
        return f"{relation.strip()} {_first_sentences(held, 2)}".strip()
    return _first_sentences(held, 3)


# ─── Eddy file parsing + daily collector (issue 038) ───────────────


def read_alive_snapshot(practice_dir: Path) -> dict:
    """Read-only alive layer for story synthesis — shared with the eddy writer."""
    return read_alive(practice_dir) or {}


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


def _entry_from_front(
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

    return EddyEntry(
        thread=str(front.get("thread") or "").strip(),
        title=str(front.get("title") or "").strip(),
        trigger=str(front.get("trigger") or "").strip(),
        timestamp=parsed_ts,
        related_topics=related_topics,
        body=body.strip(),
        source_path=source_path,
    )


def collect_eddy_entries_for_date(
    target_date: date,
    *,
    practice_dir: Path | None = None,
) -> list[EddyEntry]:
    """Collect eddy-note entries whose local calendar date matches ``target_date``.

    Scans ``story/eddies/*.md`` under the practice root. Entries with missing
    or malformed front matter are **skipped** (not raised) so one bad checkpoint
    does not block daily synthesis. Returns an empty list when the eddies
    directory is missing or no entries match. Sorted chronologically within the
    day.
    """
    from state import PRACTICE_TIMEZONE

    root = practice_dir if practice_dir is not None else Path(get_pd())
    eddies_dir = root / EDDIES_SUBDIR
    if not eddies_dir.is_dir():
        return []

    tz = ZoneInfo(PRACTICE_TIMEZONE)
    collected: list[EddyEntry] = []
    for note_path in sorted(eddies_dir.glob("*.md")):
        content = note_path.read_text(encoding="utf-8")
        for front, body in parse_eddy_file_entries(content):
            entry = _entry_from_front(front, body, note_path, tz)
            if entry is None:
                continue
            if entry.timestamp.astimezone(tz).date() != target_date:
                continue
            collected.append(entry)

    collected.sort(key=lambda e: e.timestamp)
    return collected
