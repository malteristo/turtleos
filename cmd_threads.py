"""Thread and eddy commands, config views, and Magic-attuned control panel."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import discord

from eddy_spawn import post_thread_opening, spawn_eddy
from helpers import get_history, log_activity
from llm import resolve_model
from mage import (
    get_attunement_profile,
    get_thread_member_ids,
    is_practice_channel,
)
from state import (
    EDDY_DEFAULT,
    EDDY_TYPES,
    EMBED_COLORS,
    THREAD_CONTEXTS,
    active_sessions,
    client,
    dialogue_histories,
    get_channel,
    panel_selections,
    thread_configs,
    threads_flagged_for_release,
    ATTUNEMENT_LEVELS,
)


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

    model_match = re.search(r"--model\s+(\S+)", raw)
    model_str = model_match.group(1) if model_match else "local"

    attunement_match = re.search(r"--attunement\s+(\S+)", raw)
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

    type_match = re.search(r"--type\s+(\S+)", raw)
    eddy_type = type_match.group(1) if type_match else EDDY_DEFAULT
    if eddy_type not in EDDY_TYPES:
        await message.reply(
            f"Unknown eddy type `{eddy_type}`. Use: {', '.join(sorted(EDDY_TYPES))}",
            mention_author=False,
        )
        return

    context_match = re.search(r"--context\s+(\S+)", raw)
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

    config_line = build_config_line(thread.id)
    view = ThreadConfigView(current_type=eddy_type)
    await thread.send(config_line, view=view)
    # Parent river feedback: Opened eddy act posts from on_thread_create (discord_reconcile).


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
        await message.reply(
            f"Unknown type `{new_type}`. Use: {', '.join(sorted(EDDY_TYPES))}",
            mention_author=False,
        )
        return
    cfg = thread_configs.get(message.channel.id)
    if cfg:
        old_type = cfg.get("eddy_type", EDDY_DEFAULT)
        cfg["eddy_type"] = new_type
    else:
        old_type = EDDY_DEFAULT
        thread_configs[message.channel.id] = {
            "model": None,
            "use_api": False,
            "attunement": "semi",
            "model_label": "local",
            "eddy_type": new_type,
            "created": message.channel.created_at or datetime.now(timezone.utc),
        }
    info = EDDY_TYPES[new_type]
    old_info = EDDY_TYPES[old_type]
    await message.reply(
        f"{old_info['emoji']} → {info['emoji']} Thread type changed to **{info['label']}**",
        mention_author=False,
    )
    await log_activity(
        f"Thread **{message.channel.name}** type: `{old_type}` → `{new_type}`",
        info["emoji"],
        channel=message.channel,
    )


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


def build_config_line(thread_id: int) -> str:
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
    return (
        f"🧵 `{model_id}` ({'API' if use_api else 'local'}) · `{attunement}` · "
        f"{eddy_info['emoji']} {eddy_info['label']}{ctx_tag}"
    )


_build_config_line = build_config_line


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
                        discord.ButtonStyle.primary
                        if type_key == current_type
                        else discord.ButtonStyle.secondary
                    )

    async def _set_type(self, interaction: discord.Interaction, new_type: str):
        thread_id = interaction.channel.id
        cfg = thread_configs.get(thread_id)
        if cfg:
            cfg["eddy_type"] = new_type
        new_view = ThreadConfigView(current_type=new_type)
        config_line = build_config_line(thread_id)
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
                history.append(
                    {
                        "role": "user" if not m.author.bot else "assistant",
                        "content": m.content[:300],
                    }
                )

        from share_eddy import check_share_dissolve_authority

        auth = check_share_dissolve_authority(
            self.thread_id,
            thread.parent_id if thread.parent else None,
            interaction.user.id,
        )
        if not auth.allowed:
            await interaction.followup.send(auth.reason or "You cannot dissolve this eddy.", ephemeral=True)
            return

        from runtime.adapters.lifecycle import close_eddy

        result = await close_eddy(
            self.thread_id,
            history,
            source="command",
            discord_client=interaction.client,
            parent_channel_id=thread.parent_id if thread.parent else None,
        )
        if not result:
            await interaction.followup.send("Could not archive thread.", ephemeral=True)
            return

        dialogue_histories.pop(self.thread_id, None)
        active_sessions.pop(self.thread_id, None)

        summary = f"📦 **{result.thread_name}** archived"
        if result.entry_count:
            summary += f" — {result.entry_count} insights archived"
        await interaction.followup.send(summary)
        print(f"Thread dissolved & archived: {result.thread_name} ({result.entry_count} insights archived)")

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
                "model": None,
                "use_api": False,
                "attunement": "semi",
                "model_label": "local",
                "eddy_type": "standing",
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
    """Sunday sweep — flag standard threads quiet 7+ days (Magic-attuned legacy)."""
    standard_quiet_days = 7
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
        if quiet_days >= standard_quiet_days:
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
    await message.reply(
        "`!eddy-check` is retired. Use `!dissolve` in an eddy when you're done.",
        mention_author=False,
    )


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
                line = (
                    f"{eddy_info['emoji']} **{t.name}** \u2014 "
                    f"`{cfg['model_label']}` / `{cfg['attunement']}` ({age_str}){flagged}"
                )
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

    from thread_registry import load_registry

    parent_id = str(source.id) if source else None
    cooled_lines = []
    for tid, info in load_registry().get("threads", {}).items():
        if info.get("harvest_status") != "cooled":
            continue
        if parent_id and info.get("parent_channel") and info.get("parent_channel") != getattr(source, "name", None):
            continue
        keep_tag = " · 📌" if info.get("continuity") == "keep" else ""
        cooled_lines.append(
            f"\U0001f9ca **{info.get('name', 'unknown')}** — auto-archived{keep_tag} · id:{tid}"
        )
    if cooled_lines:
        parts.append("\n\u2500\u2500\u2500 cooled (auto-archived) \u2500\u2500\u2500")
        parts.extend(cooled_lines)

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
    footer = "!thread-type <type> to change | !eddy-check to scan for dissolution | !keep / !ignore"
    if not show_all and archived_threads:
        footer += f" | !threads --all to show {len(archived_threads)} archived"
    embed.set_footer(text=footer)
    await message.reply(embed=embed, mention_author=False)

    thread_summary = "Threads:\n" + "\n".join(parts)
    history = get_history(message.channel.id)
    history.append({"role": "user", "content": "!threads"})
    history.append({"role": "assistant", "content": f"[System: {thread_summary}]"})


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

        config_line = build_config_line(thread.id)
        view = ThreadConfigView(current_type=eddy_type)
        await thread.send(config_line, view=view)
        await interaction.response.send_message(
            f"Thread **{topic_val}** created (`{self.model_str}` / `{self.attunement}` / `{eddy_type}`).",
            ephemeral=True,
        )
        print(
            f"Thread created via panel: {topic_val} "
            f"(model: {model_id}, attunement: {self.attunement}, eddy: {eddy_type})"
        )


class ControlPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        custom_id="panel:model",
        placeholder="Model: claude (default)",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(
                label="claude", description="Flagship API (claude-sonnet-4-6)", value="claude", default=True
            ),
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
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(
                label="deep", description="Full practice context + soul", value="deep", default=True
            ),
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
        from commands import cmd_status

        await interaction.response.defer(ephemeral=True)
        await cmd_status(_InteractionAsMessage(interaction))

    @discord.ui.button(label="Diagnose", custom_id="panel:diagnose", style=discord.ButtonStyle.secondary, row=3)
    async def diagnose_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        from commands import cmd_diagnose

        await interaction.response.defer(ephemeral=True)
        await cmd_diagnose(_InteractionAsMessage(interaction))

    @discord.ui.button(label="Release", custom_id="panel:release", style=discord.ButtonStyle.danger, row=4)
    async def release_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        from cmd_sessions import cmd_release

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
