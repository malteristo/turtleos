"""Whether a craft eddy has become work yet — and what "done" would mean.

Craft thinking happens in `#craft-turtle` eddies and becomes code on Forge or
Anvil. The seam between those two is a readiness judgement, and until now the
system could not represent one:

* `disposition: ready` existed only for **prepared** eddies — the eight Spirit
  opened with a paired workspace. An ordinary craft eddy, which is most of them,
  had no field for it at all.
* The only writer was the practitioner typing **`!dissolve`** — a word meaning
  *end this* — so saying *this is ready to become work* required reaching for the
  verb that means the opposite.
* Nothing proposed it. In the five days after the flag path shipped it fired
  once, on the day it was built, for the one eddy Spirit had prepared itself.
  Seven prepared eddies sat at `open` while their surfaces were edited days
  later. This is the shape the craft *moves* channel died of: a mechanism that
  waits for the practitioner to perform a separate marking act records nothing,
  because the practice happens in the conversation and not beside it.

**The target condition is the gate, and that is the whole design.** The Mage's
own definition of readiness is *the amount of work Spirit can perform without
having to ask for more input* — a property of the artifact, testable from
outside, rather than a feeling about the conversation. What makes that testable
is a written statement of what would be true when the work is finished. So
`propose` and `confirm` both refuse without one. An eddy with no expressible
target condition is not a ready eddy that forgot its paperwork; it is an
unfinished conversation, and the honest move is to say what is missing and let
it keep going.

**Refusal is an artifact, not a silence.** Spirit evaluates readiness
independently at the arrival and may disagree. `refuse` requires a named gap,
because a refusal with no gap takes the eddy off the board and gives the Hearth
nothing to work on.

*Where the gap actually goes, stated honestly because the first version of this
paragraph overclaimed it:* the gap is written here and rendered on the craft
board. **Nothing posts it into the eddy** — that would need a write path in
`scripts/craft_board.py`, which is read-only on purpose. So today a refusal
reaches the Mage when he reads the board or when Spirit tells him, not when he
opens the thread. Filed, not forgotten: `2026-08-17-refusal-does-not-reach-the-eddy`.

**States**

    (absent) → proposed → ready → acted
              ↘ refused ↗
              ↘ waiting

``proposed`` a noticer read a target condition out of the conversation; awaiting
             the practitioner. A proposal is not readiness.
``ready``    the practitioner confirmed. Spirit may plan work against it.
``refused``  Spirit looked and named what is **missing** from the artifact.
``waiting``  the conversation itself put the ball in someone's court — it ends on
             a question to the practitioner, or on a named trigger to wait for.
``acted``    a session consumed it. Kept rather than deleted so the take rate of
             the proposal is measurable at all.

**Why `waiting` is not a kind of `refused`.** They were one state for half a day
and the first real triage showed why they cannot be. Of the five warm craft
eddies on 2026-08-16, **three ended with the ball in the Mage's court** — one on
an unanswered question from Turtle, one on a family act only he can do, one
explicitly deferred until *"the family trial thread shows week-on-week use."*
Nothing was missing from any of those conversations. Filing them as refusals
would have said *this artifact is not actionable*, when the true statement is
*this artifact is finished and someone is holding it* — and the board's whole job
is telling those apart. Before this state existed, an eddy waiting on him was
indistinguishable from one nobody had looked at: both read `cold`.

The practical difference is what each one owes. A refusal owes the eddy a gap,
because Spirit is adding information the conversation does not contain. A wait
owes it nothing, because the eddy already says what it is waiting for — telling
him again would be repeating his own words back to him.

**Why this is not in `prepared_eddies.py`.** That module owns a *workspace*
lifecycle — a markdown surface, a `## Determination`, a harvest into bright.
This owns a *conversation* judgement, and it has to work for eddies that have no
surface. They share one sidecar file, through that module's loader, because two
YAML stores describing overlapping state is the drift this codebase keeps
logging. The file is still named `prepared_eddies.yaml`: renaming live state on
a running host is a migration and belongs in its own change, not riding along
inside a feature.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.prepared_eddies import load_sidecar, save_sidecar

ROOT_KEY = "readiness"

PROPOSED = "proposed"
READY = "ready"
REFUSED = "refused"
WAITING = "waiting"
ACTED = "acted"

STATES = (PROPOSED, READY, REFUSED, WAITING, ACTED)

# What a `waiting` row can be waiting for. `practitioner` is the common case —
# the conversation ended on a question to him. Anything else is a named trigger,
# free text, because the triggers real conversations name ("when the family
# trial shows week-on-week use") are not a closed set and pretending otherwise
# would push them into an "other" bucket nobody reads.
WAITING_ON_PRACTITIONER = "practitioner"

# Temperature vocabulary, locked in docs/chapters/design-craft-eddy-temperature.md.
# Derived from artifacts already written — no model call on a glance, because a
# temperature that costs an inference is one nobody can afford to look at often.
HOT = "hot"
WARM = "warm"
TEMP_READY = "ready"
COOLING = "cooling"
COLD = "cold"

HOT_WITHIN_HOURS = 6
WARM_WITHIN_HOURS = 48
# Beyond this with no ready signal, an eddy is not resting, it is abandoned.
COLD_AFTER_HOURS = 168  # seven days

# A target condition shorter than this is a label, not a statement of done.
# **Not a size limit on ambition.** A minimum viable target is supposed to be
# thin — `topics are eddies` is 17 characters and perfectly valid — so this floor
# only refuses things that are not statements at all (`done`, `spec it`). The
# 2026-08-17 model change made this explicit: confirm as soon as a target is
# *nameable*, then refine. Small is the point; unstatable is the failure.
MIN_TARGET_CONDITION_CHARS = 12

# The check that actually carries the weight, and it was bought by a live control
# rather than reasoning. Run against real eddy notes, the noticer produced
# *"Kermit reviews specific files … to verify if they match their intended
# concept"* — grounded, fluent, and useless, because a target whose actor is the
# practitioner is not a target an autonomous session can meet. The length floor
# waves that through: it is 74 characters.
#
# Applied to machine-authored targets only. A target the Mage writes is
# authoritative — refusing his wording because it opens with a verb would be the
# gate overruling the person it exists to serve, and a false refusal of his own
# sentence costs more than an imperfect target he chose.
_ACTION_OPENERS = frozenset(
    """write build add create make implement decide review check discuss explore
    define design figure update fix refactor document draft ship spec plan
    investigate clarify confirm choose pick evaluate assess""".split()
)

PRACTITIONER = "practitioner"

# How a revision is labelled, and why both exist. `refine` keeps the direction
# and sharpens it; `replace` means the conversation went somewhere else. They are
# recorded separately because the difference is the only way to answer whether
# confirming early actually works — see `target_survived`.
REFINE = "refine"
REPLACE = "replace"


class ReadinessError(ValueError):
    """A readiness transition that must not be performed silently."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rows(data: dict[str, Any]) -> dict[str, Any]:
    rows = data.get(ROOT_KEY)
    if not isinstance(rows, dict):
        rows = {}
        data[ROOT_KEY] = rows
    return rows


def _clean_target_condition(raw: str | None, *, by: str = PRACTITIONER) -> str:
    """The gate. Refuses what is not a statement, and what is not a *state*.

    Both checks are crude and neither pretends otherwise. Together they refuse
    the two failures actually observed: a field filled in to get past the gate,
    and a fluent sentence describing an action rather than a condition.
    """
    text = " ".join((raw or "").split())
    if len(text) < MIN_TARGET_CONDITION_CHARS:
        raise ReadinessError(
            "readiness needs a target condition — one sentence saying what is "
            "true when the work is done. Without it there is no stopping rule, "
            "and an eddy that cannot state one is still a conversation."
        )
    if by != PRACTITIONER:
        opener = text.split(" ", 1)[0].strip(",.:;\"'").lower()
        if opener in _ACTION_OPENERS:
            raise ReadinessError(
                f"'{text[:60]}…' reads as an action, not a state of the world. A "
                "target condition says what is TRUE when the work is done — a "
                "session cannot meet 'write the spec', only 'the spec exists'."
            )
    return text


def entry_for(runtime_dir: str | Path, thread_id: int) -> dict[str, Any] | None:
    entry = _rows(load_sidecar(runtime_dir)).get(str(thread_id))
    return entry if isinstance(entry, dict) else None


def state_of(runtime_dir: str | Path, thread_id: int) -> str | None:
    entry = entry_for(runtime_dir, thread_id)
    if not entry:
        return None
    raw = entry.get("state")
    return raw if raw in STATES else None


def target_condition_of(runtime_dir: str | Path, thread_id: int) -> str | None:
    entry = entry_for(runtime_dir, thread_id)
    if not entry:
        return None
    raw = entry.get("target_condition")
    return raw if isinstance(raw, str) and raw.strip() else None


def list_by_state(runtime_dir: str | Path, state: str) -> list[tuple[str, dict[str, Any]]]:
    rows = _rows(load_sidecar(runtime_dir))
    return [
        (str(tid), entry)
        for tid, entry in rows.items()
        if isinstance(entry, dict) and entry.get("state") == state
    ]


def _write(runtime_dir: str | Path, thread_id: int, entry: dict[str, Any]) -> dict[str, Any]:
    data = load_sidecar(runtime_dir)
    _rows(data)[str(thread_id)] = entry
    save_sidecar(runtime_dir, data)
    return entry


def propose(
    runtime_dir: str | Path,
    thread_id: int,
    *,
    target_condition: str,
    evidence: str = "",
    by: str = "turtle",
) -> dict[str, Any]:
    """A noticer read a target condition out of the conversation. Not readiness.

    Re-proposing over an existing proposal is allowed and overwrites: the
    conversation moved, so the previous read is stale rather than contested.
    Re-proposing over ``ready`` is refused — that would silently un-confirm
    something the practitioner already agreed to.
    """
    condition = _clean_target_condition(target_condition, by=by)
    current = state_of(runtime_dir, thread_id)
    if current in (READY, ACTED):
        raise ReadinessError(
            f"thread {thread_id} is already {current}; a proposal must not "
            "overwrite a confirmation"
        )
    entry = dict(entry_for(runtime_dir, thread_id) or {})
    entry.update(
        {
            "state": PROPOSED,
            "target_condition": condition,
            "evidence": (evidence or "").strip(),
            "proposed_at": _now(),
            "proposed_by": by,
        }
    )
    # A fresh proposal answers whatever the last refusal said was missing.
    entry.pop("gap", None)
    entry.pop("refused_at", None)
    entry.pop("refused_by", None)
    return _write(runtime_dir, thread_id, entry)


def confirm(
    runtime_dir: str | Path,
    thread_id: int,
    *,
    target_condition: str | None = None,
    by: str = PRACTITIONER,
) -> dict[str, Any]:
    """The practitioner agrees this is work. Ready from here.

    ``target_condition`` may be supplied to correct the proposal's wording, or
    omitted to accept it. It may never be absent from the result: confirming an
    entry that has no condition on record is the gate failing open.
    """
    entry = dict(entry_for(runtime_dir, thread_id) or {})
    if entry.get("state") == ACTED:
        raise ReadinessError(f"thread {thread_id} was already acted on")
    condition = _clean_target_condition(
        target_condition if target_condition is not None else entry.get("target_condition"),
        by=by,
    )
    entry.update(
        {
            "state": READY,
            "target_condition": condition,
            "confirmed_at": _now(),
            "confirmed_by": by,
        }
    )
    entry.pop("gap", None)
    return _write(runtime_dir, thread_id, entry)


def refuse(
    runtime_dir: str | Path,
    thread_id: int,
    *,
    gap: str,
    by: str = "spirit",
) -> dict[str, Any]:
    """Someone looked and this is not actionable yet. The gap is the artifact.

    Refusing requires naming what is missing, because a refusal with no gap
    takes the eddy off the board without giving the Hearth anything to work on —
    which is indistinguishable, from inside the eddy, from being ignored.
    """
    text = (gap or "").strip()
    if not text:
        raise ReadinessError(
            "refusing readiness requires naming the gap — it is the next thing "
            "to talk about in the eddy, and without it the refusal is a silence"
        )
    entry = dict(entry_for(runtime_dir, thread_id) or {})
    entry.update(
        {
            "state": REFUSED,
            "gap": text,
            "refused_at": _now(),
            "refused_by": by,
        }
    )
    return _write(runtime_dir, thread_id, entry)


def _overlap(a: str, b: str) -> float:
    """Vocabulary overlap, as evidence beside a declared label — not as the label.

    Whether a revision is a refinement or a replacement is a judgement, and the
    caller declares it. Computing it instead would put a judgement in a constant.
    Recording it *alongside* the declaration is what lets a later reader ask
    whether the labels track the text — the same discipline as the done-detector
    printing its citations.
    """
    wa = {w for w in re.findall(r"[a-z0-9]+", (a or "").lower()) if len(w) > 2}
    wb = {w for w in re.findall(r"[a-z0-9]+", (b or "").lower()) if len(w) > 2}
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def revise(
    runtime_dir: str | Path,
    thread_id: int,
    *,
    target_condition: str,
    kind: str = REFINE,
    by: str = PRACTITIONER,
) -> dict[str, Any]:
    """Change a confirmed target. `ready` is a waypoint, not a terminus.

    **Why this exists.** The first confirmed target in the practice went stale
    within seven minutes: the Mage pressed confirm at 08:53 and the eddy reached
    a narrower conclusion at 09:00 that the recorded sentence did not know. And
    nothing could update it — `propose` refuses to overwrite a confirmation, which
    is right against a noticer re-firing on a stale read and wrong against a
    practitioner who confirmed and then kept thinking.

    His model, 2026-08-17: **confirm as soon as a target is nameable, then refine
    it.** A constant gravitational pull toward something concrete, without the
    concrete thing being fixed. The risk he named is closing too early and
    suffocating what might have emerged; the sharper form of that risk is
    *anchoring* — hill-climbing converges on a local maximum, and a confirmed
    target pulls toward refinements of itself. Waiting longer does not fix that.
    Making the target cheap to **replace**, not merely to refine, does.

    So both moves exist and are recorded separately, because the difference is
    the only thing that can answer whether early confirmation works.
    """
    if kind not in (REFINE, REPLACE):
        raise ReadinessError(f"kind must be {REFINE!r} or {REPLACE!r}, got {kind!r}")
    entry = dict(entry_for(runtime_dir, thread_id) or {})
    if entry.get("state") != READY:
        raise ReadinessError(
            f"thread {thread_id} is {entry.get('state')!r}, want {READY!r} — "
            "a target is revised after it is confirmed; before that, propose"
        )
    previous = entry.get("target_condition") or ""
    condition = _clean_target_condition(target_condition, by=by)
    if condition == previous:
        raise ReadinessError("the revision is identical to the target it replaces")

    history = list(entry.get("target_history") or [])
    history.append(
        {
            "condition": previous,
            "superseded_at": _now(),
            "kind": kind,
            "by": by,
            # Evidence beside the declaration, never instead of it.
            "overlap_with_next": round(_overlap(previous, condition), 2),
        }
    )
    entry["target_condition"] = condition
    entry["target_history"] = history
    entry["revised_at"] = _now()
    return _write(runtime_dir, thread_id, entry)


def target_survived(entry: dict[str, Any] | None) -> bool:
    """True when no revision has changed the *direction* of this eddy's target.

    The number his model needs to be falsifiable. If early targets are almost
    always replaced, the capture threshold is firing before there is anything to
    pull toward. If they are never replaced, that is either the model working or
    the anchoring being real and invisible — and knowing the reading is ambiguous
    is worth more than reading it as a win.
    """
    return not any(
        row.get("kind") == REPLACE for row in (entry or {}).get("target_history") or []
    )


def is_stale_ready(entry: dict[str, Any] | None, last_activity: str | None) -> bool:
    """True when the eddy kept talking after its target was last agreed.

    Not a defect and not a nag: under the refine model this is the ordinary
    state of a live eddy, and it is the signal that the recorded sentence may be
    behind the conversation. The board says so rather than presenting a stale
    target as current — which it did for seven minutes on the first one.
    """
    if not entry or entry.get("state") != READY:
        return False
    agreed = entry.get("revised_at") or entry.get("confirmed_at")
    if not isinstance(agreed, str) or not isinstance(last_activity, str):
        return False
    try:
        return datetime.fromisoformat(last_activity) > datetime.fromisoformat(agreed)
    except ValueError:
        return False


def mark_gap_posted(runtime_dir: str | Path, thread_id: int) -> dict[str, Any]:
    """Record that the gap actually reached the thread.

    Two things can produce a `refused` row and they are not equivalent: a
    board-only refusal, and one whose gap was posted into the eddy. Without this
    field the board has to describe both the same way, and the description was
    already wrong once — three files claimed the Hearth had been told when
    nothing posted. A state that can be reached two ways needs to say which.
    """
    entry = dict(entry_for(runtime_dir, thread_id) or {})
    if entry.get("state") != REFUSED:
        raise ReadinessError(
            f"thread {thread_id} is {entry.get('state')!r}, want {REFUSED!r} — "
            "only a refusal has a gap to post"
        )
    entry["gap_posted_at"] = _now()
    return _write(runtime_dir, thread_id, entry)


def mark_waiting(
    runtime_dir: str | Path,
    thread_id: int,
    *,
    on: str = WAITING_ON_PRACTITIONER,
    note: str = "",
    by: str = "spirit",
) -> dict[str, Any]:
    """The conversation is finished and someone is holding it.

    Not a judgement about the artifact — see the module docstring. ``on`` is
    either ``practitioner`` or a named trigger in the conversation's own words,
    because a wait whose condition nobody wrote down is indistinguishable from
    a thing that was dropped.
    """
    condition = (on or "").strip()
    if not condition:
        raise ReadinessError(
            "a wait needs something to be waiting for — 'practitioner' or the "
            "trigger the conversation named. A wait with no condition is a drop."
        )
    entry = dict(entry_for(runtime_dir, thread_id) or {})
    if entry.get("state") == ACTED:
        raise ReadinessError(f"thread {thread_id} was already acted on")
    entry.update(
        {
            "state": WAITING,
            "waiting_on": condition,
            "waiting_note": (note or "").strip(),
            "waiting_since": _now(),
            "waiting_by": by,
        }
    )
    entry.pop("gap", None)
    return _write(runtime_dir, thread_id, entry)


def record_suggested_spark(
    runtime_dir: str | Path, thread_id: int, spark: str
) -> dict[str, Any] | None:
    """Keep a delta the noticer found, without posting it or changing state.

    The idle checkpoint reads each craft eddy once and gets two possible answers:
    a nameable target, or the reason there isn't one. Posting the second on every
    idle pass would make the noticer the clutter it exists to reduce — 10 cold
    eddies is 10 messages in the channel he called cluttered. So the delta is
    *recorded* and the arrival decides whether to spend it.

    Returns None when there is nothing to store, so a caller can tell "no
    suggestion" from "stored an empty one".
    """
    text = " ".join((spark or "").split())
    if not text:
        return None
    entry = dict(entry_for(runtime_dir, thread_id) or {})
    if entry.get("state") in (READY, ACTED):
        return None
    entry["suggested_spark"] = text
    entry["suggested_spark_at"] = _now()
    return _write(runtime_dir, thread_id, entry)


def mark_sparked(
    runtime_dir: str | Path,
    thread_id: int,
    *,
    spark: str,
    last_activity: str | None = None,
    by: str = "spirit",
) -> dict[str, Any]:
    """Spirit named the delta to a buildable target, in the eddy. Now his move.

    **The spark is the delta** (his framing, 2026-08-17): the distance between
    where a cooled eddy is and what would be needed to take it to the forge. That
    makes it the same object as a refusal's gap, on a different occasion — before
    any proposal rather than after one — which is why it needs no state of its
    own. After a spark the eddy is genuinely `waiting` on him, and that is what
    the board should say.

    **Scarcity is enforced, not hoped for.** A spark posted into an eddy that has
    not been touched since the last spark is the second telling of the same thing,
    and the moves channel and the handoff flag both died of a mechanism that kept
    speaking into silence. So a second spark requires that he has spoken since the
    first. There is no session counter, because a rule tied to something
    observable beats a number nobody can check.
    """
    text = " ".join((spark or "").split())
    if not text:
        raise ReadinessError(
            "a spark is the delta — what would have to be named for this to become "
            "work. Without it there is nothing to post but a nudge."
        )
    entry = dict(entry_for(runtime_dir, thread_id) or {})
    if entry.get("state") in (READY, ACTED):
        raise ReadinessError(
            f"thread {thread_id} is {entry.get('state')!r} — it already has a target"
        )
    previous_at = entry.get("sparked_at")
    if previous_at and isinstance(last_activity, str):
        # The comparison and the refusal are separate statements on purpose.
        # `ReadinessError` subclasses `ValueError`, so raising inside the
        # `try` that guards `fromisoformat` meant the guard swallowed the
        # refusal and every second spark was allowed — caught by the test that
        # claimed to cover it, and it is this week's recurring shape: a broad
        # except catching the one thing it was never meant to catch.
        spoke_since: bool | None = None
        try:
            spoke_since = datetime.fromisoformat(last_activity) > datetime.fromisoformat(
                previous_at
            )
        except ValueError:
            spoke_since = None  # unreadable stamp: do not block on a bad clock
        if spoke_since is False:
            raise ReadinessError(
                "this eddy has not been touched since the last spark — a second "
                "one is the same thing said twice into silence"
            )
    entry.update(
        {
            "state": WAITING,
            "waiting_on": WAITING_ON_PRACTITIONER,
            "spark": text,
            "sparked_at": _now(),
            "sparked_by": by,
            "spark_count": int(entry.get("spark_count") or 0) + 1,
        }
    )
    entry.pop("gap", None)
    entry.pop("suggested_spark", None)
    return _write(runtime_dir, thread_id, entry)


def spark_worked(entry: dict[str, Any] | None) -> bool | None:
    """Did a spark ever lead to a confirmed target? None when never sparked.

    The only honest measure of the spark, and it is deliberately not "does it
    read well". A spark that produces an elegant sentence and no confirmed target
    has done nothing; the eval is whether the eddy crossed into work afterwards.
    """
    entry = entry or {}
    if not entry.get("spark_count"):
        return None
    return bool(entry.get("confirmed_at"))


def mark_acted(runtime_dir: str | Path, thread_id: int) -> dict[str, Any]:
    """A session consumed this eddy. Kept, not deleted — see the module docstring."""
    entry = dict(entry_for(runtime_dir, thread_id) or {})
    if entry.get("state") != READY:
        raise ReadinessError(
            f"thread {thread_id} is {entry.get('state')!r}, want {READY!r} — "
            "work is planned against a confirmation, not against a proposal"
        )
    entry.update({"state": ACTED, "acted_at": _now()})
    return _write(runtime_dir, thread_id, entry)


def _hours_since(iso: str | None, *, now: datetime | None = None) -> float | None:
    if not isinstance(iso, str) or not iso.strip():
        return None
    try:
        stamp = datetime.fromisoformat(iso)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    reference = now or datetime.now(timezone.utc)
    return (reference - stamp).total_seconds() / 3600.0


def temperature(
    *,
    state: str | None,
    last_practitioner_message_at: str | None,
    now: datetime | None = None,
) -> str:
    """Where the heat is, from artifacts already written. No inference call.

    Readiness outranks idleness on purpose. An eddy that reached a confirmed
    target condition and then went quiet is not cooling off — it is waiting for
    a session, and reporting it as cold would hide the one row that is
    actionable behind the ones that are not.
    """
    if state in (READY, PROPOSED):
        return TEMP_READY
    if state == ACTED:
        return COOLING
    if state == WAITING:
        # An open move is heat, whoever holds it. Ageing a waiting eddy to cold
        # would hide exactly the rows that need a person rather than a session.
        return WARM
    age = _hours_since(last_practitioner_message_at, now=now)
    if age is None:
        return COLD
    if age < HOT_WITHIN_HOURS:
        return HOT
    if age < WARM_WITHIN_HOURS:
        return WARM
    if age < COLD_AFTER_HOURS:
        return WARM if state == REFUSED else COLD
    return COLD
