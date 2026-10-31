"""The backlog, one pitch at a time — Build or Drop.

The operator's backlog is a file in his Magic workshop. It grew past what anyone
reads, and he asked for it to come to him in the craft channel instead: one open
row at a time, his verdict on each. This module is the part with no Discord in
it — read the rows, remember the verdicts, say which is next.

**Where the rows come from.** The workshop is stored on this machine as a bare
repository. The rows are read from its head with ``git show`` — never from a
second working tree, which could drift without anyone being told. What the feed
shows is therefore as new as the last push from the Forge, and the pitch says
which commit it read.

**Where a verdict goes.** One small file per verdict in the practice root,
``craft/feed/``. The Forge pulls that directory beside the intake and applies it
to the backlog at its next arrival (`scripts/feed_apply.py` in the workshop). The
verdict does not wait for that: a decided row is excluded here the moment it is
written, so a Drop is final even if the Forge never applies it.

**A decided row never comes back** — Build or Drop. A row that left the open
list on its own (shipped, or dropped on the Forge) is simply no longer a pitch.

**Why this has a Drop button when offers do not.** `tests/test_no_decline_buttons.py`
holds the operator's rule that ignoring an offer is how it is declined, and the
reason is a measurement one: a decline button manufactures the event the offer
ledger infers. A pitch is not an offer. It is a row in a queue he asked to clear,
and an unanswered row stays in the queue forever — which is the thing he asked
to end. So Drop is a verdict on a row, recorded as a verdict, and **nothing here
writes the offer ledger**. That is a decision, not a gap. Pinned by
``tests/test_backlog_feed.py::test_the_feed_writes_no_offer_ledger_row``.

No Discord import, by design. The buttons are `backlog_feed_ui.py`.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from core.atomic_io import atomic_write_text

FEED_DIR = "craft/feed"
BUILD = "build"
DROP = "drop"
DECISIONS = (BUILD, DROP)

GIT_TIMEOUT_S = 10
# Discord's message limit is 2000. The pitch keeps room for the buttons' footer.
MAX_BODY_CHARS = 1200

# Two shapes of row exist. `- [ ] [id] **Title.**` carries a checkbox. Sixteen older
# rows are `- [id] **Title.**` with none, and the Forge's digest has always read
# those as open — so does this, or they would never be pitched and never leave.
_ROW = re.compile(r"^- (?:\[(?P<mark>[ xd])\]\s+)?(?P<rest>.+)$")
_DATED_ID = re.compile(r"^\[\d{4}-\d{2}-\d{2}")
_ID = re.compile(r"^\[(?P<id>[^\]]+)\]\s*(?P<rest>.*)$")
_TITLE = re.compile(r"^\*\*(?P<title>.+?)\*\*\s*(?P<rest>.*)$")
FOOTER = re.compile(r"^-# backlog id: (?P<id>\S+)(?: · .*)?$", re.MULTILINE)


class FeedUnavailable(Exception):
    """The feed cannot be shown, and the reason is a sentence he can act on."""


@dataclass(frozen=True)
class FeedItem:
    id: str
    title: str
    body: str
    state: str  # "open" | "done" | "dropped"

    @property
    def is_open(self) -> bool:
        return self.state == "open"


# ── reading the backlog ─────────────────────────────────────────


def parse_backlog(text: str) -> list[FeedItem]:
    """Every row of the backlog, in file order. A row is its line plus the
    indented lines beneath it; a heading or an unindented line ends it."""
    rows: list[tuple[str, list[str]]] = []
    current: list[str] | None = None
    for line in (text or "").splitlines():
        match = _ROW.match(line)
        # Without a checkbox only a dated id makes a row: `- [a link](…)` is prose.
        if match and (match.group("mark") is not None or _DATED_ID.match(match.group("rest"))):
            current = [match.group("rest")]
            rows.append((match.group("mark") or " ", current))
        elif current is not None and line.startswith((" ", "\t")) and line.strip():
            current.append(line.strip())
        elif line.strip():
            # A heading or an unindented line closes the open row. A blank line does not.
            current = None
    items: list[FeedItem] = []
    for mark, lines in rows:
        head = lines[0]
        ident_match = _ID.match(head)
        ident = ""
        if ident_match:
            ident, head = ident_match.group("id"), ident_match.group("rest")
        title_match = _TITLE.match(head)
        if title_match:
            title, first = title_match.group("title"), title_match.group("rest")
        else:
            title, first = head[:80], head
        body = " ".join([first, *lines[1:]]).strip()
        if not ident:
            ident = "row-" + hashlib.sha1(head.encode("utf-8")).hexdigest()[:10]
        state = {" ": "open", "x": "done", "d": "dropped"}[mark]
        items.append(FeedItem(id=ident, title=title.strip(" ."), body=body, state=state))
    return items


def read_backlog(repo: str | Path, path: str) -> tuple[str, str]:
    """``(text, commit)`` of ``path`` at the head of the bare repository ``repo``."""
    repo = Path(repo).expanduser()
    if not repo.is_dir():
        raise FeedUnavailable(f"The workshop repository is not on this machine ({repo}).")
    try:
        shown = subprocess.run(
            ["git", f"--git-dir={repo}", "show", f"HEAD:{path}"],
            capture_output=True, text=True, timeout=GIT_TIMEOUT_S, check=False,
        )
        head = subprocess.run(
            ["git", f"--git-dir={repo}", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=GIT_TIMEOUT_S, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise FeedUnavailable(f"The workshop repository did not answer ({type(exc).__name__}).") from exc
    if shown.returncode != 0:
        raise FeedUnavailable(f"The backlog is not at {path} in the workshop's latest commit.")
    return shown.stdout, head.stdout.strip() or "?"


def read_optional(repo: str | Path, path: str) -> str | None:
    """``path`` at the head of the bare repository, or None when it cannot be read.
    For material a pitch can do without (the boom, his list); the backlog itself uses
    :func:`read_backlog`, which says why it failed."""
    try:
        shown = subprocess.run(
            ["git", f"--git-dir={Path(repo).expanduser()}", "show", f"HEAD:{path}"],
            capture_output=True, text=True, timeout=GIT_TIMEOUT_S, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return shown.stdout if shown.returncode == 0 else None


# ── configuration lives in the registry, not in code ────────────


def feed_source(registry: dict, parent_id) -> tuple[str, str, str]:
    """``(owner, repo, path)`` for a craft channel that has a backlog connected."""
    entry = ((registry or {}).get("channels") or {}).get(str(parent_id))
    if not isinstance(entry, dict) or entry.get("type") != "craft" or entry.get("archived"):
        raise FeedUnavailable("The feed belongs to the craft channel.")
    owner = str(entry.get("mage") or "")
    cfg = entry.get("backlog_feed")
    if not owner or not isinstance(cfg, dict) or not cfg.get("repo") or not cfg.get("path"):
        raise FeedUnavailable(
            "No backlog is connected to this channel yet. It needs a `backlog_feed` "
            "entry (`repo`, `path`) on the channel in the registry."
        )
    return owner, str(cfg["repo"]), str(cfg["path"])


def push_enabled(registry: dict, parent_id) -> bool:
    """Whether River posts new pitches on its own in this channel. It is a flag on the
    channel because *when and what* is his to define, per channel."""
    entry = ((registry or {}).get("channels") or {}).get(str(parent_id)) or {}
    cfg = entry.get("backlog_feed")
    return bool(isinstance(cfg, dict) and cfg.get("push"))


def in_quiet_hours(now: datetime, *, start: int = 22, end: int = 8) -> bool:
    """River does not post pitches at night. ``now`` is local time to the practice."""
    return now.hour >= start or now.hour < end


def may_decide(registry: dict, parent_id, user_id) -> bool:
    """Only the channel's owner decides. A craft channel is one person's."""
    entry = ((registry or {}).get("channels") or {}).get(str(parent_id)) or {}
    owner = str(entry.get("mage") or "")
    expected = str((((registry or {}).get("mages") or {}).get(owner) or {}).get("discord_id") or "").strip()
    return bool(owner) and bool(expected) and expected == str(user_id).strip()


# ── verdicts ────────────────────────────────────────────────────


def _key(item_id: str) -> str:
    return hashlib.sha1(item_id.encode("utf-8")).hexdigest()[:10]


def _read_front_matter(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    if not lines or lines[0].strip() != "---":
        return {}
    out: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            name, _, value = line.partition(":")
            out[name.strip()] = value.strip()
    return out


def decisions(practice_root: str | Path) -> dict[str, dict[str, str]]:
    """``{row id: {decision, decided, title}}``. A Drop outranks a Build."""
    folder = Path(practice_root) / FEED_DIR
    found: dict[str, dict[str, str]] = {}
    if not folder.is_dir():
        return found
    for path in sorted(folder.glob("*.md")):
        meta = _read_front_matter(path)
        ident, verdict = meta.get("id", ""), meta.get("decision", "")
        if not ident or verdict not in DECISIONS:
            continue
        if found.get(ident, {}).get("decision") == DROP:
            continue
        found[ident] = meta
    return found


def record_decision(
    practice_root: str | Path, item: FeedItem, decision: str, *, now: datetime
) -> tuple[Path, bool]:
    """Write one verdict. ``(path, new)`` — a row already decided is left as it is."""
    if decision not in DECISIONS:
        raise ValueError(f"unknown decision {decision!r}")
    if item.id in decisions(practice_root):
        for path in sorted((Path(practice_root) / FEED_DIR).glob(f"*-{_key(item.id)}.md")):
            if _read_front_matter(path).get("decision") in DECISIONS:
                return path, False
    stamp = now.strftime("%Y-%m-%dT%H%M%S")
    path = Path(practice_root) / FEED_DIR / f"{stamp}-{decision}-{_key(item.id)}.md"
    title = " ".join(item.title.split())
    atomic_write_text(
        path,
        "\n".join(
            [
                "---",
                f"id: {item.id}",
                f"decision: {decision}",
                f"decided: {now.isoformat(timespec='seconds')}",
                f"title: {title}",
                "---",
                "",
                f"{decision.capitalize()} — {title}",
                "",
            ]
        ),
    )
    return path, True


# ── what happened around a verdict ──────────────────────────────
#
# Two more kinds of file live beside the verdicts. Neither has a ``decision:`` line,
# so neither is a verdict: `decisions()` here and `read_verdicts()` on the Forge both
# skip them (pinned by a test on each side of that line).
#
#   pitched — the pitch for a row was posted. Without this a row would be posted
#             again every time the feed looked, and the channel would fill with
#             copies. Also what lets a pitch be found again from its row.
#   talk    — he asked to talk a row through, and where. Pressing Talk twice on
#             the same row finds the same eddy rather than opening a second.

PITCHED = "pitched"
TALK = "talk"


def _write_record(practice_root, kind: str, item: FeedItem, fields: dict[str, str], now: datetime) -> Path:
    stamp = now.strftime("%Y-%m-%dT%H%M%S")
    path = Path(practice_root) / FEED_DIR / f"{stamp}-{kind}-{_key(item.id)}.md"
    title = " ".join(item.title.split())
    lines = ["---", f"id: {item.id}", f"kind: {kind}", *[f"{k}: {v}" for k, v in fields.items()],
             f"title: {title}", "---", "", f"{kind.capitalize()} — {title}", ""]
    atomic_write_text(path, "\n".join(lines))
    return path


def _records(practice_root, kind: str) -> dict[str, dict[str, str]]:
    """``{row id: front matter}`` of the newest record of ``kind`` for each row."""
    folder = Path(practice_root) / FEED_DIR
    found: dict[str, dict[str, str]] = {}
    if not folder.is_dir():
        return found
    for path in sorted(folder.glob(f"*-{kind}-*.md")):
        meta = _read_front_matter(path)
        if meta.get("id") and meta.get("kind") == kind:
            found[meta["id"]] = meta
    return found


# 1: the row's own text. 2: the row rewritten as an ideal state. 3: the same, with
# turtleOS's design notes as a source (a pitch at 2 was written without them). A pitch
# below the current format is rewritten in place when the writer can do it
# (`backlog_feed_ui.refresh_pitches`); raise this when what a pitch is made from changes.
PITCH_FORMAT = 3


def record_pitched(
    practice_root, item: FeedItem, *, channel_id, message_id, now: datetime, format: int = PITCH_FORMAT
) -> Path:
    return _write_record(
        practice_root, PITCHED, item,
        {
            "channel": str(channel_id), "message": str(message_id),
            "posted": now.isoformat(timespec="seconds"), "format": str(format),
        },
        now,
    )


def pitched(practice_root) -> dict[str, dict[str, str]]:
    return _records(practice_root, PITCHED)


def record_talk(practice_root, item: FeedItem, *, thread_id, own: bool, now: datetime) -> Path:
    """``own`` is True when the eddy was opened for this pitch, False when it is
    the eddy the row came from."""
    return _write_record(
        practice_root, TALK, item,
        {"thread": str(thread_id), "own": "true" if own else "false", "opened": now.isoformat(timespec="seconds")}, now,
    )


def talk_thread(practice_root, item_id: str) -> str | None:
    meta = _records(practice_root, TALK).get(item_id)
    return meta.get("thread") if meta else None


# ── one call that gathers everything a surface needs ───────────


@dataclass(frozen=True)
class Loaded:
    owner: str
    root: Path
    items: list[FeedItem]
    commit: str


def load(registry: dict, parent_id, *, practice_root_for) -> Loaded:
    """Read the backlog for this craft channel. ``practice_root_for(owner)`` is
    injected: a feed that reached for global configuration could not be tested
    without it."""
    owner, repo, path = feed_source(registry, parent_id)
    text, commit = read_backlog(repo, path)
    return Loaded(owner=owner, root=Path(practice_root_for(owner)), items=parse_backlog(text), commit=commit)


# ── what is next, what is queued ────────────────────────────────


def pending(items: Iterable[FeedItem], practice_root: str | Path) -> list[FeedItem]:
    """Open rows nobody has decided, oldest first (the file lists newest first)."""
    decided = decisions(practice_root)
    return [i for i in reversed(list(items)) if i.is_open and i.id not in decided]


def unposted(items: Iterable[FeedItem], practice_root: str | Path) -> list[FeedItem]:
    """Pending rows whose pitch has not been posted yet, oldest first."""
    posted = pitched(practice_root)
    return [i for i in pending(items, practice_root) if i.id not in posted]


def stale(items: Iterable[FeedItem], practice_root: str | Path) -> list[FeedItem]:
    """Pending rows pitched in an older format than `PITCH_FORMAT`, oldest first —
    the pitches still showing the row's own text. A record with no ``format`` is 1."""
    posted = pitched(practice_root)

    def fmt(meta: dict[str, str]) -> int:
        try:
            return int(meta.get("format", "1"))
        except ValueError:
            return 1

    return [i for i in pending(items, practice_root) if i.id in posted and fmt(posted[i.id]) < PITCH_FORMAT]


def build_queue(items: Iterable[FeedItem], practice_root: str | Path) -> list[FeedItem]:
    """Rows he said Build to that are still open in the backlog — the work
    Spirit has been asked to do. A row that shipped leaves this list on its own."""
    verdicts = decisions(practice_root)
    return [
        i for i in reversed(list(items))
        if i.is_open and verdicts.get(i.id, {}).get("decision") == BUILD
    ]


def counts(items: Iterable[FeedItem], practice_root: str | Path) -> dict[str, int]:
    rows = list(items)
    verdicts = decisions(practice_root)
    open_ids = {i.id for i in rows if i.is_open}
    return {
        "open": len(open_ids),
        "waiting": len(pending(rows, practice_root)),
        "build": sum(1 for k in open_ids if verdicts.get(k, {}).get("decision") == BUILD),
        "drop": sum(1 for k in open_ids if verdicts.get(k, {}).get("decision") == DROP),
    }


# ── words ───────────────────────────────────────────────────────


def compose_pitch(item: FeedItem, *, position: int, total: int, commit: str, written=None) -> str:
    """The message a row becomes. With ``written`` (the rewrite as an ideal state,
    `backlog_feed_write.py`) it is read as a press release; without, it is the row's
    own text, which is what a pitch falls back to when the rewrite cannot be made."""
    marker = f"{position} of {total} — " if total > 1 else ""
    footer = f"-# backlog id: {item.id} · workshop {commit}"
    if written is not None:
        def _say(text: str) -> str:
            return "*The row doesn't say.*" if " ".join(text.split()) == "The row doesn't say." else text

        return "\n".join(
            [
                f"**{marker}{written.headline}**",
                "",
                "**When this exists**",
                _say(written.ideal),
                "",
                "**Why it was filed**",
                _say(written.problem),
                "",
                "**Not this**",
                _say(written.not_this),
                "",
                "**How you'd know**",
                _say(written.check),
                "",
                footer,
            ]
        )
    body = " ".join(item.body.split())
    if len(body) > MAX_BODY_CHARS:
        body = body[: MAX_BODY_CHARS - 1].rstrip() + "…"
    return "\n".join([f"**{marker}{item.title}**", "", body, "", footer])


_NUMBERING = re.compile(r"^\*\*(\d+) of (\d+)\b", re.MULTILINE)


def numbering_from_message(content: str) -> tuple[int, int] | None:
    """``(k, n)`` a pitch was posted with, so a rewrite keeps the number he knows it by."""
    match = _NUMBERING.search(content or "")
    return (int(match.group(1)), int(match.group(2))) if match else None


DISCORD_LIMIT = 2000


def compose_talk_opener(pitch_text: str, context_text: str, *, pitch_url: str | None, came_from_here: bool) -> str:
    """What River posts into the eddy where a pitch is talked through: the pitch as he
    read it, and what is known about it. Turtle reads it as the eddy's first context,
    so the conversation starts from the same page he is on. It asks nothing."""
    head = (
        "**A backlog pitch is being talked through here.** This is the conversation the row came from."
        if came_from_here
        else "**A backlog pitch is being talked through here.**"
    )
    pitch = FOOTER.sub("", pitch_text or "").strip()
    tail = [f"-# Decide: {pitch_url}"] if pitch_url else []
    fixed = "\n\n".join([head, pitch, *tail])
    room = DISCORD_LIMIT - len(fixed) - 4
    if context_text and room > 200:
        text = context_text if len(context_text) <= room else context_text[: room - 1].rstrip() + "…"
        return "\n\n".join([head, pitch, text, *tail])
    return fixed[:DISCORD_LIMIT]


BRIEF_PARTS = (
    "What is true when it is finished, in your words (the pitch's *When this exists* is a draft)",
    "What has been decided here, and why",
    "What is not part of it",
    "How you would check that it worked",
    "What Spirit must not guess: people, data, anything that cannot be undone",
)


def compose_talk_destination(pitch_url: str | None) -> str:
    """Where a talked-through pitch is going — the second post in its eddy.

    A conversation with no destination wanders, and Craft Turtle can only help it
    arrive if it knows what arriving is. Two ends: Drop, or Build with a brief Spirit
    can carry out without asking him anything. That is the house definition of a
    ready eddy (`core/craft_readiness.py`), put where the conversation starts and not
    guessed afterwards from the note.
    """
    parts = "\n".join(f"{n}. {text}" for n, text in enumerate(BRIEF_PARTS, start=1))
    where = f" Build and Drop are on the pitch: {pitch_url}" if pitch_url else ""
    return (
        "**Where this conversation is going.** It ends in one of two ways. *Drop*: it is not worth doing, "
        "and it does not come back. *Build*: it is, and what is said here becomes a brief Spirit can carry out "
        "without asking you anything. The brief has five parts, and this conversation is done when each has an answer:\n\n"
        f"{parts}\n\n"
        "Craft Turtle: ask for the first part that has no answer yet, one at a time, and say which part it is. "
        "When all five are answered, write the brief out in plain words and say it is ready for Build."
        f"{where}"
    )[:2000]


def item_id_from_message(content: str) -> str | None:
    match = FOOTER.search(content or "")
    return match.group("id") if match else None


def compose_queue(queue: list[FeedItem]) -> str:
    if not queue:
        return "Nothing is waiting for Spirit."
    lines = [f"**Waiting for Spirit** — {len(queue)}"]
    lines += [f"- {i.title}" for i in queue]
    return "\n".join(lines)[:1900]


def compose_status(c: dict[str, int], commit: str) -> str:
    return (
        f"{c['open']} open in the backlog (workshop {commit}). "
        f"{c['waiting']} wait for your word, {c['build']} for Spirit to build, "
        f"{c['drop']} dropped but not yet applied by the Forge."
    )
