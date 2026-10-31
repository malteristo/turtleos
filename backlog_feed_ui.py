"""The feed's Discord half: pitches in craft, and the buttons under each one.

Each open backlog row becomes a message of its own — the row written as the ideal
state it asks for (`backlog_feed_write.py`), with what turtleOS already holds about
it and the row as filed in an embed — and three buttons: **Build**, **Drop**, and **Talk it
through**. The messages stay where they are. A pitch waits for him as long as it
takes; the buttons have no timeout and are re-armed at startup, so a pitch from
last week answers the same as one from a minute ago.

**When pitches arrive.** They arrive on their own — River's heartbeat posts any
open row that has not been pitched yet (`feed_chore`), at most once each, never at
night. The first beat posts the whole existing backlog back to back; after that a
row appears when it is added. This is the prompt for the offer, defined
2026-10-10: *what* is a backlog row, *from what* is the workshop's head, *when* is
"a row has no pitch yet", and what an answer writes is a verdict file. `!feed`
posts whatever has not been posted yet without waiting for the beat. The beat does
its work in the background and only while no conversation is live (the deploy
guard's own check), because each rewrite holds the one local-inference slot for tens
of seconds; pitches posted in an older format are edited in place the same way. A channel opts
in with `push: true` under its `backlog_feed` in the registry.

**Talk it through.** An unconvincing pitch is improved by talking, not by editing a
field (the standing finding in `craft_ready_ui.py`). If the row came from a craft
eddy, River posts the pitch and its context into that eddy and the button becomes a
link to it. Otherwise River opens an eddy for the pitch, with the same post at its
top. Either way Turtle reads that post when he starts to talk. Eddies of other
channels are never posted into and never linked: a row can come from a private room
and the pitch must not carry craft into it or it out of it.

The two answering buttons carry fixed ids and read which row they are under from the
message's own footer, so a restart needs one `add_view` and no per-message
bookkeeping — the same shape as the `!model` menu. The process that posts a pitch is
the process that has to answer it; River posts, so River answers, and both bots arm
the view.

Why Drop exists when offers carry no decline button: see `backlog_feed.py`.
"""

from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import discord

from backlog_feed import (
    BUILD,
    DROP,
    FeedUnavailable,
    build_queue,
    compose_pitch,
    compose_queue,
    compose_status,
    compose_talk_destination,
    compose_talk_opener,
    counts,
    feed_source,
    in_quiet_hours,
    item_id_from_message,
    load,
    may_decide,
    push_enabled,
    read_optional,
    record_decision,
    record_pitched,
    pitched,
    record_talk,
    stale,
    talk_thread,
    unposted,
    numbering_from_message,
    decisions,
    PITCH_FORMAT,
)
from backlog_feed_context import (
    ALTBACKLOG_PATH,
    BOOM_PATH,
    compose_embed,
    jump_url,
    load_corpus,
    origin_candidates,
    read_design_notes,
)
from backlog_feed_judge import context_for_item
from backlog_feed_write import write_for_item

BUILD_ID = "craft:feed:build"
DROP_ID = "craft:feed:drop"
TALK_ID = "craft:feed:talk"
ACT = "Backlog pitch handled."

AUTO_MAX = 60  # more than this unposted at once is not a feed, it is a surprise: `!feed` posts them
PAUSE_S = 1.0

_get_registry = None
_practice_root_for = None
# Opens an eddy in a channel. Handed in by the shell: importing the spawner here would
# put this module in the runtime's mutual-dependency component for one function.
_spawn_eddy = None
_post_lock = asyncio.Lock()

_NOT_YOURS = "These pitches are for the owner of this channel."
_NOT_READY = "The feed is not ready yet."


def _parent_id(channel) -> int:
    return getattr(channel, "parent_id", None) or channel.id


def _now() -> datetime:
    return datetime.now().astimezone()


class FeedView(discord.ui.View):
    """Build, Drop, and Talk. With a ``thread_url`` the third button is a link."""

    def __init__(self, thread_url: str | None = None):
        super().__init__(timeout=None)
        build = discord.ui.Button(label="Build", custom_id=BUILD_ID, style=discord.ButtonStyle.primary)
        build.callback = self._build
        drop = discord.ui.Button(label="Drop", custom_id=DROP_ID, style=discord.ButtonStyle.secondary)
        drop.callback = self._drop
        self.add_item(build)
        self.add_item(drop)
        if thread_url:
            self.add_item(discord.ui.Button(label="Open the eddy", url=thread_url))
        else:
            talk = discord.ui.Button(label="Talk it through", custom_id=TALK_ID, style=discord.ButtonStyle.secondary)
            talk.callback = self._talk
            self.add_item(talk)

    async def _build(self, interaction: discord.Interaction) -> None:
        await _decide(interaction, BUILD)

    async def _drop(self, interaction: discord.Interaction) -> None:
        await _decide(interaction, DROP)

    async def _talk(self, interaction: discord.Interaction) -> None:
        await _talk(interaction)


# ── posting pitches ─────────────────────────────────────────────


async def _pitch_parts(corpus, item, *, position, total, commit, guild_id):
    """``(message text, embed text, format)``. The rewrite when the writer can make
    one; otherwise the row's own text, at format 1, which `refresh_pitches` retries."""
    context = await context_for_item(corpus, item)
    written = await write_for_item(item, context)
    text = compose_pitch(item, position=position, total=total, commit=commit, written=written)
    return text, compose_embed(context, guild_id, item.body), (PITCH_FORMAT if written else 1)


def _corpus_for(loaded, registry, parent_id):
    _owner, repo, _path = feed_source(registry, parent_id)
    return asyncio.to_thread(
        lambda: load_corpus(
            loaded.root,
            parent_id,
            boom_text=read_optional(repo, BOOM_PATH),
            altbacklog_text=read_optional(repo, ALTBACKLOG_PATH),
            design_notes=read_design_notes(Path(__file__).resolve().parent),
        )
    )


def _guild_id(channel) -> int:
    return getattr(getattr(channel, "guild", None), "id", 0)


# How long the beat waits for a conversation to go quiet before it stops for now. Each
# rewrite holds the one local-inference slot for tens of seconds; a reply he is waiting
# for must not queue behind a pitch.
QUIET_MINUTES = 3
BUSY_WAIT_S = 60
BUSY_WAITS = 20
RETRY_AFTER_S = 3600  # a row the writer could not do is tried again after this

_attempted: dict[str, float] = {}


def _conversation_busy() -> bool:
    """True only when the deploy guard *sees* a conversation. A guard that cannot see
    ('unknown') does not block a background rewrite: waiting forever is the worse error."""
    try:
        from scripts.deploy_guard import assess

        return assess(quiet_minutes=QUIET_MINUTES).get("verdict") == "busy"
    except Exception:  # noqa: BLE001 — not seeing is not a reason to stop
        return False


async def _may_work(gentle: bool) -> bool:
    """For the beat: wait out a live conversation; stop at night. `!feed` is not gentle."""
    if not gentle:
        return True
    for _ in range(BUSY_WAITS):
        tz = ZoneInfo(os.environ.get("PRACTICE_TIMEZONE", "Europe/Berlin"))
        if in_quiet_hours(datetime.now(tz)):
            return False
        if not _conversation_busy():
            return True
        await asyncio.sleep(BUSY_WAIT_S)
    return False


async def post_pending(
    channel, registry: dict, parent_id, *, limit: int | None = None, pause: float | None = None, gentle: bool = False
) -> int:
    """Post the pitch of every open row that has none, oldest first. Returns how many.

    Holding the lock makes two callers (the beat and `!feed`) take turns instead of
    each posting the same rows; a row is recorded as pitched the moment its message
    exists, so a second pass finds nothing left.
    """
    pause = PAUSE_S if pause is None else pause
    posted = 0
    async with _post_lock:
        loaded = load(registry, parent_id, practice_root_for=_practice_root_for)
        batch = unposted(loaded.items, loaded.root)
        if limit is not None:
            batch = batch[:limit]
        if not batch:
            return 0
        corpus = await _corpus_for(loaded, registry, parent_id)
        for index, item in enumerate(batch, start=1):
            if not await _may_work(gentle):
                break
            text, embed_text, fmt = await _pitch_parts(
                corpus, item, position=index, total=len(batch), commit=loaded.commit, guild_id=_guild_id(channel)
            )
            sent = await channel.send(text, embed=discord.Embed(description=embed_text), view=FeedView())
            record_pitched(loaded.root, item, channel_id=channel.id, message_id=sent.id, now=_now(), format=fmt)
            posted += 1
            if pause:
                await asyncio.sleep(pause)
    return posted


async def refresh_pitches(
    channel, registry: dict, parent_id, *, gentle: bool = False, pause: float | None = None
) -> int:
    """Rewrite, in place, the pitches that still show the row's own text. Returns how
    many were rewritten.

    Edits the message he already has — same place in the channel, same number — so a
    pitch he has been meaning to get to is the one he finds. A row the writer cannot do
    is left as it is and tried again later. A row decided in the meantime is skipped:
    editing would give a decided message its buttons back.
    """
    pause = PAUSE_S if pause is None else pause
    done = 0
    async with _post_lock:
        loaded = load(registry, parent_id, practice_root_for=_practice_root_for)
        todo = [
            i for i in stale(loaded.items, loaded.root)
            if time.monotonic() - _attempted.get(i.id, -RETRY_AFTER_S) >= RETRY_AFTER_S
        ]
        if not todo:
            return 0
        recorded = pitched(loaded.root)
        corpus = await _corpus_for(loaded, registry, parent_id)
        for item in todo:
            if not await _may_work(gentle):
                break
            meta = recorded[item.id]
            try:
                message = await channel.fetch_message(int(meta["message"]))
            except discord.NotFound:
                message = None
            except (discord.HTTPException, ValueError, KeyError):
                continue
            k, n = numbering_from_message(getattr(message, "content", "")) or (1, 1)
            text, embed_text, fmt = await _pitch_parts(
                corpus, item, position=k, total=n, commit=loaded.commit, guild_id=_guild_id(channel)
            )
            _attempted[item.id] = time.monotonic()
            if fmt < PITCH_FORMAT:
                continue
            if item.id in decisions(loaded.root):
                continue
            thread = talk_thread(loaded.root, item.id)
            view = FeedView(thread_url=jump_url(_guild_id(channel), thread) if thread else None)
            embed = discord.Embed(description=embed_text)
            if message is None:
                message = await channel.send(text, embed=embed, view=view)
            else:
                await message.edit(content=text, embed=embed, view=view)
            record_pitched(loaded.root, item, channel_id=channel.id, message_id=message.id, now=_now(), format=fmt)
            done += 1
            if pause:
                await asyncio.sleep(pause)
    return done


_worker: asyncio.Task | None = None


async def _work(channel, registry: dict, parent_id) -> None:
    """The beat's work, in the background: a rewrite takes tens of seconds and the
    heartbeat runs its other chores one after another."""
    try:
        n = await post_pending(channel, registry, parent_id, gentle=True)
        m = await refresh_pitches(channel, registry, parent_id, gentle=True)
        if n or m:
            print(f"Backlog feed: posted {n}, rewrote {m} in {parent_id}")
    except Exception as exc:  # noqa: BLE001 — a background task has no one to raise to
        print(f"Backlog feed work failed: {type(exc).__name__}: {exc}")


async def feed_chore(client) -> str | None:
    """River's heartbeat chore: start the work for channels that opted in — post
    pitches for rows that have none, rewrite those still in the row's own text.
    Quiet at night; a flood waits for `!feed`."""
    global _worker
    if _get_registry is None or _practice_root_for is None:
        return None
    if _worker is not None and not _worker.done():
        return None
    registry = _get_registry()
    tz = ZoneInfo(os.environ.get("PRACTICE_TIMEZONE", "Europe/Berlin"))
    if in_quiet_hours(datetime.now(tz)):
        return None
    lines: list[str] = []
    for channel_id, entry in ((registry or {}).get("channels") or {}).items():
        if not isinstance(entry, dict) or not push_enabled(registry, channel_id):
            continue
        try:
            channel = client.get_channel(int(channel_id)) or await client.fetch_channel(int(channel_id))
            loaded = load(registry, channel_id, practice_root_for=_practice_root_for)
            waiting = len(unposted(loaded.items, loaded.root))
            rewrites = len(stale(loaded.items, loaded.root))
        except (FeedUnavailable, discord.HTTPException) as exc:
            lines.append(f"feed {channel_id}: {exc}")
            continue
        if waiting > AUTO_MAX:
            lines.append(f"{waiting} pitches are waiting in {channel_id}; `!feed` posts them")
            waiting = 0
        if waiting or rewrites:
            _worker = asyncio.create_task(_work(channel, registry, channel_id))
            lines.append(f"working on {waiting} new and {rewrites} older pitches in {channel_id}")
            break
    return "; ".join(lines) or None


# ── pressing a button ───────────────────────────────────────────


async def _owner_and_item(interaction: discord.Interaction):
    """``(registry, parent_id, loaded, item)`` or None after answering why not."""
    if _get_registry is None or _practice_root_for is None:
        await interaction.response.send_message(_NOT_READY, ephemeral=True)
        return None
    registry = _get_registry()
    parent_id = _parent_id(interaction.channel)
    if not may_decide(registry, parent_id, interaction.user.id):
        await interaction.response.send_message(_NOT_YOURS, ephemeral=True)
        return None
    try:
        loaded = load(registry, parent_id, practice_root_for=_practice_root_for)
    except FeedUnavailable as exc:
        await interaction.response.send_message(str(exc), ephemeral=True)
        return None
    ident = item_id_from_message(getattr(interaction.message, "content", ""))
    item = next((i for i in loaded.items if i.id == ident), None) if ident else None
    return registry, parent_id, loaded, item


async def _decide(interaction: discord.Interaction, decision: str) -> None:
    found = await _owner_and_item(interaction)
    if found is None:
        return
    _registry, _pid, loaded, item = found
    if item is None or not item.is_open:
        await interaction.response.edit_message(
            content="This one is no longer open in the backlog. Nothing recorded.", embed=None, view=None
        )
        return
    record_decision(loaded.root, item, decision, now=_now())
    waiting = counts(loaded.items, loaded.root)["waiting"]
    verdict = (
        f"**Build** — {item.title}. Spirit has it." if decision == BUILD else f"**Dropped** — {item.title}."
    )
    await interaction.response.edit_message(
        content=f"{verdict}\n-# {waiting} left to decide", embed=None, view=None
    )


async def _open_origin(interaction: discord.Interaction, parent_id, candidates):
    """The eddy the row came from, if it is a live eddy of this craft channel."""
    for raw in candidates:
        try:
            channel = interaction.client.get_channel(int(raw)) or await interaction.client.fetch_channel(int(raw))
        except (discord.HTTPException, ValueError):
            continue
        if isinstance(channel, discord.Thread) and channel.parent_id == parent_id:
            return channel
    return None


async def _talk(interaction: discord.Interaction) -> None:
    found = await _owner_and_item(interaction)
    if found is None:
        return
    _registry, parent_id, loaded, item = found
    await interaction.response.defer(ephemeral=True)
    if item is None:
        await interaction.followup.send("I can't find this pitch in the backlog any more.", ephemeral=True)
        return
    guild_id = interaction.guild_id or 0
    thread_id = talk_thread(loaded.root, item.id)
    if thread_id is None:
        embeds = getattr(interaction.message, "embeds", None) or []
        context_text = (embeds[0].description or "") if embeds else ""
        pitch_url = getattr(interaction.message, "jump_url", None)
        pitch_text = getattr(interaction.message, "content", "") or item.title
        thread = await _open_origin(interaction, parent_id, origin_candidates(loaded.root, item.id, item.body))
        own = thread is None
        try:
            if own and _spawn_eddy is not None:
                thread = await _spawn_eddy(interaction.channel, topic=item.title[:100])
            elif getattr(thread, "archived", False):
                await thread.edit(archived=False)
            if thread is not None:
                await thread.send(
                    compose_talk_opener(pitch_text, context_text, pitch_url=pitch_url, came_from_here=not own)
                )
                await thread.send(compose_talk_destination(pitch_url))
        except discord.HTTPException as exc:
            await interaction.followup.send(f"I could not open the conversation ({exc}).", ephemeral=True)
            return
        if thread is None:
            await interaction.followup.send("I could not open an eddy for this one.", ephemeral=True)
            return
        thread_id = str(thread.id)
        record_talk(loaded.root, item, thread_id=thread_id, own=own, now=_now())
    url = jump_url(guild_id, thread_id)
    try:
        await interaction.message.edit(view=FeedView(thread_url=url))
    except discord.HTTPException:
        pass
    await interaction.followup.send(f"Talk it through here: {url}", ephemeral=True)


# ── !feed ───────────────────────────────────────────────────────


async def cmd_feed(message, args):
    """`!feed` — post every pitch not posted yet. `!feed queue` — what Spirit has been
    asked to build. `!feed status`."""
    if _get_registry is None or _practice_root_for is None:
        await message.reply(_NOT_READY, mention_author=False)
        return "Feed not armed."
    registry = _get_registry()
    parent_id = _parent_id(message.channel)
    if not may_decide(registry, parent_id, message.author.id):
        await message.reply(_NOT_YOURS, mention_author=False)
        return "Feed refused: not the owner."
    try:
        word = args[0].lower() if args else ""
        loaded = load(registry, parent_id, practice_root_for=_practice_root_for)
        c = counts(loaded.items, loaded.root)
        if word == "queue":
            await message.reply(compose_queue(build_queue(loaded.items, loaded.root)), mention_author=False)
            return "Feed queue shown."
        if word == "status":
            await message.reply(compose_status(c, loaded.commit), mention_author=False)
            return "Feed status shown."
        waiting = len(unposted(loaded.items, loaded.root))
    except FeedUnavailable as exc:
        await message.reply(str(exc), mention_author=False)
        return "Feed unavailable."
    if not waiting:
        await message.reply(
            "Every open row has been pitched already. " + compose_status(c, loaded.commit), mention_author=False
        )
        return "Nothing new to pitch."
    if _post_lock.locked():
        await message.reply("Pitches are being posted now.", mention_author=False)
        return "Feed already posting."
    await message.reply(f"Posting {waiting} pitches. Each one waits for you.", mention_author=False)
    asyncio.create_task(_post_and_report(message.channel, registry, parent_id))
    return "Backlog pitches posting."


async def _post_and_report(channel, registry: dict, parent_id) -> None:
    try:
        await post_pending(channel, registry, parent_id)
    except Exception as exc:  # noqa: BLE001 — a background task has no one to raise to
        print(f"Backlog feed post failed: {type(exc).__name__}: {exc}")
        try:
            await channel.send(f"The feed stopped partway ({type(exc).__name__}). `!feed` continues where it left off.")
        except discord.HTTPException:
            pass


def arm_feed(client, get_registry, practice_root_for, spawn_eddy=None) -> None:
    """The shell hands these in. A button press has no other way to see the room."""
    global _get_registry, _practice_root_for, _spawn_eddy
    _get_registry = get_registry
    _practice_root_for = practice_root_for
    _spawn_eddy = spawn_eddy
    client.add_view(FeedView())
