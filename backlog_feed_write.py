"""A backlog row, written as the ideal state it asks for — so he can judge it.

A row is a note its author wrote to a later self: ids, dates, "harvested", "pickup",
file names. He does not read code and asked for each pitch as a short press-release
and ideal-state description instead: what exists when this has succeeded, why it was
filed, what it is not, and how he would know it works (the house PR/FAQ headings,
`pr_faq.py`, cut to what fits in a message he reads on a phone).

**This is the one place a model writes words he reads.** Everything else on a pitch
is quoted. So the boundary is kept narrow:

- The model sees the row, his own words when he filed it, and the sources the judge
  kept, and nothing else. The prompt says to use only those.
- Where they say nothing, the model is told to say so (*"The row doesn't say."*) and
  not to fill the gap. A pitch that says what it does not know is worth more to him
  than a fluent one that invents a limit.
- The text is a *rewrite*, labelled as one: the row as filed and every quotation sit
  in the embed beside it, so he can check the rewrite against what it came from.
- Code words are refused (file names, snake_case, backticks). They are the thing he
  said was hard to read, and a model drifts back to them. A rewrite that fails the
  check is asked for once more, and then the pitch falls back to the row's own text.
  It never fails to post.

No Discord import. The model call is injected so the tests never need a model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from backlog_feed import FeedItem
from backlog_feed_context import Context

WRITE_NUM_CTX = 8192
ROW_CHARS = 1600
LIMITS = {"headline": 100, "ideal": 560, "problem": 320, "not_this": 240, "check": 280}

LABELS = (
    ("headline", "HEADLINE"),
    ("ideal", "WHEN THIS EXISTS"),
    ("problem", "WHY IT WAS FILED"),
    ("not_this", "NOT THIS"),
    ("check", "HOW YOU WOULD KNOW"),
)

PROMPT = """You are rewriting one backlog item as a short press release and ideal-state description, for Kermit. He is a user-experience researcher. He does not read code and cannot judge an item from developer notes. He will decide Build or Drop from what you write.

Write what he would SEE and DO, in plain language: what exists when this has succeeded, and what he no longer has to do. Present tense. No file names, module names, function names, commit ids, dates, or words such as harvest, pickup, dest, chapter, slice, forge, mechanism. Write "Turtle", "River", "the eddy", "the channel" as he would say them. Speak to the reader as "you". If the material is about someone else (a guest, a tester), say "a guest" or "they"; never write his name.

Use ONLY the material below. Never invent the trouble, the person, the steps or the outcome. Where the material gives no basis for a part, write exactly: The row doesn't say.
The material is sometimes very thin, a title and a few words. Then WHEN THIS EXISTS is one plain sentence that restates what the title asks for, and the parts the material cannot support say "The row doesn't say." A short honest pitch is correct; a fluent invented one is wrong.

BACKLOG ITEM (as filed)
%(row)s
%(said)s%(origin)s%(related)s
Answer in exactly these five parts, each on its own, label first:

HEADLINE: one line, at most 12 words, what he gets, as a news headline.
WHEN THIS EXISTS: two to four short sentences, what he sees and does.
WHY IT WAS FILED: one or two sentences, the trouble he met.
NOT THIS: one sentence, what it deliberately is not.
HOW YOU WOULD KNOW: one sentence, something he could observe that shows it works."""

# Code words (he said they are what makes a pitch hard to read) and his own name (he is
# the reader, "you"; a model writing about the row's guest drifts into calling him by it).
_CODE_WORD = re.compile(r"\b[\w-]+\.(?:py|md|yaml|yml|json|sh|txt)\b|\b[a-z]+_[a-z0-9_]+\b|`|\bKermit\b")
_ABSENT = "The row doesn't say."
_NO_BASIS = re.compile(
    r"^(?:the )?(?:row|material|item)\s+(?:doesn['’]t|does not|cannot|can['’]t)\s+(?:say|support|give|tell)\b[^.]{0,60}\.?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Written:
    headline: str
    ideal: str
    problem: str
    not_this: str
    check: str


def _line(text: str) -> str:
    return " ".join((text or "").split())


def build_prompt(item: FeedItem, context: Context) -> str:
    row = _line(f"{item.title}. {item.body}")[:ROW_CHARS]
    said = f"\nHIS OWN WORDS WHEN HE FILED IT\n{context.said.quote}\n" if context.said else ""
    origin = ""
    if context.origin and context.origin.quote:
        origin = f"\nTHE CONVERSATION IT CAME FROM ({context.origin.label})\n{context.origin.quote}\n"
    related = ""
    if context.related:
        lines = [f"- {s.label}: {s.quote}" for s in context.related]
        related = "\nNOTES ABOUT THE SAME SUBJECT\n" + "\n".join(lines) + "\n"
    return PROMPT % {"row": row, "said": said, "origin": origin, "related": related}


def parse_written(raw: str) -> Written | None:
    """The five parts, or None. Strict: a missing part, an over-long part or a code
    word means the rewrite is not used."""
    text = (raw or "").replace("**", "")
    positions = []
    for key, label in LABELS:
        match = re.search(rf"^\s*{re.escape(label)}\s*:\s*", text, re.MULTILINE | re.IGNORECASE)
        if not match:
            return None
        positions.append((match.start(), match.end(), key))
    positions.sort()
    parts: dict[str, str] = {}
    for index, (_start, body_start, key) in enumerate(positions):
        end = positions[index + 1][0] if index + 1 < len(positions) else len(text)
        parts[key] = _line(text[body_start:end])
    for key in parts:
        if _NO_BASIS.match(parts[key]):
            parts[key] = _ABSENT
        elif _ABSENT in parts[key]:
            # An answer with the model's own admission tacked on ("… The row doesn't
            # say.") is the answer; the admission is dropped, not the answer. A part
            # that is only the admission stays one (above).
            parts[key] = _line(parts[key].replace(_ABSENT, "")) or _ABSENT
    for key, limit in LIMITS.items():
        value = parts.get(key, "")
        if not value or len(value) > limit or _CODE_WORD.search(value):
            return None
        parts[key] = value
    return Written(**parts)


async def ask(prompt: str, *, model: str | None = None) -> str:
    from core.models import REFLECTION_MODEL
    from llm import chat_ollama

    return await chat_ollama(
        "You write plainly and never invent facts.",
        [{"role": "user", "content": prompt}],
        model=model or REFLECTION_MODEL,
        num_ctx=WRITE_NUM_CTX,
        think=False,
    )


async def write_for_item(item: FeedItem, context: Context, *, ask_fn=ask) -> Written | None:
    """The rewrite, or None. Never raises: a pitch without one posts the row's own text."""
    prompt = build_prompt(item, context)
    for attempt in range(2):
        try:
            raw = await ask_fn(
                prompt if attempt == 0 else prompt + "\n\nYour last answer used code words or broke the format. Plain words only, exactly the five labelled parts."
            )
        except Exception as exc:  # noqa: BLE001 — fail closed: the pitch falls back
            print(f"Backlog feed writer declined: {type(exc).__name__}: {exc}")
            return None
        written = parse_written(raw)
        if written is not None:
            return written
    return None


def absent(text: str) -> bool:
    return _line(text) == _ABSENT
