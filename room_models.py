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

from channel_primitives import resolve_primitive
from cloud_fallback import house_dir
from core.model_profiles import is_cloud, label_for, profile_for

PICKS_FILE = "room_models.json"

# What an owner can pick, by the word they type. The local entry resolves to
# the house's local model at call time, so changing TURTLE_MODEL moves it.
CHOICES: dict[str, str | None] = {
    "local": None,
    "sonnet": "claude-sonnet-5",
    "opus": "claude-opus-5-5",
}


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
    if word.strip().lower() == "local":
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
        f"- **This channel's model** {who}: `!model` shows the options, "
        "`!model sonnet` / `!model opus` / `!model local` changes it.\n"
        + _OTHER_ROOMS_LINE + "\n"
    )


def describe(model: str) -> str:
    profile = profile_for(model)
    where = "cloud" if is_cloud(model) else "local, on the house machine"
    lines = [f"**{label_for(model)}** ({where})."]
    if profile and profile.suits:
        lines.append("Good for: " + ", ".join(profile.suits) + ".")
    return " ".join(lines)


_CLOUD_NOTE = (
    "-# Cloud models are paid from the community account and read what you say here "
    "on the provider's servers. The local model never leaves the house."
)
_HEALTH_CLOUD_NOTE = (
    "-# Cloud models are paid from the community account. On one, your health board, "
    "the text read from your documents and what you say here are read on the provider's "
    "servers. Uploads are still read in the house. The local model never leaves the house."
)


def picker_text(parent_channel_id, current: str, registry: dict | None = None) -> str:
    options = " · ".join(
        f"`!model {word}` ({label_for(choice_model(word))})" for word in CHOICES
    )
    note = _HEALTH_CLOUD_NOTE if is_health(parent_channel_id, registry) else _CLOUD_NOTE
    return f"This channel runs {describe(current)}\nYou can pick: {options}.\n{note}"


_REFUSAL = {
    "no_room": "This room has no owner or members I can check, so its model stays as set.",
    "not_owner": "Only the owner of this channel can change its model.",
    "not_member": "Only members of this room can change its model.",
    "unknown": "I don't know that one. Pick `sonnet`, `opus` or `local`.",
}

_SHARED_NOTE = "-# Any member of this room can change it. The change is said here, with who made it."


def _who(message) -> str:
    author = getattr(message, "author", None)
    return getattr(author, "display_name", None) or getattr(author, "name", None) or "A member"


async def cmd_model(message, args, *, parent_id, registry: dict | None, default: str):
    shared = owner_of(parent_id, registry) is None and bool(members_of(parent_id, registry))
    if not args:
        current, _, _ = resolve_room_model(parent_id, None, default)
        if owner_of(parent_id, registry) is None and not shared:
            await message.reply(
                f"This room runs {describe(current)}\n" + _REFUSAL["no_room"], mention_author=False)
        else:
            text = picker_text(parent_id, current, registry)
            if shared:
                text += "\n" + _SHARED_NOTE
            await message.reply(text, mention_author=False)
        return f"Model for this room: {current}."
    word = args[0].strip().lower()
    try:
        model = set_pick(parent_id, message.author.id, word, registry)
    except PickRefused as refused:
        await message.reply(_REFUSAL[str(refused)], mention_author=False)
        return f"Model pick refused ({refused})."
    if is_cloud(model) and is_health(parent_id, registry):
        tail = ("Your health board, document text and what you say here are now read on the "
                "provider's servers. `!model local` goes back.")
    elif is_cloud(model) and shared:
        tail = ("Everyone here now talks to it; what is said here is read on the provider's "
                "servers, and the community account pays. `!model local` goes back.")
    elif is_cloud(model):
        tail = "It reads what you say here on the provider's servers. `!model local` goes back."
    else:
        tail = "It runs on the house machine; nothing leaves the house."
    if shared:
        head = f"**{_who(message)}** set this room to {label_for(model)}."
    else:
        head = f"This channel now runs {label_for(model)}."
    await message.reply(f"{head} {tail}", mention_author=False)
    parent = getattr(getattr(message, "channel", None), "parent", None)
    if shared and parent is not None and getattr(parent, "id", None) == parent_id:
        try:
            await parent.send(f"-# {head}", silent=True)
        except Exception as exc:
            print(f"model change notice in parent failed: {exc}")
    return f"Model for this channel set to {model}."
