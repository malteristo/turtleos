"""`!` and `!help`: what can be typed here, as one card in the design language.

The list is the curated set. A command that is not on it may still answer (see
`LISTED_ELSEWHERE`), but a person is only ever shown what the house means them to
reach for. `tests/test_help_card.py` fails if a listed command does not exist, or
if a command a member can run is neither listed nor named as deliberately unlisted.
"""

from __future__ import annotations

import ui_kit

_TEXT = {
    "en": {
        "title": "What you can type here",
        "quiet": "A command happens at once. The model is not asked.",
        "eddies": "Eddies",
        "look": "Look and keep",
        "house": "The house",
        "operator": "For the operator",
        "older": "A few older commands (like `!threads`) still work and are not listed.",
        "release": "Close the session: save, then start clean",
        "dissolve": "Archive this eddy when you are done with it",
        "rename": "Give this eddy its own title",
        "pin": "Keep a plan or a message where you can find it",
        "share": "Send this eddy to someone in the house",
        "flows": "Start a guided flow",
        "eddy": "Your latest eddies here, with links",
        "live": "What is live in this channel",
        "context": "What Turtle read to answer you",
        "dates": "What is coming up",
        "spark": "Drop a spark in this eddy's note",
        "status": "How the house is doing",
        "readiness": "Check that the practice is ready",
        "model": "Choose who answers in this channel",
        "mcp": "Which programs can read your context",
        "help": "This list",
        "diagnose": "Check the whole stack",
        "admin": "Run the house (`!admin` lists what it can do)",
        "feed": "Craft: post the pitches that were not posted yet",
        "pi": "Maintain the coding agent on this machine",
        "git": "What the workshop has not kept yet",
        "gone_fetch": "`!fetch` is gone. Paste the link and I read it. After I answer, you can save it to your library.",
        "gone_date": "`!date` is gone. Just tell me the date (\"Anna's birthday is on the 3rd\") and I offer to keep it. `!dates` shows what is coming.",
        "gone_focus": "`!focus` is gone. Tell me what to focus on, attach a file, or share an eddy link.",
        "gone_day": "`!day` is gone. The daily note refreshes itself.",
        "gone_new": "`!{cmd}` is gone. Press **new eddy** in the channel.",
        "gone_type": "`!thread-type` is gone. The buttons under an eddy's first message change its kind.",
        "gone_eddy_check": "`!eddy-check` is gone. Use `!dissolve` in an eddy when you are done.",
        "gone_absorb": "`!{cmd}` is gone. I carry what matters across eddies on my own, and `!live` shows what I have in mind here.",
        "gone_files": "`!{cmd}` is gone. Ask me and I look through your files myself; saved notes come with an **Open** button.",
        "gone_keep": "`!keep` is gone. Tell me to keep this eddy and I offer a button.",
        "gone_ignore": "`!ignore` is gone. Tell me not to remember this eddy and I offer a button.",
        "gone_share": "`!share` is gone. Send `...` in the eddy and press **share**.",
        "gone_checkpoint": "`!checkpoint` is gone. Send `...` and press **checkpoint**, or carry on: I save where we are when it goes quiet.",
    },
    "de": {
        "title": "Was du hier tippen kannst",
        "quiet": "Ein Befehl geschieht sofort. Das Modell wird nicht gefragt.",
        "eddies": "Eddies",
        "look": "Ansehen und festhalten",
        "house": "Das Haus",
        "operator": "Für den Betrieb",
        "older": "Ein paar ältere Befehle (wie `!threads`) funktionieren noch und stehen nicht in der Liste.",
        "release": "Die Sitzung beenden: sichern, dann frisch beginnen",
        "dissolve": "Dieses Eddy archivieren, wenn du fertig bist",
        "rename": "Diesem Eddy einen eigenen Titel geben",
        "pin": "Einen Plan oder eine Nachricht griffbereit halten",
        "share": "Dieses Eddy an jemanden im Haus schicken",
        "flows": "Einen geführten Ablauf starten",
        "eddy": "Deine letzten Eddies hier, mit Links",
        "live": "Was in diesem Kanal lebendig ist",
        "context": "Was Turtle gelesen hat, um dir zu antworten",
        "dates": "Was ansteht",
        "spark": "Einen Funken in die Notiz dieses Eddys legen",
        "status": "Wie es dem Haus geht",
        "readiness": "Prüfen, ob die Praxis bereit ist",
        "model": "Wählen, wer in diesem Kanal antwortet",
        "mcp": "Welche Programme deinen Kontext lesen können",
        "help": "Diese Liste",
        "diagnose": "Den ganzen Stack prüfen",
        "admin": "Das Haus betreiben (`!admin` zeigt, was geht)",
        "feed": "Craft: die noch nicht geposteten Ideen posten",
        "pi": "Den Coding-Agenten auf diesem Rechner pflegen",
        "git": "Was die Werkstatt noch nicht festgehalten hat",
        "gone_fetch": "`!fetch` gibt es nicht mehr. Füg den Link einfach ein, dann lese ich ihn. Nach meiner Antwort kannst du ihn in deine Bibliothek speichern.",
        "gone_date": "`!date` gibt es nicht mehr. Sag mir einfach das Datum (\"Annas Geburtstag ist am 3.\"), dann frage ich, ob ich es merken soll. `!dates` zeigt, was ansteht.",
        "gone_focus": "`!focus` gibt es nicht mehr. Sag mir, worauf ich mich konzentrieren soll, häng eine Datei an oder teil einen Eddy-Link.",
        "gone_day": "`!day` gibt es nicht mehr. Die Tagesnotiz aktualisiert sich selbst.",
        "gone_new": "`!{cmd}` gibt es nicht mehr. Drück **new eddy** im Kanal.",
        "gone_type": "`!thread-type` gibt es nicht mehr. Die Knöpfe unter der ersten Nachricht eines Eddys ändern seine Art.",
        "gone_eddy_check": "`!eddy-check` gibt es nicht mehr. Nutz `!dissolve` in einem Eddy, wenn du fertig bist.",
        "gone_absorb": "`!{cmd}` gibt es nicht mehr. Ich trage, was wichtig ist, von selbst über Eddys hinweg, und `!live` zeigt, was ich hier im Kopf habe.",
        "gone_files": "`!{cmd}` gibt es nicht mehr. Frag mich, dann suche ich selbst in deinen Dateien; gespeicherte Notizen haben einen **Öffnen**-Knopf.",
        "gone_keep": "`!keep` gibt es nicht mehr. Sag mir, dass ich diesen Eddy behalten soll, dann biete ich einen Knopf an.",
        "gone_ignore": "`!ignore` gibt es nicht mehr. Sag mir, dass ich mir diesen Eddy nicht merken soll, dann biete ich einen Knopf an.",
        "gone_share": "`!share` gibt es nicht mehr. Schick `...` im Eddy und drück **share**.",
        "gone_checkpoint": "`!checkpoint` gibt es nicht mehr. Schick `...` und drück **checkpoint**, oder mach einfach weiter: Ich halte fest, wo wir stehen, sobald es ruhig wird.",
    },
}

# (what is typed, the command it runs, key of its sentence). Seven to a group at most.
GROUPS: tuple[tuple[str, tuple[tuple[str, str, str], ...]], ...] = (
    (
        "eddies",
        (
            ("!release", "release", "release"),
            ("!dissolve", "dissolve", "dissolve"),
            ("!rename <title>", "rename", "rename"),
            ("!pin", "pin", "pin"),
            ("!flows", "flows", "flows"),
        ),
    ),
    (
        "look",
        (
            ("!eddy", "eddy", "eddy"),
            ("!live", "live", "live"),
            ("!dates", "dates", "dates"),
            ("!spark", "spark", "spark"),
        ),
    ),
    (
        "house",
        (
            ("!readiness", "readiness", "readiness"),
            ("!model", "model", "model"),
            ("!mcp", "mcp", "mcp"),
            ("!", "help", "help"),
        ),
    ),
)

OPERATOR = (
    ("!status", "status", "status"),
    ("!context", "context", "context"),
    ("!diagnose", "diagnose", "diagnose"),
    ("!admin", "admin", "admin"),
    ("!feed", "feed", "feed"),
    ("!pi", "pi", "pi"),
    ("!git", "git", "git"),
)

# Commands that exist and a person can run, and are deliberately not on the card.
# "Decided not to list", not "never got to": each is on its way out or too thin to
# teach. A command that is neither listed nor here fails `tests/test_help_card.py`.
LISTED_ELSEWHERE = frozenset(
    {
        "threads",  # the older name of !eddy
        "flow",  # the singular alias of !flows
    }
)


# Typed commands that are gone because Turtle does the thing natively (his rule,
# 2026-10-14: a `!` command is for what the system does not do natively). Typing one
# answers once with where it went, instead of staying silent. The act behind
# `!fetch` still exists for the offer button; only the typed door closed.
RETIRED = {
    "fetch": "gone_fetch",
    "date": "gone_date",
    "focus": "gone_focus",
    "day": "gone_day",
    "thread": "gone_new",
    "new": "gone_new",
    "thread-type": "gone_type",
    "panel": "gone_new",
    "eddy-check": "gone_eddy_check",
    "absorb": "gone_absorb",
    "absorbed": "gone_absorb",
    "forget": "gone_absorb",
    "ls": "gone_files",
    "search": "gone_files",
    "artifacts": "gone_files",
    "read": "gone_files",
    "export": "gone_files",
    "keep": "gone_keep",
    "ignore": "gone_ignore",
    "share": "gone_share",
    "checkpoint": "gone_checkpoint",
}
# Retired commands whose act still runs from a button, so the handler stays. Every other
# retired command must have no handler left: a door that is shut and a room behind it
# nobody can enter is dead code (`tests/test_help_card.py` fails the difference).
# `read`, `artifacts` and `export` are what the Open and Browse buttons run; `share` is what
# the share and checkpoint buttons under `...` run; `keep` and `ignore` are what Turtle's offers run.
RETIRED_KEEPS_ACT = frozenset({"fetch", "read", "artifacts", "export", "share", "keep", "ignore", "checkpoint"})


def retired_answer(command: str, *, locale: str = "en") -> str | None:
    key = RETIRED.get(command)
    if not key:
        return None
    return (_TEXT.get(locale) or _TEXT["en"])[key].replace("{cmd}", command)


def handlers_left(direct_commands) -> frozenset[str]:
    """Retired commands that still have a handler behind the shut door (should be none)."""
    return frozenset(name for name in RETIRED if name not in RETIRED_KEEPS_ACT and name in direct_commands)


def listed_commands() -> frozenset[str]:
    names = {command for _, rows in GROUPS for _, command, _ in rows}
    names |= {command for _, command, _ in OPERATOR}
    return frozenset(names)


def _item(typed: str, key: str, t: dict) -> ui_kit.Item:
    return ui_kit.Item(typed, t[key])


def render(*, locale: str = "en", operator: bool = False, menu=None):
    """`menu` is the listener for the button that opens the channel menu's checklist.

    Without one there is no button: a card must not offer a press nothing answers.
    """
    t = _TEXT.get(locale) or _TEXT["en"]
    items: list = [ui_kit.Header(t["title"], t["quiet"])]
    for group, rows in GROUPS:
        items.append(ui_kit.Card(title=t[group], rows=tuple(_item(typed, key, t) for typed, _, key in rows)))
    if operator:
        items.append(ui_kit.Card(title=t["operator"], rows=tuple(_item(typed, key, t) for typed, _, key in OPERATOR)))
    if menu is not None:
        import bar_menu

        items.append(bar_menu.foot_card(locale, menu))
    items.append(ui_kit.Note(f"-# {t['older']}"))
    return ui_kit.build(items)
