"""What Boom Turtle may cite: topics, open sparks, intentions. Not their bodies.

A thought is related to this index. The paragraphs of the boom buffer, the text
of an intention, and the body of an eddy are not copied in. A missing file is
an empty band, said as empty.
"""

from __future__ import annotations

from pathlib import Path

# 106 open sparks on the house, 2026-10-15. Past this, the band says how many
# are unlisted, which is the sign to raise it. A silent cut would make a
# thought look untouched.
_CAP = 120


_SKIP_TOPICS = {"readme", "bright", "bright_archive"}


def _title(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    except (OSError, UnicodeDecodeError):
        return ""
    return ""


def _topics(boom: Path) -> list[str]:
    """Topic files under desk/boom/. The capture buffer's dump headings are not topics."""
    if not boom.is_dir():
        return []
    names = []
    for path in sorted(boom.glob("*.md")):
        if path.stem.lower() in _SKIP_TOPICS:
            continue
        names.append(_title(path) or path.stem)
    return names


def _intention_names(active: Path) -> list[str]:
    if not active.is_dir():
        return []
    names = []
    for path in sorted(active.glob("*.md")):
        name = ""
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.startswith("# "):
                    name = line[2:].strip()
                    break
        except (OSError, UnicodeDecodeError):
            continue
        names.append(name or path.stem)
    return names


def _spark_roots(workshop: Path | None, practice: Path | None) -> list[Path]:
    """Live notes sit at the practice root. The chronicle sits at desk/story."""
    roots = []
    if practice is not None and practice.is_dir():
        roots.append(practice)
    chronicle = workshop / "desk" if workshop is not None else None
    if chronicle is not None and chronicle.is_dir() and chronicle not in roots:
        roots.append(chronicle)
    return roots


def _spark_lines(workshop: Path | None, practice: Path | None) -> list[str]:
    from craft_context_page import load_entries

    lines = []
    seen = set()
    for root in _spark_roots(workshop, practice):
        for entry in load_entries(root):
            for spark in entry.sparks or []:
                if not isinstance(spark, dict):
                    continue
                if str(spark.get("status") or "open") != "open":
                    continue
                name = str(spark.get("name") or "").strip()
                topic = str(spark.get("topic") or "").strip()
                line = " — ".join(part for part in (name, topic) if part)
                if line and line not in seen:
                    seen.add(line)
                    lines.append(line)
    return lines


def _band(title: str, rows: list[str]) -> list[str]:
    shown = rows[:_CAP]
    lines = [f"### {title}", ""]
    if not shown:
        lines.append("None.")
    else:
        lines.extend(f"- {row}" for row in shown)
        if len(rows) > _CAP:
            lines.append(f"- and {len(rows) - _CAP} more")
    lines.append("")
    return lines


def render_index(workshop: Path | None, practice: Path | None = None) -> str:
    """Headings, open sparks, intention titles. A planted paragraph stays out."""
    topics: list[str] = []
    intentions: list[str] = []
    if workshop is not None:
        topics = _topics(workshop / "desk" / "boom")
        intentions = _intention_names(workshop / "desk" / "intentions" / "active")
    lines = [
        "## What a thought can touch",
        "",
        "Cite only what is listed. If a thought touches none of it, say so.",
        "",
    ]
    lines.extend(_band("Boom topics", topics))
    lines.extend(_band("Open sparks", _spark_lines(workshop, practice)))
    lines.extend(_band("Intentions", intentions))
    return "\n".join(lines).rstrip() + "\n"
