"""Memory agent — memory as a byproduct of practice, curated into topics.

The room already writes its memory: every checkpoint leaves an eddy note under
``story/eddies/``. Entwine may also write derived notes under
``story/exogenous/`` — history that did not happen in this room. Room memory (``continuity_engine.render_scope_block``) reads
the last few of those by recency, which answers *what has been said here
lately* and nothing else. On 2026-09-01 a member asked what Turtle remembered
about a topic the room had discussed in 30 notes over five weeks; the newest
was 7.5 days old, the window was 7 days, and Turtle said there was no archive.

This module is the other half: a curator that reads **all** of a room's notes
and forms **topics** — what the room keeps returning to — with a heat that
decays by half-life rather than a window that cuts. The result is written as
readable markdown under ``memory/`` and is rebuilt from the notes on demand, so
nothing here is standing state that can drift from its source: delete
``memory/`` and rebuild it and you get the same answer (``--rebuild``).

Two formation paths, same output:

- **keyword** — deterministic clustering on salient words shared across
  conversations. Always available; the positive control for the other path.
- **model** — the reflection model groups the entry listing into named topics
  with a one-line summary each. Entry ids it invents are dropped; a topic it
  forms from one conversation is dropped unless recent.

Boundaries (TURTLE_SPEC §15.5, asymmetric by design, Mage 2026-09-03):

- A **shared** room's memory is formed from its own notes only.
- A **personal** root's memory may also include the shared rooms that
  practitioner is a member of — a member remembers the rooms they are in.
- Nothing ever reads another practitioner's personal root. Private content
  reaches a shared room only when a member shares it (link, share eddy).

``memory_roots_for`` is the single place that rule lives; the tests in
``tests/test_memory_agent.py`` are what fails when it stops being true.
"""

from __future__ import annotations

import json
import math
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable
from zoneinfo import ZoneInfo

import yaml

from core.atomic_io import atomic_write_text
from story_entries import EDDIES_SUBDIR, entry_from_front, parse_eddy_file_entries

EXOGENOUS_SUBDIR = Path("story") / "exogenous"
EXOGENOUS_DROP_ROUTES = frozenset({"skip"})
EXOGENOUS_ORIGIN_PHRASE = "from a ChatGPT conversation you imported"
_NATIVE_WE_VOICE = re.compile(
    r"\b("
    r"I remember when we|"
    r"we (?:talked|discussed|spoke|chatted)(?: about| of)?|"
    r"when we (?:talked|discussed|spoke)|"
    r"our (?:conversation|chat) (?:last year|last month|together|here)"
    r")\b",
    re.I,
)

MEMORY_SUBDIR = Path("memory")
TOPICS_YAML = "topics.yaml"
TOPICS_INDEX = "topics.md"
TOPICS_DIR = "topics"
MEMORY_SCHEMA_VERSION = 1

# Heat halves every three weeks. A topic touched in 30 conversations over five
# weeks stays hot for a month after the last one; a single mention is cold in
# three. Chosen so the 2026-09-01 case (last touch 7.5 d before the question)
# is unambiguously hot — and named here so the eval can move it on evidence.
HEAT_HALF_LIFE_DAYS = 21.0
# A topic needs this many distinct conversations to exist at all, unless its
# newest entry is within RECENT_DAYS — a theme raised yesterday in one eddy is
# alive even though it has not recurred yet.
MIN_CONVERSATIONS = 2
RECENT_DAYS = 3
MAX_TOPICS = 12
MAX_EXCERPTS_PER_TOPIC = 6
EXCERPT_CHARS = 320

# Passive injection budget — what a turn carries about the room's topics.
TOPIC_BLOCK_TOP_N = 3
TOPIC_BLOCK_MATCH_N = 2
TOPIC_BLOCK_CHAR_BUDGET = 3200
TOPIC_BLOCK_EXCERPTS = 2

# Glance — related sediment only. Heat is a tie-break, never a fill-in.
# One shared name (e.g. "Kermit" in a Derek note) is not relatedness.
GLANCE_MATCH_N = 3
GLANCE_MIN_SCORE = 2
GLANCE_EXCERPTS = 1
GLANCE_CHAR_BUDGET = 1200
GLANCE_REACH_CHARS = 4000
GLANCE_NOTE_CHARS = 2000
_GLANCE_SKIP = frozenset({".", "..", "...", "go", "continue", "next"})

_STOPWORDS = frozenset(
    """
    the and for with that this from your you about their there they them then
    than into over under between during while after before again more most
    some such very just also only both each other were been being have has had
    what when where which who whom whose will would could should might must
    shall does did done doing make made makes making take took taken taking
    give gave given going went come came like need needs needed want wants
    wanted feel feels feeling felt think thinks thought know knows knew known
    says said saying tell tells told turtle kermit conversation conversations
    today tonight morning evening afternoon week weeks month months year years
    time times thing things something anything nothing everything someone
    around through without within toward towards because since until upon
    really still already maybe perhaps another together toward first last next
    talk talked talking asked asking ask shared share sharing discussion discussed
    """.split()
)


@dataclass
class MemoryEntry:
    """One note entry as the memory agent sees it — native eddy or exogenous."""

    ref: str  # "<room>:<index>" — stable within one build
    room: str  # registry key or directory name of the root it came from
    thread: str
    title: str
    timestamp: datetime
    themes: list[str]
    body: str
    source_path: str
    participants: list[str] = field(default_factory=list)
    origin: str = ""
    origin_platform: str = ""


@dataclass
class Topic:
    id: str
    label: str
    summary: str
    entries: list[MemoryEntry]
    heat: float = 0.0
    conversations: int = 0
    since: str = ""
    last_seen: str = ""
    rooms: list[str] = field(default_factory=list)
    formed_by: str = "keyword"
    keywords: list[str] = field(default_factory=list)

    def to_record(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "summary": self.summary,
            "keywords": list(self.keywords),
            "heat": round(self.heat, 3),
            "conversations": self.conversations,
            "since": self.since,
            "last_seen": self.last_seen,
            "rooms": list(self.rooms),
            "formed_by": self.formed_by,
            "entries": [
                {
                    "when": e.timestamp.isoformat(timespec="minutes"),
                    "thread": e.thread,
                    "title": e.title,
                    "room": e.room,
                    "who": _attribution(e),
                    "source": e.source_path,
                    "origin": e.origin,
                    "origin_platform": e.origin_platform,
                    "excerpt": " ".join(e.body.split())[:EXCERPT_CHARS].rstrip(),
                }
                for e in sorted(self.entries, key=lambda e: e.timestamp, reverse=True)
            ],
        }


# ─── Roots and boundaries ────────────────────────────────────────────


def memory_roots_for(
    practice_dir: str | os.PathLike,
    *,
    registry: dict[str, Any] | None,
    key: str | None,
    kind: str | None,
    boundary: str | None = None,
) -> list[tuple[str, Path]]:
    """The roots whose notes may form this root's memory: ``[(room, path), …]``.

    Own root first. A personal root (``kind == "mage"``) adds every shared
    space whose member list names ``key``, except spaces marked
    ``memory: isolated`` (health is the first). A shared space adds nothing.
    A root the registry does not know (``key is None``) is its own memory
    and nothing else — the rule fails closed.

    Pure: the registry and the resolved ``(key, kind)`` are passed in, so this
    module never imports the registry and the rule can be tested with a dict.
    ``mage.memory_roots`` is the glue that supplies them from the live registry.
    """
    own = Path(practice_dir).expanduser()
    roots: list[tuple[str, Path]] = [(key or own.name or "room", own)]
    if boundary in {"own_root", "isolated", "personal_without_shared"}:
        return roots
    if boundary is not None and boundary != "personal_plus_shared":
        return roots
    if kind != "mage" or not key or not registry:
        return roots
    spaces = registry.get("spaces") or {}
    for space_key, space in spaces.items():
        if not isinstance(space, dict) or space.get("archived"):
            continue
        if str(space.get("memory") or "").strip().lower() == "isolated":
            continue
        members = [str(m) for m in (space.get("members") or [])]
        if key not in members:
            continue
        configured = space.get("practice_dir")
        if not configured:
            continue
        path = Path(os.path.expanduser(str(configured)))
        if path.resolve() == own.resolve():
            continue
        roots.append((str(space_key), path))
    return roots


def own_root(practice_dir: str | os.PathLike) -> list[tuple[str, Path]]:
    """A root as its own only memory source — what a shared room gets."""
    own = Path(practice_dir).expanduser()
    return [(own.name or "room", own)]


# ─── Collection ──────────────────────────────────────────────────────


def _tz() -> ZoneInfo:
    # Same source and default as ``state.PRACTICE_TIMEZONE``; read here directly
    # so this module stays a leaf (see the import-graph baseline).
    return ZoneInfo(os.environ.get("PRACTICE_TIMEZONE", "Europe/Berlin"))


def collect_entries(roots: list[tuple[str, Path]]) -> list[MemoryEntry]:
    """Every eddy note and kept exogenous note under each root, all time."""
    tz = _tz()

    out: list[MemoryEntry] = []
    for room, root in roots:
        index = 0
        eddies = root / EDDIES_SUBDIR
        if eddies.is_dir():
            for note_path in sorted(eddies.glob("*.md")):
                try:
                    content = note_path.read_text(encoding="utf-8")
                except OSError:
                    continue
                for front, body in parse_eddy_file_entries(content):
                    entry = entry_from_front(front, body, note_path, tz)
                    if entry is None:
                        continue
                    index += 1
                    out.append(
                        MemoryEntry(
                            ref=f"{room}:{index}",
                            room=room,
                            thread=entry.thread,
                            title=entry.title,
                            timestamp=entry.timestamp,
                            themes=list(entry.proposed_themes) + list(entry.related_topics),
                            body=_strip_frontmatter(entry.body),
                            source_path=str(note_path.relative_to(root)),
                            participants=list(entry.participants),
                        )
                    )
        exogenous = root / EXOGENOUS_SUBDIR
        if exogenous.is_dir():
            for note_path in sorted(exogenous.rglob("*.md")):
                entry = _entry_from_exogenous(note_path, root, room, tz, index + 1)
                if entry is None:
                    continue
                index += 1
                entry.ref = f"{room}:{index}"
                out.append(entry)
    out.sort(key=lambda e: e.timestamp)
    return out


def _entry_from_exogenous(
    note_path: Path,
    root: Path,
    room: str,
    tz: ZoneInfo,
    index: int,
) -> MemoryEntry | None:
    """One Entwine note. Does not open an archive; the note is the corpus."""
    try:
        content = note_path.read_text(encoding="utf-8")
    except OSError:
        return None
    blocks = parse_eddy_file_entries(content)
    if not blocks:
        return None
    front, body = blocks[0]
    source = str(front.get("source") or "").strip().lower()
    if not source.startswith("exogenous/"):
        return None
    route = str(front.get("route") or "").strip().lower()
    if route in EXOGENOUS_DROP_ROUTES:
        return None
    stamp = _exogenous_timestamp(front, tz)
    if stamp is None:
        return None
    conversation_id = str(front.get("conversation_id") or note_path.stem).strip()
    platform = str(front.get("origin_platform") or source.split("/", 1)[-1]).strip()
    themes = front.get("proposed-themes") or front.get("themes") or []
    if not isinstance(themes, list):
        themes = []
    return MemoryEntry(
        ref=f"{room}:{index}",
        room=room,
        thread=conversation_id,
        title=str(front.get("title") or conversation_id).strip(),
        timestamp=stamp,
        themes=[str(t).strip() for t in themes if str(t).strip()],
        body=_strip_frontmatter(body),
        source_path=str(note_path.relative_to(root)),
        origin=source,
        origin_platform=platform,
    )


def _exogenous_timestamp(front: dict[str, Any], tz: ZoneInfo) -> datetime | None:
    for key in ("created", "updated", "timestamp", "entwined"):
        raw = front.get(key)
        if not raw:
            continue
        text = str(raw).strip()
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            try:
                parsed = datetime.strptime(text, "%Y-%m-%d")
            except ValueError:
                continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=tz)
        else:
            parsed = parsed.astimezone(tz)
        return parsed
    return None


def has_native_we_voice(text: str) -> bool:
    """True when a reply claims this room had the talk — the Entwine lie."""
    return bool(_NATIVE_WE_VOICE.search(text or ""))


def _strip_frontmatter(text: str) -> str:
    return re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.S).strip()


# ─── Heat ────────────────────────────────────────────────────────────


def heat_of(entries: list[MemoryEntry], now: datetime) -> float:
    """Sum of half-life decayed weights, one per entry."""
    total = 0.0
    for e in entries:
        age = max(0.0, (now - e.timestamp).total_seconds() / 86400.0)
        total += math.pow(0.5, age / HEAT_HALF_LIFE_DAYS)
    return total


def _finish_topic(topic: Topic, now: datetime) -> Topic:
    entries = sorted(topic.entries, key=lambda e: e.timestamp)
    topic.entries = entries
    topic.heat = heat_of(entries, now)
    topic.conversations = len({e.thread for e in entries})
    topic.since = entries[0].timestamp.strftime("%Y-%m-%d") if entries else ""
    topic.last_seen = entries[-1].timestamp.strftime("%Y-%m-%d") if entries else ""
    topic.rooms = sorted({e.room for e in entries})
    return topic


def _keep(topic: Topic, now: datetime) -> bool:
    if not topic.entries:
        return False
    if topic.conversations >= MIN_CONVERSATIONS:
        return True
    newest = max(e.timestamp for e in topic.entries)
    return (now - newest).total_seconds() / 86400.0 <= RECENT_DAYS


# ─── Formation: keyword (deterministic) ──────────────────────────────


_WORD_RE = re.compile(r"[a-zäöüß][a-zäöüß'-]{3,}", re.I)


def salient_words(text: str) -> set[str]:
    """Content words: no stopwords, no adverbs (-ly), no past-tense verbs (-ed).

    A crude part-of-speech filter, but the failure it removes is concrete: on
    the first real corpus the seeds were "rather / agreements", "instead /
    anymore", "responded / cats" — narrative glue, not what the room is about.
    """
    words = {
        re.sub(r"'s$", "", w.lower().strip("'-")) for w in _WORD_RE.findall(text or "")
    }
    return {
        w
        for w in words
        if len(w) >= 4
        and w not in _STOPWORDS
        and not w.endswith("ly")
        and not (w.endswith("ed") and len(w) > 5)
    }


def _headline_words(entry: MemoryEntry) -> set[str]:
    """Words from what the note-writer itself chose as title and themes."""
    return salient_words(" ".join([entry.title, *entry.themes]))


def _entry_words(entry: MemoryEntry) -> set[str]:
    return salient_words(" ".join([entry.title, *entry.themes, entry.body[:600]]))


def form_topics_keyword(entries: list[MemoryEntry], now: datetime) -> list[Topic]:
    """Cluster entries by salient words that recur across conversations.

    A word becomes a topic seed when it appears in entries from at least
    ``MIN_CONVERSATIONS`` distinct threads. Seeds whose entry sets mostly
    overlap merge into one topic labelled by their words. Crude on purpose:
    it needs no model, and it is what the model path is measured against.
    """
    # Seeds come from titles and themes — the labels the note-writer chose —
    # while membership may match anywhere in the entry, so a note whose theme
    # phrase avoided the word still joins the topic it is plainly about.
    words_by_entry = {e.ref: _entry_words(e) for e in entries}
    threads_by_word: dict[str, set[str]] = defaultdict(set)
    entries_by_word: dict[str, list[MemoryEntry]] = defaultdict(list)
    for e in entries:
        for w in _headline_words(e):
            threads_by_word[w].add(e.thread)
            entries_by_word[w].append(e)

    def _recent(e: MemoryEntry) -> bool:
        return (now - e.timestamp).total_seconds() / 86400.0 <= RECENT_DAYS

    seeds = [
        w
        for w, threads in threads_by_word.items()
        if len(threads) >= MIN_CONVERSATIONS or any(_recent(e) for e in entries_by_word[w])
    ]
    # Words present in nearly every note describe the room, not a topic. Only
    # meaningful once there are enough notes for "nearly every" to mean much.
    total = max(1, len(entries))
    if total >= 10:
        seeds = [w for w in seeds if len(entries_by_word[w]) / total <= 0.8]
    # Tighter words first, so a broad word that happens to co-occur joins a
    # specific cluster rather than anchoring one and pulling strangers in.
    seeds.sort(key=lambda w: (len(entries_by_word[w]), w))

    clusters: list[tuple[list[str], set[str]]] = []  # (words, entry refs)
    for w in seeds:
        refs = {e.ref for e in entries_by_word[w]}
        merged = False
        for words, members in clusters:
            overlap = len(refs & members) / max(1, min(len(refs), len(members)))
            if overlap >= 0.6:
                words.append(w)
                merged = True
                break
        if not merged:
            clusters.append(([w], set(refs)))

    # Membership is decided per entry, against the whole cluster: an entry that
    # shares one broad word with a cluster of five is not about that topic.
    by_ref = {e.ref: e for e in entries}
    for words, members in clusters:
        need = max(1, math.ceil(len(words) / 2))
        members.clear()
        for e in entries:
            if len(words_by_entry[e.ref] & set(words)) >= need:
                members.add(e.ref)
    names = {p.lower() for e in entries for p in e.participants}
    topics: list[Topic] = []
    for words, members in clusters:
        # Label from the words the notes themselves used as titles or themes —
        # the reflection model's own naming — never from participant names.
        member_entries = [by_ref[r] for r in members]
        headline = Counter()
        for e in member_entries:
            for w in salient_words(" ".join([e.title, *e.themes])):
                headline[w] += 1
        candidates = [w for w in words if w not in names]
        candidates.sort(key=lambda w: (-headline.get(w, 0), -len(entries_by_word[w]), w))
        label = " / ".join(candidates[:3]) or " / ".join(words[:3])
        topic = Topic(
            id=_slug(label),
            label=label,
            summary="",
            keywords=candidates[:8],
            entries=[by_ref[r] for r in members],
            formed_by="keyword",
        )
        topic = _finish_topic(topic, now)
        if _keep(topic, now):
            topics.append(topic)
    topics.sort(key=lambda t: t.heat, reverse=True)
    return topics[:MAX_TOPICS]


# ─── Formation: model ────────────────────────────────────────────────


_FORMATION_SYSTEM = (
    "You curate the memory of a shared practice space from its own notes. "
    "You group note entries into the topics the people here keep returning to. "
    "You never invent entries, people, or events; you only group what is listed. "
    "Every member of the space will read the topic names, so name topics the way "
    "a fair witness would — what the topic is about, never a verdict on a person: "
    "no diagnoses, no character judgements, no one's 'hypocrisy' or 'loyalty'. "
    "Answer with JSON only."
)


def _listing(entries: list[MemoryEntry]) -> str:
    lines = []
    for e in entries:
        first = " ".join(e.body.split())[:160]
        themes = "; ".join(e.themes[:3])
        lines.append(
            f"{e.ref} | {e.timestamp.strftime('%Y-%m-%d')} | {e.title} | {themes} | {first}"
        )
    return "\n".join(lines)


def formation_prompt(entries: list[MemoryEntry]) -> str:
    return (
        "Below is every checkpoint note of this space, one per line: "
        "id | date | conversation title | themes | opening words.\n\n"
        f"{_listing(entries)}\n\n"
        f"Group them into at most {MAX_TOPICS} topics that this space keeps returning to. "
        "A topic must span at least two different conversations unless it is from the last few days. "
        "Prefer topics a member would recognise by name (a relationship, a recurring situation, "
        "a plan, a person's condition) over abstract themes. Leave out entries that fit nothing.\n\n"
        "For each topic also give 3-8 keywords: the distinctive words and names that appear in "
        "notes about it (people, places, things — not feelings or abstractions). They are used to "
        "find every note on the topic, so include spelling variants that occur in the notes, and "
        "leave out words so general that notes on other topics contain them too (e.g. 'mother', "
        "'wife', 'family', 'home' on their own).\n\n"
        'Reply with JSON: {"topics": [{"label": "short plain-language name", '
        '"summary": "one sentence a member would agree with", '
        '"keywords": ["word", ...], "entries": ["id", ...]}]}'
    )


def assign_by_keywords(
    entries: list[MemoryEntry], keywords: list[str]
) -> list[MemoryEntry]:
    """Every entry whose text contains one of the keywords.

    The model names the topic and says what words mark it; which notes belong
    is then decided by reading the notes, deterministically, so recall does
    not depend on how many ids the model felt like listing. First real run:
    the model assigned 4 conversations to a topic the notes mention 30 times.
    """
    needles = [k.strip().lower() for k in keywords if len(k.strip()) >= 3]
    if not needles:
        return []
    out: list[MemoryEntry] = []
    for e in entries:
        hay = " ".join([e.title, *e.themes, e.body]).lower()
        if any(n in hay for n in needles):
            out.append(e)
    return out


# A topic name every member reads must say what the topic is about, not pass a
# verdict on one of them. The formation prompt says so; this is the part that
# holds when the prompt does not. First model run, before the instruction:
# "<member>'s Hypocrisy and Double Standards". Third run, with it: "<member>'s
# Loyalty and the 'Two Realities' Conflict". The pattern is a member's name
# next to a judgement word; the repair is to fall back to the topic's own
# keywords, which name things rather than people.
_VERDICT_WORDS = (
    "hypocri", "loyal", "narciss", "gaslight", "martyr", "manipulat", "toxic",
    "abus", "victim", "patholog", "enmesh", "selfish", "lazy", "fail", "blam",
    "guilt", "denial", "defensive", "double standard", "dishonest", "lying",
)


def neutralize_naming(label: str, summary: str, keywords: list[str], names: set[str]) -> tuple[str, str]:
    """Return (label, summary) safe for every member of the room to read.

    A label that pairs a member's name with a verdict word is replaced by the
    topic's keywords; a summary that does the same is dropped. Names alone are
    fine ("<child>'s birthday"); verdict words alone are fine ("defining
    narcissism" was a topic the room genuinely discussed).
    """
    def _judges(text: str) -> bool:
        low = text.lower()
        return any(n in low for n in names) and any(v in low for v in _VERDICT_WORDS)

    if _judges(label):
        label = " / ".join(k for k in keywords[:3] if not any(n in k.lower() for n in names)) or "a recurring topic"
    if _judges(summary):
        summary = ""
    return label, summary


def parse_formation_reply(raw: str, entries: list[MemoryEntry], now: datetime) -> list[Topic]:
    """Turn the model's JSON into topics; drop what it invented."""
    text = (raw or "").strip()
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    by_ref = {e.ref: e for e in entries}
    names = {p.lower() for e in entries for p in e.participants if len(p) >= 3}
    topics: list[Topic] = []
    for item in data.get("topics") or []:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        if not label:
            continue
        refs = [str(r).strip() for r in (item.get("entries") or [])]
        members = {r: by_ref[r] for r in refs if r in by_ref}
        keywords = [str(k) for k in (item.get("keywords") or []) if str(k).strip()]
        for e in assign_by_keywords(entries, keywords):
            members.setdefault(e.ref, e)
        if not members:
            continue
        label, summary = neutralize_naming(
            label, str(item.get("summary") or "").strip(), keywords, names
        )
        topic = Topic(
            id=_slug(label),
            label=label,
            summary=summary,
            keywords=keywords,
            entries=list(members.values()),
            formed_by="model",
        )
        topic = _finish_topic(topic, now)
        if _keep(topic, now):
            topics.append(topic)
    topics.sort(key=lambda t: t.heat, reverse=True)
    return topics[:MAX_TOPICS]


ChatFn = Callable[[str, list[dict[str, str]]], Awaitable[str]]


async def form_topics_model(
    entries: list[MemoryEntry], now: datetime, chat: ChatFn
) -> list[Topic]:
    raw = await chat(_FORMATION_SYSTEM, [{"role": "user", "content": formation_prompt(entries)}])
    return parse_formation_reply(raw, entries, now)


# ─── Writing ─────────────────────────────────────────────────────────


def memory_dir(practice_dir: str | os.PathLike) -> Path:
    return Path(practice_dir) / MEMORY_SUBDIR


def _slug(label: str) -> str:
    slug = re.sub(r"[^a-z0-9äöüß]+", "-", label.strip().lower()).strip("-")
    return slug[:60] or "topic"


def _attribution(entry: MemoryEntry) -> str:
    if entry.participants:
        return ", ".join(entry.participants[:3])
    return ""


def write_room_memory(
    practice_dir: str | os.PathLike,
    topics: list[Topic],
    *,
    now: datetime,
    roots: list[tuple[str, Path]],
    formed_by: str,
) -> Path:
    """Persist topics as ``memory/topics.yaml`` + readable markdown.

    The directory is replaced whole: memory is a derived view of the notes,
    and a stale topic file left behind would be the standing state this design
    refuses to keep.
    """
    mdir = memory_dir(practice_dir)
    tdir = mdir / TOPICS_DIR
    tdir.mkdir(parents=True, exist_ok=True)
    for stale in tdir.glob("*.md"):
        stale.unlink()

    newest = newest_note_at(roots)
    record = {
        "version": MEMORY_SCHEMA_VERSION,
        "built_at": now.isoformat(timespec="seconds"),
        # The notes as they stood when read; staleness is measured against
        # this, not against the clock, so "current" means "reflects the notes".
        "notes_newest_ts": newest.timestamp() if newest else 0.0,
        "formed_by": formed_by,
        "roots": [{"room": room, "path": str(path)} for room, path in roots],
        "topics": [t.to_record() for t in topics],
    }
    atomic_write_text(
        mdir / TOPICS_YAML,
        yaml.safe_dump(record, sort_keys=False, allow_unicode=True),
    )

    own_room = roots[0][0] if roots else ""
    index = [
        "# What this space keeps returning to",
        "",
        f"*Built {now.strftime('%Y-%m-%d %H:%M')} from {sum(len(t.entries) for t in topics)} "
        f"note entries across {len(roots)} room(s) — formed by {formed_by}. "
        "Derived from the eddy notes; rebuild with `python3 scripts/memory_rebuild.py <root> --rebuild`.*",
        "",
        "| Topic | Since | Last | Conversations | Heat | Where |",
        "|---|---|---|---|---|---|",
    ]
    for t in topics:
        where = ", ".join("here" if r == own_room else r for r in t.rooms)
        index.append(
            f"| [{t.label}]({TOPICS_DIR}/{t.id}.md) | {t.since} | {t.last_seen} | "
            f"{t.conversations} | {t.heat:.1f} | {where} |"
        )
        page = [
            f"# {t.label}",
            "",
            f"*{t.conversations} conversations, {t.since} → {t.last_seen}; heat {t.heat:.1f}.*",
            "",
        ]
        if t.summary:
            page += [t.summary, ""]
        page.append("## What was written, newest first")
        page.append("")
        for e in sorted(t.entries, key=lambda e: e.timestamp, reverse=True)[:MAX_EXCERPTS_PER_TOPIC]:
            excerpt = " ".join(e.body.split())[:EXCERPT_CHARS].rstrip()
            who = _attribution(e)
            room = "" if e.room == own_room else f" · in {e.room}"
            page.append(
                f"- **{e.timestamp.strftime('%Y-%m-%d')}** — *{e.title}*"
                f"{' (' + who + ')' if who else ''}{room}: {excerpt}"
            )
        if len(t.entries) > MAX_EXCERPTS_PER_TOPIC:
            page.append(f"- … and {len(t.entries) - MAX_EXCERPTS_PER_TOPIC} earlier entries.")
        page += ["", "## Sources", ""]
        page += [f"- {e.room}: `{e.source_path}`" for e in t.entries]
        atomic_write_text(tdir / f"{t.id}.md", "\n".join(page) + "\n")
    atomic_write_text(mdir / TOPICS_INDEX, "\n".join(index) + "\n")
    return mdir


def read_topics(practice_dir: str | os.PathLike) -> list[dict[str, Any]]:
    path = memory_dir(practice_dir) / TOPICS_YAML
    if not path.exists():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, dict):
        return []
    topics = data.get("topics")
    return list(topics) if isinstance(topics, list) else []


# ─── Building ────────────────────────────────────────────────────────
#
# Every builder takes ``roots`` — the ``(room, path)`` list ``memory_roots_for``
# produces — rather than resolving them. Resolution needs the registry, and the
# registry lives in ``mage``, inside the runtime's mutual-dependency component;
# this module stays outside it (import-graph baseline). ``mage.memory_roots``
# is the one-line glue callers use.

Roots = list[tuple[str, Path]]


def build_room_memory(
    practice_dir: str | os.PathLike,
    roots: Roots | None = None,
    *,
    now: datetime | None = None,
    topics: list[Topic] | None = None,
    formed_by: str = "keyword",
) -> list[Topic]:
    """Synchronous build: collect, form (keyword unless topics given), write."""
    now = now or datetime.now().astimezone()
    roots = roots if roots is not None else own_root(practice_dir)
    entries = collect_entries(roots)
    if topics is None:
        topics = form_topics_keyword(entries, now)
        formed_by = "keyword"
    write_room_memory(practice_dir, topics, now=now, roots=roots, formed_by=formed_by)
    return topics


async def rebuild_room_memory(
    practice_dir: str | os.PathLike,
    roots: Roots | None = None,
    *,
    now: datetime | None = None,
    chat: ChatFn | None = None,
) -> list[Topic]:
    """Rebuild from the notes. Model formation when ``chat`` is given, keyword otherwise.

    A model reply that yields no topics is treated as unavailable, not as
    "the room has no topics": the keyword path decides that, deterministically.
    """
    now = now or datetime.now().astimezone()
    roots = roots if roots is not None else own_root(practice_dir)
    entries = collect_entries(roots)
    topics: list[Topic] = []
    formed_by = "keyword"
    if chat is not None and entries:
        try:
            topics = await form_topics_model(entries, now, chat)
            if topics:
                formed_by = "model"
        except Exception as exc:
            print(f"Memory formation (model) failed for {practice_dir}: {type(exc).__name__}: {exc}")
            topics = []
    if not topics:
        topics = form_topics_keyword(entries, now)
        formed_by = "keyword"
    write_room_memory(practice_dir, topics, now=now, roots=roots, formed_by=formed_by)
    return topics


# ─── Keeping it current ──────────────────────────────────────────────
#
# Currency is a state, drift is a rate: nothing here asks a checkpoint to
# remember to rebuild. An hourly pass asks two questions of each root — is the
# memory older than the newest note it should contain, and is anyone talking —
# and rebuilds when the answers are yes and no. The quiet check is the deploy
# guard's signal (dialogue/*.json mtimes) because a model-formed rebuild holds
# the inference gate for minutes, and a family member waiting on a reply must
# never pay for it.

REBUILD_QUIET_MINUTES = 10.0


def newest_note_at(roots: Roots) -> datetime | None:
    newest: float | None = None
    for _, root in roots:
        for folder in (root / EDDIES_SUBDIR, root / EXOGENOUS_SUBDIR):
            if not folder.is_dir():
                continue
            for path in folder.rglob("*.md"):
                try:
                    mtime = path.stat().st_mtime
                except OSError:
                    continue
                newest = mtime if newest is None or mtime > newest else newest
    return datetime.fromtimestamp(newest).astimezone() if newest is not None else None


def memory_is_stale(practice_dir: str | os.PathLike, roots: Roots | None = None) -> bool:
    """True when the notes have changed since the memory read them (or none exists)."""
    path = memory_dir(practice_dir) / TOPICS_YAML
    if not path.exists():
        return True
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        read_ts = float(data.get("notes_newest_ts") or 0.0)
    except Exception:
        return True
    newest = newest_note_at(roots if roots is not None else own_root(practice_dir))
    return newest is not None and newest.timestamp() > read_ts


def practice_is_quiet(
    roots: list[Path], minutes: float = REBUILD_QUIET_MINUTES, now: float | None = None
) -> bool:
    """No turn written under any of these roots in the last ``minutes``."""
    import time

    now = now if now is not None else time.time()
    for root in roots:
        for path in Path(root).glob("dialogue/*.json"):
            try:
                if now - path.stat().st_mtime < minutes * 60:
                    return False
            except OSError:
                continue
    return True


async def maintain_room_memories(
    rooms: list[tuple[Path, Roots]],
    *,
    chat: ChatFn | None = None,
) -> list[str]:
    """One pass: rebuild every root whose memory is stale, if the practice is quiet.

    ``rooms`` pairs each practice root with the roots its memory may read.
    Returns the roots rebuilt. Quiet is judged across *all* the roots given,
    since the inference gate is shared.
    """
    all_roots = [root for root, _ in rooms]
    stale = [(root, srcs) for root, srcs in rooms if root.is_dir() and memory_is_stale(root, srcs)]
    if not stale:
        return []
    if not practice_is_quiet(all_roots):
        print(f"Memory maintenance deferred: practice live, {len(stale)} root(s) stale")
        return []
    rebuilt: list[str] = []
    for root, srcs in stale:
        try:
            await rebuild_room_memory(root, srcs, chat=chat)
            rebuilt.append(str(root))
        except Exception as exc:
            print(f"Memory rebuild failed for {root}: {type(exc).__name__}: {exc}")
        if not practice_is_quiet(all_roots):
            break  # someone started talking; the rest waits for the next pass
    return rebuilt


# ─── Passive injection ───────────────────────────────────────────────


def _topic_haystack(
    topic: dict[str, Any],
    excerpts_by_topic: dict[str, list[str]] | None = None,
) -> str:
    return " ".join(
        [
            str(topic.get("label") or ""),
            str(topic.get("summary") or ""),
            *(str(k) for k in (topic.get("keywords") or [])),
            *(excerpts_by_topic or {}).get(str(topic.get("id")), []),
            *(str(e.get("title") or "") for e in (topic.get("entries") or [])),
        ]
    )


def topic_overlap_score(
    topic: dict[str, Any],
    words: set[str],
    excerpts_by_topic: dict[str, list[str]] | None = None,
) -> int:
    if not words:
        return 0
    return len(words & salient_words(_topic_haystack(topic, excerpts_by_topic)))


def select_topics(
    topics: list[dict[str, Any]],
    message_text: str = "",
    *,
    top_n: int = TOPIC_BLOCK_TOP_N,
    match_n: int = TOPIC_BLOCK_MATCH_N,
    excerpts_by_topic: dict[str, list[str]] | None = None,
) -> list[dict[str, Any]]:
    """The hottest topics, plus the ones the current message reaches for.

    Heat answers *what this room is about*; the message match answers *what is
    being asked right now*, so a topic that has cooled still surfaces when a
    member brings it up again — which is the 2026-09-01 case exactly.
    """
    ranked = sorted(topics, key=lambda t: float(t.get("heat") or 0.0), reverse=True)
    chosen = ranked[:top_n]
    chosen_ids = {t.get("id") for t in chosen}
    words = salient_words(message_text)
    if words and match_n > 0:
        scored: list[tuple[int, dict[str, Any]]] = []
        for t in ranked:
            if t.get("id") in chosen_ids:
                continue
            score = topic_overlap_score(t, words, excerpts_by_topic)
            if score:
                scored.append((score, t))
        scored.sort(key=lambda pair: (pair[0], float(pair[1].get("heat") or 0.0)), reverse=True)
        chosen.extend(t for _, t in scored[:match_n])
    return chosen


def _topic_match_haystack(topic: dict[str, Any]) -> str:
    """Label, summary, keywords — not excerpts or entry titles.

    Excerpts repeat the practitioner's name. Titles are worse: a mis-assigned
    note (this eddy filed under a family topic because it named the
    practitioner) would make that family topic match any glance here.
    """
    return " ".join(
        [
            str(topic.get("label") or ""),
            str(topic.get("summary") or ""),
            *(str(k) for k in (topic.get("keywords") or [])),
        ]
    )


def select_related_topics(
    topics: list[dict[str, Any]],
    conversation_text: str,
    *,
    match_n: int = GLANCE_MATCH_N,
    min_score: int = GLANCE_MIN_SCORE,
    excerpts_by_topic: dict[str, list[str]] | None = None,
) -> list[dict[str, Any]]:
    """Topics this conversation reaches for. Empty when it reaches for none.

    Heat is a tie-break only. The hottest topics are never filled in — that is
    the glance's difference from the passive packet. ``excerpts_by_topic`` is
    accepted and ignored: excerpts are for showing, not for matching.
    """
    del excerpts_by_topic
    words = salient_words(conversation_text)
    if not words or match_n <= 0:
        return []
    scored: list[tuple[int, float, dict[str, Any]]] = []
    for t in topics:
        score = len(words & salient_words(_topic_match_haystack(t)))
        if score >= min_score:
            scored.append((score, float(t.get("heat") or 0.0), t))
    scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return [t for _, _, t in scored[:match_n]]


def conversation_reach_text(
    thread_name: str = "",
    *,
    dialogue: list[dict[str, Any]] | None = None,
    note_text: str = "",
    char_budget: int = GLANCE_REACH_CHARS,
) -> str:
    """What the glance scores against — not the `...` itself."""
    parts: list[str] = []
    name = (thread_name or "").strip()
    if name:
        parts.append(name)
    note = (note_text or "").strip()
    if note:
        parts.append(note)
    for entry in dialogue or []:
        content = str(entry.get("content") or "").strip()
        if not content or content in _GLANCE_SKIP:
            continue
        parts.append(content)
    return "\n".join(parts)[: max(0, char_budget)]


def note_text_for_thread(
    practice_dir: str | os.PathLike,
    thread_id: int | str,
    *,
    char_budget: int = GLANCE_NOTE_CHARS,
) -> str:
    """This eddy's own notes — used as reach text, never as a related excerpt."""
    eddies = Path(practice_dir) / EDDIES_SUBDIR
    if not eddies.is_dir():
        return ""
    chunks: list[str] = []
    for path in sorted(eddies.glob(f"{thread_id}-*.md")):
        try:
            chunks.append(path.read_text(encoding="utf-8"))
        except OSError:
            continue
    return "\n".join(chunks)[: max(0, char_budget)]


def _excerpt_line(entry: dict[str, Any], own_room: str) -> str:
    when = str(entry.get("when") or "")[:10]
    who = str(entry.get("who") or "")
    room = str(entry.get("room") or "")
    origin = str(entry.get("origin") or "")
    platform = str(entry.get("origin_platform") or "ChatGPT")
    tail = f" ({who})" if who else ""
    if room and own_room and room != own_room:
        tail += f" · in {room}"
    title = entry.get("title") or "a conversation"
    excerpt = entry.get("excerpt") or ""
    if origin.startswith("exogenous/"):
        label = (
            EXOGENOUS_ORIGIN_PHRASE
            if platform.lower() == "chatgpt"
            else f"from an earlier {platform} conversation you imported"
        )
        return f"{when} — {label} — {title}{tail}: {excerpt}"
    return f"{when} — {title}{tail}: {excerpt}"


def _topics_without_shared_rooms(
    topics: list[dict[str, Any]],
    shared_rooms: set[str],
) -> list[dict[str, Any]]:
    """Drop shared-space excerpts, then topics that have nothing else left.

    The baked personal index includes shared rooms by design (the integrating
    exception). A craft surface reads that same index and must not remember
    those rooms. This is a render cut, not a rebuild of ``memory_roots_for``.
    """
    if not shared_rooms:
        return topics
    kept: list[dict[str, Any]] = []
    for topic in topics:
        own_entries = [
            entry
            for entry in (topic.get("entries") or [])
            if str(entry.get("room") or "") not in shared_rooms
        ]
        if not own_entries:
            continue
        filtered = dict(topic)
        filtered["entries"] = own_entries
        kept.append(filtered)
    return kept


def _topics_for_surface(
    practice_dir: str | os.PathLike,
    *,
    exclude_shared_rooms: bool = False,
) -> tuple[list[dict[str, Any]], str]:
    """Topics this surface may show, plus the own-room name for excerpts."""
    root = Path(practice_dir)
    topics = read_topics(root)
    if not topics:
        return [], ""
    own_room = ""
    shared_rooms: set[str] = set()
    try:
        data = yaml.safe_load((memory_dir(root) / TOPICS_YAML).read_text(encoding="utf-8")) or {}
        roots = data.get("roots") or []
        own_room = str(roots[0].get("room") or "") if roots else ""
        shared_rooms = {
            str(item.get("room") or "")
            for item in roots[1:]
            if item.get("room")
        }
    except Exception:
        pass
    if exclude_shared_rooms:
        topics = _topics_without_shared_rooms(topics, shared_rooms)
    return topics, own_room


def _excerpts_by_topic(topics: list[dict[str, Any]]) -> dict[str, list[str]]:
    return {
        str(t.get("id")): [str(e.get("excerpt") or "") for e in (t.get("entries") or [])]
        for t in topics
    }


def _render_topic_lines(
    chosen: list[dict[str, Any]],
    own_room: str,
    *,
    exclude_thread: str | None,
    excerpts_per_topic: int,
    char_budget: int,
    heading: str | None,
) -> str:
    lines = [heading] if heading else []
    budget = char_budget
    shown: set[tuple[str, str]] = set()
    for t in chosen:
        head = (
            f"- {t.get('label')} — {t.get('conversations')} conversations, "
            f"{t.get('since')} → {t.get('last_seen')}."
        )
        if t.get("summary"):
            head += f" {t.get('summary')}"
        parts = [head]
        count = 0
        for entry in t.get("entries") or []:
            if count >= excerpts_per_topic:
                break
            if exclude_thread and str(entry.get("thread")) == str(exclude_thread):
                continue
            key = (str(entry.get("thread")), str(entry.get("when")))
            if key in shown:
                continue
            shown.add(key)
            parts.append(f"    · {_excerpt_line(entry, own_room)}")
            count += 1
        text = "\n".join(parts)
        if len(text) > budget:
            break
        lines.append(text)
        budget -= len(text)
    if heading and len(lines) == 1:
        return ""
    if not heading and not lines:
        return ""
    return "\n".join(lines)


def render_topic_memory_block(
    practice_dir: str | os.PathLike,
    message_text: str = "",
    *,
    char_budget: int = TOPIC_BLOCK_CHAR_BUDGET,
    considered: list[dict[str, Any]] | None = None,
    exclude_thread: str | None = None,
    excerpts_per_topic: int | None = None,
    exclude_shared_rooms: bool = False,
) -> str:
    """What this space keeps returning to — the passive layer of room memory.

    Empty string when no memory has been built: the recency block already
    says what it cannot see, and two disclaimers are a recital.

    ``exclude_thread`` drops excerpts from the conversation being spoken in —
    it is already in the prompt as history. An excerpt is shown once even when
    its entry belongs to several topics: the first real render put the same
    note under all three headings.

    ``exclude_shared_rooms`` is the craft-surface cut: shared-space excerpts
    and topics that only live there do not reach the packet or the step card.
    Native private river leaves this false and still sees the merged index.
    """
    topics, own_room = _topics_for_surface(
        practice_dir, exclude_shared_rooms=exclude_shared_rooms
    )
    if not topics:
        return ""
    excerpts = _excerpts_by_topic(topics)
    chosen = select_topics(topics, message_text, excerpts_by_topic=excerpts)
    if considered is not None:
        chosen_ids = {t.get("id") for t in chosen}
        considered.extend(
            {
                "topic": t.get("id"),
                "label": t.get("label"),
                "heat": t.get("heat"),
                "last_seen": t.get("last_seen"),
                "selected": t.get("id") in chosen_ids,
            }
            for t in topics
        )
    per_topic = TOPIC_BLOCK_EXCERPTS if excerpts_per_topic is None else max(0, excerpts_per_topic)
    body = _render_topic_lines(
        chosen,
        own_room,
        exclude_thread=exclude_thread,
        excerpts_per_topic=per_topic,
        char_budget=char_budget,
        heading="What this space keeps returning to (from its own notes, all time):",
    )
    if not body:
        return ""
    conduct = (
        "Draw on these when they serve the reply; never recite them. When asked what "
        "you remember, answer from these notes and say so. Do not say you checked or "
        "searched anything unless you actually used a tool this turn — if you did not "
        "look, say what you hold and that you did not look further.\n"
    )
    if "you imported" in body:
        conduct += (
            "Notes marked as imported did not happen in this room. Say they came from "
            "an earlier chat the practitioner imported. Never 'we discussed' or "
            "'I remember when we' about them.\n"
        )
    return body + "\n" + conduct


def render_memory_glance(
    practice_dir: str | os.PathLike,
    conversation_text: str,
    *,
    exclude_thread: str | None = None,
    exclude_shared_rooms: bool = False,
    match_n: int = GLANCE_MATCH_N,
    excerpts_per_topic: int = GLANCE_EXCERPTS,
    char_budget: int = GLANCE_CHAR_BUDGET,
) -> str:
    """Related sediment for this conversation. Empty when nothing related.

    Does not narrate "I remember." Does not fill in the hottest topics.
    """
    topics, own_room = _topics_for_surface(
        practice_dir, exclude_shared_rooms=exclude_shared_rooms
    )
    if not topics:
        return ""
    excerpts = _excerpts_by_topic(topics)
    chosen = select_related_topics(
        topics, conversation_text, match_n=match_n, excerpts_by_topic=excerpts
    )
    if not chosen:
        return ""
    return _render_topic_lines(
        chosen,
        own_room,
        exclude_thread=exclude_thread,
        excerpts_per_topic=max(0, excerpts_per_topic),
        char_budget=char_budget,
        heading=None,
    )
