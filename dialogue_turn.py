"""Dialogue turn execution — handle_dialogue and LLM reply path.

Slice 3 of discord_bot.py decomposition (2026-07-10).
Re-exported from discord_bot for backward compatibility.

Turns are serialized per channel by ``dialogue_queue``. Since 2026-08-07 that
queue also *coalesces*: messages that arrive while a reply is in flight are
absorbed into history in order, and the newest one answers them together.
"""

from __future__ import annotations

import asyncio
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
    DIALOGUE_INJECT_MAX,
    external_urls,
    fetch_urls_with_status,
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
    CRAFT_MODEL,
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


class _StepCard:
    """Show the turn working: one message in the channel, edited as steps happen.

    Discord has no token stream; it has edits. The card is posted at the first
    significant operation — a link or attachment already read, or the first
    lookup the model makes — and otherwise only once the turn has run past
    ``PROGRESS_AFTER_SECONDS``; a quick reply with nothing to show posts
    nothing. While it runs, each lookup and each sentence the model wrote
    before a lookup is appended, edits are spaced ``CARD_EDIT_INTERVAL_SECONDS``
    apart so Discord is never asked to redraw faster than it will, and every
    ``CARD_TICK_SECONDS`` the elapsed time is refreshed so a long compose is
    visibly still alive.

    ``full`` decides what the card becomes when the reply lands: on craft
    surfaces and personal rooms it stays as the step list next to the answer
    (the operator's ask: watch Turtle work, keep the record); in a shared room
    it collapses to the one-line trace, so the room reads an answer and not a
    process log. A Discord failure here never costs the turn.
    """

    def __init__(self, channel, steps: AttunementSteps, model: str, started: float,
                 *, full: bool = False, after: float | None = None):
        self.channel = channel
        self.attunement = steps
        self.model = model
        self.started = started
        self.full = full
        self.after = PROGRESS_AFTER_SECONDS if after is None else after
        self.steps: list[Step] = attunement_step_list(steps)
        self.operations = bool(steps.links or steps.attachments or steps.dereferenced or steps.forwarded)
        self.posted = None
        self._timer = None
        self._tick = None
        self._pending_edit = None
        self._last_edit = 0.0
        self._closed = False

    def _elapsed(self) -> float:
        return time.monotonic() - self.started

    def start(self) -> None:
        if self.operations:
            self._timer = asyncio.ensure_future(self._post())
        elif self.after > 0:
            self._timer = asyncio.ensure_future(self._post_after(self.after))

    async def on_event(self, kind: str, payload: dict) -> None:
        if self._closed:
            return
        if kind == "prose":
            step = prose_step(str(payload.get("text") or ""))
            if step:
                self.steps.append(step)
        elif kind == "tool":
            self.steps.append(describe_tool(
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

    async def _post(self) -> None:
        if self.posted is not None or self._closed:
            return
        try:
            self.posted = await self.channel.send(render_card(self.steps, self._elapsed(), self.model))
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
            await self.posted.edit(content=render_card(self.steps, self._elapsed(), self.model))
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

    async def settle(self, tools_executed) -> None:
        self._closed = True
        for task in (self._timer, self._tick, self._pending_edit):
            if task is not None and not task.done():
                task.cancel()
        if self.posted is None:
            return
        try:
            if self.full:
                content = render_card(self.steps, self._elapsed(), self.model, done=True)
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
    dereferenced_count = 0
    ref_text = message.content or ""
    if forwarded_snapshot_is_partial(message):
        source_ref = forward_source_ref(message)
        if source_ref:
            g, c, m = source_ref
            from discord_ref_read import permalink_for

            ref_text = f"{permalink_for(g or 0, c, m)}\n{ref_text}"
    if ref_text.strip():
        from discord_ref_read import extract_all_discord_refs, fetch_all_discord_refs_with_status

        if extract_all_discord_refs(ref_text):
            _ref_results, dereferenced_context = await fetch_all_discord_refs_with_status(
                message.channel, state.client, ref_text
            )
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
        user_entry += f"\n\n[Fetched content]:\n{url_content[:DIALOGUE_INJECT_MAX + 512]}"
    if dereferenced_context:
        user_entry += f"\n\n{dereferenced_context[:6000]}"
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
                f"[Fetched content]:\n{url_content[:DIALOGUE_INJECT_MAX + 512]}"
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
    if prompt_profile == "native" and native_eddy:
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
        system_prompt = get_native_eddy_prompt(ctx)
        thread_use_api = False
        thread_model = (cfg or {}).get("model") or TURTLE_MODEL
    elif prompt_profile == "craft":
        from llm import resolve_model

        ctx = (cfg or {}).get("context_type") if cfg else None
        if not ctx:
            ctx = get_channel_default_context(parent_ch_id) or "craft"
        system_prompt = get_craft_channel_prompt(ctx)
        # Craft defaults to frontier (CRAFT_MODEL). Upgrade legacy local-stamped
        # configs from before craft used an API model.
        if cfg and cfg.get("model") and cfg.get("use_api"):
            thread_use_api = bool(cfg["use_api"])
            thread_model = cfg["model"]
        elif cfg and cfg.get("model") and str(cfg["model"]).startswith(
            ("claude-", "gemini-")
        ):
            thread_model, thread_use_api = resolve_model(cfg["model"])
        else:
            thread_model, thread_use_api = resolve_model(CRAFT_MODEL)
    elif prompt_profile == "health":
        ctx = (cfg or {}).get("context_type") if cfg else None
        if not ctx:
            ctx = get_channel_default_context(parent_ch_id) or "health"
        system_prompt = get_health_channel_prompt(ctx)
        thread_use_api = USE_API
        thread_model = DIALOGUE_MODEL
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

    if native_eddy:
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

    steps = AttunementSteps(
        links=(url_source_count or len(urls)) if url_content else 0,
        link_chars=len(url_content or ""),
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
    progress = _StepCard(message.channel, steps, thread_model, turn_started, full=card_full)

    async with message.channel.typing():
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
                        reply, tools_executed = await chat_anthropic_with_model(
                            system_prompt, messages_for_llm, thread_model, use_tools=True,
                            tos_tools=tools_for_channel(parent_ch_id), execute_tool=execute_tos_tool,
                            on_event=progress.on_event)
                        tool_report = build_tool_report(tools_executed)
                    else:
                        reply, tools_executed = await chat_ollama_with_tools(
                            system_prompt, messages_for_llm, model_override=thread_model,
                            tos_tools=tools_for_channel(parent_ch_id), execute_tool=execute_tos_tool,
                            on_event=progress.on_event)
                        tool_report = build_tool_report(tools_executed)
                elif thread_use_api:
                    reply, tools_executed = await chat_anthropic_with_model(
                        system_prompt, messages_for_llm, thread_model, use_tools=True,
                        tos_tools=tools_for_channel(parent_ch_id), execute_tool=execute_tos_tool,
                        on_event=progress.on_event)
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
                print(f"Dialogue error ({thread_model}): {type(e).__name__}: {e}")
                reply = ""
                if not thread_use_api and not is_gemini:
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

    # Persist the inject this turn used. Not current.yaml — that file already
    # exists from CE's debounce write. The packet is the named blocks that
    # actually went into the prompt, plus tools and files from this call.
    try:
        from turn_packet import persist_turn_packet

        persist_turn_packet(
            get_pd(),
            channel_id,
            injected={
                "practice_substrate": current_block,
                "runtime_environment": runtime_env,
                "home_working_plan": home_block,
                "absorbed_threads": absorbed_block,
                "url_content": url_content,
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
    history.append({"role": "assistant", "content": reply})
    for chunk in split_message(reply):
        await message.reply(chunk, mention_author=False)
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
    print(render_log(
        message.channel.name, steps, time.monotonic() - turn_started, thread_model,
        len(reply), tool_names(tools_executed),
    ))

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

    sync_history(channel_id)
