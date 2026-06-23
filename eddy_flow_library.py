"""In-eddy flow library — load guided flows inside a materialized eddy (Slice 1)."""

from __future__ import annotations

import discord

from flow_runner import list_resolvable_flow_ids


def _flow_display_name(flow_id: str) -> str:
    return flow_id.replace("_", " ").title()


async def load_flow_in_eddy(
    thread: discord.Thread,
    flow_id: str,
    bot_client,
) -> bool:
    """Attach a flow to the current eddy (does not spawn a new thread)."""
    from commands import thread_configs
    from eddy_spawn import patch_awaiting_title, prepare_flow_eddy_entry
    from flow_runner import load_flow_spec

    parent_id = thread.parent_id
    if not parent_id:
        return False

    spec = load_flow_spec(flow_id)
    if not spec:
        return False

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

    await prepare_flow_eddy_entry(thread, flow_id, bot_client)
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
