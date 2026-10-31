"""The channel bar's menu: which commands a channel keeps in it.

He will not memorise the commands. `!` shows what exists; this lets him keep the few he
uses in the menu under "new eddy", so one press runs them. The menu belongs to the
channel (the bar is one message everybody in the channel sees), and only commands that
make sense in a channel and need no extra words can be kept in it.

Pure: no runtime imports, so it adds nothing to the import cycle (see
`tests/test_import_graph.py`). The press handlers live in `room_models.py`, which
already holds the channel lookup.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import discord

import help_card
import ui_kit

PINS_FILE = "bar_pins.json"
MENU_SELECT_ID = "room:menu:pick"
MENU_OPEN_ID = "room:menu:open"

# Channel-scope, no words after them, and they answer in the channel. A command that
# acts on an eddy (checkpoint, release, share) is not in the channel's menu, and a
# command that takes words (!rename, !fetch) cannot run from a menu.
# `tests/test_bar_menu.py` fails when one of these is missing from the command table,
# is not on the `!` card, or takes words.
PINNABLE = ("eddy", "live", "dates", "readiness")

# What the menu always holds (the channel bar's own entries), in the order shown.
_ALWAYS_FIRST = "commands"
_ALWAYS_LAST = ("mcp", "model")

_TEXT = {
    "en": {
        "title": "What's in the menu",
        "quiet": "The menu under \"new eddy\" in this channel. Choose a command to put it there, or to take it out.",
        "card": "Commands you can keep there",
        "in": "in the menu",
        "out": "not in the menu",
        "placeholder": "Put a command in the menu, or take it out",
        "choice_in": "In the menu. Choose to take it out",
        "choice_out": "Not in the menu. Choose to put it in",
        "added": "{name} is in the menu now.",
        "removed": "{name} is out of the menu.",
        "always": "`commands`, `mcp` and `model` are always in the menu.",
        "shared": "The menu belongs to this channel: everyone here sees what you choose.",
        "button": "Choose what's in the menu",
        "foot_title": "The menu",
        "foot_quiet": "Keep the commands you use most in this channel's menu, so you do not have to type them.",
        "commands": "Everything you can type, in a list only you see",
        "mcp": "Which programs can read your context (only you see this)",
        "model": "Who answers in this channel (only you see this)",
        "not_ready": "The menu is not ready yet. Try again in a moment.",
    },
    "de": {
        "title": "Was im Menü ist",
        "quiet": "Das Menü unter \"new eddy\" in diesem Kanal. Wähle einen Befehl, um ihn dort abzulegen oder wieder herauszunehmen.",
        "card": "Befehle, die du dort behalten kannst",
        "in": "im Menü",
        "out": "nicht im Menü",
        "placeholder": "Einen Befehl ins Menü legen oder herausnehmen",
        "choice_in": "Im Menü. Wählen, um ihn herauszunehmen",
        "choice_out": "Nicht im Menü. Wählen, um ihn hineinzulegen",
        "added": "{name} ist jetzt im Menü.",
        "removed": "{name} ist nicht mehr im Menü.",
        "always": "`commands`, `mcp` und `model` sind immer im Menü.",
        "shared": "Das Menü gehört diesem Kanal: alle hier sehen, was du wählst.",
        "button": "Wählen, was im Menü ist",
        "foot_title": "Das Menü",
        "foot_quiet": "Behalte die Befehle, die du am meisten nutzt, im Menü dieses Kanals, damit du sie nicht tippen musst.",
        "commands": "Alles, was du tippen kannst, als Liste, die nur du siehst",
        "mcp": "Welche Programme deinen Kontext lesen können (nur du siehst das)",
        "model": "Wer in diesem Kanal antwortet (nur du siehst das)",
        "not_ready": "Das Menü ist noch nicht bereit. Versuch es gleich noch einmal.",
    },
}


def text(locale: str) -> dict:
    return _TEXT.get(locale) or _TEXT["en"]


def _path(base: Path) -> Path:
    return Path(base) / PINS_FILE


def _read(base: Path) -> dict:
    try:
        data = json.loads(_path(base).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def pins(base: Path, channel_id) -> list[str]:
    """The commands this channel keeps in its menu, in the order they are offered."""
    kept = _read(base).get(str(channel_id))
    kept = kept if isinstance(kept, list) else []
    return [name for name in PINNABLE if name in kept]


def toggle(base: Path, channel_id, name: str) -> tuple[list[str], bool]:
    """Put a command in the menu or take it out. Returns the new list and whether it is in."""
    if name not in PINNABLE:
        raise ValueError(f"{name!r} cannot be kept in the menu")
    now = pins(base, channel_id)
    on = name not in now
    now = [n for n in PINNABLE if (n in now) != (n == name)]
    data = _read(base)
    data[str(channel_id)] = now
    Path(base).mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(base), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, _path(base))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return now, on


def menu_options(kept: list[str], *, locale: str = "en") -> list[tuple[str, str, str]]:
    """(value, label, description) for the bar's menu: `commands`, what is kept, `mcp`, `model`."""
    t = text(locale)
    card = help_card._TEXT.get(locale) or help_card._TEXT["en"]
    rows = [(_ALWAYS_FIRST, _ALWAYS_FIRST, t["commands"])]
    rows += [(name, name, card[name]) for name in kept if name in PINNABLE]
    rows += [(name, name, t[name]) for name in _ALWAYS_LAST]
    return rows


def render(kept: list[str], *, locale: str = "en", changed: str = "", shared: bool = False, on_pick=None):
    """The checklist card: each keepable command, in or out, and one menu that flips it."""
    t = text(locale)
    card = help_card._TEXT.get(locale) or help_card._TEXT["en"]
    rows = tuple(
        ui_kit.Row(
            name=f"!{name}",
            state="on" if name in kept else "off",
            word=t["in"] if name in kept else t["out"],
            line=card[name],
        )
        for name in PINNABLE
    )
    pick = ui_kit.Pick(
        t["placeholder"],
        MENU_SELECT_ID,
        tuple(
            ui_kit.Choice(
                label=f"!{name}"[:100],
                value=name,
                line=t["choice_in"] if name in kept else t["choice_out"],
            )
            for name in PINNABLE
        ),
        on_pick or _unbound,
    )
    items: list = []
    if changed:
        items.append(ui_kit.Note(f"**{changed}**"))
    items.append(ui_kit.Header(t["title"], t["quiet"]))
    items.append(ui_kit.Card(title=t["card"], rows=rows, pick=pick, accent="done" if changed else "info"))
    items.append(ui_kit.Note(f"-# {t['always']}"))
    if shared:
        items.append(ui_kit.Note(f"-# {t['shared']}"))
    return ui_kit.build(items)


async def _unbound(interaction: discord.Interaction) -> None:  # pragma: no cover - replaced by the glue
    raise RuntimeError("the menu's listener is bound in room_models")


def foot_card(locale: str, callback) -> ui_kit.Card:
    """The last card of the `!` list: where the menu is chosen."""
    t = text(locale)
    return ui_kit.Card(
        title=t["foot_title"],
        quiet=t["foot_quiet"],
        acts=(ui_kit.Act(t["button"], MENU_OPEN_ID, callback),),
    )
