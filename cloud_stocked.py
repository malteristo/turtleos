"""The button on a credit-out notice.

Whoever posts the notice hears the press. A press tries the cloud at once.
If the credit is still out, only the person who pressed is told. If it
answers, the parked words continue as the next turn, and the room gains no
extra line from the press itself.
"""

from __future__ import annotations

import discord

from cloud_fallback import STOCKED_ID, STOCKED_LABEL

_resume = None


def bind_resume(fn) -> None:
    global _resume
    _resume = fn


def arm_stocked(client) -> None:
    client.add_view(StockedView())


class StockedView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label=STOCKED_LABEL,
        custom_id=STOCKED_ID,
        style=discord.ButtonStyle.success,
    )
    async def on_stocked(self, interaction: discord.Interaction, button: discord.ui.Button):
        if _resume is None:
            await interaction.response.send_message(
                "The cloud cannot be tried from here.", ephemeral=True
            )
            return
        await _resume(interaction)
