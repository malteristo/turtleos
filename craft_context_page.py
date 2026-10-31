"""The page the craft channel keeps for Spirit.

Pointers, not a second copy of the eddies. Highlights are what moved since
Spirit last prepared a decision surface. Standing work stays listed when it
has been quiet. Health and family are absent because this reads only the
practice it is given, and it runs only for a craft surface.

Intention pointers and channel remarks are files the practice may carry.
They are not inferred from eddy prose. A missing file is an empty band.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from core.atomic_io import atomic_write_text
from story_entries import EDDIES_SUBDIR, entry_from_front, parse_eddy_file_entries

PAGE_NAME = "craft-context.md"
SURFACE_LIMIT = 12
LOOKED_NAME = "craft-context-looked.txt"
INTENTIONS_NAME = "craft-intentions.yaml"
REMARKS_NAME = "craft-remarks.yaml"
_LINE_CAP = 160


@dataclass(frozen=True)
class IntentionPointer:
    name: str
    path: str
    passed: bool
    unbuilt: bool
    line: str


@dataclass(frozen=True)
class RemarkPointer:
    at: datetime
    pointer: str
    line: str


def practice_tz() -> ZoneInfo:
    return ZoneInfo(os.environ.get("PRACTICE_TIMEZONE", "Europe/Berlin"))


def _story(practice_dir: Path) -> Path:
    return practice_dir / "story"


def load_entries(practice_dir: Path, tz: ZoneInfo | None = None) -> list:
    """Latest checkpoint of each eddy under this practice. No other root."""
    tz = tz or practice_tz()
    eddies = practice_dir / EDDIES_SUBDIR
    if not eddies.is_dir():
        return []
    newest: dict[str, object] = {}
    for note_path in sorted(eddies.glob("*.md")):
        if note_path.name == PAGE_NAME:
            continue
        try:
            content = note_path.read_text(encoding="utf-8")
        except OSError:
            continue
        for front, body in parse_eddy_file_entries(content):
            entry = entry_from_front(front, body, note_path, tz)
            if entry is None:
                continue
            key = entry.thread or note_path.name
            held = newest.get(key)
            if held is None or entry.timestamp >= held.timestamp:
                newest[key] = entry
    return sorted(newest.values(), key=lambda entry: entry.timestamp, reverse=True)


def load_looked(practice_dir: Path, tz: ZoneInfo | None = None) -> datetime | None:
    tz = tz or practice_tz()
    path = _story(practice_dir) / LOOKED_NAME
    if not path.is_file():
        return None
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz)
    return parsed.astimezone(tz)


def load_intentions(practice_dir: Path) -> list[IntentionPointer]:
    path = _story(practice_dir) / INTENTIONS_NAME
    if not path.is_file():
        return []
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(loaded, list):
        return []
    intentions: list[IntentionPointer] = []
    for item in loaded:
        if not isinstance(item, dict) or not item.get("name") or not item.get("path"):
            continue
        intentions.append(
            IntentionPointer(
                name=str(item["name"]).strip(),
                path=str(item["path"]).strip(),
                passed=bool(item.get("passed")),
                unbuilt=bool(item.get("unbuilt")),
                line=_one_line(str(item.get("line") or "")),
            )
        )
    return intentions


def load_remarks(practice_dir: Path, tz: ZoneInfo | None = None) -> list[RemarkPointer]:
    tz = tz or practice_tz()
    path = _story(practice_dir) / REMARKS_NAME
    if not path.is_file():
        return []
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(loaded, list):
        return []
    remarks: list[RemarkPointer] = []
    for item in loaded:
        if not isinstance(item, dict) or not item.get("pointer"):
            continue
        try:
            at = datetime.fromisoformat(str(item.get("at") or "").strip())
        except ValueError:
            continue
        if at.tzinfo is None:
            at = at.replace(tzinfo=tz)
        remarks.append(
            RemarkPointer(
                at=at.astimezone(tz),
                pointer=str(item["pointer"]).strip(),
                line=_one_line(str(item.get("line") or "")),
            )
        )
    return remarks


def _one_line(text: str) -> str:
    flat = " ".join((text or "").split())
    for mark in (". ", "? ", "! "):
        cut = flat.find(mark)
        if cut != -1:
            flat = flat[: cut + 1]
            break
    if len(flat) > _LINE_CAP:
        return flat[: _LINE_CAP - 1].rstrip() + "…"
    return flat


def _rel(practice_dir: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(practice_dir.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _open_sparks(entry) -> list[str]:
    names: list[str] = []
    for spark in entry.sparks or []:
        if not isinstance(spark, dict):
            continue
        if str(spark.get("status") or "open") != "open":
            continue
        name = str(spark.get("name") or "").strip()
        if name:
            names.append(name)
    return names


def _eddy_line(practice_dir: Path, entry, last_look: datetime | None) -> str:
    moved = "yes" if last_look is not None and entry.timestamp > last_look else "no"
    if last_look is None:
        moved = "no previous look"
    sparks = _open_sparks(entry)
    spark_text = ", ".join(sparks) if sparks else "none"
    when = entry.timestamp.strftime("%Y-%m-%d %H:%M")
    about = _one_line(entry.body)
    return (
        f"- [{entry.title}]({_rel(practice_dir, entry.source_path)})"
        f" — {when} — since last look: {moved}"
        f" — open: {spark_text}"
        f" — {about}"
    )


def render_craft_context_page(
    practice_dir: Path,
    entries: list,
    intentions: list[IntentionPointer],
    remarks: list[RemarkPointer],
    last_look: datetime | None,
    *,
    updated: datetime,
) -> str:
    """The page. Eddy bodies beyond the one line are not included."""
    since_eddies = [
        entry
        for entry in entries
        if last_look is not None and entry.timestamp > last_look
    ]
    since_remarks = [
        remark
        for remark in remarks
        if last_look is not None and remark.at > last_look
    ]
    lines = [
        "# Craft context",
        "",
        f"Updated: {updated.isoformat(timespec='seconds')}",
        (
            f"Last look: {last_look.isoformat(timespec='seconds')}"
            if last_look is not None
            else "Last look: none"
        ),
        "",
        "## Since the last look",
        "",
    ]
    if last_look is None:
        lines.append("Spirit has not prepared a decision surface from this page yet.")
        lines.append("")
    elif not since_eddies and not since_remarks:
        lines.append("Nothing has moved since the last look.")
        lines.append("")
    else:
        for entry in since_eddies:
            lines.append(_eddy_line(practice_dir, entry, last_look))
        for remark in since_remarks:
            lines.append(
                f"- remark [{remark.pointer}] — {remark.at.strftime('%Y-%m-%d %H:%M')} — {remark.line}"
            )
        lines.append("")

    lines.extend(["## Standing", "", "### Eddies", ""])
    if not entries:
        lines.append("No eddies.")
        lines.append("")
    else:
        for entry in entries:
            lines.append(_eddy_line(practice_dir, entry, last_look))
        lines.append("")

    lines.extend(["### Sparks", ""])
    spark_rows = []
    for entry in entries:
        for spark in entry.sparks or []:
            if not isinstance(spark, dict):
                continue
            if str(spark.get("status") or "open") != "open":
                continue
            topic = str(spark.get("topic") or "unspecified").strip()
            name = str(spark.get("name") or "").strip()
            spark_rows.append(
                f"- {name} — {topic} — [{entry.title}]({_rel(practice_dir, entry.source_path)})"
            )
    lines.extend(spark_rows or ["No open sparks.", ""])
    if spark_rows:
        lines.append("")

    lines.extend(["### Intentions", ""])
    if not intentions:
        lines.append("No intention pointers on this page yet.")
        lines.append("")
    else:
        for item in intentions:
            state = []
            if item.passed:
                state.append("passed")
            if item.unbuilt:
                state.append("unbuilt")
            mark = ", ".join(state) if state else "held"
            lines.append(f"- [{item.name}]({item.path}) — {mark} — {item.line}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def refresh_craft_context_page(
    practice_dir: Path,
    *,
    updated: datetime | None = None,
    tz: ZoneInfo | None = None,
) -> Path:
    """Rewrite the page from this practice only. Returns the page path."""
    tz = tz or practice_tz()
    updated = updated or datetime.now(tz)
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=tz)
    story = _story(practice_dir)
    story.mkdir(parents=True, exist_ok=True)
    page = story / PAGE_NAME
    text = render_craft_context_page(
        practice_dir,
        load_entries(practice_dir, tz),
        load_intentions(practice_dir),
        load_remarks(practice_dir, tz),
        load_looked(practice_dir, tz),
        updated=updated,
    )
    atomic_write_text(page, text)
    return page


def _section(page: str, heading: str, until: str | None) -> str:
    start = page.find(heading)
    if start < 0:
        return ""
    start += len(heading)
    end = page.find(until, start) if until else -1
    body = page[start:] if end < 0 else page[start:end]
    return body.strip()


def _bullets(section: str) -> list[str]:
    return [line for line in section.splitlines() if line.startswith("- ")]


def decision_surface(page: str, *, limit: int = SURFACE_LIMIT) -> str:
    """What `...` prepares. The page keeps every pointer. Bodies stay out.

    A passed, unbuilt intention is the recommendation. The recent eddies are
    the standing work he can still choose. Older lines stay on the page.
    """
    since = _section(page, "## Since the last look", "## Standing")
    eddies = _section(page, "### Eddies", "### Sparks")
    intentions = _section(page, "### Intentions", None)
    since_bullets = _bullets(since)
    eddy_bullets = _bullets(eddies)
    intention_bullets = _bullets(intentions)

    lines = ["# Decision surface", ""]
    lines.append("## Since the last look")
    lines.append("")
    if since_bullets:
        shown = since_bullets[:limit]
        lines.extend(shown)
        hidden = len(since_bullets) - len(shown)
        if hidden:
            lines.append(f"- and {hidden} more that moved, on the page")
    else:
        lines.append(since.splitlines()[0] if since else "Nothing has moved since the last look.")
    lines.append("")

    lines.append("## Recent standing eddies")
    lines.append("")
    shown_eddies = eddy_bullets[:limit]
    lines.extend(shown_eddies or ["No eddies."])
    hidden_eddies = len(eddy_bullets) - len(shown_eddies)
    if hidden_eddies:
        lines.append(f"- and {hidden_eddies} older eddies, on the page")
    lines.append("")

    lines.append("## Intentions")
    lines.append("")
    lines.extend(intention_bullets or ["No intention pointers on this page yet."])
    lines.append("")

    waiting = next(
        (line for line in intention_bullets if "passed, unbuilt" in line),
        "",
    )
    lines.append("## Recommendation")
    lines.append("")
    if waiting:
        lines.append(waiting)
    else:
        lines.append("No passed description is waiting on the page.")
    lines.append("")
    return "\n".join(lines)


def mark_looked(practice_dir: Path, when: datetime | None = None, tz: ZoneInfo | None = None) -> Path:
    """Stamp the look. The next refresh highlights only what developed after it."""
    tz = tz or practice_tz()
    when = when or datetime.now(tz)
    if when.tzinfo is None:
        when = when.replace(tzinfo=tz)
    story = _story(practice_dir)
    story.mkdir(parents=True, exist_ok=True)
    path = story / LOOKED_NAME
    atomic_write_text(path, when.astimezone(tz).isoformat(timespec="seconds") + "\n")
    return path


def maintain_craft_context_page(practice_dir: Path, channel_id: int, uses_craft_surface) -> bool:
    """Refresh only when this channel is the craft surface. Other rooms write nothing.

    ``uses_craft_surface`` is the caller's (`mage.uses_craft_surface`); this module
    does not import `mage` (issue 053)."""
    if not uses_craft_surface(channel_id):
        return False
    refresh_craft_context_page(practice_dir)
    return True
