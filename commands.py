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

from helpers import local_now, get_history, log_activity, split_message
from eddy_spawn import spawn_eddy, should_offer_eddy, generate_topic, make_eddy_spawn_view, post_thread_opening

INTAKE_PUBLIC_URL = os.environ.get("INTAKE_PUBLIC_URL", "http://localhost:8742/paste")


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

    practice = [
        f"Practice root: `{get_pd()}`",
        f"Session files: **{len(session_files)}** (last `{last_session}`)",
        f"Installed flows: **{len(flow_files)}**",
    ]
    embed.add_field(name="Practice root", value="\n".join(practice), inline=False)
    embed.set_footer(text="turtleOS shell")
    await message.reply(embed=embed, mention_author=False)
    return (
        f"{len(session_files)} sessions, {len(flow_files)} flows, "
        f"last session `{last_session}`, {active_count} active channel(s)"
    )


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
    await message.reply(embed=embed, mention_author=False)


def _help_lines(pairs: list[tuple[str, str]]) -> str:
    return "\n".join(f"{cmd} — {desc}" for cmd, desc in pairs)


def _help_embed_fields() -> list[tuple[str, str]]:
    """Profile-aware turtle-talk sections. See docs/turtle-talk.md."""
    mage_type = get_mage_type()
    fields: list[tuple[str, str]] = []

    river_cmds = [
        ("**new eddy** · **flow menu**", "Standing bar — primary spawn (TURTLE_SPEC §5.4)"),
        ("`!flows`", "List installed flows — same picker as **flow menu**"),
        ("`!pin`", "Pin a message — reply with `!pin` or `!pin <message_id>`"),
        ("`!dissolve`", "Archive eddy + chronicle (river or in-thread)"),
    ]
    fields.append(("River (parent channel)", _help_lines(river_cmds)))

    eddy_core = [
        ("`!checkpoint`", "Save resonance — flow state + session note; keeps history"),
        ("`!release`", "Close session — checkpoint, then clear history"),
        ("`!dissolve`", "Archive eddy + chronicle — distinct from `!release`"),
        ("`!help`", "This inventory"),
        ("`!status`", "System + practice-root dashboard"),
        ("`!readiness`", "Substrate / practice-readiness check"),
        ("`!rename <title>`", "Exact eddy title (in thread)"),
        ("`!fetch <url>`", "Distill URL to library (not auto link-read in chat)"),
        ("`!read` / `!ls` / `!search`", "Browse files under practice root"),
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
        ("`!admin …`", "Operator tools incl. `river-key` (§15.4)"),
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
    if attunement_match:
        attunement = attunement_match.group(1)
    else:
        from mage import get_effective_attunement
        eff = get_effective_attunement(message.channel.id)
        attunement = "native" if eff == "native" else "semi"
    valid_attunements = ATTUNEMENT_LEVELS | {"native"}
    if attunement not in valid_attunements:
        await message.reply(
            f"Unknown attunement `{attunement}`. Use: {', '.join(sorted(valid_attunements))}",
            mention_author=False,
        )
        return

    type_match = re.search(r'--type\s+(\S+)', raw)
    eddy_type = type_match.group(1) if type_match else EDDY_DEFAULT
    if eddy_type not in EDDY_TYPES:
        await message.reply(f"Unknown eddy type `{eddy_type}`. Use: {', '.join(sorted(EDDY_TYPES))}", mention_author=False)
        return

    context_match = re.search(r'--context\s+(\S+)', raw)
    context_type = context_match.group(1) if context_match else None
    if context_type and context_type not in THREAD_CONTEXTS:
        valid = ", ".join(sorted(THREAD_CONTEXTS))
        await message.reply(f"Unknown context `{context_type}`. Use: {valid}", mention_author=False)
        return

    if not context_type:
        from mage import get_channel_default_context
        context_type = get_channel_default_context(message.channel.id)

    model_id, use_api = resolve_model(model_str)

    try:
        eddy_archive = EDDY_TYPES.get(eddy_type, {}).get("archive_minutes", 4320)
        thread = await message.create_thread(name=topic, auto_archive_duration=eddy_archive)
    except discord.HTTPException as e:
        if e.code == 160004:
            await message.reply(
                "A thread already exists on this message. "
                "Try `!thread` on a different message, or post a new message first.",
                mention_author=False,
            )
        else:
            await message.reply(f"Couldn't create thread: {e.text}", mention_author=False)
        return

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
        "context_type": context_type,
        "created": datetime.now(timezone.utc),
    }

    await post_thread_opening(
        thread,
        topic,
        origin=f"`!thread` in #{getattr(message.channel, 'name', 'practice channel')}",
        source_text=message.content,
    )

    config_line = _build_config_line(thread.id)
    view = ThreadConfigView(current_type=eddy_type)
    await thread.send(config_line, view=view)
    try:
        await message.channel.send(
            f"🌀 Thread created: **{topic}** — {thread.mention}",
            silent=True,
        )
    except Exception as e:
        print(f"Thread parent link failed: {e}")
async def cmd_thread_type(message, args):
    if not isinstance(message.channel, discord.Thread):
        await message.reply("Use `!thread-type` inside a thread.", mention_author=False)
        return
    if not args:
        cfg = thread_configs.get(message.channel.id, {})
        current = cfg.get("eddy_type", EDDY_DEFAULT)
        info = EDDY_TYPES[current]
        types_list = " / ".join(f"`{k}` ({v['emoji']} {v['label']})" for k, v in EDDY_TYPES.items())
        await message.reply(
            f"Current type: {info['emoji']} **{info['label']}** (`{current}`)\n"
            f"Available: {types_list}\n"
            f"Usage: `!thread-type standing`",
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
    await message.reply(
        f"{old_info['emoji']} → {info['emoji']} Thread type changed to **{info['label']}**",
        mention_author=False,
    )
    await log_activity(f"Thread **{message.channel.name}** type: `{old_type}` → `{new_type}`", info['emoji'], channel=message.channel)


async def cmd_rename(message, args):
    """Rename the current eddy: !rename Your exact title"""
    if not isinstance(message.channel, discord.Thread):
        await message.reply(
            "Use `!rename Your title` inside an eddy thread.",
            mention_author=False,
        )
        return
    if not is_practice_channel(message):
        await message.reply("Use `!rename` in your practice channel threads.", mention_author=False)
        return

    from eddy_spawn import parse_rename_command, rename_eddy_thread

    title = parse_rename_command(message.content)
    if not title:
        await message.reply(
            "Usage: `!rename Your exact title` — quotes optional for multi-word names.",
            mention_author=False,
        )
        return

    before = message.channel.name
    new_name, err = await rename_eddy_thread(message.channel, title)
    if err:
        await message.reply(err, mention_author=False)
        return

    if new_name == before:
        await message.reply(f"Already titled **{new_name}**.", mention_author=False)
    # Success: Discord's system line ("turtle changed the channel name") is enough trace.


# ─── Views ───────────────────────────────────────────────────────

def _build_config_line(thread_id: int) -> str:
    """Build the config display line for a thread's opening message."""
    cfg = thread_configs.get(thread_id, {})
    model_label = cfg.get("model_label", "local")
    model_id = cfg.get("model") or model_label
    use_api = cfg.get("use_api", False)
    attunement = cfg.get("attunement", "semi")
    eddy_type = cfg.get("eddy_type", EDDY_DEFAULT)
    context_type = cfg.get("context_type")
    eddy_info = EDDY_TYPES[eddy_type]
    ctx_tag = ""
    if context_type:
        ctx_info = THREAD_CONTEXTS.get(context_type, {})
        ctx_tag = f" · {ctx_info.get('emoji', '📎')} {ctx_info.get('label', context_type)}"
    return f"🧵 `{model_id}` ({'API' if use_api else 'local'}) · `{attunement}` · {eddy_info['emoji']} {eddy_info['label']}{ctx_tag}"


class ThreadConfigView(discord.ui.View):
    """Persistent thread configuration — type buttons. Never disables."""

    def __init__(self, current_type: str = "standard"):
        super().__init__(timeout=None)
        self._current_type = current_type
        for child in self.children:
            cid = child.custom_id or ""
            if cid.startswith("tconfig:"):
                type_key = cid.split(":")[1]
                if type_key in EDDY_TYPES:
                    child.style = (
                        discord.ButtonStyle.primary if type_key == current_type
                        else discord.ButtonStyle.secondary
                    )

    async def _set_type(self, interaction: discord.Interaction, new_type: str):
        thread_id = interaction.channel.id
        cfg = thread_configs.get(thread_id)
        if cfg:
            cfg["eddy_type"] = new_type
        new_view = ThreadConfigView(current_type=new_type)
        config_line = _build_config_line(thread_id)
        await interaction.response.edit_message(content=config_line, view=new_view)

    @discord.ui.button(label="💬 Standard", custom_id="tconfig:standard", style=discord.ButtonStyle.primary, row=0)
    async def standard_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._set_type(interaction, "standard")

    @discord.ui.button(label="🌊 Standing", custom_id="tconfig:standing", style=discord.ButtonStyle.secondary, row=0)
    async def standing_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._set_type(interaction, "standing")

    @discord.ui.button(label="🍃 Manual Release", custom_id="tconfig:manual", style=discord.ButtonStyle.secondary, row=0)
    async def manual_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._set_type(interaction, "manual")


# Keep ThreadTypeView as alias for backward compat with any existing views
ThreadTypeView = ThreadConfigView


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

        history = []
        async for m in thread.history(limit=50, oldest_first=True):
            if m.author == client.user or not m.author.bot:
                history.append({
                    "role": "user" if not m.author.bot else "assistant",
                    "content": m.content[:300],
                })

        from sessions import dissolve_eddy

        result = await dissolve_eddy(self.thread_id, history)
        if not result:
            await interaction.followup.send("Could not archive thread.", ephemeral=True)
            return

        dialogue_histories.pop(self.thread_id, None)
        active_sessions.pop(self.thread_id, None)

        summary = f"📦 **{result.thread_name}** archived"
        if result.entry_count:
            summary += f" — {result.entry_count} entries captured to boom"
        await interaction.followup.send(summary)
        print(f"Thread dissolved & archived: {result.thread_name} ({result.entry_count} boom entries)")

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
    """Sunday sweep — flag standard threads that have been quiet 7+ days.

    Standing threads never dissolve. Manual threads dissolve at session end.
    Standard threads are checked here on Sundays (or on-demand via !eddy-check).
    """
    STANDARD_QUIET_DAYS = 7
    now = datetime.now(timezone.utc)
    newly_flagged = []

    for tid, cfg in list(thread_configs.items()):
        eddy_type = cfg.get("eddy_type", EDDY_DEFAULT)
        if eddy_type != "standard":
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
        if quiet_days >= STANDARD_QUIET_DAYS:
            threads_flagged_for_release[tid] = {
                "flagged_at": now,
                "reason": f"Quiet for {int(quiet_days)}d (standard thread)",
                "thread_name": thread.name,
            }
            newly_flagged.append(thread.name)

            parent = thread.parent or get_channel("dialogue")
            if parent:
                eddy_info = EDDY_TYPES["standard"]
                embed = discord.Embed(
                    title=f"{eddy_info['emoji']} Thread ready to dissolve",
                    description=(
                        f"**{thread.name}** has been quiet for **{int(quiet_days)}d**.\n\n"
                        "What should happen with this thread?"
                    ),
                    color=0xFFA500,
                )
                view = EddyDissolutionView(tid, thread.name)
                await parent.send(embed=embed, view=view)

    return newly_flagged


async def cmd_eddy_check(message, args):
    if get_attunement_profile() != "magic":
        await message.reply(
            "`!eddy-check` is Magic-attuned legacy (metabolic sweep). "
            "Vanilla v1: use `!dissolve` in an eddy when you're done — no auto-dissolve (TURTLE_SPEC §9.2).",
            mention_author=False,
        )
        return
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
    return os.path.join(get_runtime_dir(), "link-resonance")


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
    now = local_now().strftime("%Y-%m-%d %H:%M")
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


def _paste_endpoint_for(url: str) -> str:
    """Build a prefilled paste endpoint link for unfetchable content."""
    return f"{INTAKE_PUBLIC_URL}?{urlencode({'url': url})}"


async def cmd_fetch(message, args):
    if not args:
        await message.reply(
            "Usage: `!fetch <url>` — distill and cache resonance in `link-resonance/`\n"
            "For dialogue read, drop the URL in chat (auto-read) or use **Read article** on incidental links.\n"
            "Copy-paste friendly: `!fetch https://example.com/article`",
            mention_author=False,
        )
        return

    url = args[0].strip("<>")
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        await message.reply(f"Not a valid URL: `{url}`", mention_author=False)
        return

    from url_validate import validate_fetch_url

    blocked = validate_fetch_url(url)
    if blocked:
        await message.reply(
            f"Cannot fetch `{url}` — {blocked}",
            mention_author=False,
        )
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
        embed.set_footer(text="Cached resonance • add --fresh to refetch • drop URL in chat for dialogue read")
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
            paste_url = _paste_endpoint_for(url)
            await message.reply(
                f"\U0001f517 Could not fetch `{url}` ({source_type}).\n"
                f"Paste the text here so Turtle can process it with source context: {paste_url}",
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
    embed.set_footer(text=f"Distilled via {source_type or 'direct'} • cached in link-resonance/ • drop URL in chat for dialogue read")
    await message.reply(embed=embed, mention_author=False)


async def cmd_threads(message, args):
    show_all = "--all" in args
    source = message.channel
    if isinstance(source, discord.Thread):
        source = source.parent

    active_threads = []
    dormant_threads = []
    archived_threads = []
    now = datetime.now(timezone.utc)

    if source and hasattr(source, "threads"):
        for t in source.threads:
            cfg = thread_configs.get(t.id)
            configured = cfg is not None
            age = now - (cfg["created"] if cfg else t.created_at)
            age_days = age.total_seconds() / 86400

            if age.total_seconds() >= 86400:
                age_str = f"{int(age_days)}d"
            elif age.total_seconds() >= 3600:
                age_str = f"{int(age.total_seconds() / 3600)}h"
            else:
                age_str = f"{int(age.total_seconds() / 60)}m"

            eddy_type = cfg.get("eddy_type", EDDY_DEFAULT) if cfg else EDDY_DEFAULT
            eddy_info = EDDY_TYPES[eddy_type]
            flagged = " \u26a0\ufe0f" if t.id in threads_flagged_for_release else ""

            if cfg:
                line = f"{eddy_info['emoji']} **{t.name}** \u2014 `{cfg['model_label']}` / `{cfg['attunement']}` ({age_str}){flagged}"
            else:
                line = f"{eddy_info['emoji']} **{t.name}** \u2014 unconfigured ({age_str}){flagged}"

            if configured or age_days < 7:
                active_threads.append(line)
            elif age_days < 20:
                dormant_threads.append(line)
            else:
                archived_threads.append(line)

    if not active_threads and not dormant_threads:
        await message.reply("No active threads. Use `!thread \"topic\"` to create one.", mention_author=False)
        history = get_history(message.channel.id)
        history.append({"role": "user", "content": "!threads"})
        history.append({"role": "assistant", "content": "[System: No active threads.]"})
        return

    parts = []
    if active_threads:
        parts.extend(active_threads)
    if dormant_threads:
        parts.append("\n\u2500\u2500\u2500 dormant \u2500\u2500\u2500")
        parts.extend(dormant_threads)
    if show_all and archived_threads:
        parts.append("\n\u2500\u2500\u2500 archived \u2500\u2500\u2500")
        parts.extend(archived_threads)

    title = f"\U0001f9f5 Threads \u2014 {len(active_threads)} active"
    if dormant_threads:
        title += f" \u00b7 {len(dormant_threads)} dormant"
    if archived_threads:
        title += f" \u00b7 {len(archived_threads)} archived"

    embed = discord.Embed(
        title=title,
        description="\n".join(parts),
        color=EMBED_COLORS["help"],
    )
    footer = "!thread-type <type> to change | !eddy-check to scan for dissolution"
    if not show_all and archived_threads:
        footer += f" | !threads --all to show {len(archived_threads)} archived"
    embed.set_footer(text=footer)
    await message.reply(embed=embed, mention_author=False)

    thread_summary = "Threads:\n" + "\n".join(parts)
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
async def cmd_checkpoint(message):
    channel_id = message.channel.id
    history = get_history(channel_id)
    if len(history) < MIN_EXCHANGES_FOR_CHECKPOINT:
        await message.reply(
            "Not enough conversation to checkpoint yet.",
            mention_author=False,
        )
        return

    from sessions import checkpoint_session

    result = await checkpoint_session(channel_id, trigger="manual", mark_paused=False)

    if not result.captured_anything:
        await message.reply(
            "Checkpoint ran — nothing new met the save threshold.",
            mention_author=False,
        )
        return

    lines: list[str] = []
    if result.flow_writes:
        lines.append(f"**Flow:** `{result.flow_writes[0]}`")
    if result.session_note:
        lines.append(f"**Session note:** `sessions/{result.session_note}`")
    if result.proposal:
        lines.append(f"**Proposal:** `proposals/{result.proposal}`")

    embed = discord.Embed(
        title="Checkpoint saved",
        description="\n".join(lines),
        color=0x5865F2,
    )
    embed.set_footer(text="History kept — continue when ready, or !release to close.")
    await message.reply(embed=embed, mention_author=False)


async def cmd_release(message):
    channel_id = message.channel.id
    history = get_history(channel_id)
    if len(history) < 2:
        await message.reply("Not enough conversation to release. Just go — rest well.", mention_author=False)
        return

    await message.reply("Closing session...", mention_author=False)
    from sessions import checkpoint_session

    await checkpoint_session(channel_id, trigger="release", mark_paused=True)

    dialogue_histories.pop(channel_id, None)
    active_sessions.pop(channel_id, None)

    embed = discord.Embed(title="Session Released", color=0x2ECC71)
    embed.description = f"Session note written. Conversation history cleared.\nRest well, {get_mage_name()}."

    boom = read_safe(os.path.join(get_pd(), "boom.md"))
    boom_count = count_items(boom)
    if boom_count > 0:
        embed.add_field(name="Note", value=f"Boom has **{boom_count}** items. Consider `!sweep` before you go.", inline=False)

    await message.reply(embed=embed, mention_author=False)


async def cmd_dissolve(message, args):
    """Archive eddy — essence, file archive, chronicle. Distinct from !release."""
    if not isinstance(message.channel, discord.Thread):
        await message.reply(
            "Use `!dissolve` inside an eddy thread to archive it.",
            mention_author=False,
        )
        return
    if not is_practice_channel(message):
        await message.reply("Use `!dissolve` in your practice eddies.", mention_author=False)
        return

    channel_id = message.channel.id
    history = get_history(channel_id)
    from_lifecycle_bar = getattr(message, "from_lifecycle_bar", False)
    discord_client = getattr(message, "discord_client", None)

    if not from_lifecycle_bar:
        await message.reply("Dissolving eddy…", mention_author=False)

    from sessions import dissolve_eddy

    result = await dissolve_eddy(channel_id, history, discord_client=discord_client)
    if not result:
        await message.reply("Could not dissolve — thread not found.", mention_author=False)
        return

    dialogue_histories.pop(channel_id, None)
    active_sessions.pop(channel_id, None)

    lines = [f"**{result.thread_name}** archived."]
    if result.already_archived:
        lines = [f"**{result.thread_name}** is archived — still readable in Discord's thread list."]
    elif result.entry_count:
        lines.append(f"{result.entry_count} entries captured to boom.")
    if result.jump_url and not result.already_archived:
        lines.append(f"Chronicle: {result.jump_url}")
    embed = discord.Embed(
        title="Eddy archived" if result.already_archived else "Eddy dissolved",
        description="\n".join(lines),
        color=0x2ECC71,
    )
    await message.reply(embed=embed, mention_author=False)


async def cmd_flows(message, args):
    """River channel — open flow picker (same as standing bar flow menu)."""
    if isinstance(message.channel, discord.Thread):
        await message.reply(
            "Run `!flows` in the river channel, or use **flow menu** on the standing bar.",
            mention_author=False,
        )
        return
    if not is_practice_channel(message):
        await message.reply("Use `!flows` in your practice river channel.", mention_author=False)
        return

    from flow_runner import list_resolvable_flow_ids
    from river_handler import RiverFlowPickerView

    flows = list_resolvable_flow_ids()
    if not flows:
        await message.reply(
            "No flows installed under your practice root (`flows/`).",
            mention_author=False,
        )
        return

    view = RiverFlowPickerView(message.channel.id, flows)
    client.add_view(view)
    names = ", ".join(f"`{fid.replace('_', ' ').title()}`" for fid in flows[:8])
    extra = f" (+{len(flows) - 8} more)" if len(flows) > 8 else ""
    embed = discord.Embed(
        title="Practice flows",
        description=(
            f"**{len(flows)}** installed flow(s): {names}{extra}\n\n"
            "Pick one to open an eddy (same as **flow menu** on the bar)."
        ),
        color=0x5865F2,
    )
    await message.reply(embed=embed, view=view, mention_author=False)


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
    title = (
        "🌊 Practice substrate"
        if get_mage_type() == "practitioner"
        else "🧭 Practice-Readiness Assessment"
    )
    embed = discord.Embed(
        title=title,
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
            "- `!admin onboard <username> [de|en]` — create hosted river + practitioner workshop\n"
            "- `!admin river-key <name> <emoji> [de|en]` — invite-to-claim room + river key\n",
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

    else:
        await message.reply(f"Unknown admin command: `{subcmd}`. Try `!admin` for help.", mention_author=False)


DIRECT_COMMANDS = {
    "status": lambda msg, args: cmd_status(msg),
    "read": lambda msg, args: cmd_read(msg, args),
    "ls": lambda msg, args: cmd_ls(msg, args),
    "search": lambda msg, args: cmd_search(msg, args),
    "checkpoint": lambda msg, args: cmd_checkpoint(msg),
    "release": lambda msg, args: cmd_release(msg),
    "dissolve": lambda msg, args: cmd_dissolve(msg, args),
    "flows": lambda msg, args: cmd_flows(msg, args),
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
    "diagnose": lambda msg, args: cmd_diagnose(msg),
    "panel": lambda msg, args: cmd_panel(msg),
    "help": lambda msg, args: cmd_help(msg),
    "admin": lambda msg, args: cmd_admin(msg, args),
    "new": lambda msg, args: cmd_new(msg, args),
}

COMMAND_ACT_FALLBACK = {
    "status": "Platform status embed posted (models, uptime, practice root summary).",
    "diagnose": "Stack diagnostic embed posted (canary checks).",
    "help": "Command inventory embed posted.",
    "thread-type": "Eddy type updated.",
    "rename": "Eddy renamed on Discord.",
    "eddy-check": "Eddy dissolution scan completed.",
    "fetch": "URL fetched and distilled to practice library cache.",
    "checkpoint": "Checkpoint complete — flow state and/or session note saved.",
    "release": "Session released — checkpoint saved, history cleared.",
    "dissolve": "Eddy dissolved — thread archived, chronicle updated.",
    "flows": "Flow menu opened.",
    "pin": "Message pinned in river channel.",
    "readiness": "Practice-readiness assessment posted.",
    "read": "Practice file content displayed.",
    "ls": "Practice directory listing displayed.",
    "search": "Practice file search results displayed.",
}


def inject_act_digest(channel_id: int, cmd: str, summary: str) -> None:
    """Record a River act outcome for Turtle dialogue context (not Turtle prose)."""
    text = summary.strip()
    if not text:
        text = COMMAND_ACT_FALLBACK.get(cmd, f"Command `!{cmd}` completed.")
    history = get_history(channel_id)
    history.append({"role": "user", "content": f"[Act: !{cmd}] {text}"})
    if len(history) > MAX_DIALOGUE_HISTORY:
        del history[0 : len(history) - MAX_DIALOGUE_HISTORY]


_PRACTITIONER_COMMANDS = {
    "status", "help", "checkpoint", "release", "dissolve",
    "flows", "pin", "readiness", "rename", "fetch", "read", "ls", "search",
}

CONTEXTUAL_ACTION_TIMEOUT = 3600
CONTEXTUAL_ACTION_COMMANDS = {
    "status", "diagnose", "checkpoint", "release", "dissolve",
    "thread", "new", "threads", "eddy-check", "fetch",
    "absorb", "absorbed", "forget", "readiness", "flows",
}


async def send_with_actions(channel, message: str, actions: list[tuple[str, str]]):
    """Post seneschal act buttons via River (split-bot) or Turtle (single-bot fallback)."""
    from mage import river_bot_enabled

    if river_bot_enabled():
        from river_state import river_client

        client = river_client
    else:
        client = getattr(getattr(channel, "_state", None), "_get_client", lambda: None)()
        if client is None:
            return await channel.send(message)

    from eddy_lifecycle_bar import post_act_suggestion_row

    return await post_act_suggestion_row(channel, message, actions, client)


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
        digest = None
        try:
            result = await handler(message, args)
            if isinstance(result, str) and result.strip():
                digest = result.strip()
        except Exception as e:
            await message.reply(f"Command error: {e}", mention_author=False)
            await log_activity(f"Command `!{cmd}` failed: {e}", "\u274c", channel=message.channel)
            digest = f"Failed: {e}"
        inject_act_digest(message.channel.id, cmd, digest or COMMAND_ACT_FALLBACK.get(cmd, ""))
        return True
    return False


async def dispatch_direct_command(message, *, bar_client=None) -> bool:
    """Execute turtle-talk `!` command, inject act digest, re-anchor bars."""
    if not await try_direct_command(message):
        return False
    from bar_anchor import _is_eddy_thread, ensure_channel_bars

    if _is_eddy_thread(message.channel):
        from eddy_lifecycle_bar import touch_eddy_lifecycle_bar, is_practitioner_input

        await touch_eddy_lifecycle_bar(message, from_practitioner=is_practitioner_input(message))
    await ensure_channel_bars(message.channel, bar_client)
    return True


# ─── Control Panel ───────────────────────────────────────────────

class _InteractionAsMessage:
    def __init__(self, interaction: discord.Interaction):
        self._interaction = interaction
        self._message = interaction.message
        self.channel = interaction.channel
        self.author = interaction.user
        self.content = ""
        self.id = interaction.message.id if interaction.message else interaction.id
        self.guild = interaction.guild
        self._followup_sent = False

    async def create_thread(self, *args, **kwargs):
        if not self._message:
            raise RuntimeError("Contextual action has no source message to create a thread from")
        return await self._message.create_thread(*args, **kwargs)

    async def reply(self, content=None, *, embed=None, mention_author=False, **kwargs):
        send_kwargs = {}
        if content:
            send_kwargs["content"] = content
        if embed:
            send_kwargs["embed"] = embed
        if not send_kwargs:
            return
        try:
            if not self._followup_sent:
                await self._interaction.followup.send(**send_kwargs, ephemeral=True)
                self._followup_sent = True
            else:
                await self._interaction.followup.send(**send_kwargs, ephemeral=True)
        except (discord.NotFound, discord.HTTPException):
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
        eddy_type = getattr(self, "eddy_type", EDDY_DEFAULT)
        eddy_archive = EDDY_TYPES.get(eddy_type, {}).get("archive_minutes", 4320)
        thread = await msg.create_thread(name=topic_val, auto_archive_duration=eddy_archive)

        # Auto-add practitioners to thread
        parent_id = dialogue.id
        for uid in get_thread_member_ids(parent_id):
            try:
                user = await client.fetch_user(int(uid))
                await thread.add_user(user)
            except Exception as e:
                print(f"Could not auto-add user {uid} to thread: {e}")

        thread_configs[thread.id] = {
            "model": model_id,
            "use_api": use_api,
            "attunement": self.attunement,
            "model_label": self.model_str,
            "eddy_type": eddy_type,
            "created": datetime.now(timezone.utc),
        }

        await post_thread_opening(
            thread,
            topic_val,
            origin="control panel thread launcher",
            source_text=f"{topic_val} — {self.model_str} / {self.attunement}",
        )

        config_line = _build_config_line(thread.id)
        view = ThreadConfigView(current_type=eddy_type)
        await thread.send(config_line, view=view)
        await interaction.response.send_message(
            f"Thread **{topic_val}** created (`{self.model_str}` / `{self.attunement}` / `{eddy_type}`).",
            ephemeral=True,
        )
        print(f"Thread created via panel: {topic_val} (model: {model_id}, attunement: {self.attunement}, eddy: {eddy_type})")


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

    @discord.ui.button(label="Release", custom_id="panel:release", style=discord.ButtonStyle.danger, row=4)
    async def release_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await cmd_release(_InteractionAsMessage(interaction))


async def cmd_panel(message):
    embed = discord.Embed(
        title="\U0001f3ae Operator Control Panel",
        description=(
            "**Threads** \u2014 pick model + attunement, then tap New Thread (Appendix A legacy).\n"
            "**Ops** \u2014 status, diagnose, eddy-check.\n"
            "**Session** \u2014 release current eddy (in thread)."
        ),
        color=0x5865F2,
    )
    view = ControlPanelView()
    await message.channel.send(embed=embed, view=view)


async def cmd_new(message, args):
    """Spawn a focused thread from this message: !new [optional topic]"""
    if isinstance(message.channel, discord.Thread):
        await message.reply("Use `!new` in the main channel to spawn a thread.", mention_author=False)
        return

    topic = " ".join(args).strip() if args else None
    thread = await spawn_eddy(message, topic=topic)
    if thread:
        await message.add_reaction("🧵")
    else:
        await message.reply("Could not create thread \u2014 this message may already have one.", mention_author=False)
