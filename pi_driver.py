"""One Pi session, in a worktree, with abort.

The live checkout is not a place it works, and a secret file is not a file it
may see. The local coder does not receive the house key. Abort is a command
on that session. An edit to a test Spirit named is refused by the sandbox,
and the session is aborted when the edit or write tool names that file.
A climb is not started from here.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

from workshop_tools import Refused

from pi_engagement import render as render_engagement

_KEEP = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR")
_EDIT_TOOLS = {"edit", "write"}
_VERBS = {
    "read": "reading",
    "grep": "searching",
    "find": "searching",
    "ls": "looking",
    "edit": "editing",
    "write": "writing",
    "bash": "checking",
}


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _inside(live: Path, dest: Path) -> bool:
    live = live.resolve()
    dest = dest.resolve()
    return dest == live or live in dest.parents


_TEMPLATES = {".env.template", ".env.example", ".env.sample"}


def _secret(root: Path) -> bool:
    if (root / ".env").exists() or (root / "credentials.json").exists():
        return True
    if (root / "delegate" / "key").exists():
        return True
    return any(path.name not in _TEMPLATES for path in root.glob(".env.*"))


def _relative(root: Path, raw: str) -> str | None:
    candidate = Path(raw)
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        return None


def held_edit(record: dict, spirit_tests: set[str], root: Path) -> str | None:
    """The Spirit test an edit or write is aimed at, if this event is one."""
    if record.get("type") not in {"tool_execution_start", "tool_execution_update"}:
        return None
    name = str(record.get("toolName") or "")
    args = record.get("args") if isinstance(record.get("args"), dict) else {}
    if name in _EDIT_TOOLS:
        raw = args.get("path") or args.get("filePath") or args.get("file")
        if not isinstance(raw, str):
            return None
        rel = _relative(root, raw)
        return rel if rel in spirit_tests else None
    if name == "bash":
        command = str(args.get("command") or "")
        for rel in spirit_tests:
            if rel and rel in command:
                return rel
    return None


def sandbox_profile(worktree: Path, spirit_tests: set[str]) -> str:
    """Deny writing the named tests, and deny reading a secret."""
    root = worktree.resolve()
    literals: list[str] = []
    for rel in sorted(spirit_tests):
        path = (root / rel).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise Refused("A Spirit test is inside the worktree.") from exc
        literals.append(f'(literal "{path}")')
    write = "(deny file-write*\n  " + "\n  ".join(literals) + ")" if literals else ""
    return f"""
(version 1)
(allow default)
{write}
(deny file-read*
    (regex #"/\\.env$")
    (regex #"/\\.env\\.[^/]*$")
    (regex #"/credentials\\.json$")
    (regex #"/delegate/key$"))
""".strip()


def open_worktree(bare: Path, dest: Path, branch: str, live: Path) -> Path:
    """A new worktree of the bare repo. Never the live checkout."""
    bare = Path(bare).resolve()
    dest = Path(dest).resolve()
    live = Path(live).resolve()
    if not (bare / "HEAD").is_file():
        raise Refused("The bare repo is not here.")
    if _inside(live, dest):
        raise Refused("Pi does not work in the live checkout.")
    if dest.exists():
        raise Refused("The worktree has to be a new directory.")
    done = subprocess.run(
        ["git", f"--git-dir={bare}", "worktree", "add", "-b", branch, str(dest), "HEAD"],
        capture_output=True,
        text=True,
    )
    if done.returncode != 0:
        raise Refused("The worktree was not created.")
    if _secret(dest):
        raise Refused("That worktree holds a secret.")
    return dest


class Session:
    """One Pi process. A second one is refused while this one is alive."""

    def __init__(
        self,
        worktree: Path,
        spirit_tests: set[str],
        *,
        pi: str,
        live: Path,
        branch: str = "",
        hear=None,
    ) -> None:
        self.worktree = Path(worktree).resolve()
        self.spirit_tests = {p.strip() for p in spirit_tests if p.strip()}
        self.pi = pi
        self.live = Path(live).resolve()
        self.branch = branch
        self.hear = hear
        self.looks = 0
        self.progress = ""
        self.failed: list[str] = []
        self.claims: list[str] = []
        self.lock = self.worktree.parent / f"{self.worktree.name}.pi.lock"
        self.proc: subprocess.Popen[str] | None = None
        self.lines: list[str] = []
        self._reader: threading.Thread | None = None

    def start(self) -> None:
        if self.proc is not None:
            raise Refused("One Pi session is already open.")
        if _inside(self.live, self.worktree):
            raise Refused("Pi does not work in the live checkout.")
        if _secret(self.worktree):
            raise Refused("That worktree holds a secret.")
        if self.lock.exists():
            try:
                pid = int(self.lock.read_text().strip())
            except ValueError:
                pid = 0
            if pid and _alive(pid):
                raise Refused("One Pi session is already open.")
        sandbox = shutil.which("sandbox-exec")
        if sandbox is None or sys.platform != "darwin":
            raise Refused("Pi is not available on this machine.")
        if not Path(self.pi).exists() and shutil.which(self.pi) is None:
            raise Refused("Pi is not on this machine.")
        env = {k: os.environ[k] for k in _KEEP if os.environ.get(k)}
        env.setdefault("PATH", "/usr/bin:/bin:/usr/sbin:/sbin")
        self.proc = subprocess.Popen(
            [
                sandbox,
                "-p",
                sandbox_profile(self.worktree, self.spirit_tests),
                self.pi,
                "--mode",
                "rpc",
                "--no-session",
                "--no-mcp",
            ],
            cwd=str(self.worktree),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        self.lock.write_text(str(self.proc.pid))
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()
        self._hear("starting", "opening")

    def _hear(self, phase: str, progress: str) -> None:
        """The card. A failure to say it does not stop the session."""
        self.progress = progress
        if self.hear is None:
            return
        try:
            self.hear(
                render_engagement(
                    phase=phase,
                    branch=self.branch,
                    progress=progress,
                    failed=self.failed,
                    claims=self.claims,
                    looks=self.looks,
                )
            )
        except Exception:
            return

    def observe(self, record: dict) -> str | None:
        """One event. The card keeps the count and the verb, not the path."""
        if record.get("type") != "tool_execution_start":
            return None
        self.looks += 1
        if held_edit(record, self.spirit_tests, self.worktree) is not None:
            return self.consider(record)
        name = str(record.get("toolName") or "")
        self._hear("working", _VERBS.get(name, "working"))
        return None

    def _read(self) -> None:
        proc = self.proc
        if proc is None or proc.stdout is None:
            return
        for line in proc.stdout:
            self.lines.append(line)

    def command(self, record: dict) -> None:
        if self.proc is None or self.proc.stdin is None:
            raise Refused("No Pi session is open.")
        self.proc.stdin.write(json.dumps(record) + "\n")
        self.proc.stdin.flush()

    def abort(self) -> None:
        self.command({"type": "abort"})
        self._hear("aborted", self.progress or "aborted")

    def consider(self, record: dict) -> str | None:
        """Abort when this event would edit a test Spirit named."""
        rel = held_edit(record, self.spirit_tests, self.worktree)
        if rel is None:
            return None
        if rel not in self.failed:
            self.failed.append(rel)
        self.progress = "refused an edit"
        if self.proc is not None:
            self.abort()
        else:
            self._hear("aborted", "refused an edit")
        return f"Pi does not edit Spirit's tests (`{rel}`)."

    def close(self) -> None:
        proc = self.proc
        if proc is not None and proc.stdin is not None and not proc.stdin.closed:
            proc.stdin.close()
        if self._reader is not None:
            self._reader.join(timeout=5)
        self.proc = None
        if proc is not None:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
            if proc.stdout is not None and not proc.stdout.closed:
                proc.stdout.close()
            if proc.stderr is not None and not proc.stderr.closed:
                proc.stderr.close()
        if self.lock.exists():
            self.lock.unlink()
