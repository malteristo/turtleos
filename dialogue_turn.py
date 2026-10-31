"""Dialogue turn execution — handle_dialogue and LLM reply path.

Slice 3 of discord_bot.py decomposition (2026-07-10).
Re-exported from discord_bot for backward compatibility.

Turns are serialized per channel by ``dialogue_queue``. Since 2026-08-07 that
queue also *coalesces*: messages that arrive while a reply is in flight are
absorbed into history in order, and the newest one answers them together.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime, timezone

import discord

from content_fetch import (
    extract_urls as _extract_urls,
    format_text_attachments_for_dialogue,
    split_text_and_vision_attachments,
)
from dialogue_attachments import (
    attachment_display_names,
    attachments_from_forward_chain,
    gather_dialogue_attachments,
    intake_primitive_attachments,
)
from dialogue_message import (
    forward_source_ref,
    forwarded_snapshot_is_partial,
    visible_message_content,
)
from dialogue_runtime import (
    build_native_runtime_env,
    build_runtime_env,
    build_source_trace,
    update_thread_state,
)
from eddy_spawn import ensure_native_presence, post_flow_presence_if_needed
from helpers import (
    get_history,
    load_thread_history,
    preprocess_attachments,
    split_message,
    summarize_thread_context,
    sync_history,
)
from llm import (
    chat_anthropic_with_model,
    chat_gemini,
    chat_ollama,
    chat_ollama_with_tools,
)
from link_read import (
    external_urls,
    fetch_urls_with_status,
    inject_limit,
    maybe_refine_thread_name_from_fetch,
    post_link_offer,
)
from mage import get_pd, resolve_dialogue_channel_id
from practice_io import read_thread_state
from prompts import (
    get_craft_channel_prompt,
    get_health_channel_prompt,
    get_native_eddy_prompt,
    get_system_prompt,
    get_thread_prompt,
    uses_native_turtle_prompt,
)
from sessions import maybe_reflect
import state
from state import (
    DIALOGUE_MODEL,
    EDDY_DEFAULT,
    GOOGLE_API_KEY,
    HAS_GEMINI,
    MAX_DIALOGUE_HISTORY,
    REFLECTION_MODEL,
    TURTLE_MODEL,
    USE_API,
    absorbed_contexts,
    active_sessions,
    dialogue_histories,
    thread_configs,
)
import cloud_fallback
from core.model_profiles import awareness_block
from room_models import owner_line, resolve_room_model
from thread_registry import register_thread, update_thread_activity
from tos_tools import (
    build_tool_report,
    execute_tos_tool,
    local_governed_tools_for_channel,
    memory_tools_for_channel,
    team_tools_for_channel,
    tools_for_channel,
)
from triage import triage_message
from turn_trace import (
    CARD_EDIT_INTERVAL_SECONDS,
    CARD_TICK_SECONDS,
    PROGRESS_AFTER_SECONDS,
    AttunementSteps,
    Step,
    attunement_step_list,
    describe_tool,
    prose_step,
    remember_step,
    render_card,
    render_log,
    render_trace,
    tool_names,
)

# A message the prompt has already grown past: a link spill or an attachment
# is in it, or the practitioner wrote at length. The room's topic memory then
# renders compact (one excerpt per topic) — the memory is kept, its cost is
# not doubled on the turns that are already the slow ones.
COMPACT_TOPICS_MESSAGE_CHARS = int(os.environ.get("COMPACT_TOPICS_MESSAGE_CHARS", "4000"))



def _magic_loop_limits(prompt_profile: str) -> dict:
    """What a magic turn's model loop is allowed: more rounds, and a reply without the narration."""
    if prompt_profile != "magic":
        return {}
    from magic_prompt import MAGIC_TOOL_ROUNDS

    return {"max_rounds": MAGIC_TOOL_ROUNDS, "final_prose_only": True}


class _SpiritPosted:
    """A message Spirit posted, so later edits go through the same account."""

    def __init__(self, channel_id: int, message_id: int):
        self.channel_id = channel_id
        self.id = message_id

    async def edit(self, *, content: str, components=None) -> None:
        from spirit_voice import edit

        await edit(self.channel_id, self.id, content, components=components)


class _NoTyping:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _record_magic_trace(channel, text: str, message=None, tool: int | None = None) -> None:
    """The trace as it was posted, in the session file.

    ``message`` is the id of the card that carries the button. ``tool`` is
    that card's call in the turn already written above it.
    """
    try:
        from mage import get_pd
        from session_record import append_event

        append_event(
            get_pd(), channel.id, kind="trace", actor="spirit", text=text,
            message="" if message is None else str(message),
            tool=tool,
        )
    except Exception as exc:
        print(f"Magic trace record failed: {type(exc).__name__}: {exc}")


def _file_link(path: str) -> str | None:
    """A link when the house can open the file. A workshop path has none."""
    from artifact_viewer import is_artifact_readable
    from practice_io import artifact_read_url

    if not is_artifact_readable(path, mage_type="practitioner"):
        return None
    return artifact_read_url(path)


async def open_trace_calls(interaction) -> None:
    """The press. Only the person who pressed sees the calls."""
    from mage import get_pd, set_practice_context_for_channel
    from session_record import read_turns
    from trace_reveal import QUIET, calls_for_message, reveal_calls

    channel_id = getattr(interaction, "channel_id", None)
    if channel_id is None:
        channel = getattr(interaction, "channel", None)
        channel_id = getattr(channel, "id", None)
    try:
        set_practice_context_for_channel(channel_id)
    except Exception as exc:
        print(f"Trace calls context failed: {type(exc).__name__}: {exc}")
    posted = getattr(interaction, "message", None)
    try:
        events = read_turns(get_pd(), channel_id)
    except Exception as exc:
        print(f"Trace calls read failed: {type(exc).__name__}: {exc}")
        events = []
    tools = calls_for_message(events, getattr(posted, "id", None))
    text = (
        f"{QUIET}\n\nThis turn is not written down yet."
        if tools is None
        else reveal_calls(tools, link_for=_file_link)
    )
    from ui_kit import read_window

    await interaction.response.send_modal(read_window("What this turn opened", text))


_CALL_VALUE_CHARS = 80


def _call_value(value) -> str:
    """The argument, as a few words. A file body stays a count."""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, (list, dict)):
        text = json.dumps(value, ensure_ascii=False, default=str)
    else:
        text = "" if value is None else str(value)
    if "\n" in text:
        lines = [line for line in text.splitlines() if line.strip()]
        return f"{len(lines) or 1} lines"
    text = " ".join(text.split())
    if len(text) > _CALL_VALUE_CHARS:
        return f"{len(text)} characters"
    return text


def call_as_sent(name: str, args) -> str:
    """One quiet line: the tool, then each argument as its key and its value.

    The result is not on the line. A value that is a file stays a count,
    so the line never carries the body.
    """
    name = (name or "").strip() or "call"
    parts = [name]
    if isinstance(args, dict):
        for key, value in args.items():
            label = str(key).strip() or "arg"
            shown = _call_value(value)
            parts.append(f"{label} {shown}".rstrip() if shown else label)
    return "-# " + " · ".join(parts)


class _StepCard:
    """Show the turn working.

    Discord has no token stream. In a personal room, a craft room, and a magic
    room, each sentence is posted as the model wrote it, and each call is
    posted as the model made it. Those messages are created once. A shared
    room still uses one message and, when the reply lands, one line.

    The card is posted at the first significant operation — a link or
    attachment already read, or the first lookup the model makes — and
    otherwise only once the turn has run past ``PROGRESS_AFTER_SECONDS``; a
    quick reply with nothing to show posts nothing. Edits are spaced
    ``CARD_EDIT_INTERVAL_SECONDS`` apart so Discord is never asked to redraw
    faster than it will, and every ``CARD_TICK_SECONDS`` the elapsed time is
    refreshed so a long compose is visibly still alive.

    A Discord failure here never costs the turn. The provider's chain of
    thought is not posted and not stored.
    """

    def __init__(self, channel, steps: AttunementSteps, model: str, started: float,
                 *, full: bool = False, after: float | None = None, as_spirit: bool = False):
        self.channel = channel
        self.attunement = steps
        self.model = model
        self.started = started
        self.full = full
        self.as_spirit = as_spirit
        self.express = bool(full or as_spirit)
        self.after = PROGRESS_AFTER_SECONDS if after is None else after
        self.steps: list[Step] = attunement_step_list(steps)
        self.operations = bool(steps.links or steps.attachments or steps.dereferenced or steps.forwarded)
        self.posted = None
        self._pages: list = []
        self._page_text: list[str] = []
        self._record: list[dict] = []
        self._placed: list[dict] = []
        self._live = None
        self._live_text = ""
        self._tool_count = 0
        self._queue: asyncio.Queue = asyncio.Queue()
        self._actor = None
        self._lock = asyncio.Lock()
        self._timer = None
        self._tick = None
        self._pending_edit = None
        self._last_edit = 0.0
        self._closed = False

    def _elapsed(self) -> float:
        return time.monotonic() - self.started

    def _card(self, *, done: bool = False) -> str:
        return render_card(
            self.steps, self._elapsed(), self.model,
            done=done, voice="spirit" if self.as_spirit else "turtle",
        )

    def start(self) -> None:
        if self.express:
            self._ensure_actor()
            return
        if self.operations:
            self._timer = asyncio.ensure_future(self._post())
        elif self.after > 0:
            self._timer = asyncio.ensure_future(self._post_after(self.after))

    async def on_event(self, kind: str, payload: dict) -> None:
        if self._closed:
            return
        if self.express:
            if kind not in {"prose", "tool", "status"}:
                return
            self._ensure_actor()
            self._queue.put_nowait((kind, payload))
            return
        if kind == "prose":
            step = prose_step(str(payload.get("text") or ""))
            if step:
                self.steps.append(step)
        elif kind == "tool":
            remember_step(self.steps, describe_tool(
                str(payload.get("name") or ""), payload.get("args") or {}, str(payload.get("result") or "")
            ))
        else:
            return
        if self.posted is None:
            if self._timer is not None and not self._timer.done():
                self._timer.cancel()
            await self._post()
        else:
            self._request_edit()

    async def _post_after(self, delay: float) -> None:
        try:
            await asyncio.sleep(delay)
            await self._post()
        except asyncio.CancelledError:
            raise

    async def _send_page(self, text: str):
        if self.as_spirit:
            from spirit_voice import say

            mid = await say(self.channel.id, text)
            if mid:
                return _SpiritPosted(self.channel.id, mid)
        return await self.channel.send(text)

    async def _post(self) -> None:
        if self.posted is not None or self._closed:
            return
        try:
            text = self._card()
            self.posted = await self.channel.send(text)
            self._last_edit = time.monotonic()
            if CARD_TICK_SECONDS > 0:
                self._tick = asyncio.ensure_future(self._tick_loop())
        except Exception as exc:
            print(f"Step card post failed: {type(exc).__name__}: {exc}")

    def _request_edit(self) -> None:
        if self._pending_edit is not None and not self._pending_edit.done():
            return  # the pending edit renders whatever has accumulated by then
        wait = max(0.0, self._last_edit + CARD_EDIT_INTERVAL_SECONDS - time.monotonic())
        self._pending_edit = asyncio.ensure_future(self._edit_after(wait))

    async def _edit_after(self, wait: float) -> None:
        try:
            if wait:
                await asyncio.sleep(wait)
            if self._closed or self.posted is None:
                return
            await self.posted.edit(content=self._card())
            self._last_edit = time.monotonic()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"Step card edit failed: {type(exc).__name__}: {exc}")

    async def _tick_loop(self) -> None:
        try:
            while not self._closed:
                await asyncio.sleep(CARD_TICK_SECONDS)
                if not self._closed:
                    self._request_edit()
        except asyncio.CancelledError:
            raise

    def _ensure_actor(self) -> None:
        if self._actor is None or self._actor.done():
            self._actor = asyncio.ensure_future(self._actor_loop())

    def _status_line(self, payload: dict) -> str:
        written = str(payload.get("text") or "").strip()
        if written:
            return f"-# {written}"
        name = str(payload.get("name") or "").strip()
        if not name:
            return "-# writing"
        return f"-# {name}"

    async def _actor_loop(self) -> None:
        while True:
            item = await self._queue.get()
            try:
                if item is None:
                    return
                kind, payload = item
                await self._apply(kind, payload)
            except Exception as exc:
                print(f"Step card line failed: {type(exc).__name__}: {exc}")
            finally:
                self._queue.task_done()

    async def _place(self, text: str, item: dict | None) -> None:
        """A new message. Editing it would mark the model's own words as edited."""
        for index, chunk in enumerate(split_message(text)):
            posted = await self._send_page(chunk)
            if posted is None:
                return
            self._placed.append({"message": posted, "text": chunk, "item": item if index == 0 else None})

    async def _apply(self, kind: str, payload: dict) -> None:
        if kind == "status":
            await self._show_live(self._status_line(payload))
            return
        if kind == "prose":
            step = prose_step(str(payload.get("text") or ""))
            if not step:
                return
            item = {"kind": "prose", "text": step.text}
            self._record.append(item)
            await self._place(step.text, item)
            return
        if kind != "tool":
            return
        text = call_as_sent(str(payload.get("name") or ""), payload.get("args") or {})
        item = {
            "kind": "tool",
            "text": text,
            "name": str(payload.get("name") or ""),
            "index": self._tool_count,
        }
        self._tool_count += 1
        self._record.append(item)
        await self._place(text, item)

    async def _show_live(self, text: str) -> None:
        if not text.strip() or text == self._live_text:
            return
        if self._live is None:
            posted = await self._send_page(text)
            if posted is None:
                return
            self._live = posted
        else:
            await self._live.edit(content=text)
        self._live_text = text

    async def _clear_live(self) -> None:
        live = self._live
        self._live = None
        self._live_text = ""
        if live is None:
            return
        try:
            if isinstance(live, _SpiritPosted):
                from spirit_voice import remove

                await remove(live.channel_id, live.id)
            else:
                await live.delete()
        except Exception as exc:
            print(f"Step card clear failed: {type(exc).__name__}: {exc}")

    async def _drain(self) -> None:
        self._ensure_actor()
        await self._queue.join()
        self._queue.put_nowait(None)
        actor = self._actor
        self._actor = None
        if actor is not None:
            try:
                await actor
            except Exception as exc:
                print(f"Step card actor failed: {type(exc).__name__}: {exc}")

    async def flush(self) -> None:
        """The model is done. The sentences and calls are already posted.

        The live line was only a status. It is removed so the thread keeps
        the messages that were created, not a message that was rewritten.
        """
        await self._drain()
        await self._clear_live()

    async def dress(self) -> None:
        """The visual layer is not on these messages yet.

        The call is the message. A button edited onto it is what stamped
        every line as edited, and it paraphrased the call to do it.
        """
        return

    async def settle(self, tools_executed) -> None:
        self._closed = True
        for task in (self._timer, self._tick, self._pending_edit):
            if task is not None and not task.done():
                task.cancel()
        if self.express:
            try:
                await self.flush()
            except Exception as exc:
                print(f"Step card close failed: {type(exc).__name__}: {exc}")
            return
        if self.posted is None:
            return
        try:
            if self.full:
                content = self._card(done=True)
            else:
                content = render_trace(self.attunement, self._elapsed(), self.model, tool_names(tools_executed))
            await self.posted.edit(content=content)
        except Exception as exc:
            print(f"Step card close failed: {type(exc).__name__}: {exc}")


# How many model calls the local remembering loop may spend. Two: one to look,
# one to answer. `LOCAL_MEMORY_TOOLS=0` switches the loop off entirely.
LOCAL_MEMORY_TOOL_ROUNDS = int(os.environ.get("LOCAL_MEMORY_TOOL_ROUNDS", "2"))
LOCAL_TEAM_TOOL_ROUNDS = int(os.environ.get("LOCAL_TEAM_TOOL_ROUNDS", "3"))


def local_memory_tools(parent_channel_id) -> list[dict]:
    """The remembering pair for a local-model turn, or [] when it has nothing to read.

    Offered only when the room's memory has been built (``memory/topics.yaml``
    exists under the practice root). A room without one keeps the plain call —
    the tools would find nothing the packet did not already carry, and the
    loop costs a non-streaming round trip.
    """
    if os.environ.get("LOCAL_MEMORY_TOOLS", "1").strip() in {"0", "false", "no", "off"}:
        return []
    try:
        from memory_agent import memory_dir, TOPICS_YAML

        if not (memory_dir(get_pd()) / TOPICS_YAML).exists():
            return []
        return memory_tools_for_channel(parent_channel_id)
    except Exception as exc:
        print(f"Local memory tools unavailable: {type(exc).__name__}: {exc}")
        return []


def local_turn_tools(parent_channel_id) -> tuple[list[dict], int]:
    """Capability-scoped local tools; governed state works without an API model.

    Memory pair (when a memory is built) + team tools + the room's governed
    tools. The governed set is what a health room on the local model was
    missing until 2026-09-21: the catalog offered `recap_health_visit`, this
    function did not, and the rules text promised a write that could not land.
    """
    tools = list(local_memory_tools(parent_channel_id))
    governed = list(team_tools_for_channel(parent_channel_id))
    governed.extend(local_governed_tools_for_channel(parent_channel_id))
    names = {
        (item.get("function") or {}).get("name") or item.get("name")
        for item in tools
    }
    for item in governed:
        name = (item.get("function") or {}).get("name") or item.get("name")
        if name in names:
            continue
        names.add(name)
        tools.append(item)
    rounds = LOCAL_TEAM_TOOL_ROUNDS if governed else LOCAL_MEMORY_TOOL_ROUNDS
    return tools, rounds

# Last resort, and it should now be genuinely rare: the model is unreachable
# rather than merely slow. Turtle's own voice, no traceback — a practitioner
# in the middle of a hard conversation should never be handed an exception
# class as an answer. The message is theirs to retry, not an apology.
TURN_UNAVAILABLE_REPLY = (
    "*I'm here, but I couldn't get a thought together just now — "
    "something on my end, not you. Say it again when you're ready "
    "and I'll pick it up.*"
)


async def handle_dialogue(message, *, reply: bool = True):
    """Hold the turn where a restart can see it, then absorb the message."""
    channel = getattr(message, "channel", None)
    channel_id = int(getattr(channel, "id", 0) or 0)
    from dialogue_store import begin_turn, end_turn

    if channel_id:
        begin_turn(channel_id)
    try:
        await _handle_dialogue(message, reply=reply)
    finally:
        if channel_id:
            end_turn(channel_id)


async def _handle_dialogue(message, *, reply: bool = True):
    """Absorb a practitioner message and, unless coalesced, answer it.

    ``reply=False`` runs everything except the generation: the message still
    enters history, attachments and links are still fetched, the eddy still
    registers activity. Only the LLM turn is deferred to the newer message
    that is already waiting behind this one in ``dialogue_queue``.
    """
    try:
        from share_eddy import maybe_notify_sharer_on_first_peer_reply

        await maybe_notify_sharer_on_first_peer_reply(message)
    except Exception as exc:
        print(f"Share notify hook failed: {type(exc).__name__}: {exc}")

    visible_content, forwarded_context = visible_message_content(message)

    try:
        from share_eddy import maybe_skip_shared_eddy_dialogue

        skip = await maybe_skip_shared_eddy_dialogue(message, visible_content)
        if skip is not None:
            print(
                f"Shared eddy witness ({skip.reason}) "
                f"[{message.author.display_name}]: {visible_content[:80]}"
            )
            return
    except Exception as exc:
        print(f"Shared eddy gate failed: {type(exc).__name__}: {exc}")

    if isinstance(message.channel, discord.Thread):
        from thread_registry import is_eddy_locked

        if is_eddy_locked(
            message.channel.id,
            discord_locked=getattr(message.channel, "locked", False),
        ):
            print(
                f"Dialogue skipped — thread locked: "
                f"{message.channel.name} ({message.channel.id})"
            )
            return

    channel_id = message.channel.id
    parent_ch_id = resolve_dialogue_channel_id(message)
    from mage import (
        address_for_mage_key,
        channel_has_capability,
        get_actor_key,
        get_channel_primitive,
    )
    from team_lanes import bind_current_eddy, gate_lane_turn

    bind_current_eddy(
        channel_id if isinstance(message.channel, discord.Thread) else None
    )
    if isinstance(message.channel, discord.Thread):
        lane_gate = gate_lane_turn(
            channel_id,
            actor=get_actor_key(),
            primitive=get_channel_primitive(parent_ch_id),
        )
        if not lane_gate.allowed:
            owner = address_for_mage_key(lane_gate.owner) if lane_gate.owner else "another member"
            await message.reply(
                f"This is {owner}'s lane. You may read it, but continue from "
                "your own eddy so both paths can advance independently.",
                mention_author=False,
            )
            print(
                f"Team lane turn refused [{channel_id}]: {lane_gate.reason}"
            )
            return

    intake_context = ""
    if channel_has_capability(parent_ch_id, "source_intake") and message.attachments:
        intake_results, intake_context = await intake_primitive_attachments(
            message,
            parent_ch_id,
            practice_dir=get_pd(),
            actor=get_actor_key() or "unknown",
        )
        raw_attachments = list(message.attachments)
        attachments = []
        attachment_names = [result.filename for result in intake_results]
        attachment_source = "primitive source store"
        states = ", ".join(
            f"{result.filename}: {result.status}" for result in intake_results
        )
        attachment_note = f" [record intake: {states}]"
    else:
        attachments, attachment_names, attachment_note, raw_attachments, attachment_source = (
            await gather_dialogue_attachments(message)
        )
    # Discord converts pastes over the character limit into message.txt (often
    # with an empty body). Fold text attachments into the practitioner content
    # so triage/history see the article, not "(attachment: message.txt)".
    text_atts, vision_atts = split_text_and_vision_attachments(attachments)
    if channel_has_capability(parent_ch_id, "source_intake") and vision_atts:
        # A reply-parent attachment was readable for this turn but was not the
        # direct upload persisted above. Never send sensitive bytes to Gemini.
        skipped = ", ".join(filename for _, _, filename in vision_atts)
        attachment_note += (
            f" [record attachment not imported from reply ({skipped}); "
            "upload it directly in this eddy]"
        )
        vision_atts = []
    if text_atts:
        primary, extras = format_text_attachments_for_dialogue(text_atts)
        if primary:
            if visible_content.strip():
                visible_content = f"{visible_content.rstrip()}\n\n{primary}"
            else:
                visible_content = primary
            attachment_note += " [inlined text attachment]"
        if extras:
            visible_content = (
                f"{visible_content.rstrip()}\n\n{extras}" if visible_content.strip()
                else extras
            )
            if not primary:
                attachment_note += " [inlined text attachment]"
        attachments = vision_atts
        attachment_names = [fn for _, _, fn in vision_atts]
    if not visible_content.strip() and raw_attachments:
        visible_content = f"(attachment: {attachment_display_names(raw_attachments)})"
    native_eddy = isinstance(message.channel, discord.Thread) and uses_native_turtle_prompt(parent_ch_id)

    if native_eddy:
        triage = {"category": "practice", "needs_state": False}
        triage_cat = "practice"
    else:
        triage = await triage_message(visible_content)
        triage_cat = triage.get("category", "practice")
        print(f"Triage [{message.author.display_name}]: {triage_cat} (state={triage.get('needs_state', True)}) — {visible_content[:80]}")

    history = get_history(channel_id)

    if not history and isinstance(message.channel, discord.Thread):
        loaded = await load_thread_history(
            message.channel, exclude_message_id=message.id
        )
        if loaded:
            dialogue_histories[channel_id] = loaded
            history = dialogue_histories[channel_id]
            sync_history(channel_id)
            print(f"Thread memory restored: {message.channel.name} ({len(loaded)} messages)")
            summary = summarize_thread_context(loaded, message.channel.name)
            # Internal log only — operational noise, not surfaced to channel (016 principle)
            print(f"Thread memory context: {message.channel.name} ({len(loaded)} msgs) — {summary[:100]}")

    attachment_extracted = False
    urls = []
    url_content = ""
    url_source_count = 0
    pending_incidental_urls: list[str] = []
    urls = await _extract_urls(visible_content)
    external = external_urls(urls)
    from link_read import plan_dialogue_urls

    auto_fetch, urls, pending_incidental_urls = plan_dialogue_urls(
        visible_content, external, native_eddy=native_eddy
    )
    if auto_fetch:
        fetch_results, url_content = await fetch_urls_with_status(message.channel, urls)
        if url_content:
            url_source_count = len(urls)
            attachment_note += f" [fetched {url_source_count} URL(s)]"
            if isinstance(message.channel, discord.Thread):
                await maybe_refine_thread_name_from_fetch(message.channel, fetch_results)

    dereferenced_context = ""
    ref_inject_max = 6000
    dereferenced_count = 0
    ref_text = message.content or ""
    if forwarded_snapshot_is_partial(message):
        source_ref = forward_source_ref(message)
        if source_ref:
            g, c, m = source_ref
            from discord_ref_read import permalink_for

            ref_text = f"{permalink_for(g or 0, c, m)}\n{ref_text}"
    if ref_text.strip():
        from discord_ref_read import (
            FRONTIER_BUDGET, LOCAL_BUDGET, extract_all_discord_refs,
            fetch_all_discord_refs_with_status,
        )
        from room_models import room_reads_on_cloud

        if extract_all_discord_refs(ref_text):
            from mage import get_registry as _registry
            from room_models import default_for_room

            room_default = default_for_room(parent_ch_id, _registry(), TURTLE_MODEL)
            ref_budget = (
                FRONTIER_BUDGET
                if room_reads_on_cloud(parent_ch_id, thread_configs.get(channel_id), room_default)
                else LOCAL_BUDGET
            )
            _ref_results, dereferenced_context = await fetch_all_discord_refs_with_status(
                message.channel, state.client, ref_text,
                user_id=getattr(message.author, "id", None), budget=ref_budget,
            )
            ref_inject_max = ref_budget.inject_max
            dereferenced_count = sum(1 for r in _ref_results if r.ok)
            if dereferenced_context:
                thread_reads = sum(1 for r in _ref_results if r.ok and r.scope == "thread")
                if thread_reads:
                    attachment_note += f" [read {thread_reads} Discord thread(s)]"
                else:
                    attachment_note += f" [read {dereferenced_count} Discord message(s)]"

    if not attachments and forwarded_snapshot_is_partial(message):
        source_ref = forward_source_ref(message)
        if source_ref:
            chain_attachments, chain_names, chain_note = await attachments_from_forward_chain(
                source_ref
            )
            if chain_attachments:
                attachments = chain_attachments
                attachment_names = chain_names
                attachment_note += chain_note

    # Include fetched content in history so it persists across turns
    user_entry = f"[{message.author.display_name}]: {visible_content}{attachment_note}"
    if intake_context:
        user_entry += f"\n\n[Locally extracted record evidence]:\n{intake_context}"
    if url_content:
        user_entry += f"\n\n[Fetched content]:\n{url_content[:inject_limit(url_content)]}"
    if dereferenced_context:
        user_entry += f"\n\n{dereferenced_context[:ref_inject_max + 2000]}"
    history.append({"role": "user", "content": user_entry})
    if len(history) > MAX_DIALOGUE_HISTORY:
        history.pop(0)

    # Coalescing: when more of the practitioner's messages are already queued
    # for this channel, absorb this one into history and let the last arrival
    # answer them together. Nothing is lost — everything above has run — and
    # the room gets one current answer instead of three to a conversation that
    # has moved on. `dialogue_queue` decides; this only honours the decision.
    if not reply:
        print(
            f"Message absorbed, reply deferred to the newer one "
            f"[{getattr(message.channel, 'name', channel_id)}]"
        )
        return

    await continue_dialogue_turn(
        message,
        history,
        triage_cat=triage_cat,
        native_eddy=native_eddy,
        attachments=attachments,
        attachment_names=attachment_names,
        attachment_note=attachment_note,
        attachment_extracted=attachment_extracted,
        raw_attachments=raw_attachments,
        url_content=url_content,
        url_source_count=url_source_count,
        urls=urls,
        forwarded_context=forwarded_context,
        dereferenced_context=dereferenced_context,
        dereferenced_count=dereferenced_count,
        pending_incidental_urls=pending_incidental_urls,
    )


async def run_link_read_followup(
    interaction: discord.Interaction,
    source_message_id: int,
    urls: list[str],
) -> None:
    """Second turn after Read article on an incidental link."""
    channel = interaction.channel
    if not isinstance(channel, discord.Thread):
        return
    source = await channel.fetch_message(source_message_id)
    fetch_results, url_content = await fetch_urls_with_status(channel, urls)
    await maybe_refine_thread_name_from_fetch(channel, fetch_results)
    history = get_history(channel.id)
    history.append(
        {
            "role": "user",
            "content": (
                f"[Link read requested: {urls[0]}]\n\n"
                f"[Fetched content]:\n{url_content[:inject_limit(url_content)]}"
            ),
        }
    )
    if len(history) > MAX_DIALOGUE_HISTORY:
        history.pop(0)
    sync_history(channel.id)
    native_eddy = uses_native_turtle_prompt(resolve_dialogue_channel_id(source))
    # Never coalesced: this turn is owed to a button the practitioner pressed.
    await continue_dialogue_turn(
        source,
        history,
        triage_cat="link",
        native_eddy=native_eddy,
        attachments=[],
        attachment_names=[],
        attachment_note=" [link read followup]",
        attachment_extracted=False,
        raw_attachments=[],
        url_content=url_content,
        url_source_count=len(urls),
        urls=urls,
        forwarded_context="",
        dereferenced_context="",
        dereferenced_count=0,
        pending_incidental_urls=[],
    )


_resuming: set[int] = set()


class _ResumeMessage:
    """A turn the button started. The reply quotes the notice; they typed nothing."""

    def __init__(self, channel, content: str, author_name: str, anchor_id: int):
        self.channel = channel
        self.content = content
        self.id = anchor_id
        self.author = type("Author", (), {"display_name": author_name, "id": 0, "bot": False})()
        self.attachments = []
        self.reference = None

    async def reply(self, text, *, mention_author=False, view=None):
        if view is None:
            await self.channel.send(text)
        else:
            await self.channel.send(text, view=view)


async def _resume_room(interaction):
    """The turtle client's channel. Spirit's gateway does not keep the thread."""
    cid = int(getattr(interaction, "channel_id", 0) or 0)
    try:
        found = state.client.get_channel(cid) if cid else None
        if found is None and cid:
            found = await state.client.fetch_channel(cid)
        if found is not None:
            return found
    except Exception as exc:
        print(f"Stocked room lookup failed: {type(exc).__name__}: {exc}")
    return getattr(interaction, "channel", None)


async def resume_stocked(interaction) -> None:
    """The press says the credit is back. Try now, and continue what was parked."""
    channel_id = int(getattr(interaction, "channel_id", 0) or 0)
    if channel_id in _resuming:
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "Already trying the cloud.", ephemeral=True
            )
        return
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)
    _resuming.add(channel_id)
    try:
        await _resume_stocked(interaction, channel_id)
    finally:
        _resuming.discard(channel_id)


async def _resume_stocked(interaction, channel_id: int) -> None:
    from mage import set_practice_context_for_channel

    try:
        set_practice_context_for_channel(channel_id)
    except Exception as exc:
        print(f"Stocked context failed: {type(exc).__name__}: {exc}")

    async def ask(model: str) -> None:
        await chat_anthropic_with_model(
            "Reply with ok.",
            [{"role": "user", "content": "ok"}],
            model,
            use_tools=False,
        )

    try:
        back = await cloud_fallback.try_now(ask)
    except Exception as exc:
        print(f"Stocked probe failed: {type(exc).__name__}: {exc}")
        back = False
    if not back:
        await interaction.followup.send("The credit is still out.", ephemeral=True)
        return

    try:
        await interaction.message.edit(view=None)
    except Exception as exc:
        print(f"Stocked button stayed: {type(exc).__name__}: {exc}")

    channel = await _resume_room(interaction)
    if channel is None:
        await interaction.followup.send("This room is not open from here.", ephemeral=True)
        return

    text = ""
    try:
        waiting = cloud_fallback.parked_for(get_pd(), int(getattr(channel, "id", channel_id) or channel_id))
        text = cloud_fallback.asked(waiting[-1]) if waiting else ""
    except Exception as exc:
        print(f"Stocked park read failed: {type(exc).__name__}: {exc}")
    if not text:
        await interaction.followup.send("Back on the cloud.", ephemeral=True)
        return

    who = getattr(getattr(interaction, "user", None), "display_name", None) or "practitioner"
    room_id = int(getattr(channel, "id", channel_id) or channel_id)
    history = get_history(room_id)
    history.append({"role": "user", "content": f"[{who}]: {text}"})
    if len(history) > MAX_DIALOGUE_HISTORY:
        history.pop(0)
    sync_history(room_id)

    anchor = int(getattr(getattr(interaction, "message", None), "id", 0) or 0)
    stand = _ResumeMessage(channel, text, who, anchor)
    native_eddy = False
    try:
        native_eddy = uses_native_turtle_prompt(resolve_dialogue_channel_id(stand))
    except Exception as exc:
        print(f"Stocked attunement failed: {type(exc).__name__}: {exc}")

    from dialogue_store import begin_turn, end_turn

    if room_id:
        begin_turn(room_id)
    try:
        await continue_dialogue_turn(
            stand,
            history,
            triage_cat="practice",
            native_eddy=native_eddy,
            attachments=[],
            attachment_names=[],
            attachment_note="",
            attachment_extracted=False,
            raw_attachments=[],
            url_content="",
            url_source_count=0,
            urls=[],
            forwarded_context="",
            dereferenced_context="",
            dereferenced_count=0,
            pending_incidental_urls=[],
        )
    finally:
        if room_id:
            end_turn(room_id)


async def continue_dialogue_turn(
    message,
    history,
    *,
    triage_cat: str,
    native_eddy: bool,
    attachments,
    attachment_names,
    attachment_note: str,
    attachment_extracted: bool,
    raw_attachments=None,
    url_content: str,
    url_source_count: int,
    urls: list,
    forwarded_context: str,
    dereferenced_context: str,
    dereferenced_count: int,
    pending_incidental_urls: list[str] | None = None,
):
    channel_id = message.channel.id
    _forge_token = None
    _platform_token = None
    turn_started = time.monotonic()
    now = datetime.now(timezone.utc)
    is_new_session = channel_id not in active_sessions or active_sessions[channel_id]["closed"]
    if channel_id not in active_sessions:
        active_sessions[channel_id] = {"started": now, "last_message": now, "closed": False}
    active_sessions[channel_id]["last_message"] = now
    active_sessions[channel_id]["closed"] = False

    if is_new_session and not isinstance(message.channel, discord.Thread):
        pd = get_pd()
        sdir = os.path.join(pd, "sessions")
        session_files = [f for f in os.listdir(sdir) if f.endswith(".md")] if os.path.isdir(sdir) else []
        flows_dir = os.path.join(pd, "flows")
        flow_files = (
            [f for f in os.listdir(flows_dir) if f.endswith(".md") or f.endswith(".flow.md")]
            if os.path.isdir(flows_dir)
            else []
        )
        ctx_parts = [f"{len(session_files)} sessions", f"{len(flow_files)} flows"]
        if session_files:
            last_session = max(session_files, key=lambda f: os.path.getmtime(os.path.join(sdir, f))).replace(".md", "")
            ctx_parts.append(f"last session: {last_session}")

        # INT-023: Context loads silently. Healthy state needs no announcement.

    parent_ch_id = resolve_dialogue_channel_id(message)
    from mage import (
        get_actor_key,
        get_channel_default_context,
        get_channel_primitive,
        get_registry,
    )
    from health_room import vet_health_reply
    from primitive_runtime import runtime_for

    primitive = get_channel_primitive(parent_ch_id)
    primitive_runtime = runtime_for(primitive)
    prompt_profile = (
        primitive_runtime.prompt_profile if primitive_runtime else "native"
    )
    try:
        from boom_takeup import begin_platform_turn
        from mage import get_runtime_dir

        token = begin_platform_turn(
            isinstance(message.channel, discord.Thread),
            get_runtime_dir(),
            channel_id,
        )
        if token is not None:
            prompt_profile = "magic"
            _platform_token = token
    except Exception as exc:
        print(f"Platform session check failed: {type(exc).__name__}: {exc}")
    craft_surface = bool(
        primitive_runtime and primitive_runtime.parent_handler == "craft_intake"
    )
    health_surface = bool(
        primitive and primitive.data_policy == "sensitive_local"
    )
    exclude_shared_memory = bool(
        primitive and primitive.memory_boundary == "personal_without_shared"
    )
    cfg = thread_configs.get(channel_id)
    if prompt_profile in ("native", "magic") and native_eddy:
        from eddy_spawn import hydrate_native_eddy_context

        parent_for_hydrate = (
            message.channel.parent_id
            if hasattr(message.channel, "parent_id")
            else None
        )
        hydrate_native_eddy_context(channel_id, parent_for_hydrate)
        cfg = thread_configs.get(channel_id)
        ctx = (cfg or {}).get("context_type")
        if not ctx and hasattr(message.channel, "parent_id") and message.channel.parent_id:
            ctx = get_channel_default_context(message.channel.parent_id)
        if prompt_profile == "magic":
            from magic_prompt import turn_prompt_and_model

            system_prompt, thread_model, thread_use_api = turn_prompt_and_model(parent_ch_id, cfg)
        else:
            system_prompt = get_native_eddy_prompt(ctx)
            thread_model, thread_use_api, _ = resolve_room_model(parent_ch_id, cfg, TURTLE_MODEL)
    elif prompt_profile == "craft":
        ctx = (cfg or {}).get("context_type") if cfg else None
        if not ctx:
            ctx = get_channel_default_context(parent_ch_id) or "craft"
        system_prompt = get_craft_channel_prompt(ctx)
        thread_model, thread_use_api, _ = resolve_room_model(parent_ch_id, cfg, TURTLE_MODEL)
    elif prompt_profile == "health":
        ctx = (cfg or {}).get("context_type") if cfg else None
        if not ctx:
            ctx = get_channel_default_context(parent_ch_id) or "health"
        system_prompt = get_health_channel_prompt(ctx)
        thread_model, thread_use_api, source = resolve_room_model(parent_ch_id, cfg, DIALOGUE_MODEL)
        if source == "default":
            thread_model, thread_use_api = DIALOGUE_MODEL, USE_API
    elif cfg:
        ctx = cfg.get("context_type")
        if not ctx and hasattr(message.channel, "parent_id") and message.channel.parent_id:
            ctx = get_channel_default_context(message.channel.parent_id)
        system_prompt = get_thread_prompt(
            cfg["attunement"], cfg["use_api"], context_type=ctx, channel_id=parent_ch_id
        )
        thread_use_api = cfg["use_api"]
        thread_model = cfg["model"]
    else:
        system_prompt = get_system_prompt()
        thread_use_api = USE_API
        thread_model = DIALOGUE_MODEL

    # Thread cards are magic-era persistence — native eddies use visible history only.
    if (
        isinstance(message.channel, discord.Thread)
        and not native_eddy
        and not read_thread_state(message.channel.name)
    ):
        await update_thread_state(message.channel, cfg, history)

    if prompt_profile == "magic":
        from magic_prompt import magic_runtime_env
        from spirit_voice import is_forge_turn
        from workshop_tools import set_forge_turn

        _forge_token = set_forge_turn(is_forge_turn(message))
        runtime_env = magic_runtime_env(
            getattr(getattr(message.channel, "parent", None), "name", None),
            getattr(message.channel, "name", ""),
        )
        system_prompt = runtime_env + system_prompt
    elif native_eddy:
        runtime_env = build_native_runtime_env(message, cfg, history)
        system_prompt = runtime_env + system_prompt
    else:
        runtime_env = build_runtime_env(message, cfg)
        triage_hint = f"- **Message triage:** {triage_cat}"
        if triage_cat == "deep":
            triage_hint += " (take your time, go deep)"
        elif triage_cat in ("greeting", "casual"):
            triage_hint += " (keep it light and brief)"
        runtime_env = runtime_env.rstrip() + "\n" + triage_hint + "\n\n"
        system_prompt = runtime_env + system_prompt
    system_prompt = awareness_block(thread_model) + owner_line(parent_ch_id, get_registry()) + system_prompt

    # Named inject slots for the turn packet (TURTLE_SPEC §3.2). Empty until
    # each block is composed; persist after the model call so tools are known.
    current_block = ""
    home_block = ""
    absorbed_block = ""
    tools_executed: list = []

    # Continuity Engine — current layer + alive headers + the room's recent
    # memory, read from its own eddy notes on every turn. Prepend the substrate
    # packet so Turtle is oriented in the present and remembers what this space
    # has been about, without being told and without being asked. Scope (from
    # scopes.yaml, written by !focus in the River bot) narrows what is already
    # there. dialogue_model is resolved for THIS turn (hw honesty).
    # Declared outside the try so a CE failure leaves an empty candidate list
    # rather than an undefined name at persist time.
    room_memory_considered: list[dict] = []
    topics_considered: list[dict] = []
    # A magic room's Spirit stands on the workshop. Turtle's memory of the room (topics,
    # checkpoint, other rooms' notes) is not handed to it: it misattributed Spirit's own
    # session to Turtle, and the practice already holds what Spirit needs.
    if prompt_profile != "magic":
        try:
            from continuity_engine import get_scope, render_substrate_packet

            pd = get_pd()
            scope = get_scope(pd, channel_id)
            message_text = str(getattr(message, "content", "") or "")
            current_block = render_substrate_packet(
                pd,
                dialogue_model=thread_model,
                use_api=thread_use_api,
                scope=scope,
                current_thread=str(channel_id),
                considered=room_memory_considered,
                message_text=message_text,
                topics_considered=topics_considered,
                compact_topics=bool(url_content) or bool(attachments)
                or len(message_text) > COMPACT_TOPICS_MESSAGE_CHARS,
                exclude_shared_rooms=exclude_shared_memory,
            )
            if current_block:
                system_prompt = current_block + system_prompt
        except Exception as exc:
            print(f"CE substrate packet failed: {type(exc).__name__}: {exc}")

        # Pinned home eddy — inject working-plan attunement (river pin + file, not sidebar).
        try:
            from home_plans import render_home_attunement_packet

            home_block = render_home_attunement_packet(get_pd(), channel_id)
            if home_block:
                system_prompt = home_block + system_prompt
        except Exception as exc:
            print(f"Home-plan attunement failed: {type(exc).__name__}: {exc}")

    source_flags = []
    if url_content:
        source_flags.append(f"bot-fetched URL content ({url_source_count or len(urls)} URL(s))")
    if "[inlined text attachment]" in attachment_note:
        source_flags.append("inlined text attachment")
    if attachments:
        source_flags.append(f"attachment metadata ({', '.join(attachment_names)})")
    elif raw_attachments and "[inlined text attachment]" not in attachment_note:
        source_flags.append(
            f"attachment present but not extracted ({attachment_display_names(raw_attachments)})"
        )
    if forwarded_context:
        source_flags.append("forwarded message snapshot")
    if dereferenced_context:
        source_flags.append(f"read Discord context ({dereferenced_count})")

    messages_for_llm = list(history)
    contexts = absorbed_contexts.get(channel_id, [])
    if contexts and not cfg:
        source_flags.append(f"absorbed thread context ({len(contexts)} thread(s))")
        digest_parts = []
        for ctx in contexts:
            model_info = ctx.get("model_info", "")
            config_tag = f" `{model_info.strip()}`" if model_info.strip() else ""
            state_file = read_thread_state(ctx["name"])
            state_note = f"\n*Thread state:* {state_file}" if state_file else ""
            digest_parts.append(
                f"**Thread \"{ctx['name']}\"**{config_tag}:\n{ctx['digest']}{state_note}"
            )
        absorbed_block = (
            "## Absorbed Thread Context\n\n"
            "The Mage has absorbed the following thread resonances into this conversation. "
            "Draw on these naturally when relevant — they are part of your working context.\n\n"
            + "\n\n---\n\n".join(digest_parts)
        )
        messages_for_llm = [{"role": "user", "content": absorbed_block},
                            {"role": "assistant", "content": "I have this thread context. Let's continue."}] + messages_for_llm

    from act_offer_signal import act_offer_turn_context, extract_and_propose_from_reply

    x_images: list[dict] = []
    if url_content:
        try:
            from core.offload import run_blocking
            from outgoing_x import fetch_views, views_in_text

            looked = views_in_text(url_content)
            if looked:
                x_images = await run_blocking(fetch_views, looked, name="x_images") or []
        except Exception as exc:
            print(f"X picture fetch failed: {type(exc).__name__}")

    steps = AttunementSteps(
        links=(url_source_count or len(urls)) if url_content else 0,
        link_chars=len(url_content or ""),
        pictures=sum(1 for item in x_images if item.get("kind") != "video"),
        videos=sum(1 for item in x_images if item.get("kind") == "video"),
        attachments=list(attachment_names or []),
        forwarded=bool(forwarded_context),
        dereferenced=dereferenced_count or 0,
        topics=[str(t.get("label")) for t in topics_considered if t.get("selected")],
        room_notes=sum(1 for n in room_memory_considered if n.get("selected")),
        home_plan=bool(home_block),
        absorbed_threads=len(contexts) if contexts and not cfg else 0,
        prompt_chars=len(system_prompt),
    )
    try:
        from mage import space_members_for_practice_dir

        card_full = bool(craft_surface) or not space_members_for_practice_dir(get_pd())
    except Exception:
        card_full = False  # unknown room → the shared-room shape
    progress = _StepCard(
        message.channel, steps, thread_model, turn_started,
        full=card_full, as_spirit=prompt_profile == "magic",
    )

    turn_usage: dict = {}
    cloud_prose: list[str] = []
    cloud_tools: list[str] = []
    cloud_answered = False
    fallback_notice_line = ""
    stocked = False
    hold = cloud_fallback.read_hold() if thread_use_api else None
    cloud_held = bool(hold) and not cloud_fallback.should_try_cloud(hold)
    if hold and not cloud_held:
        cloud_fallback.mark_tried(hold)
    practitioner_text = str(getattr(message, "content", "") or "")
    parent_channel = getattr(message.channel, "parent", None)
    room_label = (
        getattr(parent_channel, "name", None)
        or getattr(message.channel, "name", None)
        or str(channel_id)
    )
    eddy_label = getattr(message.channel, "name", None) if parent_channel is not None else None

    async def _capture(kind, payload):
        if kind == "prose":
            cloud_prose.append(str(payload.get("text", "")))
        elif kind == "tool":
            cloud_tools.append(str(payload.get("name", "tool")))
        await progress.on_event(kind, payload)

    async def _cloud_turn():
        nonlocal cloud_answered
        if cloud_held:
            raise cloud_fallback.CloudHeld(hold)
        result = await chat_anthropic_with_model(
            system_prompt, messages_for_llm, thread_model, use_tools=True,
            tos_tools=tools_for_channel(parent_ch_id), execute_tool=execute_tos_tool,
            on_event=_capture, usage=turn_usage, images=x_images,
            **_magic_loop_limits(prompt_profile))
        cloud_answered = True
        return result

    async def _cloud_fallback_reply(exc: BaseException) -> tuple[str, str]:
        nonlocal stocked
        held = isinstance(exc, cloud_fallback.CloudHeld)
        kind = cloud_fallback.classify(exc)
        current = hold if held else cloud_fallback.note_failure(kind, thread_model, exc)
        parked = False
        try:
            path = cloud_fallback.park(
                get_pd(), channel_id=channel_id, room=room_label,
                author=getattr(message.author, "display_name", "") or "",
                message_text=practitioner_text, cloud_model=thread_model, kind=kind,
                partial_prose=cloud_prose, tools_run=cloud_tools, held_turn=held)
            parked = True
            print(f"Cloud fallback ({kind}) parked [{channel_id}]: {path}")
        except Exception as park_exc:
            print(f"Cloud fallback park failed: {type(park_exc).__name__}: {park_exc}")
        local_model = TURTLE_MODEL
        if held:
            local_system = awareness_block(local_model, fallback_from=thread_model) + system_prompt
            local_messages = messages_for_llm
        else:
            local_system = cloud_fallback.parking_prompt(
                local_model, thread_model, kind, practitioner_text, cloud_prose, cloud_tools)
            local_messages = list(messages_for_llm)[-6:]
        try:
            text = await chat_ollama(local_system, local_messages, model=local_model,
                                     num_ctx=32768, think=False)
        except Exception as local_exc:
            print(f"Cloud fallback local call failed: {type(local_exc).__name__}: {local_exc}")
            text = ""
        notice = cloud_fallback.fallback_notice(
            thread_model, local_model, kind, parked=parked,
            since=(current or {}).get("since"))
        stocked = bool(parked) and cloud_fallback.offers_stocked(kind)
        return text, notice

    async with (_NoTyping() if prompt_profile == "magic" else message.channel.typing()):
        with act_offer_turn_context(channel_id, message.id):
            progress.start()
            if native_eddy:
                try:
                    await ensure_native_presence(message.channel)
                except Exception as exc:
                    print(f"Native presence failed: {exc}")
                cfg = thread_configs.get(channel_id) or cfg
                try:
                    await post_flow_presence_if_needed(message.channel, cfg)
                except Exception as exc:
                    print(f"Flow presence failed: {exc}")
            tool_report = ""
            tools_executed = []
            if craft_surface:
                try:
                    from core.offload import run_blocking
                    from outgoing_connections import refresh_catalog_if_due

                    await run_blocking(refresh_catalog_if_due, name="x_catalog")
                except Exception as exc:
                    print(f"X catalog refresh failed: {type(exc).__name__}")
            is_gemini = thread_model.startswith("gemini-")
            if native_eddy:
                thread_label = message.channel.name if isinstance(message.channel, discord.Thread) else "eddy"
                print(f"Native Turtle [{thread_label}]: {thread_model} prompt={len(system_prompt)} chars")
            try:
                if is_gemini and HAS_GEMINI and GOOGLE_API_KEY:
                    reply, tools_executed = await chat_gemini(system_prompt, messages_for_llm, model=thread_model, attachments=attachments)
                    tool_report = build_tool_report(tools_executed)
                elif attachments and not is_gemini:
                    extraction = await preprocess_attachments(attachments) if attachments else ""
                    if extraction:
                        messages_for_llm[-1] = dict(messages_for_llm[-1])
                        block = extraction
                        if extraction.startswith("[Attachment processing failed") and raw_attachments:
                            url_lines = []
                            for att in raw_attachments[:3]:
                                url = getattr(att, "url", None)
                                if url:
                                    url_lines.append(f"- {att.filename}: {url}")
                            if url_lines:
                                block += "\n[Attachment URLs for practitioner]:\n" + "\n".join(url_lines)
                        messages_for_llm[-1]["content"] += "\n\n[Attachment content]:\n" + block
                        if not extraction.startswith("[Attachment processing failed"):
                            attachment_extracted = True
                    if thread_use_api:
                        reply, tools_executed = await _cloud_turn()
                        tool_report = build_tool_report(tools_executed)
                    else:
                        reply, tools_executed = await chat_ollama_with_tools(
                            system_prompt, messages_for_llm, model_override=thread_model,
                            tos_tools=tools_for_channel(parent_ch_id), execute_tool=execute_tos_tool,
                            on_event=progress.on_event)
                        tool_report = build_tool_report(tools_executed)
                elif thread_use_api:
                    reply, tools_executed = await _cloud_turn()
                    tool_report = build_tool_report(tools_executed)
                else:
                    # Direct commands are handled before dialogue. The full
                    # tool loop stays off here so a local model does not spend
                    # turns routing while Discord waits — but a room whose
                    # memory has been built gets the read-only remembering pair
                    # (memory_tools_for_channel) with a two-round cap, so "what
                    # do you remember about…" can be answered by looking rather
                    # than by narrating a look (2026-09-01). Rooms without a
                    # built memory keep the plain call.
                    # Act offers: use [[act-offer:…]] trailer (stripped before send).
                    local_tools, local_rounds = local_turn_tools(parent_ch_id)
                    if local_tools:
                        reply, tools_executed = await chat_ollama_with_tools(
                            system_prompt, messages_for_llm, model_override=thread_model,
                            tos_tools=local_tools, execute_tool=execute_tos_tool,
                            max_rounds=local_rounds, on_event=progress.on_event)
                        tool_report = build_tool_report(tools_executed)
                    else:
                        reply = await chat_ollama(
                            system_prompt, messages_for_llm, model=thread_model,
                            num_ctx=32768, think=False)
                        tools_executed = []

                if not reply:
                    reply = "(no response generated)"
            except Exception as e:
                # The old fallback here retried with REFLECTION_MODEL — a
                # *different* 17GB model, so a timeout caused by congestion
                # bought an eviction and a reload queued behind the same
                # congested slot, and the second failure's exception string
                # was posted into the conversation. Retry the model that is
                # already resident instead, once, and never put a traceback
                # in front of a practitioner.
                if not isinstance(e, cloud_fallback.CloudHeld):
                    print(f"Dialogue error ({thread_model}): {type(e).__name__}: {e}")
                reply = ""
                if thread_use_api and not is_gemini:
                    reply, fallback_notice_line = await _cloud_fallback_reply(e)
                elif not is_gemini:
                    try:
                        reply = await chat_ollama(
                            system_prompt, list(history), model=thread_model,
                            num_ctx=32768, think=False)
                        print(f"Dialogue recovered on retry ({thread_model})")
                    except Exception as e2:
                        print(
                            f"Dialogue retry failed ({thread_model}): "
                            f"{type(e2).__name__}: {e2}"
                        )
                if not reply:
                    reply = TURN_UNAVAILABLE_REPLY
                    print(f"Dialogue gave up [{channel_id}] — held reply posted")
            finally:
                await progress.settle(tools_executed)

    if cloud_answered:
        if hold:
            cloud_fallback.clear_hold()
            print(f"Cloud hold cleared ({thread_model} answered)")
        try:
            waiting = cloud_fallback.parked_for(get_pd(), channel_id)
            if waiting:
                fallback_notice_line = cloud_fallback.return_notice(thread_model, waiting)
                cloud_fallback.mark_surfaced(waiting)
        except Exception as exc:
            print(f"Parked-item check failed: {type(exc).__name__}: {exc}")
    turn_cost = None
    if turn_usage.get("calls"):
        try:
            turn_cost = cloud_fallback.record_usage(
                channel_id=channel_id, room=room_label, eddy=eddy_label,
                model=thread_model, usage=turn_usage)
        except Exception as exc:
            print(f"Usage record failed: {type(exc).__name__}: {exc}")

    # Persist the inject this turn used. Not current.yaml — that file already
    # exists from CE's debounce write. The packet is the named blocks that
    # actually went into the prompt, plus tools and files from this call.
    try:
        from link_read import stored_fetch
        from turn_packet import persist_turn_packet

        persist_turn_packet(
            get_pd(),
            channel_id,
            injected={
                "practice_substrate": current_block,
                "runtime_environment": runtime_env,
                "home_working_plan": home_block,
                "absorbed_threads": absorbed_block,
                "url_content": stored_fetch(url_content),
                "attachments": attachment_note,
                "forwarded_messages": forwarded_context,
                "discord_context": dereferenced_context,
            },
            considered=room_memory_considered + [
                {"topic": t.get("topic"), "title": f"topic: {t.get('label')}",
                 "when": t.get("last_seen"), "heat": t.get("heat"),
                 "selected": t.get("selected")}
                for t in topics_considered
            ],
            tools_executed=tools_executed,
        )
    except Exception as exc:
        print(f"Turn packet persist failed: {type(exc).__name__}: {exc}")

    try:
        from continuity_open import persist_first_exchange

        persist_first_exchange(
            get_pd(),
            channel_id,
            practitioner_text=str(getattr(message, "content", "") or ""),
            turtle_text=reply,
            thread_loaded=bool(current_block),
        )
    except Exception as exc:
        print(f"Continuity open persist failed: {type(exc).__name__}: {exc}")

    # Detect and remove repeated paragraphs before sending
    paragraphs = reply.split("\n\n")
    if len(paragraphs) > 2:
        seen = set()
        deduped = []
        for p in paragraphs:
            normalized = p.strip()[:200]
            if normalized and normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(p)
        if len(deduped) < len(paragraphs):
            print(f"Dedup: removed {len(paragraphs) - len(deduped)} repeated paragraphs")
            reply = "\n\n".join(deduped)

    if health_surface:
        reply = vet_health_reply(reply)
    if native_eddy:
        from flow_runner import apply_flow_reply_guard, strip_model_operational_lines

        reply, stripped_ops = strip_model_operational_lines(reply)
        if stripped_ops:
            print(f"Stripped model operational lines: {stripped_ops}")
        flow_id = (cfg or {}).get("context_type")
        reply, guard_notes = apply_flow_reply_guard(reply, flow_id, history)
        if guard_notes:
            print(f"Flow reply guard: {guard_notes}")
        if (
            flow_id == "dnd_dm"
            and primitive
            and primitive.has("member_lanes")
            and reply != TURN_UNAVAILABLE_REPLY
        ):
            try:
                from campaign_state import extract_scene_boundary, record_turn

                actor = get_actor_key()
                if not actor:
                    raise PermissionError("campaign turn has no registered actor")
                reply, scene_boundary = extract_scene_boundary(reply)
                recorded = record_turn(
                    get_pd(),
                    primitive=primitive,
                    actor=actor,
                    thread_id=channel_id,
                    player_text=str(getattr(message, "content", "") or ""),
                    turtle_text=reply,
                    scene_boundary=scene_boundary,
                )
                print(
                    f"Campaign event {recorded['event']['event_id']} "
                    f"persisted for {actor}"
                )
            except Exception as exc:
                print(
                    f"Campaign turn held before send: "
                    f"{type(exc).__name__}: {exc}"
                )
                reply = (
                    "*The scene holds for a moment; this turn could not be "
                    "written into the shared story, so nothing advances yet.*"
                )
    # Structured River act offer (tool and/or [[act-offer:…]] trailer) — never visible in Discord.
    reply, act_intent = extract_and_propose_from_reply(reply, channel_id, message.id)
    if act_intent:
        print(
            f"Act offer queued ({act_intent.action}"
            f"{' ' + act_intent.url if act_intent.url else ''}) "
            f"for eddy {channel_id}"
        )
    if tool_report:
        reply = f"{reply}\n\n-# ⚙️ {tool_report}"
    if attachment_extracted:
        source_flags.append("extracted attachment text")
    source_trace = build_source_trace(source_flags)
    if source_trace and not native_eddy:
        reply = f"{reply}\n\n-# {source_trace}"
    if fallback_notice_line:
        reply = f"{fallback_notice_line}\n{reply}"
    history.append({"role": "assistant", "content": reply})
    if prompt_profile == "magic":
        try:
            from session_record import append_turn

            append_turn(
                get_pd(), channel_id,
                practitioner=str(getattr(message, "content", "") or ""),
                reply=reply,
                tools=tools_executed,
                model=thread_model,
                usage=turn_usage,
            )
            from magic_session import finish_release, is_release_ask
            from pathlib import Path

            if is_release_ask(str(getattr(message, "content", "") or "")):
                from workshop_tools import room_checkout

                parent = getattr(message.channel, "parent_id", None)
                checkout = room_checkout(parent) if isinstance(parent, int) else None
                await finish_release(message.channel, Path(get_pd()), checkout)
        except Exception as exc:
            print(f"Session record failed: {type(exc).__name__}: {exc}")
    components = cloud_fallback.stocked_components() if stocked else None
    view = None
    if components:
        from cloud_stocked import StockedView

        view = StockedView()
    if prompt_profile == "magic":
        from spirit_voice import deliver

        await deliver(message, split_message(reply), components=components, view=view)
        try:
            from delegate_key import take_offer

            if take_offer():
                from delegate_setup_ui import post_key_button

                await post_key_button(message.channel)
        except Exception as exc:
            print(f"Delegate key offer failed: {type(exc).__name__}: {exc}")
    else:
        first = True
        for chunk in split_message(reply):
            if first and view is not None:
                await message.reply(chunk, mention_author=False, view=view)
            else:
                await message.reply(chunk, mention_author=False)
            first = False
    try:
        await progress.dress()
    except Exception as exc:
        print(f"Step card dress failed: {type(exc).__name__}: {exc}")
    if (
        primitive
        and primitive.has("intersection_state")
        and isinstance(message.channel, discord.Thread)
    ):
        from team_federation import mark_offered_delivered

        delivered = mark_offered_delivered()
        if delivered:
            print(
                f"Team federation delivered {delivered} sibling event(s) "
                f"to eddy {channel_id}"
            )
    if health_surface:
        try:
            from health_record_ui import post_pending_health_proposals

            primitive = get_channel_primitive(parent_ch_id)
            if primitive and primitive.subject:
                await post_pending_health_proposals(
                    message.channel,
                    get_pd(),
                    subject=primitive.subject,
                    registry=get_registry(),
                )
        except Exception as exc:
            print(f"Health proposal UI failed: {type(exc).__name__}: {exc}")
    log_line = render_log(
        message.channel.name, steps, time.monotonic() - turn_started, thread_model,
        len(reply), tool_names(tools_executed),
    )
    if turn_usage.get("calls"):
        log_line += (
            f" · tokens in={turn_usage.get('input_tokens', 0)}"
            f" cached={turn_usage.get('cache_read_input_tokens', 0)}"
            f" out={turn_usage.get('output_tokens', 0)}"
            f" · usd={turn_cost if turn_cost is not None else 'unpriced'}"
        )
    if fallback_notice_line.startswith("-# ⚠️"):
        log_line += " · FALLBACK local"
    print(log_line)

    # Super-ego: think aloud after sustained conversation
    asyncio.ensure_future(maybe_reflect(message.channel, history))

    if isinstance(message.channel, discord.Thread):
        await update_thread_state(message.channel, cfg, history)
        if native_eddy:
            from mage import river_bot_enabled

            # Split-bot: River re-anchors bars after each turn (see river_eddy_seneschal).
            if not river_bot_enabled():
                from bar_anchor import ensure_channel_bars

                await ensure_channel_bars(message.channel)
        # Phase 1 Eyes: update thread registry on every exchange
        if isinstance(message.channel, discord.Thread):
            try:
                parent_name = message.channel.parent.name if message.channel.parent else "unknown"
                model_label = cfg.get("model_label", "default") if cfg else "default"
                att = cfg.get("attunement", "semi") if cfg else "semi"
                ctx_type = cfg.get("context_type") if cfg else None
                eddy = cfg.get("eddy_type", EDDY_DEFAULT) if cfg else EDDY_DEFAULT
                register_thread(
                    message.channel.id, message.channel.name,
                    parent_channel=parent_name,
                    parent_channel_id=message.channel.parent_id,
                    model=model_label,
                    attunement=att, context_type=ctx_type, eddy_type=eddy,
                )
                update_thread_activity(message.channel.id)
            except Exception as e:
                print(f"Registry update failed: {e}")

    if pending_incidental_urls:
        from state import client as turtle_client

        # discord.Message has no `.client` attribute — use the Turtle bot
        # client. Same class as get_share_bot_client (test_share_ui). Found
        # 2026-08-11: inlined message.txt + incidental URL → empty Claude
        # reply posted, then AttributeError here aborted the link offer.
        await post_link_offer(
            message.channel,
            message,
            pending_incidental_urls,
            turtle_client,
        )

    if _forge_token is not None:
        from workshop_tools import reset_forge_turn

        reset_forge_turn(_forge_token)
    if _platform_token is not None:
        from workshop_tools import reset_platform_turn

        reset_platform_turn(_platform_token)
    sync_history(channel_id)
