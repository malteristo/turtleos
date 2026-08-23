"""Constrained shell harness for turtleOS self-development.

This is deliberately small: it gives Turtle enough body access to inspect and
verify its own shell without granting arbitrary command execution.
"""

import json
import os
import re
import shlex
import shutil
import subprocess
from datetime import datetime, timezone
from fnmatch import fnmatch
from pathlib import Path

from mage import get_runtime_dir


# Default to this checkout (the directory that contains shell_harness.py).
# Mini sets TURTLEOS_ROOT=~/turtleos in the service environment; Forge laptop
# checkouts live under Documents/ and must not require a second clone at ~/turtleos.
TURTLEOS_ROOT = Path(
    os.environ.get("TURTLEOS_ROOT", str(Path(__file__).resolve().parent))
).expanduser().resolve()
MAX_TIMEOUT = 30
MAX_OUTPUT = 6000

_SHELL_METACHARS = set("|&;<>`$(){}[]\n\r")
# Chaining / substitution only — rg patterns need | () [] {} as regex.
_SHELL_CHAIN_METACHARS = set("&;<>`$\n\r")
_GIT_READ_ONLY = {"status", "diff", "log", "branch", "rev-parse", "show"}
_HEAD_TAIL_MAX_LINES = 200


def _runtime_log_path() -> Path:
    runtime = Path(get_runtime_dir()).expanduser()
    runtime.mkdir(parents=True, exist_ok=True)
    return runtime / "shell-actions.jsonl"


def _clip(text: str, limit: int = MAX_OUTPUT) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 80] + "\n... [truncated by shell harness]"


def _inside_root(path: Path) -> bool:
    try:
        path.resolve().relative_to(TURTLEOS_ROOT)
        return True
    except ValueError:
        return False


def _resolve_cwd(cwd: str | None) -> Path:
    if not cwd:
        return TURTLEOS_ROOT
    candidate = Path(cwd).expanduser()
    if not candidate.is_absolute():
        candidate = TURTLEOS_ROOT / candidate
    candidate = candidate.resolve()
    if not _inside_root(candidate):
        raise ValueError("cwd must stay inside ~/turtleos")
    if not candidate.is_dir():
        raise ValueError(f"cwd does not exist: {candidate}")
    return candidate


def _safe_rel_path(arg: str, cwd: Path) -> bool:
    if arg.startswith("-"):
        return True
    path = Path(arg).expanduser()
    if not path.is_absolute():
        path = cwd / path
    return _inside_root(path)


def _git_top_level(cwd: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=5,
    )
    if result.returncode != 0:
        raise ValueError("cwd is not inside a git repository")
    top = Path(result.stdout.strip()).resolve()
    if top != TURTLEOS_ROOT:
        raise ValueError(f"git root mismatch: {top}")
    return str(top)


def _git_status(cwd: Path) -> str:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=5,
    )
    return result.stdout.strip()


def _validate_git(args: list[str], cwd: Path) -> tuple[bool, str]:
    if len(args) < 2:
        return False, "git subcommand required"
    sub = args[1]
    if sub not in _GIT_READ_ONLY:
        return False, f"git {sub} is not allowed through shell_harness"
    if sub == "rev-parse" and args[2:] != ["--show-toplevel"]:
        return False, "only git rev-parse --show-toplevel is allowed"
    if sub == "branch" and args[2:] != ["--show-current"]:
        return False, "only git branch --show-current is allowed"
    if sub == "status":
        allowed = {"--short", "--porcelain", "--branch", "-sb"}
        if any(a not in allowed for a in args[2:]):
            return False, "git status only allows --short, --porcelain, --branch, -sb"
    if sub == "log":
        # Craft survey needs short -N counts and --name-only/--stat for coupling.
        i = 2
        while i < len(args):
            a = args[i]
            if a.isdigit() or (a.startswith("-") and len(a) > 1 and a[1:].isdigit()):
                i += 1
                continue
            if a in {"--oneline", "--name-only", "--stat", "--", "--color=never"}:
                i += 1
                continue
            if a.startswith("--max-count="):
                i += 1
                continue
            if a.startswith("-n") and len(a) > 2 and a[2:].isdigit():
                i += 1
                continue
            if a in {"-n", "--max-count"} and i + 1 < len(args) and args[i + 1].isdigit():
                i += 2
                continue
            return False, (
                "git log only allows --oneline, count flags (-N / -n N / --max-count), "
                "--name-only, and --stat"
            )
    if sub in {"diff", "show"}:
        for a in args[2:]:
            if a in {"--stat", "--name-only", "--", "--color=never"}:
                continue
            if a.startswith("-"):
                return False, f"git {sub} flag not allowed: {a}"
            if not _safe_rel_path(a, cwd):
                return False, f"path escapes ~/turtleos: {a}"
    return True, ""


def _validate_python_compile(args: list[str], cwd: Path) -> tuple[bool, str]:
    if len(args) < 4 or args[1:3] != ["-m", "py_compile"]:
        return False, "only python -m py_compile <files> is allowed"
    for target in args[3:]:
        if not target.endswith(".py"):
            return False, "py_compile targets must be .py files"
        if not _safe_rel_path(target, cwd):
            return False, f"path escapes ~/turtleos: {target}"
    return True, ""


def _validate_rg(args: list[str], cwd: Path) -> tuple[bool, str]:
    if len(args) < 2:
        return False, "rg query required"
    allowed_flags = {
        "-n", "--line-number", "--files", "--glob", "-g",
        "-i", "--ignore-case", "--type", "-t",
        "-l", "--files-with-matches", "-c", "--count",
    }
    expect_value = False
    for arg in args[1:]:
        if expect_value:
            expect_value = False
            continue
        if arg in {"--glob", "-g", "--type", "-t"}:
            expect_value = True
            continue
        # -r is --replace in ripgrep, not grep's recursive. Left allowed it
        # would rewrite every match in the output and still exit 0, so the
        # caller reasons from a corrupted answer instead of hitting an error.
        if arg == "-r" or arg.startswith("-r") and not arg.startswith("--"):
            return False, (
                "rg -r is --replace (it rewrites matches in the output), not "
                "grep's recursive — rg already searches recursively. Drop it: "
                "use `rg -n <pattern>` or `rg -l <pattern>`."
            )
        if arg == "--replace" or arg.startswith("--replace"):
            return False, "rg --replace rewrites output text and is not allowed"
        if arg.startswith("--type="):
            continue
        # Compact -tpy
        if arg.startswith("-t") and len(arg) > 2 and not arg.startswith("--"):
            continue
        if arg.startswith("-") and arg not in allowed_flags:
            return False, f"rg flag not allowed: {arg}"
        if "/" in arg or arg.endswith((".py", ".md", ".yaml", ".yml", ".json", ".txt")):
            if not _safe_rel_path(arg, cwd):
                return False, f"path escapes ~/turtleos: {arg}"
    return True, ""


def _validate_head_tail(args: list[str], cwd: Path) -> tuple[bool, str]:
    """Allow ``head -n N file`` / ``head -N file`` (same for tail). Read-only."""
    if len(args) < 2:
        return False, f"{args[0]} requires a file path"
    i = 1
    lines = 10
    if args[i] == "-n" and i + 1 < len(args) and args[i + 1].isdigit():
        lines = int(args[i + 1])
        i += 2
    elif args[i].startswith("-n") and len(args[i]) > 2 and args[i][2:].isdigit():
        lines = int(args[i][2:])
        i += 1
    elif args[i].startswith("-") and len(args[i]) > 1 and args[i][1:].isdigit():
        lines = int(args[i][1:])
        i += 1
    if lines < 1 or lines > _HEAD_TAIL_MAX_LINES:
        return False, f"{args[0]} line count must be 1..{_HEAD_TAIL_MAX_LINES}"
    if i >= len(args):
        return False, f"{args[0]} requires a file path"
    if len(args) != i + 1:
        return False, f"{args[0]} takes one file path"
    target = args[i]
    if target.startswith("-"):
        return False, f"{args[0]} flag not allowed: {target}"
    if not _safe_rel_path(target, cwd):
        return False, f"path escapes ~/turtleos: {target}"
    return True, ""


def _validate_args(args: list[str], cwd: Path) -> tuple[bool, str]:
    if not args:
        return False, "empty command"
    exe = args[0]
    # rg patterns are regex — allow | () [] {} in the pattern arg only.
    if exe == "rg":
        danger = _SHELL_CHAIN_METACHARS
    else:
        danger = _SHELL_METACHARS
    if any(any(ch in arg for ch in danger) for arg in args):
        return False, "shell metacharacters are not allowed"
    if exe == "pwd":
        return (len(args) == 1, "pwd takes no arguments" if len(args) != 1 else "")
    if exe == "ls":
        # -1 = one column (craft survey module lists); still no wildcards via shell.
        allowed_flags = {"-l", "-a", "-la", "-al", "-1", "-l1", "-1l"}
        for arg in args[1:]:
            if arg.startswith("-") and arg not in allowed_flags:
                return False, f"ls flag not allowed: {arg}"
            if not arg.startswith("-") and not _safe_rel_path(arg, cwd):
                return False, f"path escapes ~/turtleos: {arg}"
        return True, ""
    if exe == "git":
        return _validate_git(args, cwd)
    if exe in {"python", "python3", "/Users/turtle/turtleos/venv/bin/python3"}:
        return _validate_python_compile(args, cwd)
    if exe == "rg":
        return _validate_rg(args, cwd)
    if exe in {"head", "tail"}:
        return _validate_head_tail(args, cwd)
    return False, f"command not allowed: {exe}"


def _iter_source_files(paths: list[str], cwd: Path, glob_patterns: list[str]):
    roots = paths or ["."]
    for item in roots:
        path = Path(item).expanduser()
        if not path.is_absolute():
            path = cwd / path
        path = path.resolve()
        if not _inside_root(path):
            continue
        candidates = [path] if path.is_file() else path.rglob("*")
        for candidate in candidates:
            if not candidate.is_file():
                continue
            rel = str(candidate.relative_to(TURTLEOS_ROOT))
            parts = set(candidate.parts)
            if ".git" in parts or "__pycache__" in parts or "venv" in parts:
                continue
            if candidate.suffix not in {".py", ".md", ".yaml", ".yml", ".json", ".txt"}:
                continue
            if glob_patterns and not any(fnmatch(rel, pat) or fnmatch(candidate.name, pat) for pat in glob_patterns):
                continue
            yield candidate, rel


def _run_python_rg(args: list[str], cwd: Path) -> dict:
    """Small rg-compatible fallback for safe source search when rg is absent."""
    line_numbers = "-n" in args or "--line-number" in args
    ignore_case = "-i" in args or "--ignore-case" in args
    files_only = "--files" in args
    glob_patterns = []
    positional = []
    i = 1
    while i < len(args):
        arg = args[i]
        if arg in {"-n", "--line-number", "-i", "--ignore-case", "--files"}:
            i += 1
            continue
        if arg in {"-g", "--glob"} and i + 1 < len(args):
            glob_patterns.append(args[i + 1])
            i += 2
            continue
        if arg.startswith("-"):
            i += 1
            continue
        positional.append(arg)
        i += 1

    if files_only:
        lines = [rel for _, rel in _iter_source_files(positional, cwd, glob_patterns)]
        return {
            "returncode": 0,
            "stdout": "\n".join(lines[:200]) + ("\n... [truncated by shell harness]" if len(lines) > 200 else ""),
            "stderr": "",
        }

    if not positional:
        return {"returncode": 2, "stdout": "", "stderr": "rg query required"}

    query = positional[0]
    paths = positional[1:]
    flags = re.IGNORECASE if ignore_case else 0
    try:
        pattern = re.compile(query, flags)
    except re.error:
        pattern = re.compile(re.escape(query), flags)

    matches = []
    for file_path, rel in _iter_source_files(paths, cwd, glob_patterns):
        try:
            text = file_path.read_text(errors="replace")
        except Exception:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                prefix = f"{rel}:{line_no}:" if line_numbers else f"{rel}:"
                matches.append(prefix + line[:200])
                if len(matches) >= 120:
                    break
        if len(matches) >= 120:
            break

    if not matches:
        return {"returncode": 1, "stdout": "", "stderr": ""}
    stdout = "\n".join(matches)
    if len(matches) >= 120:
        stdout += "\n... [truncated by shell harness]"
    return {"returncode": 0, "stdout": stdout, "stderr": ""}


def _record(entry: dict) -> None:
    try:
        with _runtime_log_path().open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"shell_harness log failed: {type(e).__name__}: {e}")


def run_shell_command(command: str, cwd: str | None = None, reason: str = "", requester: str = "turtle") -> dict:
    """Run a constrained read-only shell command inside ~/turtleos."""
    timestamp = datetime.now(timezone.utc).isoformat()
    entry = {
        "timestamp": timestamp,
        "requester": requester,
        "command": command,
        "cwd": cwd or str(TURTLEOS_ROOT),
        "reason": reason,
    }

    try:
        run_cwd = _resolve_cwd(cwd)
        _git_top_level(run_cwd)
        args = shlex.split(command)
        ok, error = _validate_args(args, run_cwd)
        if not ok:
            entry.update({"allowed": False, "error": error})
            _record(entry)
            return {"ok": False, "error": error, "allowed": False}

        status_before = _git_status(run_cwd)
        if args[0] == "rg" and shutil.which("rg") is None:
            result_data = _run_python_rg(args, run_cwd)
            returncode = result_data["returncode"]
            stdout = result_data["stdout"]
            stderr = result_data["stderr"]
        else:
            result = subprocess.run(
                args,
                cwd=str(run_cwd),
                capture_output=True,
                text=True,
                timeout=MAX_TIMEOUT,
            )
            returncode = result.returncode
            stdout = result.stdout
            stderr = result.stderr
        status_after = _git_status(run_cwd)
        changed = status_before != status_after

        response = {
            "ok": returncode == 0,
            "allowed": True,
            "command": command,
            "cwd": str(run_cwd),
            "returncode": returncode,
            "stdout": _clip(stdout),
            "stderr": _clip(stderr),
            "git_dirty": bool(status_after),
            "git_changed": changed,
        }
        entry.update(response)
        _record(entry)
        return response
    except subprocess.TimeoutExpired:
        entry.update({"allowed": True, "ok": False, "error": "command timed out"})
        _record(entry)
        return {"ok": False, "allowed": True, "error": "command timed out"}
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
        entry.update({"allowed": False, "ok": False, "error": error})
        _record(entry)
        return {"ok": False, "allowed": False, "error": error}


def format_shell_result(result: dict) -> str:
    if not result.get("allowed", False):
        return f"Shell command blocked: {result.get('error', 'not allowed')}"
    if not result.get("ok", False):
        error = result.get("error") or result.get("stderr") or f"exit {result.get('returncode')}"
        return f"Shell command failed: `{result.get('command')}`\n{_clip(str(error), 1800)}"

    parts = [f"$ {result.get('command')}"]
    stdout = (result.get("stdout") or "").strip()
    stderr = (result.get("stderr") or "").strip()
    if stdout:
        parts.append(stdout)
    if stderr:
        parts.append("[stderr]\n" + stderr)
    if result.get("git_changed"):
        parts.append("WARNING: git state changed during command.")
    return "\n".join(parts)
