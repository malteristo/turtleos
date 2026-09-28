"""The owner's river is where a connection is consented to.

River posts each pending offer from `mcp_access.offers` into the owner's
private river with one button. The owner's press opens a short pickup window
and tells them what to say to their Spirit; the Spirit's connect tool collects
the credential from the owner's own tailnet identity and writes it straight
into the client's settings. No key is ever shown here — not in the channel and
not in the ephemeral reply. Ignoring the offer is how it is declined.

The view is persistent (custom id carries the offer) and re-registered at
startup from the offers still open, so a restart does not leave a dead button.
The pickup happens in the access-point process; River's tick edits the message
once it has.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

import discord

from mcp_access import offers as offer_store
from mcp_access.registry import private_root, river_channel_id

CUSTOM_ID_PREFIX = "mcp:connect:"

_TEXT = {
    "en": {
        "head": "A connection to your own context is ready for an AI client.",
        "press": "Press **Connect**, then tell your Spirit in Cursor what the reply says. There is no key to copy.",
        "ready": (
            "Ready for {minutes} minutes. On the computer you want to connect, press **Open in Cursor** — "
            "the sentence is already in the chat, you only press Enter. Your Spirit puts the key straight "
            "into Cursor's settings; nobody sees it, you included.\n"
            "For another agent: copy the sentence below (right-click → Copy Text)."
        ),
        "sentence": "Connect me to turtleOS: {base} — with scripts/turtleos_connect.py",
        "open": "Open in Cursor",
        "done": "**Connected** — {principal}, until {expires}. The key went straight into the settings; nobody saw it.",
        "not_owner": "This connection is for its owner only.",
    },
    "de": {
        "head": "Eine Verbindung zu deinem eigenen Kontext ist für einen KI-Client bereit.",
        "press": "Drück **Verbinden** und sag deinem Spirit in Cursor, was in der Antwort steht. Es gibt keinen Schlüssel zum Abschreiben.",
        "ready": (
            "Bereit für {minutes} Minuten. Drück auf dem Computer, den du verbinden willst, **In Cursor öffnen** — "
            "der Satz steht dann schon im Chat, du drückst nur noch Enter. Dein Spirit legt den Schlüssel direkt "
            "in die Cursor-Einstellungen; niemand sieht ihn, auch du nicht.\n"
            "Für einen anderen Agenten: den Satz darunter kopieren (Rechtsklick → Text kopieren)."
        ),
        "sentence": "Verbinde mich mit turtleOS: {base} — mit scripts/turtleos_connect.py",
        "open": "In Cursor öffnen",
        "done": "**Verbunden** — {principal}, bis {expires}. Der Schlüssel ging direkt in die Einstellungen; niemand hat ihn gesehen.",
        "not_owner": "Diese Verbindung ist nur für ihre Besitzerin oder ihren Besitzer.",
    },
}


def _t(locale: str) -> dict:
    return _TEXT.get(locale) or _TEXT["en"]


def owner_locale(registry: dict, owner: str) -> str:
    return str(((registry.get("mages") or {}).get(owner) or {}).get("locale") or "en")


def presser_is_owner(registry: dict, owner: str, user_id: int | str) -> bool:
    expected = str(((registry.get("mages") or {}).get(owner) or {}).get("discord_id") or "").strip()
    return bool(expected) and expected == str(user_id).strip()


def compose_offer_text(offer: offer_store.Offer, locale: str) -> str:
    t = _t(locale)
    return "\n".join([t["head"], "", *offer_store.describe(offer), "", t["press"]])


CURSOR_PROMPT_LINK = "https://cursor.com/link/prompt?text="


def compose_ready_text(offer: offer_store.Offer, locale: str) -> str:
    return _t(locale)["ready"].format(minutes=offer_store.PICKUP_MINUTES)


def spirit_sentence(offer: offer_store.Offer, locale: str) -> str:
    return _t(locale)["sentence"].format(base=offer_store.base_url(offer.url))


def cursor_prompt_url(sentence: str) -> str:
    # %20, not "+": Cursor's deeplink reader keeps "+" as a literal character.
    return CURSOR_PROMPT_LINK + quote(sentence, safe="")


def ready_view(offer: offer_store.Offer, locale: str) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    view.add_item(
        discord.ui.Button(
            label=_t(locale)["open"],
            style=discord.ButtonStyle.link,
            url=cursor_prompt_url(spirit_sentence(offer, locale)),
        )
    )
    return view


def owner_root(registry: dict, owner: str) -> Path | None:
    return private_root(owner, registry)


class McpConnectView(discord.ui.View):
    def __init__(self, offer_id: str, owner: str, root: Path, registry_loader):
        super().__init__(timeout=None)
        self._offer_id = offer_id
        self._owner = owner
        self._root = Path(root)
        self._registry = registry_loader
        from runtime.offers import label_for

        button = discord.ui.Button(
            label=label_for("mcp_connect", owner_locale(registry_loader(), owner)),
            custom_id=f"{CUSTOM_ID_PREFIX}{offer_id}",
            style=discord.ButtonStyle.primary,
        )
        button.callback = self._on_connect
        self.add_item(button)

    async def _on_connect(self, interaction: discord.Interaction) -> None:
        registry = self._registry()
        locale = owner_locale(registry, self._owner)
        if not presser_is_owner(registry, self._owner, interaction.user.id):
            await interaction.response.send_message(_t(locale)["not_owner"], ephemeral=True)
            return
        try:
            offer = offer_store.mark_ready(self._root, self._offer_id)
        except offer_store.OfferError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        await interaction.response.send_message(
            compose_ready_text(offer, locale), view=ready_view(offer, locale), ephemeral=True
        )
        await interaction.followup.send(spirit_sentence(offer, locale), ephemeral=True)


async def announce_pickups(client, registry_loader) -> int:
    """Edit each picked-up offer's message to say so and drop its button."""
    from offer_ledger import record_for_channel

    registry = registry_loader()
    done = 0
    for owner in (registry.get("mages") or {}):
        root = owner_root(registry, owner)
        if root is None or not root.is_dir():
            continue
        for offer in offer_store.to_announce(root):
            locale = owner_locale(registry, owner)
            text = _t(locale)["done"].format(
                principal=offer.principal, expires=(offer.grant_expires or "?")[:10]
            )
            try:
                channel = client.get_channel(offer.channel_id) or await client.fetch_channel(offer.channel_id)
                message = await channel.fetch_message(offer.message_id)
                await message.edit(content=text, view=None)
            except discord.HTTPException as exc:
                print(f"MCP connect: announce failed for {offer.id}: {exc}")
                continue
            offer_store.mark_announced(root, offer.id)
            record_for_channel(offer.channel_id, kind="mcp_connect", event="accepted")
            done += 1
    return done


async def post_pending_offers(client, registry_loader) -> int:
    """Post every unposted offer into its owner's river. Returns count posted."""
    from offer_ledger import record_for_channel

    registry = registry_loader()
    posted = 0
    for owner in (registry.get("mages") or {}):
        root = owner_root(registry, owner)
        if root is None or not root.is_dir():
            continue
        for offer in offer_store.to_post(root):
            channel_id = river_channel_id(owner, registry)
            if channel_id is None:
                continue
            channel = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
            view = McpConnectView(offer.id, owner, root, registry_loader)
            msg = await channel.send(compose_offer_text(offer, owner_locale(registry, owner)), view=view)
            offer_store.mark_posted(root, offer.id, channel_id=channel_id, message_id=msg.id)
            client.add_view(view, message_id=msg.id)
            record_for_channel(channel_id, kind="mcp_connect", event="offered", detail=offer.principal[:120])
            posted += 1
    return posted


def rehydrate_connect_views(client, registry_loader) -> int:
    registry = registry_loader()
    count = 0
    for owner in (registry.get("mages") or {}):
        root = owner_root(registry, owner)
        if root is None or not root.is_dir():
            continue
        for offer in offer_store.posted_pending(root):
            try:
                client.add_view(McpConnectView(offer.id, owner, root, registry_loader), message_id=offer.message_id)
                count += 1
            except Exception as exc:  # noqa: BLE001 — one bad row must not cost the rest
                print(f"MCP connect rehydrate failed for {offer.id}: {type(exc).__name__}: {exc}")
    return count
