"""The house spirit's terminal on this machine.

One command, in the house repo or the workshop. A forge turn cannot run it,
including a command that only looks. Restarting the house and forceful git are
refused before a process starts. A secret file cannot be read from the command:
the process is sandboxed, and when the sandbox is missing the command does not
run. The audit names the act, not the command.

Stopping the bot by its process number is not refused. The command is kept in
the session, which is the record. A blocklist of pids would not hold.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from workshop_tools import (
    OUTPUT_MAX,
    RUN_TIMEOUT,
    Refused,
    audit,
    checkout_for,
    current,
    forge_active,
    offered,
)

TIMEOUT = RUN_TIMEOUT
COMMAND_MAX = 2_000
FORGE_HELD = "A forge spirit does not have the terminal."
RESTART = "Restarting the house waits for a quiet window."
FORCE = "Forceful git waits."

_SPLIT = {"|", "||", "&&", ";", "&"}
_SHELLS = {"bash", "sh", "zsh", "dash", "env"}
_HELD = {"launchctl", "restart.sh"}

# sandbox-exec is the mechanism. The string screen is the sentence the spirit
# reads; a command that disguises the same act still hits the profile.
PROFILE = r"""
(version 1)
(allow default)
(deny file-read*
    (regex #"/\.env$")
    (regex #"/\.env\.[^/]*$")
    (regex #"/credentials\.json$")
    (regex #"/delegate/key$"))
(deny process-exec
    (regex #"/restart\.sh$")
    (literal "/bin/launchctl")
    (literal "/usr/bin/launchctl"))
""".strip()

_TOOL = {
    "type": "function",
    "function": {
        "name": "house_terminal",
        "description": (
            "Run one command on this machine. where is house (the turtleOS repo) or workshop. "
            "Restarting the house, reading a secret, and forceful git are refused. "
            "A forge spirit cannot run this."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "where": {"type": "string", "enum": ["house", "workshop"]},
            },
            "required": ["command"],
        },
    },
}
NAMES = frozenset({"house_terminal"})


def handles(name: str) -> bool:
    return name in NAMES


def tools_offered() -> list[dict]:
    return [_TOOL] if offered() else []


def channel_line(name: str, args: dict | None = None) -> str | None:
    """The command, clipped. Never its output."""
    if name not in NAMES:
        return None
    command = str((args or {}).get("command") or "").strip().replace("\n", " ")
    if len(command) > 120:
        command = command[:120] + "…"
    return f"ran `{command}`" if command else "ran a command"


def house_repo() -> Path | None:
    raw = os.environ.get("TURTLEOS_REPO") or str(Path.home() / "turtleos")
    root = Path(os.path.expanduser(raw)).resolve()
    return root if (root / ".git").exists() else None


def _name(token: str) -> str:
    return Path(token).name


def _groups(command: str) -> list[list[str]]:
    try:
        parts = shlex.split(command, posix=True)
    except ValueError as exc:
        raise Refused("That command could not be read.") from exc
    groups: list[list[str]] = []
    current: list[str] = []
    for part in parts:
        if part in _SPLIT:
            if current:
                groups.append(current)
                current = []
        else:
            current.append(part)
    if current:
        groups.append(current)
    return groups


def _expand(command: str, depth: int = 0) -> list[list[str]]:
    groups = _groups(command)
    if depth >= 3:
        return groups
    found = list(groups)
    for argv in groups:
        for arg in argv[1:]:
            if any(mark in arg for mark in (" ", ";", "|", "&")):
                found.extend(_expand(arg, depth + 1))
    return found


def _forced(argv: list[str]) -> bool:
    if _name(argv[0]) != "git":
        return False
    rest = argv[1:]
    force = any(a == "--force" or a.startswith("--force=") or a == "--force-with-lease" for a in rest)
    if "push" in rest and (force or "-f" in rest):
        return True
    if "reset" in rest and "--hard" in rest:
        return True
    if "clean" in rest and (force or "-f" in rest or "-fd" in rest):
        return True
    return False


def _screen(command: str) -> None:
    if not command.strip():
        raise Refused("Name the command.")
    if len(command) > COMMAND_MAX:
        raise Refused("That command is too long.")
    for argv in _expand(command):
        if not argv:
            continue
        head = _name(argv[0])
        if head in _HELD:
            raise Refused(RESTART)
        if head in _SHELLS and any(_name(arg) in _HELD for arg in argv[1:]):
            raise Refused(RESTART)
        if _forced(argv):
            raise Refused(FORCE)


def _cwd(where: str, registry: dict, person: str) -> Path:
    chosen = (where or "house").strip()
    if chosen == "workshop":
        root = checkout_for(registry, person)
        if root is None:
            raise Refused("The workshop is not on this machine.")
        return root
    if chosen == "house":
        root = house_repo()
        if root is None:
            raise Refused("The house repo is not on this machine.")
        return root
    raise Refused("where is house or workshop.")


def _clip(text: str) -> str:
    text = (text or "").strip()
    return text if len(text) <= OUTPUT_MAX else text[:OUTPUT_MAX] + "\n… (cut)"


def _run(command: str, cwd: Path) -> str:
    sandbox = shutil.which("sandbox-exec")
    if sandbox is None or sys.platform != "darwin":
        raise Refused("The terminal is not available on this machine.")
    env = {k: os.environ[k] for k in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR") if os.environ.get(k)}
    env.setdefault("PATH", "/usr/bin:/bin:/usr/sbin:/sbin")
    try:
        done = subprocess.run(
            [sandbox, "-p", PROFILE, "/bin/bash", "-c", command],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise Refused("That command did not finish in time.") from exc
    out = (done.stdout or "") + (("\n" + done.stderr) if done.returncode else "")
    body = _clip(out)
    return f"{body}\n(exit {done.returncode})" if done.returncode else body


def call(name: str, arguments: dict | None = None) -> str:
    if name not in NAMES:
        return "That tool is not available."
    args = arguments if isinstance(arguments, dict) else {}
    registry, _channel, person = current()
    if not offered():
        audit(person, name, "refused")
        return "Not in this room."
    if forge_active():
        audit(person, name, "refused")
        return FORGE_HELD
    try:
        command = str(args.get("command") or "")
        _screen(command)
        cwd = _cwd(str(args.get("where") or ""), registry, person)
        body = _run(command, cwd)
    except Refused as exc:
        audit(person, name, "refused")
        return str(exc)
    except (OSError, subprocess.SubprocessError, ValueError):
        audit(person, name, "failed")
        return "That did not work."
    audit(person, name, "called")
    return body
