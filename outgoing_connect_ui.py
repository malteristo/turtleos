"""The door to a person's connections.

A channel reply is the room's, so `!mcp` posts one button. What it opens is the
private reply in `mcp_list_ui` (who can read your context, what your house uses
for you), which only the person who pressed can see. The account name is not in
it. A key is not typed here.
"""

from __future__ import annotations

import os
from pathlib import Path

import discord

from outgoing_connections import Shell, bind, shell

CHANNEL_LINE = "Your connections. Only you see the list."
NOT_MEMBER = "This list is for a member of the house."
ACT = "Connections opened. Only the asker sees the list."

_LIST = "mcp:out:list"


def member_for(user_id: int | str) -> tuple[str, Path] | None:
    """The person who pressed, and their own runtime. Another member is another lookup."""
    bound = shell()
    if bound is None:
        return None
    wanted = str(user_id)
    for key, info in (bound.registry().get("mages") or {}).items():
        if not isinstance(info, dict):
            continue
        if str(info.get("discord_id") or "") != wanted:
            continue
        raw = str(info.get("runtime_dir") or "")
        if not raw:
            return None
        return str(key), Path(os.path.expanduser(raw))
    return None


def register_outgoing_views(client, outgoing_shell: Shell) -> None:
    """Bind the door to this bot's view of the practice, then arm the buttons.
    Both bots call this once, and nothing else binds the door (a test says so)."""
    bind(outgoing_shell)
    client.add_view(OutgoingConnectionsView())


class OutgoingConnectionsView(discord.ui.View):
    """The one public button. Pause, remove, open and close live on the private reply it opens."""

    def __init__(self):
        super().__init__(timeout=None)
        button = discord.ui.Button(label="Your connections", custom_id=_LIST, style=discord.ButtonStyle.primary)
        button.callback = self._on_list
        self.add_item(button)

    async def _on_list(self, interaction: discord.Interaction) -> None:
        await open_list(interaction)


async def open_list(interaction: discord.Interaction) -> None:
    """The private list, for whoever pressed. The button and the channel bar's menu both come here."""
    found = member_for(interaction.user.id)
    if found is None:
        await interaction.response.send_message(NOT_MEMBER, ephemeral=True)
        return
    person, root = found
    from mcp_list_ui import render

    await interaction.response.send_message(view=render(person, root, shell().registry()), ephemeral=True)
