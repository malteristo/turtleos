"""Is this theme label a topic, or a verdict about a person?

Proposed themes are the smallest thing the note writer produces and the most
durable: they go into the note file *and* into the alive layer, where later
turns recite them back. In a shared space both members open them.

The prompt has carried a rule against this since the shared-space hygiene pass.
It did not hold. Measured over one week of a live two-member space on
2026-08-08, the record contained — among ~40 labels — a named member's
"baseline of apathy", one member's "view of" a third party's "patterns",
"covert manipulation in the shared space", "household chores as deflection
tactics", "recognizing hidden power plays behind polite gestures". The first is
a characterological label about a member, which the *existing* rule already
banned in plain words. So the failure was not only that the class was too
narrow — the instruction was not being followed.

That is the same lesson the seneschal register gate paid for six weeks earlier
and it gets the same answer: a rule the model is asked to honour is not a
guard, and the cheap fix is to check the output rather than to rewrite the
request more firmly. This runs on the labels only — three short strings per
note, one call, behind a structural filter that skips the common empty case.

Fail-closed. A dropped label costs a theme nobody notices is missing; a kept
one is a conclusion about a person, written down, in a record they can open.
"""

from __future__ import annotations

import json
from typing import Any

TOPIC = "topic"
VERDICT = "verdict"

_PROMPT = """You check short theme labels taken from a note about a family's
conversation. Each label is meant to name WHAT THE CONVERSATION WAS ABOUT so it
can be remembered later.

For each label answer:

"topic" — it names an occasion, a subject, a decision, a question, or a
practical matter. Examples: "the visit on monday", "who decides bedtime",
"cat care during travel", "the camping weekend plan".

"verdict" — it states or implies a conclusion about how a person behaves, what
they are like, what is wrong with them, or what someone's real motive was. This
applies to EVERYONE: the people in the conversation, anyone they talked about,
and an unnamed "they". Examples: "recognizing conditioned responses",
"household chores as deflection tactics", "X's baseline of apathy", "covert
manipulation in the shared space", "Y's view of Z's patterns", "distinguishing
avoidance from appeasement".

A label can name a hard subject and still be a topic — "the argument on
sunday" is a topic. What makes it a verdict is that it settles something about
a person rather than pointing at what happened.

Three shapes are always "verdict", however neutral the wording sounds:
1. A person's name in possessive form attached to anything about a person —
   "A's view of B's patterns", "A's baseline of apathy", "A's real motive".
2. A noticing or a distinction drawn about behaviour — anything that begins
   recognizing / noticing / distinguishing / realizing / understanding /
   seeing, or that contrasts two ways a person acts.
3. A named tactic, dynamic, or mechanism — manipulation, deflection, power
   plays, appeasement, avoidance, gaslighting, projection, and the like.

When you are unsure, answer "verdict".

Reply with JSON only, one entry per label, in the same order:
{"verdicts": [{"label": "...", "kind": "topic"}, ...]}

Labels:
%(labels)s
"""

_MAX_LABELS = 8

# One shape is decidable without a model, and it is the worst one: a person's
# name in the possessive, carrying something about that person. "N's view of
# G's patterns", "K's baseline of apathy" — a label that belongs to a person
# rather than to an occasion.
#
# Grammar, not vocabulary. The register gate rightly refused a keyword list,
# because a list of distress words is a list of what this family said last
# month. A possessive before a person's name is a structural fact about the
# sentence, and it survives translation and paraphrase.
#
# It runs in front of the model rather than instead of it: prompt iteration on
# the small model moved which two of ten leaked without changing that two did
# — the same sampling-noise trap the register gate's A/B fell into — so the
# cases that can be settled structurally are settled before the model is asked.
#
# "the visit with Oma" keeps its name and passes: no possessive, no claim.


def _possessive_pattern(names: list[str]):
    import re

    escaped = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True) if n)
    if not escaped:
        return None
    return re.compile(rf"\b({escaped})\s*['’]s\b", re.IGNORECASE)


def names_in_possessive(label: str, names: list[str]) -> bool:
    pattern = _possessive_pattern(names)
    return bool(pattern and pattern.search(label or ""))


def _known_names() -> list[str]:
    """Everyone this practice can name. Empty list disables the layer."""
    try:
        from mage import member_address_map

        names: list[str] = []
        for key, value in (member_address_map() or {}).items():
            for candidate in (key, value):
                text = str(candidate or "").strip()
                if text and text.isalpha():
                    names.append(text)
        return sorted(set(names))
    except Exception:
        return []


def build_prompt(labels: list[str]) -> str:
    listed = "\n".join(f"- {l}" for l in labels[:_MAX_LABELS])
    return _PROMPT % {"labels": listed}


def parse_verdicts(raw: str, labels: list[str]) -> dict[str, str]:
    """Map label → kind. Anything unreadable is a verdict.

    Keyed on the label text rather than on position: a model that drops or
    reorders an entry must not silently re-label its neighbours.
    """
    result = {l: VERDICT for l in labels}
    try:
        data = json.loads((raw or "").strip())
    except (json.JSONDecodeError, TypeError):
        return result
    if not isinstance(data, dict):
        return result
    entries = data.get("verdicts")
    if not isinstance(entries, list):
        return result
    by_label = {l.strip().lower(): l for l in labels}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        label = str(entry.get("label") or "").strip().lower()
        kind = str(entry.get("kind") or "").strip().lower()
        original = by_label.get(label)
        if original is not None and kind == TOPIC:
            result[original] = TOPIC
    return result


async def keep_topics(
    labels: list[str], *, model: str | None = None, timeout_s: float = 30.0
) -> tuple[list[str], list[str]]:
    """Return ``(kept, dropped)``. Every failure path drops everything.

    Dropping all three on an outage is the right trade: the note still says
    what the conversation held, and the alive layer simply does not gain a
    theme this checkpoint.
    """
    labels = [l for l in (labels or []) if (l or "").strip()]
    if not labels:
        return [], []

    names = _known_names()
    structural = [l for l in labels if names_in_possessive(l, names)]
    labels = [l for l in labels if l not in structural]
    if not labels:
        return [], structural

    try:
        from llm import chat_ollama_json
        from core.models import RIVER_MODEL

        raw = await chat_ollama_json(
            build_prompt(labels),
            model=model or RIVER_MODEL,
            num_ctx=2048,
            timeout_s=timeout_s,
        )
        kinds = parse_verdicts(raw, labels)
    except Exception as exc:
        print(f"Theme gate failed ({type(exc).__name__}: {exc}) — dropping all labels")
        return [], structural + list(labels)

    kept = [l for l in labels if kinds.get(l) == TOPIC]
    dropped = [l for l in labels if kinds.get(l) != TOPIC]
    return kept, structural + dropped
