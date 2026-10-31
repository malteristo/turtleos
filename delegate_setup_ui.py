"""The modal that takes the coding-delegate key.

A persistent button. The owner presses it; nobody else can. The value goes
straight into the house file and is never posted, logged, or returned to Spirit.
"""

from __future__ import annotations

import discord

from delegate_key import SET_REPLY, Refused, accept_key, key_is_set

CUSTOM_ID = "magic:delegate:key"
NOT_OWNER = "This is for the room's owner."
OFFER = (
    "The coding-delegate key is set in a modal. Spirit does not see it. "
    "Use a spend-capped Anthropic key, not the house's."
)
REPLACE = "The coding-delegate key is already set. Replace it only if you mean to."

_registry_loader = None


def register_delegate_views(client, registry_loader=None) -> None:
    global _registry_loader
    if registry_loader is not None:
        _registry_loader = registry_loader
    client.add_view(KeyView())


def _registry():
    if _registry_loader is None:
        return None
    return _registry_loader()


def parent_id_of(channel) -> int | None:
    if channel is None:
        return None
    parent = getattr(channel, "parent_id", None)
    if parent:
        return int(parent)
    cid = getattr(channel, "id", None)
    return int(cid) if cid is not None else None


def presser_allowed(interaction) -> bool:
    """The presser owns this magic room. Anyone else, or any other room, is refused."""
    registry = _registry()
    parent_id = parent_id_of(getattr(interaction, "channel", None))
    user_id = getattr(getattr(interaction, "user", None), "id", None)
    if registry is None or parent_id is None or user_id is None:
        return False
    from channel_primitives import resolve_primitive
    from room_connections import owner_of

    primitive = resolve_primitive(registry, parent_id)
    if not primitive or not primitive.has("workshop"):
        return False
    owner = owner_of(registry, parent_id)
    expected = str(((registry.get("mages") or {}).get(owner) or {}).get("discord_id") or "").strip()
    return bool(expected) and expected == str(user_id).strip()


async def handle_press(interaction) -> None:
    if not presser_allowed(interaction):
        await interaction.response.send_message(NOT_OWNER, ephemeral=True)
        return
    await interaction.response.send_modal(KeyModal())


async def handle_submit(interaction, raw: str) -> None:
    try:
        reply = accept_key(raw)
    except Refused as exc:
        reply = str(exc)
    await interaction.response.send_message(reply, ephemeral=True)


class KeyModal(discord.ui.Modal, title="Coding-delegate key"):
    def __init__(self):
        super().__init__()
        self._field = discord.ui.TextInput(
            label="Anthropic API key",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=400,
            placeholder="a spend-capped key, not the house's",
        )
        self.add_item(self._field)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await handle_submit(interaction, str(self._field.value or ""))


class KeyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        button = discord.ui.Button(
            label="Set the key",
            style=discord.ButtonStyle.primary,
            custom_id=CUSTOM_ID,
        )
        button.callback = self._open
        self.add_item(button)

    async def _open(self, interaction: discord.Interaction) -> None:
        await handle_press(interaction)


async def post_key_button(channel) -> None:
    text = REPLACE if key_is_set() else OFFER
    await channel.send(text, view=KeyView())
