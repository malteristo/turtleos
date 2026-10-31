"""One file in the house repo.

A forge turn can read it. The terminal stays closed to that turn, because a
command that only looks is still a command. A secret file and anything in
`.git` are refused. The audit names the act, not the text.
"""

from __future__ import annotations

from pathlib import Path

from house_terminal import house_repo
from workshop_tools import READ_MAX, Refused, audit, current, offered

_TOOL = {
    "type": "function",
    "function": {
        "name": "house_read",
        "description": (
            "Read one file in the house repo. path is relative to that repo. "
            "A secret file and .git are refused. A forge spirit can read."
        ),
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
}
NAMES = frozenset({"house_read"})


def handles(name: str) -> bool:
    return name in NAMES


def tools_offered() -> list[dict]:
    return [_TOOL] if offered() else []


def channel_line(name: str, args: dict | None = None) -> str | None:
    """The path. Never the text."""
    if name not in NAMES:
        return None
    path = str((args or {}).get("path") or "").strip().replace("\n", " ")
    if not path:
        return "read a house file"
    if len(path) > 120:
        path = path[:120] + "…"
    return f"read `{path}`"


def _held(rel: Path) -> bool:
    if ".git" in rel.parts:
        return True
    name = rel.name
    if name == ".env" or name.startswith(".env.") or name == "credentials.json":
        return True
    return rel.as_posix() == "delegate/key"


def _file(root: Path, raw: str) -> Path:
    text = raw.strip()
    if not text:
        raise Refused("Name the file.")
    root = root.resolve()
    candidate = Path(text)
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    try:
        rel = resolved.relative_to(root)
    except ValueError as exc:
        raise Refused("That file is not in the house.") from exc
    if _held(rel):
        raise Refused("That file is not one to read.")
    if not resolved.is_file():
        raise Refused("That file is not in the house.")
    return resolved


def _text(path: Path) -> str:
    try:
        body = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise Refused("That file is not text.") from exc
    if len(body) > READ_MAX:
        body = body[:READ_MAX] + f"\n… (cut at {READ_MAX} characters; ask for a range)"
    return body


def call(name: str, arguments: dict | None = None) -> str:
    if name not in NAMES:
        return "That tool is not available."
    args = arguments if isinstance(arguments, dict) else {}
    _registry, _channel, person = current()
    if not offered():
        audit(person, name, "refused")
        return "Not in this room."
    root = house_repo()
    if root is None:
        audit(person, name, "refused")
        return "The house repo is not here."
    try:
        path = _file(root, str(args.get("path") or ""))
        body = _text(path)
    except Refused as exc:
        audit(person, name, "refused")
        return str(exc)
    except OSError:
        audit(person, name, "failed")
        return "That did not work."
    audit(person, name, "called")
    return body
