"""In-thread lifecycle bar — River-owned checkpoint / release / dissolve affordances."""

from __future__ import annotations

import asyncio
import json
import os

import discord

DISSOLVE_CONFIRM_TIMEOUT = 15
SPIRIT_BOT_ID = 1487405701440733294
_revert_tasks: dict[int, asyncio.Task] = {}
_dissolve_in_progress: set[int] = set()


def _is_practitioner_author(message: discord.Message) -> bool:
    """Practitioner activity — includes Spirit bot (dyad partner), excludes other bots."""
    if not message.author.bot:
        return True
    return message.author.id == SPIRIT_BOT_ID


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


def lifecycle_bar_eligible(thread_id: int, parent_id: int | None) -> bool:
    """True when the eddy is live enough for lifecycle controls."""
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


def get_lifecycle_bar_client(thread: discord.Thread):
    from mage import river_bot_enabled

    if river_bot_enabled():
        from river_state import river_client

        return river_client
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
        if not send_kwargs:
            return
        if not self._sent:
            await self._interaction.followup.send(**send_kwargs)
            self._sent = True
        else:
            await self._interaction.followup.send(**send_kwargs)

    async def add_reaction(self, emoji):
        pass


async def _run_lifecycle_command(
    interaction: discord.Interaction,
    cmd: str,
    args: list[str] | None = None,
) -> None:
    from commands import DIRECT_COMMANDS
    from mage import set_practice_context_for_channel

    parent_id = interaction.channel.parent_id if isinstance(interaction.channel, discord.Thread) else None
    if parent_id:
        set_practice_context_for_channel(parent_id)

    handler = DIRECT_COMMANDS.get(cmd)
    if not handler:
        await interaction.followup.send(f"Unknown command `{cmd}`.", ephemeral=True)
        return
    msg = _LifecycleInteractionMessage(
        interaction,
        f"!{cmd}",
        from_lifecycle_bar=True,
    )
    await handler(msg, args or [])


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
        view = EddyLifecycleBarView(thread_id)
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
    """Normal lifecycle row — checkpoint, release, dissolve."""

    def __init__(self, thread_id: int):
        super().__init__(timeout=None)
        self._thread_id = thread_id

        checkpoint_btn = discord.ui.Button(
            label="Checkpoint",
            custom_id=f"eddy:lifecycle:checkpoint:{thread_id}",
            style=discord.ButtonStyle.secondary,
            emoji="💾",
        )
        checkpoint_btn.callback = self._on_checkpoint
        self.add_item(checkpoint_btn)

        release_btn = discord.ui.Button(
            label="Release",
            custom_id=f"eddy:lifecycle:release:{thread_id}",
            style=discord.ButtonStyle.secondary,
            emoji="🌙",
        )
        release_btn.callback = self._on_release
        self.add_item(release_btn)

        dissolve_btn = discord.ui.Button(
            label="Dissolve",
            custom_id=f"eddy:lifecycle:dissolve:{thread_id}",
            style=discord.ButtonStyle.secondary,
            emoji="🍃",
        )
        dissolve_btn.callback = self._on_dissolve
        self.add_item(dissolve_btn)

    async def _on_checkpoint(self, interaction: discord.Interaction):
        if interaction.channel.id != self._thread_id:
            await interaction.response.send_message("Wrong thread.", ephemeral=True)
            return
        await interaction.response.defer()
        await _run_lifecycle_command(interaction, "checkpoint")
        await ensure_eddy_lifecycle_bar_at_bottom(interaction.channel, interaction.client)

    async def _on_release(self, interaction: discord.Interaction):
        if interaction.channel.id != self._thread_id:
            await interaction.response.send_message("Wrong thread.", ephemeral=True)
            return
        await interaction.response.defer()
        await _run_lifecycle_command(interaction, "release")
        await ensure_eddy_lifecycle_bar_at_bottom(interaction.channel, interaction.client)

    async def _on_dissolve(self, interaction: discord.Interaction):
        if interaction.channel.id != self._thread_id:
            await interaction.response.send_message("Wrong thread.", ephemeral=True)
            return
        confirm = EddyDissolveConfirmView(self._thread_id)
        interaction.client.add_view(confirm)
        await interaction.response.edit_message(content="\u200b", view=confirm)
        _schedule_confirm_revert(interaction, self._thread_id)


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
        view = EddyLifecycleBarView(self._thread_id)
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


async def post_eddy_lifecycle_bar(
    thread: discord.Thread,
    client,
) -> discord.Message | None:
    view = EddyLifecycleBarView(thread.id)
    try:
        msg = await thread.send("\u200b", view=view, silent=True)
    except discord.HTTPException as exc:
        print(f"Lifecycle bar post failed for {thread.id}: {type(exc).__name__}: {exc}")
        return None
    _mark_bar_message(thread.id, msg.id)
    client.add_view(view)
    return msg


async def ensure_eddy_lifecycle_bar_at_bottom(
    thread: discord.Thread,
    client=None,
) -> None:
    if not isinstance(thread, discord.Thread):
        return
    parent_id = thread.parent_id
    if not parent_id or not is_lifecycle_bar_active(thread.id):
        return
    if not lifecycle_bar_eligible(thread.id, parent_id):
        return

    client = client or get_lifecycle_bar_client(thread)
    if not client:
        return

    from state import get_channel_lock

    lock = get_channel_lock(thread.id)
    async with lock:
        state = _load_state()
        bar_id = state.get(str(thread.id))
        if bar_id:
            try:
                bar_msg = await thread.fetch_message(bar_id)
                async for last in thread.history(limit=1):
                    if last.id == bar_id:
                        view = EddyLifecycleBarView(thread.id)
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

        msg = await post_eddy_lifecycle_bar(thread, client)
        if msg:
            print(f"Lifecycle bar reposted in #{thread.name} ({thread.id})")


async def touch_eddy_lifecycle_bar(
    message: discord.Message,
    *,
    from_practitioner: bool = False,
) -> None:
    """Activate on first practitioner activity; keep bar at bottom afterward."""
    if not isinstance(message.channel, discord.Thread):
        return
    thread = message.channel
    parent_id = thread.parent_id
    if not parent_id or not lifecycle_bar_eligible(thread.id, parent_id):
        return

    client = get_lifecycle_bar_client(thread)
    if not client:
        return

    from state import get_channel_lock

    lock = get_channel_lock(thread.id)
    async with lock:
        if from_practitioner and _is_practitioner_author(message):
            if not is_lifecycle_bar_active(thread.id):
                msg = await post_eddy_lifecycle_bar(thread, client)
                if msg:
                    print(f"Lifecycle bar activated in #{thread.name} ({thread.id})")
                return

        if is_lifecycle_bar_active(thread.id):
            await ensure_eddy_lifecycle_bar_at_bottom(thread, client)


async def handle_lifecycle_bar_interaction(interaction: discord.Interaction) -> bool:
    """Fallback router — prefer view callbacks registered via add_view."""
    return False
