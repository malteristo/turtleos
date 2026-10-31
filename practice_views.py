"""One pattern, run differently in each practice: `!eddy`, `!live`, and `...` in a channel.

A command is worth keeping when it is a pattern that every practice can use and that
each practice fills in its own way. `!live` is the first: *what is live here*. Every
channel shows the same two things (what Turtle has in mind, which eddies are open)
and then what only that practice has: a craft channel shows who holds the next move on
each eddy; a personal river shows the dates coming up; a health room shows the
shape of what is moving and none of its words. Which practice adds what is declared
below (`LIVE_EXTRAS`, `NO_LIVE_EXTRAS`) and `tests/test_practice_views.py` fails when a
channel primitive is in neither, so a new kind of channel cannot appear without
someone deciding what its live state is.

This module only draws. It imports nothing from the runtime's tangle (`mage`, the
registry, Discord), because the layering ratchet (`tests/test_import_graph.py`) lets
the tangle shrink and never grow: the command layer (`cmd_threads.place_for`) reads
the world and hands a `Place` in.

The topics are read through `memory_agent.live_topics`, which is the same selection
the passive block puts in front of Turtle on every turn. That is why the card can say
"Turtle has these in mind": it is the same list, and a test compares them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import ui_kit

_TEXT = {
    "en": {
        "eddy_title": "Your eddies here",
        "eddy_quiet": "Latest activity first. Open one from its name.",
        "eddies_title": "Open eddies",
        "parked_title": "Parked",
        "parked_quiet": "Not active right now.",
        "no_eddies": "No eddies here yet. Press **new eddy** below to open one.",
        "no_note": "No note yet",
        "more": "…and {n} more. `!eddy all` lists them.",
        "live": "live",
        "kept": "kept",
        "sealed": "sealed",
        "resting": "parked",
        "live_title": "What is live in {name}",
        "live_quiet": "Where your practice stands in this channel.",
        "toward": "Toward **{x}**: the topics it matches come first.",
        "carried_title": "Turtle has these in mind",
        "carried_quiet": "In every answer here, without you mentioning them.",
        "rest_title": "Comes up when you mention it",
        "rest_quiet": "Turtle brings these in when your message reaches for them.",
        "no_topics": "Nothing has built up here yet. A topic forms once two conversations return to the same thing.",
        "conversations": "{n} conversations",
        "waiting_title": "Waiting",
        "waiting_quiet": "Who holds the next move.",
        "move_you": "Your move",
        "move_session": "Ready: waits for a session",
        "move_confirm": "Waits for your yes",
        "move_other": "Waits for {who}",
        "dates_title": "Coming up",
        "dates_quiet": "The next two weeks.",
        "left_out": "{n} more sections do not fit on one card.",
        "summary_hidden": "A sensitive room: topics show their size and when, not their words.",
        "topic_n": "Topic {n}",
    },
    "de": {
        "eddy_title": "Deine Eddies hier",
        "eddy_quiet": "Neueste Aktivität zuerst. Öffne eines über seinen Namen.",
        "eddies_title": "Offene Eddies",
        "parked_title": "Geparkt",
        "parked_quiet": "Gerade nicht aktiv.",
        "no_eddies": "Hier gibt es noch keine Eddies. Drück unten auf **new eddy**, um eines zu öffnen.",
        "no_note": "Noch keine Notiz",
        "more": "…und {n} weitere. `!eddy all` zeigt sie.",
        "live": "offen",
        "kept": "behalten",
        "sealed": "versiegelt",
        "resting": "geparkt",
        "live_title": "Was in {name} lebendig ist",
        "live_quiet": "Wo deine Praxis in diesem Kanal steht.",
        "toward": "Auf **{x}** zu: die passenden Themen kommen zuerst.",
        "carried_title": "Turtle hat diese im Sinn",
        "carried_quiet": "In jeder Antwort hier, ohne dass du sie erwähnst.",
        "rest_title": "Kommt auf, wenn du es erwähnst",
        "rest_quiet": "Turtle holt diese dazu, wenn deine Nachricht sie berührt.",
        "no_topics": "Hier hat sich noch nichts angesammelt. Ein Thema entsteht, sobald zwei Gespräche zum selben zurückkehren.",
        "conversations": "{n} Gespräche",
        "waiting_title": "Wartet",
        "waiting_quiet": "Wer den nächsten Zug hat.",
        "move_you": "Dein Zug",
        "move_session": "Bereit: wartet auf eine Sitzung",
        "move_confirm": "Wartet auf dein Ja",
        "move_other": "Wartet auf {who}",
        "dates_title": "Demnächst",
        "dates_quiet": "Die nächsten zwei Wochen.",
        "left_out": "{n} weitere Abschnitte passen nicht auf eine Karte.",
        "summary_hidden": "Ein sensibler Raum: Themen zeigen Größe und Zeitpunkt, nicht ihre Worte.",
        "topic_n": "Thema {n}",
    },
}

LIVE_EDDIES = 5  # a glance: the five that were touched last
EDDY_LIST = 7  # the kit's row limit
NOTE_CHARS = ui_kit.ITEM_LINE_MAX
SENSITIVE_POLICIES = frozenset({"sensitive_local"})  # channel_primitives data_policy


def _t(locale: str) -> dict:
    return _TEXT.get(locale) or _TEXT["en"]


@dataclass
class Place:
    """The channel a pattern is run in, and everything a provider may read about it."""

    parent: Any
    parent_id: int
    name: str
    guild_id: int | None
    primitive: Any  # channel_primitives.ChannelPrimitive | None
    practice_dir: Path | None
    runtime_dir: Path | None
    locale: str = "en"
    now: datetime | None = None
    threads: dict | None = None  # registry rows, by thread id
    records: list = field(default_factory=list)  # every eddy of this channel, newest activity first
    coming: list = field(default_factory=list)  # (title, date in words) for the next two weeks, soonest first

    @property
    def t(self) -> dict:
        return _t(self.locale)

    @property
    def exclude_shared_rooms(self) -> bool:
        return bool(self.primitive and self.primitive.memory_boundary == "personal_without_shared")

    @property
    def sensitive(self) -> bool:
        return bool(self.primitive and self.primitive.data_policy in SENSITIVE_POLICIES)


# ── Links and small words ──────────────────────────────────────────────


def _link(name: str, guild_id, thread_id) -> str:
    clean = (name or "eddy").replace("[", "(").replace("]", ")").strip() or "eddy"
    url = f"https://discord.com/channels/{guild_id}/{thread_id}" if guild_id and thread_id else ""
    return f"[{clean}]({url})" if url else clean


def _relative(unix: float) -> str:
    return f"<t:{int(unix)}:R>"


def _clip(text: str, limit: int = NOTE_CHARS) -> str:
    flat = " ".join((text or "").split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


def _first_sentence(text: str) -> str:
    flat = " ".join((text or "").split())
    return re.split(r"(?<=[.!?])\s+", flat)[0] if flat else ""


def held_line(practice_dir: Path | None, thread_id) -> str:
    """What the eddy last held, in the note's own first sentence. Empty when it has no note."""
    if not practice_dir:
        return ""
    from story_entries import EDDIES_SUBDIR, parse_eddy_file_entries

    folder = Path(practice_dir) / EDDIES_SUBDIR
    if not folder.is_dir():
        return ""
    latest = ("", "")
    for path in folder.glob(f"{thread_id}-*.md"):
        try:
            entries = parse_eddy_file_entries(path.read_text(encoding="utf-8"))
        except OSError:
            continue
        for front, body in entries:
            stamp = str(front.get("timestamp") or "")
            if stamp >= latest[0]:
                latest = (stamp, body)
    return _clip(_first_sentence(latest[1]))


# ── Eddies ─────────────────────────────────────────────────────────────


def eddy_records(place: Place, *, days: int | None = None) -> list[dict]:
    """The channel's eddies, newest activity first; a spoken window is a filter, not a new list."""
    if days is None:
        return list(place.records)
    return [r for r in place.records if r.get("age_seconds", 1e18) <= days * 86400]


def _eddy_item(record: dict, place: Place) -> ui_kit.Item:
    when = place.now.timestamp() - float(record.get("age_seconds") or 0)
    held = held_line(place.practice_dir, record["thread_id"]) or place.t["no_note"]
    return ui_kit.Item(_link(record["name"], place.guild_id, record["thread_id"]), held, meta=_relative(when))


def _counts(records: list[dict], t: dict) -> str:
    order = ("live", "kept", "sealed", "resting")
    bits = [f"{sum(r['state'] == s for r in records)} {t[s]}" for s in order if any(r["state"] == s for r in records)]
    return " · ".join(bits)


def eddies_cards(place: Place, *, limit: int = EDDY_LIST, show_all: bool = False, days: int | None = None) -> tuple[list[ui_kit.Card], list]:
    """(cards, notes). Open eddies first; parked ones only when asked for."""
    t = place.t
    every = eddy_records(place, days=days)
    open_ = [r for r in every if r["state"] in ("live", "kept", "sealed")]
    parked = [r for r in every if r["state"] == "resting"]
    cards: list[ui_kit.Card] = []
    notes: list = []
    if open_:
        cards.append(
            ui_kit.Card(
                title=t["eddies_title"],
                quiet=_counts(every, t),
                rows=tuple(_eddy_item(r, place) for r in open_[:limit]),
            )
        )
        if len(open_) > limit:
            notes.append(ui_kit.Note(f"-# {t['more'].format(n=len(open_) - limit)}"))
    if show_all and parked:
        cards.append(
            ui_kit.Card(
                title=t["parked_title"], quiet=t["parked_quiet"],
                rows=tuple(_eddy_item(r, place) for r in parked[:limit]),
            )
        )
        if len(parked) > limit:
            notes.append(ui_kit.Note(f"-# {t['more'].format(n=len(parked) - limit)}"))
    return cards, notes


def eddies_view(place: Place, *, show_all: bool = False, days: int | None = None):
    t = place.t
    cards, notes = eddies_cards(place, show_all=show_all, days=days)
    if not cards:
        return ui_kit.build([ui_kit.Header(t["eddy_title"], t["eddy_quiet"]), ui_kit.Note(t["no_eddies"])])
    return ui_kit.build([ui_kit.Header(t["eddy_title"], t["eddy_quiet"]), *cards, *notes])


# ── Live ───────────────────────────────────────────────────────────────


def _unix_of(when: str) -> float | None:
    try:
        parsed = datetime.fromisoformat(str(when))
    except (TypeError, ValueError):
        return None
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).timestamp()


def _related_links(topic: dict, place: Place, *, limit: int = 2) -> list[str]:
    """The newest distinct eddies this topic came from, that still exist."""
    out: list[str] = []
    seen: set[str] = set()
    for entry in topic.get("entries") or []:
        thread = str(entry.get("thread") or "")
        info = (place.threads or {}).get(thread)
        if not thread or thread in seen or not info or info.get("harvest_status") == "dissolved":
            continue
        seen.add(thread)
        out.append(_link(info.get("name") or entry.get("title"), place.guild_id, thread))
        if len(out) >= limit:
            break
    return out


def _topic_item(topic: dict, place: Place, n: int) -> ui_kit.Item:
    t = place.t
    count = t["conversations"].format(n=topic.get("conversations") or 0)
    line = count if place.sensitive else (_clip(str(topic.get("summary") or "")) or count)
    latest = next((_unix_of(e.get("when")) for e in topic.get("entries") or [] if _unix_of(e.get("when"))), None)
    bits = [] if place.sensitive or line == count else [count]
    if latest:
        bits.append(_relative(latest))
    bits += _related_links(topic, place)
    label = t["topic_n"].format(n=n) if place.sensitive else (str(topic.get("label") or "") or t["topic_n"].format(n=n))
    return ui_kit.Item(label, line, meta=" · ".join(bits))


def _topic_cards(place: Place, toward: str) -> tuple[list[ui_kit.Card], list]:
    from memory_agent import live_topics

    t = place.t
    if not place.practice_dir:
        return [], [ui_kit.Note(t["no_topics"])]
    carried, rest, _ = live_topics(place.practice_dir, exclude_shared_rooms=place.exclude_shared_rooms, toward=toward)
    if not carried and not rest:
        return [], [ui_kit.Note(t["no_topics"])]
    cards = []
    if carried:
        cards.append(ui_kit.Card(title=t["carried_title"], quiet=t["carried_quiet"], rows=tuple(_topic_item(x, place, i) for i, x in enumerate(carried, 1))))
    if rest:
        cards.append(ui_kit.Card(title=t["rest_title"], quiet=t["rest_quiet"], rows=tuple(_topic_item(x, place, i) for i, x in enumerate(rest, len(carried) + 1))))
    return cards, []


def _craft_waiting(place: Place) -> list[ui_kit.Card]:
    """Craft: the eddies that wait, and for whom. Session first, then you."""
    from core.craft_readiness import waiting_glance_rows

    t = place.t
    if not place.runtime_dir:
        return []
    rows = waiting_glance_rows(
        place.runtime_dir, place.threads or {}, parent_name=getattr(place.parent, "name", None), parent_id=place.parent_id
    )
    if not rows:
        return []
    items = []
    for row in rows[:LIVE_EDDIES]:
        move = row.get("move") or ""
        line = {"you": t["move_you"], "session": t["move_session"], "confirm": t["move_confirm"]}.get(move) or t["move_other"].format(who=move)
        items.append(ui_kit.Item(_link(row["name"], place.guild_id, row["thread_id"]), _clip(line)))
    return [ui_kit.Card(title=t["waiting_title"], quiet=t["waiting_quiet"], rows=tuple(items))]


def _dates_coming(place: Place) -> list[ui_kit.Card]:
    """A personal river: the dates the next two weeks hold."""
    t = place.t
    if not place.coming:
        return []
    items = tuple(ui_kit.Item(_clip(title or "?", 60), when) for title, when in place.coming[:LIVE_EDDIES])
    return [ui_kit.Card(title=t["dates_title"], quiet=t["dates_quiet"], rows=items)]


# What each practice adds to the live state. A channel primitive appears in exactly one
# of these two tables, and `tests/test_practice_views.py` says so, so a new kind of
# channel cannot arrive without someone deciding what its live state is.
LIVE_EXTRAS: dict[str, Callable[[Place], list[ui_kit.Card]]] = {
    "craft": _craft_waiting,  # whose move each eddy is waiting on
    "private": _dates_coming,  # the dates this person asked to be reminded of
}
NO_LIVE_EXTRAS: dict[str, str] = {
    "shared": "a room of several people: what is live is the shared eddies and topics; no one's private dates belong here",
    "partnership": "same as shared; two people's live state is what they both said here",
    "team": "its own shared work state (goals, lanes, tasks) is a larger design; not guessed here",
    "magic": "the practice itself lives in the workshop's files, not in the room's topics; the live card says what is moving and adds nothing from outside it",
    "health": "sensitive: the card shows the shape of what is moving and none of its words, and adds nothing else",
}


def live_cards(place: Place, *, toward: str = "") -> tuple[list[ui_kit.Card], list]:
    topics, notes = _topic_cards(place, toward)
    eddies, more = eddies_cards(place, limit=LIVE_EDDIES)
    extras: list[ui_kit.Card] = []
    provider = LIVE_EXTRAS.get(place.primitive.name if place.primitive else "")
    if provider:
        extras = provider(place)
    return [*topics, *eddies, *extras], [*notes, *more]


def live_view(place: Place, *, toward: str = ""):
    t = place.t
    head: list = [ui_kit.Header(t["live_title"].format(name=place.name), t["live_quiet"])]
    if toward:
        head.append(ui_kit.Note(f"-# {t['toward'].format(x=toward)}"))
    if place.sensitive:
        head.append(ui_kit.Note(f"-# {t['summary_hidden']}"))
    cards, notes = live_cards(place, toward=toward)
    used = sum(i.parts() for i in head) + sum(n.parts() for n in notes)
    shown, hidden = ui_kit.fit(cards, ui_kit.PART_BUDGET - used - 1)
    tail = [ui_kit.Note(f"-# {t['left_out'].format(n=hidden)}")] if hidden else []
    return ui_kit.build([*head, *shown, *notes, *tail])
