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

from core.atomic_io import atomic_write_text
from helpers import local_now
from llm import chat_ollama
from mage import current_practice_dir, get_pd, list_registered_practice_dirs
from state import REFLECTION_MODEL
from story_notes import (
    _NO_SECOND_PERSON_RULE,
    _PERCEPTION_RULE,
    _THIRD_PARTY_RULE,
    _TURTLE_VOICE_RULE,
    _practitioner_binding,
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
    "only when it is genuine; otherwise stay descriptive. Do not invent an arc.\n\n"
    f"{_TURTLE_VOICE_RULE} {_PERCEPTION_RULE} {_THIRD_PARTY_RULE}"
)


_WITNESS_SYSTEM_PROMPT = (
    "You write short daily notes recording a shared space's day for the "
    "people in it. You will see what each conversation held today, sometimes "
    "a few recent daily notes for continuity.\n\n"
    "Write in plain, warm, everyday language, in the THIRD PERSON. "
    f"{_NO_SECOND_PERSON_RULE} Name people and attribute what they brought to "
    "them; never merge two members into one voice.\n\n"
    f"{_TURTLE_VOICE_RULE}\n\n"
    f"{_PERCEPTION_RULE} Never use internal or technical vocabulary. No "
    "bullet lists of thread titles. Synthesize 1-3 short paragraphs that "
    "sound like the space's day: what moved, what connected, what was left "
    "open. Name a connection across conversations only when it is genuine; "
    "otherwise stay descriptive. Do not invent an arc."
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
        # INT-049: a note found defective is withdrawn from continuity without
        # being rewritten. The file stays exactly as it was written — a record
        # of what the system actually said, including its errors — and the
        # frontmatter carries why it is no longer fed forward. Amending the
        # prose instead would falsify the archive, which is the same move as
        # the defect: deciding after the fact whose account something was.
        if _daily_frontmatter(content).get("withdrawn"):
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


def _daily_frontmatter(content: str) -> dict:
    """Parse a daily note's frontmatter, tolerating malformed or absent blocks."""
    if not content.startswith("---"):
        return {}
    end = content.find("\n---", 3)
    if end == -1:
        return {}
    try:
        loaded = yaml.safe_load(content[3:end])
    except yaml.YAMLError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


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
    upcoming_dates: str | None = None,
    *,
    practitioner: str | None = None,
) -> str:
    parts: list[str] = [f"DATE: {target_date.isoformat()}"]

    # The daily synthesis sees only eddy bodies. Those are third-person by
    # construction when the eddy note named the practitioner, so without this
    # the referent for "you" has to be guessed from the material — which is
    # exactly how an operator's own river came to read "you followed <name>".
    # Solo roots only; the witness prompt bans second person.
    if practitioner:
        parts.append(_practitioner_binding(practitioner))

    if recent_dailies:
        parts.append(
            "RECENT DAYS (continuity only — do not repeat verbatim; let today "
            f"build on or diverge):\n{recent_dailies}"
        )

    if alive_line:
        parts.append(alive_line)

    if upcoming_dates:
        parts.append(
            "UPCOMING DATES (ambient — mention only when they color today's story):\n"
            f"{upcoming_dates.strip()}"
        )

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

    # Charter §3.3: above one member the record narrates in third person, so
    # that no member reads another's material as their own. The per-member
    # second-person rendering that used to derive from this record is gone —
    # it inverted whose day it was telling (INT-048), and the delivery it
    # existed for is withdrawn (per-member-periodic-notes.md §Delivery
    # withdrawn). This record is written and kept; retrieval reads it.
    from mage import space_members_for_practice_dir

    witness = len(space_members_for_practice_dir(root)) > 1

    # Resolve the practitioner from the *root being written for*, never from
    # the ambient channel context — the scheduler iterates every root, so the
    # ambient name belongs to whoever last spoke (INT-046's failure shape).
    practitioner = None
    if not witness:
        from mage import address_for_mage_key, registry_key_for_practice_dir

        key, kind = registry_key_for_practice_dir(root)
        if kind == "mage" and key:
            practitioner = address_for_mage_key(key)

    upcoming = ""
    try:
        from dates import render_upcoming_dates_context

        upcoming = render_upcoming_dates_context(root, today=target_date)
    except Exception:
        upcoming = ""

    prompt = _build_prompt(
        entries,
        _recent_daily_context(root, target_date),
        None if witness else _alive_one_liner(root),
        target_date,
        upcoming_dates=upcoming or None,
        practitioner=practitioner,
    )

    raw = await chat_ollama(
        _WITNESS_SYSTEM_PROMPT if witness else _SYSTEM_PROMPT,
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


def _practice_root_for_note(note_path: Path) -> Path:
    """The practice root that owns ``story/daily/<date>.md``."""
    return note_path.parent.parent.parent


def build_daily_note_surface(
    target_date: date, result: DailyNoteResult
) -> "ArtifactSurface | None":
    """River / !day preview surface (issue 041)."""
    import discord

    from artifact_presenter import ArtifactSurface, compose_artifact_preview_content

    if result.note_path is None:
        return None

    preview = None
    if result.preview_text.strip():
        preview = compose_artifact_preview_content(result.preview_text.strip())

    try:
        rel = result.note_path.relative_to(
            _practice_root_for_note(result.note_path)
        ).as_posix()
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
    """Post daily note preview to the owning river after a fresh synthesis.

    The target resolves from the note's own practice root (INT-042). Shared-space
    roots resolve to None and are not posted: a space's day is not one member's
    day, and publishing it to any single river misattributes every other
    member's material to the reader.
    """
    if not result.created or result.note_path is None:
        return

    from mage import river_channel_id_for_practice_dir

    root = _practice_root_for_note(result.note_path)
    channel_id = river_channel_id_for_practice_dir(root)
    if not channel_id:
        print(f"Daily note river post skipped — no owning river for {root}")
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


# ─── Triggers (issue 040; INT-046 root-explicit) ────────────────────


def _done_key(practice_dir: Path) -> str:
    """Stable per-root key for scheduled/catchup done maps."""
    return str(practice_dir.expanduser().resolve())


async def run_scheduled_daily_note(
    practice_dirs: list[Path | str] | None = None,
) -> DailyNoteResult | None:
    """Hourly scheduled path: after ``DAILY_NOTE_HOUR``, write today per root.

    INT-046: iterates registered practice roots explicitly. Never calls
    ``get_pd()`` — ambient context is unset in the background loop task.

    Family-dates reminders share this heartbeat (same root list) but are not
    gated on ``DAILY_NOTE_HOUR`` — done-keys provide once-per-lead idempotency.
    """
    from state import DAILY_NOTE_HOUR

    now = local_now()
    roots = (
        [Path(p) for p in practice_dirs]
        if practice_dirs is not None
        else [Path(p) for p in list_registered_practice_dirs()]
    )

    last: DailyNoteResult | None = None
    if now.hour >= DAILY_NOTE_HOUR:
        today = now.date()
        for root in roots:
            result = await _run_scheduled_daily_note_for_root(root, today)
            if result is not None:
                last = result

    try:
        from dates import run_scheduled_date_reminders

        await run_scheduled_date_reminders(practice_dirs=roots)
    except Exception as exc:
        print(f"Date reminders scheduled pass failed: {type(exc).__name__}: {exc}")

    return last


async def _run_scheduled_daily_note_for_root(
    root: Path, today: date
) -> DailyNoteResult | None:
    import state as _state

    key = today.isoformat()
    done_key = _done_key(root)
    if _state.daily_note_scheduled_done.get(done_key) == key:
        return None

    note_path = _daily_note_path(root, today)
    if note_path.exists():
        _state.daily_note_scheduled_done[done_key] = key
        return None

    if not collect_eddy_entries_for_date(today, practice_dir=root):
        return None

    try:
        result = await write_daily_note(today, practice_dir=root)
    except DailyNoteError as exc:
        print(f"Daily note scheduled write failed for {root}: {exc}")
        return None

    if result.note_path is not None:
        _state.daily_note_scheduled_done[done_key] = key
    if result is not None and result.created:
        await post_daily_note_river_visibility(today, result)
    return result


async def maybe_run_daily_note_catchup(
    practice_dir: Path | str | None = None,
) -> DailyNoteResult | None:
    """Morning catch-up: before noon, synthesize yesterday for one root.

    INT-046: requires an explicit ``practice_dir`` or an active practice
    context. Never falls back to the primary mage via ``get_pd()``.
    """
    import state as _state

    now = local_now()
    if now.hour >= 12:
        return None

    if practice_dir is not None:
        root = Path(practice_dir)
    else:
        ctx = current_practice_dir()
        if not ctx:
            return None
        root = Path(ctx)

    yesterday = now.date() - timedelta(days=1)
    key = yesterday.isoformat()
    done_key = _done_key(root)
    if _state.daily_note_catchup_done.get(done_key) == key:
        return None

    if _daily_note_path(root, yesterday).exists():
        _state.daily_note_catchup_done[done_key] = key
        return None

    if not collect_eddy_entries_for_date(yesterday, practice_dir=root):
        _state.daily_note_catchup_done[done_key] = key
        return None

    _state.daily_note_catchup_done[done_key] = key
    try:
        result = await write_daily_note(yesterday, practice_dir=root)
    except DailyNoteError as exc:
        _state.daily_note_catchup_done.pop(done_key, None)
        print(f"Daily note catch-up failed for {root}: {exc}")
        return None
    if result is not None and result.created:
        await post_daily_note_river_visibility(yesterday, result)
    return result
