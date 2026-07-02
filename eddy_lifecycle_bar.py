"""In-thread lifecycle bar — River-owned checkpoint / release / dissolve affordances."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from urllib.parse import quote, unquote

import discord

_ACT_CUSTOM_ID_PREFIX = "river:act:"
_ACT_CUSTOM_ID_MAX = 100
_PENDING_ACT_COMMANDS: dict[str, str] = {}

DISSOLVE_CONFIRM_TIMEOUT = 15
_revert_tasks: dict[int, asyncio.Task] = {}
_dissolve_in_progress: set[int] = set()


def standing_lifecycle_bar_enabled() -> bool:
    """Standing eddy action bar — flows · checkpoint · share at thread bottom."""
    return True


def is_practitioner_input(message: discord.Message) -> bool:
    """Practitioner activity — includes Spirit bot (dyad partner), excludes other bots."""
    from state import SPIRIT_BOT_ID

    if not message.author.bot:
        return True
    return message.author.id == SPIRIT_BOT_ID


def _is_practitioner_author(message: discord.Message) -> bool:
    return is_practitioner_input(message)


def _state_path() -> str:
    from mage import get_runtime_dir

    bar_dir = os.path.join(get_runtime_dir(), "thread-state", "eddy")
    os.makedirs(bar_dir, exist_ok=True)
    return os.path.join(bar_dir, "lifecycle_bar.json")


def _load_state() -> dict[str, int]:
    path = _state_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return {str(k): int(v) for k, v in data.items()}
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


def _save_state(state: dict[str, int]) -> None:
    with open(_state_path(), "w", encoding="utf-8") as fh:
        json.dump(state, fh)


def is_lifecycle_bar_active(thread_id: int) -> bool:
    return str(thread_id) in _load_state()


def _mark_bar_message(thread_id: int, message_id: int) -> None:
    state = _load_state()
    state[str(thread_id)] = message_id
    _save_state(state)


def clear_lifecycle_bar_state(thread_id: int) -> None:
    state = _load_state()
    if state.pop(str(thread_id), None) is not None:
        _save_state(state)
    clear_bar_phase(thread_id)


def _phase_state_path() -> str:
    from mage import get_runtime_dir

    bar_dir = os.path.join(get_runtime_dir(), "thread-state", "eddy")
    os.makedirs(bar_dir, exist_ok=True)
    return os.path.join(bar_dir, "bar_phase.json")


def _load_phase_state() -> dict[str, str]:
    path = _phase_state_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return {str(k): str(v) for k, v in data.items()}
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


def _save_phase_state(state: dict[str, str]) -> None:
    with open(_phase_state_path(), "w", encoding="utf-8") as fh:
        json.dump(state, fh)


def get_bar_phase(thread_id: int) -> str | None:
    phase = _load_phase_state().get(str(thread_id))
    if phase in ("bootstrap", "live"):
        return phase
    return None


def set_bar_phase(thread_id: int, phase: str) -> None:
    if phase not in ("bootstrap", "live"):
        return
    state = _load_phase_state()
    state[str(thread_id)] = phase
    _save_phase_state(state)


def clear_bar_phase(thread_id: int) -> None:
    state = _load_phase_state()
    if state.pop(str(thread_id), None) is not None:
        _save_phase_state(state)


def bootstrap_bar_eligible(thread_id: int, parent_id: int | None) -> bool:
    """Phase 0 bar — flows select on empty eddy (may be awaiting first message)."""
    if not standing_lifecycle_bar_enabled():
        return False
    if not parent_id:
        return False
    from eddy_spawn import is_awaiting_flow_intake
    from prompts import uses_native_turtle_prompt

    if not uses_native_turtle_prompt(parent_id):
        return False
    if is_awaiting_flow_intake(thread_id, parent_id):
        return False
    return True


def lifecycle_bar_eligible(thread_id: int, parent_id: int | None) -> bool:
    """Phase 1+ bar — checkpoint/share need live dialogue (not pre-first-message)."""
    if not standing_lifecycle_bar_enabled():
        return False
    if not parent_id:
        return False
    from eddy_spawn import is_awaiting_flow_intake, is_awaiting_title
    from prompts import uses_native_turtle_prompt

    if not uses_native_turtle_prompt(parent_id):
        return False
    if is_awaiting_flow_intake(thread_id, parent_id):
        return False
    if is_awaiting_title(thread_id, parent_id):
        return False
    return True


def _bar_eligible_for_phase(thread_id: int, parent_id: int | None, phase: str) -> bool:
    if phase == "bootstrap":
        return bootstrap_bar_eligible(thread_id, parent_id)
    return lifecycle_bar_eligible(thread_id, parent_id)


def _flow_display_name(flow_id: str) -> str:
    return flow_id.replace("_", " ").title()


def get_lifecycle_bar_client(thread: discord.Thread):
    from mage import river_bot_enabled

    if river_bot_enabled():
        from river_state import river_client

        if getattr(river_client, "is_ready", lambda: False)():
            return river_client
        return None
    if thread.guild:
        return thread.guild._state._get_client()
    return None


class _LifecycleInteractionMessage:
    """Adapter so lifecycle buttons run the same handlers as turtle-talk (public replies)."""

    def __init__(
        self,
        interaction: discord.Interaction,
        command: str,
        *,
        from_lifecycle_bar: bool = False,
    ):
        self._interaction = interaction
        self.channel = interaction.channel
        self.author = interaction.user
        self.content = command
        self.id = interaction.message.id if interaction.message else interaction.id
        self.guild = interaction.guild
        self._sent = False
        self.discord_client = interaction.client
        self.from_lifecycle_bar = from_lifecycle_bar

    async def reply(self, content=None, *, embed=None, mention_author=False, **kwargs):
        send_kwargs = {}
        if content:
            send_kwargs["content"] = content
        if embed:
            send_kwargs["embed"] = embed
        send_kwargs.update(kwargs)
        if not send_kwargs:
            return
        if not self._sent:
            await self._interaction.followup.send(**send_kwargs)
            self._sent = True
        else:
            await self._interaction.followup.send(**send_kwargs)

    async def add_reaction(self, emoji):
        pass


def _encode_act_custom_id(channel_id: int, command: str) -> str | None:
    """Encode a turtle-talk command in a persistent River button custom_id."""
    cmd_text = command.lstrip("!")
    encoded = quote(cmd_text, safe="")
    custom_id = f"{_ACT_CUSTOM_ID_PREFIX}{channel_id}:{encoded}"
    if len(custom_id) <= _ACT_CUSTOM_ID_MAX:
        return custom_id
    digest = hashlib.sha256(cmd_text.encode()).hexdigest()[:16]
    key = f"{channel_id}:{digest}"
    _PENDING_ACT_COMMANDS[key] = cmd_text
    hashed = f"{_ACT_CUSTOM_ID_PREFIX}{channel_id}:h:{digest}"
    if len(hashed) > _ACT_CUSTOM_ID_MAX:
        return None
    return hashed


def _decode_act_custom_id(custom_id: str) -> tuple[int, str]:
    if not custom_id.startswith(_ACT_CUSTOM_ID_PREFIX):
        raise ValueError(f"Not an act button: {custom_id!r}")
    rest = custom_id[len(_ACT_CUSTOM_ID_PREFIX) :]
    channel_id_str, _, encoded = rest.partition(":")
    if not channel_id_str:
        raise ValueError(f"Malformed act button id: {custom_id!r}")
    if encoded.startswith("h:"):
        digest = encoded[2:]
        cmd = _PENDING_ACT_COMMANDS.get(f"{channel_id_str}:{digest}")
        if not cmd:
            raise ValueError(f"Expired act button: {custom_id!r}")
        return int(channel_id_str), cmd
    if not encoded:
        raise ValueError(f"Malformed act button id: {custom_id!r}")
    return int(channel_id_str), unquote(encoded)


def _parse_act_command(command: str) -> tuple[str, list[str]]:
    text = command.strip()
    if text.startswith("!"):
        text = text[1:]
    parts = text.split(None, 1)
    cmd = parts[0].lower() if parts else ""
    args = parts[1].split() if len(parts) > 1 else []
    return cmd, args


async def _run_river_act_command(
    interaction: discord.Interaction,
    cmd: str,
    args: list[str] | None = None,
    *,
    from_lifecycle_bar: bool = False,
) -> None:
    """Execute a turtle-talk command from a River-owned button (public timeline replies)."""
    from commands import COMMAND_ACT_FALLBACK, DIRECT_COMMANDS, inject_act_digest
    from helpers import log_activity
    from mage import set_practice_context_for_channel

    parent_id = interaction.channel.parent_id if isinstance(interaction.channel, discord.Thread) else None
    if parent_id:
        set_practice_context_for_channel(parent_id)
    elif interaction.channel:
        set_practice_context_for_channel(interaction.channel.id)

    handler = DIRECT_COMMANDS.get(cmd)
    if not handler:
        await interaction.followup.send(f"Unknown command `{cmd}`.", ephemeral=True)
        return

    msg = _LifecycleInteractionMessage(
        interaction,
        f"!{cmd}",
        from_lifecycle_bar=from_lifecycle_bar,
    )
    digest = None
    try:
        result = await handler(msg, args or [])
        if isinstance(result, str) and result.strip():
            digest = result.strip()
    except Exception as exc:
        await interaction.followup.send(f"Command error: {exc}", mention_author=False)
        await log_activity(f"Act `!{cmd}` failed: {exc}", "\u274c", channel=interaction.channel)
        inject_act_digest(interaction.channel.id, cmd, f"Failed: {exc}")
        return

    inject_act_digest(interaction.channel.id, cmd, digest or COMMAND_ACT_FALLBACK.get(cmd, ""))

    from cmd_dispatch import INTERACTIVE_COMMANDS_DEFER_BAR

    if cmd not in INTERACTIVE_COMMANDS_DEFER_BAR:
        from bar_anchor import ensure_channel_bars

        await ensure_channel_bars(interaction.channel, interaction.client)

    # Act digest is enough for Turtle context — skip channel ops embed on success
    # (it sandwiched the standing bar between command output and practitioner UI).


async def _run_lifecycle_command(
    interaction: discord.Interaction,
    cmd: str,
    args: list[str] | None = None,
) -> None:
    await _run_river_act_command(
        interaction,
        cmd,
        args,
        from_lifecycle_bar=True,
    )


def _cancel_confirm_revert(thread_id: int) -> None:
    task = _revert_tasks.pop(thread_id, None)
    if task and not task.done():
        task.cancel()


async def _revert_confirm_after(
    thread_id: int,
    message_id: int,
    client,
    *,
    delay: int = DISSOLVE_CONFIRM_TIMEOUT,
) -> None:
    try:
        await asyncio.sleep(delay)
        thread = await client.fetch_channel(thread_id)
        if not isinstance(thread, discord.Thread):
            return
        bar_msg = await thread.fetch_message(message_id)
        custom_ids = {
            getattr(c, "custom_id", None)
            for row in (bar_msg.components or [])
            for c in getattr(row, "children", [])
        }
        if not any(cid and cid.startswith("eddy:lifecycle:confirm:") for cid in custom_ids):
            return
        parent_id = thread.parent_id
        phase = get_bar_phase(thread_id) or "live"
        if parent_id:
            view = EddyLifecycleBarView(thread_id, parent_id, phase=phase)
        else:
            view = EddyLifecycleBarView(thread_id, 0, phase=phase)
        client.add_view(view)
        await bar_msg.edit(content="\u200b", view=view)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        print(f"Dissolve confirm timeout revert failed: {type(exc).__name__}: {exc}")
    finally:
        _revert_tasks.pop(thread_id, None)


def _schedule_confirm_revert(interaction: discord.Interaction, thread_id: int) -> None:
    if not interaction.message:
        return
    _cancel_confirm_revert(thread_id)
    task = asyncio.create_task(
        _revert_confirm_after(thread_id, interaction.message.id, interaction.client)
    )
    _revert_tasks[thread_id] = task


class EddyLifecycleBarView(discord.ui.View):
    """Phased eddy bar — bootstrap: flow select only; live: flows + checkpoint + share."""

    def __init__(self, thread_id: int, parent_id: int, *, phase: str = "live"):
        super().__init__(timeout=None)
        self._thread_id = thread_id
        self._parent_id = parent_id
        self._phase = phase if phase in ("bootstrap", "live") else "live"

        from flow_runner import list_flow_ids_for_bar_phase

        flow_ids = list_flow_ids_for_bar_phase(self._phase)
        if flow_ids:
            placeholder = (
                "Load a guided flow…"
                if self._phase == "bootstrap"
                else "Load or switch flow…"
            )
            options = [
                discord.SelectOption(label=_flow_display_name(fid)[:100], value=fid)
                for fid in flow_ids[:25]
            ]
            select = discord.ui.Select(
                placeholder=placeholder,
                options=options,
                custom_id=f"eddy:lifecycle:flowpick:{thread_id}",
            )
            select.callback = self._on_flow_pick
            self.add_item(select)

        if self._phase == "live":
            checkpoint_btn = discord.ui.Button(
                label="checkpoint",
                custom_id=f"eddy:lifecycle:checkpoint:{thread_id}",
                style=discord.ButtonStyle.secondary,
                emoji="💾",
            )
            checkpoint_btn.callback = self._on_checkpoint
            self.add_item(checkpoint_btn)

            share_btn = discord.ui.Button(
                label="share",
                custom_id=f"eddy:lifecycle:share:{thread_id}",
                style=discord.ButtonStyle.secondary,
                emoji="📤",
            )
            share_btn.callback = self._on_share
            self.add_item(share_btn)

    async def _on_flow_pick(self, interaction: discord.Interaction):
        values = interaction.data.get("values") or []
        flow_id = values[0] if values else None
        if not flow_id:
            await interaction.response.send_message("No flow selected.", ephemeral=True)
            return
        thread = interaction.channel
        if not isinstance(thread, discord.Thread) or thread.id != self._thread_id:
            await interaction.response.send_message("Open this from the eddy thread.", ephemeral=True)
            return
        await interaction.response.defer()
        from eddy_flow_library import _complete_flow_pick

        await _complete_flow_pick(
            interaction,
            thread_id=self._thread_id,
            parent_id=self._parent_id,
            flow_id=flow_id,
            dismiss_message=False,
        )
        from bar_anchor import ensure_channel_bars

        await ensure_channel_bars(thread, interaction.client)

    async def _on_checkpoint(self, interaction: discord.Interaction):
        if interaction.channel.id != self._thread_id:
            await interaction.response.send_message("Wrong thread.", ephemeral=True)
            return
        await interaction.response.defer()
        await _run_lifecycle_command(interaction, "checkpoint")

    async def _on_share(self, interaction: discord.Interaction):
        if interaction.channel.id != self._thread_id:
            await interaction.response.send_message("Wrong thread.", ephemeral=True)
            return
        await interaction.response.defer()
        await _run_lifecycle_command(interaction, "share")


class EddyDissolveConfirmView(discord.ui.View):
    """Two-step dissolve — archive + explicit cancel + timed revert."""

    def __init__(self, thread_id: int):
        super().__init__(timeout=None)
        self._thread_id = thread_id

        archive_btn = discord.ui.Button(
            label="Archive this eddy?",
            custom_id=f"eddy:lifecycle:confirm:{thread_id}",
            style=discord.ButtonStyle.danger,
        )
        archive_btn.callback = self._on_confirm
        self.add_item(archive_btn)

        cancel_btn = discord.ui.Button(
            label="Cancel",
            custom_id=f"eddy:lifecycle:cancel:{thread_id}",
            style=discord.ButtonStyle.secondary,
        )
        cancel_btn.callback = self._on_cancel
        self.add_item(cancel_btn)

    async def _on_cancel(self, interaction: discord.Interaction):
        _cancel_confirm_revert(self._thread_id)
        thread = interaction.channel
        parent_id = thread.parent_id if isinstance(thread, discord.Thread) else 0
        phase = get_bar_phase(self._thread_id) or "live"
        view = EddyLifecycleBarView(self._thread_id, parent_id or 0, phase=phase)
        interaction.client.add_view(view)
        await interaction.response.edit_message(content="\u200b", view=view)

    async def _on_confirm(self, interaction: discord.Interaction):
        if interaction.channel.id != self._thread_id:
            await interaction.response.send_message("Wrong thread.", ephemeral=True)
            return
        if self._thread_id in _dissolve_in_progress:
            await interaction.response.send_message("Already archiving…", ephemeral=True)
            return
        _dissolve_in_progress.add(self._thread_id)
        _cancel_confirm_revert(self._thread_id)
        try:
            await interaction.response.defer()
            await _run_lifecycle_command(interaction, "dissolve")
            clear_lifecycle_bar_state(self._thread_id)
            try:
                if interaction.message:
                    await interaction.message.delete()
            except discord.HTTPException:
                pass
        finally:
            _dissolve_in_progress.discard(self._thread_id)


async def _post_eddy_bar(
    thread: discord.Thread,
    client,
    *,
    phase: str,
) -> discord.Message | None:
    if not standing_lifecycle_bar_enabled():
        return None
    parent_id = thread.parent_id
    if not parent_id or not _bar_eligible_for_phase(thread.id, parent_id, phase):
        return None

    from flow_runner import list_flow_ids_for_bar_phase

    if not list_flow_ids_for_bar_phase(phase):
        return None

    from bar_anchor import channel_for_client

    ch = await channel_for_client(thread, client)
    view = EddyLifecycleBarView(ch.id, parent_id, phase=phase)
    if not view.children:
        return None
    try:
        msg = await ch.send("\u200b", view=view, silent=True)
    except discord.HTTPException as exc:
        print(f"Lifecycle bar post failed for {ch.id}: {type(exc).__name__}: {exc}")
        return None
    _mark_bar_message(ch.id, msg.id)
    set_bar_phase(ch.id, phase)
    client.add_view(view)
    return msg


async def post_eddy_bootstrap_bar(
    thread: discord.Thread,
    client,
) -> discord.Message | None:
    """Phase 0 — filtered flow select on empty eddy."""
    return await _post_eddy_bar(thread, client, phase="bootstrap")


async def post_eddy_lifecycle_bar(
    thread: discord.Thread,
    client,
) -> discord.Message | None:
    """Phase 1 — full bar after practitioner content."""
    return await _post_eddy_bar(thread, client, phase="live")


async def upgrade_eddy_bar_to_live(thread: discord.Thread, client) -> None:
    """Expand bootstrap bar to live phase after first practitioner message."""
    parent_id = thread.parent_id
    if not parent_id:
        return
    set_bar_phase(thread.id, "live")
    from bar_anchor import channel_for_client

    ch = await channel_for_client(thread, client)
    state = _load_state()
    bar_id = state.get(str(ch.id))
    view = EddyLifecycleBarView(ch.id, parent_id, phase="live")
    if not view.children:
        return
    client.add_view(view)
    if bar_id:
        try:
            bar_msg = await ch.fetch_message(bar_id)
            await bar_msg.edit(content="\u200b", view=view)
            print(f"Lifecycle bar upgraded to live in #{getattr(ch, 'name', ch.id)} ({ch.id})")
            return
        except discord.HTTPException:
            pass
    await _post_eddy_bar(ch, client, phase="live")


async def ensure_eddy_lifecycle_bar_at_bottom(
    thread: discord.Thread,
    client=None,
) -> None:
    from state import get_channel_lock

    lock = get_channel_lock(thread.id)
    async with lock:
        await _ensure_eddy_lifecycle_bar_at_bottom_unlocked(thread, client)


async def _ensure_eddy_lifecycle_bar_at_bottom_unlocked(
    thread: discord.Thread,
    client=None,
) -> None:
    parent_id = getattr(thread, "parent_id", None)
    if not parent_id or not is_lifecycle_bar_active(thread.id):
        return
    phase = get_bar_phase(thread.id) or "live"
    if not _bar_eligible_for_phase(thread.id, parent_id, phase):
        return

    client = client or get_lifecycle_bar_client(thread)
    if not client:
        return

    from bar_anchor import channel_for_client

    ch = await channel_for_client(thread, client)
    state = _load_state()
    bar_id = state.get(str(ch.id))
    if bar_id:
        try:
            bar_msg = await ch.fetch_message(bar_id)
            async for last in ch.history(limit=1):
                if last.id == bar_id:
                    view = EddyLifecycleBarView(ch.id, parent_id, phase=phase)
                    client.add_view(view)
                    try:
                        await bar_msg.edit(view=view)
                    except discord.HTTPException:
                        pass
                    return
            try:
                await bar_msg.delete()
            except discord.HTTPException:
                pass
        except discord.HTTPException:
            pass

    msg = await _post_eddy_bar(ch, client, phase=phase)
    if msg:
        print(f"Lifecycle bar reposted in #{getattr(ch, 'name', ch.id)} ({ch.id})")


async def touch_eddy_lifecycle_bar(
    message: discord.Message,
    *,
    from_practitioner: bool = False,
) -> None:
    """Post bootstrap bar on materialize; upgrade to live on first practitioner activity."""
    if not standing_lifecycle_bar_enabled():
        return
    if not isinstance(message.channel, discord.Thread):
        return
    thread = message.channel
    parent_id = thread.parent_id
    if not parent_id:
        return
    phase = get_bar_phase(thread.id)
    if phase == "bootstrap":
        if not bootstrap_bar_eligible(thread.id, parent_id):
            return
    elif phase == "live":
        if not lifecycle_bar_eligible(thread.id, parent_id):
            return
    elif not bootstrap_bar_eligible(thread.id, parent_id) and not lifecycle_bar_eligible(
        thread.id, parent_id
    ):
        return

    client = get_lifecycle_bar_client(thread)
    if not client:
        return

    from state import get_channel_lock

    lock = get_channel_lock(thread.id)
    async with lock:
        await _touch_eddy_lifecycle_bar_unlocked(message, from_practitioner=from_practitioner)


async def _touch_eddy_lifecycle_bar_unlocked(
    message: discord.Message,
    *,
    from_practitioner: bool = False,
) -> None:
    if not isinstance(message.channel, discord.Thread):
        return
    thread = message.channel
    parent_id = thread.parent_id
    if not parent_id:
        return

    client = get_lifecycle_bar_client(thread)
    if not client:
        return

    if from_practitioner and _is_practitioner_author(message):
        phase = get_bar_phase(thread.id)
        if phase == "bootstrap":
            await upgrade_eddy_bar_to_live(thread, client)
            await _ensure_eddy_lifecycle_bar_at_bottom_unlocked(thread, client)
            return
        if not is_lifecycle_bar_active(thread.id) and lifecycle_bar_eligible(thread.id, parent_id):
            msg = await post_eddy_lifecycle_bar(thread, client)
            if msg:
                print(f"Lifecycle bar activated in #{thread.name} ({thread.id})")
            return

    if is_lifecycle_bar_active(thread.id):
        await _ensure_eddy_lifecycle_bar_at_bottom_unlocked(thread, client)


async def handle_lifecycle_bar_interaction(interaction: discord.Interaction) -> bool:
    """Fallback router — prefer view callbacks registered via add_view."""
    return False


class RiverActSuggestionView(discord.ui.View):
    """River-owned seneschal act row — same execution path as the lifecycle bar."""

    def __init__(self, channel_id: int, actions: list[tuple[str, str]]):
        super().__init__(timeout=None)
        self._channel_id = channel_id
        from commands import CONTEXTUAL_ACTION_COMMANDS

        for label, command in actions[:3]:
            cmd, _ = _parse_act_command(command)
            if cmd not in CONTEXTUAL_ACTION_COMMANDS:
                continue
            custom_id = _encode_act_custom_id(channel_id, command)
            if not custom_id:
                print(f"Act button skipped — command too long for custom_id: {command[:60]}...")
                continue
            button = discord.ui.Button(
                label=label[:80],
                custom_id=custom_id,
                style=discord.ButtonStyle.secondary,
            )
            button.callback = self._make_callback(custom_id)
            self.add_item(button)

    def _make_callback(self, custom_id: str):
        async def callback(interaction: discord.Interaction):
            if interaction.channel.id != self._channel_id:
                await interaction.response.send_message("Wrong channel.", ephemeral=True)
                return
            try:
                _, command = _decode_act_custom_id(custom_id)
            except ValueError:
                await interaction.response.send_message("This action expired.", ephemeral=True)
                return
            cmd, args = _parse_act_command(command)
            await interaction.response.defer()
            await _run_river_act_command(interaction, cmd, args)
            for child in self.children:
                child.disabled = True
            try:
                if interaction.message:
                    await interaction.message.edit(view=self)
            except discord.HTTPException:
                pass

        return callback


async def post_act_suggestion_row(
    channel,
    actions: list[tuple[str, str]],
    client,
    *,
    description: str | None = None,
    content: str | None = None,
) -> discord.Message | None:
    """Post River-owned act buttons — embed hint (native) or legacy content line."""
    from bar_anchor import channel_for_client

    ch = await channel_for_client(channel, client)
    view = RiverActSuggestionView(ch.id, actions)
    if not view.children:
        return None
    client.add_view(view)
    embed = None
    send_content = "\u200b"
    if description:
        from bar_anchor import RIVER_OFFER_EMBED_COLOR

        embed = discord.Embed(description=description, color=RIVER_OFFER_EMBED_COLOR)
    elif content:
        send_content = content
    try:
        msg = await ch.send(send_content, embed=embed, view=view, silent=True)
        bot_name = getattr(getattr(client, "user", None), "name", "?")
        print(f"Seneschal row posted as {bot_name} in #{getattr(ch, 'name', ch.id)}")
        return msg
    except discord.HTTPException as exc:
        print(f"Act suggestion row failed for {ch.id}: {type(exc).__name__}: {exc}")
        return None
