"""The card in the owner's home channel that opens and closes what a connection shows.

A connection's message in the home channel says that it connected, once. Under it
sits this card: one row per thing the connection may see, with its state and the
button that changes it (docs/design/mcp-list-v2.md, the home-channel card). A press
changes the card in place and the next request from the program sees it.

The card is a layout message and the connect message is not, and Discord cannot
turn the one into the other, so the card is its own message and the offer remembers
which (`Offer.card_message_id`). A connection made before that is moved once, at
startup, by `restore_reveal_cards`.

Says the kind of thing, never the grant id or the source id.
"""

from __future__ import annotations

import asyncio

import discord

import ui_kit
from mcp_access import offers as offer_store
from mcp_access.grants import Grant, GrantStore
from mcp_access.registry import KIND_SUBJECT, KIND_WORKSHOP
from mcp_access.reveal import RevealError, program_of, rows, set_open, unix
from mcp_connect_ui import owner_locale, presser_is_owner

CUSTOM_ID_PREFIX = "mcp:reveal:"

_posting = asyncio.Lock()  # startup and the announce tick both post cards; only one may decide "not yet posted"

_KIND = {"private": "notes", KIND_SUBJECT: "health", KIND_WORKSHOP: "practice"}

_TEXT = {
    "en": {
        "not_owner": "This connection is for its owner only.",
        "inactive": "This connection is no longer active.",
        "unreachable": "This connection cannot show that.",
        "title": "{name} is connected",
        "quiet": "Until {expires}. Open what it may see. Close it and it stops seeing it. End it, or see all connections, with !mcp.",
        "moved": "{name} is connected. What it may see is on the card below.",
        "this_program": "This program",
        "nothing": "Nothing can be shown on this connection.",
        "name_private": "Notes",
        "name_subject": "Health picture",
        "name_workshop": "Practice",
        "open": "open",
        "closed": "closed",
        "seen_private": "{program} can read them",
        "seen_subject": "{program} can read it",
        "seen_workshop": "{program} can read it",
        "hidden": "Hidden from {program}",
        "act_open": "Open",
        "act_close": "Close",
    },
    "de": {
        "not_owner": "Diese Verbindung ist nur für ihre Besitzerin oder ihren Besitzer.",
        "inactive": "Diese Verbindung ist nicht mehr aktiv.",
        "unreachable": "Diese Verbindung kann das nicht zeigen.",
        "title": "{name} ist verbunden",
        "quiet": "Bis {expires}. Öffne, was es sehen darf. Schließt du es, sieht es das nicht mehr. Beenden oder alle Verbindungen sehen: !mcp.",
        "moved": "{name} ist verbunden. Was es sehen darf, steht auf der Karte darunter.",
        "this_program": "Dieses Programm",
        "nothing": "Auf dieser Verbindung kann nichts gezeigt werden.",
        "name_private": "Notizen",
        "name_subject": "Gesundheitsbild",
        "name_workshop": "Praxis",
        "open": "offen",
        "closed": "zu",
        "seen_private": "{program} kann sie lesen",
        "seen_subject": "{program} kann es lesen",
        "seen_workshop": "{program} kann sie lesen",
        "hidden": "Vor {program} verborgen",
        "act_open": "Öffnen",
        "act_close": "Schließen",
    },
}


def _t(locale: str) -> dict:
    return _TEXT.get(locale) or _TEXT["en"]


def kind_rows(grant: Grant, registry: dict, locale: str, *, id_for, press) -> list[ui_kit.Row]:
    """One row per thing this connection may see: its state in words, and the button that flips it.

    `id_for(source_id)` is the button's custom id and `press(source_id)` its callback, so the
    `!mcp` list and the home card show the same rows and answer in their own way.
    """
    t = _t(locale)
    who = program_of(grant) or t["this_program"]
    found = []
    for row in rows(grant, registry):
        kind = row["kind"]
        opened = row["open"]
        found.append(
            ui_kit.Row(
                name=t[f"name_{kind}"],
                kind=_KIND[kind],
                state="on" if opened else "off",
                word=t["open"] if opened else t["closed"],
                line=t[f"seen_{kind}"].format(program=who) if opened else t["hidden"].format(program=who),
                act=ui_kit.Act(
                    t["act_close"] if opened else t["act_open"],
                    id_for(row["id"]),
                    press(row["id"]),
                    style="safe" if opened else "primary",
                ),
            )
        )
    return found


def card_view(grant: Grant, registry: dict, locale: str, loader=None):
    """The home-channel card for one connection. Presses read the registry through `loader`."""
    t = _t(locale)
    loader = loader or (lambda: registry)

    def press(source_id: str):
        async def pressed(interaction: discord.Interaction) -> None:
            await _on_press(interaction, grant.id, grant.owner, loader, source_id)

        return pressed

    listed = kind_rows(grant, registry, locale, id_for=lambda s: f"{CUSTOM_ID_PREFIX}{grant.id}:{s}", press=press)
    stamp = unix(grant.expires or "")
    quiet = t["quiet"].format(expires=f"<t:{stamp}:D>" if stamp else "?")
    if not listed:
        return ui_kit.build([ui_kit.Card(title=t["title"].format(name=grant.principal), quiet=t["nothing"])])
    return ui_kit.build([ui_kit.Card(title=t["title"].format(name=grant.principal), quiet=quiet, rows=tuple(listed))])


async def _on_press(interaction, grant_id: str, owner: str, loader, source_id: str) -> None:
    registry = loader()
    locale = owner_locale(registry, owner)
    t = _t(locale)
    if not presser_is_owner(registry, owner, interaction.user.id):
        await interaction.response.send_message(t["not_owner"], ephemeral=True)
        return
    store = GrantStore()
    current = store.get(grant_id)
    try:
        grant = set_open(
            store,
            grant_id,
            source_id,
            opened=not (current is not None and source_id in current.sources),
            registry=registry,
        )
    except RevealError as exc:
        await interaction.response.send_message(t.get(exc.code, exc.code), ephemeral=True)
        return
    view = card_view(grant, registry, locale, loader)
    await interaction.response.edit_message(view=view)
    interaction.client.add_view(view, message_id=interaction.message.id)


def _offer_for(grant: Grant, registry: dict):
    from mcp_access.registry import private_root

    root = private_root(grant.owner, registry)
    if root is None or not root.is_dir():
        return None
    offer = next((o for o in offer_store.accepted(root) if o.grant == grant.id and o.channel_id), None)
    return (root, offer) if offer else None


async def _channel(client, channel_id):
    return client.get_channel(channel_id) or await client.fetch_channel(channel_id)


async def show_card(client, registry: dict, offer, grant: Grant, *, said: str) -> None:
    """Post the connection's card under its message once, and let the message say `said`.

    Safe to repeat: a card that was posted is never posted twice, and the message is only
    rewritten once the card exists. Raises discord.HTTPException; callers decide what a
    failure costs them.
    """
    from mcp_access.registry import private_root

    locale = owner_locale(registry, grant.owner)
    channel = await _channel(client, offer.channel_id)
    async with _posting:
        root = private_root(grant.owner, registry)
        fresh = next((o for o in offer_store.accepted(root) if o.id == offer.id), offer)
        if not fresh.card_message_id:
            view = card_view(grant, registry, locale)
            sent = await channel.send(view=view)
            offer_store.mark_card(root, offer.id, sent.id)
            client.add_view(view, message_id=sent.id)
    message = await channel.fetch_message(offer.message_id)
    await message.edit(content=said, view=None)


async def refresh_card(client, registry: dict, grant: Grant, *, ended_text: str = "") -> bool:
    """The card in the home channel says what is open. A change made from `!mcp` must change it too.

    Best effort: the grant is the truth and the next request already sees it, so a card that
    cannot be edited is reported by the False return, never raised into the press.
    """
    found = _offer_for(grant, registry)
    if found is None:
        return False
    _root, offer = found
    locale = owner_locale(registry, grant.owner)
    try:
        if not offer.card_message_id:
            if ended_text:
                channel = await _channel(client, offer.channel_id)
                old = await channel.fetch_message(offer.message_id)
                await old.edit(content=ended_text, view=None)
                return True
            await show_card(client, registry, offer, grant, said=_t(locale)["moved"].format(name=grant.principal))
            return True
        channel = await _channel(client, offer.channel_id)
        message = await channel.fetch_message(offer.card_message_id)
        if ended_text:
            await message.edit(view=ui_kit.build([ui_kit.Note(f"**{ended_text}**")]))
            return True
        view = card_view(grant, registry, locale)
        await message.edit(view=view)
        client.add_view(view, message_id=offer.card_message_id)
    except discord.HTTPException as exc:
        print(f"MCP card refresh failed for {grant.id}: {exc}")
        return False
    return True


async def restore_reveal_cards(client, registry_loader) -> int:
    """At startup: every live connection's card answers presses again; an old-style card is moved once."""
    from mcp_access.registry import private_root

    store = GrantStore()
    registry = registry_loader()
    count = 0
    for owner in registry.get("mages") or {}:
        root = private_root(owner, registry)
        if root is None or not root.is_dir():
            continue
        for offer in offer_store.accepted(root):
            grant = store.get(offer.grant or "")
            if grant is None or grant.status != "active" or not offer.channel_id:
                continue
            locale = owner_locale(registry, owner)
            try:
                if offer.card_message_id:
                    client.add_view(card_view(grant, registry, locale, registry_loader), message_id=offer.card_message_id)
                else:
                    await show_card(client, registry, offer, grant, said=_t(locale)["moved"].format(name=grant.principal))
                count += 1
            except Exception as exc:  # noqa: BLE001 — one bad row must not cost the rest
                print(f"MCP card restore failed for {offer.id}: {type(exc).__name__}: {exc}")
    return count
