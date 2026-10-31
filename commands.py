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

import state
from state import (
    CHANNELS, OPS_EMBED_COLOR, SPIRIT_BOT_ID, EMBED_COLORS,
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
    get_pd, get_runtime_dir, get_topology, get_mage_name, get_mage_key, get_mage_type,
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
from cmd_sessions import cmd_checkpoint, cmd_dissolve, cmd_ignore, cmd_keep, cmd_release, cmd_spark
from share_eddy import cmd_share
from dates import cmd_dates as _cmd_dates
from cmd_practice_io import cmd_artifacts, cmd_export, cmd_read
from cmd_threads import (
    EddyDissolutionView,
    ThreadConfigView,
    ThreadTypeView,
    build_config_line,
    build_config_line as _build_config_line,
    cmd_rename,
    cmd_eddy,
    cmd_live,
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

    def _run_all_checks():
        """Every canary check, in order, in one thread.

        `!diagnose` used to run this loop directly in the command handler, so the
        entire bot stopped for the duration of the whole board — which includes four
        tool invocations, model probes and filesystem walks. The checks stay
        sequential because that is what they were, and one thread for the batch keeps
        it that way; the point is only that the batch is not on the event loop.
        """
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
        return results, has_red, has_yellow

    from core.offload import run_blocking

    results, has_red, has_yellow = await run_blocking(_run_all_checks, name="canary_board")

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


async def cmd_mcp(message, args):
    """The list is a button. The reply only the asker sees is the press."""
    from outgoing_connect_ui import ACT, CHANNEL_LINE, OutgoingConnectionsView

    await message.reply(
        CHANNEL_LINE,
        view=OutgoingConnectionsView(),
        mention_author=False,
    )
    return ACT


async def cmd_help(message):
    """`!` or `!help`: the curated commands as one card. The card is the whole answer."""
    from help_card import render
    from room_models import locale_for, open_menu_private

    locale = locale_for(message.author.id, get_registry())
    await message.reply(
        view=render(locale=locale, operator=get_mage_type() != "practitioner", menu=open_menu_private),
        mention_author=False,
    )
    return "Command card posted."


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
            ok = await load_flow_in_eddy(message.channel, flow_id, state.client)
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
        state.client.add_view(view)
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
        await message.reply("Use `!flows` in your channel or an eddy.", mention_author=False)
        return

    await message.reply(
        "Open an eddy with **new eddy**, then use the **flow library** inside the thread "
        "(or run `!flows` there).",
        mention_author=False,
    )


async def cmd_pin(message, args):
    """Working-plan product act (eddy) or legacy river message pin.

    In an eddy: bind home eddy ↔ Tier-1 artifact and post a river pin card.
    On the river: pin a replied-to message (moderation path).
    """
    if isinstance(message.channel, discord.Thread):
        await _cmd_pin_home_eddy(message, args)
        return
    if not is_practice_channel(message):
        await message.reply(
            "Use `!pin` in a practice eddy (working plan) or your channel (message pin).",
            mention_author=False,
        )
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
            "On the river: reply to a message with `!pin`, or `!pin <message_id>`.\n"
            "In an eddy: `!pin` keeps the conversation as a working plan "
            "(river pin card + home eddy).",
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


def _home_plan_title_from_body(body: str) -> str:
    """Prefer a real heading over the first bullet of a workout list."""
    from home_plans import title_from_plan_body

    title = title_from_plan_body(body, fallback="")
    return title


async def _cmd_pin_home_eddy(message, args):
    """Bind or refresh a home-plan pin from inside an eddy."""
    from home_plan_ui import bind_and_post_pin, resolve_pin_client
    from home_plans import HomePlanError, get_by_eddy
    from mage import get_pd

    thread = message.channel
    parent_id = getattr(thread, "parent_id", None)
    if not parent_id:
        await message.reply(
            "Cannot find the channel this eddy belongs to.", mention_author=False
        )
        return

    pd = get_pd()
    existing = get_by_eddy(pd, thread.id)
    pin_client = resolve_pin_client(message=message)

    title = " ".join(args).strip() if args else ""
    body = None
    if message.reference and message.reference.message_id:
        try:
            src = await thread.fetch_message(message.reference.message_id)
            body = (src.content or "").strip() or None
            if not title and body:
                title = _home_plan_title_from_body(body)
        except (discord.NotFound, discord.Forbidden):
            pass

    # No reply: prefer latest substantial non-command message in the eddy (Turtle plan).
    if not body and hasattr(thread, "history"):
        try:
            async for m in thread.history(limit=20):
                text = (m.content or "").strip()
                if not text or text.startswith("!"):
                    continue
                if len(text) < 80:
                    continue
                body = text
                if not title:
                    title = _home_plan_title_from_body(body)
                break
        except (discord.Forbidden, discord.HTTPException, TypeError, AttributeError):
            pass

    if existing:
        try:
            plan = await bind_and_post_pin(
                practice_dir=pd,
                title=existing.get("title") or title or thread.name or "Working plan",
                home_eddy_id=thread.id,
                river_channel_id=parent_id,
                refresh_plan=existing,
                discord_client=pin_client,
                message=message,
                body=body,
            )
        except HomePlanError as exc:
            await message.reply(str(exc), mention_author=False)
            return
        except Exception as exc:
            await message.reply(f"Could not refresh pin: {exc}", mention_author=False)
            return
        await message.reply(
            f"Refreshed river pin for **{plan.get('title')}** — Continue anytime.",
            mention_author=False,
        )
        return

    if not title:
        title = (thread.name or "").strip() or "Working plan"
        if title.lower().startswith("new eddy"):
            title = "Working plan"

    try:
        plan = await bind_and_post_pin(
            practice_dir=pd,
            title=title,
            home_eddy_id=thread.id,
            river_channel_id=parent_id,
            body=body,
            discord_client=pin_client,
            message=message,
        )
    except HomePlanError as exc:
        await message.reply(str(exc), mention_author=False)
        return
    except Exception as exc:
        await message.reply(f"Could not pin working plan: {exc}", mention_author=False)
        return

    await message.reply(
        f"Pinned **{plan.get('title')}** in your channel — "
        "Continue anytime from the pin tray. Open shows the file.",
        mention_author=False,
    )


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


async def cmd_context(message, args):
    """Show what this eddy's last turn injected (TURTLE_SPEC §3.2).

    Renders the persisted packet: named shell-injected blocks, tools called,
    files loaded, and which injection slots were empty. Does not name the
    alive layer or ``confirmed_by`` — those are not injection slots.
    """
    from turn_packet import render_context_command

    set_practice_context(message)
    body = render_context_command(get_pd(), message.channel.id)
    for chunk in split_message(body):
        await message.reply(chunk, mention_author=False)
    return "Context this turn posted."


# ─── Admin Commands ──────────────────────────────────────────────

async def _resolve_guild_member(guild, token: str, message=None):
    """Resolve a guild member from mention, snowflake, username, or display name.

    Cache scan needs Server Members Intent. Snowflake ``fetch_member`` works
    without a full member list (HTTP). Prefer mentions when the operator tags.
    """
    if guild is None or not token:
        return None
    raw = token.strip()
    mention = re.fullmatch(r"<@!?(\d+)>", raw)
    if mention:
        uid = int(mention.group(1))
        cached = guild.get_member(uid)
        if cached:
            return cached
        if message is not None:
            for m in message.mentions:
                if m.id == uid:
                    return m if isinstance(m, discord.Member) else guild.get_member(uid)
        try:
            return await guild.fetch_member(uid)
        except (discord.NotFound, discord.HTTPException):
            return None

    if raw.isdigit():
        uid = int(raw)
        cached = guild.get_member(uid)
        if cached:
            return cached
        try:
            return await guild.fetch_member(uid)
        except (discord.NotFound, discord.HTTPException):
            return None

    needle = raw.lower().lstrip("@")
    for m in guild.members:
        if m.name.lower() == needle or m.display_name.lower() == needle:
            return m

    # Partial cache / slow chunk: HTTP query (still needs members intent on gateway apps).
    try:
        found = await guild.query_members(query=needle, limit=5)
    except (discord.HTTPException, TypeError, ValueError, AttributeError):
        found = []
    for m in found:
        if m.name.lower() == needle or m.display_name.lower() == needle:
            return m
    if len(found) == 1:
        return found[0]
    return None


async def cmd_admin(message, args):
    """Server seneschal commands — host experience (invite, spaces, health)."""
    from admin_experience import admin_help_advanced, admin_help_default

    if not args:
        await message.reply(admin_help_default(), mention_author=False)
        return

    subcmd = args[0].lower()
    if subcmd == "advanced":
        await message.reply(admin_help_advanced(), mention_author=False)
        return

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
        body = "\n".join(lines) or "(no members)"
        humans = [m for m in guild.members if not m.bot]
        if len(guild.members) <= 1 or not humans:
            body += (
                "\n\n⚠️ Member cache looks empty — enable **Server Members Intent** "
                "on this bot's Discord application (Developer Portal → Bot), then restart."
            )
        await message.reply(body, mention_author=False)

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

    elif subcmd == "onboard":
        await message.reply(
            "`!admin onboard` is deprecated. Use:\n"
            "`!admin invite <name> <emoji> [en|de] [--member @member|id|username]`\n"
            "See `!admin` for host commands.",
            mention_author=False,
        )

    elif subcmd in ("invite", "river-key"):
        from river_keys import (
            _looks_like_single_key,
            _normalize_mage_key,
            _primary_operator_ids,
            parse_invite_args,
            provision_unclaimed_river,
        )

        if message.author.id not in _primary_operator_ids():
            await message.reply("River invite requires the primary operator.", mention_author=False)
            return

        try:
            display_name, river_key, locale, member_token = parse_invite_args(args[1:])
        except ValueError as exc:
            await message.reply(str(exc), mention_author=False)
            return

        if not _looks_like_single_key(river_key):
            await message.reply(
                "River key must be a **single emoji** (the one your guest chose).",
                mention_author=False,
            )
            return

        mage_key = _normalize_mage_key(display_name)
        guild = message.guild
        if not guild:
            await message.reply("River invites can only be provisioned from a server channel.", mention_author=False)
            return

        guest_member = None
        if member_token:
            guest_member = await _resolve_guild_member(guild, member_token, message)
            if guest_member is None:
                await message.reply(
                    f"Could not resolve `--member {member_token}`. "
                    "Try @mention, username, or Discord id — or omit `--member` and send the channel invite.",
                    mention_author=False,
                )
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
                guest_member=guest_member,
            )
        except discord.HTTPException as exc:
            await message.reply(f"Could not create claim room: {exc}", mention_author=False)
            return

        deep_link = f"https://discord.com/channels/{guild.id}/{channel.id}"
        if guest_member is not None:
            handoff = (
                f"- Door open for **{guest_member.display_name}** (channel perms granted)\n"
                f"- Deep link (send privately): {deep_link}\n\n"
                f"Tell them to open the link and send {river_key} in `#{channel.name}`."
            )
        else:
            handoff = (
                f"- Invite (send privately): {invite.url}\n"
                f"- Deep link (if already on the server): {deep_link}\n\n"
                f"If they joined the server earlier, prefer the deep link — "
                f"channel invites often hide private claim rooms from existing members.\n"
                f"Tell them to open the link and send {river_key} in the channel."
            )

        await message.reply(
            f"**River invite ready for {display_name}** (`{mage_key}`)\n"
            f"- Key: {river_key}\n"
            f"- River: `#{channel.name}`\n"
            f"- Workshop: `~/workshops/{mage_key}/`\n"
            f"{handoff}",
            mention_author=False,
        )
        await log_activity(
            f"Provisioned river invite for **{display_name}** — #{channel.name}",
            "\U0001f511",
            channel=message.channel,
        )

    elif subcmd == "rivers":
        from admin_experience import (
            apply_sync_names,
            format_rivers_list,
            format_sync_preview,
            iter_river_rows,
            plan_sync_names,
        )
        from river_keys import _primary_operator_ids

        if message.author.id not in _primary_operator_ids():
            await message.reply("River inventory requires the primary operator.", mention_author=False)
            return

        registry = get_registry()
        if len(args) == 1:
            await message.reply(format_rivers_list(iter_river_rows(registry)), mention_author=False)
            return

        rivers_sub = args[1].lower()
        if rivers_sub == "sync-names":
            confirm = "--confirm" in [a.lower() for a in args[2:]]
            guild = message.guild
            actions = plan_sync_names(registry, guild)
            if not confirm:
                await message.reply(format_sync_preview(actions), mention_author=False)
                return
            if not guild:
                await message.reply("sync-names --confirm needs a server channel.", mention_author=False)
                return
            if not actions:
                await message.reply(format_sync_preview(actions), mention_author=False)
                return
            results = await apply_sync_names(registry, guild, actions)
            await message.reply(
                "**Rivers sync-names applied:**\n" + "\n".join(results),
                mention_author=False,
            )
            await log_activity(
                f"Rivers sync-names — {len(results)} change(s)",
                "\U0001f3e0",
                channel=message.channel,
            )
        elif rivers_sub == "admit":
            from river_keys import admit_member_to_unclaimed_river

            if len(args) < 4:
                await message.reply(
                    "Usage: `!admin rivers admit <name> <@member|id|username>`",
                    mention_author=False,
                )
                return
            guild = message.guild
            if not guild:
                await message.reply("admit needs a server channel.", mention_author=False)
                return
            mage_key = args[2]
            member_token = args[3]
            target = await _resolve_guild_member(guild, member_token, message)
            if target is None:
                await message.reply(
                    f"Member `{member_token}` not found. Try @mention, username, or Discord id.",
                    mention_author=False,
                )
                return
            try:
                channel, key = await admit_member_to_unclaimed_river(
                    guild, mage_key=mage_key, member=target
                )
            except ValueError as exc:
                await message.reply(str(exc), mention_author=False)
                return
            except discord.HTTPException as exc:
                await message.reply(f"Could not grant access: {exc}", mention_author=False)
                return
            deep_link = f"https://discord.com/channels/{guild.id}/{channel.id}"
            await message.reply(
                f"**Admitted** **{target.display_name}** to `#{channel.name}` (`{key}`).\n"
                f"Deep link: {deep_link}\n"
                f"They send their key emoji there to claim.",
                mention_author=False,
            )
            await log_activity(
                f"Admitted **{target.display_name}** to #{channel.name}",
                "\U0001f511",
                channel=message.channel,
            )
        else:
            await message.reply(
                "Unknown rivers command. Try:\n"
                "- `!admin rivers`\n"
                "- `!admin rivers admit <name> <@member|id|username>`\n"
                "- `!admin rivers sync-names [--confirm]`",
                mention_author=False,
            )

    elif subcmd == "doctor":
        from admin_experience import collect_doctor_findings, format_doctor

        findings = collect_doctor_findings(get_registry(), message.guild)
        await message.reply(format_doctor(findings), mention_author=False)

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
                "- `!admin space create <space-key> [--members @member ...] [--open] [--policy all_practitioners|members_only] [--context family|shared] [--channel name]`\n"
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
                from river_handler import _river_client_for_channel, reconcile_river_bar_floor

                bar_client = _river_client_for_channel(channel) or state.client
                await reconcile_river_bar_floor(channel, bar_client)
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
                summary = await close_shared_space(guild, options, discord_client=state.client)
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
                summary = await hide_shared_space(guild, options, discord_client=state.client)
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
            from discord_reconcile import ensure_channel_category
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
            ch_id_str, entry = binding
            channel = guild.get_channel(int(ch_id_str))
            if channel is None:
                await message.reply(f"Channel `{ch_id_str}` not found on server.", mention_author=False)
                return
            permissions_changed = await ensure_space_channel_access(
                channel, guild=guild
            )
            category_changed = await ensure_channel_category(channel, entry)
            changed = permissions_changed or category_changed
            detail = []
            detail.append(
                f"permissions {'updated' if permissions_changed else 'aligned'}"
            )
            if entry.get("discord_category"):
                detail.append(
                    f"category {'updated' if category_changed else 'aligned'}"
                )
            await message.reply(
                f"Synced **`{space_key}`** — {', '.join(detail)}"
                f"{'' if changed else ' (no changes)'}.",
                mention_author=False,
            )

        else:
            await message.reply(
                f"Unknown space command: `{space_sub}`. Try `!admin space` for help.",
                mention_author=False,
            )

    else:
        await message.reply(f"Unknown admin command: `{subcmd}`. Try `!admin` for help.", mention_author=False)


async def _cmd_model(message, args):
    from core.models import conversation_model
    from mage import get_registry, resolve_dialogue_channel_id
    from room_models import cmd_model

    parent_id = resolve_dialogue_channel_id(message)
    default = conversation_model()
    return await cmd_model(
        message, args, parent_id=parent_id, registry=get_registry(), default=default)


async def _cmd_feed(message, args):
    from backlog_feed_ui import cmd_feed

    return await cmd_feed(message, args)


async def cmd_pi(message, args):
    """The coding agent's version and model. An update names the release and asks."""
    from mage import get_channel_primitive, resolve_dialogue_channel_id

    from pi_card import _t, maintained_here, read_installed, reply_view

    prim = get_channel_primitive(resolve_dialogue_channel_id(message))
    locale = "en"
    try:
        from room_models import locale_for

        locale = locale_for(message.author.id, get_registry())
    except Exception:
        locale = "en"
    if not maintained_here(getattr(prim, "name", None)):
        await message.reply(_t(locale)["elsewhere"], mention_author=False)
        return "Pi is maintained in #magic."
    version, model = read_installed()
    await message.reply(view=reply_view(version, model, locale=locale), mention_author=False)
    return "Pi card posted."


async def cmd_git(message, args):
    """The workshop's unkept files. Arguments are ignored: this is not a diff."""
    from mage import get_channel_primitive, get_registry, resolve_dialogue_channel_id
    from room_connections import owner_of
    from workshop_tools import checkout_for

    from git_card import _t, maintained_here, reply_for

    del args  # a path or a verb would turn the list into a diff
    channel_id = resolve_dialogue_channel_id(message)
    prim = get_channel_primitive(channel_id)
    locale = "en"
    try:
        from room_models import locale_for

        locale = locale_for(message.author.id, get_registry())
    except Exception:
        locale = "en"
    if not maintained_here(getattr(prim, "name", None)):
        await message.reply(_t(locale)["elsewhere"], mention_author=False)
        return "Git list is in #magic."
    registry = get_registry()
    owner = owner_of(registry, channel_id)
    text = reply_for(checkout_for(registry, owner) if owner else None, locale=locale)
    await message.reply(text, mention_author=False)
    return "Workshop list posted."


DIRECT_COMMANDS = {
    "status": lambda msg, args: cmd_status(msg),
    "artifacts": lambda msg, args: cmd_artifacts(msg, args),
    "export": lambda msg, args: cmd_export(msg, args),
    "read": lambda msg, args: cmd_read(msg, args),
    "checkpoint": lambda msg, args: cmd_checkpoint(msg),
    "spark": lambda msg, args: cmd_spark(msg, args),
    "release": lambda msg, args: cmd_release(msg),
    "dissolve": lambda msg, args: cmd_dissolve(msg, args),
    "keep": lambda msg, args: cmd_keep(msg, args),
    "ignore": lambda msg, args: cmd_ignore(msg, args),
    "flows": lambda msg, args: cmd_flows(msg, args),
    "flow": lambda msg, args: cmd_flows(msg, args),
    "pin": lambda msg, args: cmd_pin(msg, args),
    "threads": lambda msg, args: cmd_eddy(msg, args),  # the older name of !eddy
    "eddy": lambda msg, args: cmd_eddy(msg, args),
    "live": lambda msg, args: cmd_live(msg, args),
    "rename": lambda msg, args: cmd_rename(msg, args),
    "fetch": lambda msg, args: cmd_fetch(msg, args),
    "readiness": lambda msg, args: cmd_readiness(msg),
    "context": lambda msg, args: cmd_context(msg, args),
    "diagnose": lambda msg, args: cmd_diagnose(msg),
    "help": lambda msg, args: cmd_help(msg),
    "admin": lambda msg, args: cmd_admin(msg, args),
    "share": lambda msg, args: cmd_share(msg, args),
    "dates": lambda msg, args: _cmd_dates(msg, args),
    "model": lambda msg, args: _cmd_model(msg, args),
    "mcp": lambda msg, args: cmd_mcp(msg, args),
    "feed": lambda msg, args: _cmd_feed(msg, args),
    "pi": lambda msg, args: cmd_pi(msg, args),
    "git": lambda msg, args: cmd_git(msg, args),
}
