"""turtleOS commands — 28 direct commands, views, control panel, dispatch."""

import asyncio
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import discord

from state import (
    client, CHANNELS, OPS_EMBED_COLOR, EMBED_COLORS,
    get_channel,
    IDENTITY_DIR, OLLAMA_URL, DIALOGUE_MODEL, REFLECTION_MODEL, USE_API,
    EDIT_DELEGATE_MODEL,
    MAX_DIALOGUE_HISTORY, MAX_TOOL_ROUNDS,
    OBSIDIAN_VAULT, PRACTICE_WEB_BASE,
    dialogue_histories, active_sessions, _processed_messages,
    ATTUNEMENT_LEVELS, KNOWN_MODELS,
    thread_configs, absorbed_contexts,
    EDDY_TYPES, EDDY_DEFAULT, threads_flagged_for_release,
    panel_selections,
    GOOGLE_API_KEY, HAS_GEMINI,
)

from mage import (
    get_pd, get_mage_name, get_mage_key, get_mage_type,
    set_practice_context, set_practice_context_for_channel,
    is_practice_channel, is_registered_parent_channel,
    reload_mage_registry, get_registry,
    _resolve_mage_from_author, _MAGE_REGISTRY,
    get_thread_member_ids,
)

from practice_io import (
    read_safe, read_header, count_items, truncate, obsidian_link,
    summarize_bright, extract_section, list_headings, load_intentions_list,
    is_readable, is_writable,
    file_age_hours, format_age,
    get_thread_state_dir, read_thread_state,
)

from llm import (
    resolve_model, chat_anthropic, chat_anthropic_with_model,
    chat_gemini, chat_ollama, chat_ollama_with_tools,
)

from tos_tools import TOS_TOOLS, execute_tos_tool, build_tool_report

from readiness import assess_readiness, startup_readiness_check, save_readiness_trail

from content_fetch import (
    extract_urls as _extract_urls,
    fetch_url_content as _fetch_url_content,
    litl_check as _litl_check,
    fetch_twitter as _fetch_twitter,
    fetch_youtube_transcript as _fetch_youtube_transcript,
    detect_platform as _detect_platform,
    process_urls as _process_urls,
)

from helpers import get_history, log_activity, split_message
from attunement import perform_attunement, get_digest_age_hours


# ─── Direct Commands ─────────────────────────────────────────────

async def cmd_status(message):
    now = datetime.now(timezone.utc)
    try:
        uptime_raw = subprocess.run(["uptime"], capture_output=True, text=True, timeout=5).stdout.strip()
        uptime = uptime_raw.split("up ")[-1].split(",")[0].strip() if "up " in uptime_raw else "unknown"
    except Exception:
        uptime = "unknown"

    try:
        tags = subprocess.run(["curl", "-s", "http://localhost:11434/api/tags"],
                              capture_output=True, text=True, timeout=5)
        model_data = json.loads(tags.stdout)
        models = [m["name"] for m in model_data.get("models", [])]
        ollama_status = ", ".join(models) if models else "no models"
    except Exception:
        ollama_status = "unreachable"

    boom = read_safe(os.path.join(get_pd(), "boom.md"))
    bright = read_safe(os.path.join(get_pd(), "bright.md"))
    compass = read_safe(os.path.join(get_pd(), "compass.md"))

    sdir = os.path.join(get_pd(), "sessions")
    session_files = [f for f in os.listdir(sdir) if f.endswith(".md")] if os.path.isdir(sdir) else []
    if session_files:
        last_session = max(session_files, key=lambda f: os.path.getmtime(os.path.join(sdir, f))).replace(".md", "")
    else:
        last_session = "none"

    idir = os.path.join(get_pd(), "intentions")
    intention_files = [f for f in os.listdir(idir) if f.endswith(".md")] if os.path.isdir(idir) else []

    active_count = sum(1 for s in active_sessions.values() if not s["closed"])

    embed = discord.Embed(title="\U0001f422 Turtle Status", color=EMBED_COLORS["status_ok"], timestamp=now)
    embed.add_field(name="Dialogue", value=f"`{DIALOGUE_MODEL}`\n({'API' if USE_API else 'local'})", inline=True)
    embed.add_field(name="Reflection", value=f"`{REFLECTION_MODEL}`\n(local)", inline=True)
    embed.add_field(name="Ollama", value=ollama_status, inline=True)
    embed.add_field(name="Uptime", value=uptime, inline=True)
    embed.add_field(name="Sessions", value=str(active_count), inline=True)
    embed.add_field(name="tOS", value="active" if os.path.isfile(os.path.join(get_pd(), "system.md")) else "missing", inline=True)

    practice = [
        f"Boom: **{count_items(boom)}** items",
        f"Bright: **{count_items(bright)}** items",
        f"Compass: {'built' if compass.strip() else 'not yet'}",
        f"Intentions: **{len(intention_files)}** active",
        f"Last session: `{last_session}`",
    ]
    embed.add_field(name="Practice", value="\n".join(practice), inline=False)
    embed.set_footer(text="turtleOS shell")
    await message.reply(embed=embed, mention_author=False)


async def cmd_boom(message, args):
    boom_path = os.path.join(get_pd(), "boom.md")
    if args and args[0].lower() == "add":
        text = " ".join(args[1:])
        if not text:
            await message.reply("Usage: `!boom add <your thought>`", mention_author=False)
            return
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(boom_path, "a") as f:
            f.write(f"\n- {text} ({timestamp})\n")
        await message.add_reaction("\U0001f4a5")
        count = count_items(read_safe(boom_path))
        await message.reply(f"Dropped into boom. ({count} items now)", mention_author=False)
        # Context injection: Turtle knows what was added (016 nervous system)
        history = get_history(message.channel.id)
        history.append({"role": "user", "content": f"!boom add {text}"})
        history.append({"role": "assistant", "content": f"[System: Added to boom: \"{text}\" ({count} items total)]"})
        return

    boom = read_safe(boom_path)
    if not boom.strip():
        embed = discord.Embed(title="\U0001f4a5 Boom Buffer", description="*Empty.*", color=EMBED_COLORS["boom"])
    else:
        embed = discord.Embed(title=f"\U0001f4a5 Boom Buffer ({count_items(boom)} items)",
                              description=truncate(boom), color=EMBED_COLORS["boom"])
    embed.set_footer(text="!boom add <thought> to capture | !boom convert to distill conversation")
    await message.reply(embed=embed, mention_author=False)

    # Context injection: give Turtle the actual boom content (016 nervous system)
    if boom.strip():
        boom_summary = f"Boom buffer ({count_items(boom)} items):\n{boom[:3000]}"
    else:
        boom_summary = "Boom buffer is empty."
    history = get_history(message.channel.id)
    history.append({"role": "user", "content": "!boom"})
    history.append({"role": "assistant", "content": f"[System: {boom_summary}]"})


async def cmd_boom_convert(message):
    channel_id = message.channel.id
    history = get_history(channel_id)
    if not history:
        await message.reply("No conversation to convert.", mention_author=False)
        return

    conversation = "\n".join(
        f"{'Mage' if m['role'] == 'user' else 'Turtle'}: {m['content']}" for m in history
    )
    distill_prompt = """Review this conversation. Extract what resonated — observations, insights, seeds, connections worth remembering. Skip small talk.
Write each as a boom entry: one line, starting with "- ". Output ONLY entries, nothing else.
If nothing worth capturing: output exactly (nothing to capture)"""

    async with message.channel.typing():
        try:
            result = await chat_ollama(distill_prompt, [{"role": "user", "content": conversation}],
                                        model=REFLECTION_MODEL, num_ctx=8192)
            if not result or "(nothing to capture)" in result.lower():
                await message.reply("Nothing worth capturing from this conversation.", mention_author=False)
                return

            boom_path = os.path.join(get_pd(), "boom.md")
            existing = read_safe(boom_path)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            with open(boom_path, "w") as f:
                f.write(existing.rstrip() + f"\n\n## Turtle Dialogue ({timestamp})\n" + result + "\n")

            entry_count = sum(1 for line in result.split("\n") if line.strip().startswith("- "))
            embed = discord.Embed(title=f"\U0001f4a5 Converted ({entry_count} entries)",
                                  description=truncate(result, 1800), color=EMBED_COLORS["boom"])
            embed.set_footer(text="Spirit reads these during next boom sweep")
            await message.reply(embed=embed, mention_author=False)
        except Exception as e:
            await message.reply(f"Boom conversion failed: {e}", mention_author=False)


async def cmd_bright(message):
    bright = read_safe(os.path.join(get_pd(), "bright.md"))
    if not bright.strip():
        embed = discord.Embed(title="\u2728 Bright Surface", description="*Empty.*", color=EMBED_COLORS["bright"])
    else:
        embed = discord.Embed(title=f"\u2728 Bright Surface ({count_items(bright)} items)",
                              description=truncate(bright), color=EMBED_COLORS["bright"])
    await message.reply(embed=embed, mention_author=False)

    # Context injection: give Turtle the actual bright content (016 nervous system)
    if bright.strip():
        bright_summary = f"Bright surface ({count_items(bright)} items):\n{bright[:3000]}"
    else:
        bright_summary = "Bright surface is empty."
    history = get_history(message.channel.id)
    history.append({"role": "user", "content": "!bright"})
    history.append({"role": "assistant", "content": f"[System: {bright_summary}]"})


async def cmd_compass(message):
    compass = read_safe(os.path.join(get_pd(), "compass.md"))
    if not compass.strip():
        embed = discord.Embed(title="\U0001f9ed Compass", description="*Not yet built.*", color=EMBED_COLORS["compass"])
    else:
        embed = discord.Embed(title="\U0001f9ed Compass", description=truncate(compass), color=EMBED_COLORS["compass"])
    await message.reply(embed=embed, mention_author=False)


async def cmd_intentions(message):
    idir = os.path.join(get_pd(), "intentions")
    if not os.path.isdir(idir):
        await message.reply("No intentions directory yet.", mention_author=False)
        return
    files = sorted(f for f in os.listdir(idir) if f.endswith(".md"))
    if not files:
        await message.reply("No active intentions.", mention_author=False)
        return
    embed = discord.Embed(title=f"\U0001f3af Intentions ({len(files)})", color=EMBED_COLORS["compass"])
    for fname in files:
        content = read_safe(os.path.join(idir, fname))
        name = fname.replace(".md", "").replace("-", " ").replace("_", " ")
        embed.add_field(name=name, value=content.strip()[:200] if content.strip() else "(empty)", inline=False)
    await message.reply(embed=embed, mention_author=False)


async def cmd_sync(message):
    now = datetime.now()
    files = ["boom.md", "bright.md", "compass.md"]
    lines = []
    for fname in files:
        path = os.path.join(get_pd(), fname)
        if os.path.isfile(path):
            mtime = datetime.fromtimestamp(os.path.getmtime(path))
            age = now - mtime
            if age.total_seconds() < 3600:
                age_str = f"{int(age.total_seconds() / 60)}m ago"
            elif age.total_seconds() < 86400:
                age_str = f"{int(age.total_seconds() / 3600)}h ago"
            else:
                age_str = f"{int(age.total_seconds() / 86400)}d ago"
            lines.append(f"`{fname}`: {age_str}")
        else:
            lines.append(f"`{fname}`: missing")
    freshness = "\n".join(lines)

    # 016 reroute: check if anything is stale (> 24h) or missing
    has_issues = any("missing" in l or "d ago" in l for l in lines)
    if has_issues:
        embed = discord.Embed(title="\U0001f504 Practice State Freshness", color=EMBED_COLORS["sync"])
        embed.add_field(name="Files", value=freshness, inline=False)
        embed.add_field(name="Sync Method",
                        value="Obsidian LiveSync via CouchDB — bidirectional, real-time.\n`!diagnose` for full stack health.",
                        inline=False)
        await message.reply(embed=embed, mention_author=False)
    else:
        # Healthy — brief confirmation, no verbose embed
        print(f"Sync healthy: {' | '.join(lines)}")
        await message.reply("\u2705 Practice state fresh.", mention_author=False)


async def cmd_diagnose(message):
    """Full practice stack diagnostic — checks all five layers."""
    now = datetime.now(timezone.utc)
    issues = []
    actions = []

    # ── Layer 1: Services
    services_lines = []

    def _check_process(name, pattern):
        try:
            r = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True, timeout=5)
            return r.returncode == 0
        except Exception:
            return False

    def _check_launchd(label):
        try:
            r = subprocess.run(["launchctl", "list"], capture_output=True, text=True, timeout=5)
            return label in r.stdout
        except Exception:
            return False

    couchdb_running = _check_process("CouchDB", "beam.smp")
    obsidian_running = _check_process("Obsidian", "Obsidian")
    discord_running = _check_launchd("com.turtle.discord")
    ollama_reachable = False

    services_lines.append(f"{'✅' if discord_running else '❌'} Discord bot")
    services_lines.append(f"{'✅' if couchdb_running else '❌'} CouchDB")
    services_lines.append(f"{'✅' if obsidian_running else '❌'} Obsidian (LiveSync host)")

    try:
        r = subprocess.run(["curl", "-s", "-m", "3", "http://localhost:11434/api/tags"],
                           capture_output=True, text=True, timeout=5)
        model_data = json.loads(r.stdout)
        models = [m["name"] for m in model_data.get("models", [])]
        ollama_reachable = True
        services_lines.append(f"✅ Ollama ({len(models)} models)")
    except Exception:
        services_lines.append("❌ Ollama")

    if not couchdb_running:
        issues.append("CouchDB is down — all sync is dead")
        actions.append("`open ~/Applications/Apache\\ CouchDB.app`")
    if not obsidian_running:
        issues.append("Obsidian not running — LiveSync relay is offline")
        actions.append("`launchctl kickstart -k gui/$(id -u)/com.obsidian`")
    if not discord_running:
        issues.append("Discord bot is down")
        actions.append("`launchctl kickstart -k gui/$(id -u)/com.turtle.discord`")
    if not ollama_reachable:
        issues.append("Ollama unreachable — local inference unavailable")
        actions.append("Check if Ollama is installed and running")

    # ── Layer 2: Connections
    connections_lines = []

    couchdb_healthy = False
    couchdb_doc_count = 0
    try:
        r = subprocess.run(
            ["curl", "-s", "-m", "3", "http://admin:LPWDpWLuf4i9Bp1A2OCKpQ@localhost:5984/workshop_sync"],
            capture_output=True, text=True, timeout=5)
        db_info = json.loads(r.stdout)
        couchdb_doc_count = db_info.get("doc_count", 0)
        couchdb_healthy = couchdb_doc_count > 0
        connections_lines.append(f"✅ CouchDB: {couchdb_doc_count} docs")
    except Exception:
        connections_lines.append("❌ CouchDB: cannot connect")
        if couchdb_running:
            issues.append("CouchDB process running but not responding on port 5984")
            actions.append("Check CouchDB logs: `tail -20 ~/Library/Application\\\\ Support/CouchDB2/couch.log`")

    tailscale_ok = False
    tailscale_url = ""
    try:
        r = subprocess.run(["/Applications/Tailscale.app/Contents/MacOS/Tailscale", "serve", "status"],
                           capture_output=True, text=True, timeout=5)
        if "proxy" in r.stdout and "5984" in r.stdout:
            tailscale_ok = True
            for line in r.stdout.split("\n"):
                if "https://" in line:
                    tailscale_url = line.strip().split()[0]
                    break
            connections_lines.append(f"✅ Tailscale serve → `{tailscale_url}`")
        else:
            connections_lines.append("⚠️ Tailscale serve: not proxying CouchDB")
            issues.append("Tailscale serve is not proxying CouchDB — mobile sync broken")
            actions.append("`sudo /Applications/Tailscale.app/Contents/MacOS/Tailscale serve --bg http://localhost:5984`")
    except Exception:
        connections_lines.append("❌ Tailscale: cannot check status")
        issues.append("Tailscale binary not found or not responding")
        actions.append("Verify Tailscale is installed: `brew install tailscale`")

    gateway_latency = round(client.latency * 1000)
    connections_lines.append(f"✅ Discord gateway: {gateway_latency}ms" if gateway_latency < 5000
                             else f"⚠️ Discord gateway: {gateway_latency}ms (slow)")

    # ── Layer 3: Sync
    sync_lines = []

    disk_file_count = 0
    try:
        for root, dirs, files in os.walk(get_pd()):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            disk_file_count += sum(1 for f in files if f.endswith(".md"))
    except Exception:
        pass

    if couchdb_healthy and disk_file_count > 0:
        sync_lines.append(f"✅ Disk: {disk_file_count} files | CouchDB: {couchdb_doc_count} docs")
    elif disk_file_count > 0 and not couchdb_healthy:
        sync_lines.append(f"⚠️ Disk: {disk_file_count} files | CouchDB: unreachable")
        issues.append("Files exist on disk but CouchDB is unreachable — sync paused")
    elif disk_file_count == 0:
        sync_lines.append("❌ No practice files on disk")
        issues.append("Practice directory appears empty")

    practice_files = ["boom.md", "bright.md", "compass.md"]
    stale_files = []
    for fname in practice_files:
        age = file_age_hours(os.path.join(get_pd(), fname))
        if age > 48:
            stale_files.append(f"`{fname}` ({format_age(age)})")
    if stale_files:
        sync_lines.append(f"⚠️ Stale: {', '.join(stale_files)}")
    else:
        sync_lines.append("✅ Core files fresh (< 48h)")

    # ── Layer 4: Practice Flow
    practice_lines = []

    boom = read_safe(os.path.join(get_pd(), "boom.md"))
    boom_count = count_items(boom)
    boom_age = file_age_hours(os.path.join(get_pd(), "boom.md"))
    if boom_count >= 15 and boom_age > 24:
        practice_lines.append(f"⚠️ Boom: {boom_count} items, untouched {format_age(boom_age)} — needs sweep")
        actions.append("`!sweep` to process boom into bright")
    elif boom_count > 0:
        practice_lines.append(f"✅ Boom: {boom_count} items")
    else:
        practice_lines.append("✅ Boom: empty")

    sdir = os.path.join(get_pd(), "sessions")
    if os.path.isdir(sdir):
        session_files = [f for f in os.listdir(sdir) if f.endswith(".md")]
        if session_files:
            latest = max(session_files, key=lambda f: os.path.getmtime(os.path.join(sdir, f)))
            latest_session_age = file_age_hours(os.path.join(sdir, latest))
            if latest_session_age > 72:
                practice_lines.append(f"⚠️ Last session: {format_age(latest_session_age)} ago")
            else:
                practice_lines.append(f"✅ Last session: {format_age(latest_session_age)} ago")
        else:
            practice_lines.append("⚠️ No session notes yet")

    pdir = os.path.join(get_pd(), "proposals")
    if os.path.isdir(pdir):
        proposals = [f for f in os.listdir(pdir) if f.endswith(".md")]
        if len(proposals) >= 3:
            practice_lines.append(f"⚠️ {len(proposals)} proposals waiting")
        elif proposals:
            practice_lines.append(f"✅ {len(proposals)} proposal(s)")

    # ── Layer 5: Reachability
    reach_lines = []
    if tailscale_ok and tailscale_url:
        reach_lines.append(f"✅ Mobile sync URL: `{tailscale_url}`")
        reach_lines.append("Phone not syncing? Check:\n"
                           "1. Tailscale app connected on phone\n"
                           "2. LiveSync URI matches the URL above\n"
                           "3. Try toggling LiveSync off/on in Obsidian")
    elif not tailscale_ok:
        reach_lines.append("❌ Mobile sync unavailable (Tailscale serve down)")
    reach_lines.append(f"✅ SSH: `turtle@192.168.8.106` (LAN) or Tailscale IP")

    # ── Build embed
    has_errors = any("❌" in l for l in services_lines + connections_lines + sync_lines)
    has_warnings = any("⚠️" in l for l in services_lines + connections_lines + sync_lines + practice_lines)

    if has_errors:
        color = EMBED_COLORS["status_error"]
        title = "🔴 Practice Stack — Issues Detected"
    elif has_warnings:
        color = EMBED_COLORS["status_warn"]
        title = "🟡 Practice Stack — Attention Needed"
    else:
        color = EMBED_COLORS["status_ok"]
        title = "🟢 Practice Stack — All Healthy"

    embed = discord.Embed(title=title, color=color, timestamp=now)
    embed.add_field(name="Services", value="\n".join(services_lines), inline=False)
    embed.add_field(name="Connections", value="\n".join(connections_lines), inline=False)
    embed.add_field(name="Sync", value="\n".join(sync_lines), inline=False)
    embed.add_field(name="Practice Flow", value="\n".join(practice_lines), inline=False)
    embed.add_field(name="Reachability", value="\n".join(reach_lines), inline=False)

    if actions:
        embed.add_field(name="Suggested Actions", value="\n".join(f"→ {a}" for a in actions), inline=False)

    embed.set_footer(text="!diagnose checks all 5 layers of the practice stack")
    await message.reply(embed=embed, mention_author=False)


async def cmd_help(message):
    embed = discord.Embed(title="\U0001f422 Turtle Commands",
                          description="Direct commands bypass the LLM — instant and free.",
                          color=EMBED_COLORS["help"])
    practice_cmds = [
        ("`!recall`", "Practice state overview — start of session"),
        ("`!release`", "Close session, write reflection — end of session"),
        ("`!sweep`", "Process boom into bright (triage + update)"),
        ("`!boom`", "Show boom buffer"),
        ("`!boom add <thought>`", "Capture a thought"),
        ("`!boom convert`", "Distill conversation into boom entries"),
        ("`!boom thread`", "Capture thread essence to boom (in thread or `!boom thread <name>`)"),
        ("`!bright`", "Show bright surface"),
        ("`!compass`", "Show life compass"),
        ("`!intentions`", "List active intentions"),
    ]
    file_cmds = [
        ("`!ls [dir]`", "Browse practice files"),
        ("`!read <file>`", "View a file (e.g. `!read intentions/turtle.md`)"),
        ("`!search <query>`", "Search across all practice files"),
        ("`!edit boom clear`", "Clear boom buffer"),
        ("`!edit bright append <text>`", "Add item to bright"),
        ("`!edit bright section <name> <text>`", "Add section to bright"),
        ("`!edit compass set <text>`", "Set compass content"),
        ("`!edit intention <name> <text>`", "Create/update intention"),
    ]
    thread_cmds = [
        ("`!thread \"topic\" [--model M] [--type T]`", "Create focused thread (types: fast/slow/confluence/standing)"),
        ("`!threads`", "List active threads with eddy types"),
        ("`!thread-type <type>`", "Change thread's eddy type (in thread)"),
        ("`!eddy-check`", "Scan threads for dissolution readiness"),
        ("`!absorb <name>`", "Bring thread resonance into main channel"),
        ("`!absorbed`", "Show absorbed thread contexts"),
        ("`!forget [name]`", "Release absorbed context (all or one)"),
    ]
    fetch_cmds = [
        ("`!fetch <url>`", "Fetch & distill a URL's resonance"),
        ("`!fetch <url> --fresh`", "Refetch (ignore cache)"),
    ]
    infra_cmds = [
        ("`!status`", "System dashboard"),
        ("`!readiness`", "Full 8-dimension practice-readiness assessment"),
        ("`!signals`", "Review, approve, or dismiss outfacing signal drafts"),
        ("`!sync`", "Practice state freshness"),
        ("`!diagnose`", "Full stack health check — services, sync, reachability"),
    ]
    embed.add_field(name="Practice", value="\n".join(f"{c} — {d}" for c, d in practice_cmds), inline=False)
    embed.add_field(name="Files", value="\n".join(f"{c} — {d}" for c, d in file_cmds), inline=False)
    embed.add_field(name="Threads", value="\n".join(f"{c} — {d}" for c, d in thread_cmds), inline=False)
    embed.add_field(name="Links", value="\n".join(f"{c} — {d}" for c, d in fetch_cmds), inline=False)
    embed.add_field(name="Infrastructure", value="\n".join(f"{c} — {d}" for c, d in infra_cmds), inline=False)
    models_str = ", ".join(f"`{k}`" for k in KNOWN_MODELS.keys())
    embed.add_field(name="Dialogue", value=f"Base: `{DIALOGUE_MODEL}` ({'API' if USE_API else 'local'})\nModels: {models_str}\nAttunement: `raw`, `semi`, `deep`", inline=False)
    await message.reply(embed=embed, mention_author=False)


async def cmd_thread(message, args):
    """Create a configured thread: !thread "topic" [--model M] [--attunement L]"""
    if isinstance(message.channel, discord.Thread):
        await message.reply("Use `!thread` in a main channel, not inside a thread.", mention_author=False)
        return
    if not is_practice_channel(message):
        await message.reply("Use `!thread` in your practice channel to create threads.", mention_author=False)
        return

    raw = " ".join(args) if args else ""
    topic_match = re.search(r'"([^"]+)"', raw)
    topic = topic_match.group(1) if topic_match else (raw.split("--")[0].strip() or "thread")

    model_match = re.search(r'--model\s+(\S+)', raw)
    model_str = model_match.group(1) if model_match else "local"

    attunement_match = re.search(r'--attunement\s+(\S+)', raw)
    attunement = attunement_match.group(1) if attunement_match else "semi"
    if attunement not in ATTUNEMENT_LEVELS:
        await message.reply(f"Unknown attunement `{attunement}`. Use: {', '.join(sorted(ATTUNEMENT_LEVELS))}", mention_author=False)
        return

    type_match = re.search(r'--type\s+(\S+)', raw)
    eddy_type = type_match.group(1) if type_match else EDDY_DEFAULT
    if eddy_type not in EDDY_TYPES:
        await message.reply(f"Unknown eddy type `{eddy_type}`. Use: {', '.join(sorted(EDDY_TYPES))}", mention_author=False)
        return

    model_id, use_api = resolve_model(model_str)

    thread = await message.create_thread(name=topic)

    # Auto-add practitioners to thread
    parent_id = message.channel.id
    for uid in get_thread_member_ids(parent_id):
        try:
            user = await client.fetch_user(int(uid))
            await thread.add_user(user)
        except Exception as e:
            print(f"Could not auto-add user {uid} to thread: {e}")

    thread_configs[thread.id] = {
        "model": model_id,
        "use_api": use_api,
        "attunement": attunement,
        "model_label": model_str,
        "eddy_type": eddy_type,
        "created": datetime.now(timezone.utc),
    }

    eddy_info = EDDY_TYPES[eddy_type]
    config_line = f"Model: `{model_id}` ({'API' if use_api else 'local'}) | Attunement: `{attunement}` | {eddy_info['emoji']} `{eddy_type}`"
    await thread.send(f"\U0001f9f5 {config_line}", view=ThreadTypeView(thread.id))
    print(f"Thread created: {topic} (id: {thread.id}, model: {model_id}, attunement: {attunement}, eddy: {eddy_type})")
    await log_activity(f"Thread created: **{topic}** (`{model_str}` / `{attunement}` / `{eddy_type}`)", "\U0001f9f5", channel=thread)


async def cmd_boom_thread(message, args):
    target_channel = None

    if isinstance(message.channel, discord.Thread):
        target_channel = message.channel
    elif args:
        name = " ".join(args).strip().lower()
        source = message.channel
        if isinstance(source, discord.Thread):
            source = source.parent
        if source and hasattr(source, "threads"):
            for t in source.threads:
                if t.name.lower() == name or str(t.id) == name:
                    target_channel = t
                    break
        if not target_channel:
            await message.reply(f"Thread `{name}` not found. Try `!threads` to see active threads.", mention_author=False)
            return
    else:
        await message.reply("Usage: `!boom thread` (from inside a thread) or `!boom thread <name>` (from main channel)", mention_author=False)
        return

    msgs = []
    async for m in target_channel.history(limit=50, oldest_first=True):
        if m.author == client.user or not m.author.bot:
            role = "Mage" if not m.author.bot else "Spirit"
            msgs.append(f"{role}: {m.content[:300]}")

    if len(msgs) < 2:
        await message.reply("Not enough conversation in this thread to capture.", mention_author=False)
        return

    conversation = "\n".join(msgs)
    distill_prompt = (
        f"This is a Discord thread called \"{target_channel.name}\". "
        "Extract the key insights, ideas, or decisions worth remembering. "
        "Write each as a boom entry: one line, starting with \"- \". "
        "Prefix each with the thread name in bold for context. "
        "Output ONLY entries, nothing else. If nothing worth capturing: output exactly (nothing to capture)"
    )

    async with message.channel.typing():
        try:
            result = await chat_ollama(
                distill_prompt,
                [{"role": "user", "content": conversation}],
                model=REFLECTION_MODEL, num_ctx=8192,
            )
            if not result or "(nothing to capture)" in result.lower():
                await message.reply(f"Nothing worth capturing from **{target_channel.name}**.", mention_author=False)
                return

            boom_path = os.path.join(get_pd(), "boom.md")
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            with open(boom_path, "a") as f:
                f.write(f"\n\n## Thread: {target_channel.name} ({timestamp})\n{result}\n")

            entry_count = sum(1 for line in result.split("\n") if line.strip().startswith("- "))
            embed = discord.Embed(
                title=f"\U0001f4a5 Boomed from \"{target_channel.name}\" ({entry_count} entries)",
                description=truncate(result, 1800),
                color=EMBED_COLORS["boom"],
            )
            embed.set_footer(text="Spirit reads these during next boom sweep")
            await message.reply(embed=embed, mention_author=False)
            await log_activity(f"Boomed thread **{target_channel.name}** ({entry_count} entries)", "\U0001f4a5", channel=message.channel)
        except Exception as e:
            await message.reply(f"Boom thread failed: {e}", mention_author=False)


async def cmd_thread_type(message, args):
    if not isinstance(message.channel, discord.Thread):
        await message.reply("Use `!thread-type` inside a thread.", mention_author=False)
        return
    if not args:
        cfg = thread_configs.get(message.channel.id, {})
        current = cfg.get("eddy_type", EDDY_DEFAULT)
        info = EDDY_TYPES[current]
        types_list = " / ".join(f"`{k}` ({v['emoji']} {v['days'] or '∞'}d)" for k, v in EDDY_TYPES.items())
        await message.reply(
            f"Current type: {info['emoji']} **{info['label']}** (`{current}`)\n"
            f"Available: {types_list}\n"
            f"Usage: `!thread-type slow`",
            mention_author=False,
        )
        return
    new_type = args[0].lower()
    if new_type not in EDDY_TYPES:
        await message.reply(f"Unknown type `{new_type}`. Use: {', '.join(sorted(EDDY_TYPES))}", mention_author=False)
        return
    cfg = thread_configs.get(message.channel.id)
    if cfg:
        old_type = cfg.get("eddy_type", EDDY_DEFAULT)
        cfg["eddy_type"] = new_type
    else:
        old_type = EDDY_DEFAULT
        thread_configs[message.channel.id] = {
            "model": None, "use_api": False, "attunement": "semi",
            "model_label": "local", "eddy_type": new_type,
            "created": message.channel.created_at or datetime.now(timezone.utc),
        }
    info = EDDY_TYPES[new_type]
    old_info = EDDY_TYPES[old_type]
    days_str = f"{info['days']}d" if info['days'] else "∞"
    await message.reply(
        f"{old_info['emoji']} → {info['emoji']} Thread type changed to **{info['label']}** (dissolves after {days_str} quiet)",
        mention_author=False,
    )
    await log_activity(f"Thread **{message.channel.name}** type: `{old_type}` → `{new_type}`", info['emoji'], channel=message.channel)


# ─── Views ───────────────────────────────────────────────────────

class ThreadTypeView(discord.ui.View):
    def __init__(self, thread_id: int):
        super().__init__(timeout=3600)
        self.thread_id = thread_id
        for child in self.children:
            child.custom_id = f"{child.custom_id}:{thread_id}"

    async def _set_type(self, interaction: discord.Interaction, new_type: str):
        cfg = thread_configs.get(self.thread_id)
        if cfg:
            cfg["eddy_type"] = new_type
        info = EDDY_TYPES[new_type]
        await interaction.response.send_message(
            f"{info['emoji']} Thread type → **{info['label']}** ({info['days'] or '∞'}d)",
            ephemeral=False,
        )
        for child in self.children:
            child.disabled = True
        try:
            await interaction.message.edit(view=self)
        except Exception:
            pass

    @discord.ui.button(label="⚡ Fast (3d)", custom_id="ttype:fast", style=discord.ButtonStyle.secondary)
    async def fast_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._set_type(interaction, "fast")

    @discord.ui.button(label="🌀 Slow (14d)", custom_id="ttype:slow", style=discord.ButtonStyle.secondary)
    async def slow_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._set_type(interaction, "slow")

    @discord.ui.button(label="🔀 Confluence (7d)", custom_id="ttype:confluence", style=discord.ButtonStyle.secondary)
    async def confluence_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._set_type(interaction, "confluence")

    @discord.ui.button(label="🌊 Standing (∞)", custom_id="ttype:standing", style=discord.ButtonStyle.primary)
    async def standing_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._set_type(interaction, "standing")


class EddyDissolutionView(discord.ui.View):
    def __init__(self, thread_id: int, thread_name: str):
        super().__init__(timeout=86400)
        self.thread_id = thread_id
        self.thread_name = thread_name
        for child in self.children:
            child.custom_id = f"{child.custom_id}:{thread_id}"

    @discord.ui.button(label="Archive & Capture", custom_id="eddy:archive", style=discord.ButtonStyle.primary, emoji="📦")
    async def archive_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=False)
        thread = client.get_channel(self.thread_id)
        if not thread:
            await interaction.followup.send("Thread no longer accessible.", ephemeral=True)
            return

        msgs = []
        async for m in thread.history(limit=50, oldest_first=True):
            if m.author == client.user or not m.author.bot:
                role = "Mage" if not m.author.bot else "Spirit"
                msgs.append(f"{role}: {m.content[:300]}")

        essence = ""
        if len(msgs) >= 2:
            conversation = "\n".join(msgs)
            try:
                result = await chat_ollama(
                    f"This thread \"{self.thread_name}\" is being archived. "
                    "Extract the essential insights worth keeping. Write as boom entries (- prefix). "
                    "If nothing worth keeping: output (nothing to capture)",
                    [{"role": "user", "content": conversation}],
                    model=REFLECTION_MODEL, num_ctx=8192,
                )
                if result and "(nothing to capture)" not in result.lower():
                    essence = result
                    boom_path = os.path.join(get_pd(), "boom.md")
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
                    with open(boom_path, "a") as f:
                        f.write(f"\n\n## Thread dissolved: {self.thread_name} ({timestamp})\n{essence}\n")
            except Exception as e:
                print(f"Essence capture failed for {self.thread_name}: {e}")

        archive_dir = Path(get_pd()) / "thread-archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        safe_name = re.sub(r'[^\w-]', '_', self.thread_name.lower())
        archive_path = archive_dir / f"{today}_{safe_name}.md"
        archive_content = f"# Thread Archive: {self.thread_name}\n\n"
        archive_content += f"**Archived:** {today}\n"
        archive_content += f"**Messages:** {len(msgs)}\n\n"
        if essence:
            archive_content += f"## Essence\n{essence}\n\n"
        archive_content += "## Conversation\n" + "\n".join(msgs[-20:]) + "\n"
        archive_path.write_text(archive_content)

        threads_flagged_for_release.pop(self.thread_id, None)
        thread_configs.pop(self.thread_id, None)

        try:
            await thread.edit(archived=True)
        except Exception:
            pass

        entry_count = sum(1 for line in essence.split("\n") if line.strip().startswith("- ")) if essence else 0
        summary = f"📦 **{self.thread_name}** archived"
        if entry_count:
            summary += f" ��� {entry_count} entries captured to boom"
        await interaction.followup.send(summary)
        dialogue = get_channel("dialogue")
        print(f"Thread dissolved & archived: {self.thread_name} ({entry_count} boom entries)")  # 016 reroute: internal only

        for child in self.children:
            child.disabled = True
        try:
            await interaction.message.edit(view=self)
        except Exception:
            pass

    @discord.ui.button(label="Keep Spinning", custom_id="eddy:keep", style=discord.ButtonStyle.secondary, emoji="\U0001f504")
    async def keep_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        threads_flagged_for_release.pop(self.thread_id, None)
        cfg = thread_configs.get(self.thread_id)
        if cfg:
            cfg["created"] = datetime.now(timezone.utc)
        await interaction.response.send_message(
            f"\U0001f504 **{self.thread_name}** unflagged — timer reset. Thread keeps spinning.",
            ephemeral=False,
        )
        for child in self.children:
            child.disabled = True
        try:
            await interaction.message.edit(view=self)
        except Exception:
            pass

    @discord.ui.button(label="Make Standing Wave", custom_id="eddy:standing", style=discord.ButtonStyle.success, emoji="\U0001f30a")
    async def standing_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        threads_flagged_for_release.pop(self.thread_id, None)
        cfg = thread_configs.get(self.thread_id)
        if cfg:
            cfg["eddy_type"] = "standing"
        else:
            thread_configs[self.thread_id] = {
                "model": None, "use_api": False, "attunement": "semi",
                "model_label": "local", "eddy_type": "standing",
                "created": datetime.now(timezone.utc),
            }
        await interaction.response.send_message(
            f"🌊 **{self.thread_name}** upgraded to **Standing Wave** — never dissolves automatically.",
            ephemeral=False,
        )
        await log_activity(f"Thread **{self.thread_name}** → standing wave", "🌊", channel=interaction.channel)
        for child in self.children:
            child.disabled = True
        try:
            await interaction.message.edit(view=self)
        except Exception:
            pass


async def eddy_dissolution_check():
    now = datetime.now(timezone.utc)
    newly_flagged = []

    for tid, cfg in list(thread_configs.items()):
        eddy_type = cfg.get("eddy_type", EDDY_DEFAULT)
        threshold_days = EDDY_TYPES.get(eddy_type, {}).get("days")
        if threshold_days is None:
            continue
        if tid in threads_flagged_for_release:
            continue

        thread = client.get_channel(tid)
        if not thread:
            continue

        last_activity = cfg.get("created", now)
        session = active_sessions.get(tid)
        if session and session.get("last_message"):
            last_activity = max(last_activity, session["last_message"])

        try:
            async for msg in thread.history(limit=1):
                if msg.created_at > last_activity:
                    last_activity = msg.created_at
        except Exception:
            pass

        quiet_days = (now - last_activity).total_seconds() / 86400
        if quiet_days >= threshold_days:
            threads_flagged_for_release[tid] = {
                "flagged_at": now,
                "reason": f"Quiet for {int(quiet_days)}d (threshold: {threshold_days}d for {eddy_type})",
                "thread_name": thread.name,
            }
            newly_flagged.append(thread.name)

            parent = thread.parent or get_channel("dialogue")
            if parent:
                eddy_info = EDDY_TYPES[eddy_type]
                embed = discord.Embed(
                    title=f"{eddy_info['emoji']} Thread ready to dissolve",
                    description=(
                        f"**{thread.name}** has been quiet for **{int(quiet_days)}d** "
                        f"(type: {eddy_info['label']}, threshold: {threshold_days}d)\n\n"
                        "What should happen with this thread?"
                    ),
                    color=0xFFA500,
                )
                view = EddyDissolutionView(tid, thread.name)
                await parent.send(embed=embed, view=view)

    return newly_flagged


async def cmd_eddy_check(message, args):
    async with message.channel.typing():
        flagged = await eddy_dissolution_check()
    if flagged:
        await message.reply(
            f"🌀 Flagged {len(flagged)} thread(s) for dissolution: {', '.join(f'**{n}**' for n in flagged)}",
            mention_author=False,
        )
    else:
        await message.reply("✅ No threads ready for dissolution.", mention_author=False)


# ─── Link Fetching ───────────────────────────────────────────────

def _resonance_cache_dir():
    return os.path.join(get_pd(), "link-resonance")


def _get_cached_resonance(url: str) -> str | None:
    import hashlib
    cache_dir = _resonance_cache_dir()
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
    path = os.path.join(cache_dir, f"{url_hash}.md")
    if os.path.exists(path):
        try:
            with open(path) as f:
                return f.read()
        except Exception:
            pass
    return None


def _cache_resonance(url: str, resonance: str, title: str = ""):
    import hashlib
    cache_dir = _resonance_cache_dir()
    os.makedirs(cache_dir, exist_ok=True)
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
    path = os.path.join(cache_dir, f"{url_hash}.md")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    content = f"# {title or url}\n\n**URL:** {url}\n**Cached:** {now}\n\n---\n\n{resonance}\n"
    try:
        with open(path, "w") as f:
            f.write(content)
    except Exception as e:
        print(f"Resonance cache write failed for {url}: {e}")


async def _distill_resonance(raw_content: str, url: str) -> str:
    prompt = (
        "Distill this web content into its essential resonance. "
        "Extract the key insights, claims, or ideas worth remembering. "
        "Write concisely — bullet points or short paragraphs. "
        "If it's a tweet, preserve the voice. If it's an article, capture the argument. "
        "If it's a page with little content, say so. "
        "Output ONLY the distilled resonance, nothing else."
    )
    try:
        result = await chat_ollama(
            prompt,
            [{"role": "user", "content": f"URL: {url}\n\nContent:\n{raw_content[:6000]}"}],
            model=REFLECTION_MODEL, num_ctx=8192,
        )
        return result.strip() if result else raw_content[:2000]
    except Exception:
        return raw_content[:2000]


class LinkFetchView(discord.ui.View):
    def __init__(self, urls: list[str]):
        super().__init__(timeout=3600)
        self.urls = urls[:3]
        for i, url in enumerate(self.urls):
            btn = discord.ui.Button(
                label=f"Fetch {urlparse(url).netloc}"[:40],
                custom_id=f"fetch:{i}:{hash(url) % 100000}",
                style=discord.ButtonStyle.secondary,
                emoji="\U0001f517",
                row=i,
            )
            btn.callback = self._make_callback(url)
            self.add_item(btn)

    def _make_callback(self, url: str):
        async def callback(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=False)

            cached = _get_cached_resonance(url)
            if cached:
                lines = cached.split("\n")
                title = lines[0].lstrip("# ").strip() if lines else url
                embed = discord.Embed(
                    title=f"\U0001f517 {title}",
                    description=truncate("\n".join(lines[5:]), 2000),
                    color=0x3498DB,
                )
                embed.set_footer(text="Cached resonance")
                await interaction.followup.send(embed=embed)
                return

            raw_content, source_type = None, None
            platform = _detect_platform(url)
            if platform == "twitter":
                raw_content, source_type = await _fetch_twitter(url)
            elif platform == "youtube":
                raw_content, source_type = await _fetch_youtube_transcript(url)
            if not raw_content:
                raw_content, source_type = await _fetch_url_content(url)

            if not raw_content:
                await interaction.followup.send(
                    f"\U0001f517 Could not fetch `{url}` ({source_type}). "
                    "Share a screenshot or paste the text directly."
                )
                return

            litl_hits = _litl_check(raw_content)
            if litl_hits:
                await interaction.followup.send(
                    f"⚠️ Content from `{url}` contains instruction-like patterns. "
                    "Presenting with caution."
                )

            resonance = await _distill_resonance(raw_content, url)
            _cache_resonance(url, resonance, title=url)

            embed = discord.Embed(
                title=f"\U0001f517 {url}",
                description=truncate(resonance, 2000),
                color=0x3498DB,
            )
            embed.set_footer(text=f"Fetched via {source_type or 'direct'} • !fetch <url> to refetch")
            await interaction.followup.send(embed=embed)

            for child in self.children:
                child.disabled = True
            try:
                await interaction.message.edit(view=self)
            except Exception:
                pass

        return callback


async def cmd_fetch(message, args):
    if not args:
        await message.reply(
            "Usage: `!fetch <url>` — fetch and distill a URL's resonance\n"
            "Copy-paste friendly: `!fetch https://example.com/article`",
            mention_author=False,
        )
        return

    url = args[0].strip("<>")
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        await message.reply(f"Not a valid URL: `{url}`", mention_author=False)
        return

    cached = _get_cached_resonance(url)
    if cached:
        lines = cached.split("\n")
        title = lines[0].lstrip("# ").strip() if lines else url
        embed = discord.Embed(
            title=f"\U0001f517 {title}",
            description=truncate("\n".join(lines[5:]), 2000),
            color=0x3498DB,
        )
        embed.set_footer(text="Cached resonance • add --fresh to refetch")
        await message.reply(embed=embed, mention_author=False)
        if "--fresh" not in " ".join(args):
            return

    async with message.channel.typing():
        raw_content, source_type = None, None
        platform = _detect_platform(url)
        if platform == "twitter":
            raw_content, source_type = await _fetch_twitter(url)
        elif platform == "youtube":
            raw_content, source_type = await _fetch_youtube_transcript(url)
        if not raw_content:
            raw_content, source_type = await _fetch_url_content(url)

        if not raw_content:
            await message.reply(
                f"\U0001f517 Could not fetch `{url}` ({source_type}).\n"
                "Try: screenshot it, paste the text, or share via a different link.",
                mention_author=False,
            )
            return

        litl_hits = _litl_check(raw_content)
        if litl_hits:
            await message.reply(
                f"⚠️ Content from `{url}` contains instruction-like patterns ({len(litl_hits)} hits). "
                "Presenting with caution.",
                mention_author=False,
            )

        resonance = await _distill_resonance(raw_content, url)
        _cache_resonance(url, resonance, title=url)

    embed = discord.Embed(
        title=f"\U0001f517 {url}",
        description=truncate(resonance, 2000),
        color=0x3498DB,
    )
    embed.set_footer(text=f"Fetched via {source_type or 'direct'} • resonance cached")
    await message.reply(embed=embed, mention_author=False)


async def cmd_threads(message, args):
    source = message.channel
    if isinstance(source, discord.Thread):
        source = source.parent
    all_threads = []

    if source and hasattr(source, "threads"):
        for t in source.threads:
            cfg = thread_configs.get(t.id)
            age = datetime.now(timezone.utc) - (cfg["created"] if cfg else t.created_at)
            if age.total_seconds() >= 86400:
                age_str = f"{int(age.total_seconds() / 86400)}d"
            elif age.total_seconds() >= 3600:
                age_str = f"{int(age.total_seconds() / 3600)}h"
            else:
                age_str = f"{int(age.total_seconds() / 60)}m"
            eddy_type = cfg.get("eddy_type", EDDY_DEFAULT) if cfg else EDDY_DEFAULT
            eddy_info = EDDY_TYPES[eddy_type]
            flagged = " ⚠️" if t.id in threads_flagged_for_release else ""
            if cfg:
                all_threads.append(
                    f"{eddy_info['emoji']} **{t.name}** — `{cfg['model_label']}` / `{cfg['attunement']}` ({age_str}){flagged}"
                )
            else:
                all_threads.append(f"{eddy_info['emoji']} **{t.name}** — unconfigured ({age_str}){flagged}")

    if not all_threads:
        await message.reply("No active threads. Use `!thread \"topic\"` to create one.", mention_author=False)
        # Context injection for no-threads case too (016)
        history = get_history(message.channel.id)
        history.append({"role": "user", "content": "!threads"})
        history.append({"role": "assistant", "content": "[System: No active threads.]"})
        return

    embed = discord.Embed(
        title=f"\U0001f9f5 Active Threads ({len(all_threads)})",
        description="\n".join(all_threads),
        color=EMBED_COLORS["help"],
    )
    embed.set_footer(text="!thread-type <type> to change | !eddy-check to scan for dissolution")
    await message.reply(embed=embed, mention_author=False)

    # Context injection: give Turtle the actual thread data (016 nervous system principle)
    thread_summary = "Active threads:\n" + "\n".join(all_threads)
    history = get_history(message.channel.id)
    history.append({"role": "user", "content": "!threads"})
    history.append({"role": "assistant", "content": f"[System: {thread_summary}]"})


async def cmd_read(message, args):
    if not args:
        await message.reply(
            "Usage: `!read <file>`\n"
            "Examples: `!read bright.md`, `!read intentions/turtle.md`, `!read sessions/2026-03-16.md`\n"
            "Use `!ls` to browse available files.",
            mention_author=False,
        )
        return

    filename = args[0]
    if not filename.endswith(".md"):
        filename += ".md"

    if not is_readable(filename):
        await message.reply(f"Cannot read `{filename}`. Use `!ls` to see available files.", mention_author=False)
        return

    path = os.path.join(get_pd(), filename)
    content = read_safe(path)
    if not content.strip():
        await message.reply(f"`{filename}` is empty.", mention_author=False)
        return

    link = obsidian_link(filename)
    if len(content) <= 1800:
        await message.reply(f"{link}\n```md\n{content}\n```", mention_author=False)
    elif len(content) <= 6000:
        await message.reply(link, mention_author=False)
        for chunk in split_message(f"```md\n{content}\n```", limit=1900):
            await message.reply(chunk, mention_author=False)
    else:
        preview = content[:1500]
        lines = content.count("\n") + 1
        await message.reply(
            f"{link} ({lines} lines, {len(content)} chars) — showing first ~50 lines:\n"
            f"```md\n{preview}\n```\n"
            f"*File too long for Discord. Use `!search <term>` or ask Spirit to summarize.*",
            mention_author=False,
        )


async def cmd_ls(message, args):
    directory = args[0] if args else ""
    target = os.path.join(get_pd(), directory) if directory else get_pd()

    if not os.path.isdir(target):
        await message.reply(f"Directory `{directory}` not found.", mention_author=False)
        return

    lines = []
    for item in sorted(os.listdir(target)):
        full = os.path.join(target, item)
        if item.startswith("."):
            continue
        if os.path.isdir(full):
            count = len([f for f in os.listdir(full) if f.endswith(".md")])
            lines.append(f"  `{item}/` — {count} files")
        elif item.endswith(".md"):
            size = os.path.getsize(full)
            age = datetime.now().timestamp() - os.path.getmtime(full)
            if age < 3600:
                age_str = f"{int(age / 60)}m ago"
            elif age < 86400:
                age_str = f"{int(age / 3600)}h ago"
            else:
                age_str = f"{int(age / 86400)}d ago"
            filepath = f"{directory}/{item}" if directory else item
            link = obsidian_link(filepath)
            lines.append(f"  {link} — {size}b, {age_str}")

    if not lines:
        await message.reply(f"`{directory or 'practice/'}` is empty.", mention_author=False)
        return

    header = f"**{directory + '/' if directory else 'practice/'}**"
    await message.reply(f"{header}\n" + "\n".join(lines), mention_author=False)


async def cmd_sweep(message):
    boom_path = os.path.join(get_pd(), "boom.md")
    bright_path = os.path.join(get_pd(), "bright.md")
    boom = read_safe(boom_path)
    bright = read_safe(bright_path)
    compass = read_safe(os.path.join(get_pd(), "compass.md"))

    if not boom.strip():
        await message.reply("Boom is empty — nothing to sweep.", mention_author=False)
        return

    item_count = count_items(boom)
    await message.reply(f"Sweeping {item_count} boom items...", mention_author=False)

    sweep_prompt = f"""You are Spirit sweeping the Mage's boom buffer. For each item, decide:

- **bright** — belongs on the bright surface (active, worth tracking)
- **release** — served its purpose, can be cleared
- **box** — interesting but not active; note essence and release

For each item, output ONE line: `[ACTION] original item text | optional note`

Then output a BRIGHT UPDATE — the additions/modifications to make to the bright surface.
Place items under the right section (Actions/Craft, Seeds, Reflections, Conceptual Tensions, etc.)
Do NOT reproduce existing bright items, only additions.

Format:
---TRIAGE---
[bright] item text | note
[release] item text
[box] item text | essence to keep
---END_TRIAGE---

---BRIGHT_ADDITIONS---
(markdown to append to bright.md, with proper section headers)
---END_BRIGHT_ADDITIONS---

COMPASS (for alignment):
{compass[:1500] if compass else '(none)'}

CURRENT BRIGHT (for deduplication):
{summarize_bright(bright)}

BOOM TO SWEEP:
{boom}"""

    async with message.channel.typing():
        try:
            result = await chat_ollama(
                read_safe(os.path.join(IDENTITY_DIR, "soul.md")),
                [{"role": "user", "content": sweep_prompt}],
                model=REFLECTION_MODEL, num_ctx=8192,
            )

            if not result or "---TRIAGE---" not in result:
                await message.reply("Sweep failed — model didn't produce structured output. Try again.", mention_author=False)
                return

            triage_text = result.split("---TRIAGE---")[1].split("---END_TRIAGE---")[0].strip()

            bright_additions = ""
            if "---BRIGHT_ADDITIONS---" in result and "---END_BRIGHT_ADDITIONS---" in result:
                bright_additions = result.split("---BRIGHT_ADDITIONS---")[1].split("---END_BRIGHT_ADDITIONS---")[0].strip()

            counts = {"bright": 0, "release": 0, "box": 0}
            for line in triage_text.split("\n"):
                for action in counts:
                    if line.strip().lower().startswith(f"[{action}]"):
                        counts[action] += 1

            if bright_additions:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
                with open(bright_path, "a") as f:
                    f.write(f"\n\n<!-- swept {timestamp} -->\n{bright_additions}\n")

            with open(boom_path, "w") as f:
                f.write(f"# Boom\n> Swept {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")

            embed = discord.Embed(
                title=f"Boom swept ({item_count} items)",
                color=EMBED_COLORS["boom"],
            )
            embed.add_field(
                name="Triage",
                value=f"Bright: **{counts['bright']}** | Released: **{counts['release']}** | Boxed: **{counts['box']}**",
                inline=False,
            )
            if bright_additions:
                preview = bright_additions[:500] + "..." if len(bright_additions) > 500 else bright_additions
                embed.add_field(name="Added to bright", value=preview, inline=False)
            embed.add_field(name="Triage detail", value=truncate(triage_text, 800), inline=False)
            embed.set_footer(text="Review with !bright or open in Obsidian | Boom cleared")
            await message.reply(embed=embed, mention_author=False)

        except Exception as e:
            await message.reply(f"Sweep error: {type(e).__name__}: {e}", mention_author=False)


async def cmd_recall(message):
    boom = read_safe(os.path.join(get_pd(), "boom.md"))
    bright = read_safe(os.path.join(get_pd(), "bright.md"))
    compass = read_safe(os.path.join(get_pd(), "compass.md"))

    boom_count = count_items(boom)
    bright_count = count_items(bright)
    intentions = load_intentions_list()

    sdir = os.path.join(get_pd(), "sessions")
    last_sessions = []
    if os.path.isdir(sdir):
        recent = sorted([f for f in os.listdir(sdir) if f.endswith(".md")], reverse=True)[:3]
        for fname in recent:
            content = read_safe(os.path.join(sdir, fname))
            if content.strip():
                summary = content.strip().split("\n")[0][:120]
                last_sessions.append(f"`{fname.replace('.md','')}` — {summary}")

    pdir = os.path.join(get_pd(), "proposals")
    proposals = []
    if os.path.isdir(pdir):
        pfiles = sorted([f for f in os.listdir(pdir) if f.endswith(".md")], reverse=True)[:3]
        for fname in pfiles:
            content = read_safe(os.path.join(pdir, fname))
            title = content.strip().split("\n")[0][:100] if content.strip() else fname
            proposals.append(f"`{fname.replace('.md','')}` — {title}")

    embed = discord.Embed(title="Practice Recall", color=0x9B59B6, timestamp=datetime.now(timezone.utc))
    embed.add_field(name="Compass", value=compass[:300] + "..." if len(compass) > 300 else (compass or "(none)"), inline=False)
    embed.add_field(name="Practice State", value=(
        f"Boom: **{boom_count}** items | Bright: **{bright_count}** items\n"
        f"Intentions: {', '.join(intentions) if intentions else '(none)'}"
    ), inline=False)

    if last_sessions:
        embed.add_field(name="Recent Sessions", value="\n".join(last_sessions), inline=False)
    if proposals:
        embed.add_field(name="Pending Proposals", value="\n".join(proposals), inline=False)

    freshness_lines = []
    any_stale = False
    for fname in ["boom.md", "bright.md", "compass.md"]:
        fpath = os.path.join(get_pd(), fname)
        if os.path.isfile(fpath):
            age = datetime.now().timestamp() - os.path.getmtime(fpath)
            if age < 3600:
                age_str = f"{int(age / 60)}m"
            elif age < 86400:
                age_str = f"{int(age / 3600)}h"
            else:
                age_str = f"{int(age / 86400)}d"
                any_stale = True
            freshness_lines.append(f"`{fname}`: {age_str}")
        else:
            freshness_lines.append(f"`{fname}`: missing")
            any_stale = True
    # 016 reroute: only surface freshness when something is stale — silence when healthy
    if any_stale:
        embed.add_field(name="Freshness ⚠️", value=" | ".join(freshness_lines), inline=False)
    embed.set_footer(text="!bright for details | !boom to see buffer | !sweep to process")
    await message.reply(embed=embed, mention_author=False)


async def cmd_release(message):
    channel_id = message.channel.id
    history = get_history(channel_id)
    if len(history) < 2:
        await message.reply("Not enough conversation to release. Just go — rest well.", mention_author=False)
        return

    await message.reply("Closing session...", mention_author=False)
    from sessions import close_session
    await close_session(channel_id)

    dialogue_histories.pop(channel_id, None)
    active_sessions.pop(channel_id, None)

    embed = discord.Embed(title="Session Released", color=0x2ECC71)
    embed.description = "Session note written. Conversation history cleared.\nRest well, Kermit."

    boom = read_safe(os.path.join(get_pd(), "boom.md"))
    boom_count = count_items(boom)
    if boom_count > 0:
        embed.add_field(name="Note", value=f"Boom has **{boom_count}** items. Consider `!sweep` before you go.", inline=False)

    await message.reply(embed=embed, mention_author=False)


async def cmd_edit(message, args):
    if not args:
        await message.reply(
            "Usage:\n"
            "`!edit boom clear` — clear boom\n"
            "`!edit bright append <text>` — append to bright\n"
            "`!edit bright section <name> <text>` — add under a section\n"
            "`!edit compass set <text>` — replace compass\n"
            "`!edit intention <name> <text>` — create/replace an intention",
            mention_author=False,
        )
        return

    target = args[0].lower()
    action = args[1].lower() if len(args) > 1 else ""
    content = " ".join(args[2:]) if len(args) > 2 else ""

    if target == "boom":
        if action == "clear":
            boom_path = os.path.join(get_pd(), "boom.md")
            with open(boom_path, "w") as f:
                f.write(f"# Boom\n> Cleared {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
            await message.add_reaction("\u2705")
            await message.reply(f"Boom cleared. {obsidian_link('boom.md')}", mention_author=False)
        else:
            await message.reply("Use `!edit boom clear` or `!boom add <thought>`", mention_author=False)

    elif target == "bright":
        bright_path = os.path.join(get_pd(), "bright.md")
        if action == "append" and content:
            with open(bright_path, "a") as f:
                f.write(f"\n- {content}\n")
            await message.add_reaction("\u2728")
            await message.reply(f"Added to bright: `- {content}` {obsidian_link('bright.md')}", mention_author=False)
        elif action == "section" and content:
            parts = content.split(" ", 1)
            section_name = parts[0]
            section_content = parts[1] if len(parts) > 1 else ""
            with open(bright_path, "a") as f:
                f.write(f"\n\n### {section_name}\n- {section_content}\n")
            await message.add_reaction("\u2728")
            await message.reply(f"Section '{section_name}' added to bright. {obsidian_link('bright.md')}", mention_author=False)
        else:
            await message.reply("Use `!edit bright append <text>` or `!edit bright section <name> <text>`", mention_author=False)

    elif target == "compass":
        if action == "set" and content:
            compass_path = os.path.join(get_pd(), "compass.md")
            with open(compass_path, "w") as f:
                f.write(content + "\n")
            await message.add_reaction("\U0001f9ed")
            await message.reply(f"Compass updated. {obsidian_link('compass.md')}", mention_author=False)
        else:
            await message.reply("Use `!edit compass set <full compass text>`", mention_author=False)

    elif target == "intention":
        if not content:
            await message.reply("Use `!edit intention <name> <content>`", mention_author=False)
            return
        name = action
        idir = os.path.join(get_pd(), "intentions")
        os.makedirs(idir, exist_ok=True)
        ipath = os.path.join(idir, f"{name}.md")
        with open(ipath, "w") as f:
            f.write(content + "\n")
        await message.add_reaction("\U0001f3af")
        await message.reply(f"Intention `{name}` written. {obsidian_link(f'intentions/{name}.md')}", mention_author=False)

    else:
        await message.reply("Unknown target. Use: `boom`, `bright`, `compass`, `intention`", mention_author=False)


async def cmd_search(message, args):
    if not args:
        await message.reply("Usage: `!search <query>`\nSearches across all practice files for matching text.", mention_author=False)
        return
    query = " ".join(args)
    result = execute_tos_tool("search_practice_files", {"query": query})
    if len(result) <= 1900:
        await message.reply(result, mention_author=False)
    else:
        for chunk in split_message(result, limit=1900):
            await message.reply(chunk, mention_author=False)


async def cmd_absorb(message, args):
    dialogue = get_channel("dialogue")
    if not dialogue:
        await message.reply("No dialogue channel configured.", mention_author=False)
        return

    main_id = dialogue.id
    if isinstance(message.channel, discord.Thread):
        main_id = message.channel.parent_id

    if not args:
        return await cmd_absorbed(message, [])

    name = " ".join(args).strip().strip('"').lower()
    target_thread = None
    for t in dialogue.threads:
        if t.name.lower() == name or str(t.id) == name:
            target_thread = t
            break

    if not target_thread:
        await message.reply(f"Thread `{name}` not found. Try `!threads` to see active threads.", mention_author=False)
        return

    cfg = thread_configs.get(target_thread.id)
    model_info = f" [{cfg['model_label']} / {cfg['attunement']}]" if cfg else ""

    state = read_thread_state(target_thread.name)
    if state:
        digest = f"In the \"{target_thread.name}\" thread{model_info}:\n{state}"
        if main_id not in absorbed_contexts:
            absorbed_contexts[main_id] = []
        existing = [a for a in absorbed_contexts[main_id] if a["name"] != target_thread.name]
        existing.append({
            "name": target_thread.name,
            "digest": digest,
            "absorbed_at": datetime.now(timezone.utc),
            "model_info": model_info,
        })
        absorbed_contexts[main_id] = existing
        count = len(absorbed_contexts[main_id])
        embed = discord.Embed(
            title=f"🌀 Absorbed \"{target_thread.name}\" (from state file — instant)",
            description=truncate(digest, 1800),
            color=EMBED_COLORS.get("help", 0x2ECC71),
        )
        embed.set_footer(text=f"{count} thread(s) in context. Use !absorbed to list, !forget to clear.")
        await message.reply(embed=embed, mention_author=False)
        await log_activity(f"Absorbed thread **{target_thread.name}** (instant, from state file)", "🌀", channel=message.channel)
        return

    msgs = []
    async for m in target_thread.history(limit=50, oldest_first=True):
        if m.author == client.user or not m.author.bot:
            role = "Mage" if not m.author.bot else "Spirit"
            msgs.append(f"{role}: {m.content[:500]}")

    if len(msgs) < 2:
        await message.reply("Not enough conversation in this thread to absorb.", mention_author=False)
        return

    conversation = "\n".join(msgs)

    digest_prompt = (
        f"Distill this Discord thread \"{target_thread.name}\"{model_info} into a compact context digest. "
        "Capture: key ideas discussed, positions taken, insights reached, open questions, "
        "and the emotional/intellectual tone. Write as a dense paragraph or two — "
        "this will be injected into another conversation as background context. "
        "Write in present tense. Start with 'In the \"{name}\" thread:'"
    )

    async with message.channel.typing():
        try:
            digest = await chat_ollama(
                digest_prompt,
                [{"role": "user", "content": conversation}],
                model=REFLECTION_MODEL, num_ctx=8192,
            )
            if not digest:
                await message.reply("Failed to generate digest.", mention_author=False)
                return

            if main_id not in absorbed_contexts:
                absorbed_contexts[main_id] = []

            existing = [a for a in absorbed_contexts[main_id] if a["name"] != target_thread.name]
            existing.append({
                "name": target_thread.name,
                "digest": digest,
                "absorbed_at": datetime.now(timezone.utc),
                "model_info": model_info,
            })
            absorbed_contexts[main_id] = existing

            count = len(absorbed_contexts[main_id])
            embed = discord.Embed(
                title=f"\U0001f300 Absorbed \"{target_thread.name}\"",
                description=truncate(digest, 1800),
                color=EMBED_COLORS.get("help", 0x2ECC71),
            )
            embed.set_footer(text=f"{count} thread(s) in context. Use !absorbed to list, !forget to clear.")
            await message.reply(embed=embed, mention_author=False)
            await log_activity(f"Absorbed thread **{target_thread.name}** into main channel", "\U0001f300", channel=message.channel)
        except Exception as e:
            await message.reply(f"Absorb failed: {e}", mention_author=False)


async def cmd_absorbed(message, args):
    dialogue = get_channel("dialogue")
    main_id = dialogue.id if dialogue else message.channel.id
    if isinstance(message.channel, discord.Thread):
        main_id = message.channel.parent_id

    contexts = absorbed_contexts.get(main_id, [])
    if not contexts:
        await message.reply(
            "No absorbed threads. Use `!absorb <thread-name>` to bring a thread's resonance into the main channel.",
            mention_author=False,
        )
        return

    lines = []
    for ctx in contexts:
        age = datetime.now(timezone.utc) - ctx["absorbed_at"]
        age_str = f"{int(age.total_seconds() / 60)}m" if age.total_seconds() < 3600 else f"{int(age.total_seconds() / 3600)}h"
        preview = ctx["digest"][:120].replace("\n", " ")
        lines.append(f"**{ctx['name']}**{ctx.get('model_info', '')} ({age_str} ago)\n> {preview}...")

    embed = discord.Embed(
        title=f"\U0001f300 Absorbed Context ({len(contexts)} threads)",
        description="\n\n".join(lines),
        color=EMBED_COLORS.get("help", 0x2ECC71),
    )
    embed.set_footer(text="Spirit sees these when responding in the main channel. !forget to clear.")
    await message.reply(embed=embed, mention_author=False)


async def cmd_forget(message, args):
    dialogue = get_channel("dialogue")
    main_id = dialogue.id if dialogue else message.channel.id
    if isinstance(message.channel, discord.Thread):
        main_id = message.channel.parent_id

    if args:
        name = " ".join(args).strip().strip('"').lower()
        contexts = absorbed_contexts.get(main_id, [])
        before = len(contexts)
        absorbed_contexts[main_id] = [c for c in contexts if c["name"].lower() != name]
        after = len(absorbed_contexts.get(main_id, []))
        if after < before:
            await message.reply(f"\U0001f300 Released **{name}** from context. {after} thread(s) remaining.", mention_author=False)
        else:
            await message.reply(f"Thread `{name}` not found in absorbed context.", mention_author=False)
    else:
        count = len(absorbed_contexts.get(main_id, []))
        absorbed_contexts[main_id] = []
        await message.reply(f"\U0001f300 Cleared all absorbed context ({count} threads).", mention_author=False)


async def cmd_readiness(message):
    set_practice_context(message)
    result = assess_readiness()
    embed = discord.Embed(
        title="🧭 Practice-Readiness Assessment",
        description=result["summary"],
        color=0x2ECC71 if not result["highest_leverage"] else
              (0xE67E22 if result["highest_leverage"]["status"] == "degraded" else 0xE74C3C),
    )
    embed.set_footer(text=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
    await message.reply(embed=embed, mention_author=False)
    save_readiness_trail(result)


# ─── Admin Commands ──────────────────────────────────────────────

async def cmd_admin(message, args):
    """Server seneschal commands — infrastructure management."""
    if not args:
        await message.reply(
            "**Seneschal Commands:**\n"
            "- `!admin status` — server overview\n"
            "- `!admin channels` — channel topology with permissions\n"
            "- `!admin members` — server membership\n"
            "- `!admin audit` — permission health check\n"
            "- `!admin onboard <username>` — create practice space for new mage\n",
            mention_author=False
        )
        return

    subcmd = args[0].lower()

    if subcmd == "status":
        guild = message.guild
        channels = guild.channels
        members = guild.members
        roles = guild.roles
        text_channels = [c for c in channels if isinstance(c, discord.TextChannel)]
        forum_channels = [c for c in channels if isinstance(c, discord.ForumChannel)]
        threads = []
        for c in text_channels:
            threads.extend(c.threads)
        await message.reply(
            f"**Server: {guild.name}**\n"
            f"Members: {len(members)} | Roles: {len(roles)}\n"
            f"Text channels: {len(text_channels)} | Forums: {len(forum_channels)} | Active threads: {len(threads)}\n"
            f"Owner: {guild.owner}\n"
            f"Seneschal: {guild.me.display_name} (Administrator: {guild.me.guild_permissions.administrator})",
            mention_author=False
        )

    elif subcmd == "channels":
        guild = message.guild
        lines = []
        for ch in sorted(guild.channels, key=lambda c: c.position):
            if isinstance(ch, discord.CategoryChannel):
                lines.append(f"\n**{ch.name}**")
                continue
            ch_type = "text" if isinstance(ch, discord.TextChannel) else "forum" if isinstance(ch, discord.ForumChannel) else str(ch.type)
            overwrites = ch.overwrites
            if overwrites:
                perm_parts = []
                for target_role, ow in overwrites.items():
                    name = target_role.name if hasattr(target_role, "name") else str(target_role)
                    pair = ow.pair()
                    if pair[1].view_channel:
                        perm_parts.append(f"{name}: \u274c view")
                    elif pair[0].view_channel:
                        perm_parts.append(f"{name}: \u2705 view")
                perm_str = " | ".join(perm_parts)
                lines.append(f"  `#{ch.name}` ({ch_type}) — {perm_str}")
            else:
                lines.append(f"  `#{ch.name}` ({ch_type}) — inherits")
        await message.reply("\n".join(lines) or "(no channels)", mention_author=False)

    elif subcmd == "members":
        guild = message.guild
        lines = []
        for m in guild.members:
            role_names = [r.name for r in m.roles if r.name != "@everyone"]
            bot_tag = " \U0001f916" if m.bot else ""
            lines.append(f"- **{m.display_name}** ({m.name}){bot_tag} — {', '.join(role_names) if role_names else 'no roles'}")
        await message.reply("\n".join(lines) or "(no members)", mention_author=False)

    elif subcmd == "audit":
        guild = message.guild
        audit_issues = []
        registry = get_registry()

        for ch_id, mage_key_val in registry.get("channels", {}).items():
            ch = guild.get_channel(int(ch_id))
            if not ch:
                audit_issues.append(f"\u26a0\ufe0f Registry channel `{ch_id}` ({mage_key_val}) not found in server")
                continue
            mage = registry.get("mages", {}).get(mage_key_val, {})
            if mage and mage.get("discord_id"):
                overwrites = ch.overwrites
                everyone_role = guild.default_role
                if everyone_role not in overwrites or overwrites[everyone_role].pair()[1].view_channel is not True:
                    audit_issues.append(f"\u26a0\ufe0f `#{ch.name}` — @everyone can view (should be private for {mage_key_val})")
                else:
                    mage_member = guild.get_member(int(mage.get("discord_id")))
                    if mage_member and mage_member not in overwrites:
                        audit_issues.append(f"\u26a0\ufe0f `#{ch.name}` — {mage_key_val} has no explicit access")

        registered_ids = set(registry.get("channels", {}).keys())
        for ch in guild.text_channels:
            if str(ch.id) not in registered_ids:
                audit_issues.append(f"\u2139\ufe0f `#{ch.name}` — not in mage registry")

        if audit_issues:
            await message.reply("**Permission Audit:**\n" + "\n".join(audit_issues), mention_author=False)
        else:
            await message.reply("**Permission Audit:** All clear. Channel permissions match registry.", mention_author=False)

    elif subcmd == "onboard" and len(args) > 1:
        username = args[1]
        guild = message.guild

        target_member = None
        for m in guild.members:
            if m.name == username or m.display_name.lower() == username.lower():
                target_member = m
                break
        if not target_member:
            await message.reply(f"Member `{username}` not found on server.", mention_author=False)
            return

        channel_name = f"{username.lower()}-dialogue"
        existing = discord.utils.get(guild.text_channels, name=channel_name)
        if existing:
            await message.reply(f"Channel `#{channel_name}` already exists.", mention_author=False)
            return

        category = discord.utils.get(guild.categories, name="Practice")

        everyone_role = guild.default_role
        turtle_role = guild.me.top_role
        overwrites = {
            everyone_role: discord.PermissionOverwrite(view_channel=False),
            target_member: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True,
                create_public_threads=True, send_messages_in_threads=True
            ),
            turtle_role: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True,
                send_messages_in_threads=True
            ),
        }
        new_ch = await guild.create_text_channel(
            channel_name, category=category, overwrites=overwrites,
            topic=f"Private practice space for {target_member.display_name}"
        )

        import yaml
        registry_path = os.path.expanduser("~/turtle-shell/mage_registry.yaml")
        with open(registry_path) as f:
            reg = yaml.safe_load(f) or {}
        if "mages" not in reg:
            reg["mages"] = {}
        if "channels" not in reg:
            reg["channels"] = {}
        mage_key_val = username.lower()
        reg["mages"][mage_key_val] = {
            "discord_id": str(target_member.id),
            "address": target_member.display_name,
            "practice_dir": f"~/workshops/{mage_key_val}"
        }
        reg["channels"][str(new_ch.id)] = mage_key_val
        with open(registry_path, "w") as f:
            yaml.dump(reg, f, default_flow_style=False, allow_unicode=True)
        reload_mage_registry()

        workshop = os.path.expanduser(f"~/workshops/{mage_key_val}")
        os.makedirs(os.path.join(workshop, "sessions"), exist_ok=True)
        os.makedirs(os.path.join(workshop, "intentions"), exist_ok=True)
        os.makedirs(os.path.join(workshop, "proposals"), exist_ok=True)
        os.makedirs(os.path.join(workshop, "thread-state"), exist_ok=True)
        for fname in ("compass.md", "boom.md", "bright.md", "mirror.md"):
            fpath = os.path.join(workshop, fname)
            if not os.path.exists(fpath):
                open(fpath, "w").close()
        template = os.path.expanduser("~/workshops/nesrine/system.md")
        dest = os.path.join(workshop, "system.md")
        if os.path.exists(template) and not os.path.exists(dest):
            import shutil
            shutil.copy2(template, dest)

        await message.reply(
            f"**Onboarding complete for {target_member.display_name}:**\n"
            f"- Channel: `#{channel_name}` (private, sovereign)\n"
            f"- Workshop: `~/workshops/{mage_key_val}/`\n"
            f"- Registry: updated\n"
            f"They can start talking to Turtle in their channel now.",
            mention_author=False
        )
        await log_activity(
            f"Onboarded **{target_member.display_name}** — `#{channel_name}` created, workshop initialized", "\U0001f331", channel=message.channel
        )

    else:
        await message.reply(f"Unknown admin command: `{subcmd}`. Try `!admin` for help.", mention_author=False)


# ─── Command Dispatch ────────────────────────────────────────────


async def cmd_signals(message, args):
    """List, approve, or dismiss outfacing signal drafts."""
    import discord as _discord
    from pathlib import Path as _Path
    from practice_io import read_safe as _read_safe

    signals_dir = _Path(get_pd()) / "outfacing" / "drafts" / "signals"
    if not signals_dir.exists():
        await message.reply("No signal drafts yet.", mention_author=False)
        return

    drafts = sorted(signals_dir.glob("*.md"), reverse=True)
    if not drafts:
        await message.reply("No signal drafts pending.", mention_author=False)
        return

    if args and args[0].lower() == "approve":
        # Approve a specific draft: !signals approve <filename>
        if len(args) < 2:
            await message.reply("Usage: `!signals approve <filename>`", mention_author=False)
            return
        target = args[1]
        match = None
        for d in drafts:
            if target in d.name:
                match = d
                break
        if not match:
            await message.reply(f"No draft matching `{target}`", mention_author=False)
            return

        content_text = _read_safe(str(match))
        # Extract the draft text
        draft_text = ""
        in_draft = False
        for line in content_text.split("\n"):
            if line.strip() == "## Draft":
                in_draft = True
                continue
            elif line.strip().startswith("## ") and in_draft:
                break
            elif in_draft:
                draft_text += line + "\n"
        draft_text = draft_text.strip()

        if not draft_text:
            await message.reply("Could not extract draft text.", mention_author=False)
            return

        # Post to Twitter
        try:
            import subprocess
            result = subprocess.run(
                ["/Users/turtle/turtle-shell/venv/bin/python3",
                 "/Users/turtle/turtle-shell/twitter_ops.py",
                 "post", draft_text],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                posted_dir = signals_dir.parent / "posted"
                posted_dir.mkdir(parents=True, exist_ok=True)
                match.rename(posted_dir / match.name)
                output = result.stdout.strip()
                await message.reply(f"Posted. {output}", mention_author=False)
                await log_activity(f"Signal posted to X: `{match.name}`", "\U0001f4e1", channel=message.channel)
            else:
                await message.reply(f"Twitter post failed: {result.stderr[:200]}", mention_author=False)
        except Exception as e:
            await message.reply(f"Post failed: {e}", mention_author=False)
        return

    if args and args[0].lower() == "dismiss":
        if len(args) < 2:
            await message.reply("Usage: `!signals dismiss <filename>`", mention_author=False)
            return
        target = args[1]
        for d in drafts:
            if target in d.name:
                d.unlink()
                await message.reply(f"Dismissed `{d.name}`", mention_author=False)
                return
        await message.reply(f"No draft matching `{target}`", mention_author=False)
        return

    # Default: list drafts
    embed = _discord.Embed(title="\U0001f4e1 Signal Drafts", color=0x3498DB)
    for d in drafts[:10]:
        content_text = _read_safe(str(d))
        # Extract draft text for preview
        draft_preview = ""
        in_draft = False
        for line in content_text.split("\n"):
            if line.strip() == "## Draft":
                in_draft = True
                continue
            elif line.strip().startswith("## ") and in_draft:
                break
            elif in_draft and line.strip():
                draft_preview = line.strip()[:200]
                break
        sig_type = ""
        for line in content_text.split("\n"):
            if line.startswith("**Type:**"):
                sig_type = line.replace("**Type:**", "").strip()
                break
        label = f"{sig_type} -- {d.stem}" if sig_type else d.stem
        embed.add_field(name=label, value=draft_preview or "(empty)", inline=False)

    embed.set_footer(text="!signals approve <name> | !signals dismiss <name>")
    await message.reply(embed=embed, mention_author=False)




async def cmd_attune(message):
    """Turtle's self-attunement ritual -- read lore, integrate, write digest."""
    embed = discord.Embed(
        title="Attunement Ritual",
        description="Reading practice lore and integrating understanding...",
        color=EMBED_COLORS.get("sync", 0x1ABC9C),
    )
    status_msg = await message.reply(embed=embed, mention_author=False)

    digest, scroll_count, error = await perform_attunement()

    if error:
        embed = discord.Embed(
            title="Attunement Failed",
            description=f"Could not complete attunement: {error}",
            color=EMBED_COLORS.get("status_error", 0xE74C3C),
        )
        await status_msg.edit(embed=embed)
        return

    # Show completion
    digest_lines = digest.split("\n")
    preview_lines = digest_lines[:8]
    digest_preview = "\n".join(preview_lines)
    if len(digest_lines) > 8:
        digest_preview += "\n..."
    embed = discord.Embed(
        title="Attunement Complete",
        description=f"Read {scroll_count} scrolls. Digest written to identity.",
        color=EMBED_COLORS.get("status_ok", 0x2ECC71),
    )
    embed.add_field(name="Digest Preview", value=digest_preview[:1000], inline=False)
    await status_msg.edit(embed=embed)
    await log_activity(f"Self-attunement ritual completed ({scroll_count} scrolls)", "\U0001f52e", channel=message.channel)


DIRECT_COMMANDS = {
    "status": lambda msg, args: cmd_status(msg),
    "boom": lambda msg, args: cmd_boom_convert(msg) if args and args[0].lower() == "convert" else (cmd_boom_thread(msg, args[1:]) if args and args[0].lower() == "thread" else cmd_boom(msg, args)),
    "bright": lambda msg, args: cmd_bright(msg),
    "compass": lambda msg, args: cmd_compass(msg),
    "intentions": lambda msg, args: cmd_intentions(msg),
    "read": lambda msg, args: cmd_read(msg, args),
    "ls": lambda msg, args: cmd_ls(msg, args),
    "search": lambda msg, args: cmd_search(msg, args),
    "sync": lambda msg, args: cmd_sync(msg),
    "sweep": lambda msg, args: cmd_sweep(msg),
    "recall": lambda msg, args: cmd_recall(msg),
    "release": lambda msg, args: cmd_release(msg),
    "edit": lambda msg, args: cmd_edit(msg, args),
    "thread": lambda msg, args: cmd_thread(msg, args),
    "threads": lambda msg, args: cmd_threads(msg, args),
    "thread-type": lambda msg, args: cmd_thread_type(msg, args),
    "eddy-check": lambda msg, args: cmd_eddy_check(msg, args),
    "fetch": lambda msg, args: cmd_fetch(msg, args),
    "absorb": lambda msg, args: cmd_absorb(msg, args),
    "absorbed": lambda msg, args: cmd_absorbed(msg, args),
    "forget": lambda msg, args: cmd_forget(msg, args),
    "readiness": lambda msg, args: cmd_readiness(msg),
    "diagnose": lambda msg, args: cmd_diagnose(msg),
    "panel": lambda msg, args: cmd_panel(msg),
    "help": lambda msg, args: cmd_help(msg),
    "admin": lambda msg, args: cmd_admin(msg, args),
    "signals": lambda msg, args: cmd_signals(msg, args),
    "attune": lambda msg, args: cmd_attune(msg),
}

COMMAND_CONTEXT = {
    "status": "I displayed the practice status embed (boom count, bright count, compass, intentions, session age).",
    "diagnose": "I ran a full practice stack diagnostic — checked services, connections, sync, practice flow, and reachability. The results were shown as a color-coded embed.",
    # "boom" — handled directly in cmd_boom with actual content (016)
    # "bright" — handled directly in cmd_bright with actual content (016)
    "compass": "I showed the compass.",
    "intentions": "I showed the active intentions.",
    "sync": "I displayed the sync status.",
    "sweep": "I ran a boom sweep — processing boom items into bright/release/box.",
    # "threads" — handled directly in cmd_threads with actual thread data (016)
    "thread-type": "I changed the thread's eddy type (fast/slow/confluence/standing).",
    "eddy-check": "I scanned all threads for dissolution readiness and flagged any that exceeded their quiet threshold.",
    "fetch": "I fetched a URL and distilled its resonance — the essential insights from the linked content.",
    "recall": "I performed a recall — loaded practice state and recent sessions.",
    "release": "I ran a session release — wrote reflection and cleared history.",
    "readiness": "I ran a full practice-readiness assessment across all 8 dimensions.",
    "signals": "I showed the outfacing signal drafts -- Turtle-generated content awaiting Mage curation.",
    "attune": "I performed a self-attunement ritual -- read core practice lore, integrated understanding, and wrote a fresh attunement digest.",
}


_PRACTITIONER_COMMANDS = {"status", "help", "recall", "release"}


async def try_direct_command(message):
    text = message.content.strip()
    if not text.startswith("!"):
        return False
    parts = text[1:].split(None, 1)
    cmd = parts[0].lower() if parts else ""
    args = parts[1].split() if len(parts) > 1 else []
    # Practitioners only get a minimal command set; everything else falls through to dialogue
    if get_mage_type() == "practitioner" and cmd not in _PRACTITIONER_COMMANDS:
        return False
    handler = DIRECT_COMMANDS.get(cmd)
    if handler:
        try:
            await handler(message, args)
        except Exception as e:
            await message.reply(f"Command error: {e}", mention_author=False)
            await log_activity(f"Command `!{cmd}` failed: {e}", "\u274c", channel=message.channel)
        ctx_note = COMMAND_CONTEXT.get(cmd)
        if ctx_note:
            channel_id = message.channel.id
            history = get_history(channel_id)
            history.append({"role": "user", "content": f"!{cmd}"})
            history.append({"role": "assistant", "content": f"[System: {ctx_note}]"})
        return True
    return False


# ─── Control Panel ───────────────────────────────────────────────

class _InteractionAsMessage:
    def __init__(self, interaction: discord.Interaction):
        self._interaction = interaction
        self.channel = interaction.channel
        self.author = interaction.user
        self.content = ""
        self.id = interaction.id
        self.guild = interaction.guild

    async def reply(self, content=None, *, embed=None, mention_author=False, **kwargs):
        send_kwargs = {}
        if content:
            send_kwargs["content"] = content
        if embed:
            send_kwargs["embed"] = embed
        if send_kwargs:
            await self.channel.send(**send_kwargs)

    async def add_reaction(self, emoji):
        pass


class ThreadTopicModal(discord.ui.Modal, title="New Thread"):
    topic = discord.ui.TextInput(
        label="Topic",
        placeholder="e.g. philosophy, book-outline, session-prep",
        max_length=100,
    )

    def __init__(self, model_str: str, attunement: str, eddy_type: str = EDDY_DEFAULT):
        super().__init__()
        self.model_str = model_str
        self.attunement = attunement
        self.eddy_type = eddy_type

    async def on_submit(self, interaction: discord.Interaction):
        dialogue = get_channel("dialogue")
        if not dialogue:
            await interaction.response.send_message("No dialogue channel configured.", ephemeral=True)
            return

        topic_val = self.topic.value.strip() or "thread"
        model_id, use_api = resolve_model(self.model_str)

        msg = await dialogue.send(f"\U0001f9f5 **{topic_val}** \u2014 `{self.model_str}` / `{self.attunement}`")
        thread = await msg.create_thread(name=topic_val)

        # Auto-add practitioners to thread
        parent_id = dialogue.id
        for uid in get_thread_member_ids(parent_id):
            try:
                user = await client.fetch_user(int(uid))
                await thread.add_user(user)
            except Exception as e:
                print(f"Could not auto-add user {uid} to thread: {e}")

        eddy_type = getattr(self, "eddy_type", EDDY_DEFAULT)
        thread_configs[thread.id] = {
            "model": model_id,
            "use_api": use_api,
            "attunement": self.attunement,
            "model_label": self.model_str,
            "eddy_type": eddy_type,
            "created": datetime.now(timezone.utc),
        }

        eddy_info = EDDY_TYPES[eddy_type]
        config_line = f"Model: `{model_id}` ({'API' if use_api else 'local'}) | Attunement: `{self.attunement}` | {eddy_info['emoji']} `{eddy_type}`"
        await thread.send(f"\U0001f9f5 {config_line}", view=ThreadTypeView(thread.id))
        await interaction.response.send_message(
            f"Thread **{topic_val}** created (`{self.model_str}` / `{self.attunement}` / `{eddy_type}`).",
            ephemeral=True,
        )
        print(f"Thread created via panel: {topic_val} (model: {model_id}, attunement: {self.attunement}, eddy: {eddy_type})")
        await log_activity(f"Thread created: **{topic_val}** (`{self.model_str}` / `{self.attunement}` / `{eddy_type}`)", "\U0001f9f5", channel=thread)


class ControlPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        custom_id="panel:model",
        placeholder="Model: claude (default)",
        min_values=1, max_values=1,
        options=[
            discord.SelectOption(label="claude", description="Flagship API (claude-sonnet-4-6)", value="claude", default=True),
            discord.SelectOption(label="qwen", description="Local 9b, free", value="qwen"),
            discord.SelectOption(label="qwen-4b", description="Local 4b, fast", value="qwen-4b"),
        ],
        row=0,
    )
    async def model_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        uid = interaction.user.id
        panel_selections.setdefault(uid, {"model": "claude", "attunement": "deep"})
        panel_selections[uid]["model"] = select.values[0]
        await interaction.response.send_message(
            f"Model set to **{select.values[0]}** for next thread.", ephemeral=True
        )

    @discord.ui.select(
        custom_id="panel:attunement",
        placeholder="Attunement: deep (default)",
        min_values=1, max_values=1,
        options=[
            discord.SelectOption(label="deep", description="Full practice context + soul", value="deep", default=True),
            discord.SelectOption(label="semi", description="Discord prompt + behavioral guidance", value="semi"),
            discord.SelectOption(label="raw", description="Minimal — soul + direct", value="raw"),
        ],
        row=1,
    )
    async def attunement_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        uid = interaction.user.id
        panel_selections.setdefault(uid, {"model": "claude", "attunement": "deep"})
        panel_selections[uid]["attunement"] = select.values[0]
        await interaction.response.send_message(
            f"Attunement set to **{select.values[0]}** for next thread.", ephemeral=True
        )

    @discord.ui.button(label="New Thread", custom_id="panel:new_thread", style=discord.ButtonStyle.primary, row=2)
    async def new_thread_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        sel = panel_selections.get(uid, {"model": "claude", "attunement": "deep"})
        eddy = panel_selections.get(uid, {}).get("eddy_type", EDDY_DEFAULT)
        modal = ThreadTopicModal(model_str=sel["model"], attunement=sel["attunement"], eddy_type=eddy)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Eddy Check", custom_id="panel:eddy_check", style=discord.ButtonStyle.secondary, row=2)
    async def eddy_check_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=False)
        flagged = await eddy_dissolution_check()
        if flagged:
            await interaction.followup.send(
                f"🌀 Flagged {len(flagged)} thread(s): {', '.join(f'**{n}**' for n in flagged)}"
            )
        else:
            await interaction.followup.send("✅ No threads ready for dissolution.")

    @discord.ui.button(label="Status", custom_id="panel:status", style=discord.ButtonStyle.secondary, row=3)
    async def status_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await cmd_status(_InteractionAsMessage(interaction))

    @discord.ui.button(label="Diagnose", custom_id="panel:diagnose", style=discord.ButtonStyle.secondary, row=3)
    async def diagnose_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await cmd_diagnose(_InteractionAsMessage(interaction))

    @discord.ui.button(label="Boom", custom_id="panel:boom", style=discord.ButtonStyle.secondary, row=3)
    async def boom_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await cmd_boom(_InteractionAsMessage(interaction), [])

    @discord.ui.button(label="Sweep", custom_id="panel:sweep", style=discord.ButtonStyle.secondary, row=3)
    async def sweep_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await cmd_sweep(_InteractionAsMessage(interaction))

    @discord.ui.button(label="Recall", custom_id="panel:recall", style=discord.ButtonStyle.success, row=4)
    async def recall_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await cmd_recall(_InteractionAsMessage(interaction))

    @discord.ui.button(label="Release", custom_id="panel:release", style=discord.ButtonStyle.danger, row=4)
    async def release_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await cmd_release(_InteractionAsMessage(interaction))


async def cmd_panel(message):
    embed = discord.Embed(
        title="\U0001f3ae Spirit Control Panel",
        description=(
            "**Threads** \u2014 pick model + attunement, then tap New Thread.\n"
            "**Practice** \u2014 quick access to status, diagnostics, boom, sweep.\n"
            "**Session** \u2014 recall to orient, release to close."
        ),
        color=0x5865F2,
    )
    view = ControlPanelView()
    await message.channel.send(embed=embed, view=view)

