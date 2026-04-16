#!/usr/bin/env python3
"""turtleOS Shell — Spirit's persistent interface

Modular architecture (2026-03-29 refactor):
  state.py — shared state, config, client
  mage.py — multi-mage registry, practice directory resolution
  practice_io.py — file I/O utilities
  llm.py — LLM backends (Anthropic, Gemini, Ollama)
  tos_tools.py — 9 practice file tools + execution
  triage.py — message classification (sub-2B local model)
  readiness.py — 8-dimension practice health assessment
  prompts.py — system prompt builders (identity + practice state)
  helpers.py — shared utilities (history, logging, message splitting)
  sessions.py — session lifecycle (timeout, reflection, notes)
  background.py — background tasks (health, interoception)
  commands.py — 28 commands, views, control panel, dispatch

This file: event handlers, handle_dialogue, main().
"""

import asyncio
import os
import json
import re
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

import discord


# ─── Load .env ────────────────────────────────────────────────────

def load_env(env_path=None):
    path = env_path or os.environ.get("DOTENV_PATH", ".env")
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

load_env()

# ─── Module Imports ───────────────────────────────────────────────

from state import (
    client, CHANNELS, OPS_EMBED_COLOR, EMBED_COLORS, _processed_messages,
    get_channel_lock, get_channel,
    IDENTITY_DIR, DIALOGUE_MODEL, REFLECTION_MODEL, TRIAGE_MODEL, USE_API,
    HAS_GEMINI, GOOGLE_API_KEY,
    MAX_DIALOGUE_HISTORY, EDDY_DEFAULT,
    dialogue_histories, active_sessions,
    KNOWN_MODELS,
    thread_configs, absorbed_contexts,
    EDDY_TYPES, EDDY_DEFAULT, threads_flagged_for_release,
)

from mage import (
    get_pd, get_mage_name, get_mage_key,
    set_practice_context, set_practice_context_for_channel,
    is_practice_channel, is_registered_parent_channel,
    get_registry, _resolve_mage_from_author,
    get_thread_member_ids,
)

from practice_io import (
    read_safe, count_items,
    file_age_hours, format_age, load_intentions_list,
    get_thread_state_dir, read_thread_state,
)

from thread_registry import (
    register_thread, update_thread_activity,
    backfill_from_discord, get_registry_summary,
)

from llm import (
    chat_anthropic_with_model, chat_gemini, chat_ollama, chat_ollama_with_tools,
)

from tos_tools import TOS_TOOLS, execute_tos_tool, build_tool_report

from triage import triage_message, prewarm_triage

from prompts import (
    get_system_prompt, get_thread_prompt, build_thread_summary,
)

from readiness import startup_readiness_check

from helpers import (
    local_now, get_history, log_activity, split_message,
    load_thread_history, summarize_thread_context,
    preprocess_attachments,
)

from sessions import session_monitor, close_session, maybe_reflect
from boom_thread import handle_boom_thread_message
from eddy_spawn import should_offer_eddy, make_eddy_spawn_view, handle_eddy_spawn_interaction
from proprioceptor import prepare_context_brief
from background import practice_health_loop, interoception_loop, daily_reminders_loop, health_canary_loop

from commands import (
    try_direct_command, DIRECT_COMMANDS, ControlPanelView, LinkFetchView,
    ThreadConfigView,
)

from content_fetch import (
    extract_urls as _extract_urls,
    fetch_url_content as _fetch_url_content,
    process_urls as _process_urls,
    extract_attachments as _extract_attachments,
)

# Boom thread fetched content cache (message.id -> content string)
_boom_fetched_content = {}


# ─── handle_dialogue ─────────────────────────────────────────────

def _build_runtime_env(message, cfg):
    channel = message.channel
    mage_name = get_mage_name()
    mage_key = get_mage_key()

    is_thread = isinstance(channel, discord.Thread)
    if is_thread:
        parent = channel.parent
        channel_name = parent.name if parent else "(unknown)"
        thread_name = channel.name
    else:
        channel_name = channel.name if hasattr(channel, "name") else "(DM)"
        thread_name = None

    if cfg:
        model = cfg.get("model_label", cfg.get("model", "unknown"))
        attunement = cfg.get("attunement", "semi")
    else:
        model = DIALOGUE_MODEL if USE_API else REFLECTION_MODEL
        attunement = "orchestrator"

    lines = [
        "## Runtime Environment",
        f"- **Channel:** #{channel_name}",
    ]
    if thread_name:
        lines.append(f"- **Thread:** {thread_name}")
    lines.append(f"- **Mage:** {mage_name}")
    lines.append(f"- **Model:** {model}")
    lines.append(f"- **Attunement:** {attunement}")

    if mage_key == "family":
        lines.append(f"- **Message from:** {message.author.display_name}")
        space = get_registry().get("spaces", {}).get("family", {})
        members = space.get("members", [])
        if members:
            lines.append(f"- **Space members:** {', '.join(m.capitalize() for m in members)}")

        speaking_mage, personal_pd = _resolve_mage_from_author(message.author)
        if speaking_mage and personal_pd:
            lines.append(f"- **Speaking mage workspace:** {personal_pd}")
            compass_path = os.path.join(personal_pd, "compass.md")
            if os.path.exists(compass_path):
                compass = read_safe(compass_path)
                if compass.strip():
                    lines.append("")
                    lines.append(f"**{speaking_mage.capitalize()}'s personal compass** (from their sovereign workspace):")
                    lines.append(compass[:3000])

        lines.append("")
        lines.append("**Context:** Shared family space. Keep responses accessible and warm. "
                      "You have access to the speaking member's personal practice state "
                      "via their workspace above. Reference it naturally when relevant. "
                      "Each member's data is sovereign — only share what the speaker asks about.")
    elif thread_name and cfg and cfg.get("attunement") == "raw":
        lines.append("")
        lines.append("**Context boundary:** Raw attunement. "
                      "Be direct and focused on the topic at hand.")

    return "\n".join(lines) + "\n\n"


async def _update_thread_state(thread: discord.Thread, cfg: dict | None, history: list[dict]):
    os.makedirs(get_thread_state_dir(), exist_ok=True)
    safe_name = re.sub(r'[^\w\-]', '_', thread.name.lower())
    state_path = os.path.join(get_thread_state_dir(), f"{safe_name}.md")

    model_label = cfg["model_label"] if cfg else "default"
    attunement = cfg["attunement"] if cfg else "semi"
    msg_count = len(history)
    now = local_now().strftime("%Y-%m-%d %H:%M")

    recent_exchange = ""
    if len(history) >= 2:
        last_user = ""
        last_assistant = ""
        for m in reversed(history):
            if m["role"] == "assistant" and not last_assistant:
                last_assistant = m["content"][:300]
            elif m["role"] == "user" and not last_user:
                last_user = m["content"][:300]
            if last_user and last_assistant:
                break
        if last_user and last_assistant:
            recent_exchange = f"\n**Last exchange:**\n> Mage: {last_user}\n> Spirit: {last_assistant}\n"

    eddy_type = cfg.get("eddy_type", EDDY_DEFAULT) if cfg else EDDY_DEFAULT
    eddy_info = EDDY_TYPES.get(eddy_type, EDDY_TYPES[EDDY_DEFAULT])
    flagged = threads_flagged_for_release.get(thread.id)
    flag_line = f"\n**⚠️ Flagged for release:** {flagged['reason']}\n" if flagged else ""

    content = (
        f"# Thread: {thread.name}\n\n"
        f"**Config:** `{model_label}` / `{attunement}`\n"
        f"**Eddy:** {eddy_info['emoji']} `{eddy_type}` ({eddy_info['days'] or '∞'}d)\n"
        f"**Messages:** {msg_count}\n"
        f"**Last active:** {now}\n"
        f"**Thread ID:** {thread.id}\n"
        f"{flag_line}"
        f"{recent_exchange}"
    )

    try:
        with open(state_path, "w") as f:
            f.write(content)
    except Exception as e:
        print(f"Thread state write failed for {thread.name}: {e}")


async def handle_dialogue(message):
    channel_id = message.channel.id

    # Run triage and proprioceptor in parallel — tissue prepares while classification runs
    triage_task = asyncio.create_task(triage_message(message.content))
    # Proprioceptor runs in parallel — cancelled later if triage says trivial

    proprioceptor_task = asyncio.create_task(prepare_context_brief(message.content))

    triage = await triage_task
    triage_cat = triage.get("category", "practice")
    print(f"Triage [{message.author.display_name}]: {triage_cat} (state={triage.get('needs_state', True)}) — {message.content[:80]}")

    # Cancel proprioceptor for trivial messages — not needed
    if proprioceptor_task and triage_cat not in ("practice", "deep", "link"):
        proprioceptor_task.cancel()
        proprioceptor_task = None

    history = get_history(channel_id)

    if not history and isinstance(message.channel, discord.Thread):
        loaded = await load_thread_history(message.channel)
        if loaded:
            dialogue_histories[channel_id] = loaded
            history = dialogue_histories[channel_id]
            print(f"Thread memory restored: {message.channel.name} ({len(loaded)} messages)")
            summary = summarize_thread_context(loaded, message.channel.name)
            # Internal log only — operational noise, not surfaced to channel (016 principle)
            print(f"Thread memory context: {message.channel.name} ({len(loaded)} msgs) — {summary[:100]}")

    attachments = []
    attachment_note = ""
    if message.attachments:
        attachments = await _extract_attachments(message)
        if attachments:
            fnames = ", ".join(f"{fn}" for _, _, fn in attachments)
            attachment_note = f" [attached: {fnames}]"

    url_content = _boom_fetched_content.pop(message.id, "")
    _urls_already_processed = False
    if url_content:
        attachment_note += " [content from boom capture]"
        _urls_already_processed = True
    else:
        urls = await _extract_urls(message.content)
        if urls:
            _urls_already_processed = True
            url_content = await _process_urls(urls)
            if url_content:
                attachment_note += f" [fetched {len(urls)} URL(s)]"

    # Include fetched content in history so it persists across turns
    user_entry = f"[{message.author.display_name}]: {message.content}{attachment_note}"
    if url_content:
        user_entry += f"\n\n[Fetched content]:\n{url_content[:6000]}"
    history.append({"role": "user", "content": user_entry})
    if len(history) > MAX_DIALOGUE_HISTORY:
        history.pop(0)

    now = datetime.now(timezone.utc)
    is_new_session = channel_id not in active_sessions or active_sessions[channel_id]["closed"]
    if channel_id not in active_sessions:
        active_sessions[channel_id] = {"started": now, "last_message": now, "closed": False}
    active_sessions[channel_id]["last_message"] = now
    active_sessions[channel_id]["closed"] = False

    if is_new_session and not isinstance(message.channel, discord.Thread):
        from mage import get_mage_type
        ctx_parts = []
        pd = get_pd()
        boom_count = count_items(read_safe(os.path.join(pd, "boom.md")))
        bright_count = count_items(read_safe(os.path.join(pd, "boom", "bright.md")))
        compass_age = format_age(file_age_hours(os.path.join(pd, "intentions", "compass.md")))
        intentions = load_intentions_list()
        sdir = os.path.join(pd, "sessions")
        last_session = ""
        if os.path.isdir(sdir):
            recent = sorted([f for f in os.listdir(sdir) if f.endswith(".md")], reverse=True)
            if recent:
                last_session = recent[0].replace(".md", "")
        ctx_parts.append(f"compass ({compass_age})")
        ctx_parts.append(f"boom ({boom_count})")
        ctx_parts.append(f"bright ({bright_count})")
        if intentions:
            ctx_parts.append(f"{len(intentions)} intentions")
        if last_session:
            ctx_parts.append(f"last session: {last_session}")

        # INT-023: Context loads silently. Healthy state needs no announcement.

    cfg = thread_configs.get(channel_id)
    if cfg:
        ctx = cfg.get("context_type")
        if not ctx and hasattr(message.channel, "parent_id") and message.channel.parent_id:
            from mage import get_channel_default_context
            ctx = get_channel_default_context(message.channel.parent_id)
        system_prompt = get_thread_prompt(cfg["attunement"], cfg["use_api"], context_type=ctx)
        thread_use_api = cfg["use_api"]
        thread_model = cfg["model"]
    else:
        system_prompt = get_system_prompt()
        thread_use_api = USE_API
        thread_model = DIALOGUE_MODEL

    runtime_env = _build_runtime_env(message, cfg)
    triage_hint = f"- **Message triage:** {triage_cat}"
    if triage_cat == "deep":
        triage_hint += " (take your time, go deep)"
    elif triage_cat in ("greeting", "casual"):
        triage_hint += " (keep it light and brief)"
    runtime_env = runtime_env.rstrip() + "\n" + triage_hint + "\n\n"

    # Collect proprioceptor — worth waiting since dialogue call is the real bottleneck
    context_brief = None
    proprioceptor_time = None
    if proprioceptor_task:
        _t0 = asyncio.get_event_loop().time()
        try:
            context_brief = await asyncio.wait_for(proprioceptor_task, timeout=5.0)
            proprioceptor_time = asyncio.get_event_loop().time() - _t0
            if context_brief:
                print(f"Proprioceptor: {len(context_brief)} chars ({proprioceptor_time:.1f}s)")
        except asyncio.TimeoutError:
            proprioceptor_time = asyncio.get_event_loop().time() - _t0
            print(f"Proprioceptor: timed out ({proprioceptor_time:.1f}s)")
        except Exception as e:
            print(f"Proprioceptor: failed ({type(e).__name__})")

    # Parse proprioceptor output: REFLEX (visible micro-expression) + BRIEF (for dialogue model)
    _reflex = None
    _tissue_brief = context_brief  # fallback: use raw output
    if context_brief:
        for _pi, _pline in enumerate(context_brief.strip().splitlines()):
            if _pline.strip().upper().startswith("REFLEX:"):
                _raw_reflex = _pline.split(":", 1)[1].strip()
                if _raw_reflex and _raw_reflex != "—" and _raw_reflex != "-":
                    _reflex = _raw_reflex
            elif _pline.strip().upper().startswith("BRIEF:"):
                _rest = context_brief.strip().splitlines()[_pi:]
                _tissue_brief = " ".join(l.strip() for l in _rest).replace("BRIEF:", "", 1).strip()
                break

    # Inject proprioceptor brief into dialogue model system prompt
    if _tissue_brief and context_brief:
        proprioceptor_block = (
            "## Proprioceptive Context (connective tissue model)\n\n"
            f"{_tissue_brief}\n\n"
        )
        system_prompt = runtime_env + proprioceptor_block + system_prompt
    else:
        system_prompt = runtime_env + system_prompt


    messages_for_llm = list(history)
    contexts = absorbed_contexts.get(channel_id, [])
    if contexts and not cfg:
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

    # Micro-expression — body's visible reflex before the mind responds
    if _reflex:
        await message.channel.send(f"-# {_reflex}", silent=True)

    async with message.channel.typing():
        tool_report = ""
        is_gemini = thread_model.startswith("gemini-")
        try:
            if is_gemini and HAS_GEMINI and GOOGLE_API_KEY:
                reply, tools_executed = await chat_gemini(system_prompt, messages_for_llm, model=thread_model, attachments=attachments)
                tool_report = build_tool_report(tools_executed)
            elif attachments and not is_gemini:
                extraction = await preprocess_attachments(attachments) if attachments else ""
                if extraction:
                    messages_for_llm[-1] = dict(messages_for_llm[-1])
                    messages_for_llm[-1]["content"] += "\n\n[Attachment content]:\n" + extraction
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
                reply, tools_executed = await chat_ollama_with_tools(
                    system_prompt, messages_for_llm, model_override=thread_model,
                    tos_tools=TOS_TOOLS, execute_tool=execute_tos_tool)
                tool_report = build_tool_report(tools_executed)

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

    if tool_report:
        reply = f"{reply}\n\n-# ⚙️ {tool_report}"
    history.append({"role": "assistant", "content": reply})
    for chunk in split_message(reply):
        await message.reply(chunk, mention_author=False)

    # Super-ego: think aloud after sustained conversation
    asyncio.ensure_future(maybe_reflect(message.channel, history))

    if urls and not _urls_already_processed:
        external_urls = [u for u in urls if "discord" not in urlparse(u).netloc]
        if external_urls:
            view = LinkFetchView(external_urls)
            await message.channel.send(
                f"\U0001f517 `!fetch {external_urls[0]}`",
                view=view,
            )

    if isinstance(message.channel, discord.Thread):
        await _update_thread_state(message.channel, cfg, history)
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


# ─── Event Handlers ──────────────────────────────────────────────

@client.event
async def on_interaction(interaction: discord.Interaction):
    """Route eddy:spawn button clicks to the handler."""
    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data.get("custom_id", "")
        if custom_id.startswith("eddy:spawn:"):
            await handle_eddy_spawn_interaction(interaction)
            return


@client.event
async def on_ready():
    client.add_view(ControlPanelView())
    client.add_view(ThreadConfigView())
    print(f"Turtle online: {client.user}")
    print(f"tOS: {get_pd()} | Identity: {IDENTITY_DIR}")
    print(f"Dialogue: {DIALOGUE_MODEL} ({'API' if USE_API else 'local'})")
    print(f"Reflection: {REFLECTION_MODEL} (local)")
    print(f"Triage: {TRIAGE_MODEL} (local)")
    print(f"Commands: {', '.join(DIRECT_COMMANDS.keys())}")
    prompt = get_system_prompt()
    print(f"System prompt: {len(prompt)} chars")

    dialogue = get_channel("dialogue")
    thread_count = 0
    if dialogue:
        thread_count = len(dialogue.threads)
        ts = int(datetime.now(timezone.utc).timestamp())
        should_post = True
        try:
            async for prev in dialogue.history(limit=10):
                if prev.author == client.user and prev.embeds:
                    for e in prev.embeds:
                        if e.title and ("Spirit online" in e.title or "enters the river" in e.title):
                            age = (datetime.now(timezone.utc) - prev.created_at).total_seconds()
                            if age < 300:
                                should_post = False
                                print(f"Startup message debounced (last was {age:.0f}s ago)")
                            break
                if not should_post:
                    break
        except Exception:
            pass
        if should_post:
            from pulse import scan_pulse, compose_river_entry, save_river_state
            try:
                set_practice_context_for_channel(dialogue.id)
                pulse_data = scan_pulse()
                entry_title, entry_desc = compose_river_entry(pulse_data, thread_count)
                embed = discord.Embed(
                    title=entry_title,
                    description=entry_desc,
                    color=0x2ECC71,
                )
                embed.set_footer(text=local_now().strftime("%Y-%m-%d %H:%M"))
                await dialogue.send(embed=embed, silent=True)
                save_river_state(entry_title, entry_desc)
            except Exception as e:
                print(f"River-entry failed, falling back: {e}")
                import traceback; traceback.print_exc()
                readiness = startup_readiness_check()
                embed = discord.Embed(
                    title="\U0001f422 Turtle online",
                    description=f"**Threads:** {thread_count}\n{readiness}",
                    color=0x2ECC71,
                )
                embed.set_footer(text=local_now().strftime("%Y-%m-%d %H:%M"))
                await dialogue.send(embed=embed, silent=True)

    asyncio.get_event_loop().create_task(prewarm_triage())

    # Pre-warm delegate edit model to avoid cold-start latency
    async def _prewarm_edit_model():
        import urllib.request
        from state import OLLAMA_URL, EDIT_DELEGATE_MODEL
        try:
            payload = json.dumps({
                "model": EDIT_DELEGATE_MODEL,
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False,
                "options": {"num_ctx": 512, "num_predict": 1},
                "keep_alive": "30m",
            }).encode()
            def _do():
                req = urllib.request.Request(
                    f"{OLLAMA_URL}/api/chat",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    resp.read()
            import asyncio
            await asyncio.to_thread(_do)
            print(f"Edit model pre-warmed: {EDIT_DELEGATE_MODEL}")
        except Exception as e:
            print(f"Edit model pre-warm failed: {e}")
    asyncio.get_event_loop().create_task(_prewarm_edit_model())

    if dialogue:
        try:
            active = dialogue.threads
            for t in active:
                try:
                    await t.join()
                    print(f"Rejoined thread: {t.name} (id: {t.id})")
                    await asyncio.sleep(1)  # Throttle to avoid Discord rate limits
                except Exception as e:
                    print(f"Failed to join thread {t.name}: {e}")
                    await asyncio.sleep(2)  # Back off more on failure
            archived_threads = []
            async for t in dialogue.archived_threads(limit=20):
                archived_threads.append(t)
            for t in archived_threads:
                try:
                    await t.edit(archived=False)
                    await asyncio.sleep(0.5)
                    await t.join()
                    print(f"Unarchived & joined: {t.name} (id: {t.id})")
                    await asyncio.sleep(1)
                except Exception as e:
                    print(f"Skipped archived thread {t.name}: {e}")
        except Exception as e:
            print(f"Thread sync on startup failed: {e}")

        try:
            state_dir = get_thread_state_dir()
            if os.path.isdir(state_dir):
                live_thread_ids = set()
                for t in dialogue.threads:
                    live_thread_ids.add(str(t.id))
                cleaned = 0
                for fname in os.listdir(state_dir):
                    if not fname.endswith(".md"):
                        continue
                    fpath = os.path.join(state_dir, fname)
                    try:
                        with open(fpath) as f:
                            content = f.read()
                        tid_match = re.search(r"\*\*Thread ID:\*\*\s*(\d+)", content)
                        if tid_match and tid_match.group(1) not in live_thread_ids:
                            os.remove(fpath)
                            cleaned += 1
                    except Exception:
                        pass
                if cleaned:
                    print(f"Cleaned {cleaned} stale thread-state files")
        except Exception as e:
            print(f"Thread-state cleanup failed: {e}")

        # Phase 1 Eyes: backfill thread registry from Discord
        try:
            guild = dialogue.guild
            gfull = await client.fetch_guild(guild.id)
            from mage import get_registry as _get_mage_registry
            _reg = _get_mage_registry()
            _practice_channels = []
            for ch_id_str in _reg.get("channels", {}).keys():
                try:
                    _practice_channels.append(int(ch_id_str))
                except (ValueError, TypeError):
                    pass
            added, updated = await backfill_from_discord(gfull, _practice_channels or None)
            summary = get_registry_summary()
            print(f"Thread registry backfill: {added} added, {updated} updated — {summary}")
        except Exception as e:
            print(f"Thread registry backfill failed: {e}")

        has_panel = False
        try:
            async for m in dialogue.pins():
                if m.author == client.user:
                    for e in (m.embeds or []):
                        if e.title and e.title.startswith("\U0001f3ae"):
                            has_panel = True
        except Exception:
            pass
        if not has_panel:
            try:
                async for m in dialogue.history(limit=20):
                    if m.author == client.user:
                        for e in (m.embeds or []):
                            if e.title and e.title.startswith("\U0001f3ae"):
                                has_panel = True
                                break
                    if has_panel:
                        break
            except Exception:
                pass
        if not has_panel:
            try:
                embed = discord.Embed(
                    title="\U0001f3ae Spirit Control Panel",
                    description=(
                        "**Threads** \u2014 pick model + attunement, then tap New Thread.\n"
                        "**Practice** \u2014 quick access to status, diagnostics, boom, sweep.\n"
                        "**Session** \u2014 recall to orient, release to close."
                    ),
                    color=0x5865F2,
                )
                panel_msg = await dialogue.send(embed=embed, view=ControlPanelView())
                try:
                    await panel_msg.pin()
                    print("Control panel deployed and pinned.")
                except Exception:
                    print("Control panel deployed (pin failed — pin manually).")
            except Exception as e:
                print(f"Control panel deploy failed: {e}")

    try:
        if not session_monitor.is_running():
            session_monitor.start()
            print("session_monitor started")
        if not practice_health_loop.is_running():
            practice_health_loop.start()
            print("practice_health_loop started")
        if not interoception_loop.is_running():
            interoception_loop.start()
            print("interoception_loop started")
        if not daily_reminders_loop.is_running():
            daily_reminders_loop.start()
            print("daily_reminders_loop started")
        if not health_canary_loop.is_running():
            health_canary_loop.start()
            print("health_canary_loop started (INT-027)")
    except Exception as e:
        import traceback
        print(f"Background task start failed: {e}")
        traceback.print_exc()

    
    print("on_ready complete")


@client.event
async def on_thread_create(thread):
    if is_registered_parent_channel(thread.parent_id):
        await thread.join()
        set_practice_context_for_channel(thread.parent_id)
        for uid in get_thread_member_ids(thread.parent_id):
            try:
                await thread.add_user(discord.Object(id=int(uid)))
            except Exception:
                pass
        # Phase 1 Eyes: register new thread
        try:
            parent_name = thread.parent.name if thread.parent else "unknown"
            created = thread.created_at.isoformat() if thread.created_at else None
            register_thread(
                thread.id, thread.name,
                parent_channel=parent_name, created=created,
            )
            print(f"Joined + registered thread: {thread.name} (id: {thread.id})")
        except Exception as e:
            print(f"Joined thread: {thread.name} (id: {thread.id}) [registry failed: {e}]")


@client.event
async def on_thread_update(before, after):
    if is_registered_parent_channel(after.parent_id if after.parent_id else 0):
        from thread_registry import update_thread_name
        if before.name != after.name:
            try:
                update_thread_name(after.id, after.name)
                print(f"Thread renamed: {before.name} -> {after.name}")
            except Exception as e:
                print(f"Thread rename registry update failed: {e}")


@client.event
async def on_member_join(member):
    if member.bot:
        return
    await log_activity(
        f"New member joined: **{member.display_name}** ({member.name}). "
        f"Use `!admin onboard {member.name}` to create their practice space.",
        "\U0001f44b"
    )
    print(f"New member joined: {member.name} (id: {member.id})")


@client.event
async def on_member_remove(member):
    if member.bot:
        return
    await log_activity(
        f"Member left: **{member.display_name}** ({member.name}).",
        "\U0001f6aa"
    )
    print(f"Member left: {member.name} (id: {member.id})")


# Spirit bot (dyad partner) — messages from Spirit are treated as practitioner input
SPIRIT_BOT_ID = 1487405701440733294


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.type not in (discord.MessageType.default, discord.MessageType.reply):
        return

    set_practice_context(message)

    if message.author.bot:
        if message.author.id == SPIRIT_BOT_ID and is_practice_channel(message):
            # Spirit (dyad partner) — process like a practitioner message
            pass  # fall through to normal handling below
        elif client.user in message.mentions and is_practice_channel(message):
            await handle_dialogue(message)
            return
        else:
            return

    if is_practice_channel(message):
        if await try_direct_command(message):
            return
        # Message-level dedup: skip if already seen (prevents duplicate responses)
        if message.id in _processed_messages:
            print(f"Skipping duplicate message {message.id}")
            return
        _processed_messages.append(message.id)

        # Boom thread: URLs/attachments capture-only; plain text captures AND converses
        if (isinstance(message.channel, discord.Thread)
                and message.channel.name.lower() == "boom"
                and not message.content.strip().startswith("!")):
            has_urls = "http://" in message.content or "https://" in message.content
            has_attachments = bool(message.attachments)
            # All boom messages: capture to boom, then fall through to dialogue
            lock = get_channel_lock(message.channel.id)
            async with lock:
                fetched_content = await handle_boom_thread_message(message)
            if fetched_content:
                _boom_fetched_content[message.id] = fetched_content
            # Fall through to handle_dialogue below

        # Auto-detect thread-worthy content in main channel
        offer_eddy = (
            not isinstance(message.channel, discord.Thread)
            and should_offer_eddy(message)
        )

        lock = get_channel_lock(message.channel.id)
        async with lock:
            await handle_dialogue(message)

        if offer_eddy:
            try:
                view = make_eddy_spawn_view(message)
                await message.channel.send(
                    "-# 🧵 This looks like it could be its own thread.",
                    view=view,
                    silent=True,
                )
            except Exception as e:
                print(f"Eddy offer failed: {e}")


# ─── Main ────────────────────────────────────────────────────────


def _ensure_single_instance():
    """Prevent duplicate bot processes using an exclusive file lock.

    Uses fcntl.flock() — atomic, kernel-level, automatically released on
    process exit (including crashes). No race conditions unlike pgrep.
    """
    import fcntl
    lock_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".discord_bot.lock")
    global _lock_file
    _lock_file = open(lock_path, "w")
    try:
        fcntl.flock(_lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        _lock_file.write(str(os.getpid()))
        _lock_file.flush()
    except (IOError, OSError):
        print("Another discord_bot.py is already running. Exiting.", file=sys.stderr)
        sys.exit(1)

def main():
    _ensure_single_instance()
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        print("Error: DISCORD_BOT_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    if "--test" in sys.argv:
        print(f"Bot token: ...{token[-8:]}")
        print(f"Practice: {get_pd()} | Identity: {IDENTITY_DIR}")
        print(f"Dialogue: {DIALOGUE_MODEL} ({'API' if USE_API else 'local'})")
        print(f"Reflection: {REFLECTION_MODEL} (local)")
        print(f"Channels: {', '.join(k for k,v in CHANNELS.items() if v)}")
        print(f"Commands: {', '.join(DIRECT_COMMANDS.keys())}")
        prompt = get_system_prompt()
        print(f"System prompt: {len(prompt)} chars")
        print("Configuration OK.")
        return

    import logging
    logging.basicConfig(level=logging.WARNING, stream=sys.stdout, force=True)
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
    client.run(token)


if __name__ == "__main__":
    main()
