"""Read the eddy note that was just written and ask whether it named a target condition.

**Why the note and not the transcript.** The design chapter's rule for the
temperature instrument is *derive from artifacts already written*, and the eddy
note is exactly such an artifact: the idle checkpoint has already spent one
inference reading the conversation and has already written down what it was
about. Reading it again from scratch would spend a second, larger call on the
hottest background path in the bot to answer a smaller question.

It also fails in the right direction. The note is a paragraph, so this is a
bounded call with a bounded answer, and when the note is thin the noticer has
nothing to propose — which is correct, because a conversation whose own summary
cannot say what would be finished is a conversation that is not finished.

**What it is not allowed to do.** It does not mark anything ready. It writes a
*proposal*, which the practitioner confirms or ignores; `core.craft_readiness`
enforces that separation. And it never invents a target condition: the prompt
asks for a sentence the note already supports, and the parser drops a proposal
whose condition does not appear to be grounded in the note's own words. An
enthusiastic noticer is worse than a silent one here, because a proposal that is
wrong costs the practitioner the one thing this whole seam exists to save —
attention at the moment of deciding what to work on.

**Fails closed, on purpose and everywhere.** Model down, timeout, unparseable
JSON, missing key, ungrounded condition: all return ``None``. A noticer that
raises into `checkpoint_session` would turn a missing suggestion into a missing
eddy note, and the note is the practice record.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from core.craft_readiness import MIN_TARGET_CONDITION_CHARS
from core.models import REFLECTION_MODEL

NOTICER_TIMEOUT_S = 20.0
NOTICER_NUM_CTX = 4096

# Below this the note is a stub and there is nothing to read a condition out of.
MIN_NOTE_CHARS = 200

# A proposed condition must share this much vocabulary with the note. The check
# is crude and that is deliberate: it cannot tell a good condition from a bad
# one, but it can catch the failure mode that matters — a fluent sentence about
# a project the conversation never mentioned.
MIN_GROUNDING_OVERLAP = 0.34

# A **delta** is held to a lower bar than a target, and the reason is structural
# rather than a concession: a target condition describes what the conversation was
# about, so it should reuse the note's vocabulary; a spark describes what the
# conversation *lacks*, so the words naming the absence are by construction words
# the note does not contain. Measured on a real case — "whether channel primitives
# are relational or thematic is undecided" scores 0.33 against a note it is
# plainly about, because `relational`, `thematic` and `undecided` are exactly the
# missing concepts.
#
# The weaker guard is affordable for one specific reason, and it stops being
# affordable the day that reason changes: a proposal posts **unattended** on every
# idle checkpoint, while a spark is only ever posted by Spirit choosing to spend
# it at an arrival. There is a human read between this number and his eddy. If a
# spark ever fires automatically, this threshold has to rise to the target's.
MIN_SPARK_GROUNDING_OVERLAP = 0.2

_STOPWORDS = frozenset(
    """a an and are as at be been but by can could do does for from had has have
    how i if in into is it its of on or should so than that the their then there
    these they this to was we were what when which who will with would you your
    turtle you're it's""".split()
)

PROMPT = """You are reading a note that summarises a software-development conversation.

Decide one thing: did the conversation reach a point where someone could go and
do the work without asking further questions?

That is true only when the note itself says what would be finished — a decision
taken, a document to write, a behaviour to change. It is NOT true when the note
describes exploring, weighing, wondering, or disagreeing.

The target condition must describe a STATE OF THE WORLD when the work is done,
never an action and never who performs it.

  good: "the spec has a channel-primitives section and the tests name it"
  bad:  "Kermit reviews the files to check they match the concept"
  bad:  "write a specification for channel primitives"

If the only thing the note points to is something the practitioner must decide,
look at, or answer, the answer is false — that is a conversation continuing, not
work waiting.

**A target may be small.** It should be the smallest thing that would be worth
building, not the best thing this conversation could produce. If building it
would end the conversation, it is too big.

If there is no target yet, say what is MISSING — the one thing that would have to
be decided or named for a target to exist. Not a summary, not advice: the gap.

Reply with JSON only:
{"ready": true|false,
 "target_condition": "one sentence stating what is true when the work is done",
 "evidence": "the phrase in the note that says so",
 "missing": "when ready is false: the one thing that would have to be settled"}

Use ONLY words and facts from the note.

THE NOTE:
%s
"""


@dataclass(frozen=True)
class Proposal:
    target_condition: str
    evidence: str


@dataclass(frozen=True)
class Reading:
    """One read, two outputs — and the negative case stops being silence.

    Before 2026-08-17 a note that named no target produced nothing at all, so a
    conversation that was two decisions away looked exactly like one that had
    gone nowhere. His reframe: the spark *is* the delta between where a cooled
    eddy sits and what it would take to reach the forge. That is the same
    question this read already asks, answered from the other side, so it costs no
    extra inference — only a field.

    `proposal` is what the idle checkpoint acts on. `spark` is recorded and spent
    deliberately, because posting a delta into every idle eddy would make this the
    clutter it exists to reduce.
    """

    proposal: Proposal | None = None
    spark: str = ""


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if w not in _STOPWORDS}


def _grounded(condition: str, note: str, *, minimum: float = MIN_GROUNDING_OVERLAP) -> bool:
    """Is the condition made of the note's own vocabulary?

    Guards against the one failure that costs more than silence: a confident
    sentence about work the conversation never discussed. Overlap is measured
    against the condition's own words, so a short condition is not penalised for
    being short.
    """
    claim = _words(condition)
    if not claim:
        return False
    shared = claim & _words(note)
    return (len(shared) / len(claim)) >= minimum


def parse_reading(raw: str, note: str) -> Reading:
    """Both halves. A malformed reply is an empty Reading, never an exception."""
    proposal = parse_reply(raw, note)
    if proposal is not None:
        return Reading(proposal=proposal)
    try:
        data = json.loads(raw or "")
    except (ValueError, TypeError):
        return Reading()
    if not isinstance(data, dict):
        return Reading()
    missing = data.get("missing")
    if not isinstance(missing, str):
        return Reading()
    missing = " ".join(missing.split())
    # The same grounding rule as a target condition, for the same reason: a
    # fluent delta about a conversation that never happened costs more than
    # silence, and this one is posted into his eddy.
    if len(missing) < MIN_TARGET_CONDITION_CHARS:
        return Reading()
    if not _grounded(missing, note, minimum=MIN_SPARK_GROUNDING_OVERLAP):
        return Reading()
    return Reading(spark=missing)


def parse_reply(raw: str, note: str) -> Proposal | None:
    """Strict parse. Anything unexpected is a decline, never an exception."""
    try:
        data = json.loads(raw or "")
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or data.get("ready") is not True:
        return None
    condition = data.get("target_condition")
    if not isinstance(condition, str):
        return None
    condition = " ".join(condition.split())
    if len(condition) < MIN_TARGET_CONDITION_CHARS:
        return None
    if not _grounded(condition, note):
        return None
    evidence = data.get("evidence")
    evidence = " ".join(evidence.split()) if isinstance(evidence, str) else ""
    return Proposal(target_condition=condition, evidence=evidence)


async def read_note(note_text: str, *, model: str | None = None) -> Proposal | None:
    """A proposal the practitioner may confirm, or None. Never raises."""
    note = (note_text or "").strip()
    if len(note) < MIN_NOTE_CHARS:
        return Reading()
    try:
        from llm import chat_ollama_json

        raw = await chat_ollama_json(
            PROMPT % note,
            model=model or REFLECTION_MODEL,
            num_ctx=NOTICER_NUM_CTX,
            timeout_s=NOTICER_TIMEOUT_S,
        )
    except Exception as exc:  # noqa: BLE001 — see module docstring
        print(f"Readiness noticer declined: {type(exc).__name__}: {exc}")
        return Reading()
    return parse_reading(raw, note)
