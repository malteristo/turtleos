"""`!git` in the magic room: the list of what the workshop has not kept.

The step card names a write and does not carry the hunks. This is the list.
A line is a path and what happened to it. The diff is not here.
"""

from __future__ import annotations

import codecs
import subprocess
from pathlib import Path

_TEXT = {
    "en": {
        "elsewhere": "The workshop list is in #magic.",
        "missing": "This room has no workshop.",
        "unread": "Git could not read the workshop.",
        "on": "On {branch}",
        "clean": "Nothing is waiting to be kept.",
        "between": "{n} more between these.",
        "modified": "modified",
        "added": "added",
        "deleted": "deleted",
        "renamed": "renamed",
        "new": "new",
        "unmerged": "unmerged",
        "changed": "changed",
    },
    "de": {
        "elsewhere": "Die Liste der Werkstatt gibt es in #magic.",
        "missing": "Dieser Raum hat keine Werkstatt.",
        "unread": "Git konnte die Werkstatt nicht lesen.",
        "on": "Auf {branch}",
        "clean": "Es wartet nichts darauf, festgehalten zu werden.",
        "between": "{n} weitere dazwischen.",
        "modified": "geändert",
        "added": "hinzugefügt",
        "deleted": "gelöscht",
        "renamed": "umbenannt",
        "new": "neu",
        "unmerged": "im Konflikt",
        "changed": "verändert",
    },
}

# A glance keeps the start and the end. The middle is a count, not a fold
# that cannot be opened.
HEAD_KEEP = 12
TAIL_KEEP = 5
_LIMIT = 1900
_XY = set(" MADRCUT?!")


def _t(locale: str) -> dict:
    return _TEXT.get(locale) or _TEXT["en"]


def maintained_here(name: str | None) -> bool:
    return name == "magic"


def _unquote(path: str) -> str:
    path = path.strip()
    if len(path) >= 2 and path[0] == '"' and path[-1] == '"':
        try:
            return codecs.decode(path[1:-1], "unicode_escape")
        except UnicodeDecodeError:
            return path[1:-1]
    return path


def _state(xy: str, t: dict) -> str:
    if "?" in xy:
        return t["new"]
    if "U" in xy:
        return t["unmerged"]
    if "R" in xy or "C" in xy:
        return t["renamed"]
    if "D" in xy:
        return t["deleted"]
    if "A" in xy:
        return t["added"]
    if "M" in xy or "T" in xy:
        return t["modified"]
    return t["changed"]


def parse_status(text: str, *, locale: str = "en") -> tuple[str, list[tuple[str, str]]]:
    """Branch name, then (state, path) from `git status --short --branch`.

    A line that is not a status line is dropped. A diff hunk must not appear
    because this parser never asks for one, and it does not echo what it
    does not understand.
    """
    t = _t(locale)
    branch = ""
    rows: list[tuple[str, str]] = []
    for raw in (text or "").splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            branch = line[3:].split("...")[0].strip() or branch
            continue
        if len(line) < 4 or line[2] != " " or any(ch not in _XY for ch in line[:2]):
            continue
        xy, rest = line[:2], line[3:]
        if " -> " in rest:
            _old, new = rest.split(" -> ", 1)
            path = f"{_unquote(_old)} → {_unquote(new)}"
        else:
            path = _unquote(rest)
        if path:
            rows.append((_state(xy, t), path))
    return branch, rows


def render(text: str, *, locale: str = "en") -> str:
    t = _t(locale)
    branch, rows = parse_status(text, locale=locale)
    head = t["on"].format(branch=branch or "—")
    if not rows:
        return f"{head}\n{t['clean']}"
    lines = [f"{state}  {path}" for state, path in rows]
    if len(lines) > HEAD_KEEP + TAIL_KEEP:
        omitted = len(lines) - HEAD_KEEP - TAIL_KEEP
        lines = lines[:HEAD_KEEP] + [t["between"].format(n=omitted)] + lines[-TAIL_KEEP:]
    body = "\n".join([head, *lines])
    if len(body) <= _LIMIT:
        return body
    return body[: _LIMIT - 1] + "…"


def read_status(root: Path) -> str:
    """The short list. Never a diff."""
    done = subprocess.run(
        ["git", "-C", str(root), "status", "--short", "--branch"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if done.returncode != 0:
        raise OSError(done.stderr.strip() or "git status failed")
    return done.stdout


def reply_for(root: Path | None, *, locale: str = "en") -> str:
    t = _t(locale)
    if root is None:
        return t["missing"]
    try:
        return render(read_status(root), locale=locale)
    except (OSError, subprocess.TimeoutExpired):
        return t["unread"]
