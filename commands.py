"""turtleOS commands — platform palette, deferred legacy handlers, dispatch."""

import asyncio
import json
import os
import re
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse

import discord

from state import (
    client, CHANNELS, OPS_EMBED_COLOR, SPIRIT_BOT_ID, EMBED_COLORS,
    get_channel,
    IDENTITY_DIR, OLLAMA_URL, DIALOGUE_MODEL, REFLECTION_MODEL, USE_API,
    RIVER_MODEL, TURTLE_MODEL, TRIAGE_MODEL,
    EDIT_DELEGATE_MODEL,
    MAX_DIALOGUE_HISTORY, MAX_TOOL_ROUNDS,
    OBSIDIAN_VAULT, PRACTICE_WEB_BASE,
    dialogue_histories, active_sessions, _processed_messages,
    ATTUNEMENT_LEVELS, KNOWN_MODELS,
    thread_configs, absorbed_contexts,
    EDDY_TYPES, EDDY_DEFAULT, threads_flagged_for_release,
    MIN_EXCHANGES_FOR_CHECKPOINT,
    THREAD_CONTEXTS,
    panel_selections,
    GOOGLE_API_KEY, HAS_GEMINI,
)

from mage import (
    get_pd, get_runtime_dir, get_workshop_root, get_topology, get_mage_name, get_mage_key, get_mage_type,
    get_attunement_profile,
    set_practice_context, set_practice_context_for_channel,
    is_practice_channel, is_registered_parent_channel, is_river_message,
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
from sessions import post_command_act

from content_fetch import (
    extract_urls as _extract_urls,
    fetch_url_content as _fetch_url_content,
    litl_check as _litl_check,
    fetch_twitter as _fetch_twitter,
    fetch_youtube_transcript as _fetch_youtube_transcript,
    detect_platform as _detect_platform,
    process_urls as _process_urls,
)

from helpers import local_now, get_history, log_activity, split_message
from eddy_spawn import spawn_eddy, should_offer_eddy, generate_topic, make_eddy_spawn_view, post_thread_opening
from cmd_link_resonance import (
    cmd_fetch,
    fetch_act_digest,
    get_cached_resonance,
    cache_resonance,
    get_cached_resonance as _get_cached_resonance,
    cache_resonance as _cache_resonance,
)
from cmd_dispatch import (
    COMMAND_ACT_FALLBACK,
    CONTEXTUAL_ACTION_COMMANDS,
    CONTEXTUAL_ACTION_TIMEOUT,
    LIFECYCLE_BAR_COMMANDS,
    SENESCHAL_ACTION_COMMANDS,
    dispatch_direct_command,
    inject_act_digest,
    send_with_actions,
    try_direct_command,
)
from cmd_sessions import cmd_checkpoint, cmd_dissolve, cmd_release
from share_eddy import cmd_share
from cmd_practice_io import cmd_artifacts, cmd_export, cmd_ls, cmd_read, cmd_search
from cmd_threads import (
    ControlPanelView,
    EddyDissolutionView,
    ThreadConfigView,
    ThreadTypeView,
    build_config_line,
    build_config_line as _build_config_line,
    cmd_eddy_check,
    cmd_new,
    cmd_panel,
    cmd_rename,
    cmd_thread,
    cmd_thread_type,
    cmd_threads,
    eddy_dissolution_check,
)


# ─── Direct Commands ─────────────────────────────────────────────

async def _post_river_command_act(message, *, title: str, body: str, emoji: str = "📋") -> None:
    """Compact River act on parent channels — not Turtle multi-field panels."""
    await post_command_act(message.channel.id, title=title, body=body, emoji=emoji)


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

    sdir = os.path.join(get_pd(), "sessions")
    session_files = [f for f in os.listdir(sdir) if f.endswith(".md")] if os.path.isdir(sdir) else []
    if session_files:
        last_session = max(session_files, key=lambda f: os.path.getmtime(os.path.join(sdir, f))).replace(".md", "")
    else:
        last_session = "none"

    flows_dir = os.path.join(get_pd(), "flows")
    flow_files = (
        [f for f in os.listdir(flows_dir) if f.endswith(".md") or f.endswith(".flow.md")]
        if os.path.isdir(flows_dir)
        else []
    )

    active_count = sum(1 for s in active_sessions.values() if not s["closed"])

    practice = [
        f"Practice root: `{get_pd()}`",
        f"Session files: **{len(session_files)}** (last `{last_session}`)",
        f"Installed flows: **{len(flow_files)}**",
    ]
    digest = (
        f"{len(session_files)} sessions, {len(flow_files)} flows, "
        f"last session `{last_session}`, {active_count} active channel(s)"
    )

    if is_river_message(message):
        river_body = "\n".join([
            f"River `{RIVER_MODEL}` · Turtle `{TURTLE_MODEL}` · Ollama: {ollama_status}",
            f"Uptime {uptime} · {active_count} active session(s)",
            *practice,
        ])
        await _post_river_command_act(message, title="Status", body=river_body, emoji="🐢")
        return digest

    embed = discord.Embed(title="\U0001f422 Turtle Status", color=EMBED_COLORS["status_ok"], timestamp=now)
    embed.add_field(name="River", value=f"`{RIVER_MODEL}`\n(local)", inline=True)
    embed.add_field(name="Turtle", value=f"`{TURTLE_MODEL}`\n(local)", inline=True)
    embed.add_field(name="Background", value=f"triage `{TRIAGE_MODEL}`\nreflect `{REFLECTION_MODEL}`", inline=True)
    if USE_API or DIALOGUE_MODEL != TURTLE_MODEL:
        embed.add_field(
            name="Dialogue override",
            value=f"`{DIALOGUE_MODEL}`\n({'API' if USE_API else 'local'})",
            inline=True,
        )
    embed.add_field(name="Ollama", value=ollama_status, inline=True)
    embed.add_field(name="Uptime", value=uptime, inline=True)
    embed.add_field(name="Sessions", value=str(active_count), inline=True)
    embed.add_field(name="tOS", value="active" if os.path.isfile(os.path.join(get_pd(), "system.md")) else "missing", inline=True)
    embed.add_field(name="Practice root", value="\n".join(practice), inline=False)
    embed.set_footer(text="turtleOS shell")
    await message.reply(embed=embed, mention_author=False)
    return digest


async def cmd_diagnose(message):
    """Grounded mechanical diagnostic — displays the same checks canary.py runs."""
    import importlib.util

    now = datetime.now(timezone.utc)
    canary_path = Path(__file__).with_name("canary.py")

    if not canary_path.exists():
        embed = discord.Embed(
            title="🔴 Mechanical Diagnostic Unavailable",
            description=f"`{canary_path}` not found.",
            color=EMBED_COLORS["status_error"],
            timestamp=now,
        )
        await message.reply(embed=embed, mention_author=False)
        return

    try:
        spec = importlib.util.spec_from_file_location("turtle_canary", canary_path)
        canary = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(canary)
    except Exception as e:
        embed = discord.Embed(
            title="🔴 Mechanical Diagnostic Import Failed",
            description=f"`canary.py` could not be loaded: `{type(e).__name__}: {e}`",
            color=EMBED_COLORS["status_error"],
            timestamp=now,
        )
        await message.reply(embed=embed, mention_author=False)
        return

    results = []
    has_red = False
    has_yellow = False
    for check in canary.CHECKS:
        if len(check) == 4:
            layer, name, fn, weight = check
        else:
            layer, name, fn, weight = "legacy", check[0], check[1], check[2]
        try:
            status, detail = fn()
        except Exception as e:
            status, detail = "red", f"check raised: {type(e).__name__}: {e}"
        results.append({"layer": layer, "name": name, "status": status, "detail": detail, "weight": weight})
        if status == "red" and weight == "high":
            has_red = True
        elif status in ("red", "yellow"):
            has_yellow = True

    overall = "red" if has_red else ("yellow" if has_yellow else "green")
    green_count = sum(1 for r in results if r["status"] == "green")

    if overall == "red":
        color = EMBED_COLORS["status_error"]
        title = "🔴 Mechanical Diagnostic — Red"
    elif overall == "yellow":
        color = EMBED_COLORS["status_warn"]
        title = "🟡 Mechanical Diagnostic — Yellow"
    else:
        color = EMBED_COLORS["status_ok"]
        title = "🟢 Mechanical Diagnostic — Green"

    status_icon = {"green": "✅", "yellow": "⚠️", "red": "❌"}
    check_lines = [
        f"{status_icon.get(r['status'], '•')} `{r['name']}` — {r['detail']}"
        for r in results
    ]

    embed = discord.Embed(
        title=title,
        description=f"{green_count}/{len(results)} checks green. Grounded in `canary.py`.",
        color=color,
        timestamp=now,
    )
    embed.add_field(name="Checks", value=truncate("\n".join(check_lines), 3900), inline=False)

    topology = get_topology()
    topology_lines = [
        f"practice: `{topology['practice_dir']}`",
        f"runtime: `{topology['runtime_dir']}`",
    ]
    if topology.get("workshop_root"):
        topology_lines.append(f"workshop: `{topology['workshop_root']}`")
    embed.add_field(name="Topology", value="\n".join(topology_lines), inline=False)

    if overall != "green":
        degraded = [r for r in results if r["status"] != "green"]
        embed.add_field(
            name="Degraded Signature",
            value="\n".join(f"`{r['name']}`: {r['status']}" for r in degraded),
            inline=False,
        )

    embed.set_footer(text="!diagnose is a read-only view of canary.py; scheduled canary handles alerts")
    digest = f"{green_count}/{len(results)} checks green ({overall})"
    if is_river_message(message):
        river_body = f"{green_count}/{len(results)} checks green ({overall}).\n" + truncate(
            "\n".join(check_lines[:12]), 3500
        )
        await _post_river_command_act(
            message,
            title="Diagnostic",
            body=river_body,
            emoji="🩺" if overall == "green" else "⚠️",
        )
        return digest
    await message.reply(embed=embed, mention_author=False)
    return digest


def _river_help_body() -> str:
    """Compact parent-river command summary — full inventory lives in eddies."""
    mage_type = get_mage_type()
    lines = [
        "**River:** standing bar · `!pin` · `!dissolve`",
        "**Eddies:** `!checkpoint` · `!release` · `!flows` · `!share` · `!help` (full list)",
        "**Browse:** `!artifacts` · `!read` / `!ls` / `!search`",
        f"Models: River `{RIVER_MODEL}` · Turtle `{TURTLE_MODEL}`",
    ]
    if mage_type != "practitioner":
        lines.insert(3, "**Operator:** `!diagnose` · `!admin …`")
    lines.append("Open an eddy for the full command inventory.")
    return "\n".join(lines)


def _help_lines(pairs: list[tuple[str, str]]) -> str:
    return "\n".join(f"{cmd} — {desc}" for cmd, desc in pairs)


def _help_embed_fields() -> list[tuple[str, str]]:
    """Profile-aware turtle-talk sections. See docs/turtle-talk.md."""
    mage_type = get_mage_type()
    fields: list[tuple[str, str]] = []

    river_cmds = [
        ("**new eddy**", "Standing bar — open a blank eddy (TURTLE_SPEC §5.4)"),
        ("`!flows`", "In-eddy flow library — load a guided flow (`!flow` alias)"),
        ("`!pin`", "Pin a message — reply with `!pin` or `!pin <message_id>`"),
        ("`!dissolve`", "Archive eddy + chronicle (river or in-thread)"),
    ]
    fields.append(("River (parent channel)", _help_lines(river_cmds)))

    eddy_core = [
        ("`!checkpoint`", "Save resonance — flow state + session note; keeps history"),
        ("`!release`", "Close session — checkpoint, then clear history"),
        ("`!focus <topic>`", "Narrow this eddy to one thing (`!focus` to view, `!focus clear` to widen)"),
        ("`!dissolve`", "Archive eddy + chronicle — distinct from `!release`"),
        ("`!help`", "This inventory"),
        ("`!status`", "System + practice-root dashboard"),
        ("`!readiness`", "Substrate / practice-readiness check"),
        ("`!rename <title>`", "Exact eddy title (in thread)"),
        ("`!share`", "Send this eddy to another practitioner (digest + received eddy)"),
        ("`!fetch <url>`", "Distill URL to library (not auto link-read in chat)"),
        ("`!artifacts`", "Curated practice artifact shelves"),
        ("`!export <path>`", "Download allowlisted artifact as .md"),
        ("`!read` / `!ls` / `!search`", "Browse allowlisted practice artifacts"),
    ]
    fields.append(("Eddy core (v1)", _help_lines(eddy_core)))

    if mage_type == "practitioner":
        fields.append((
            "Note",
            "Other `!` commands fall through to dialogue. Full map: `docs/turtle-talk.md`.",
        ))
        return fields

    operator_cmds = [
        ("`!diagnose`", "Full stack health (canary view)"),
        ("`!admin …`", "Operator tools incl. `river-key`, `space` (§15.4)"),
    ]
    fields.append(("Operator", _help_lines(operator_cmds)))
    fields.append((
        "Deferred (Appendix A)",
        "Legacy thread/orchestration (`!thread`, `!panel`, absorb, …) — not default fluency. See `docs/turtle-talk.md`.",
    ))
    fields.append((
        "Inventory",
        "Full map: `docs/turtle-talk.md`. Magic workshop commands retired — use Forge for boom/compass/@ flows.",
    ))
    return fields


async def cmd_help(message):
    if is_river_message(message):
        body = _river_help_body()
        await _post_river_command_act(message, title="Commands", body=body, emoji="📋")
        return "River command summary posted (full inventory in eddies)."

    embed = discord.Embed(
        title="\U0001f422 Turtle Commands",
        description="Direct `!` commands bypass the LLM — instant and free. Layered per TURTLE_SPEC v1.",
        color=EMBED_COLORS["help"],
    )
    for name, body in _help_embed_fields():
        embed.add_field(name=name, value=truncate(body, 1020), inline=False)
    models_str = ", ".join(f"`{k}`" for k in KNOWN_MODELS.keys())
    embed.add_field(
        name="Models",
        value=(
            f"River `{RIVER_MODEL}` · Turtle `{TURTLE_MODEL}`\n"
            f"Overrides: {models_str}\n"
            f"API opt-in: `claude`, `gemini-*` via `--model` or `DIALOGUE_MODEL`"
        ),
        inline=False,
    )
    await message.reply(embed=embed, mention_author=False)
    return "Command inventory embed posted."


# ─── Practice browse → cmd_practice_io.py ────────────────────────


async def cmd_flows(message, args):
    """List installed flows — in-eddy flow library is the primary picker."""
    from flow_runner import list_resolvable_flow_ids, load_flow_spec

    if isinstance(message.channel, discord.Thread):
        if args:
            flow_id = args[0].strip()
            from eddy_flow_library import load_flow_in_eddy

            if not load_flow_spec(flow_id):
                await message.reply(
                    f"Flow `{flow_id}` not found. Run `!flows` to see installed flows.",
                    mention_author=False,
                )
                return
            spec = load_flow_spec(flow_id)
            ok = await load_flow_in_eddy(message.channel, flow_id, client)
            if not ok:
                await message.reply(
                    f"Could not load `{flow_id}` in this eddy.",
                    mention_author=False,
                )
                return
            title = spec.title if spec else flow_id
            await message.reply(
                f"Loaded **{title}** (`{flow_id}`) in this eddy.",
                mention_author=False,
            )
            return

        flows = list_resolvable_flow_ids()
        if not flows:
            await message.reply(
                "No flows installed under your practice root (`flows/`).",
                mention_author=False,
            )
            return
        parent_id = message.channel.parent_id
        if not parent_id:
            return
        from eddy_flow_library import EddyFlowLibraryView

        view = EddyFlowLibraryView(message.channel.id, parent_id, flows)
        client.add_view(view)
        names = ", ".join(f"`{fid.replace('_', ' ').title()}`" for fid in flows[:8])
        extra = f" (+{len(flows) - 8} more)" if len(flows) > 8 else ""
        embed = discord.Embed(
            title="Flow library",
            description=(
                f"**{len(flows)}** installed flow(s): {names}{extra}\n\n"
                "Pick one to load in this eddy — or keep talking without a flow."
            ),
            color=0x5865F2,
        )
        await message.reply(embed=embed, view=view, mention_author=False)
        return

    if not is_practice_channel(message):
        await message.reply("Use `!flows` in your practice river or an eddy.", mention_author=False)
        return

    await message.reply(
        "Open an eddy with **new eddy**, then use the **flow library** inside the thread "
        "(or run `!flows` there).",
        mention_author=False,
    )


async def cmd_pin(message, args):
    """River moderation — pin a message (reply or message id)."""
    if isinstance(message.channel, discord.Thread):
        await message.reply(
            "Use `!pin` in the river channel — reply to a message to pin it.",
            mention_author=False,
        )
        return
    if not is_practice_channel(message):
        await message.reply("Use `!pin` in your practice river channel.", mention_author=False)
        return

    target = None
    if message.reference and message.reference.message_id:
        try:
            target = await message.channel.fetch_message(message.reference.message_id)
        except (discord.NotFound, discord.Forbidden):
            target = None
    elif args:
        try:
            target = await message.channel.fetch_message(int(args[0]))
        except (ValueError, discord.NotFound, discord.Forbidden):
            target = None

    if not target:
        await message.reply(
            "Reply to a message with `!pin`, or `!pin <message_id>`.",
            mention_author=False,
        )
        return

    try:
        await target.pin(reason=f"Pinned via !pin by {get_mage_name()}")
        await message.add_reaction("📌")
    except discord.Forbidden:
        await message.reply(
            "Cannot pin — the bot needs **Manage Messages** in this channel.",
            mention_author=False,
        )
    except discord.HTTPException as exc:
        await message.reply(f"Pin failed: {exc}", mention_author=False)


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

    # Search: exact match first, then partial, across cached + fetched threads
    all_threads = list(dialogue.threads)
    try:
        guild_threads = await dialogue.guild.active_threads()
        for t in guild_threads.threads:
            if t.parent_id == dialogue.id and t not in all_threads:
                all_threads.append(t)
    except Exception:
        pass

    # Exact match (name or ID)
    for t in all_threads:
        if t.name.lower() == name or str(t.id) == name:
            target_thread = t
            break

    # Partial match (search term contained in thread name)
    if not target_thread:
        partial_matches = [t for t in all_threads if name in t.name.lower()]
        if len(partial_matches) == 1:
            target_thread = partial_matches[0]
        elif len(partial_matches) > 1:
            names = ", ".join(f"**{t.name}**" for t in partial_matches[:5])
            await message.reply(f"Multiple threads match `{name}`: {names}. Be more specific.", mention_author=False)
            return

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
    mage_key = get_mage_key()
    is_space = bool(mage_key and mage_key in get_registry().get("spaces", {}))
    if get_mage_type() == "practitioner":
        title = "Practice substrate"
    elif is_space:
        title = "Shared space"
    else:
        title = "Practice-readiness"
    color = (
        0x2ECC71 if not result["highest_leverage"] else
        (0xE67E22 if result["highest_leverage"]["status"] == "degraded" else 0xE74C3C)
    )
    digest = result["summary"].replace("**", "")

    if is_river_message(message):
        await post_command_act(
            message.channel.id,
            title=title,
            body=result["summary"],
            emoji="🧭",
            color=color,
        )
        save_readiness_trail(result)
        return truncate(digest, 200)

    embed = discord.Embed(
        title=f"{'🌊' if get_mage_type() == 'practitioner' else '🧭'} {title}",
        description=result["summary"],
        color=color,
    )
    embed.set_footer(text=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
    await message.reply(embed=embed, mention_author=False)
    save_readiness_trail(result)
    return truncate(digest, 200)


async def cmd_focus(message, args):
    """Narrow this conversation to one thing (CE Slice 1 — the power-user shortcut).

    Conversational narrowing is the intended front door (Slice 1b); this ``!``
    lever exists for practitioners who want an explicit handle (design §5.2a).
      - ``!focus``            → what's in motion + this eddy's current focus
      - ``!focus <label>``    → focus on that thread (create it if new); scope
                                is per-eddy so other conversations stay wide
      - ``!focus clear``      → widen back to holistic
    """
    from continuity_engine import (
        add_active_thread,
        clear_scope,
        find_active_thread,
        get_scope,
        list_active_threads,
        set_scope,
    )

    set_practice_context(message)
    pd = get_pd()
    channel_id = message.channel.id

    # No args → show what's in motion + current focus (plain language, firewall §4).
    if not args:
        threads = list_active_threads(pd)
        current = get_scope(pd, channel_id)
        current_label = None
        if current:
            found = find_active_thread(pd, current)
            current_label = found.get("label") if found else current
        if threads:
            listed = "\n".join(
                f"- **{t.get('label', t.get('id'))}**"
                f"{' — ' + t['tone'] if t.get('tone') else ''}"
                + ("  ← focused here" if str(t.get("id")) == str(current) else "")
                for t in threads
            )
            body = f"In motion:\n{listed}"
        else:
            body = "Nothing in motion yet. `!focus <topic>` starts one."
        if current_label:
            body += f"\n\nThis eddy is focused on **{current_label}**. `!focus clear` to widen."
        await message.reply(body, mention_author=False)
        return f"Focus overview shown ({len(threads)} in motion)."

    first = args[0].lower()
    if first in ("clear", "off", "wide", "none"):
        cleared = clear_scope(pd, channel_id)
        await message.reply(
            "Widened back out — talking about everything again."
            if cleared
            else "This eddy wasn't focused on anything in particular.",
            mention_author=False,
        )
        return "Focus cleared." if cleared else "Focus already wide."

    label = " ".join(args).strip().strip('"').strip("'")
    thread = find_active_thread(pd, label)
    created = False
    if not thread:
        thread = add_active_thread(pd, label)
        created = True
    set_scope(pd, channel_id, str(thread.get("id")))
    tlabel = thread.get("label", label)
    await message.reply(
        f"Focusing on **{tlabel}**{' (new)' if created else ''} — I'll pull deeper "
        "context on it here. `!focus clear` to widen.",
        mention_author=False,
    )
    return f"Focused this eddy on \"{tlabel}\"{' (new thread)' if created else ''}."


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
            "- `!admin registry prune-orphans [--confirm]` — compact discord-deleted orphan rows\n"
            "- `!admin onboard <username> [de|en]` — create hosted river + practitioner workshop\n"
            "- `!admin river-key <name> <emoji> [de|en]` — invite-to-claim room + river key\n"
            "- `!admin space` — shared-river space provisioning (create / close / list / sync)\n",
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
        from runtime.adapters.structural import collect_registry_audit_issues

        guild = message.guild
        audit_issues = collect_registry_audit_issues(get_registry(), guild)

        if audit_issues:
            await message.reply("**Permission Audit:**\n" + "\n".join(audit_issues), mention_author=False)
        else:
            await message.reply("**Permission Audit:** All clear. Channel permissions match registry.", mention_author=False)

    elif subcmd == "registry":
        from river_keys import _primary_operator_ids
        from space_provisioning import prune_orphaned_channels

        if message.author.id not in _primary_operator_ids():
            await message.reply("Registry commands require the primary operator.", mention_author=False)
            return
        if len(args) < 2:
            await message.reply(
                "**Registry commands:**\n"
                "- `!admin registry prune-orphans` — list discord-deleted orphan rows (dry-run)\n"
                "- `!admin registry prune-orphans --confirm` — remove those rows from registry\n",
                mention_author=False,
            )
            return

        reg_sub = args[1].lower()
        if reg_sub == "prune-orphans":
            confirm = "--confirm" in [a.lower() for a in args[2:]]
            registry = get_registry()
            preview, pruned = prune_orphaned_channels(registry, confirm=confirm)
            if confirm:
                if pruned:
                    await message.reply(
                        "**Registry prune:** removed " + str(len(pruned)) + " orphan row(s):\n"
                        + "\n".join(f"- {line}" for line in pruned),
                        mention_author=False,
                    )
                else:
                    await message.reply("**Registry prune:** nothing to remove.", mention_author=False)
            elif preview:
                await message.reply(
                    "**Registry prune (dry-run):** would remove " + str(len(preview)) + " row(s):\n"
                    + "\n".join(f"- {line}" for line in preview)
                    + "\n\nRe-run with `--confirm` to compact.",
                    mention_author=False,
                )
            else:
                await message.reply("**Registry prune:** no discord-deleted orphan rows.", mention_author=False)
        else:
            await message.reply(
                f"Unknown registry command: `{reg_sub}`. Try `!admin registry` for help.",
                mention_author=False,
            )

    elif subcmd == "onboard" and len(args) > 1:
        username = args[1]
        locale = (args[2].lower() if len(args) > 2 else "en").strip()
        if locale not in ("de", "en"):
            locale = "en"
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
        from discord_reconcile import expect_channel_registry_binding

        expect_channel_registry_binding(new_ch.id)

        import yaml
        registry_path = os.path.expanduser("~/turtleos/mage_registry.yaml")
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
            "practice_dir": f"~/workshops/{mage_key_val}",
            "runtime_dir": f"~/workshops/{mage_key_val}",
            "type": "practitioner",
            "locale": locale,
        }
        reg["channels"][str(new_ch.id)] = {
            "mage": mage_key_val,
            "type": "hosted-river",
            "default_context": None,
            "description": f"Hosted practice surface for {target_member.display_name}",
        }
        with open(registry_path, "w") as f:
            yaml.dump(reg, f, default_flow_style=False, allow_unicode=True)
        reload_mage_registry()

        from hosted_river_onboarding import seed_practitioner_workshop

        workshop = seed_practitioner_workshop(mage_key_val, locale=locale)

        await message.reply(
            f"**Onboarding complete for {target_member.display_name}:**\n"
            f"- Channel: `#{channel_name}` (hosted river, sovereign)\n"
            f"- Workshop: `{workshop}`\n"
            f"- Registry: `hosted-river` + practitioner\n"
            f"- Onboarding embed: posts on next River bot restart (or re-run river)\n"
            f"They write in the river; Turtle speaks in eddies.",
            mention_author=False
        )
        await log_activity(
            f"Onboarded **{target_member.display_name}** — `#{channel_name}` created, workshop initialized", "\U0001f331", channel=message.channel
        )

    elif subcmd == "river-key" and len(args) >= 3:
        from river_keys import _looks_like_single_key, provision_unclaimed_river, _normalize_mage_key
        from river_keys import _primary_operator_ids

        if message.author.id not in _primary_operator_ids():
            await message.reply("River key provisioning requires the primary operator.", mention_author=False)
            return

        display_name = args[1].strip()
        river_key = args[2].strip()
        locale = "en"
        if len(args) > 3 and args[3].lower() in ("de", "en"):
            locale = args[3].lower()

        if not _looks_like_single_key(river_key):
            await message.reply(
                "River key must be a **single emoji** (the one your guest chose).",
                mention_author=False,
            )
            return

        mage_key = _normalize_mage_key(display_name)
        guild = message.guild
        if not guild:
            await message.reply("River keys can only be provisioned from a server channel.", mention_author=False)
            return

        registry = get_registry()
        if mage_key in registry.get("mages", {}) and registry["mages"][mage_key].get("discord_id"):
            await message.reply(
                f"`{mage_key}` is already bound. Use a different name or retire the old river first.",
                mention_author=False,
            )
            return

        for entry in registry.get("channels", {}).values():
            if isinstance(entry, dict) and entry.get("mage") == mage_key and entry.get("type") == "unclaimed-river":
                await message.reply(
                    f"A claim room for `{mage_key}` already exists. Finish or remove it before creating another.",
                    mention_author=False,
                )
                return

        try:
            channel, invite = await provision_unclaimed_river(
                guild,
                mage_key=mage_key,
                display_name=display_name,
                river_key=river_key,
                locale=locale,
            )
        except discord.HTTPException as exc:
            await message.reply(f"Could not create claim room: {exc}", mention_author=False)
            return

        await message.reply(
            f"**River key ready for {display_name}** (`{mage_key}`)\n"
            f"- Key: {river_key}\n"
            f"- Claim room: #{channel.name}\n"
            f"- Workshop: `~/workshops/{mage_key}/`\n"
            f"- Invite (send privately): {invite.url}\n\n"
            f"Tell them to open the link and send {river_key} in the channel.",
            mention_author=False,
        )
        await log_activity(
            f"Provisioned river key for **{display_name}** — #{channel.name}",
            "\U0001f511",
            channel=message.channel,
        )

    elif subcmd == "space":
        from river_keys import _primary_operator_ids
        from space_provisioning import (
            close_shared_space,
            create_shared_space,
            find_shared_river_channel,
            hide_shared_space,
            list_active_spaces,
            parse_space_close_args,
            parse_space_create_args,
            parse_space_hide_args,
            resolve_member_keys,
        )
        from mage import ensure_space_channel_access

        if message.author.id not in _primary_operator_ids():
            await message.reply("Space provisioning requires the primary operator.", mention_author=False)
            return
        if len(args) < 2:
            await message.reply(
                "**Space commands:**\n"
                "- `!admin space create <space-key> [--members @user ...] [--open] [--policy all_practitioners|members_only] [--context family|shared] [--channel name]`\n"
                "- `!admin space close <space-key> [--confirm] [--dissolve-eddies]`\n"
                "- `!admin space hide <space-key> [--confirm]` — hide an archived space from Discord (repair)\n"
                "- `!admin space list` — active shared spaces\n"
                "- `!admin space sync <space-key>` — repair Discord permissions from registry\n",
                mention_author=False,
            )
            return

        space_sub = args[1].lower()
        guild = message.guild
        if not guild:
            await message.reply("Space commands must run on the server.", mention_author=False)
            return

        if space_sub == "create":
            try:
                options = parse_space_create_args(args[1:])
                registry = get_registry()
                member_keys = resolve_member_keys(
                    guild,
                    registry,
                    member_tokens=options.member_tokens,
                    message_mentions=list(message.mentions),
                    operator_id=message.author.id,
                )
                channel, workshop = await create_shared_space(
                    guild,
                    options,
                    member_keys=member_keys,
                )
                from river_handler import _river_client_for_channel, ensure_bar_at_bottom

                bar_client = _river_client_for_channel(channel) or client
                await ensure_bar_at_bottom(channel, bar_client)
            except ValueError as exc:
                await message.reply(str(exc), mention_author=False)
                return
            except discord.HTTPException as exc:
                await message.reply(f"Could not create shared space: {exc}", mention_author=False)
                return

            visibility = "open (view-only for @everyone)" if options.open_to_everyone else "members only"
            await message.reply(
                f"**Shared space `{options.space_key}` created:**\n"
                f"- Channel: #{channel.name}\n"
                f"- Members: {', '.join(f'`{k}`' for k in member_keys)}\n"
                f"- Share policy: `{options.share_policy}`\n"
                f"- Discord visibility: {visibility}\n"
                f"- Workshop: `{workshop}`\n"
                f"- Context: `{options.default_context or 'none'}`\n\n"
                f"Optional: open an eddy and run `!flow shared-river-orientation` when ready.",
                mention_author=False,
            )
            await log_activity(
                f"Created shared space **{options.space_key}** — #{channel.name}",
                "\U0001f3db\ufe0f",
                channel=message.channel,
            )

        elif space_sub == "close":
            try:
                options = parse_space_close_args(args[1:])
                summary = await close_shared_space(guild, options, discord_client=client)
            except ValueError as exc:
                await message.reply(str(exc), mention_author=False)
                return

            if not options.confirm:
                await message.reply(
                    f"**Close `{summary['space_key']}`?**\n"
                    f"- Channel: `#{summary['channel_name']}` (`{summary['channel_id']}`)\n"
                    f"- Members: {', '.join(f'`{m}`' for m in summary['members']) or '(none)'}\n"
                    f"- Share policy: `{summary['share_policy']}`\n"
                    f"- Open threads: {summary['open_threads']}\n\n"
                    f"Re-run with `--confirm` to archive (workshop kept by default).",
                    mention_author=False,
                )
                return

            await message.reply(
                f"**Archived shared space `{summary['space_key']}`**\n"
                f"- Channel: `#{summary['channel_name']}` hidden from members (operators retain access)\n"
                f"- Registry: marked archived; river harness will skip this channel\n",
                mention_author=False,
            )
            await log_activity(
                f"Archived shared space **{summary['space_key']}** — #{summary['channel_name']}",
                "\U0001f4e6",
                channel=message.channel,
            )

        elif space_sub == "hide":
            try:
                options = parse_space_hide_args(args[1:])
                summary = await hide_shared_space(guild, options, discord_client=client)
            except ValueError as exc:
                await message.reply(str(exc), mention_author=False)
                return

            if not options.confirm:
                state = "already archived" if summary.get("registry_archived") else "active"
                await message.reply(
                    f"**Hide `{summary['space_key']}`?** (registry: {state})\n"
                    f"- Channel: `#{summary['channel_name']}` (`{summary['channel_id']}`)\n"
                    f"- Members who will lose view: {', '.join(f'`{m}`' for m in summary['members']) or '(none)'}\n"
                    f"- Open threads: {summary['open_threads']}\n\n"
                    f"Re-run with `--confirm` to hide from practitioners (operators retain access).",
                    mention_author=False,
                )
                return

            await message.reply(
                f"**Hidden shared space `{summary['space_key']}`**\n"
                f"- Channel: `#{summary['channel_name']}` no longer visible to members\n"
                f"- Registry: archived; river harness skips this channel\n",
                mention_author=False,
            )
            await log_activity(
                f"Hidden shared space **{summary['space_key']}** — #{summary['channel_name']}",
                "\U0001f4e6",
                channel=message.channel,
            )

        elif space_sub == "list":
            rows = list_active_spaces(get_registry())
            if not rows:
                await message.reply("No active shared-river spaces in registry.", mention_author=False)
                return
            lines = ["**Active shared spaces:**"]
            for row in rows:
                ch = guild.get_channel(int(row["channel_id"]))
                ch_label = f"#{ch.name}" if ch else f"id:{row['channel_id']}"
                members = ", ".join(f"`{m}`" for m in row["members"]) or "(none)"
                lines.append(
                    f"- `{row['space_key']}` → {ch_label} · members: {members} · policy: `{row['share_policy']}`"
                )
            await message.reply("\n".join(lines), mention_author=False)

        elif space_sub == "sync" and len(args) > 2:
            from space_provisioning import normalize_space_key

            try:
                space_key = normalize_space_key(args[2])
            except ValueError as exc:
                await message.reply(str(exc), mention_author=False)
                return
            binding = find_shared_river_channel(get_registry(), space_key)
            if not binding:
                await message.reply(f"No active shared-river space `{space_key}`.", mention_author=False)
                return
            ch_id_str, _entry = binding
            channel = guild.get_channel(int(ch_id_str))
            if channel is None:
                await message.reply(f"Channel `{ch_id_str}` not found on server.", mention_author=False)
                return
            changed = await ensure_space_channel_access(channel, guild=guild)
            await message.reply(
                f"Synced **`{space_key}`** — permissions {'updated' if changed else 'already aligned'}.",
                mention_author=False,
            )

        else:
            await message.reply(
                f"Unknown space command: `{space_sub}`. Try `!admin space` for help.",
                mention_author=False,
            )

    else:
        await message.reply(f"Unknown admin command: `{subcmd}`. Try `!admin` for help.", mention_author=False)


DIRECT_COMMANDS = {
    "status": lambda msg, args: cmd_status(msg),
    "artifacts": lambda msg, args: cmd_artifacts(msg, args),
    "export": lambda msg, args: cmd_export(msg, args),
    "read": lambda msg, args: cmd_read(msg, args),
    "ls": lambda msg, args: cmd_ls(msg, args),
    "search": lambda msg, args: cmd_search(msg, args),
    "checkpoint": lambda msg, args: cmd_checkpoint(msg),
    "release": lambda msg, args: cmd_release(msg),
    "dissolve": lambda msg, args: cmd_dissolve(msg, args),
    "flows": lambda msg, args: cmd_flows(msg, args),
    "flow": lambda msg, args: cmd_flows(msg, args),
    "pin": lambda msg, args: cmd_pin(msg, args),
    "thread": lambda msg, args: cmd_thread(msg, args),
    "threads": lambda msg, args: cmd_threads(msg, args),
    "thread-type": lambda msg, args: cmd_thread_type(msg, args),
    "rename": lambda msg, args: cmd_rename(msg, args),
    "eddy-check": lambda msg, args: cmd_eddy_check(msg, args),
    "fetch": lambda msg, args: cmd_fetch(msg, args),
    "absorb": lambda msg, args: cmd_absorb(msg, args),
    "absorbed": lambda msg, args: cmd_absorbed(msg, args),
    "forget": lambda msg, args: cmd_forget(msg, args),
    "readiness": lambda msg, args: cmd_readiness(msg),
    "focus": lambda msg, args: cmd_focus(msg, args),
    "diagnose": lambda msg, args: cmd_diagnose(msg),
    "panel": lambda msg, args: cmd_panel(msg),
    "help": lambda msg, args: cmd_help(msg),
    "admin": lambda msg, args: cmd_admin(msg, args),
    "new": lambda msg, args: cmd_new(msg, args),
    "share": lambda msg, args: cmd_share(msg, args),
}
