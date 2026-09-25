# Role needs — destination

**Date:** 2026-09-14  
**Status:** Destination. Named 2026-09-14 (was briefly “agent experience”; *experience* imported UX and feelings). River house picture is in the harness. Turtle `state/context.md` now has a reader; the first text is a Spirit draft awaiting his correction.  
**Spec:** TURTLE_SPEC §5.7 (River needs action selection, not conversation) · §7.4 (Turtle attunement) · continuity sequence already on the board.  
**Companions:** Magic `desk/notes/on_role_needs.md` · `desk/notes/on_spirit_and_craft_turtle.md` · `desk/notes/initiative-continuity-claim.md`.

A **role need** is what a job consumes in order to be done: an artifact, a tool, or an attunement. It comes from the implementation, the assigned role, and the tools — not from a inner life.

This is a lens, not a subsystem. No new suite. No morale.

Four artifacts first (`docs/development.md` §12). The press release is what a practitioner notices when the roles are supplied. Mechanism stays out of it.

---

## Claim class

| Claim | Class | Who can establish it |
|-------|--------|----------------------|
| At the moment of action, Turtle and River had what their role needs, and were spared what would only confuse them. | **Supply against a role** | Spirit sit (`#spirit`) + what the packet / house line actually contained + the table below. |

---

## 1. Press release

You talk. Turtle already has this room and does not ask you to recap your own life. When the house is unwell, River stays quiet instead of offering a new door on a broken floor.

You do not see their briefings. You notice fewer times you had to be their memory, and fewer acts that did not belong.

---

## 2. Happy path

```
Alex:  (opens yesterday's eddy) Still on the same thing.
Turtle: (continues. Does not ask what you were doing.)

(the house is not well)
Alex:  (types in the parent)
River: (does not offer)
```

*Invisible: Turtle was given history and the present of the room. River was given a short house picture and used it only to withhold.*

---

## 3. Success criteria

| # | Experience | Can fail in week three | Re-run |
|---|------------|------------------------|--------|
| 1 | A designer can name, for Turtle and for River, what the role needs at turn time, and whether it exists. | The table below loses a status, or a new inhabitant is added with no row. | `tests/test_role_needs_doc.py` |
| 2 | Turtle's missing needs stay the continuity sequence already named — not a second pile. | We ship a Turtle toy while the context reader is dead, or treat a file-exists check as load. | `tests/test_practitioner_context.py`; open-record dimensions. |
| 3 | Once River has a house picture, it uses it to withhold, never to chat. | A river act narrates canary, launchd, or quiet-window facts. | Spirit sit in `#spirit` parent; shake still rejects prose. |
| 4 | Role needs are never scored as feelings. | A dest, report, or sit asks whether an agent is happy. | Read this file and the desk note. |

Mechanism-blind: a different harness could still be scored on “role named, supply visible, withhold not chatter, no morale.”

---

## 4. Abandon line

Stop calling these role needs if the next three chapters add a third suite, a happiness metric, or a retreat. The lens is what the job consumes.

---

## The table

Status is `exists` / `partial` / `missing`. A row without one is a defect.

### Turtle

| Need | Source | Status | Where |
|------|--------|--------|-------|
| Present of this room | Role: honour the current interaction | exists | Thread card, inject packet |
| Shared history that can be read | Role: honour history | partial | Topic memory runs; navigable twine / catch-up still fiction |
| Current practitioner context | Role: know where they are | partial | `state/context.md` + `practitioner_context.py` at eddy-open. Draft on the kermit root; he has not corrected it. |
| Character and relation | Attunement | partial | `mirror.md` / `resonance.md` when present; empty on some roots, honestly |
| Recent eddies on this river | Role: know what this channel has been doing | partial | Packet one-line counts (no names). `survey_eddies` speaks five-state + days. Reciting the list every turn is the miss. |

### River

| Need | Source | Status | Where |
|------|--------|--------|-------|
| Action selection, not conversation | Implementation + §5.7 | exists | JSON acts; prose rejected |
| Which acts this room offers | Role + primitive | exists | River prompt + channel primitive. Craft default is `file_intake`; a display request wins. River sees the parent drop (2026-09-16). |
| Tools that prepare a display | Role: run the OS as practice | partial | Harness collectors on `show_threads` / channel menu / intake. No model tool-loop yet. |
| Whether the house is well enough to act | Role: keep the live system smooth | partial | `river_house.py` gathers canary + last turn; harness withholds offers. Live sit owed. Ops report still Spirit-only. |
| Ambient observation of practice state | Role as written, not as run | missing | Continuity initiative, after write/read evidence |

### Memory

Topic memory **runs**. It is a curator over notes, not a third conversational agent. `memory_agent.py`: topics from all eddy notes, heat, passive block each turn, hourly rebuild at quiet windows. Live on this instance (kermit `memory/topics.yaml` current).

A three-mouth architecture with Memory as a peer to River and Turtle does **not** run. That is a different claim. No row for that until something speaks.

| Need | Source | Status | Where |
|------|--------|--------|-------|
| Topics the room keeps returning to | Role: honour recurrence, not only the last week | exists | `memory/`; packet topic block; `memory_loop` |

---

## How we assess

Not “is the agent happy.”

1. **Role** — what must be true for this job, at this moment?
2. **Supply** — what reached the prompt, the tools, the memory window?
3. **Miss class** — missing artifact, wrong attunement, a tool that cannot do the job, or surplus that should have been held.

Spirit sits in `#spirit` (live-test only). Craft Turtle interprets the miss in `#craft-turtle`. The Mage still owns felt sense, in his own time.

---

## First slice — River house picture

A compact fact River already has instruments for: last canary (`/tmp/canary-history.jsonl`), last practitioner turn or write in flight (`deploy_guard` signals). Injected at classify time. The harness strips offer acts when canary is red or a turn is in flight. Never narrated into an act.

`river_house.py`. Do not add a new canary. Do not call full readiness every message.

**Spirit sit:** one `#spirit` parent line while canary is green (offers may still appear) is not the withhold case. The withhold case is a planted red in the unit test; a live red is the re-run.

---

## Second slice — practitioner context

`state/context.md` is the file. `practitioner_context.py` is the only reader. Native and craft prompts call it at eddy-open. The continuity open-record uses the same helper, so a file that exists and is empty is not “loaded.”

**Writer.** A thin projection of `desk/state.md` Continue From plus the live pressures on the craft bearings — not a sitting dump and not a second `key-turtle.md`. The key is the path. This file is this week. Spirit drafts; he corrects in `desk/state/context.md`; Spirit copies to Mini. Turtle-offered updates are not this slice.

**Sit.** `#spirit` cannot prove the kermit-root write. A prompt build against `~/workshops/kermit` is the Spirit-sufficient check. A living eddy on that root is collaboration or his own time — not a probe he types.

---

## Out of scope

- A third test suite or live-verify runner
- Team-building, morale, inner life
- Memory as a third agent until it runs
- TURTLE_SPEC amendment this sitting (candidate after the house picture exists)
- Replacing `state/context.md` with a new Turtle briefing
