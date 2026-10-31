"""A person's workshop, read from its bare repository at its head.

The workshop is a git repository the practice keeps (for the operator, the
Magic practice). It is served from the bare repo the Forge pushes to, never
from a second working tree: a working tree is a copy that can drift and say
nothing. Every answer names the release it came from (the commit at head), so
an agent cannot work on last week's file without being able to see that it is
last week's.

Read-only by construction: the only git commands issued here are ``rev-parse``,
``log``, ``rev-list``, ``ls-tree``, ``cat-file`` and ``grep``. A test pins that
list, and a second one plants a commit through a real push to check that the
next read is the new release.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass

from mcp_access.registry import Source

# Every git command this module may run. A write needs a new entry here and a
# test that says why; tests/test_mcp_workshop.py fails on any other verb.
GIT_VERBS = frozenset({"rev-parse", "log", "rev-list", "ls-tree", "cat-file", "grep"})

TIMEOUT = 15
MAX_BYTES = 300_000
MAX_HITS = 20
SNIPPET = 240
_SHA = re.compile(r"^[0-9a-f]{7,40}$")
_FILE_MODES = frozenset({"100644", "100755"})


@dataclass(frozen=True)
class Release:
    sha: str
    committed: str
    subject: str

    @property
    def short(self) -> str:
        return self.sha[:7]

    def line(self) -> str:
        return f"{self.short} · {self.committed} · {self.subject}"


def _run(source: Source, *args: str) -> bytes | None:
    """Run one allowed read-only git command against the bare repo. None on any failure."""
    if args[0] not in GIT_VERBS:
        raise ValueError(f"git {args[0]} is not a workshop read")
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": "/nonexistent",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
    }
    try:
        done = subprocess.run(
            ["git", f"--git-dir={source.root}", *args],
            capture_output=True,
            timeout=TIMEOUT,
            env=env,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout if done.returncode == 0 else None


def _git(source: Source, *args: str) -> str | None:
    out = _run(source, *args)
    return None if out is None else out.decode("utf-8", errors="replace")


def head(source: Source) -> Release | None:
    """The release the workshop is at now. Read from the repository on every call; never cached."""
    if not source.root.is_dir():
        return None
    out = _git(source, "log", "-1", "--format=%H%x00%cI%x00%s", "HEAD")
    if not out:
        return None
    parts = out.strip("\n").split("\x00")
    if len(parts) != 3 or not _SHA.match(parts[0]):
        return None
    return Release(parts[0], parts[1], " ".join(parts[2].split())[:160])


def available(source: Source) -> bool:
    return head(source) is not None


def clean_path(path: str) -> str | None:
    """A workshop-relative path with nothing that could name anything else, or None."""
    if not path or len(path) > 400 or "\x00" in path or "\\" in path:
        return None
    if path.startswith(("/", "-", ":")):
        return None
    segments = path.rstrip("/").split("/")
    if any(s in ("", ".", "..") for s in segments):
        return None
    return "/".join(segments)


def _entry(source: Source, release: Release, path: str) -> tuple[str, str, str] | None:
    """(mode, type, object) of exactly this path at this release."""
    out = _git(source, "ls-tree", "-z", release.sha, "--", path)
    if not out:
        return None
    for row in out.split("\x00"):
        if not row:
            continue
        meta, _, name = row.partition("\t")
        if name != path:
            continue
        bits = meta.split()
        if len(bits) == 3:
            return bits[0], bits[1], bits[2]
    return None


def read_file(source: Source, release: Release, path: str) -> str | None:
    """The file's text at this release. None when it is not a plain file here.

    Symlinks and submodules are refused rather than followed: the link text is
    not the file, and a followed link is a way out of the tree.
    """
    path = clean_path(path)
    if path is None:
        return None
    entry = _entry(source, release, path)
    if entry is None or entry[1] != "blob" or entry[0] not in _FILE_MODES:
        return None
    raw = _run(source, "cat-file", "blob", entry[2])
    if raw is None:
        return None
    if b"\x00" in raw[:8000]:
        return f"(binary file, {len(raw)} bytes, not shown)"
    note = ""
    if len(raw) > MAX_BYTES:
        cut = raw[:MAX_BYTES]
        cut = cut[: cut.rfind(b"\n") + 1] or cut
        note = f"\n\n(truncated: showing {len(cut)} of {len(raw)} bytes; use search to find the part you need)"
        raw = cut
    return raw.decode("utf-8", errors="replace") + note


def list_tree(source: Source, release: Release, path: str = "") -> list[dict] | None:
    """Entries directly under a directory at this release. None when the path is not a directory."""
    if path:
        path = clean_path(path)
        if path is None:
            return None
        entry = _entry(source, release, path)
        if entry is None or entry[1] != "tree":
            return None
        treeish = entry[2]
        prefix = path + "/"
    else:
        treeish = release.sha
        prefix = ""
    out = _git(source, "ls-tree", "-z", "-l", treeish)
    if out is None:
        return None
    rows = []
    for row in out.split("\x00"):
        if not row:
            continue
        meta, _, name = row.partition("\t")
        bits = meta.split()
        if len(bits) < 4:
            continue
        kind = {"tree": "dir", "blob": "file"}.get(bits[1], bits[1])
        entry_row = {"path": prefix + name, "type": kind}
        if kind == "file":
            entry_row["bytes"] = int(bits[3]) if bits[3].isdigit() else None
        rows.append(entry_row)
    return rows


def search(source: Source, release: Release, query: str, limit: int = MAX_HITS) -> list[dict]:
    """The first matching line of each file, at this release. Fixed-string, case-insensitive."""
    needle = (query or "").strip()
    if not needle or len(needle) > 200:
        return []
    out = _git(source, "grep", "-I", "-i", "-F", "-n", "--max-count=1", "-e", needle, release.sha, "--")
    if not out:
        return []
    hits = []
    for line in out.splitlines():
        # sha:path:lineno:text
        try:
            _, rest = line.split(":", 1)
            path, lineno, text = rest.split(":", 2)
        except ValueError:
            continue
        hits.append(
            {
                "path": path,
                "line": int(lineno) if lineno.isdigit() else None,
                "text": " ".join(text.split())[:SNIPPET],
            }
        )
        if len(hits) >= limit:
            break
    return hits


def behind(source: Source, since: str, now: Release) -> dict | None:
    """What changed after ``since`` up to ``now``; None when ``since`` is the current release.

    ``{"unknown": True}`` when ``since`` is not a release this repository knows,
    which is itself something to say rather than silence.
    """
    if not _SHA.match(since or ""):
        return {"unknown": True, "since": (since or "")[:12]}
    if now.sha.startswith(since):
        return None
    count = _git(source, "rev-list", "--count", f"{since}..{now.sha}")
    if count is None or not count.strip().isdigit():
        return {"unknown": True, "since": since[:12]}
    n = int(count.strip())
    if n == 0:
        # `since` is not behind head (equal by another spelling, or ahead after a rewind)
        return {"unknown": True, "since": since[:12]}
    subjects = _git(source, "log", "-3", "--format=%s", f"{since}..{now.sha}") or ""
    return {"count": n, "since": since[:7], "subjects": [s[:100] for s in subjects.splitlines() if s]}


def header(release: Release, *, path: str | None = None, behind_note: dict | None = None, since: str | None = None) -> str:
    """The lines that go above every file answer: the release, and whether the session is behind it."""
    lines = [f"[workshop release {release.line()}]"]
    if path:
        lines.append(f"[path {path}]")
    if behind_note is not None:
        if behind_note.get("unknown"):
            lines.append(
                f"[BEHIND? this session says it started at {behind_note.get('since')}, which this workshop does not know. "
                f"Read the bootstrap again to rejoin at {release.short}.]"
            )
        else:
            said = "; ".join(f"“{s}”" for s in behind_note["subjects"])
            lines.append(
                f"[BEHIND: this session started at {behind_note['since']}; the workshop is now at {release.short}, "
                f"{behind_note['count']} release{'s' if behind_note['count'] != 1 else ''} later ({said}). "
                f"What you read earlier may be out of date. Read the bootstrap again to rejoin.]"
            )
    return "\n".join(lines)


def refs(source: Source, kind: str, path: str = "") -> str:
    return f"turtleos://workshop/{source.id}/{kind}" + (f"/{path}" if path else "")


def is_workshop(source: Source) -> bool:
    return source.kind == "workshop"


def bootstrap_text(source: Source, release: Release) -> str:
    """The server's own preface (how to read a workshop with no clone), then the practice's declared bootstrap file."""
    lines = [
        header(release),
        "",
        f"# Bootstrap — {source.id}",
        "",
        "This is a practice workshop reached over MCP. There is no local clone and none is needed: "
        "read it through this connection, at the release named above.",
        "",
        f"- A file: `read(\"{refs(source, 'file')}/<path>\")`. A path written anywhere in the practice (including after an `@`) is workshop-relative; read it, do not look for it on disk.",
        f"- A folder: `read(\"{refs(source, 'tree')}\")` for the top, `read(\"{refs(source, 'tree')}/<dir>\")` for one directory.",
        f"- Search: `search(query, source=\"{source.id}\")` returns the first matching line of each file.",
        f"- Add `?since={release.short}` to a ref to be told if the workshop moves on while you work; without it, the connection compares against the last bootstrap it served.",
        "- Read-only. Nothing here can be changed through this connection; do not claim an edit was made.",
        "- A file you read is a file at a release. If a read says BEHIND, the workshop moved: say so before you rely on what you read.",
        "",
        "---",
        "",
    ]
    declared = source.bootstrap
    if not declared:
        lines.append("This workshop declares no bootstrap file. Start from its top-level folder and README.")
        return "\n".join(lines)
    body = read_file(source, release, declared)
    if body is None:
        lines.append(
            f"**The declared bootstrap file `{declared}` does not exist at this release.** "
            f"Say so, and start from the top-level folder: `read(\"{refs(source, 'tree')}\")`."
        )
        return "\n".join(lines)
    lines.append(f"The practice's own bootstrap (`{declared}`):")
    lines.append("")
    lines.append(body)
    return "\n".join(lines)


def bootstrap_missing(source: Source, release: Release) -> str | None:
    """Why the declared bootstrap cannot be served, or None when it can. Used by the brief."""
    if not source.bootstrap:
        return "no bootstrap file is declared for this workshop"
    if read_file(source, release, source.bootstrap) is None:
        return f"the declared bootstrap `{source.bootstrap}` is missing at this release"
    return None
