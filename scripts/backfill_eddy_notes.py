#!/usr/bin/env python3
"""Write eddy notes for conversations that happened before the story layer existed.

The story layer began 2026-07-15. Everything a practitioner said before that
date lives only as Discord messages: not in ``story/eddies/``, so not on the
searchable shelf (``artifact_viewer.iter_artifact_files``), not reachable by
``!search`` or by Turtle's ``search_practice_files`` tool, and not visible to
any retrieval the continuity engine might grow. In the operator's own river
that is 179 threads and 3,193 messages going back to 2026-03-18.

This reads those threads from Discord and runs them through the **live** note
writer — same prompts, same voice rules, same quality floor. A parallel
"backfill formatter" would have been easier and would have quietly dropped the
rules the corpus paid for (``_THIRD_PARTY_RULE`` and the witness/solo branch
are INT-049 and INT-040), so it reuses ``story_notes.write_eddy_note`` instead
and passes what the live path would otherwise get wrong about a past eddy:
the title (no gateway), the timestamp (not today), the alive layer (empty).

**One root at a time, named explicitly, and the default is the operator's own.**
Every other root on this host is another person's record; reading one is a
sanction-list act and the consent record that would govern it does not exist
yet (``consent.py`` is built and unwired). ``--root`` will not accept a root
whose registry entry is not the invoking operator's without ``--i-have-consent``,
which is a claim a human makes, not a flag a script sets for itself.

Usage:
    python3 scripts/backfill_eddy_notes.py --dry-run
    python3 scripts/backfill_eddy_notes.py --before 2026-07-15 --limit 5
    python3 scripts/backfill_eddy_notes.py            # the whole backlog

Idempotent: a thread that already has a note file is skipped, so an interrupted
run is resumed by re-running it.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DISCORD_API = "https://discord.com/api/v10"
DISCORD_EPOCH_MS = 1420070400000

# Discord's edge rejects urllib's default agent with a bare 403 that looks
# exactly like a bad token. The API requires a declared bot agent.
USER_AGENT = "DiscordBot (https://github.com/malteristo/turtle-os, 1.0)"

# The story layer's first note. Threads whose last message predates this never
# had a chance to be written down.
STORY_LAYER_START = "2026-07-15"

# Matches the live path: sessions.py declines to reflect below this, so a
# backfilled note over fewer exchanges would be a note the practice would never
# have written.
MIN_MESSAGES = 4


def dialogue_window() -> int:
    """``helpers.load_thread_history`` trims to ``MAX_DIALOGUE_HISTORY``, so a
    live note has always been a reading of the last N exchanges rather than the
    whole thread. Backfill inherits the same window on purpose: matching what a
    note *would* have said beats a fuller reading the format never had.

    Imported lazily — ``state`` pulls in ``discord``, which the tests and any
    non-runtime checkout do not have.
    """
    from state import MAX_DIALOGUE_HISTORY

    return MAX_DIALOGUE_HISTORY


def snowflake_time(sid: str | int) -> datetime:
    """Discord ids carry their own creation time — no extra API call needed."""
    return datetime.fromtimestamp(
        ((int(sid) >> 22) + DISCORD_EPOCH_MS) / 1000, timezone.utc
    )


class Discord:
    """The few REST calls this needs. discord.py wants a gateway connection and
    an event loop it owns; a backfill is a batch job and should not need one."""

    def __init__(self, token: str) -> None:
        self._token = token

    def _get(self, path: str, *, retries: int = 5):
        url = f"{DISCORD_API}{path}"
        for attempt in range(retries):
            req = urllib.request.Request(
                url,
                headers={
                    "Authorization": f"Bot {self._token}",
                    "User-Agent": USER_AGENT,
                },
            )
            try:
                with urllib.request.urlopen(req) as resp:
                    return json.load(resp)
            except urllib.error.HTTPError as exc:
                if exc.code == 429:
                    # Honour the server's own number; guessing a backoff is how
                    # a batch job earns a longer ban than the one it avoided.
                    try:
                        retry_after = float(json.load(exc).get("retry_after", 1.0))
                    except Exception:
                        retry_after = 1.0
                    time.sleep(retry_after + 0.5)
                    continue
                if 500 <= exc.code < 600 and attempt < retries - 1:
                    time.sleep(2**attempt)
                    continue
                raise
        raise RuntimeError(f"giving up on {path} after {retries} attempts")

    def me(self) -> dict:
        return self._get("/users/@me")

    def channel(self, channel_id: str) -> dict:
        return self._get(f"/channels/{channel_id}")

    def threads(self, guild_id: str, parent_id: str) -> list[dict]:
        """Active + archived public threads under one parent channel.

        Active threads are only listable guild-wide; archived ones only
        per-channel. Both halves are needed — a thread's archive state says how
        recently it was touched, not whether it matters.
        """
        found: list[dict] = []
        active = self._get(f"/guilds/{guild_id}/threads/active").get("threads", [])
        found.extend(t for t in active if t.get("parent_id") == parent_id)

        before = None
        while True:
            path = f"/channels/{parent_id}/threads/archived/public?limit=100"
            if before:
                path += f"&before={before}"
            page = self._get(path)
            batch = page.get("threads", [])
            found.extend(batch)
            if not page.get("has_more") or not batch:
                break
            before = batch[-1].get("thread_metadata", {}).get("archive_timestamp")
            if not before:
                break
        return found

    def messages(self, channel_id: str, limit: int) -> list[dict]:
        """Newest ``limit`` messages, returned oldest-first."""
        out: list[dict] = []
        before = None
        while len(out) < limit:
            path = f"/channels/{channel_id}/messages?limit={min(100, limit - len(out))}"
            if before:
                path += f"&before={before}"
            batch = self._get(path)
            if not batch:
                break
            out.extend(batch)
            before = batch[-1]["id"]
            if len(batch) < 100:
                break
        return list(reversed(out))


def build_history(messages: list[dict], turtle_bot_id: str) -> list[dict]:
    """Discord messages → the in-memory history shape.

    Mirrors ``helpers.load_thread_history`` deliberately: same ``[name]:``
    prefix on member turns (the witness layer parses authorship back out of it —
    INT-040), same skip of the thread-open marker, same attachment note. Only
    Turtle's own messages become ``assistant``; River's embeds and the eddy bar
    are furniture, not conversation.
    """
    history: list[dict] = []
    for msg in messages:
        author = msg.get("author") or {}
        content = (msg.get("content") or "").strip()
        if author.get("bot"):
            if str(author.get("id")) != str(turtle_bot_id):
                continue
            if not content or content.startswith("🧵"):
                continue
            history.append({"role": "assistant", "content": content})
            continue
        note = ""
        attachments = msg.get("attachments") or []
        if attachments:
            fnames = ", ".join(a.get("filename", "?") for a in attachments[:5])
            note = f" [attached: {fnames}]"
            if not content:
                content = f"(attachment: {fnames})"
        if not content:
            continue
        name = author.get("global_name") or author.get("username") or "practitioner"
        history.append({"role": "user", "content": f"[{name}]: {content}{note}"})
    return history


def existing_note(practice_dir: Path, thread_id: str) -> Path | None:
    hits = sorted((practice_dir / "story" / "eddies").glob(f"{thread_id}-*.md"))
    return hits[0] if hits else None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--root",
        default=None,
        help="practice root key (default: the operator's own, from the registry)",
    )
    p.add_argument(
        "--before",
        default=STORY_LAYER_START,
        help=f"only threads last active before this date (default: {STORY_LAYER_START})",
    )
    p.add_argument(
        "--since",
        default=None,
        help=(
            "only threads last active on or after this date. Added 2026-08-07 "
            "to repair a *specific* gap: a note write that failed on a timeout "
            "leaves a modern thread unnoted, and sweeping from the story-layer "
            "start to reach it would also write notes for a dozen old shakedown "
            "threads (Shelter, Navigator, blank-eddy dogfood). Candidates sort "
            "oldest-first, so --limit narrows to exactly the wrong end."
        ),
    )
    p.add_argument("--min-messages", type=int, default=MIN_MESSAGES)
    p.add_argument("--limit", type=int, default=0, help="stop after N notes (0 = all)")
    p.add_argument("--dry-run", action="store_true", help="list what would be written")
    p.add_argument(
        "--i-have-consent",
        action="store_true",
        help="required to read a root that is not the invoking operator's own",
    )
    return p.parse_args(argv)


async def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        print("DISCORD_BOT_TOKEN not set", file=sys.stderr)
        return 2

    import mage

    registry = mage.get_registry() or {}
    mages = registry.get("mages", {}) or {}

    operator = next(
        (key for key, val in mages.items() if isinstance(val, dict) and val.get("primary")),
        registry.get("default_mage"),
    )
    root = args.root or operator
    if not root:
        print("no operator root in the registry; pass --root explicitly", file=sys.stderr)
        return 2

    entry = mages.get(root)
    if not entry:
        print(f"unknown root {root!r}; known: {', '.join(sorted(mages))}", file=sys.stderr)
        return 2

    if root != operator and not args.i_have_consent:
        print(
            f"{root!r} is not the operator root ({operator!r}).\n"
            "Reading another practitioner's record is a sanction-list act and the\n"
            "consent record that would govern it is not wired yet. If that person\n"
            "has actually agreed, re-run with --i-have-consent.",
            file=sys.stderr,
        )
        return 3

    practice_dir = Path(entry.get("practice_dir") or "").expanduser()
    if not practice_dir.is_dir():
        print(f"practice_dir missing for {root}: {practice_dir}", file=sys.stderr)
        return 2

    resolved = mage.river_channel_id_for_mage_key(root)
    if not resolved:
        print(f"no river channel registered for {root}", file=sys.stderr)
        return 2
    river_id = str(resolved)

    cutoff = datetime.fromisoformat(args.before).replace(tzinfo=timezone.utc)
    floor = (
        datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc)
        if args.since
        else None
    )
    api = Discord(token)
    turtle_bot_id = str(api.me()["id"])
    guild_id = str(api.channel(river_id)["guild_id"])

    threads = api.threads(guild_id, river_id)
    print(f"root {root} · river {river_id} · {len(threads)} threads visible")

    candidates = []
    skipped_short = skipped_recent = skipped_noted = skipped_old = 0
    for t in threads:
        tid = str(t["id"])
        if t.get("message_count", 0) < args.min_messages:
            skipped_short += 1
            continue
        last = t.get("last_message_id")
        when = snowflake_time(last) if last else snowflake_time(tid)
        if when >= cutoff:
            skipped_recent += 1
            continue
        if floor and when < floor:
            skipped_old += 1
            continue
        if existing_note(practice_dir, tid):
            skipped_noted += 1
            continue
        candidates.append((t, when))

    candidates.sort(key=lambda pair: pair[1])
    window_note = f"{skipped_recent} at/after {args.before}"
    if floor:
        window_note += f", {skipped_old} before {args.since}"
    print(
        f"  {len(candidates)} to write · skipped {skipped_short} under "
        f"{args.min_messages} msgs, {window_note}, "
        f"{skipped_noted} already noted"
    )
    if args.limit:
        candidates = candidates[: args.limit]
        print(f"  --limit {args.limit}: writing {len(candidates)}")

    if args.dry_run:
        for t, when in candidates:
            print(f"  {when.date()}  {t.get('message_count'):>4} msgs  {t.get('name','')[:60]}")
        return 0

    from story_notes import EddyNoteError, write_eddy_note

    window = dialogue_window()
    written = failed = empty = 0
    for idx, (t, when) in enumerate(candidates, 1):
        tid = str(t["id"])
        title = t.get("name") or "eddy"
        try:
            msgs = api.messages(tid, window)
            history = build_history(msgs, turtle_bot_id)
            if len(history) < args.min_messages:
                # message_count includes River's furniture; the conversation
                # itself can be shorter than the thread.
                empty += 1
                print(f"  [{idx}/{len(candidates)}] skip (thin after filtering): {title[:50]}")
                continue
            result = await write_eddy_note(
                int(tid),
                history,
                trigger="backfill",
                parent_channel_id=int(river_id),
                title=title,
                occurred_at=when.astimezone(),
                alive_items=[],
            )
            written += 1
            print(f"  [{idx}/{len(candidates)}] {when.date()} → {result.note_path.name}")
        except EddyNoteError as exc:
            empty += 1
            print(f"  [{idx}/{len(candidates)}] declined ({exc}): {title[:50]}")
        except Exception as exc:  # keep going; one bad thread is not the run
            failed += 1
            print(f"  [{idx}/{len(candidates)}] FAILED {type(exc).__name__}: {exc}")

    print(f"\nwritten {written} · declined/thin {empty} · failed {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
