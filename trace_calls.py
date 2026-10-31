"""The button on Spirit's card. The calls open in a window, not in the channel.

Spirit posts the card. Spirit is the one who hears the press. The window is
only for the person who pressed, and closing it adds nothing to the thread.
"""

from __future__ import annotations

import discord

from trace_reveal import CALLS_ID, CALLS_LABEL

_open = None


def bind_open(fn) -> None:
    global _open
    _open = fn


def arm_calls(client) -> None:
    client.add_view(TraceCallsView())


class TraceCallsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label=CALLS_LABEL, custom_id=CALLS_ID)
    async def on_calls(self, interaction: discord.Interaction, button: discord.ui.Button):
        if _open is None:
            await interaction.response.send_message(
                "The calls are not available.", ephemeral=True
            )
            return
        await _open(interaction)
