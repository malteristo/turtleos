"""Daily note writer — day-scale story synthesis (TURTLE_SPEC §6.5).

One reflection-class LLM call turns a day's eddy-note entries into 1–3
practitioner-facing paragraphs. Reads eddy bodies via
:func:`story_notes.collect_eddy_entries_for_date`, optional recent daily
notes for continuity, and an optional one-line alive snapshot. Writes
``story/daily/YYYY-MM-DD.md`` atomically.

Scheduled/catch-up triggers and river visibility (issues 040–041).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import yaml

from atomic_io import atomic_write_text
from helpers import local_now
from llm import chat_ollama
from mage import get_pd
from state import REFLECTION_MODEL
from story_notes import (
    EddyEntry,
    collect_eddy_entries_for_date,
    read_alive_snapshot,
)

DAILY_SUBDIR = Path("story") / "daily"

_NO_RESPONSE_SENTINEL = "(no response generated)"
_MIN_BODY_CHARS = 40
_RECENT_DAILY_COUNT = 3
_RECENT_DAILY_CHAR_BUDGET = 2400

_SYSTEM_PROMPT = (
    "You write short daily notes that tell a practitioner their own story "
    "back to them. You will see what each conversation held today, sometimes "
    "a few recent daily notes for continuity, and sometimes what is currently "
    "in motion for them.\n\n"
    "Write in plain, warm, everyday language — second person (\"you\"). "
    "Never use internal or technical vocabulary. No bullet lists of thread "
    "titles. Synthesize 1–3 short paragraphs that sound like their day: what "
    "moved, what connected, what was left open. Name a cross-eddy connection "
    "only when it is genuine; otherwise stay descriptive. Do not invent an arc."
)


class DailyNoteError(RuntimeError):
    """The synthesis produced no usable daily note — nothing was written."""


@dataclass
class DailyNoteResult:
    note_path: Path | None
    preview_text: str
    created: bool


def _daily_note_path(practice_dir: Path, target_date: date) -> Path:
    return practice_dir / DAILY_SUBDIR / f"{target_date.isoformat()}.md"


def _union_related_topics(entries: list[EddyEntry]) -> list[str]:
    seen: set[str] = set()
    topics: list[str] = []
    for entry in entries:
        for topic in entry.related_topics:
            key = topic.lower()
            if key not in seen:
                seen.add(key)
                topics.append(topic)
    return topics


def _alive_one_liner(practice_dir: Path) -> str | None:
    alive = read_alive_snapshot(practice_dir)
    labels: list[str] = []
    for t in alive.get("active_threads") or []:
        if isinstance(t, dict):
            label = (t.get("label") or t.get("id") or "").strip()
            if label:
                labels.append(label)
    for i in alive.get("intention_snapshot") or []:
        if isinstance(i, dict):
            name = (i.get("name") or "").strip()
            if name:
                labels.append(name)
    if not labels:
        return None
    return "Currently in motion for you: " + ", ".join(labels[:8])


def _recent_daily_context(practice_dir: Path, target_date: date) -> str:
    daily_dir = practice_dir / DAILY_SUBDIR
    if not daily_dir.is_dir():
        return ""

    parts: list[str] = []
    budget = _RECENT_DAILY_CHAR_BUDGET
    for offset in range(1, _RECENT_DAILY_COUNT + 1):
        prior = target_date - timedelta(days=offset)
        path = daily_dir / f"{prior.isoformat()}.md"
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            continue
        body = _daily_body_from_file(content)
        if not body:
            continue
        chunk = f"Daily note {prior.isoformat()}:\n{body.strip()}"
        if len(chunk) > budget:
            chunk = chunk[: budget - 3].rstrip() + "..."
        parts.append(chunk)
        budget -= len(chunk) + 2
        if budget <= 0:
            break
    return "\n\n".join(parts)


def _daily_body_from_file(content: str) -> str:
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            return content[end + 4 :].strip()
    return content.strip()


def _format_eddy_entries(entries: list[EddyEntry]) -> str:
    blocks: list[str] = []
    for entry in entries:
        header = entry.title or f"thread {entry.thread}"
        blocks.append(f"[{entry.timestamp.strftime('%H:%M')}] {header}\n{entry.body}")
    return "\n\n".join(blocks)


def _build_prompt(
    entries: list[EddyEntry],
    recent_dailies: str,
    alive_line: str | None,
    target_date: date,
) -> str:
    parts: list[str] = [f"DATE: {target_date.isoformat()}"]

    if recent_dailies:
        parts.append(
            "RECENT DAYS (continuity only — do not repeat verbatim; let today "
            f"build on or diverge):\n{recent_dailies}"
        )

    if alive_line:
        parts.append(alive_line)

    parts.append(
        "TODAY'S CONVERSATIONS (chronological — synthesize into one day story):\n"
        f"{_format_eddy_entries(entries)}"
    )
    return "\n\n".join(parts)


def _compose_daily_file(
    target_date: date, eddy_count: int, related_topics: list[str], body: str
) -> str:
    fields = {
        "date": target_date.isoformat(),
        "eddy_count": eddy_count,
        "related-topics": related_topics,
    }
    dumped = yaml.safe_dump(
        fields, sort_keys=False, allow_unicode=True, default_flow_style=None
    ).strip()
    return f"---\n{dumped}\n---\n\n{body.strip()}\n"


def _compose_preview(body: str) -> str:
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
    if paragraphs:
        return paragraphs[0]
    return body.strip()[:400]


async def write_daily_note(
    target_date: date,
    *,
    force: bool = False,
    practice_dir: Path | None = None,
) -> DailyNoteResult:
    """Synthesize and write the daily note for ``target_date``.

    Returns a result with ``created=False`` when there are no eddy entries
    (honest absence) or when the file already exists and ``force`` is false.
    """
    root = practice_dir if practice_dir is not None else Path(get_pd())
    note_path = _daily_note_path(root, target_date)

    entries = collect_eddy_entries_for_date(target_date, practice_dir=root)
    if not entries:
        return DailyNoteResult(note_path=None, preview_text="", created=False)

    if note_path.exists() and not force:
        body = _daily_body_from_file(note_path.read_text(encoding="utf-8"))
        return DailyNoteResult(
            note_path=note_path,
            preview_text=_compose_preview(body),
            created=False,
        )

    prompt = _build_prompt(
        entries,
        _recent_daily_context(root, target_date),
        _alive_one_liner(root),
        target_date,
    )

    raw = await chat_ollama(
        _SYSTEM_PROMPT,
        [{"role": "user", "content": prompt}],
        model=REFLECTION_MODEL,
        num_ctx=8192,
        think=False,
    )

    body = (raw or "").strip()
    if body == _NO_RESPONSE_SENTINEL or len(body) < _MIN_BODY_CHARS:
        raise DailyNoteError(
            f"daily synthesis failed the quality floor: {body[:80]!r}"
        )

    related_topics = _union_related_topics(entries)
    file_text = _compose_daily_file(
        target_date, len(entries), related_topics, body
    )

    note_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(note_path, file_text)

    return DailyNoteResult(
        note_path=note_path,
        preview_text=_compose_preview(body),
        created=True,
    )


def build_daily_note_surface(
    target_date: date, result: DailyNoteResult
) -> "ArtifactSurface | None":
    """River / !day preview surface (issue 041)."""
    import discord

    from artifact_presenter import ArtifactSurface, compose_artifact_preview_content
    from mage import get_pd

    if result.note_path is None:
        return None

    preview = None
    if result.preview_text.strip():
        preview = compose_artifact_preview_content(result.preview_text.strip())

    try:
        rel = result.note_path.relative_to(Path(get_pd())).as_posix()
    except ValueError:
        rel = None

    embed = discord.Embed(
        title="Daily note",
        description=f"**{target_date.isoformat()}** — your day in story",
        color=0x57F287,
    )
    open_actions: list[tuple[str, str]] = []
    if rel:
        open_actions.append(("Open note", f"!read {rel}"))

    return ArtifactSurface(
        template_id="post_daily_note",
        embed=embed,
        content=preview,
        open_actions=open_actions,
    )


async def post_daily_note_river_visibility(
    target_date: date, result: DailyNoteResult
) -> None:
    """Post daily note preview to the river after a fresh synthesis (issue 041)."""
    if not result.created or result.note_path is None:
        return

    from mage import _resolve_dialogue_channel_id

    channel_id = _resolve_dialogue_channel_id()
    if not channel_id:
        print("Daily note river post skipped — no dialogue channel")
        return

    surface = build_daily_note_surface(target_date, result)
    if surface is None:
        return

    try:
        from artifact_presenter import send_artifact_surface

        await send_artifact_surface(channel_id, surface, silent=False)
        print(f"Daily note posted to river: {result.note_path}")
    except Exception as exc:
        print(f"Daily note river post failed: {type(exc).__name__}: {exc}")


# ─── Triggers (issue 040) ──────────────────────────────────────────


async def run_scheduled_daily_note() -> DailyNoteResult | None:
    """Hourly scheduled path: after ``DAILY_NOTE_HOUR``, write today when material exists."""
    import state as _state
    from state import DAILY_NOTE_HOUR

    now = local_now()
    if now.hour < DAILY_NOTE_HOUR:
        return None

    today = now.date()
    key = today.isoformat()
    if _state.daily_note_scheduled_done == key:
        return None

    root = Path(get_pd())
    note_path = _daily_note_path(root, today)
    if note_path.exists():
        _state.daily_note_scheduled_done = key
        return None

    if not collect_eddy_entries_for_date(today, practice_dir=root):
        return None

    try:
        result = await write_daily_note(today, practice_dir=root)
    except DailyNoteError as exc:
        print(f"Daily note scheduled write failed: {exc}")
        return None

    if result.note_path is not None:
        _state.daily_note_scheduled_done = key
    if result is not None and result.created:
        await post_daily_note_river_visibility(today, result)
    return result


async def maybe_run_daily_note_catchup() -> DailyNoteResult | None:
    """Morning catch-up: before noon, synthesize yesterday if material exists."""
    import state as _state
    from datetime import timedelta

    now = local_now()
    if now.hour >= 12:
        return None

    yesterday = now.date() - timedelta(days=1)
    key = yesterday.isoformat()
    if _state.daily_note_catchup_done == key:
        return None

    root = Path(get_pd())
    if _daily_note_path(root, yesterday).exists():
        _state.daily_note_catchup_done = key
        return None

    if not collect_eddy_entries_for_date(yesterday, practice_dir=root):
        _state.daily_note_catchup_done = key
        return None

    _state.daily_note_catchup_done = key
    try:
        result = await write_daily_note(yesterday, practice_dir=root)
    except DailyNoteError as exc:
        _state.daily_note_catchup_done = None
        print(f"Daily note catch-up failed: {exc}")
        return None
    if result is not None and result.created:
        await post_daily_note_river_visibility(yesterday, result)
    return result
