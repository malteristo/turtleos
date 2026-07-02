"""In-eddy flow library — load guided flows inside a materialized eddy (Slice 1+)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import discord

from bar_anchor import RIVER_OFFER_EMBED_COLOR
from flow_runner import list_resolvable_flow_ids

_BLANK_EDDY_NAMES = frozenset({"new eddy", "blank eddy", "thread"})


def flow_library_bar_enabled() -> bool:
    """Native eddies: bottom flow library bar replaces standing lifecycle bar."""
    from mage import get_attunement_profile

    return get_attunement_profile() == "native"


def _flow_library_bar_state_path() -> str:
    from mage import get_runtime_dir

    bar_dir = os.path.join(get_runtime_dir(), "thread-state", "eddy")
    os.makedirs(bar_dir, exist_ok=True)
    return os.path.join(bar_dir, "flow_library_bar.json")


def _load_flow_library_bar_state() -> dict[str, int]:
    path = _flow_library_bar_state_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return {str(k): int(v) for k, v in data.items()}
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


def _save_flow_library_bar_state(state: dict[str, int]) -> None:
    with open(_flow_library_bar_state_path(), "w", encoding="utf-8") as fh:
        json.dump(state, fh)


def is_flow_library_bar_active(thread_id: int) -> bool:
    return str(thread_id) in _load_flow_library_bar_state()


def _mark_flow_library_bar_message(thread_id: int, message_id: int) -> None:
    state = _load_flow_library_bar_state()
    state[str(thread_id)] = message_id
    _save_flow_library_bar_state(state)


def clear_flow_library_bar_state(thread_id: int) -> None:
    state = _load_flow_library_bar_state()
    if state.pop(str(thread_id), None) is not None:
        _save_flow_library_bar_state(state)


def flow_library_bar_eligible(thread_id: int, parent_id: int | None) -> bool:
    if not flow_library_bar_enabled() or not parent_id:
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


def get_flow_library_bar_client(thread: discord.Thread):
    from mage import river_bot_enabled

    if river_bot_enabled():
        from river_state import river_client

        if getattr(river_client, "is_ready", lambda: False)():
            return river_client
        return None
    if thread.guild:
        return thread.guild._state._get_client()
    return None


def _flow_display_name(flow_id: str) -> str:
    return flow_id.replace("_", " ").title()


def is_lens_load(thread: discord.Thread, flow_id: str) -> bool:
    """True when applying a flow to an ongoing eddy (mid-conversation lens)."""
    from commands import thread_configs
    from helpers import get_history

    cfg = thread_configs.get(thread.id) or {}
    if cfg.get("bootstrap_complete") or cfg.get("presence_posted"):
        return True

    history = get_history(thread.id)
    user_turns = [
        m
        for m in history
        if m.get("role") == "user" and (m.get("content") or "").strip()
    ]
    if user_turns:
        return True

    current = (thread.name or "").strip().lower()
    flow_slug = flow_id.replace("_", " ").lower()
    if current not in _BLANK_EDDY_NAMES and current != flow_slug:
        return True

    prior_flow = (cfg.get("context_type") or "").strip().lower()
    if prior_flow and prior_flow != flow_id.lower():
        return True

    return False


def _rename_offer_path(thread_id: int) -> Path:
    from mage import get_runtime_dir

    offer_dir = Path(get_runtime_dir()) / "thread-state" / "flow-rename-offer"
    offer_dir.mkdir(parents=True, exist_ok=True)
    return offer_dir / f"{thread_id}.json"


def write_rename_offer(
    thread_id: int,
    parent_id: int,
    suggested: str,
    *,
    message_id: int | None = None,
) -> None:
    path = _rename_offer_path(thread_id)
    data: dict = {"parent_id": parent_id, "suggested": suggested[:100]}
    if message_id is not None:
        data["message_id"] = message_id
    elif path.exists():
        try:
            prior = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(prior, dict) and prior.get("message_id"):
                data["message_id"] = prior["message_id"]
        except json.JSONDecodeError:
            pass
    path.write_text(json.dumps(data), encoding="utf-8")


def read_rename_offer(thread_id: int) -> dict | None:
    path = _rename_offer_path(thread_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def clear_rename_offer(thread_id: int) -> None:
    path = _rename_offer_path(thread_id)
    if path.exists():
        path.unlink()


async def suggest_rename_title(thread_id: int, history_excerpt: str) -> str | None:
    """Best-effort title from thread content — optional opt-in rename only."""
    from eddy_spawn import generate_topic

    seed = (history_excerpt or "").strip()
    if len(seed) < 40:
        return None
    try:
        title = (await generate_topic(seed[:2000])).strip()[:100]
    except Exception as exc:
        print(f"Flow rename suggestion failed: {type(exc).__name__}: {exc}")
        return None
    return title or None


class FlowRenameOfferView(discord.ui.View):
    """Opt-in thread rename after lens load — never automatic."""

    def __init__(self, thread_id: int, parent_id: int):
        super().__init__(timeout=None)
        self._thread_id = thread_id
        self._parent_id = parent_id
        rename_btn = discord.ui.Button(
            label="Rename thread",
            style=discord.ButtonStyle.secondary,
            custom_id=f"eddy:flow:rename:{thread_id}:{parent_id}",
        )
        rename_btn.callback = self._on_rename
        self.add_item(rename_btn)
        dismiss_btn = discord.ui.Button(
            label="Keep title",
            style=discord.ButtonStyle.secondary,
            custom_id=f"eddy:flow:rename:dismiss:{thread_id}:{parent_id}",
        )
        dismiss_btn.callback = self._on_dismiss
        self.add_item(dismiss_btn)

    async def _on_rename(self, interaction: discord.Interaction):
        thread = interaction.channel
        if not isinstance(thread, discord.Thread) or thread.id != self._thread_id:
            await interaction.response.send_message("Open this from the eddy thread.", ephemeral=True)
            return

        offer = read_rename_offer(self._thread_id)
        suggested = (offer or {}).get("suggested") or ""
        if not suggested.strip():
            await interaction.response.send_message("Rename suggestion expired.", ephemeral=True)
            return

        from eddy_spawn import rename_eddy_thread

        await interaction.response.defer(ephemeral=True)
        new_name, err = await rename_eddy_thread(thread, suggested)
        clear_rename_offer(self._thread_id)
        try:
            await interaction.message.delete()
        except discord.HTTPException:
            pass
        if err:
            await interaction.followup.send(err, ephemeral=True)
            return
        await interaction.followup.send(f"Renamed to **{new_name}**.", ephemeral=True)

    async def _on_dismiss(self, interaction: discord.Interaction):
        clear_rename_offer(self._thread_id)
        await interaction.response.defer(ephemeral=True)
        try:
            await interaction.message.delete()
        except discord.HTTPException:
            pass


async def post_flow_rename_offer(
    channel,
    thread_id: int,
    parent_id: int,
    suggested: str | None,
    bot_client,
) -> None:
    """Post optional rename affordance after lens bootstrap — explicit opt-in only."""
    if not suggested or not str(suggested).strip():
        return

    try:
        current = (getattr(channel, "name", "") or "").strip().lower()
    except Exception:
        current = ""
    proposed = str(suggested).strip()[:100]
    if proposed.lower() == current:
        return

    existing = read_rename_offer(thread_id)
    if existing and existing.get("message_id"):
        try:
            old_msg = await channel.fetch_message(int(existing["message_id"]))
            await old_msg.delete()
        except (discord.HTTPException, TypeError, ValueError):
            pass

    write_rename_offer(thread_id, parent_id, proposed)
    view = FlowRenameOfferView(thread_id, parent_id)
    bot_client.add_view(view)
    embed = discord.Embed(
        description=f"Suggested thread title: **{proposed}**",
        color=RIVER_OFFER_EMBED_COLOR,
    )
    embed.set_footer(text="Optional — only if a new name helps you find this eddy.")
    try:
        msg = await channel.send(embed=embed, view=view, silent=True)
    except discord.HTTPException as exc:
        print(f"Flow rename offer post failed: {exc}")
        return
    write_rename_offer(thread_id, parent_id, proposed, message_id=msg.id)


async def load_flow_in_eddy(
    thread: discord.Thread,
    flow_id: str,
    bot_client,
) -> bool:
    """Attach a flow to the current eddy (does not spawn a new thread)."""
    from commands import thread_configs
    from eddy_spawn import prepare_flow_eddy_entry
    from flow_runner import load_flow_spec

    parent_id = thread.parent_id
    if not parent_id:
        return False

    spec = load_flow_spec(flow_id)
    if not spec:
        return False

    lens = is_lens_load(thread, flow_id)

    cfg = thread_configs.get(thread.id)
    if cfg is not None:
        cfg["context_type"] = flow_id
        cfg["blank_eddy"] = False
    else:
        from eddy_spawn import patch_pending_native_eddy

        patch_pending_native_eddy(
            thread.id,
            parent_id,
            {"context_type": flow_id, "blank_eddy": False},
        )

    await prepare_flow_eddy_entry(thread, flow_id, bot_client, lens=lens)
    return True


async def dismiss_eddy_flow_library(thread: discord.Thread, parent_id: int) -> None:
    """Remove the intro flow library embed (top of thread). Bottom bar stays."""
    from eddy_spawn import patch_awaiting_title, read_awaiting_title

    data = read_awaiting_title(thread.id, parent_id)
    if not data:
        return
    msg_id = data.get("flow_library_msg_id")
    if not msg_id:
        return
    try:
        msg = await thread.fetch_message(int(msg_id))
        await msg.delete()
    except discord.HTTPException:
        pass
    patch_awaiting_title(thread.id, parent_id, flow_library_msg_id=None)


async def dismiss_eddy_flow_library_bar(thread: discord.Thread) -> None:
    """Remove bottom flow library bar after practitioner loads a flow."""
    bar_id = _load_flow_library_bar_state().get(str(thread.id))
    clear_flow_library_bar_state(thread.id)
    if not bar_id:
        return
    try:
        msg = await thread.fetch_message(int(bar_id))
        await msg.delete()
    except discord.HTTPException:
        pass


async def retire_standing_flow_library_bars(client) -> None:
    """Delete legacy auto-posted bottom flow bars (picker is now ``!flows`` inline only)."""
    if not flow_library_bar_enabled():
        return
    state = _load_flow_library_bar_state()
    if not state:
        return
    retired = 0
    for thread_id_str, message_id in list(state.items()):
        try:
            ch = client.get_channel(int(thread_id_str))
            if ch is None:
                ch = await client.fetch_channel(int(thread_id_str))
            if isinstance(ch, discord.Thread):
                try:
                    msg = await ch.fetch_message(int(message_id))
                    await msg.delete()
                    retired += 1
                except discord.HTTPException:
                    pass
        except Exception as exc:
            print(f"Flow library bar retire failed for {thread_id_str}: {exc}")
    _save_flow_library_bar_state({})
    if retired:
        print(f"Retired {retired} standing flow library bar(s)")


async def _complete_flow_pick(
    interaction: discord.Interaction,
    *,
    thread_id: int,
    parent_id: int,
    flow_id: str,
    dismiss_message: bool = True,
) -> None:
    thread = interaction.channel
    if not isinstance(thread, discord.Thread):
        await interaction.followup.send("Open an eddy first.", ephemeral=True)
        return

    ok = await load_flow_in_eddy(thread, flow_id, interaction.client)
    if not ok:
        await interaction.followup.send("Could not load that flow.", ephemeral=True)
        return

    from mage import set_practice_context_for_channel

    set_practice_context_for_channel(parent_id)

    from eddy_lifecycle_bar import get_bar_phase, upgrade_eddy_bar_to_live

    if get_bar_phase(thread_id) == "bootstrap" and not is_lens_load(thread, flow_id):
        await upgrade_eddy_bar_to_live(thread, interaction.client)

    from eddy_spawn import patch_awaiting_title

    patch_awaiting_title(thread_id, parent_id, flow_library_msg_id=None)
    await dismiss_eddy_flow_library(thread, parent_id)
    await dismiss_eddy_flow_library_bar(thread)
    if dismiss_message and interaction.message:
        try:
            await interaction.message.delete()
        except discord.HTTPException as exc:
            print(f"Eddy flow library dismiss failed: {exc}")


class EddyFlowLibraryView(discord.ui.View):
    """Flow picker inside a blank eddy — intentional load, not river bar."""

    def __init__(self, thread_id: int, parent_id: int, flow_ids: list[str]):
        super().__init__(timeout=None)
        self._thread_id = thread_id
        self._parent_id = parent_id
        options = [
            discord.SelectOption(
                label=_flow_display_name(fid)[:100],
                value=fid,
            )
            for fid in flow_ids[:25]
        ]
        select = discord.ui.Select(
            placeholder="Load a guided flow…",
            options=options,
            custom_id=f"eddy:flowlib:pick:{thread_id}",
        )
        select.callback = self._on_pick
        self.add_item(select)

    async def _on_pick(self, interaction: discord.Interaction):
        values = interaction.data.get("values") or []
        flow_id = values[0] if values else None
        if not flow_id:
            await interaction.response.send_message("No flow selected.", ephemeral=True)
            return

        thread = interaction.channel
        if not isinstance(thread, discord.Thread):
            await interaction.response.send_message("Open an eddy first.", ephemeral=True)
            return

        await interaction.response.defer()
        await _complete_flow_pick(
            interaction,
            thread_id=self._thread_id,
            parent_id=self._parent_id,
            flow_id=flow_id,
        )


class EddyFlowLibraryBarView(discord.ui.View):
    """Bottom-anchored flow picker — persists after first practitioner message."""

    def __init__(self, thread_id: int, parent_id: int, flow_ids: list[str]):
        super().__init__(timeout=None)
        self._thread_id = thread_id
        self._parent_id = parent_id
        options = [
            discord.SelectOption(
                label=_flow_display_name(fid)[:100],
                value=fid,
            )
            for fid in flow_ids[:25]
        ]
        select = discord.ui.Select(
            placeholder="Load a guided flow…",
            options=options,
            custom_id=f"eddy:flowlib:bar:{thread_id}",
        )
        select.callback = self._on_pick
        self.add_item(select)

    async def _on_pick(self, interaction: discord.Interaction):
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
        await _complete_flow_pick(
            interaction,
            thread_id=self._thread_id,
            parent_id=self._parent_id,
            flow_id=flow_id,
        )


async def post_eddy_flow_library(thread: discord.Thread, bot_client) -> discord.Message | None:
    """Post optional flow library affordance in a blank materialized eddy."""
    from eddy_spawn import patch_awaiting_title

    parent_id = thread.parent_id
    if not parent_id:
        return None

    flows = list_resolvable_flow_ids()
    if not flows:
        return None

    view = EddyFlowLibraryView(thread.id, parent_id, flows)
    embed = discord.Embed(
        description=(
            "Talk about anything — or load a **guided flow** if you want structure. "
            "Flows are optional."
        ),
        color=RIVER_OFFER_EMBED_COLOR,
    )
    embed.set_footer(text="Or just start typing — no flow required.")
    try:
        msg = await thread.send(embed=embed, view=view, silent=True)
    except discord.HTTPException as exc:
        print(f"Eddy flow library post failed: {exc}")
        return None

    bot_client.add_view(view)
    patch_awaiting_title(thread.id, parent_id, flow_library_msg_id=msg.id)
    return msg


async def post_eddy_flow_library_bar(
    thread: discord.Thread,
    client,
) -> discord.Message | None:
    """Post bottom flow library bar (native eddies after first practitioner message)."""
    if not flow_library_bar_enabled():
        return None

    parent_id = thread.parent_id
    if not parent_id:
        return None

    flows = list_resolvable_flow_ids()
    if not flows:
        return None

    from bar_anchor import channel_for_client

    ch = await channel_for_client(thread, client)
    view = EddyFlowLibraryBarView(ch.id, parent_id, flows)
    try:
        msg = await ch.send(
            "\u200b",
            embed=discord.Embed(
                description="Optional — load a **guided flow** or keep talking.",
                color=RIVER_OFFER_EMBED_COLOR,
            ),
            view=view,
            silent=True,
        )
    except discord.HTTPException as exc:
        print(f"Eddy flow library bar post failed for {ch.id}: {type(exc).__name__}: {exc}")
        return None

    _mark_flow_library_bar_message(ch.id, msg.id)
    client.add_view(view)
    return msg


async def ensure_eddy_flow_library_bar_at_bottom(
    thread: discord.Thread,
    client=None,
) -> None:
    from state import get_channel_lock

    lock = get_channel_lock(thread.id)
    async with lock:
        await _ensure_eddy_flow_library_bar_at_bottom_unlocked(thread, client)


async def _ensure_eddy_flow_library_bar_at_bottom_unlocked(
    thread: discord.Thread,
    client=None,
) -> None:
    parent_id = getattr(thread, "parent_id", None)
    if not parent_id or not is_flow_library_bar_active(thread.id):
        return
    if not flow_library_bar_eligible(thread.id, parent_id):
        return

    client = client or get_flow_library_bar_client(thread)
    if not client:
        return

    from bar_anchor import channel_for_client

    ch = await channel_for_client(thread, client)
    state = _load_flow_library_bar_state()
    bar_id = state.get(str(ch.id))
    flows = list_resolvable_flow_ids()
    if not flows:
        return

    if bar_id:
        try:
            bar_msg = await ch.fetch_message(bar_id)
            async for last in ch.history(limit=1):
                if last.id == bar_id:
                    view = EddyFlowLibraryBarView(ch.id, parent_id, flows)
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

    msg = await post_eddy_flow_library_bar(ch, client)
    if msg:
        print(f"Flow library bar reposted in #{getattr(ch, 'name', ch.id)} ({ch.id})")


async def touch_eddy_flow_library_bar(
    message: discord.Message,
    *,
    from_practitioner: bool = False,
) -> None:
    """Activate bottom flow library bar on first live eddy activity."""
    if not flow_library_bar_enabled():
        return
    if not isinstance(message.channel, discord.Thread):
        return
    thread = message.channel
    parent_id = thread.parent_id
    if not parent_id or not flow_library_bar_eligible(thread.id, parent_id):
        return

    from eddy_lifecycle_bar import is_practitioner_input

    client = get_flow_library_bar_client(thread)
    if not client:
        return

    from state import get_channel_lock

    lock = get_channel_lock(thread.id)
    async with lock:
        await _touch_eddy_flow_library_bar_unlocked(
            message, from_practitioner=from_practitioner, client=client
        )


async def _touch_eddy_flow_library_bar_unlocked(
    message: discord.Message,
    *,
    from_practitioner: bool = False,
    client=None,
) -> None:
    if not isinstance(message.channel, discord.Thread):
        return
    thread = message.channel
    parent_id = thread.parent_id
    if not parent_id or not flow_library_bar_eligible(thread.id, parent_id):
        return

    from eddy_lifecycle_bar import is_practitioner_input

    client = client or get_flow_library_bar_client(thread)
    if not client:
        return

    if from_practitioner and is_practitioner_input(message):
        if not is_flow_library_bar_active(thread.id):
            await dismiss_eddy_flow_library(thread, parent_id)
            msg = await post_eddy_flow_library_bar(thread, client)
            if msg:
                print(f"Flow library bar activated in #{thread.name} ({thread.id})")
            return

    if is_flow_library_bar_active(thread.id):
        await _ensure_eddy_flow_library_bar_at_bottom_unlocked(thread, client)


async def migrate_eddy_flow_library_to_bottom(
    thread: discord.Thread,
    client=None,
) -> None:
    """After first practitioner message: collapse intro embed → bottom bar."""
    if not flow_library_bar_enabled():
        return
    parent_id = thread.parent_id
    if not parent_id or not flow_library_bar_eligible(thread.id, parent_id):
        return
    client = client or get_flow_library_bar_client(thread)
    if not client:
        return
    from state import get_channel_lock

    lock = get_channel_lock(thread.id)
    async with lock:
        if is_flow_library_bar_active(thread.id):
            await _ensure_eddy_flow_library_bar_at_bottom_unlocked(thread, client)
            return
        await dismiss_eddy_flow_library(thread, parent_id)
        msg = await post_eddy_flow_library_bar(thread, client)
        if msg:
            print(f"Flow library bar activated in #{thread.name} ({thread.id})")
