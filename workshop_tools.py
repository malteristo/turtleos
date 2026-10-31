"""Spirit's hands in the magic channel: read, search, edit, and keep a workshop.

The workshop is a git checkout the house owns (`mages.<person>.workshop.checkout`).
These tools work inside it and nowhere else, for the one person whose room it is.
They are offered only in a room that has the `workshop` capability, and every call
checks that again, so a tool listed in one room cannot be called from another.

What is refused, and why it is here and not in a prompt:

* a path outside the checkout, through `..` or a link, or anything inside `.git`;
* a write inside a nested repository (`circles/*`, `portals/*`): those are other
  people's records, and changing them is not this tool's to do;
* `git add` of anything but named files; a force push; any remote but the house's;
* a push of `main` until the registry says the house is its one writer;
* running anything that is not on the short list below;
* a write, an edit, a git verb, or a run during a forge turn: that spirit can look, and a change waits on him.

The terminal is not one of these tools. It lives in `house_terminal.py`.

The audit names the person, the act and the decision. It never holds content.
See docs/design/magic-port.md.
"""

from __future__ import annotations

import contextvars
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REMOTE = "turtle"  # the house's own bare repository; the only remote a push may name
AUDIT_NAME = "workshop_audit.jsonl"
READ_MAX = 60_000  # characters returned by one read
WRITE_MAX = 400_000
SEARCH_MAX_LINES = 60
SEARCH_FILE_MAX = 1_000_000
RUN_TIMEOUT = 120
OUTPUT_MAX = 8_000
BRANCH_OK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,60}$")
_NESTED = ("circles", "portals")

# name -> argv, relative to the checkout. Nothing else can be run.
RUNNABLE: dict[str, list[str]] = {
    "size_budget": ["{python}", "scripts/size_budget.py"],
    "public_surface_check": ["bash", "scripts/public_surface.sh", "--self-test"],
    "publish_dry_run": ["bash", "scripts/publish_public_magic.sh", "--dry-run"],
    "date": ["date", "+%A %Y-%m-%d %H:%M %Z"],
    # The arrival's read-only duties. Both only read the workshop (checked on the Mini
    # 2026-10-14); the first `...` in the room could not reach either and said so.
    "rot_radar": ["{python}", "scripts/rot_radar.py", "--quiet"],
    "practice_measures": ["{python}", "scripts/practice_ledger.py", "measures"],
}
GIT_READS = ("status", "diff", "log")
GIT_VERBS = (*GIT_READS, "add", "commit", "push", "branch")


class Refused(Exception):
    """Carries a sentence a person can read. Never a path outside the checkout's own."""


def _spec(name: str, description: str, properties: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required or []},
        },
    }


WORKSHOP_TOOLS = [
    _spec(
        "workshop_list",
        "List one directory of the workshop (names only; a trailing / is a folder). Default: the top.",
        {"path": {"type": "string", "description": "A folder inside the workshop, e.g. desk/intentions."}},
    ),
    _spec(
        "workshop_read",
        "Read one file of the workshop, optionally a range of lines.",
        {
            "path": {"type": "string"},
            "start_line": {"type": "integer", "description": "1-based first line. Default 1."},
            "max_lines": {"type": "integer", "description": "How many lines. Default all, up to the size limit."},
        },
        ["path"],
    ),
    _spec(
        "workshop_search",
        "Find lines in the workshop that contain a phrase (case-insensitive). Returns path:line: text.",
        {
            "query": {"type": "string"},
            "path": {"type": "string", "description": "Limit to a folder or file. Default the whole workshop."},
        },
        ["query"],
    ),
    _spec(
        "workshop_write",
        "Create or replace a whole file in the workshop. Prefer workshop_edit for a change to an existing file.",
        {"path": {"type": "string"}, "content": {"type": "string"}},
        ["path", "content"],
    ),
    _spec(
        "workshop_edit",
        "Replace one exact piece of text in a file with another. The old text must occur exactly once.",
        {"path": {"type": "string"}, "old": {"type": "string"}, "new": {"type": "string"}},
        ["path", "old", "new"],
    ),
    _spec(
        "workshop_git",
        "Keep the workshop. verb is one of: status, diff, log, add (name the files; never everything), "
        "commit (needs a message), push (to the house, current branch only), branch (start a new branch from here).",
        {
            "verb": {"type": "string", "enum": list(GIT_VERBS)},
            "paths": {"type": "array", "items": {"type": "string"}, "description": "For add, and to limit diff."},
            "message": {"type": "string", "description": "For commit."},
            "name": {"type": "string", "description": "For branch."},
        },
        ["verb"],
    ),
    _spec(
        "workshop_run",
        "Run one of the workshop's own checks. name is one of: " + ", ".join(sorted(RUNNABLE)) + ".",
        {"name": {"type": "string", "enum": sorted(RUNNABLE)}},
        ["name"],
    ),
]
NAMES = frozenset(str((t["function"])["name"]) for t in WORKSHOP_TOOLS)

# What the channel shows: the act and the object. Never the content.
_CHANNEL_NAMES = frozenset(
    {
        "workshop_list",
        "workshop_read",
        "workshop_search",
        "workshop_write",
        "workshop_edit",
        "workshop_git",
        "workshop_run",
    }
)


def handles(name: str) -> bool:
    return name in NAMES


def channel_line(name: str, args: dict | None = None) -> str | None:
    """The act and the object, for the trace. Never the file's content."""
    if name not in _CHANNEL_NAMES:
        return None
    args = args if isinstance(args, dict) else {}
    path = str(args.get("path") or "").strip()
    if name == "workshop_read":
        return f"read `{path}`" if path else "read a file"
    if name == "workshop_search":
        query = str(args.get("query") or "").strip()
        shown = query[:72] + ("…" if len(query) > 72 else "")
        where = f" in `{path}`" if path else ""
        return f'searched for "{shown}"{where}' if shown else "searched the workshop"
    if name == "workshop_list":
        return f"looked in `{path}`" if path else "looked in the workshop"
    if name == "workshop_write":
        return f"wrote `{path}`" if path else "wrote a file"
    if name == "workshop_edit":
        return f"edited `{path}`" if path else "edited a file"
    if name == "workshop_git":
        verb = str(args.get("verb") or "").strip()
        if verb in {"status", "diff", "log"}:
            return f"looked · {verb}"
        if verb in {"add", "commit", "push", "branch"}:
            return f"kept · {verb}"
        return "looked · git"
    if name == "workshop_run":
        check = str(args.get("name") or "").strip()
        return f"ran `{check}`" if check else "ran a check"
    return None


# ── Where, and for whom ────────────────────────────────────────────────


def _context() -> tuple[dict, object, str]:
    """The registry, the room and the asker, from the bound shell (as service_tools does)."""
    from outgoing_connections import _asker, shell

    bound = shell()
    if bound is None:
        return {}, None, ""
    try:
        registry = bound.registry()
    except Exception:
        registry = {}
    channel = None
    if bound.channel_id is not None:
        try:
            channel = bound.channel_id()
        except Exception:
            channel = None
    return registry, channel, _asker()


def _room_has_capability(registry: dict, channel) -> bool:
    if channel is None:
        return False
    try:
        from channel_primitives import resolve_primitive

        primitive = resolve_primitive(registry, channel)
    except Exception:
        return False
    return bool(primitive and primitive.has("workshop"))


def _shop(registry: dict, person: str) -> dict:
    info = ((registry or {}).get("mages") or {}).get(person)
    shop = info.get("workshop") if isinstance(info, dict) else None
    return shop if isinstance(shop, dict) else {}


def checkout_for(registry: dict, person: str) -> Path | None:
    """The person's workshop checkout, only if it is a real git working copy."""
    shop = _shop(registry, person)
    raw = str(shop.get("checkout") or "")
    if not raw:
        return None
    root = Path(os.path.expanduser(raw))
    return root if (root / ".git").exists() else None


def reading_checkout() -> Path | None:
    """The checkout of the room's owner, for a prompt that only reads.

    The workshop capability is what allows writing, and this does not check it.
    With no room bound, the caller uses the primary mage. This module does not
    import the mage hub to find that key.
    """
    registry, channel, _person = _context()
    if channel is None or not registry:
        return None
    from room_connections import owner_of

    key = owner_of(registry, channel)
    if not key:
        return None
    return checkout_for(registry, key)


def _asker_checkout(registry: dict, channel, person: str) -> Path | None:
    """The asker's checkout when they own this room. The room's capability is not consulted."""
    if not person:
        return None
    from room_connections import owner_of

    if owner_of(registry, channel) != person:
        return None
    return checkout_for(registry, person)


def current_checkout() -> Path | None:
    """The checkout for this room and asker, or None. The one test the prompt and the greeting share."""
    registry, channel, person = _context()
    if platform_turn():
        return _asker_checkout(registry, channel, person)
    if not person or not _room_has_capability(registry, channel):
        return None
    return _asker_checkout(registry, channel, person)


def room_checkout(channel_id, user_id=None) -> Path | None:
    """The checkout of a magic room, for a press of its button: the owner only, asker or not bound."""
    registry, _channel, _person = _context()
    if not _room_has_capability(registry, channel_id):
        return None
    from room_connections import owner_of

    owner = owner_of(registry, channel_id)
    if not owner:
        return None
    if user_id is not None:
        who = next(
            (k for k, v in ((registry or {}).get("mages") or {}).items()
             if isinstance(v, dict) and str(v.get("discord_id", "")) == str(user_id)),
            None,
        )
        if who != owner:
            return None
    return checkout_for(registry, owner)


def release_of(root: Path) -> str:
    """The short head of the checkout, with a mark when it holds changes not yet kept."""
    head = _git(root, "rev-parse", "--short", "HEAD").stdout.strip()
    if not head:
        return "unknown"
    dirty = bool(_git(root, "status", "--porcelain").stdout.strip())
    return head + ("+" if dirty else "")


def offered() -> bool:
    """True when this room, this asker, and this house have a workshop to work in.

    A home has no workshop capability. A platform session in the owner's home
    is the exception, and only for the turn that was marked at open.
    """
    registry, channel, person = _context()
    if platform_turn():
        return _asker_checkout(registry, channel, person) is not None
    if not person or not _room_has_capability(registry, channel):
        return False
    return _asker_checkout(registry, channel, person) is not None


def tools_offered() -> list[dict]:
    return list(WORKSHOP_TOOLS) if offered() else []


# ── Paths ──────────────────────────────────────────────────────────────


def _inside(root: Path, rel: str, *, write: bool) -> Path:
    rel = (rel or "").strip()
    if rel.startswith(("/", "~")) or "\x00" in rel:
        raise Refused("A path is inside the workshop, written from its top.")
    parts = Path(rel).parts
    if ".." in parts or ".git" in parts:
        raise Refused("That is not a place Spirit works in.")
    target = (root / rel).resolve()
    top = root.resolve()
    if target != top and top not in target.parents:
        raise Refused("That is outside the workshop.")
    if ".git" in target.relative_to(top).parts:
        raise Refused("That is not a place Spirit works in.")
    if write:
        first = target.relative_to(top).parts[:1]
        if first and first[0] in _NESTED:
            raise Refused("That folder holds other people's records. Spirit reads it and does not write to it.")
        probe = target
        while probe != top:
            if (probe / ".git").exists():
                raise Refused("That is another repository's. Spirit does not write to it.")
            probe = probe.parent
    return target


def _rel(root: Path, target: Path) -> str:
    return str(target.relative_to(root.resolve())) or "."


# ── The tools ──────────────────────────────────────────────────────────


def _list(root: Path, args: dict) -> str:
    target = _inside(root, str(args.get("path") or ""), write=False)
    if not target.is_dir():
        raise Refused("That is not a folder in the workshop.")
    names = sorted(
        (p.name + ("/" if p.is_dir() else "")) for p in target.iterdir() if p.name != ".git"
    )
    return "\n".join(names) or "(empty)"


def _read(root: Path, args: dict) -> str:
    target = _inside(root, str(args.get("path") or ""), write=False)
    if not target.is_file():
        raise Refused("That is not a file in the workshop.")
    try:
        text = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise Refused("That file is not text.")
    lines = text.splitlines()
    start = max(int(args.get("start_line") or 1), 1)
    count = args.get("max_lines")
    chosen = lines[start - 1 : (start - 1 + int(count)) if count else None]
    body = "\n".join(chosen)
    if len(body) > READ_MAX:
        body = body[:READ_MAX] + f"\n… (cut at {READ_MAX} characters; ask for a range)"
    return body or "(empty)"


def _search(root: Path, args: dict) -> str:
    query = str(args.get("query") or "").strip().lower()
    if not query:
        raise Refused("A search needs words.")
    base = _inside(root, str(args.get("path") or ""), write=False)
    files = [base] if base.is_file() else sorted(p for p in base.rglob("*") if p.is_file())
    top = root.resolve()
    hits: list[str] = []
    for path in files:
        if ".git" in path.relative_to(top).parts or path.stat().st_size > SEARCH_FILE_MAX:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(lines, 1):
            if query in line.lower():
                hits.append(f"{path.relative_to(top)}:{number}: {line.strip()[:200]}")
                if len(hits) >= SEARCH_MAX_LINES:
                    return "\n".join(hits) + f"\n… (first {SEARCH_MAX_LINES}; narrow the path)"
    return "\n".join(hits) or "No line contains that."


def _write(root: Path, args: dict) -> str:
    target = _inside(root, str(args.get("path") or ""), write=True)
    content = str(args.get("content") if args.get("content") is not None else "")
    if len(content) > WRITE_MAX:
        raise Refused("That is too large for one write.")
    if target.is_dir():
        raise Refused("That is a folder.")
    existed = target.exists()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"{'Replaced' if existed else 'Created'} {_rel(root, target)} ({len(content)} characters)."


def _edit(root: Path, args: dict) -> str:
    target = _inside(root, str(args.get("path") or ""), write=True)
    if not target.is_file():
        raise Refused("That file is not in the workshop.")
    old, new = str(args.get("old") or ""), str(args.get("new") if args.get("new") is not None else "")
    if not old:
        raise Refused("An edit names the text it replaces.")
    text = target.read_text(encoding="utf-8")
    found = text.count(old)
    if found != 1:
        raise Refused("The old text occurs " + ("nowhere" if not found else f"{found} times") + " in that file; it must occur once.")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")
    return f"Edited {_rel(root, target)}."


def _git_env() -> dict:
    env = {k: v for k, v in os.environ.items() if k in {"PATH", "HOME", "LANG", "LC_ALL"}}
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def _git(root: Path, *argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *argv],
        capture_output=True,
        text=True,
        timeout=RUN_TIMEOUT,
        env=_git_env(),
    )


def _clip(text: str) -> str:
    text = (text or "").strip()
    return text if len(text) <= OUTPUT_MAX else text[:OUTPUT_MAX] + "\n… (cut)"


def _branch(root: Path) -> str:
    return _git(root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()


def _main_writable(registry: dict, person: str) -> bool:
    return _shop(registry, person).get("main_writable") is True


def _git_tool(root: Path, args: dict, registry: dict, person: str) -> str:
    verb = str(args.get("verb") or "")
    if verb not in GIT_VERBS:
        raise Refused("That is not something Spirit does to the workshop.")
    paths = [str(p) for p in (args.get("paths") or [])]
    if verb == "status":
        return _clip(_git(root, "status", "--short", "--branch").stdout) or "Clean."
    if verb == "log":
        return _clip(_git(root, "log", "--oneline", "-n", "15").stdout)
    if verb == "diff":
        for p in paths:
            _inside(root, p, write=False)
        return _clip(_git(root, "diff", "--stat", "--", *paths).stdout) or "No changes."
    if verb == "add":
        if not paths:
            raise Refused("Say which files. Spirit does not add everything.")
        for p in paths:
            if p.strip() in {".", "*", ""} or any(ch in p for ch in "*?[") or p.startswith("-"):
                raise Refused("Name each file. Spirit does not add everything.")
            _inside(root, p, write=True)
        done = _git(root, "add", "--", *paths)
        if done.returncode:
            raise Refused("Git would not add that.")
        return f"Staged {len(paths)} file(s)."
    if verb == "branch":
        name = str(args.get("name") or "")
        if not BRANCH_OK.match(name) or name in {"main", "master"}:
            raise Refused("A branch name is plain words, and not main.")
        done = _git(root, "switch", "-c", name)
        if done.returncode:
            raise Refused("Git would not start that branch.")
        return f"On branch {name}."
    if verb == "commit":
        message = str(args.get("message") or "").strip()
        if not message:
            raise Refused("A commit needs a message.")
        if _git(root, "diff", "--cached", "--quiet").returncode == 0:
            raise Refused("Nothing is staged.")
        done = _git(root, "commit", "-m", message)
        if done.returncode:
            raise Refused("Git would not commit. " + _clip(done.stderr)[:200])
        return _clip(done.stdout)
    # push
    branch = _branch(root)
    if branch in {"main", "master"} and not _main_writable(registry, person):
        raise Refused("The house is not yet the only writer to main. Start a branch and push that.")
    if not branch or branch == "HEAD":
        raise Refused("There is no branch to push.")
    done = _git(root, "push", REMOTE, f"{branch}:{branch}")
    if done.returncode:
        raise Refused("The push did not go through. " + _clip(done.stderr)[:200])
    return f"Pushed {branch} to the house."


def _run(root: Path, args: dict) -> str:
    name = str(args.get("name") or "")
    template = RUNNABLE.get(name)
    if template is None:
        raise Refused("That is not one of the workshop's checks.")
    python = shutil.which("python3") or sys.executable
    argv = [part.replace("{python}", python) for part in template]
    try:
        done = subprocess.run(
            argv,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=RUN_TIMEOUT,
            env=_git_env(),
        )
    except subprocess.TimeoutExpired:
        raise Refused("That check did not finish in time.")
    out = _clip((done.stdout or "") + (("\n" + done.stderr) if done.returncode else ""))
    return f"{out}\n(exit {done.returncode})" if done.returncode else out


# ── The door ───────────────────────────────────────────────────────────


def _audit_to(runtime: Path | None, person: str, operation: str, decision: str) -> None:
    if runtime is None:
        return
    path = runtime / "state" / AUDIT_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "person": person,
            "operation": operation,
            "decision": decision,
        },
        ensure_ascii=False,
    )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


# A forge turn may look. It does not change the workshop: that still waits on him.
_FORGE_TURN: contextvars.ContextVar[bool] = contextvars.ContextVar("workshop_forge_turn", default=False)
FORGE_HOLDS = frozenset({"workshop_write", "workshop_edit", "workshop_git", "workshop_run"})
FORGE_HELD = "A forge spirit does not change the workshop. This turn can look. A change waits on him."


def set_forge_turn(active: bool):
    return _FORGE_TURN.set(bool(active))


def reset_forge_turn(token) -> None:
    _FORGE_TURN.reset(token)


def forge_active() -> bool:
    return bool(_FORGE_TURN.get())


# A platform session is one thread in the owner's home. The home room itself
# does not have the workshop. The turn sets this; the file on disk is what
# tells the turn to set it. Another member's home never sets it.
_PLATFORM_TURN: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "workshop_platform_turn", default=False
)


def set_platform_turn(active: bool):
    return _PLATFORM_TURN.set(bool(active))


def reset_platform_turn(token) -> None:
    _PLATFORM_TURN.reset(token)


def platform_turn() -> bool:
    return bool(_PLATFORM_TURN.get())


def current() -> tuple[dict, object, str]:
    """The registry, the room and the asker, for a tool that shares this door."""
    return _context()


def audit(person: str, operation: str, decision: str) -> None:
    """Record the act. The line never holds the command or the file."""
    from outgoing_connections import _runtime_root

    _audit_to(_runtime_root(), person, operation, decision)


def call(name: str, arguments: dict | None = None) -> str:
    """Run one tool. Checked again here, in this room, for this asker."""
    if name not in NAMES:
        return "That tool is not available."
    args = arguments if isinstance(arguments, dict) else {}
    registry, channel, person = _context()
    from outgoing_connections import _runtime_root

    runtime = _runtime_root()
    if not offered():
        _audit_to(runtime, person, name, "refused")
        return "Not in this room."
    if _FORGE_TURN.get() and name in FORGE_HOLDS:
        _audit_to(runtime, person, name, "refused")
        return FORGE_HELD
    root = checkout_for(registry, person)
    assert root is not None  # offered() said so
    try:
        if name == "workshop_list":
            body = _list(root, args)
        elif name == "workshop_read":
            body = _read(root, args)
        elif name == "workshop_search":
            body = _search(root, args)
        elif name == "workshop_write":
            body = _write(root, args)
        elif name == "workshop_edit":
            body = _edit(root, args)
        elif name == "workshop_git":
            body = _git_tool(root, args, registry, person)
        else:
            body = _run(root, args)
    except Refused as exc:
        _audit_to(runtime, person, name, "refused")
        return str(exc)
    except (OSError, subprocess.SubprocessError, ValueError):
        _audit_to(runtime, person, name, "failed")
        return "That did not work."
    _audit_to(runtime, person, name, "called")
    return body
