"""The judge that decides which loosely related notes a backlog pitch may show.

`backlog_feed_context.shortlist` finds candidates by shared vocabulary, and shared
vocabulary is not shared subject. This reads the row and the shortlist and keeps
the candidates that are about the same thing. It is a gate in the sense the rest
of the house uses the word: one greedy JSON call through the inference gate, which
fails closed. A failed call keeps **nothing**; it never falls back to the
shortlist, because the shortlist is exactly the noise the judge is here to remove.

The judge chooses keys. It writes no words that reach him: the text on the pitch is
the source's own, taken from the file, and a key that is not on the shortlist is
dropped by `decide`. That is why a model can be allowed to do this at all.
"""

from __future__ import annotations

import json
import re

from backlog_feed_context import Candidate, Context, Corpus, Shortlist, decide, shortlist
from backlog_feed import FeedItem

JUDGE_NUM_CTX = 8192
JUDGE_TIMEOUT_S = 90.0
ROW_CHARS = 900

PROMPT = """You are helping decide what to show next to a backlog item, so its owner can judge it.

BACKLOG ITEM
%s

CANDIDATES (notes, sparks and lines of his own writing, each with a key)
%s

Keep a candidate only if it is about the same subject as the item: the same problem,
the same mechanism, or the same intention. Sharing a word or a theme is not enough.
A candidate that merely mentions turtleOS, Turtle, River, craft, eddies or the
practice in general does not count. If you are unsure, leave it out. Most items have
few or none, and an empty answer is correct when nothing is about the same subject.
Keep at most 4.

Answer with JSON only: {"keep": ["c2", "c5"]}  — or {"keep": []}."""


def _candidate_block(candidates: tuple[Candidate, ...]) -> str:
    return "\n".join(f"[{c.key}] {' '.join(c.text.split())}" for c in candidates)


def build_prompt(item: FeedItem, short: Shortlist) -> str:
    row = " ".join(f"{item.title}. {item.body}".split())[:ROW_CHARS]
    return PROMPT % (row, _candidate_block(short.candidates))


def parse_keep(raw: str, valid: set[str]) -> list[str]:
    """Keys the judge kept, in the order it gave them, only those that exist."""
    match = re.search(r"\{.*\}", raw or "", re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    keep = data.get("keep") if isinstance(data, dict) else None
    if not isinstance(keep, list):
        return []
    seen: list[str] = []
    for key in keep:
        if isinstance(key, str) and key in valid and key not in seen:
            seen.append(key)
    return seen


async def ask(prompt: str, *, model: str | None = None) -> str:
    """One greedy JSON call through the gate. Raises on failure; `keep_for` catches."""
    from core.models import REFLECTION_MODEL
    from llm import chat_ollama_json

    return await chat_ollama_json(
        prompt, model=model or REFLECTION_MODEL, num_ctx=JUDGE_NUM_CTX, timeout_s=JUDGE_TIMEOUT_S
    )


async def keep_for(item: FeedItem, short: Shortlist, *, ask_fn=ask) -> list[str]:
    """Keys to keep. Never raises: a judge that cannot answer keeps nothing."""
    if not short.candidates:
        return []
    try:
        raw = await ask_fn(build_prompt(item, short))
    except Exception as exc:  # noqa: BLE001 — fail closed, see module docstring
        print(f"Backlog feed judge declined: {type(exc).__name__}: {exc}")
        return []
    return parse_keep(raw, {c.key for c in short.candidates})


async def context_for_item(corpus: Corpus, item: FeedItem, *, ask_fn=ask) -> Context:
    short = shortlist(corpus, item.id, item.title, item.body)
    return decide(short, await keep_for(item, short, ask_fn=ask_fn))
