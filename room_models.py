"""Which model answers in a room — resolved at every turn, picked by whoever owns the room.

Destination: ``docs/design/own-channel-model.md``.

Order: an explicit per-eddy override (``model_source: explicit``) → the room's
pick → the room's default. A model stamped into an eddy's config when it opened
is a default, not a choice; honouring it would pin every eddy to the model of
the day it was opened, so a room's pick would never reach its older eddies.

Picks are written only through ``set_pick``, which checks the room's
authority, read from its resolved primitive: a solo room (a home channel, any
private channel, craft) is its member's; a health channel is its subject's,
not its support person's; a shared room is its members' — any one of them may
change it, and the change is said in the room with who made it. A room is
changed from inside it; nobody picks for a room they are not in.

The mage registry is passed in by callers that already hold it, so this module
adds no importer to the ``mage`` hub (tests/test_import_graph.py).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import discord

import bar_menu
import help_card
import ui_kit
from channel_primitives import resolve_primitive
from cloud_fallback import house_dir
from core.model_profiles import is_cloud, label_for, profile_for
from core.models import RIVER_MODEL, REFLECTION_MODEL, lists_in_menu

PICKS_FILE = "room_models.json"

# Filled at startup by the shell, which already imports the registry.
# This module does not import it. The menu callback is the one caller
# that has no registry handed to it.
_get_registry = None
_resolve_channel = None
# River hands this in: put the standing bar back with the menu as it is now. This module
# does not import the bar (it would join the import cycle), so the shell binds it.
_refresh_bar = None

# What an owner can pick, by the word they type. The local entry resolves to
# the house's local model at call time, so changing TURTLE_MODEL moves it.
# What an owner can pick, by the word they type or the menu value.
# ``local`` resolves to the house conversation model at call time.
# Fast stack models (River, triage) are not here — they are system models.
CHOICES: dict[str, str | None] = {
    "local": None,
    "sonnet": "claude-sonnet-5",
    "sonnet-5.5": "claude-sonnet-5-5",
    "opus": "claude-opus-5-5",
    "gemini": "gemini-2.5-flash",
    "gemini-pro": "gemini-2.5-pro",
    "gemma-26b": "gemma4:26b",
    "gemma-12b": "gemma4:12b",
    "qwen-27b": "qwen3.5:27b",
    "qwen-35b": "qwen3.6:35b-a3b",
}

_LOCAL_WORDS = ("gemma-26b", "gemma-12b", "qwen-27b", "qwen-35b")
_ANTHROPIC_WORDS = ("sonnet", "sonnet-5.5", "opus")
_GEMINI_WORDS = ("gemini", "gemini-pro")
MODEL_SELECT_ID = "room:model"
MENU_LIMIT = 25


def _local_model() -> str:
    from core.models import TURTLE_MODEL

    return TURTLE_MODEL


def choice_model(word: str) -> str | None:
    word = (word or "").strip().lower()
    if word not in CHOICES:
        return None
    return CHOICES[word] or _local_model()


def _channel_entry(channel_id, registry: dict | None):
    return ((registry or {}).get("channels") or {}).get(str(channel_id))


def _primitive(channel_id, registry: dict | None):
    entry = _channel_entry(channel_id, registry)
    if not isinstance(entry, dict) or entry.get("archived"):
        return None
    return resolve_primitive(registry or {}, channel_id)


def owner_of(channel_id, registry: dict | None) -> str | None:
    """Mage key owning a solo or health room, or None for shared/unknown rooms.

    A health channel belongs to its subject even when a support person
    (steward) shares it — support tends the room, it does not choose for it.
    """
    primitive = _primitive(channel_id, registry)
    if primitive is None:
        return None
    if primitive.name == "health":
        return primitive.subject or None
    if primitive.base == "solo":
        return str(_channel_entry(channel_id, registry).get("mage") or "") or None
    return None


def members_of(channel_id, registry: dict | None) -> tuple[str, ...]:
    """Members who may pick a shared room's model; empty for owned/unknown rooms."""
    primitive = _primitive(channel_id, registry)
    if primitive is None or primitive.name == "health" or primitive.base != "shared":
        return ()
    return tuple(primitive.members)


def is_health(channel_id, registry: dict | None) -> bool:
    primitive = _primitive(channel_id, registry)
    return bool(primitive and primitive.name == "health")


def mage_key_for_user(user_id, registry: dict | None) -> str | None:
    for key, info in ((registry or {}).get("mages") or {}).items():
        if isinstance(info, dict) and str(info.get("discord_id", "")) == str(user_id):
            return key
    return None


def default_for_room(channel_id, registry: dict | None, fallback: str) -> str:
    """The model a room speaks with until someone picks: Sonnet 5.5 where there is a workshop, else the house's."""
    primitive = _primitive(channel_id, registry)
    if primitive is not None and primitive.has("workshop"):
        from magic_prompt import MAGIC_MODEL

        return MAGIC_MODEL
    return fallback


def _picks_path():
    return house_dir() / PICKS_FILE


def read_picks() -> dict:
    path = _picks_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def pick_for(channel_id) -> str | None:
    row = read_picks().get(str(channel_id))
    if isinstance(row, dict) and row.get("model"):
        return str(row["model"])
    return None


class PickRefused(Exception):
    pass


def set_pick(channel_id, user_id, word: str, registry: dict | None) -> str:
    """Record a pick for a room the picker may choose for; return the model id. Raises PickRefused."""
    picker = mage_key_for_user(user_id, registry)
    owner = owner_of(channel_id, registry)
    if owner is not None:
        if picker != owner:
            raise PickRefused("not_owner")
    elif members_of(channel_id, registry):
        if picker not in members_of(channel_id, registry):
            raise PickRefused("not_member")
    else:
        raise PickRefused("no_room")
    model = choice_model(word)
    if model is None:
        raise PickRefused("unknown")
    picks = read_picks()
    if word.strip().lower() == "local" and default_for_room(channel_id, registry, model) == model:
        picks.pop(str(channel_id), None)
    else:
        picks[str(channel_id)] = {
            "model": model,
            "set_by": picker,
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    path = house_dir(create=True) / PICKS_FILE
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(picks, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)
    return model


def _use_api(model: str) -> bool:
    from llm import resolve_model

    return resolve_model(model)[1]


def resolve_room_model(parent_channel_id, cfg: dict | None, default: str) -> tuple[str, bool, str]:
    """(model, use_api, source) for a turn in this room. source: explicit | pick | default."""
    cfg = cfg or {}
    if cfg.get("model_source") == "explicit" and cfg.get("model"):
        model = str(cfg["model"])
        return model, bool(cfg.get("use_api")) if "use_api" in cfg else _use_api(model), "explicit"
    picked = pick_for(parent_channel_id)
    if picked:
        use_api = _use_api(picked)
        if is_cloud(picked) and not use_api:
            return _local_model(), False, "default"
        return picked, use_api, "pick"
    return default, _use_api(default), "default"


def room_reads_on_cloud(parent_channel_id, cfg: dict | None, default: str) -> bool:
    model, use_api, _ = resolve_room_model(parent_channel_id, cfg, default)
    return use_api and is_cloud(model)


_OTHER_ROOMS_LINE = (
    "- **Other rooms:** you do not watch the member's other channels, but when they "
    "paste a Discord link to a message, an eddy or a whole channel they can see, the "
    "shell reads it for you and it arrives in their message. Say so when they ask what "
    "you can see elsewhere.\n"
)


def owner_line(parent_channel_id, registry: dict | None) -> str:
    """Prompt lines saying who can change this room's model (and what links do)."""
    if owner_of(parent_channel_id, registry) is not None:
        who = "is its owner's choice"
    elif members_of(parent_channel_id, registry):
        who = ("is its members' choice — any member can change it, and the change is "
               "said here with who made it")
    else:
        return ""
    return (
        f"- **This channel's model** {who}: `!model` shows this channel and the "
        "house models, and a menu to change this channel. "
        "`!model sonnet-5.5` / `!model opus` / `!model local` changes it.\n"
        + _OTHER_ROOMS_LINE + "\n"
    )


_TEXT = {
    "en": {
        "title": "Who answers here",
        "quiet": "The model that reads and replies in this channel. Change it with the menu, or type !model and a name.",
        "here": "answering here",
        "good_for": "Good for: {suits}.",
        "local_line": "Runs on the house machine. Nothing leaves the house.",
        "cloud_line": "Reads what you say here on the provider's servers. The community account pays.",
        "cloud_shared_line": "Everyone here talks to it. What is said here is read on the provider's servers, and the community account pays.",
        "cloud_health_line": (
            "Reads your health board, the text from your documents and what you say here on the provider's servers. "
            "The community account pays. Uploads are still read in the house."
        ),
        "cloud_note": "A cloud model is paid from the community account and reads what you say here on the provider's servers. The local model never leaves the house.",
        "cloud_health_note": (
            "A cloud model is paid from the community account. On one, your health board, the text read from your documents "
            "and what you say here are read on the provider's servers. Uploads are still read in the house. "
            "The local model never leaves the house."
        ),
        "house": "The house itself runs River on {river} and Memory on {memory}. Those are not chosen here.",
        "placeholder": "Change this channel's model",
        "choice_cloud": "Cloud · community account · reads this room",
        "choice_house": "House · stays on this machine",
        "too_long": "The list is too long for a menu. Type !model and a name.",
        "shared": "Any member of this room can change it. The change is said here, with who made it.",
        "changed": "{model} answers here from now on.",
        "changed_by": "{who} set this room to {model}.",
        "api_none": "API models are not connected.",
        "gemini_none": "Gemini is not connected.",
        "claude_none": "Claude is not connected.",
        "not_ready": "The model menu is not ready yet.",
        "no_room": "This room has no owner or members I can check, so its model stays as set.",
        "not_owner": "Only the owner of this channel can change its model.",
        "not_member": "Only members of this room can change its model.",
        "unknown": "I don't know that one. Use the menu, or sonnet, sonnet-5.5, opus, or local.",
    },
    "de": {
        "title": "Wer hier antwortet",
        "quiet": "Das Modell, das in diesem Kanal liest und antwortet. Ändere es im Menü oder tippe !model und einen Namen.",
        "here": "antwortet hier",
        "good_for": "Gut für: {suits}.",
        "local_line": "Läuft auf dem Rechner des Hauses. Nichts verlässt das Haus.",
        "cloud_line": "Liest, was du hier sagst, auf den Servern des Anbieters. Das Gemeinschaftskonto zahlt.",
        "cloud_shared_line": "Alle hier sprechen damit. Was hier gesagt wird, wird auf den Servern des Anbieters gelesen, und das Gemeinschaftskonto zahlt.",
        "cloud_health_line": (
            "Liest dein Gesundheitsbrett, den Text aus deinen Dokumenten und was du hier sagst auf den Servern des Anbieters. "
            "Das Gemeinschaftskonto zahlt. Uploads werden weiterhin im Haus gelesen."
        ),
        "cloud_note": "Ein Cloud-Modell wird vom Gemeinschaftskonto bezahlt und liest, was du hier sagst, auf den Servern des Anbieters. Das lokale Modell verlässt das Haus nie.",
        "cloud_health_note": (
            "Ein Cloud-Modell wird vom Gemeinschaftskonto bezahlt. Auf einem werden dein Gesundheitsbrett, der Text aus deinen Dokumenten "
            "und was du hier sagst auf den Servern des Anbieters gelesen. Uploads werden weiterhin im Haus gelesen. "
            "Das lokale Modell verlässt das Haus nie."
        ),
        "house": "Das Haus selbst nutzt River auf {river} und Memory auf {memory}. Die wählst du hier nicht.",
        "placeholder": "Modell dieses Kanals ändern",
        "choice_cloud": "Cloud · Gemeinschaftskonto · liest diesen Raum",
        "choice_house": "Haus · bleibt auf diesem Rechner",
        "too_long": "Die Liste ist zu lang für ein Menü. Tippe !model und einen Namen.",
        "shared": "Jedes Mitglied dieses Raums kann es ändern. Die Änderung wird hier gesagt, mit Namen.",
        "changed": "{model} antwortet hier ab jetzt.",
        "changed_by": "{who} hat diesen Raum auf {model} gestellt.",
        "api_none": "API-Modelle sind nicht verbunden.",
        "gemini_none": "Gemini ist nicht verbunden.",
        "claude_none": "Claude ist nicht verbunden.",
        "not_ready": "Das Modellmenü ist noch nicht bereit.",
        "no_room": "Dieser Raum hat keine Besitzerin und keine Mitglieder, die ich prüfen kann; sein Modell bleibt, wie es ist.",
        "not_owner": "Nur die Besitzerin oder der Besitzer dieses Kanals kann sein Modell ändern.",
        "not_member": "Nur Mitglieder dieses Raums können sein Modell ändern.",
        "unknown": "Das kenne ich nicht. Nimm das Menü, oder sonnet, sonnet-5.5, opus oder local.",
    },
}


def _t(locale: str) -> dict:
    return _TEXT.get(locale) or _TEXT["en"]


def locale_for(user_id, registry: dict | None) -> str:
    key = mage_key_for_user(user_id, registry)
    info = ((registry or {}).get("mages") or {}).get(key) if key else None
    return str((info or {}).get("locale") or "en")


def menu_rows(*, anthropic: bool, gemini: bool) -> list[tuple[str, str]]:
    """(word, model id) the menu may show. House default first, then other local, then cloud.

    A row needs a route: a profile, and a provider key for an API model.
    Sonnet 5.5 is included only while its request still carries ``between_tools``.
    The house conversation model is the ``local`` row, not a second copy.
    """
    rows: list[tuple[str, str]] = [("local", _local_model())]
    house = _local_model()
    for word in _LOCAL_WORDS:
        model = choice_model(word)
        if not model or model == house:
            continue
        profile = profile_for(model)
        if profile is None or profile.tier != "local-capable":
            continue
        rows.append((word, model))
    cloud: list[str] = []
    if anthropic:
        cloud.extend(_ANTHROPIC_WORDS)
    if gemini:
        cloud.extend(_GEMINI_WORDS)
    for word in cloud:
        model = choice_model(word)
        if model and lists_in_menu(model):
            rows.append((word, model))
    return rows


def _consequence(model: str, parent_id, registry, t: dict, *, shared: bool) -> str:
    if not is_cloud(model):
        return t["local_line"]
    if is_health(parent_id, registry):
        return t["cloud_health_line"]
    return t["cloud_shared_line"] if shared else t["cloud_line"]


def _missing(t: dict, *, anthropic: bool, gemini: bool) -> str:
    if anthropic and gemini:
        return ""
    if not anthropic and not gemini:
        return t["api_none"]
    return t["gemini_none"] if not gemini else t["claude_none"]


def render(
    parent_channel_id,
    current: str,
    registry: dict | None,
    *,
    locale: str = "en",
    anthropic: bool = False,
    gemini: bool = False,
    shared: bool = False,
    can_pick: bool = True,
    changed: str = "",
    notice: str = "",
):
    """The `!model` card: who answers here, what that means, and the menu that changes it."""
    t = _t(locale)
    profile = profile_for(current)
    line = _consequence(current, parent_channel_id, registry, t, shared=shared)
    if profile and profile.suits:
        line = f"{line} {t['good_for'].format(suits=profile.suits)}"
    row = ui_kit.Row(name=label_for(current), state="on", word=t["here"], line=line)
    items: list = []
    if changed:
        items.append(ui_kit.Note(f"**{changed}**"))
    items.append(ui_kit.Header(t["title"], t["quiet"]))
    extra: list[str] = []
    pick = None
    choices = menu_rows(anthropic=anthropic, gemini=gemini)
    if can_pick and len(choices) > MENU_LIMIT:
        extra.append(t["too_long"])
    elif can_pick:
        marked = False
        options = []
        for word, model in choices:
            is_current = model == current and not marked
            marked = marked or is_current
            options.append(
                ui_kit.Choice(
                    label=label_for(model)[:100],
                    value=word,
                    line=t["choice_cloud"] if is_cloud(model) else t["choice_house"],
                    current=is_current,
                )
            )
        pick = ui_kit.Pick(t["placeholder"], MODEL_SELECT_ID, tuple(options), _on_pick)
    items.append(ui_kit.Card(rows=(row,), pick=pick, accent="done" if changed else "info"))
    items.append(ui_kit.Note(f"-# {t['house'].format(river=label_for(RIVER_MODEL), memory=label_for(REFLECTION_MODEL))}"))
    missing = _missing(t, anthropic=anthropic, gemini=gemini)
    if missing:
        extra.append(missing)
    if can_pick and not is_cloud(current):
        extra.append(t["cloud_health_note"] if is_health(parent_channel_id, registry) else t["cloud_note"])
    if shared:
        extra.append(t["shared"])
    if notice:
        extra.insert(0, notice)
    items.extend(ui_kit.Note(f"-# {text}") for text in extra)
    return ui_kit.build(items)


def _is_card(message) -> bool:
    """A card made by this code is a layout message; the menus posted before it are not, and cannot become one."""
    return bool(getattr(getattr(message, "flags", None), "components_v2", False))


def _said(model: str, t: dict, *, shared: bool, who: str) -> str:
    if shared:
        return t["changed_by"].format(who=who, model=label_for(model))
    return t["changed"].format(model=label_for(model))


async def _on_pick(interaction: discord.Interaction) -> None:
    """One listener for every `!model` menu. The press changes the card in place; that is the receipt."""
    locale = "en"
    if _get_registry is None or _resolve_channel is None:
        await interaction.response.send_message(_t(locale)["not_ready"], ephemeral=True)
        return
    word = (interaction.data or {}).get("values", [""])[0]
    parent_id = _resolve_channel(interaction)
    registry = _get_registry()
    locale = locale_for(interaction.user.id, registry)
    t = _t(locale)
    try:
        model = set_pick(parent_id, interaction.user.id, word, registry)
    except PickRefused as refused:
        await interaction.response.send_message(t[str(refused)], ephemeral=True)
        return
    shared = owner_of(parent_id, registry) is None and bool(members_of(parent_id, registry))
    said = _said(model, t, shared=shared, who=_who(interaction))
    anthropic, gemini = provider_flags()
    view = render(
        parent_id, model, registry, locale=locale, anthropic=anthropic, gemini=gemini, shared=shared, changed=said
    )
    if _is_card(interaction.message):
        await interaction.response.edit_message(view=view)
    else:
        await interaction.response.send_message(view=view)
    await _tell_the_room(interaction.channel, parent_id, said, shared=shared)


async def _tell_the_room(channel, parent_id, said: str, *, shared: bool) -> None:
    """A change in a shared room's eddy is also said in the room, with who made it."""
    parent = getattr(channel, "parent", None)
    if shared and parent is not None and getattr(parent, "id", None) == parent_id:
        try:
            await parent.send(f"-# {said}", silent=True)
        except Exception as exc:
            print(f"model change notice in parent failed: {exc}")


def _who(source) -> str:
    # A MagicMock grows a `.user` the moment it is read, so a message and an
    # interaction are told apart by which name is actually a string.
    for attr in ("author", "user"):
        person = getattr(source, attr, None)
        for field in ("display_name", "name"):
            name = getattr(person, field, None)
            if isinstance(name, str) and name:
                return name
    return "A member"


def provider_flags() -> tuple[bool, bool]:
    from llm import ANTHROPIC_API_KEY, GOOGLE_API_KEY, HAS_ANTHROPIC, HAS_GEMINI

    return bool(HAS_ANTHROPIC and ANTHROPIC_API_KEY), bool(HAS_GEMINI and GOOGLE_API_KEY)


def bind_room_lookup(get_registry, resolve_channel, refresh_bar=None) -> None:
    """The shell hands these in. A menu press has no other way to see the room."""
    global _get_registry, _resolve_channel, _refresh_bar
    _get_registry = get_registry
    _resolve_channel = resolve_channel
    _refresh_bar = refresh_bar


def register_model_view(client) -> None:
    """One listener for every `!model` menu, including after a restart."""
    stub = ui_kit.Pick(
        _t("en")["placeholder"], MODEL_SELECT_ID, (ui_kit.Choice(label="local", value="local"),), _on_pick
    )
    client.add_view(ui_kit.build([ui_kit.Card(title=_t("en")["title"], pick=stub)]))


def arm_model_menu(client, get_registry, resolve_channel, refresh_bar=None) -> None:
    """The process that posts the menu is the process that has to answer it.

    Turtle and River are separate processes. Binding in one does not bind the other.
    """
    bind_room_lookup(get_registry, resolve_channel, refresh_bar)
    register_model_view(client)
    register_menu_view(client)


async def open_private(interaction: discord.Interaction, *, default: str) -> None:
    """The room's card, for whoever opened the channel bar's menu. Only they see it.

    A pick on it changes the card in place and tells the room, as a typed `!model` does.
    """
    if _get_registry is None or _resolve_channel is None:
        await interaction.response.send_message(_t("en")["not_ready"], ephemeral=True)
        return
    registry = _get_registry()
    parent_id = _resolve_channel(interaction)
    locale = locale_for(interaction.user.id, registry)
    t = _t(locale)
    shared = owner_of(parent_id, registry) is None and bool(members_of(parent_id, registry))
    pickable = owner_of(parent_id, registry) is not None or shared
    anthropic, gemini = provider_flags()
    current, _, _ = resolve_room_model(parent_id, None, default_for_room(parent_id, registry, default))
    view = render(
        parent_id, current, registry, locale=locale, anthropic=anthropic, gemini=gemini,
        shared=shared, can_pick=pickable, notice="" if pickable else t["no_room"],
    )
    await interaction.response.send_message(view=view, ephemeral=True)


async def cmd_model(message, args, *, parent_id, registry: dict | None, default: str):
    shared = owner_of(parent_id, registry) is None and bool(members_of(parent_id, registry))
    locale = locale_for(message.author.id, registry)
    t = _t(locale)
    anthropic, gemini = provider_flags()
    if not args:
        current, _, _ = resolve_room_model(parent_id, None, default_for_room(parent_id, registry, default))
        pickable = owner_of(parent_id, registry) is not None or shared
        await message.reply(
            view=render(
                parent_id, current, registry, locale=locale, anthropic=anthropic, gemini=gemini,
                shared=shared, can_pick=pickable,
                notice="" if pickable else t["no_room"],
            ),
            mention_author=False,
        )
        return f"Model for this room: {current}."
    word = args[0].strip().lower()
    try:
        model = set_pick(parent_id, message.author.id, word, registry)
    except PickRefused as refused:
        await message.reply(t[str(refused)], mention_author=False)
        return f"Model pick refused ({refused})."
    said = _said(model, t, shared=shared, who=_who(message))
    await message.reply(
        view=render(
            parent_id, model, registry, locale=locale, anthropic=anthropic, gemini=gemini,
            shared=shared, changed=said,
        ),
        mention_author=False,
    )
    await _tell_the_room(getattr(message, "channel", None), parent_id, said, shared=shared)
    return f"Model for this channel set to {model}."


# ─── The channel bar's menu: which commands a channel keeps in it ───────────────


def _menu_room(interaction):
    """(channel id the bar belongs to, registry, locale, shared) for a press, or None when not ready."""
    if _get_registry is None or _resolve_channel is None:
        return None
    registry = _get_registry()
    parent_id = _resolve_channel(interaction)
    locale = locale_for(interaction.user.id, registry)
    shared = owner_of(parent_id, registry) is None and bool(members_of(parent_id, registry))
    return parent_id, registry, locale, shared


async def open_menu_private(interaction: discord.Interaction) -> None:
    """The checklist, from the button on the `!` list. Only the person who pressed sees it."""
    room = _menu_room(interaction)
    if room is None:
        await interaction.response.send_message(bar_menu.text("en")["not_ready"], ephemeral=True)
        return
    parent_id, _, locale, shared = room
    view = bar_menu.render(
        bar_menu.pins(house_dir(), parent_id), locale=locale, shared=shared, on_pick=_on_menu_pick
    )
    await interaction.response.send_message(view=view, ephemeral=True)


async def _on_menu_pick(interaction: discord.Interaction) -> None:
    """One press flips one command in or out; the card changes in place and the bar is redrawn."""
    room = _menu_room(interaction)
    if room is None:
        await interaction.response.send_message(bar_menu.text("en")["not_ready"], ephemeral=True)
        return
    parent_id, _, locale, shared = room
    t = bar_menu.text(locale)
    name = ((interaction.data or {}).get("values") or [""])[0]
    try:
        kept, now_in = bar_menu.toggle(house_dir(create=True), parent_id, name)
    except ValueError:
        await interaction.response.send_message(t["not_ready"], ephemeral=True)
        return
    said = t["added" if now_in else "removed"].format(name=f"!{name}")
    view = bar_menu.render(kept, locale=locale, changed=said, shared=shared, on_pick=_on_menu_pick)
    if _is_card(interaction.message):
        await interaction.response.edit_message(view=view)
    else:
        await interaction.response.send_message(view=view, ephemeral=True)
    if _refresh_bar is not None:
        try:
            await _refresh_bar(interaction.client, parent_id)
        except Exception as exc:  # the choice is saved; the bar catches up at its next redraw
            print(f"Bar menu refresh failed for {parent_id}: {type(exc).__name__}: {exc}")


async def open_commands_private(interaction: discord.Interaction, *, operator: bool = False) -> None:
    """The `!` list, from the channel menu's `commands` entry. Only the person who chose it sees it."""
    if _get_registry is None:
        await interaction.response.send_message(bar_menu.text("en")["not_ready"], ephemeral=True)
        return
    locale = locale_for(interaction.user.id, _get_registry())
    await interaction.response.send_message(
        view=help_card.render(locale=locale, operator=operator, menu=open_menu_private), ephemeral=True
    )


def register_menu_view(client) -> None:
    """Listeners for the `!` list's button and the checklist's menu, including after a restart."""
    client.add_view(help_card.render(menu=open_menu_private))
    client.add_view(bar_menu.render([], on_pick=_on_menu_pick))
