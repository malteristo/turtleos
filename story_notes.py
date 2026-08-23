"""Eddy note writer — the story layer's smallest unit (TURTLE_SPEC §6.5, §8.4).

At checkpoint, one reflection-class LLM call turns an eddy's conversation
into a short practitioner-facing note: what the conversation held, and —
only when something genuinely connects — how it relates to the threads and
intentions alive for the practitioner. No forced relations: when nothing
alive connects, the note says what the conversation held and stops.

One file per eddy under the practice root story surface
(``story/eddies/<thread-id>-<slug>.md``); each checkpoint appends a dated
entry with front matter (thread id, title, trigger, timestamp, related
topics). All writes go through the atomic primitive (issue 033); file
discovery and the read-append-write cycle are held under a per-eddy
``file_lock`` keyed on the channel id, so River and Turtle cannot
interleave entries or fork the note file on concurrent first checkpoints.

Degenerate model output (the chat_ollama no-response sentinel, too-short
replies, an empty held section) raises :class:`EddyNoteError` before any
write — the checkpoint caller decides how to degrade.

Relations read state surfaces only — the alive layer and the practitioner's
intention files under the same practice root — never other eddies'
transcripts. The composer layer enforces honesty a second time: a relation
the model names is kept only when it points at something actually alive.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from core.atomic_io import atomic_write_text, file_lock
from continuity_engine import read_alive
from helpers import local_now
from llm import chat_ollama
from mage import (
    get_mage_name,
    get_pd,
    member_address_map,
    set_practice_context_for_channel,
    space_members_for_practice_dir,
)
from state import REFLECTION_MODEL

EDDIES_SUBDIR = Path("story") / "eddies"

_HELD = "---HELD---"
_RELATION = "---RELATION---"
_TOPICS = "---RELATED-TOPICS---"
_PROPOSED = "---PROPOSED-THEMES---"
_END = "---END---"
_MAX_PROPOSED_THEMES = 3
_MAX_THEME_LABEL_CHARS = 60

# Every eddy has at least two speakers in it — the practitioner and Turtle —
# and the transcript already labels them (``_speaker_and_body``). What was
# missing is any instruction to keep them apart when the note is written.
#
# INT-040 branched on *member* cardinality and gave the multi-member case a
# full attribution rule. But a solo river has one member and two speakers, so
# the branch that most needs this — private, second person, warm, "your story"
# — was the only one without it. A note that absorbs Turtle's claims into the
# practitioner's account writes fabrication into their permanent history as
# their own words, and later turns then cite it back as fact (INT-041).
#
# This is a rule and not a guard on purpose: the transcript carries the
# speaker boundary intact, so the synthesis has what it needs and simply was
# not told to use it. Nothing here has to be checked after the fact.
_TURTLE_VOICE_RULE = (
    "Attribute what was said to whoever said it. What Turtle said is "
    "Turtle's — never retell Turtle's readings, suggestions or claims as the "
    "practitioner's own words or realizations. If Turtle claimed to have "
    "seen, read or reviewed something, record that Turtle claimed it, not "
    "that it happened."
)

_PERCEPTION_RULE = (
    "Hold one person's account of another as that person's perception, never "
    "as established fact."
)

# The conduct file governs what the witness *says*. Nothing governed what it
# *wrote down*, and the note composer never reads conduct.md — so the heavy-
# moments rule and the label ban stopped at the reply boundary and the record
# kept the things the reply was forbidden to produce.
#
# Observed in a live two-member space: notes taken from acute conversations
# reached verdicts about contested history, and proposed-themes carried
# clinical characterizations of one member by the other — each written into a
# durable artifact both members can open. The specifics stay in the operator's
# private practice record; what belongs here is the failure shape.
#
# Moved into the base prompt 2026-08-10 — both rules were witness-only, and the
# exemption that kept them out of the solo prompt does not survive the case it
# met. The reasoning on file was "a practitioner's private processing surface is
# composted by design", which is sound when someone processes *their own*
# material. It fails when the sustained subject of a solo root is a third party:
# the composting argument protects the practitioner's own bad hours, and there
# is nothing in it that licenses writing a diagnosis of someone who is not in
# the room and cannot answer. A note is a durable artifact in every root. What
# the exemption actually protects — venting, ugly first drafts, an unflattering
# day recorded plainly — none of it requires a clinical label about a person.
_HOT_MOMENT_RULE = (
    "If the conversation was acute — active conflict, someone in pain, a "
    "rupture still open — the note gets shorter and plainer, not deeper. "
    "Record what was said and what was left unresolved. Do not diagnose the "
    "situation, name patterns, or reach conclusions about who is doing what "
    "to whom. The restraint that governs what is said in a heavy moment "
    "governs what is written down about it."
)

_NO_LABELS_RULE = (
    "No clinical or characterological labels anywhere in the note — not in "
    "the summary, not in the themes. This covers gaslighting, toxic, "
    "triangulation, narcissistic, abusive, manipulative and their neighbours, "
    "in any language. Describe the checkable behaviour and let it stand. A "
    "label spoken and gone is recoverable; a label written into a durable "
    "record someone can open is a wound with an address. This protects people "
    "who are not in the conversation as much as people who are — a diagnosis "
    "of someone absent is the one they can never answer."
)

# One rule, one copy. It existed twice and disagreed with itself: the shared
# prompt carried "never a verdict on a member" and the solo prompt carried no
# restriction at all — so the guard was absent from exactly the notes written
# into a person's own private river, which is where a conversation about a
# family conflict actually happens.
#
# Widened 2026-08-08. "A member" was the wrong class. Measured live the same
# morning: the shared family root carried "the cost of prioritizing quiet over
# boundaries", "distinguishing avoidance from active appeasement",
# "recognizing conditioned responses in real time"; a private root carried
# "husband and mother-in-law boundaries, labeling vs actual behaviour". Every
# one passes "not a verdict on a member" — the verdicts are about a person who
# is not a member, or about the situation, or about nobody nameable at all.
# The class is *any* named person, and the shape to refuse is the verdict
# itself, not who it lands on.
_THEMES_RULE = (
    "Up to 3 short labels (2-6 words) for themes that emerged in THIS "
    "conversation and would be useful to remember later — durable threads, "
    "not a summary. Name what the conversation was ABOUT, never a conclusion "
    "about how anyone behaves. This holds for everyone, not only the people "
    "in this space: someone discussed but not present gets the same "
    "protection, and so does an unnamed \"they\". Good: \"the visit on "
    "monday\", \"who decides bedtime\", \"sharing the school run\". Not: a "
    "diagnosis, one person's characterization of another, or a lesson drawn "
    "about someone's patterns — \"recognizing conditioned responses\", "
    "\"avoidance versus appeasement\", \"the cost of keeping quiet\" are all "
    "verdicts wearing a topic's clothes. If the honest label would be a "
    "verdict, name the occasion instead. If nothing durable emerged: none\n"
)

# INT-049: the two prompt families need opposite rules about "you", and only
# one of them had ever been written down.
#
# The shared prompt bans second person outright — several people read the note,
# so "you" has no referent. The solo prompt was told to write in second person
# and never told who "you" was, so a practitioner talking *about* someone else
# had that person's experience narrated back as his own day. The source was
# sound: the eddy note named a third party's difficulty in clean third person
# ("B's stress … her family"), and the daily synthesis rewrote it into second
# person addressed to A ("your years within B's family") — folding one
# person's situation into the other's account of their own day.
#
# Neither existing rule covered it. _TURTLE_VOICE_RULE governs Turtle's turns;
# _PERCEPTION_RULE governs epistemic status (perception vs fact) and says
# nothing about pronouns. This is the third face: a third party, in a solo root.
_NO_SECOND_PERSON_RULE = (
    "Never address anyone as \"you\" — every member reads this note, so \"you\" "
    "has no stable meaning."
)

_THIRD_PARTY_RULE = (
    "\"You\" is the practitioner and no one else. Anyone they talked about "
    "stays in the third person, named. Never fold another person's experience, "
    "feelings or history into \"you\" — a conversation about someone else's "
    "situation is not the practitioner's own account of their day."
)


def _practitioner_binding(name: str) -> str:
    """Bind the pronoun to a person. The fifth face of the ownership law.

    ``_THIRD_PARTY_RULE`` settles who "you" is *not*, and has been in both solo
    prompts since INT-049. Nothing ever said who "you" **is**: ``_transcript``
    labels the practitioner's turns with a concrete name while the prompt frame
    called them "THE PRACTITIONER", leaving the model to bind the two itself.
    It did so inconsistently — same root, one hour apart, one note opening
    "You asked Turtle whether…" and the next "<name> shared two drafts… Turtle
    responded by…". The daily synthesis reading both then wrote the operator's
    own day as "you followed <name> as he stepped back": "you" resolved to
    Turtle, so the practitioner's record addressed an observer of him.

    Solo prompts only: the witness family bans second person outright, so a
    binding there would contradict ``_NO_SECOND_PERSON_RULE``.
    """
    return (
        f"THE PRACTITIONER IS {name}. Write \"you\" to mean {name}, and no one "
        f"else — their turns are labelled \"{name}:\" below. Turtle is the "
        "other speaker in the transcript and is never \"you\"; never write the "
        f"note as though addressing an observer of {name}."
    )

_SYSTEM_PROMPT = (
    "You write short notes that tell a practitioner's story back to them. "
    "You will see one conversation they had, and sometimes a list of threads "
    "and intentions currently in motion for them.\n\n"
    "Write in plain, warm, everyday language. Never use internal or technical "
    "vocabulary — no system terms, no layer names. Say \"this conversation\", "
    "\"your thread about X\", \"your intention to X\".\n\n"
    f"{_TURTLE_VOICE_RULE} {_PERCEPTION_RULE} {_THIRD_PARTY_RULE}\n\n"
    f"{_NO_LABELS_RULE}\n\n"
    f"{_HOT_MOMENT_RULE}\n\n"
    "Answer in exactly this structure:\n"
    f"{_HELD}\n"
    "2-5 sentences: what this conversation held — what was talked about, what "
    "emerged, what was decided or left open.\n"
    f"{_RELATION}\n"
    "ONE sentence naming how this conversation connects to something in motion "
    "for the practitioner — ONLY if a genuine connection exists. Never force a "
    "relation: if nothing in motion truly connects, write exactly: none\n"
    f"{_TOPICS}\n"
    "The items from the in-motion list that the relation points at, one per "
    "line prefixed with \"- \". If you wrote none above, write exactly: none\n"
    f"{_PROPOSED}\n"
    f"{_THEMES_RULE}"
    "Prefer reusing an in-motion label when it fits.\n"
    f"{_END}"
)


# Charter §3.3: above one member, dialogue-voice and witness-voice must diverge.
# Second person has no stable referent when several people read the same note,
# so the communal record narrates in third person and attributes every turn.
# Per-member second-person renderings come later, from this same record.
_WITNESS_SYSTEM_PROMPT = (
    "You write short notes recording what happened in a shared space that has "
    "several members. You will see one conversation, with each person's name "
    "on what they said.\n\n"
    "Write in plain, warm, everyday language, in the THIRD PERSON. "
    f"{_NO_SECOND_PERSON_RULE} Name people and attribute what they said to "
    "them. Never merge two people into one voice, and never attribute one "
    "person's words, feelings or decisions to another.\n\n"
    f"{_TURTLE_VOICE_RULE}\n\n"
    f"{_PERCEPTION_RULE} Write \"Ana experienced Ben as dismissive\", not "
    "\"Ben was dismissive\". This matters most when the content is a "
    "grievance about someone who will read the note.\n\n"
    f"{_HOT_MOMENT_RULE}\n\n"
    f"{_NO_LABELS_RULE}\n\n"
    "Never use internal or technical vocabulary — no system terms, no layer "
    "names.\n\n"
    "Answer in exactly this structure:\n"
    f"{_HELD}\n"
    "2-5 sentences: what this conversation held — what was discussed, who "
    "brought what, what emerged, what was decided or left open.\n"
    f"{_RELATION}\n"
    "ONE sentence naming how this conversation connects to something in motion "
    "in this shared space — ONLY if a genuine connection exists. Never force a "
    "relation: if nothing truly connects, write exactly: none\n"
    f"{_TOPICS}\n"
    "The items from the in-motion list that the relation points at, one per "
    "line prefixed with \"- \". If you wrote none above, write exactly: none\n"
    f"{_PROPOSED}\n"
    f"{_THEMES_RULE}"
    f"{_END}"
)


_NO_RESPONSE_SENTINEL = "(no response generated)"
_MIN_REPLY_CHARS = 20  # legacy session-note floor: len(reflection.strip()) > 20


class EddyNoteError(RuntimeError):
    """The reflection produced no usable note — nothing was written.

    Raised before any file write when the model returns the chat_ollama
    no-response sentinel, a degenerate too-short reply, or an empty
    what-the-eddy-held section. The caller (issue 035) decides how to degrade.
    """


@dataclass
class EddyNoteResult:
    note_path: Path
    entry_text: str
    preview_text: str
    proposed_themes: list[str] = field(default_factory=list)


@dataclass
class EddyEntry:
    """One checkpoint entry from an eddy note file, ready for daily synthesis."""

    thread: str
    title: str
    trigger: str
    timestamp: datetime
    related_topics: list[str]
    body: str
    source_path: Path
    participants: list[str] = field(default_factory=list)
    proposed_themes: list[str] = field(default_factory=list)


_ENTRY_FRONT_RE = re.compile(r"---\n(.*?)---\n\n", re.S)


async def write_eddy_note(
    channel_id: int,
    history: list[dict],
    *,
    trigger: str,
    since_index: int | None = None,
    parent_channel_id: int | None = None,
    title: str | None = None,
    occurred_at: datetime | None = None,
    alive_items: list[str] | None = None,
) -> EddyNoteResult:
    """Write (or append to) the eddy's story note and return it with a preview.

    ``trigger == "manual"`` weights the reflection toward
    ``history[since_index:]`` — the exchanges since the last checkpoint.

    Prefer ``parent_channel_id`` (Discord thread parent) so hosted-river eddies
    write under the practitioner root even when thread-state parent lookup is stale.

    The last three are for reading a conversation that already happened
    (``scripts/backfill_eddy_notes.py``), and each exists because the live
    defaults would lie about a past eddy:

    ``title``        the registry and the gateway only know threads this process
                     has seen; an unseen one resolves to the literal ``"eddy"``.
    ``occurred_at``  the entry stamp. Defaulting to *now* would date a March
                     conversation today — the age-invariant
                     (``design/consent-and-continuity.md``: anything carried
                     forward carries its own age) forbids exactly that.
    ``alive_items``  what is in motion *today*. Relating a past eddy to it would
                     manufacture a connection that did not exist; backfill
                     passes ``[]`` and the note simply carries no relation.
    """
    set_practice_context_for_channel(parent_channel_id or channel_id)
    practice_dir = Path(get_pd())
    mage_name = get_mage_name()

    # Branch on member cardinality (charter §3.3): one sovereign keeps the
    # intimate second person; a space with two or more takes witness voice with
    # authorship preserved.
    witness = len(space_members_for_practice_dir(practice_dir)) > 1
    names = member_address_map() if witness else None

    if alive_items is None:
        alive_items = _alive_items(practice_dir)
    prompt = _build_prompt(
        history, mage_name, alive_items, trigger, since_index, names=names
    )

    raw = await chat_ollama(
        _WITNESS_SYSTEM_PROMPT if witness else _SYSTEM_PROMPT,
        [{"role": "user", "content": prompt}],
        model=REFLECTION_MODEL,
        num_ctx=8192,
        think=False,
    )

    # Quality floor (M1): chat_ollama never returns empty — it substitutes a
    # literal sentinel — so gate on the sentinel and on degenerate length
    # before anything can reach the practitioner-facing note file.
    reply = (raw or "").strip()
    if reply == _NO_RESPONSE_SENTINEL or len(reply) <= _MIN_REPLY_CHARS:
        raise EddyNoteError(f"reflection reply failed the quality floor: {reply[:80]!r}")

    held, relation, topics, proposed = _parse_response(reply)
    if not held.strip():
        raise EddyNoteError("reflection reply had an empty what-the-eddy-held section")
    relation, topics = _validate_relation(relation, topics, alive_items)
    proposed = _normalize_proposed_themes(proposed, alive_items)
    # Behind the cheap filter: normalisation usually leaves nothing, and the
    # gate is skipped entirely when it does. Filtered here rather than in
    # either consumer, because the labels reach two durable surfaces — the note
    # file and the alive layer — and a guard on one of them is the shape of
    # defect this is repairing.
    if proposed:
        from theme_gate import keep_topics

        proposed, dropped = await keep_topics(proposed)
        if dropped:
            # Counted, not printed with its contents: the dropped label is the
            # thing that should not be written down.
            print(f"Theme gate held back {len(dropped)} label(s) for {channel_id}")
    _promote_proposed_themes(practice_dir, proposed, trigger)

    title = title or _resolve_thread_title(channel_id)
    entry_text = _compose_entry(
        channel_id,
        title,
        trigger,
        held,
        relation,
        topics,
        proposed,
        _participants(history, mage_name, names) if witness else None,
        occurred_at=occurred_at,
    )

    # Per-eddy lock (keyed on channel id) held across discovery + append so
    # two concurrent first checkpoints cannot fork the eddy's note file.
    eddies_dir = practice_dir / EDDIES_SUBDIR
    with file_lock(eddies_dir / str(channel_id)):
        note_path = _note_path(practice_dir, channel_id, title)
        _append_entry(note_path, entry_text)

    return EddyNoteResult(
        note_path=note_path,
        entry_text=entry_text,
        preview_text=_compose_preview(held, relation),
        proposed_themes=proposed,
    )


# ─── Alive context (read-only, same practice root) ───────────────────


def _alive_items(practice_dir: Path) -> list[str]:
    """Plain-language labels of what's in motion: alive threads, alive-layer
    intention snapshot, and intention files under the practice root."""
    items: list[str] = []
    alive = read_alive(practice_dir) or {}
    for t in alive.get("active_threads") or []:
        label = (t.get("label") or t.get("id") or "").strip() if isinstance(t, dict) else ""
        if label:
            items.append(label)
    for i in alive.get("intention_snapshot") or []:
        name = (i.get("name") or "").strip() if isinstance(i, dict) else ""
        if name:
            items.append(name)
    intentions_dir = practice_dir / "intentions"
    if intentions_dir.is_dir():
        for f in sorted(intentions_dir.glob("*.md")):
            items.append(f.stem.replace("-", " ").replace("_", " ").strip())
    seen: set[str] = set()
    unique = []
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


# ─── Prompt ──────────────────────────────────────────────────────────


_SPEAKER_PREFIX_RE = re.compile(r"^\[([^\]\n]{1,64})\]:[ \t]*")


def _speaker_and_body(
    entry: dict, mage_name: str, names: dict[str, str] | None
) -> tuple[str, str]:
    """Per-turn speaker, preserving the authorship the shell already captured.

    Dialogue turns are stored as ``[display name]: text``. The old renderer
    relabelled every member turn with a single ``mage_name`` — which for a space
    resolves to the *space* key, producing ``Family: [riverhand]: …``, a
    contradictory double label whose outer frame wins. That is the mechanical
    cause of a shared space reading as one undifferentiated "you" (INT-040).

    ``names`` is supplied only for shared spaces, where distinct speakers must
    survive. For a single-member root there is one sovereign to address, so the
    turn is relabelled with their address and the raw handle never reaches the
    prompt.
    """
    content = entry.get("content") or ""
    if entry.get("role") != "user":
        return "Turtle", content

    match = _SPEAKER_PREFIX_RE.match(content)
    if not match:
        return mage_name, content

    body = content[match.end() :]
    if names is None:
        return mage_name, body
    handle = match.group(1).strip()
    return names.get(handle.lower(), handle), body


def _participants(
    history: list[dict], mage_name: str, names: dict[str, str] | None
) -> list[str]:
    """Distinct human speakers in this eddy, in order of first appearance."""
    seen: list[str] = []
    for entry in history:
        if entry.get("role") != "user":
            continue
        speaker, _ = _speaker_and_body(entry, mage_name, names)
        if speaker and speaker not in seen:
            seen.append(speaker)
    return seen


def _transcript(
    history: list[dict], mage_name: str, names: dict[str, str] | None = None
) -> str:
    return "\n".join(
        "{}: {}".format(*_speaker_and_body(m, mage_name, names)) for m in history
    )


def _build_prompt(
    history: list[dict],
    mage_name: str,
    alive_items: list[str],
    trigger: str,
    since_index: int | None,
    *,
    names: dict[str, str] | None = None,
) -> str:
    parts: list[str] = []
    witness = names is not None
    subject = "THIS SHARED SPACE" if witness else "THE PRACTITIONER"

    if not witness and mage_name:
        parts.append(_practitioner_binding(mage_name))

    if alive_items:
        listing = "\n".join(f"- {item}" for item in alive_items)
        parts.append(
            f"WHAT'S ALIVE FOR {subject} (threads and intentions in "
            "motion — relate ONLY to these, and only when the connection is "
            f"genuine):\n{listing}"
        )
    else:
        parts.append(
            f"Nothing is currently listed as in motion for {subject.lower()} — "
            "describe what the conversation held and stop; do not invent a "
            "connection."
        )

    weighted = (
        trigger == "manual"
        and since_index is not None
        and 0 < since_index < len(history)
    )
    if weighted:
        parts.append(
            "EARLIER IN THIS CONVERSATION (background only — do not center "
            f"the note on this):\n{_transcript(history[:since_index], mage_name, names)}"
        )
        parts.append(
            "SINCE THE LAST CHECKPOINT (the practitioner deliberately asked "
            "to capture now — write the note mainly about these exchanges):\n"
            f"{_transcript(history[since_index:], mage_name, names)}"
        )
    else:
        parts.append(f"THE CONVERSATION:\n{_transcript(history, mage_name, names)}")

    return "\n\n".join(parts)


# ─── Response parsing + honesty gate ─────────────────────────────────


def _section(raw: str, start: str, end: str) -> str | None:
    if start not in raw:
        return None
    body = raw.split(start, 1)[1]
    if end in body:
        body = body.split(end, 1)[0]
    return body.strip()


def _parse_bullet_labels(body: str) -> list[str]:
    labels: list[str] = []
    for line in body.splitlines():
        line = line.strip().lstrip("-").strip()
        if line and line.lower() not in ("none", "none."):
            labels.append(line)
    return labels


def _parse_response(raw: str) -> tuple[str, str | None, list[str], list[str]]:
    held = _section(raw, _HELD, _RELATION)
    if held is None:
        # Sentinels missing — degrade to treating the whole reply as the note.
        return raw.strip(), None, [], []

    relation = _section(raw, _RELATION, _TOPICS) or ""
    if relation.strip().lower() in ("", "none", "none."):
        relation = None

    if _PROPOSED in raw:
        topics_body = _section(raw, _TOPICS, _PROPOSED) or ""
        proposed_body = _section(raw, _PROPOSED, _END) or ""
    else:
        # Pre-Slice-2 replies omit proposed themes.
        topics_body = _section(raw, _TOPICS, _END) or ""
        proposed_body = ""

    return held, relation, _parse_bullet_labels(topics_body), _parse_bullet_labels(
        proposed_body
    )


def _normalize_proposed_themes(
    proposed: list[str], alive_items: list[str]
) -> list[str]:
    """Cap, trim, and drop themes already listed as in motion.

    Unlike related-topics, proposed themes are allowed when the alive layer is
    empty — that is the first-use path for Continuity Engine Slice 2.
    """
    kept: list[str] = []
    seen: set[str] = set()
    for raw in proposed:
        label = " ".join((raw or "").split())
        if not label or len(label) < 2:
            continue
        if len(label) > _MAX_THEME_LABEL_CHARS:
            label = label[:_MAX_THEME_LABEL_CHARS].rstrip()
        key = label.lower()
        if key in seen:
            continue
        if any(_topic_matches_alive(label, alive) for alive in alive_items):
            continue
        seen.add(key)
        kept.append(label)
        if len(kept) >= _MAX_PROPOSED_THEMES:
            break
    return kept


def _normalize_words(text: str) -> set[str]:
    """Lowercase, hyphens/underscores → spaces, strip punctuation, word set."""
    text = text.lower().replace("-", " ").replace("_", " ")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return set(text.split())


def _topic_matches_alive(topic: str, alive_item: str) -> bool:
    """Exact match or whole-word containment either way after normalization:
    'the health thread' matches alive 'health'; 'healthcare' does not."""
    topic_words = _normalize_words(topic)
    alive_words = _normalize_words(alive_item)
    if not topic_words or not alive_words:
        return False
    return alive_words <= topic_words or topic_words <= alive_words


def _promote_proposed_themes(
    practice_dir: Path, themes: list[str], trigger: str
) -> list[str]:
    """Put what the conversation raised into the alive layer, unasked.

    The layer's writer was never missing — it was reachable only through the
    Keep-these surface, which is offered after ``!checkpoint`` and ``!release``
    and nowhere else. Both are typed. Across every root, 106 of 112 real
    checkpoints fired on idle, and since 2026-07-18 the count is 32 of 32, so
    the surface had not been shown once in three weeks while three consumers
    went on reading a 17 July snapshot as the present.

    Waiting for a member to press a button is the defect, not the safeguard.
    The twine has to hold on its own; a deliberate act should *enrich* a record
    that already works, never be the thing that starts it. So promotion is
    unconditional on trigger, and marked ``inferred`` — noticed, not chosen.
    Pressing Keep later upgrades the same thread in place and buys it the long
    TTL, which is what makes the button worth pressing rather than required.

    Backfill is excluded: replaying months of archived conversation would
    resurrect finished threads as though they were current, which is the exact
    failure being repaired.
    """
    if trigger == "backfill" or not themes:
        return []
    try:
        from continuity_engine import add_active_thread

        return [
            str(add_active_thread(practice_dir, label, source="inferred").get("label"))
            for label in themes
        ]
    except Exception as exc:  # never fail a note over its side effect
        print(f"Theme promotion failed: {type(exc).__name__}: {exc}")
        return []


def _validate_relation(
    relation: str | None, topics: list[str], alive_items: list[str]
) -> tuple[str | None, list[str]]:
    """Composer-layer honesty gate: a relation survives only when it points at
    something actually alive. Empty alive layer → no relation, ever.

    Surviving topics are emitted under their canonical alive-item names so
    downstream grouping (slice 2) matches the alive set. When some topics were
    dropped, the relation sentence must reference a survivor to be kept —
    otherwise the whole relation goes and the note stays descriptive."""
    if not alive_items or relation is None:
        return None, []

    kept: list[tuple[str, str]] = []  # (model's raw topic, canonical alive name)
    for topic in topics:
        for alive in alive_items:
            if _topic_matches_alive(topic, alive):
                if all(alive != canonical for _, canonical in kept):
                    kept.append((topic, alive))
                break
    if not kept:
        return None, []

    if len(kept) < len(topics):
        sentence_words = _normalize_words(relation)
        referenced = any(
            _normalize_words(canonical) <= sentence_words
            or _normalize_words(raw) <= sentence_words
            for raw, canonical in kept
        )
        if not referenced:
            return None, []

    return relation, [canonical for _, canonical in kept]


# ─── Note composition + storage ──────────────────────────────────────


def _slug(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (title or "").strip().lower()).strip("-")
    return slug or "eddy"


def _resolve_thread_title(channel_id: int) -> str:
    """Thread title from the registry, falling back to the live channel name."""
    try:
        from thread_registry import load_registry

        info = load_registry().get("threads", {}).get(str(channel_id))
        if info and info.get("name"):
            return str(info["name"])
    except Exception:
        pass
    try:
        from state import client

        channel = client.get_channel(channel_id)
        name = getattr(channel, "name", None)
        if name:
            return str(name)
    except Exception:
        pass
    return "eddy"


def _note_path(practice_dir: Path, channel_id: int, title: str) -> Path:
    """One file per eddy: reuse the existing note when present (survives
    retitles), otherwise name it from the current title."""
    eddies_dir = practice_dir / EDDIES_SUBDIR
    existing = sorted(eddies_dir.glob(f"{channel_id}-*.md"))
    if existing:
        return existing[0]
    return eddies_dir / f"{channel_id}-{_slug(title)}.md"


def _compose_entry(
    channel_id: int,
    title: str,
    trigger: str,
    held: str,
    relation: str | None,
    topics: list[str],
    proposed: list[str] | None = None,
    participants: list[str] | None = None,
    *,
    occurred_at: datetime | None = None,
) -> str:
    fields = {
        "thread": str(channel_id),
        "title": title,
        "trigger": trigger,
        "timestamp": (occurred_at or local_now()).isoformat(timespec="seconds"),
        "related-topics": topics,
        "proposed-themes": list(proposed or []),
    }
    # Who actually spoke, so the daily layer can centre a member's own thread
    # without re-deriving authorship from prose.
    if participants:
        fields["participants"] = list(participants)
    dumped = yaml.safe_dump(
        fields, sort_keys=False, allow_unicode=True, default_flow_style=None
    ).strip()
    front_matter = f"---\n{dumped}\n---"
    body = held.strip()
    if relation:
        body += f"\n\n{relation.strip()}"
    return f"{front_matter}\n\n{body}\n"


def _append_entry(note_path: Path, entry_text: str) -> None:
    """Read-append-write; the write itself is atomic. The caller holds the
    per-eddy ``file_lock`` across discovery and this append."""
    existing = ""
    if note_path.exists():
        existing = note_path.read_text(encoding="utf-8")
        if existing and not existing.endswith("\n"):
            existing += "\n"
        existing += "\n"
    atomic_write_text(note_path, existing + entry_text)


_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def _first_sentences(text: str, count: int = 2) -> str:
    flat = " ".join(text.split())
    sentences = _SENTENCE_END.split(flat)
    return " ".join(sentences[:count]).strip()


def _compose_preview(held: str, relation: str | None) -> str:
    """First sentences for the checkpoint reply surface (issue 036) — the
    relational sentence leads when present."""
    if relation:
        return f"{relation.strip()} {_first_sentences(held, 2)}".strip()
    return _first_sentences(held, 3)


# ─── Eddy file parsing + daily collector (issue 038) ───────────────


def read_alive_snapshot(practice_dir: Path) -> dict:
    """Read-only alive layer for story synthesis — shared with the eddy writer."""
    return read_alive(practice_dir) or {}


def parse_eddy_file_entries(content: str) -> list[tuple[dict, str]]:
    """Split an eddy note file into (front_matter, body) per checkpoint entry."""
    matches = list(_ENTRY_FRONT_RE.finditer(content))
    entries: list[tuple[dict, str]] = []
    for i, match in enumerate(matches):
        try:
            front = yaml.safe_load(match.group(1))
        except yaml.YAMLError:
            continue
        if not isinstance(front, dict):
            continue
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[match.end() : end].strip()
        entries.append((front, body))
    return entries


def _entry_from_front(
    front: dict, body: str, source_path: Path, tz: ZoneInfo
) -> EddyEntry | None:
    timestamp_raw = front.get("timestamp")
    if not timestamp_raw:
        return None
    try:
        parsed_ts = datetime.fromisoformat(str(timestamp_raw).strip())
        if parsed_ts.tzinfo is None:
            parsed_ts = parsed_ts.replace(tzinfo=tz)
        else:
            parsed_ts = parsed_ts.astimezone(tz)
    except (TypeError, ValueError):
        return None

    topics = front.get("related-topics") or []
    if not isinstance(topics, list):
        topics = []
    related_topics = [str(t).strip() for t in topics if str(t).strip()]

    participants = front.get("participants") or []
    if not isinstance(participants, list):
        participants = []

    # Written on every checkpoint since the theme proposer shipped and, until
    # room memory read them, consumed by nothing. `related-topics` is the
    # field the schema advertises for this and it is empty in every entry on
    # the node; `proposed-themes` is the one that is actually populated.
    themes = front.get("proposed-themes") or []
    if not isinstance(themes, list):
        themes = []

    return EddyEntry(
        participants=[str(p).strip() for p in participants if str(p).strip()],
        proposed_themes=[str(t).strip() for t in themes if str(t).strip()],
        thread=str(front.get("thread") or "").strip(),
        title=str(front.get("title") or "").strip(),
        trigger=str(front.get("trigger") or "").strip(),
        timestamp=parsed_ts,
        related_topics=related_topics,
        body=body.strip(),
        source_path=source_path,
    )


def collect_recent_eddy_entries(
    *,
    practice_dir: Path | None = None,
    since_days: int = 7,
    exclude_thread: str | None = None,
    limit: int = 5,
    per_thread_limit: int = 1,
) -> list[EddyEntry]:
    """Recent eddy entries across the whole root — the room's own memory.

    The counterpart to :func:`collect_eddy_entries_for_date`: that one gathers
    a day for synthesis, this one gathers what a conversation should be able to
    remember. Most recent first, capped.

    ``per_thread_limit`` keeps the newest entries *per eddy* rather than the
    newest overall. A long-running conversation checkpoints repeatedly, so a
    flat recency window fills with one thread's own history and the room
    appears to remember only its loudest week. What is wanted here is the last
    N *conversations*, not the last N checkpoints.

    ``exclude_thread`` drops the current eddy's own entries — that conversation
    is already in the prompt as history, and what is missing is *cross-eddy*
    memory.

    Never reads outside ``practice_dir``. A room's memory is its own notes
    (TURTLE_SPEC §15.5).
    """
    from state import PRACTICE_TIMEZONE

    root = practice_dir if practice_dir is not None else Path(get_pd())
    eddies_dir = root / EDDIES_SUBDIR
    if not eddies_dir.is_dir():
        return []

    tz = ZoneInfo(PRACTICE_TIMEZONE)
    cutoff = datetime.now(tz) - timedelta(days=since_days)
    collected: list[EddyEntry] = []
    for note_path in sorted(eddies_dir.glob("*.md")):
        try:
            content = note_path.read_text(encoding="utf-8")
        except OSError:
            continue
        for front, body in parse_eddy_file_entries(content):
            entry = _entry_from_front(front, body, note_path, tz)
            if entry is None or entry.timestamp < cutoff:
                continue
            if exclude_thread and entry.thread == str(exclude_thread):
                continue
            collected.append(entry)

    collected.sort(key=lambda e: e.timestamp, reverse=True)

    if per_thread_limit > 0:
        seen: dict[str, int] = {}
        kept: list[EddyEntry] = []
        for entry in collected:
            count = seen.get(entry.thread, 0)
            if count >= per_thread_limit:
                continue
            seen[entry.thread] = count + 1
            kept.append(entry)
        collected = kept

    return collected[:limit]


def collect_eddy_entries_for_date(
    target_date: date,
    *,
    practice_dir: Path | None = None,
) -> list[EddyEntry]:
    """Collect eddy-note entries whose local calendar date matches ``target_date``.

    Scans ``story/eddies/*.md`` under the practice root. Entries with missing
    or malformed front matter are **skipped** (not raised) so one bad checkpoint
    does not block daily synthesis. Returns an empty list when the eddies
    directory is missing or no entries match. Sorted chronologically within the
    day.
    """
    from state import PRACTICE_TIMEZONE

    root = practice_dir if practice_dir is not None else Path(get_pd())
    eddies_dir = root / EDDIES_SUBDIR
    if not eddies_dir.is_dir():
        return []

    tz = ZoneInfo(PRACTICE_TIMEZONE)
    collected: list[EddyEntry] = []
    for note_path in sorted(eddies_dir.glob("*.md")):
        content = note_path.read_text(encoding="utf-8")
        for front, body in parse_eddy_file_entries(content):
            entry = _entry_from_front(front, body, note_path, tz)
            if entry is None:
                continue
            if entry.timestamp.astimezone(tz).date() != target_date:
                continue
            collected.append(entry)

    collected.sort(key=lambda e: e.timestamp)
    return collected
