"""Fresh Eyes — assemble a plain-language story surface for the flow (§10.2).

Writes ``state/notes/fresh-eyes-surface.md`` from alive threads, last-checkpoint
one-liner, recent eddy notes, and recent daily notes. Period notes are out of
MVP. Vocabulary firewall: never name internal layers in the surface text.
"""

from __future__ import annotations

import re
from pathlib import Path

from atomic_io import atomic_write_text
from continuity_engine import list_active_threads, read_current

SURFACE_REL = "state/notes/fresh-eyes-surface.md"
_MAX_EDDY_NOTES = 3
_MAX_DAILY_NOTES = 2
_MAX_BODY_CHARS = 400
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def _first_sentences(text: str, count: int = 2) -> str:
    flat = " ".join((text or "").split())
    if not flat:
        return ""
    parts = _SENTENCE_END.split(flat)
    return " ".join(parts[:count]).strip()


def _clip(text: str, limit: int = _MAX_BODY_CHARS) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _latest_eddy_blurb(path: Path) -> tuple[str, str]:
    """Return (title, blurb) from the newest entry in an eddy note file."""
    try:
        from story_notes import parse_eddy_file_entries
    except Exception:
        parse_eddy_file_entries = None  # type: ignore

    title = path.stem
    body = ""
    if parse_eddy_file_entries is not None:
        try:
            entries = parse_eddy_file_entries(path.read_text(encoding="utf-8"))
        except Exception:
            entries = []
        if entries:
            front, entry_body = entries[-1]
            if isinstance(front, dict) and front.get("title"):
                title = str(front["title"]).strip() or title
            body = entry_body or ""
    if not body:
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            raw = ""
        # Skip YAML front matter blocks if present.
        parts = raw.split("---")
        body = parts[-1] if len(parts) >= 3 else raw
    blurb = _first_sentences(body, 2) or _clip(body, 200)
    return title, blurb


def compose_fresh_eyes_surface(practice_dir: str | Path) -> str:
    """Pure composer — returns markdown for the Fresh Eyes surface."""
    pd = Path(practice_dir)
    lines: list[str] = [
        "# What's available to look at",
        "",
        "Shell-assembled for Fresh Eyes. Plain language only.",
        "",
        "## In motion",
    ]
    threads = list_active_threads(pd)
    if threads:
        for t in threads[:8]:
            label = str(t.get("label") or t.get("id") or "").strip()
            if not label:
                continue
            since = str(t.get("since") or "").strip()
            tone = str(t.get("tone") or "").strip()
            bits = [b for b in (f"since {since}" if since else "", tone) if b]
            suffix = f" ({'; '.join(bits)})" if bits else ""
            lines.append(f"- {label}{suffix}")
    else:
        lines.append("(nothing confirmed in motion yet)")

    lines.extend(["", "## Where you left off"])
    current = read_current(pd) or {}
    one = str(current.get("last_checkpoint_one_liner") or "").strip()
    if one:
        # One line only — reflection sometimes spills reasoning into the field.
        one_line = one.splitlines()[0].strip()
        lines.append(_clip(one_line, 280))
    else:
        lines.append("(no recent checkpoint note)")

    lines.extend(["", "## Recent conversation notes"])
    eddies_dir = pd / "story" / "eddies"
    eddy_files = (
        sorted(eddies_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        if eddies_dir.is_dir()
        else []
    )
    eddy_files = [p for p in eddy_files if not p.name.endswith(".lock")][:_MAX_EDDY_NOTES]
    if not eddy_files:
        lines.append("(no conversation notes yet)")
    else:
        for path in eddy_files:
            title, blurb = _latest_eddy_blurb(path)
            lines.append(f"### {title}")
            lines.append(_clip(blurb) if blurb else "(empty note)")
            lines.append("")

    lines.extend(["## Recent day notes"])
    daily_dir = pd / "story" / "daily"
    daily_files = (
        sorted(daily_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        if daily_dir.is_dir()
        else []
    )[:_MAX_DAILY_NOTES]
    if not daily_files:
        lines.append("(no day notes yet)")
    else:
        for path in daily_files:
            try:
                body = path.read_text(encoding="utf-8").strip()
            except OSError:
                body = ""
            lines.append(f"### {path.stem}")
            lines.append(_clip(body) if body else "(empty)")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def materialize_fresh_eyes_surface(practice_dir: str | Path) -> Path:
    """Write the Fresh Eyes surface under the practice root; return its path."""
    pd = Path(practice_dir)
    path = pd / SURFACE_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, compose_fresh_eyes_surface(pd))
    return path
