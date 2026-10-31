"""The turtleOS design language, as code. docs/ux/design-language.md says why; this is how.

A surface is built from a few blocks and rendered once, here. Nothing else in the
house touches Discord's layout parts (`tests/test_ui_language.py` says so), so
the grammar has one place to be true:

* a **Row** is a name, a state, and the one act that changes it, on one line;
* a **Card** is rows and, last, at most one red act that asks first;
* a **Header** says what you are looking at, in the person's words.

Construction refuses what the grammar forbids (a red act that does not ask, a
glyph outside the vocabulary, a label too long). `violations()` checks what was
actually rendered, and is what the language test runs over every surface.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import discord
from discord import ui

ACCENTS = {"info": 0x3498DB, "done": 0x2ECC71, "attention": 0xF1C40F, "broken": 0xE74C3C}
STATES = {"on": "\U0001f7e2", "off": "\u26aa", "needs": "\U0001f7e1", "broken": "\U0001f534"}
KINDS = {"notes": "\U0001f4dd", "health": "\U0001fa7a", "practice": "\U0001f9ed"}
ACT_GLYPHS = {"pause": "\u23f8", "resume": "\u25b6"}
GLYPHS = frozenset({*STATES.values(), *KINDS.values(), *ACT_GLYPHS.values()})

PART_BUDGET = 40  # Discord counts every nested component in a layout message
LABEL_MAX = 40  # a button says what happens in a few words (Discord allows 80)
ROWS_MAX = 7  # a glance, not an inventory
PICK_MAX = 25  # Discord's limit for one menu
ITEM_LINE_MAX = 80  # what an item is for fits on one line of a phone beside its name
ITEM_META_MAX = 240  # the quiet line under it: when, how many, where to go next

# How the house speaks to a person. A modality is shippable when the design language has
# a section for it (docs/ux/design-language.md §8); `tests/test_ui_language.py` fails
# both ways. A planned one is named with the reason it has no code yet.
MODALITIES = ("text", "card", "trace")
PLANNED_MODALITIES = {
    "voice": "no voice code exists in turtleOS; the rules are written first so the first surface cannot skip them",
    "visual companion": "the picture channel that goes with a voice conversation; it ships with voice",
}

_STYLES = {
    "safe": discord.ButtonStyle.secondary,
    "primary": discord.ButtonStyle.primary,
    "danger": discord.ButtonStyle.danger,
}


class LanguageError(ValueError):
    """The surface asked for something the design language does not allow."""


@dataclass(frozen=True)
class Act:
    label: str
    custom_id: str
    callback: object
    style: str = "safe"
    asks: bool = False  # a red act that opens a question first
    confirms: bool = False  # the red act that answers that question

    def __post_init__(self):
        if self.style not in _STYLES:
            raise LanguageError(f"unknown act style {self.style!r}")
        if not self.label.strip() or len(self.label) > LABEL_MAX:
            raise LanguageError(f"a label is a few words, not {len(self.label)} characters: {self.label!r}")
        if len(self.custom_id) > 100:
            raise LanguageError("custom id too long for Discord")
        if self.style == "danger" and not (self.asks or self.confirms):
            raise LanguageError("red means it cannot be undone from here: it must ask first")
        if self.style != "danger" and (self.asks or self.confirms):
            raise LanguageError("only a red act asks or confirms")

    def button(self) -> ui.Button:
        button = ui.Button(label=self.label, custom_id=self.custom_id, style=_STYLES[self.style])
        button.callback = self.callback
        return button


@dataclass(frozen=True)
class Choice:
    label: str
    value: str
    line: str = ""  # what choosing it means, in a few words
    current: bool = False


@dataclass(frozen=True)
class Pick:
    """One menu that changes the thing the card is about. The placeholder says what it will do."""

    placeholder: str
    custom_id: str
    choices: tuple[Choice, ...]
    callback: object

    def __post_init__(self):
        if not self.placeholder.strip() or len(self.placeholder) > 150:
            raise LanguageError("a menu says what it changes, in a sentence under 150 characters")
        if not 1 <= len(self.choices) <= PICK_MAX:
            raise LanguageError(f"a menu offers 1 to {PICK_MAX} choices, not {len(self.choices)}")
        if len({c.value for c in self.choices}) != len(self.choices):
            raise LanguageError("two choices with one value")
        if sum(c.current for c in self.choices) > 1:
            raise LanguageError("only one choice is the current one")
        if any(not c.label.strip() or len(c.label) > 100 or len(c.line) > 100 for c in self.choices):
            raise LanguageError("a choice is a short label and a short line")
        if len(self.custom_id) > 100:
            raise LanguageError("custom id too long for Discord")

    def select(self) -> ui.Select:
        menu = ui.Select(
            custom_id=self.custom_id,
            placeholder=self.placeholder,
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label=c.label, value=c.value, description=c.line or None, default=c.current)
                for c in self.choices
            ],
        )
        menu.callback = self.callback
        return menu


@dataclass(frozen=True)
class Row:
    name: str
    word: str  # the state in words, always beside its dot
    state: str  # key of STATES
    kind: str | None = None  # key of KINDS, only where rows differ by kind
    extra: str = ""  # after the word: "checked <t:...:R>"
    line: str = ""  # the quiet consequence under the row
    act: Act | None = None

    def __post_init__(self):
        if self.state not in STATES:
            raise LanguageError(f"state {self.state!r} is not in the vocabulary")
        if self.kind is not None and self.kind not in KINDS:
            raise LanguageError(f"kind {self.kind!r} is not in the vocabulary")
        if not self.word.strip():
            raise LanguageError("a state glyph never stands without its word")
        if self.act is not None and self.act.style == "danger":
            raise LanguageError("red sits alone, last in its card, not on a row")

    def text(self) -> str:
        glyph = f"{KINDS[self.kind]} " if self.kind else ""
        tail = f" · {self.extra}" if self.extra else ""
        out = f"{glyph}**{self.name}**  {STATES[self.state]} {self.word}{tail}"
        return f"{out}\n-# {self.line}" if self.line else out

    def parts(self) -> int:
        return 3 if self.act else 1  # Section + text + button, or just text


@dataclass(frozen=True)
class Item:
    """A line in a list that has no state to show: a name, and what it is for, on one line.

    Rows are for things that are on or off. A list of what can be typed, or of places
    to go, is not a list of states, and a dot beside each would say nothing.
    """

    name: str
    line: str
    meta: str = ""  # quiet, under the line: <t:..:R>, a count, links to related things

    def __post_init__(self):
        if not self.name.strip() or not self.line.strip():
            raise LanguageError("an item is a name and what it is for")
        if len(self.line) > ITEM_LINE_MAX:
            raise LanguageError(f"what an item is for is one short line, not {len(self.line)} characters")
        if len(self.meta) > ITEM_META_MAX:
            raise LanguageError(f"the quiet line under an item is short, not {len(self.meta)} characters")

    def text(self) -> str:
        out = f"**{self.name}**  {self.line}"
        return f"{out}\n-# {self.meta}" if self.meta else out

    def parts(self) -> int:
        return 1


@dataclass(frozen=True)
class Card:
    title: str = ""
    quiet: str = ""
    rows: tuple[Row | Item, ...] = ()
    pick: Pick | None = None  # a menu, after the rows and before the acts
    acts: tuple[Act, ...] = ()  # safe acts, before the red one
    danger: Act | None = None  # at most one, last
    accent: str = "info"

    def __post_init__(self):
        if self.accent not in ACCENTS:
            raise LanguageError(f"accent {self.accent!r} is not in the vocabulary")
        if len(self.rows) > ROWS_MAX:
            raise LanguageError(f"a card is a glance: {len(self.rows)} rows is an inventory")
        if self.danger is not None and self.danger.style != "danger":
            raise LanguageError("the last act of a card is the red one, or there is none")
        if any(a.style == "danger" for a in self.acts):
            raise LanguageError("red is last and alone: pass it as danger=")

    def head(self) -> str:
        if not self.title:
            return ""
        return f"### {self.title}\n-# {self.quiet}" if self.quiet else f"### {self.title}"

    def parts(self) -> int:
        total = 1 + (1 if self.head() else 0) + sum(r.parts() for r in self.rows) + (2 if self.pick else 0)
        if self.acts or self.danger:
            total += 1 + len(self.acts) + (1 if self.danger else 0)
        return total


@dataclass(frozen=True)
class Header:
    title: str
    quiet: str = ""

    def text(self) -> str:
        return f"## {self.title}\n-# {self.quiet}" if self.quiet else f"## {self.title}"

    def parts(self) -> int:
        return 1


@dataclass(frozen=True)
class Note:
    text: str

    def parts(self) -> int:
        return 1


def fit(cards: list[Card], room: int) -> tuple[list[Card], int]:
    """The cards that fit in `room` parts, in order, and how many were left out. Never silent."""
    shown: list[Card] = []
    used = 0
    for card in cards:
        if used + card.parts() > room:
            break
        shown.append(card)
        used += card.parts()
    return shown, len(cards) - len(shown)


def build(items: list, *, footer: str = "") -> ui.LayoutView:
    # A receipt line may come first (the press is its own receipt). The first thing
    # that is a card or a heading must say what the surface is.
    first = next((i for i in items if isinstance(i, (Header, Card))), None)
    if isinstance(first, Card) and not first.title:
        raise LanguageError("a surface says what it is before its first card: a Header, or a card with a title")
    total = sum(item.parts() for item in items) + (1 if footer else 0)
    if total > PART_BUDGET:
        raise LanguageError(f"{total} parts: Discord allows {PART_BUDGET}; fit() the cards first")
    view = ui.LayoutView(timeout=None)
    for item in items:
        if isinstance(item, Header):
            view.add_item(ui.TextDisplay(item.text()))
        elif isinstance(item, Note):
            view.add_item(ui.TextDisplay(item.text))
        elif isinstance(item, Card):
            view.add_item(_container(item))
        else:
            raise LanguageError(f"unknown block {type(item).__name__}")
    if footer:
        view.add_item(ui.TextDisplay(f"-# {footer}"))
    return view


def _container(card: Card) -> ui.Container:
    box = ui.Container(accent_colour=discord.Colour(ACCENTS[card.accent]))
    if card.head():
        box.add_item(ui.TextDisplay(card.head()))
    for row in card.rows:
        if getattr(row, "act", None):
            box.add_item(ui.Section(ui.TextDisplay(row.text()), accessory=row.act.button()))
        else:
            box.add_item(ui.TextDisplay(row.text()))
    if card.pick:
        menu = ui.ActionRow()
        menu.add_item(card.pick.select())
        box.add_item(menu)
    if card.acts or card.danger:
        line = ui.ActionRow()
        for act in card.acts:
            line.add_item(act.button())
        if card.danger:
            line.add_item(card.danger.button())
        box.add_item(line)
    return box


# ── What was actually rendered ─────────────────────────────────────────

_ID_SHAPES = (re.compile(r"\bg_[0-9a-f]{6,}\b"), re.compile(r"\bo_[0-9a-f]{6,}\b"), re.compile(r"\btos_[A-Za-z0-9_\-]{10,}"))
_RAW_TIME = re.compile(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")  # a clock reading stays true for a minute; <t:..:R> stays true
_PICTOGRAPH = re.compile("[\U0001f000-\U0001faff\u2190-\u21ff\u2300-\u23ff\u25a0-\u25ff\u2600-\u27bf\u2b00-\u2bff]")


def _walk(nodes):
    for node in nodes or []:
        yield node
        yield from _walk(node.get("components"))
        if node.get("accessory"):
            yield from _walk([node["accessory"]])


def components(view) -> list[dict]:
    return view.to_components() if hasattr(view, "to_components") else list(view)


def texts(view) -> list[str]:
    """Every string a person can read: text parts, button labels, and a menu with its choices."""
    out = []
    for node in _walk(components(view)):
        if node.get("type") == 10:
            out.append(node["content"])
        elif node.get("type") == 2 and node.get("label"):
            out.append(node["label"])
        elif node.get("type") == 3:
            out.append(node.get("placeholder") or "")
            for option in node.get("options") or []:
                out.append(option.get("label") or "")
                if option.get("description"):
                    out.append(option["description"])
    return [t for t in out if t]


def count_parts(view) -> int:
    return sum(1 for _ in _walk(components(view)))


def violations(view, *, forbidden: tuple[str, ...] = ()) -> list[str]:
    """What breaks the grammar in a rendered surface. Empty means it keeps it."""
    found: list[str] = []
    payload = components(view)
    if count_parts(payload) > PART_BUDGET:
        found.append(f"part budget: {count_parts(payload)} > {PART_BUDGET}")
    for text in texts(payload):
        if "```" in text:
            found.append("a code block in something a person reads")
        for shape in _ID_SHAPES:
            if shape.search(text):
                found.append(f"an id-shaped string: {text[:40]!r}")
        if _RAW_TIME.search(text):
            found.append(f"a raw timestamp where relative time belongs: {text[:40]!r}")
        for word in forbidden:
            if word and word in text:
                found.append(f"names {word!r}: {text[:40]!r}")
        clean = text.replace("\ufe0f", "")
        for match in _PICTOGRAPH.finditer(clean):
            glyph = match.group()
            if glyph not in GLYPHS:
                found.append(f"{glyph!r} is not in the emoji vocabulary")
                continue
            before = re.sub(r"[\s*_#>\-]+$", "", clean[: match.start()])
            after = re.sub(r"^[\s*_#>\-]+", "", clean[match.end():])
            if not (after[:1].isalnum() or before[-1:].isalnum()):
                found.append(f"{glyph!r} stands without a word beside it: {text[:40]!r}")
    for node in _walk(payload):
        if node.get("type") == 17:
            last = (node.get("components") or [None])[-1]
            danger_rows = [
                n for n in node.get("components") or []
                if n.get("type") == 1 and any(b.get("style") == 4 for b in n.get("components") or [])
            ]
            if len(danger_rows) > 1:
                found.append("more than one red group in a card")
            for row in danger_rows:
                if row is not last:
                    found.append("a red act is not the last thing in its card")
                buttons = row["components"]
                if buttons[-1].get("style") != 4 or sum(b.get("style") == 4 for b in buttons) != 1:
                    found.append("red is not last and alone in its row")
        if node.get("type") == 9 and (node.get("accessory") or {}).get("style") == 4:
            found.append("red on a row's own act")
    return found


def parity(tables: dict[str, dict]) -> list[str]:
    """Keys one language has and another does not."""
    languages = list(tables)
    keys = set().union(*(set(t) for t in tables.values()))
    return [f"{lang} lacks {key!r}" for lang in languages for key in sorted(keys) if key not in tables[lang]]


def read_window(title: str, text: str) -> ui.Modal:
    """A window of words. Submitting it posts nothing; closing it is the end."""

    class _Read(ui.Modal, title=(title or "the calls")[:45]):
        def __init__(self) -> None:
            super().__init__()
            self.add_item(ui.TextDisplay((text or "")[:4000]))

        async def on_submit(self, interaction: discord.Interaction) -> None:
            if not interaction.response.is_done():
                await interaction.response.defer()

    return _Read()


# The surfaces that predate the language. They are not wrong; they have not been
# touched since. Each leaves this list when it is next changed for another reason,
# and a file that no longer builds an embed must be removed from it (the language
# test fails both ways). "Decided not to yet", not "never got to".
LEGACY_EMBED_SURFACES = frozenset(
    {
        "artifact_presenter.py",
        "background.py",
        "backlog_feed_ui.py",
        "cmd_link_resonance.py",
        "cmd_practice_io.py",
        "cmd_sessions.py",
        "cmd_threads.py",
        "commands.py",
        "dialogue_attachments.py",
        "discord_bot.py",
        "discord_ref_read.py",
        "discord_render.py",
        "eddy_flow_library.py",
        "eddy_lifecycle_bar.py",
        "eddy_spawn.py",
        "flow_intake_handler.py",
        "helpers.py",
        "home_plan_ui.py",
        "hosted_river_onboarding.py",
        "intake_server.py",
        "link_read.py",
        "river_handler.py",
        "river_keys.py",
        "sessions.py",
        "share_delivery.py",
        "share_transcript.py",
        "share_ui.py",
        "story_daily.py",
    }
)
