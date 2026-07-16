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

This file: Discord lifecycle events, main().
  Message dispatch: practice_dispatch.py (Slice 6).
  Dialogue stack: dialogue_* modules (Slices 1–5).
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
    client, CHANNELS, OPS_EMBED_COLOR, EMBED_COLORS,
    get_channel, SPIRIT_BOT_ID, unmark_processed_message,
    IDENTITY_DIR, DIALOGUE_MODEL, REFLECTION_MODEL, TRIAGE_MODEL, USE_API, TURTLE_MODEL,
    RIVER_MODEL,
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
    get_thread_member_ids, river_bot_enabled,
    suppress_turtle_river_voice, get_attunement_profile,
    maybe_reload_mage_registry, reload_mage_registry,
)

from practice_io import (
    read_safe, count_items,
    file_age_hours, format_age, load_intentions_list,
    get_thread_state_dir, read_thread_state,
)

from thread_registry import (
    register_thread, update_thread_activity,
    backfill_from_discord, get_registry_summary,
    get_related_thread_awareness, get_thread_awareness,
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
    local_now, get_history, log_activity, split_message, sync_history,
    load_thread_history, summarize_thread_context,
)

from sessions import session_monitor, checkpoint_session, close_session, maybe_reflect
from eddy_spawn import handle_eddy_spawn_interaction
from intake_server import start_intake_server
from background import practice_health_loop, interoception_loop, daily_reminders_loop, health_canary_loop, daily_note_loop

from commands import (
    try_direct_command, DIRECT_COMMANDS, ControlPanelView,
    ThreadConfigView,
)

from content_fetch import (
    extract_urls as _extract_urls,
)

from link_read import (
    DIALOGUE_INJECT_MAX,
    external_urls,
    should_auto_fetch_urls,
    fetch_urls_with_status,
    maybe_refine_thread_name_from_fetch,
    post_link_offer,
)

from dialogue_routing import (
    route_practice_dialogue as _route_practice_dialogue,
    should_skip_native_starter as _should_skip_native_starter,
    touch_flow_library_after_dialogue as _touch_flow_library_after_dialogue,
)

from dialogue_message import (
    visible_message_content as _visible_message_content,
    extract_forwarded_context as _extract_forwarded_context,
    summarize_message_snapshot as _summarize_message_snapshot,
    forward_source_ref as _forward_source_ref,
    snapshot_has_readable_content as _snapshot_has_readable_content,
    extract_discord_message_refs as _extract_discord_message_refs,
    forwarded_snapshot_is_partial as _forwarded_snapshot_is_partial,
    format_dereferenced_message as _format_dereferenced_message,
    fetch_discord_message_context as _fetch_discord_message_context,
)

from dialogue_turn import (
    handle_dialogue,
    continue_dialogue_turn as _continue_dialogue_turn,
    run_link_read_followup,
)

from dialogue_attachments import (
    attachment_display_names as _attachment_display_names,
    gather_dialogue_attachments as _gather_dialogue_attachments,
    attachments_from_forward_chain as _attachments_from_forward_chain,
)

from dialogue_runtime import (
    build_runtime_env as _build_runtime_env,
    build_native_runtime_env as _build_native_runtime_env,
    build_source_trace as _build_source_trace,
    update_thread_state as _update_thread_state,
)

# Boom thread fetched content cache (message.id -> content string)


# Discord permalink parsing — discord_ref_read.py


# ─── Legacy river chrome ─────────────────────────────────────────

async def _retire_legacy_river_chrome(channel) -> int:
    """Remove pinned Spirit Control Panel and other magic-era river chrome (native mode)."""
    if not channel:
        return 0
    removed = 0
    targets: list[discord.Message] = []
    seen_ids: set[int] = set()

    def _is_control_panel(msg: discord.Message) -> bool:
        if msg.author != client.user:
            return False
        for embed in msg.embeds or []:
            title = embed.title or ""
            if title.startswith("\U0001f3ae") or "Spirit Control Panel" in title:
                return True
        return False

    try:
        async for msg in channel.pins():
            if _is_control_panel(msg) and msg.id not in seen_ids:
                targets.append(msg)
                seen_ids.add(msg.id)
    except discord.HTTPException:
        pass
    try:
        async for msg in channel.history(limit=40):
            if _is_control_panel(msg) and msg.id not in seen_ids:
                targets.append(msg)
                seen_ids.add(msg.id)
    except discord.HTTPException:
        pass

    for msg in targets:
        try:
            await msg.unpin()
        except discord.HTTPException:
            pass
        try:
            await msg.delete()
            removed += 1
        except discord.HTTPException as exc:
            print(f"Control panel delete failed ({msg.id}): {exc}")
    if removed:
        print(f"Retired {removed} legacy control panel(s) in #{getattr(channel, 'name', channel.id)}")
    return removed


# ─── Event Handlers ──────────────────────────────────────────────

_intake_runner = None


@client.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    """Re-run dialogue when practitioner edits a message (Discord does not re-fire on_message)."""
    if after.author == client.user:
        return
    if (before.content or "").strip() == (after.content or "").strip():
        return
    maybe_reload_mage_registry()
    if not is_practice_channel(after):
        return
    if after.author.bot and after.author.id != SPIRIT_BOT_ID:
        return
    if await _should_skip_native_starter(after):
        return
    if after.content.strip().startswith("!") and river_bot_enabled():
        return
    if isinstance(after.channel, discord.Thread):
        from thread_registry import is_eddy_locked

        if is_eddy_locked(
            after.channel.id,
            discord_locked=getattr(after.channel, "locked", False),
        ):
            return

    set_practice_context(after)
    unmark_processed_message(after.id)

    channel_id = after.channel.id
    history = get_history(channel_id)
    visible, _ = _visible_message_content(after)
    author = after.author.display_name
    new_line = f"[{author}]: {visible}"
    replaced = False
    before_visible = (before.content or "").strip()
    for i in range(len(history) - 1, -1, -1):
        if history[i]["role"] != "user":
            continue
        if before_visible and before_visible in history[i]["content"]:
            history[i] = {"role": "user", "content": new_line}
            replaced = True
            break
    if not replaced:
        history.append({"role": "user", "content": new_line})
        if len(history) > MAX_DIALOGUE_HISTORY:
            history.pop(0)

    print(f"Turtle edit inbound [{getattr(after.channel, 'name', channel_id)}]: {visible[:120]!r}")
    await _route_practice_dialogue(after)


@client.event
async def on_interaction(interaction: discord.Interaction):
    """Route component interactions."""
    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data.get("custom_id", "")
        if custom_id.startswith("eddy:spawn:"):
            await handle_eddy_spawn_interaction(interaction)
            return


@client.event
async def on_ready():
    global _intake_runner
    reload_mage_registry()
    client.add_view(ControlPanelView())
    client.add_view(ThreadConfigView())
    try:
        from share_eddy import register_persistent_share_views

        register_persistent_share_views(client)
    except Exception as exc:
        print(f"Share view registration failed: {exc}")
    print(f"Turtle online: {client.user}")
    try:
        from eddy_spawn import cache_turtle_bot_user_id

        if client.user:
            cache_turtle_bot_user_id(client.user.id)
    except Exception as exc:
        print(f"Turtle bot id cache failed: {exc}")
    print(f"tOS: {get_pd()} | Identity: {IDENTITY_DIR}")
    print(f"River: {RIVER_MODEL} (local)")
    print(f"Turtle: {TURTLE_MODEL} (local)")
    if USE_API or DIALOGUE_MODEL != TURTLE_MODEL:
        print(f"Dialogue override: {DIALOGUE_MODEL} ({'API' if USE_API else 'local'})")
    print(f"Background: triage={TRIAGE_MODEL} reflection={REFLECTION_MODEL} (local)")
    print(f"Commands: {', '.join(DIRECT_COMMANDS.keys())}")
    prompt = get_system_prompt()
    print(f"System prompt: {len(prompt)} chars")

    # Start intake before slow Discord thread rejoin so paste stays available during startup.
    if _intake_runner is None:
        try:
            vortex_id = 1494273454738903162
            _intake_runner = await start_intake_server(discord_client=client, vortex_thread_id=vortex_id)
        except Exception as e:
            print(f"Intake server failed to start: {e}")

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
        if should_post and not suppress_turtle_river_voice():
            readiness = startup_readiness_check()
            embed = discord.Embed(
                title="\U0001f422 Turtle online",
                description=f"**Threads:** {thread_count}\n{readiness}",
                color=0x2ECC71,
            )
            embed.set_footer(text=local_now().strftime("%Y-%m-%d %H:%M"))
            await dialogue.send(embed=embed, silent=True)

    asyncio.get_event_loop().create_task(prewarm_triage())

    try:
        from flow_bootstrap import start_flow_bootstrap_watcher

        start_flow_bootstrap_watcher(client)
        print("Flow bootstrap watcher started")
    except Exception as exc:
        print(f"Intake handoff watcher failed to start: {exc}")

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
            from discord_reconcile import ensure_dissolved_threads_archived
            from eddy_spawn import should_defer_turtle_join
            from thread_registry import is_dissolved

            await ensure_dissolved_threads_archived(client, dialogue.id)

            # Active eddies on every practice parent (shared-river / hosted-river too).
            # Use guild.active_threads() — channel.threads cache misses eddies the
            # bot is not already subscribed to (the Galactic Adventure failure mode).
            # Native eddies: join only when already a Discord member so brand-new
            # blank eddies still get River's first-message add_user ceremony.
            from mage import practice_parent_channel_ids

            parent_ids = set(practice_parent_channel_ids())
            try:
                active = await dialogue.guild.active_threads()
            except Exception as e:
                print(f"active_threads fetch failed: {e}")
                active = list(dialogue.threads)

            for t in active:
                parent_id = getattr(t, "parent_id", None)
                if parent_id not in parent_ids:
                    continue
                parent = client.get_channel(parent_id) if parent_id else None
                parent_name = getattr(parent, "name", parent_id)
                if is_dissolved(t.id) and not t.archived and parent_id == dialogue.id:
                    try:
                        await t.edit(archived=True)
                        print(
                            f"Re-archived dissolved thread still active: "
                            f"{t.name} (id: {t.id})"
                        )
                    except Exception as e:
                        print(f"Failed to re-archive dissolved thread {t.name}: {e}")
                    continue
                if should_defer_turtle_join(t):
                    try:
                        await t.fetch_member(client.user.id)
                    except discord.NotFound:
                        print(
                            f"Skipped rejoin (native eddy, not yet member): "
                            f"{t.name} (id: {t.id})"
                        )
                        continue
                    except Exception as e:
                        print(
                            f"Skipped rejoin (native eddy): {t.name} "
                            f"(id: {t.id}) — {e}"
                        )
                        continue
                try:
                    await t.join()
                    print(
                        f"Rejoined thread: {t.name} (id: {t.id}) "
                        f"in #{parent_name}"
                    )
                    await asyncio.sleep(1)  # Throttle to avoid Discord rate limits
                except Exception as e:
                    print(f"Failed to join thread {t.name}: {e}")
                    await asyncio.sleep(2)  # Back off more on failure

            # Operator-river archived cleanup only (do not wake every parent).
            archived_threads = []
            async for t in dialogue.archived_threads(limit=20):
                archived_threads.append(t)
            for t in archived_threads:
                if should_defer_turtle_join(t):
                    continue
                if is_dissolved(t.id):
                    print(f"Skipped dissolved archived thread: {t.name} (id: {t.id})")
                    continue
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

        if suppress_turtle_river_voice():
            try:
                from river_handler import _iter_river_channels

                for ch in await _iter_river_channels(client):
                    await _retire_legacy_river_chrome(ch)
            except Exception as exc:
                print(f"Legacy river chrome retirement failed: {exc}")

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
        if not daily_note_loop.is_running():
            daily_note_loop.start()
            print("daily_note_loop started")
        if not health_canary_loop.is_running():
            health_canary_loop.start()
            print("health_canary_loop started (INT-027)")
    except Exception as e:
        import traceback
        print(f"Background task start failed: {e}")
        traceback.print_exc()

    
    # Intake server starts earlier in on_ready and is guarded by _intake_runner.

    if get_attunement_profile() == "native" and not river_bot_enabled():
        try:
            from river_handler import ensure_river_eddy_bar

            await ensure_river_eddy_bar(client)
        except Exception as exc:
            print(f"Eddy door setup failed: {exc}")

    print("on_ready complete")


@client.event
async def on_thread_create(thread):
    if is_registered_parent_channel(thread.parent_id):
        set_practice_context_for_channel(thread.parent_id)

        pending = None
        if river_bot_enabled() and thread.parent_id:
            import asyncio
            from eddy_spawn import (
                finalize_native_eddy_from_river,
                pop_pending_native_eddy,
                should_defer_turtle_join,
            )

            for _ in range(15):
                pending = pop_pending_native_eddy(thread.id, thread.parent_id)
                if pending:
                    break
                await asyncio.sleep(0.2)
            defer = should_defer_turtle_join(thread, pending)
            if pending:
                try:
                    await finalize_native_eddy_from_river(thread, pending)
                except Exception as exc:
                    print(f"Native eddy finalize failed: {exc}")
            if not defer:
                await thread.join()
                for uid in get_thread_member_ids(thread.parent_id):
                    try:
                        await thread.add_user(discord.Object(id=int(uid)))
                    except Exception:
                        pass
            else:
                print(f"Deferred Turtle join: {thread.name} (id: {thread.id})")
        else:
            await thread.join()
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
            await _update_thread_state(thread, None, [])
            try:
                from discord_reconcile import handle_thread_open

                await handle_thread_open(thread, discord_client=client, pending=pending)
            except Exception as exc:
                print(f"Opened eddy act failed for {thread.id}: {exc}")
            label = " (river→turtle, deferred)" if defer else (" (river→turtle)" if pending else "")
            print(f"{'Deferred' if defer else 'Joined'} + registered thread: {thread.name} (id: {thread.id}){label}")
        except Exception as e:
            print(f"Joined thread: {thread.name} (id: {thread.id}) [registry failed: {e}]")


@client.event
async def on_thread_update(before, after):
    from discord_reconcile import handle_thread_update

    await handle_thread_update(before, after, discord_client=client)


@client.event
async def on_thread_delete(thread):
    from discord_reconcile import handle_thread_delete

    try:
        outcome = await handle_thread_delete(thread, discord_client=client)
        if outcome.get("thread_deleted"):
            print(f"Native thread delete reconciled: {thread.name} ({thread.id})")
    except Exception as exc:
        print(f"Native thread delete reconcile failed for {thread.id}: {exc}")


@client.event
async def on_guild_channel_delete(channel):
    from discord_reconcile import handle_guild_channel_delete

    try:
        outcome = await handle_guild_channel_delete(channel, discord_client=client)
        if outcome.get("channel_orphaned"):
            print(f"Native channel delete reconciled: {getattr(channel, 'name', channel.id)}")
    except Exception as exc:
        print(f"Native channel delete reconcile failed for {channel.id}: {exc}")


@client.event
async def on_guild_channel_create(channel):
    from discord_reconcile import handle_guild_channel_create

    try:
        outcome = await handle_guild_channel_create(channel, discord_client=client)
        if outcome.get("notice_posted"):
            print(f"Unregistered channel notice posted: {getattr(channel, 'name', channel.id)}")
    except Exception as exc:
        print(f"Native channel create reconcile failed for {channel.id}: {exc}")


@client.event
async def on_guild_channel_update(before, after):
    from discord_reconcile import handle_guild_channel_update

    try:
        outcome = await handle_guild_channel_update(before, after, discord_client=client)
        if outcome.get("channel_updated"):
            print(f"Native channel update reconciled: {getattr(after, 'name', after.id)}")
    except Exception as exc:
        print(f"Native channel update reconcile failed for {after.id}: {exc}")


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


@client.event
async def on_message(message):
    from practice_dispatch import dispatch_incoming_message

    await dispatch_incoming_message(message)


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
        print(f"River: {RIVER_MODEL} (local)")
        print(f"Turtle: {TURTLE_MODEL} (local)")
        if USE_API or DIALOGUE_MODEL != TURTLE_MODEL:
            print(f"Dialogue override: {DIALOGUE_MODEL} ({'API' if USE_API else 'local'})")
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
