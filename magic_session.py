"""How a magic session opens, stands, and closes.

The decisions are pure. Git and Discord stay at the edges, and a test can
make each decision fail.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

BRIEFING = "floor/briefings/latest.md"
REMOTE = "turtle"

WAITED = "The room waited. This checkout is `{head}` and the house main is `{main}`."
UNREADABLE = "The room waited. The house main could not be read."
COMPANY = "Other spirits are in the workshop: {names}. They have not released. Stay out of their work."
HELD = "The release is not closed. The briefing was not written."
CLOSED = "Released. The briefing changed."


def stand_decision(
    *,
    dirty: bool,
    head: str,
    main: str,
    head_contained: bool,
    main_contained: bool,
) -> str:
    """'stay', 'move', or 'wait'.

    A dirty tree waits. A checkout that is only behind house main moves.
    A clean checkout that already contains main stands, including one with
    commits of its own. One that has diverged waits.
    """
    if dirty or not head or not main:
        return "wait"
    if head == main or main_contained:
        return "stay"
    if head_contained:
        return "move"
    return "wait"


def briefing_digest(path: Path) -> str:
    """A short hash of the release briefing, or 'missing' when it is not there."""
    try:
        raw = path.read_bytes()
    except OSError:
        return "missing"
    return hashlib.sha256(raw).hexdigest()[:16]


def release_can_close(events: list[dict], digest_now: str) -> bool:
    """True when the briefing changed after the greeting recorded it.

    No greeting, or a briefing that is still missing, cannot close. Writing the
    same bytes the session opened on cannot close.
    """
    if digest_now in ("", "missing"):
        return False
    opened = [
        event.get("briefing")
        for event in events
        if event.get("kind") == "greeting" and event.get("briefing")
    ]
    if not opened:
        return False
    return digest_now != opened[-1]


def is_release_ask(text: str) -> bool:
    """True when the message itself is the release, not a mention of one."""
    words = text.strip().casefold().lstrip("@/")
    for prefix in ("let's ", "lets "):
        if words.startswith(prefix):
            words = words[len(prefix):]
            break
    return words == "release" or words.startswith(("release ", "release.", "release,", "release:"))


def pick_session(rows: list[dict]) -> dict:
    """Summon always opens a new session.

    An unreleased session is another spirit in the same workshop. The new one
    is told their names and stays out of their work. Nothing in that list
    refuses the summon. A released session, and an archived thread, are not
    company.
    """
    company = [
        row for row in rows
        if not row.get("archived") and not row.get("released")
    ]
    text = ""
    if company:
        names = ", ".join(str(row.get("name") or row.get("id")) for row in company)
        text = COMPANY.format(names=names)
    return {"act": "open", "company": company, "text": text}


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        env=env,
    )


def _rev(root: Path, rev: str) -> str:
    return _git(root, "rev-parse", rev).stdout.strip()


def _short(root: Path, rev: str) -> str:
    return _git(root, "rev-parse", "--short", rev).stdout.strip()


def _is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    return _git(root, "merge-base", "--is-ancestor", ancestor, descendant).returncode == 0


def apply_stand(root: Path) -> str:
    """Move a clean checkout that is only behind, or say why the room waited.

    A clean checkout that already contains main is left where it is.
    Never resets, never cleans, never merges a branch that has diverged.
    An empty string means the greeting can stand on the checkout as it is now.
    """
    fetched = _git(root, "fetch", REMOTE, "main")
    head = _rev(root, "HEAD")
    main = _rev(root, f"{REMOTE}/main")
    if fetched.returncode != 0 or not head or not main:
        return UNREADABLE
    dirty = bool(_git(root, "status", "--porcelain").stdout.strip())
    decision = stand_decision(
        dirty=dirty,
        head=head,
        main=main,
        head_contained=_is_ancestor(root, "HEAD", f"{REMOTE}/main"),
        main_contained=_is_ancestor(root, f"{REMOTE}/main", "HEAD"),
    )
    if decision == "stay":
        return ""
    if decision == "move":
        if _git(root, "checkout", "main").returncode != 0:
            return WAITED.format(head=_short(root, "HEAD"), main=_short(root, f"{REMOTE}/main"))
        if _git(root, "merge", "--ff-only", f"{REMOTE}/main").returncode != 0:
            return WAITED.format(head=_short(root, "HEAD"), main=_short(root, f"{REMOTE}/main"))
        return ""
    return WAITED.format(head=_short(root, "HEAD"), main=_short(root, f"{REMOTE}/main"))


async def finish_release(channel, practice_dir: Path, checkout: Path | None) -> str:
    """Close the session when the briefing changed. Otherwise say so and leave it open."""
    from session_record import append_event, read_turns

    events = read_turns(practice_dir, channel.id)
    digest = briefing_digest(checkout / BRIEFING) if checkout is not None else "missing"
    if release_can_close(events, digest):
        append_event(practice_dir, channel.id, kind="release", actor="spirit", text=CLOSED)
        try:
            await channel.edit(archived=True)
        except Exception as exc:
            print(f"Magic release archive failed: {type(exc).__name__}: {exc}")
        return "close"
    append_event(practice_dir, channel.id, kind="held", actor="spirit", text=HELD)
    try:
        from spirit_voice import say

        await say(channel.id, HELD)
    except Exception as exc:
        print(f"Magic release hold failed: {type(exc).__name__}: {exc}")
    return "hold"
