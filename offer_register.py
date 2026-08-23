"""Is this a conversation where an operational offer is welcome?

The Magic practice has carried this rule for Spirit since long before turtleOS:

    Surface briefly in task / planning / analysis when need↔magic is clear.
    Stay observational in emotional, relational, grief/SOS, fellowship,
    casual, or mid-ritual contexts.

Turtle's seneschal never had it. Between June and August 2026 the working-plan
offer fired seventeen times — into a conversation about dissociation, one about
ADHD daily struggle, one about marriage strain after a second child, a feverish
child, chore-war exhaustion — and was taken once. Not a low take rate: sixteen
offers that misread the moment.

The check is a model call rather than a word list on purpose. "Woher weiß ich
ob ich dissoziiere?" contains no distress keyword, and any list that caught it
would be a list of the things this family happened to say last month.

It is affordable because it runs *behind* the cheap structural filter — only
when a reply already looks like a plan, which was 17 times in eight weeks.
"""

from __future__ import annotations

import json
from typing import Any

CARE = "care"
OPERATIONAL = "operational"

_PROMPT = """You judge the register of a conversation in a family's private chat.

Answer "operational" ONLY when the person is working on a task, project, plan,
logistics, or a factual question, and would welcome being handed a structured
plan to keep.

Answer "care" for anything else — feelings, health, a relationship, conflict,
grief, distress, parenting under strain, self-understanding, philosophical or
intimate reflection, or ordinary companionable chat.

Look past the surface to what is actually being carried. A practical question
can sit on top of a hard thing: dividing housework can be a conflict about
fairness, and what to feed someone can be worry about a person who is unwell.
When a task is being discussed *because* someone is struggling or unwell or at
odds with another person, that is care, not logistics.

When you are unsure, answer "care".

Reply with JSON only: {"register": "care"} or {"register": "operational"}

Conversation title: %(title)s
What the person said:
%(text)s
"""

_MAX_TEXT = 1200


def build_prompt(text: str, *, title: str | None = None) -> str:
    return _PROMPT % {
        "title": (title or "(untitled)")[:120],
        "text": (text or "").strip()[:_MAX_TEXT],
    }


def parse_register(raw: str) -> str:
    """Read the model's answer. Anything unrecognised is care."""
    try:
        data = json.loads((raw or "").strip())
    except (json.JSONDecodeError, TypeError):
        return CARE
    if not isinstance(data, dict):
        return CARE
    value = str(data.get("register") or "").strip().lower()
    return OPERATIONAL if value == OPERATIONAL else CARE


async def classify_register(
    text: str,
    *,
    title: str | None = None,
    model: str | None = None,
    timeout_s: float = 30.0,
) -> str:
    """`care` or `operational`. Every failure path answers `care`.

    Fail-closed is the whole design: a missed offer costs nothing and is
    invisible, a misplaced one lands in someone's hard morning.

    Goes through ``chat_ollama_json`` since 2026-08-08. It used to post with
    its own client and an 8s deadline, which on a one-slot host meant it
    competed with the dialogue turn holding the slot rather than queueing
    behind it — and then failed closed. So on a busy evening, when several
    conversations are live and the register question matters most, the honest
    description of this gate was "suppresses every offer". The deadline now
    starts after the slot is acquired; waiting in line is not a failure.
    """
    if not (text or "").strip():
        return CARE
    try:
        from llm import chat_ollama_json
        from core.models import RIVER_MODEL

        raw = await chat_ollama_json(
            build_prompt(text, title=title),
            model=model or RIVER_MODEL,
            num_ctx=2048,
            timeout_s=timeout_s,
        )
        return parse_register(raw)
    except Exception as exc:
        print(f"Register check failed ({type(exc).__name__}: {exc}) — holding the offer")
        return CARE


async def offer_is_welcome(text: str, *, title: str | None = None) -> bool:
    return await classify_register(text, title=title) == OPERATIONAL
