"""Dialogue turn execution — handle_dialogue and LLM reply path.

Slice 3 of discord_bot.py decomposition (2026-07-10).
Re-exported from discord_bot for backward compatibility.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone

import discord

from content_fetch import extract_urls as _extract_urls
from dialogue_attachments import (
    attachment_display_names,
    attachments_from_forward_chain,
    gather_dialogue_attachments,
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
    get_native_eddy_prompt,
    get_system_prompt,
    get_thread_prompt,
    uses_native_turtle_prompt,
)
from sessions import maybe_reflect
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
    client,
    dialogue_histories,
    thread_configs,
)
from thread_registry import register_thread, update_thread_activity
from tos_tools import TOS_TOOLS, build_tool_report, execute_tos_tool
from triage import triage_message


async def handle_dialogue(message):
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
    attachments, attachment_names, attachment_note, raw_attachments, attachment_source = (
        await gather_dialogue_attachments(message)
    )
    if not visible_content.strip() and raw_attachments:
        visible_content = f"(attachment: {attachment_display_names(raw_attachments)})"
    parent_ch_id = resolve_dialogue_channel_id(message)
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
        loaded = await load_thread_history(message.channel)
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
                message.channel, client, ref_text
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
    if url_content:
        user_entry += f"\n\n[Fetched content]:\n{url_content[:DIALOGUE_INJECT_MAX + 512]}"
    if dereferenced_context:
        user_entry += f"\n\n{dereferenced_context[:6000]}"
    history.append({"role": "user", "content": user_entry})
    if len(history) > MAX_DIALOGUE_HISTORY:
        history.pop(0)

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
    from mage import uses_craft_surface, get_channel_default_context

    craft_surface = uses_craft_surface(parent_ch_id)
    cfg = thread_configs.get(channel_id)
    if native_eddy:
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
    elif craft_surface:
        ctx = (cfg or {}).get("context_type") if cfg else None
        if not ctx:
            ctx = get_channel_default_context(parent_ch_id) or "craft"
        system_prompt = get_craft_channel_prompt(ctx)
        thread_use_api = (cfg or {}).get("use_api", USE_API) if cfg else USE_API
        thread_model = (cfg or {}).get("model", DIALOGUE_MODEL) if cfg else DIALOGUE_MODEL
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

    # Continuity Engine — Slice 0 (current layer) + Slice 1 (alive headers +
    # per-eddy narrowing). Prepend the substrate packet so Turtle is oriented in
    # the present and knows what's in motion, without being told. Scope is read
    # from scopes.yaml (cross-process: !focus runs in the River bot, this reads
    # it in the Turtle bot). dialogue_model is resolved for THIS turn (hw honesty).
    try:
        from continuity_engine import get_scope, render_substrate_packet

        pd = get_pd()
        scope = get_scope(pd, channel_id)
        current_block = render_substrate_packet(
            pd,
            dialogue_model=thread_model,
            use_api=thread_use_api,
            scope=scope,
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
    if attachments:
        source_flags.append(f"attachment metadata ({', '.join(attachment_names)})")
    elif raw_attachments:
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

    async with message.channel.typing():
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
                        tos_tools=TOS_TOOLS, execute_tool=execute_tos_tool)
                    tool_report = build_tool_report(tools_executed)
                else:
                    reply, tools_executed = await chat_ollama_with_tools(
                        system_prompt, messages_for_llm, model_override=thread_model,
                        tos_tools=TOS_TOOLS, execute_tool=execute_tos_tool)
                    tool_report = build_tool_report(tools_executed)
            elif thread_use_api:
                reply, tools_executed = await chat_anthropic_with_model(
                    system_prompt, messages_for_llm, thread_model, use_tools=True,
                    tos_tools=TOS_TOOLS, execute_tool=execute_tos_tool)
                tool_report = build_tool_report(tools_executed)
            else:
                # Direct commands are handled before dialogue. For ordinary
                # local replies, avoid the conversational tool loop so Qwen
                # does not spend turns searching or routing while Discord waits.
                reply = await chat_ollama(
                    system_prompt, messages_for_llm, model=thread_model,
                    num_ctx=32768, think=False)
                tools_executed = []

            if not reply:
                reply = "(no response generated)"
        except Exception as e:
            print(f"Dialogue error ({thread_model}): {type(e).__name__}: {e}")
            try:
                reply = await chat_ollama(system_prompt, list(history), model=REFLECTION_MODEL)
            except Exception as e2:
                reply = f"[dialogue error: {type(e2).__name__}: {e2}]"

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

    if native_eddy:
        from flow_runner import apply_flow_reply_guard, strip_model_operational_lines

        reply, stripped_ops = strip_model_operational_lines(reply)
        if stripped_ops:
            print(f"Stripped model operational lines: {stripped_ops}")
        flow_id = (cfg or {}).get("context_type")
        reply, guard_notes = apply_flow_reply_guard(reply, flow_id, history)
        if guard_notes:
            print(f"Flow reply guard: {guard_notes}")
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
    if native_eddy:
        print(f"Native Turtle reply sent [{message.channel.name}]: {len(reply)} chars")

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
                    parent_channel=parent_name, model=model_label,
                    attunement=att, context_type=ctx_type, eddy_type=eddy,
                )
                update_thread_activity(message.channel.id)
            except Exception as e:
                print(f"Registry update failed: {e}")

    if pending_incidental_urls:
        await post_link_offer(
            message.channel,
            message.id,
            pending_incidental_urls,
            message.client,
        )

    sync_history(channel_id)
