"""`!mcp`: who can read your context, and what your house uses for you.

The first application of the design language (docs/design/mcp-list-v2.md). One
private reply. Each program that can read the person's context is a card; each
thing it can see is a row with its state and its own button. The services the
house uses for them are a card of the same shape. A press changes the message
in place. Red is only "End connection" and "Remove X", last in their cards, and
both ask first.

Only the asker's own connections appear, and a press by anyone else is refused
by the ownership check the card in the home channel uses.
"""

from __future__ import annotations

import discord

import google_connection
import room_connections
import ui_kit
from mcp_access.grants import GrantStore
from mcp_access.reveal import (
    RevealError,
    end,
    listed_grants,
    program_of,
    set_open,
    unix,
)
from mcp_connect_ui import owner_locale
from mcp_reveal_ui import kind_rows, refresh_card
from outgoing_connect_ui import NOT_MEMBER, member_for
from outgoing_connections import ANSWERS_IN, private_action, service_state, shell

_TOGGLE = "mcp:list:toggle:"
_END = "mcp:list:end:"
_END_YES = "mcp:list:end-yes:"
_KEEP = "mcp:list:keep"
_PAUSE = "mcp:list:pause"
_REMOVE = "mcp:list:remove"
_REMOVE_YES = "mcp:list:remove-yes"
_G_CONNECT = "mcp:list:google-connect"
_G_ROOM = "mcp:list:google-room:"
_G_REMOVE = "mcp:list:google-remove"
_G_REMOVE_YES = "mcp:list:google-remove-yes"

_TEXT = {
    "en": {
        "title_in": "Who can read your context",
        "quiet_in": "Open what a program may see. Close it and it stops seeing it.",
        "empty_in": "Nothing is connected. To connect a program, ask your Spirit to connect you to turtleOS.",
        "title_out": "What your house uses for you",
        "asked": "Last asked {when}",
        "asked_before": "Asked before; the time was not kept",
        "not_asked": "Has not asked yet",
        "act_end": "End connection",
        "end_title": "End {name}?",
        "end_quiet": "It stops reading at once and has to be connected again.",
        "end_yes": "End it",
        "keep": "Keep",
        "ended": "{name} is ended.",
        "more": "{n} more connection(s) are not shown. End or close one to see it.",
        "x_ready": "ready",
        "x_paused": "paused",
        "x_unchecked": "not checked yet",
        "x_down": "not answering",
        "x_unsigned": "not signed in",
        "x_checked": "checked {when}",
        "x_what": "Posts, bookmarks and search, on your sign-in. In {room} only.",
        "x_signin": "Signing in is finished in the browser on the machine; a key is never typed here.",
        "x_pause": "Pause X",
        "x_resume": "Resume X",
        "x_remove": "Remove X",
        "x_remove_title": "Remove X?",
        "x_remove_quiet": "Your sign-in is removed and X stops working here until you sign in again.",
        "x_remove_yes": "Remove it",
        "refused_inactive": "That connection is no longer active.",
        "refused_unreachable": "That connection cannot show that.",
        "g_title": "Google",
        "g_signed": "Signed in as {account}. Reads only: nothing is written or sent.",
        "g_not": "not connected",
        "g_what": "Your calendar, in the rooms you choose. One sign-in covers every room that is yours.",
        "g_unset": "not set up",
        "g_unset_line": "The person who runs this house sets Google up first.",
        "g_connect": "Connect Google",
        "g_on": "on",
        "g_off": "off",
        "g_turn_on": "Turn on",
        "g_turn_off": "Turn off",
        "g_link": "Open this link to sign in to Google. It works once, for ten minutes.\n{url}\nWhen the page says Connected, open Your connections again.",
        "g_remove": "Disconnect Google",
        "g_remove_title": "Disconnect Google?",
        "g_remove_quiet": "Your sign-in is removed. Nothing from Google works in any room until you sign in again.",
        "g_remove_yes": "Disconnect",
        "g_gone": "Google is disconnected.",
        "g_room_refused": "This room cannot have that.",
    },
    "de": {
        "title_in": "Wer deinen Kontext lesen kann",
        "quiet_in": "Öffne, was ein Programm sehen darf. Schließt du es, sieht es das nicht mehr.",
        "empty_in": "Nichts ist verbunden. Um ein Programm zu verbinden, bitte deinen Spirit, dich mit turtleOS zu verbinden.",
        "title_out": "Was dein Haus für dich nutzt",
        "asked": "Zuletzt gefragt {when}",
        "asked_before": "Hat schon gefragt; die Zeit wurde nicht festgehalten",
        "not_asked": "Hat noch nicht gefragt",
        "act_end": "Verbindung beenden",
        "end_title": "{name} beenden?",
        "end_quiet": "Es liest sofort nicht mehr mit und muss neu verbunden werden.",
        "end_yes": "Beenden",
        "keep": "Behalten",
        "ended": "{name} ist beendet.",
        "more": "{n} weitere Verbindung(en) werden nicht gezeigt. Beende oder schließe eine, um sie zu sehen.",
        "x_ready": "bereit",
        "x_paused": "pausiert",
        "x_unchecked": "noch nicht geprüft",
        "x_down": "antwortet nicht",
        "x_unsigned": "nicht angemeldet",
        "x_checked": "geprüft {when}",
        "x_what": "Beiträge, Lesezeichen und Suche, mit deiner Anmeldung. Nur in {room}.",
        "x_signin": "Die Anmeldung schließt du im Browser auf dem Rechner ab; ein Schlüssel wird hier nie getippt.",
        "x_pause": "X pausieren",
        "x_resume": "X fortsetzen",
        "x_remove": "X entfernen",
        "x_remove_title": "X entfernen?",
        "x_remove_quiet": "Deine Anmeldung wird entfernt und X arbeitet hier nicht mehr, bis du dich neu anmeldest.",
        "x_remove_yes": "Entfernen",
        "refused_inactive": "Diese Verbindung ist nicht mehr aktiv.",
        "refused_unreachable": "Diese Verbindung kann das nicht zeigen.",
        "g_title": "Google",
        "g_signed": "Angemeldet als {account}. Nur lesen: nichts wird geschrieben oder gesendet.",
        "g_not": "nicht verbunden",
        "g_what": "Dein Kalender, in den Räumen, die du wählst. Eine Anmeldung gilt für jeden Raum, der dir gehört.",
        "g_unset": "nicht eingerichtet",
        "g_unset_line": "Wer dieses Haus betreibt, richtet Google zuerst ein.",
        "g_connect": "Google verbinden",
        "g_on": "an",
        "g_off": "aus",
        "g_turn_on": "Einschalten",
        "g_turn_off": "Ausschalten",
        "g_link": "Öffne diesen Link, um dich bei Google anzumelden. Er gilt einmal, zehn Minuten lang.\n{url}\nWenn die Seite „Connected“ zeigt, öffne Deine Verbindungen noch einmal.",
        "g_remove": "Google trennen",
        "g_remove_title": "Google trennen?",
        "g_remove_quiet": "Deine Anmeldung wird entfernt. Nichts von Google funktioniert in einem Raum, bis du dich neu anmeldest.",
        "g_remove_yes": "Trennen",
        "g_gone": "Google ist getrennt.",
        "g_room_refused": "Dieser Raum kann das nicht haben.",
    },
}

_X_STATE = {
    "ready": ("on", "x_ready"),
    "paused": ("off", "x_paused"),
    "unchecked": ("needs", "x_unchecked"),
    "down": ("broken", "x_down"),
    "unsigned": ("off", "x_unsigned"),
}
_X_ACCENT = {"down": "broken", "unchecked": "attention"}


def _t(locale: str) -> dict:
    return _TEXT.get(locale) or _TEXT["en"]


def _when(iso: str | None) -> str:
    stamp = unix(iso or "")
    return f"<t:{stamp}:R>" if stamp else ""


def _asked(grant, t: dict) -> str:
    when = _when((grant.extra or {}).get("last_used"))
    if when:
        return t["asked"].format(when=when)
    return t["asked_before"] if grant.calls else t["not_asked"]


def _connection_card(grant, registry: dict, locale: str, t: dict) -> ui_kit.Card:
    program = program_of(grant)
    listed = kind_rows(
        grant,
        registry,
        locale,
        id_for=lambda source: f"{_TOGGLE}{grant.id}:{source}",
        press=lambda source: _press(_toggle, grant.id, source),
    )
    return ui_kit.Card(
        title=f"{grant.principal} · {program}" if program else grant.principal,
        quiet=_asked(grant, t),
        rows=tuple(listed),
        danger=ui_kit.Act(t["act_end"], f"{_END}{grant.id}", _press(_ask_end, grant.id), style="danger", asks=True),
    )


def _service_card(person: str, root, t: dict) -> ui_kit.Card:
    state, checked = service_state(person, root)
    dot, word_key = _X_STATE[state]
    signed = state != "unsigned"
    line = t["x_what"].format(room=ANSWERS_IN)
    if not signed:
        line = f"{line} {t['x_signin']}"
    pause = None
    if signed:
        paused = state == "paused"
        pause = ui_kit.Act(
            t["x_resume"] if paused else t["x_pause"],
            _PAUSE,
            _press(_pause),
        )
    extra = t["x_checked"].format(when=_when(checked)) if state == "ready" and _when(checked) else ""
    row = ui_kit.Row(name="X", state=dot, word=t[word_key], extra=extra, line=line, act=pause)
    return ui_kit.Card(
        rows=(row,),
        danger=ui_kit.Act(t["x_remove"], _REMOVE, _press(_ask_remove), style="danger", asks=True) if signed else None,
        accent=_X_ACCENT.get(state, "info"),
    )


def _google_card(person: str, root, registry: dict, t: dict) -> ui_kit.Card:
    if not google_connection.configured():
        row = ui_kit.Row(name="Google", state="off", word=t["g_unset"], line=t["g_unset_line"])
        return ui_kit.Card(rows=(row,))
    info = google_connection.signed_in(person, root)
    if info is None:
        row = ui_kit.Row(
            name="Google",
            state="off",
            word=t["g_not"],
            line=t["g_what"],
            act=ui_kit.Act(t["g_connect"], _G_CONNECT, _press(_google_connect)),
        )
        return ui_kit.Card(rows=(row,))
    rows = []
    for service in info["services"]:
        label = room_connections.SERVICES[service].label
        for channel_id, room in room_connections.rooms_for(service, person, registry):
            on = room_connections.level(service, registry=registry, channel_id=channel_id, person=person, root=root) != "off"
            rows.append(
                ui_kit.Row(
                    name=f"{label} · {room}",
                    state="on" if on else "off",
                    word=t["g_on"] if on else t["g_off"],
                    act=ui_kit.Act(
                        t["g_turn_off"] if on else t["g_turn_on"],
                        f"{_G_ROOM}{service}:{channel_id}",
                        _press(_google_room, service, channel_id),
                    ),
                )
            )
    return ui_kit.Card(
        title=t["g_title"],
        quiet=t["g_signed"].format(account=info["account"]),
        rows=tuple(rows),
        danger=ui_kit.Act(t["g_remove"], _G_REMOVE, _press(_ask_google_remove), style="danger", asks=True),
    )


def render(person: str, root, registry: dict, *, note: str = "", store=None):
    """The whole reply for one person. Reads the grants fresh, every time."""
    store = store or GrantStore()
    locale = owner_locale(registry, person)
    t = _t(locale)
    grants = sorted(
        listed_grants(store, person, registry),
        key=lambda g: ((g.extra or {}).get("last_used") or "", g.created),
        reverse=True,
    )
    service = _service_card(person, root, t)
    google = _google_card(person, root, registry, t)
    items: list = []
    if note:
        items.append(ui_kit.Note(f"**{note}**"))
    items.append(ui_kit.Header(t["title_in"], t["quiet_in"]))
    # What is left for connection cards: the header for what goes out, its card,
    # and one part kept back for the "empty" or "more" line.
    room = ui_kit.PART_BUDGET - sum(i.parts() for i in items) - 1 - service.parts() - 1 - google.parts() - 1
    cards = [_connection_card(g, registry, locale, t) for g in grants]
    shown, hidden = ui_kit.fit(cards, room)
    if not cards:
        items.append(ui_kit.Note(t["empty_in"]))
    items.extend(shown)
    if hidden:
        items.append(ui_kit.Note(f"-# {t['more'].format(n=hidden)}"))
    items.append(ui_kit.Header(t["title_out"]))
    items.append(google)
    items.append(service)
    # No footer: Discord already says "Only you can see this" under a private reply.
    return ui_kit.build(items)


# ── Presses ────────────────────────────────────────────────────────────


def _press(handler, *args):
    async def press(interaction: discord.Interaction) -> None:
        await handler(interaction, *args)

    return press


def _who(interaction: discord.Interaction):
    found = member_for(interaction.user.id)
    if found is None:
        return None
    person, root = found
    return person, root, shell().registry()


async def _refuse(interaction: discord.Interaction, text: str) -> None:
    await interaction.response.send_message(text, ephemeral=True)


async def _redraw(interaction, person, root, registry, *, note: str = "", store=None) -> None:
    await interaction.response.edit_message(view=render(person, root, registry, note=note, store=store))


async def _toggle(interaction: discord.Interaction, grant_id: str, source_id: str) -> None:
    who = _who(interaction)
    if who is None:
        await _refuse(interaction, NOT_MEMBER)
        return
    person, root, registry = who
    t = _t(owner_locale(registry, person))
    store = GrantStore()
    current = store.get(grant_id)
    opened = not (current is not None and source_id in current.sources)
    try:
        grant = set_open(store, grant_id, source_id, opened=opened, registry=registry, owner=person)
    except RevealError as exc:
        await _refuse(interaction, t.get(f"refused_{exc.code}", exc.code))
        return
    await _redraw(interaction, person, root, registry, store=store)
    await refresh_card(interaction.client, registry, grant)


def _ask_view(title: str, quiet: str, yes: ui_kit.Act, keep: ui_kit.Act):
    return ui_kit.build([ui_kit.Card(title=title, quiet=quiet, acts=(keep,), danger=yes, accent="attention")])


async def _ask_end(interaction: discord.Interaction, grant_id: str) -> None:
    who = _who(interaction)
    if who is None:
        await _refuse(interaction, NOT_MEMBER)
        return
    person, _root, registry = who
    t = _t(owner_locale(registry, person))
    grant = GrantStore().get(grant_id)
    if grant is None or grant.owner != person or grant.status != "active":
        await _refuse(interaction, t["refused_inactive"])
        return
    view = _ask_view(
        t["end_title"].format(name=grant.principal),
        t["end_quiet"],
        ui_kit.Act(t["end_yes"], f"{_END_YES}{grant_id}", _press(_end, grant_id), style="danger", confirms=True),
        ui_kit.Act(t["keep"], _KEEP, _press(_keep)),
    )
    await interaction.response.edit_message(view=view)


async def _end(interaction: discord.Interaction, grant_id: str) -> None:
    who = _who(interaction)
    if who is None:
        await _refuse(interaction, NOT_MEMBER)
        return
    person, root, registry = who
    t = _t(owner_locale(registry, person))
    store = GrantStore()
    try:
        grant = end(store, grant_id, owner=person, registry=registry)
    except RevealError as exc:
        await _refuse(interaction, t.get(f"refused_{exc.code}", exc.code))
        return
    said = t["ended"].format(name=grant.principal)
    await _redraw(interaction, person, root, registry, note=said, store=store)
    await refresh_card(interaction.client, registry, grant, ended_text=said)


async def _keep(interaction: discord.Interaction) -> None:
    who = _who(interaction)
    if who is None:
        await _refuse(interaction, NOT_MEMBER)
        return
    person, root, registry = who
    await _redraw(interaction, person, root, registry)


async def _pause(interaction: discord.Interaction) -> None:
    who = _who(interaction)
    if who is None:
        await _refuse(interaction, NOT_MEMBER)
        return
    person, root, registry = who
    private_action(person, root, "pause")
    await _redraw(interaction, person, root, registry)


async def _ask_remove(interaction: discord.Interaction) -> None:
    who = _who(interaction)
    if who is None:
        await _refuse(interaction, NOT_MEMBER)
        return
    _person, _root, registry = who
    t = _t(owner_locale(registry, _person))
    view = _ask_view(
        t["x_remove_title"],
        t["x_remove_quiet"],
        ui_kit.Act(t["x_remove_yes"], _REMOVE_YES, _press(_remove), style="danger", confirms=True),
        ui_kit.Act(t["keep"], _KEEP, _press(_keep)),
    )
    await interaction.response.edit_message(view=view)


async def _remove(interaction: discord.Interaction) -> None:
    from outgoing_x import clear_login

    who = _who(interaction)
    if who is None:
        await _refuse(interaction, NOT_MEMBER)
        return
    person, root, registry = who
    said = private_action(person, root, "remove-yes", clear=clear_login)
    await _redraw(interaction, person, root, registry, note=said)


async def _google_connect(interaction: discord.Interaction) -> None:
    from cloud_fallback import house_dir

    who = _who(interaction)
    if who is None:
        await _refuse(interaction, NOT_MEMBER)
        return
    person, root, registry = who
    t = _t(owner_locale(registry, person))
    try:
        url = google_connection.begin(
            person=person,
            root=root,
            house=house_dir(create=True),
            channel_id=interaction.channel_id,
            services=list(google_connection.SERVICE_SCOPES),
        )
    except google_connection.SigninError as exc:
        await _refuse(interaction, str(exc))
        return
    # Only the person who pressed sees this: the link carries their one-time state.
    await interaction.response.send_message(t["g_link"].format(url=url), ephemeral=True)


async def _google_room(interaction: discord.Interaction, service: str, channel_id: str) -> None:
    who = _who(interaction)
    if who is None:
        await _refuse(interaction, NOT_MEMBER)
        return
    person, root, registry = who
    t = _t(owner_locale(registry, person))
    if channel_id not in {cid for cid, _name in room_connections.rooms_for(service, person, registry)}:
        await _refuse(interaction, t["g_room_refused"])
        return
    now = room_connections.level(service, registry=registry, channel_id=channel_id, person=person, root=root)
    try:
        room_connections.choose(root, person, service, channel_id, "off" if now != "off" else "look", registry=registry)
    except room_connections.Forbidden:
        await _refuse(interaction, t["g_room_refused"])
        return
    await _redraw(interaction, person, root, registry)


async def _ask_google_remove(interaction: discord.Interaction) -> None:
    who = _who(interaction)
    if who is None:
        await _refuse(interaction, NOT_MEMBER)
        return
    person, _root, registry = who
    t = _t(owner_locale(registry, person))
    view = _ask_view(
        t["g_remove_title"],
        t["g_remove_quiet"],
        ui_kit.Act(t["g_remove_yes"], _G_REMOVE_YES, _press(_google_remove), style="danger", confirms=True),
        ui_kit.Act(t["keep"], _KEEP, _press(_keep)),
    )
    await interaction.response.edit_message(view=view)


async def _google_remove(interaction: discord.Interaction) -> None:
    who = _who(interaction)
    if who is None:
        await _refuse(interaction, NOT_MEMBER)
        return
    person, root, registry = who
    t = _t(owner_locale(registry, person))
    import asyncio

    await asyncio.to_thread(google_connection.disconnect, person, root)
    await _redraw(interaction, person, root, registry, note=t["g_gone"])
