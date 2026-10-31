"""Eddy commands (`!eddy`, `!live`, `!rename`), the eddy config view, and the dissolution check."""

from __future__ import annotations

from datetime import datetime, timezone

import discord

from helpers import log_activity
from mage import (
    get_channel_primitive,
    get_pd,
    get_registry,
    get_runtime_dir,
    is_practice_channel,
)
import state
from state import (
    EDDY_DEFAULT,
    EDDY_TYPES,
    THREAD_CONTEXTS,
    active_sessions,
    dialogue_histories,
    get_channel,
    thread_configs,
    threads_flagged_for_release,
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
        thread = state.client.get_channel(self.thread_id)
        if not thread:
            await interaction.followup.send("Thread no longer accessible.", ephemeral=True)
            return

        history = []
        async for m in thread.history(limit=50, oldest_first=True):
            if m.author == state.client.user or not m.author.bot:
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

        thread = state.client.get_channel(tid)
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


def _thread_age_str(created, now):
    age = now - created
    if age.total_seconds() >= 86400:
        return f"{int(age.total_seconds() / 86400)}d"
    if age.total_seconds() >= 3600:
        return f"{int(age.total_seconds() / 3600)}h"
    return f"{int(age.total_seconds() / 60)}m"


def _parse_dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def _glance_line(name: str, age_str: str = "", flagged: bool = False) -> str:
    bits = [f"**{name}**"]
    if age_str:
        bits.append(age_str)
    if flagged:
        bits.append("ready")
    return " · ".join(bits)


def _same_parent(info: dict, parent_name: str | None, parent_id: int | None) -> bool:
    """Registry rows with no parent do not belong on this channel's list."""
    stored_id = info.get("parent_channel_id")
    if stored_id is not None and parent_id is not None:
        try:
            return int(stored_id) == int(parent_id)
        except (TypeError, ValueError):
            return False
    stored_name = info.get("parent_channel")
    if stored_name and parent_name:
        return stored_name == parent_name
    return False


def _aware(dt):
    if dt is None:
        return None
    return dt if getattr(dt, "tzinfo", None) else dt.replace(tzinfo=timezone.utc)


# Discord snowflakes are time-ordered. last_message_id is what the sidebar walks.
_DISCORD_EPOCH_MS = 1_420_070_400_000


def snowflake_unix(snowflake) -> float | None:
    try:
        value = int(snowflake)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return ((value >> 22) + _DISCORD_EPOCH_MS) / 1000.0


def thread_sidebar_rank(thread) -> int:
    """Higher is more recently active — the same walk as Discord's thread list."""
    for attr in ("last_message_id", "id"):
        raw = getattr(thread, attr, None)
        if raw is None:
            continue
        try:
            return int(raw)
        except (TypeError, ValueError):
            continue
    return 0


def collect_five_state_thread_records(
    discord_threads,
    registry_threads: dict,
    *,
    parent_name: str | None,
    parent_id: int | None = None,
    show_all: bool,
    now,
    is_home=None,
):
    """Rows for a glance or a spoken River display. Sidebar recency first."""
    from eddy_five_state import eddy_five_state

    ranked = []
    seen = set()
    now_ts = now.timestamp()
    for t in discord_threads:
        cfg = thread_configs.get(t.id)
        info = registry_threads.get(str(t.id), {})
        rank = thread_sidebar_rank(t)
        snowflake_ts = snowflake_unix(getattr(t, "last_message_id", None) or getattr(t, "id", None))
        last = _aware(
            _parse_dt(info.get("last_activity"))
            or (cfg["created"] if cfg else getattr(t, "created_at", None))
        )
        if snowflake_ts is not None:
            age_seconds = max(0.0, now_ts - snowflake_ts)
            age_str = _thread_age_str(
                datetime.fromtimestamp(snowflake_ts, tz=timezone.utc), now
            )
        else:
            age_str = _thread_age_str(last, now) if last else ""
            age_seconds = (now - last).total_seconds() if last else 1e18
        flagged = t.id in threads_flagged_for_release
        home = bool(is_home(t.id)) if is_home else False
        state = eddy_five_state(
            info,
            discord_archived=bool(getattr(t, "archived", False)),
            discord_locked=bool(getattr(t, "locked", False)),
            is_home=home,
        )
        name = t.name
        ranked.append(
            {
                "state": state,
                "name": name,
                "line": _glance_line(name, age_str, flagged),
                "age_seconds": age_seconds,
                "sidebar_rank": rank,
                "thread_id": str(t.id),
                "flagged": flagged,
            }
        )
        seen.add(str(t.id))

    for tid, info in registry_threads.items():
        if tid in seen:
            continue
        if parent_name or parent_id is not None:
            if not _same_parent(info, parent_name, parent_id):
                continue
        home = bool(is_home(tid)) if is_home else False
        state = eddy_five_state(info, is_home=home)
        if state == "gone" and not show_all:
            continue
        if state == "live" and tid not in seen:
            # Open Discord threads already listed. A live registry row with no
            # Discord handle is stale inventory — skip unless showing all.
            if not show_all:
                continue
        last = _aware(_parse_dt(info.get("last_activity") or info.get("created")))
        age_str = _thread_age_str(last, now) if last else ""
        age_seconds = (now - last).total_seconds() if last else 1e18
        try:
            rank = int(tid)
        except (TypeError, ValueError):
            rank = 0
        name = info.get("name", "unknown")
        ranked.append(
            {
                "state": state,
                "name": name,
                "line": _glance_line(name, age_str),
                "age_seconds": age_seconds,
                "sidebar_rank": rank,
                "thread_id": str(tid),
                "flagged": False,
            }
        )
    ranked.sort(key=lambda row: (-int(row.get("sidebar_rank") or 0), row["age_seconds"]))
    return ranked


def collect_five_state_thread_items(
    discord_threads,
    registry_threads: dict,
    *,
    parent_name: str | None,
    parent_id: int | None = None,
    show_all: bool,
    now,
    is_home=None,
):
    """Build (state, line) rows for !threads. Registry covers resting/gone Discord dropped."""
    records = collect_five_state_thread_records(
        discord_threads,
        registry_threads,
        parent_name=parent_name,
        parent_id=parent_id,
        show_all=show_all,
        now=now,
        is_home=is_home,
    )
    return [(row["state"], row["line"]) for row in records]


# ── The patterns that run differently in each practice (practice_views.py draws them) ──

LIVE_EDDY_LIMIT = 5


def _dates_coming(practice_dir, today, locale: str, days: int = 14) -> list[tuple[str, str]]:
    from datetime import timedelta

    from dates import human_date, list_dates, next_occurrence

    if not practice_dir:
        return []
    out = []
    for entry in list_dates(practice_dir):
        try:
            occurrence = next_occurrence(entry, today=today)
        except ValueError:
            continue
        if today <= occurrence <= today + timedelta(days=days):
            out.append((occurrence, str(entry.get("title") or ""), human_date(occurrence, locale=locale)))
    out.sort()
    return [(title, words) for _, title, words in out]


def place_for(channel, *, user_id=None):
    """The parent channel of wherever the command was typed, with what a surface may read about it."""
    from pathlib import Path

    from practice_views import Place
    from room_models import locale_for
    from thread_registry import load_registry

    parent = channel.parent if isinstance(channel, discord.Thread) else channel
    parent_id = int(getattr(parent, "id", 0) or 0)
    now = datetime.now(timezone.utc)
    threads = load_registry().get("threads", {})
    pd = get_pd()
    try:
        runtime = Path(get_runtime_dir())
    except Exception:
        runtime = None
    locale = locale_for(user_id, get_registry()) if user_id is not None else "en"
    return Place(
        parent=parent,
        parent_id=parent_id,
        name=f"#{getattr(parent, 'name', parent_id)}",
        guild_id=getattr(getattr(parent, "guild", None), "id", None),
        primitive=get_channel_primitive(parent_id),
        practice_dir=Path(pd) if pd else None,
        runtime_dir=runtime,
        locale=locale,
        now=now,
        threads=threads,
        coming=_dates_coming(pd, now.date(), locale),
        records=collect_five_state_thread_records(
            list(getattr(parent, "threads", None) or []),
            threads,
            parent_name=getattr(parent, "name", None),
            parent_id=parent_id,
            show_all=True,
            now=now,
        ),
    )


async def cmd_eddy(message, args):
    """`!eddy`: the latest eddies in this channel, each with what it last held and a link."""
    from practice_views import eddies_view

    place = place_for(message.channel, user_id=message.author.id)
    show_all = any(a.lower() in ("all", "--all") for a in args)
    await message.reply(view=eddies_view(place, show_all=show_all), mention_author=False)
    names = [r["name"] for r in place.records if r["state"] != "gone"][:LIVE_EDDY_LIMIT]
    return "Eddies card posted: " + ", ".join(names) + "." if names else "Eddies card posted (none yet)."


async def cmd_live(message, args):
    """`!live`: what is live in this channel, in the way this practice means it."""
    from practice_views import live_view

    place = place_for(message.channel, user_id=message.author.id)
    await message.reply(view=live_view(place, toward=" ".join(args).strip()), mention_author=False)
    return f"Live state of {place.name} posted."


async def post_channel_glance(channel, *, toward: str = "", user_id=None) -> None:
    """`...` in a channel is the same card as `!live`: where am I, here."""
    from practice_views import live_view

    await channel.send(view=live_view(place_for(channel, user_id=user_id), toward=toward))


async def post_eddies(message, *, days: int | None) -> None:
    """The spoken request ("show me threads from the last 5 days"): the same card as `!eddy`."""
    from practice_views import eddies_view

    place = place_for(message.channel, user_id=getattr(getattr(message, "author", None), "id", None))
    await message.reply(view=eddies_view(place, days=days), mention_author=False)
