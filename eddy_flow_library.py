"""In-eddy flow library — load guided flows inside a materialized eddy (Slice 1+)."""

from __future__ import annotations

import json
from pathlib import Path

import discord

from flow_runner import list_resolvable_flow_ids

_BLANK_EDDY_NAMES = frozenset({"new eddy", "blank eddy", "thread"})


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


def write_rename_offer(thread_id: int, parent_id: int, suggested: str) -> None:
    path = _rename_offer_path(thread_id)
    path.write_text(
        json.dumps({"parent_id": parent_id, "suggested": suggested[:100]}),
        encoding="utf-8",
    )


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

    write_rename_offer(thread_id, parent_id, proposed)
    view = FlowRenameOfferView(thread_id, parent_id)
    bot_client.add_view(view)
    embed = discord.Embed(
        description=f"Suggested thread title: **{proposed}**",
        color=0x5865F2,
    )
    embed.set_footer(text="Optional — only if a new name helps you find this eddy.")
    try:
        await channel.send(embed=embed, view=view, silent=True)
    except discord.HTTPException as exc:
        print(f"Flow rename offer post failed: {exc}")


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
    """Remove the flow library affordance when the practitioner starts talking."""
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
        ok = await load_flow_in_eddy(thread, flow_id, interaction.client)
        if not ok:
            await interaction.followup.send("Could not load that flow.", ephemeral=True)
            return

        from eddy_spawn import patch_awaiting_title

        patch_awaiting_title(self._thread_id, self._parent_id, flow_library_msg_id=None)
        try:
            await interaction.message.delete()
        except discord.HTTPException as exc:
            print(f"Eddy flow library dismiss failed: {exc}")


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
        color=0x5865F2,
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
