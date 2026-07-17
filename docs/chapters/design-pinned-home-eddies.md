# Design Chapter: Pinned Home Eddies

**Opened:** 2026-07-17  
**Status:** Implementing / code landed — dogfood after both-bot restart → [2026-07-17-implement-pinned-home-eddies.md](2026-07-17-implement-pinned-home-eddies.md)  
**Spec trace:** TURTLE_SPEC §5.3 (river surface), §8 (eddy lifecycle / cool), §11.5 (practice artifacts); story-layer vision §5  
**Sources:** Forge design slice 2026-07-17 (workout lifecycle; Discord-honest periphery; `!pin` as first real product use)  
**Dogfood first:** Operator river; UI copy hosted-safe

---

## Tension

Practitioners accumulate **working documents** that outlive one chat: a workout plan, a form draft, a dates list. Today those live as scroll-back in some eddy — or as Tier-1 files found only via `!artifacts` browse. Turtle once described a side-panel “shelf” that Discord does not have. The word-action gap is the product risk: fluent fiction instead of a Discord-native door.

The need: **create → revise weeks later → perform (walk the plan, note changes mid-session)** without hunting which thread held the plan.

---

## Acceptance narrative (workout lifecycle)

1. **Create** — In an eddy, Turtle and the practitioner shape a workout plan. River/Turtle offers: keep this as a working plan? Practitioner confirms (`!pin` or button).
2. **Home** — That eddy becomes the **home eddy** for the plan. A **river pin card** appears (Discord pin tray). Canonical body is a **Tier-1 artifact** on disk.
3. **Revise** — Weeks later: open the river pin → **Continue** → same home eddy → update exercises. Artifact updates; conversation stays in one room.
4. **Perform** — At the gym: same pin → Continue. Turtle walks the current plan. Mid-set (“increased the weight”, form question) → quiet write to the artifact + one-line ack. No search for “which eddy was that?”

If the practitioner cannot complete (3) and (4) from the river pin without sidebar archaeology, day one failed.

---

## Concepts

| Term | Meaning |
|------|---------|
| **Artifact** | Durable Tier-1 file (the workout plan). Canonical truth on disk. |
| **Home eddy** | The conversation room dedicated to that artifact. **1:1** with the primary artifact for day one. |
| **River pin card** | Discord-pinned short message on the practice river: title, optional last-touched, **Continue** / **Open**. Not the full document body. |
| **Attunement** | On Continue / re-entry: Turtle loads the artifact (+ summary if huge) and a recent slice (last N exchanges or latest eddy note) — not the entire thread history every time. |

**Product speech (honesty):** Say *river pin + home eddy + file*. Do **not** describe side-panels, shelves that float beside chat, or real-time sidebar sync. Discord has a pin tray; we use it.

---

## Day-one model

```text
Offer ("Keep as working plan?")
        │
        ▼
River pin card ──Continue──► Home eddy ◄──read/write──► Tier-1 artifact
        │                         ▲
        └────────Open─────────────┘ (browser / presenter)
```

| Decision | Lock |
|----------|------|
| Job | Home eddy for create / revise / perform |
| Surface | Native Discord pin tray + short card + Open |
| Cardinality | One home eddy ↔ one primary artifact |
| Creation | Offer when a clear working doc appears; confirm via button; typed path = `!pin` |
| Mid-session writes | Quiet artifact update + one-line ack (tune via dogfood) |
| Lifecycle | Home eddies **sticky** (see below) |
| Audience | Operator dogfood; buttons: Continue / Open / Stop pinning |

**Not day one:** Portable “use this plan in any eddy”; `offer_capture` (“add to your dates?”); story “three weeks untouched” nudges; floor-card shelf alternative; multi-document homes.

---

## `!pin` product semantics

Today’s `cmd_pin` ([commands.py](../../commands.py)): river-only reply/`message_id` → `message.pin()`. Almost unused in practice. Day one **repurposes `!pin` as the product act** for working plans — its first real use case. Do **not** invent a parallel `!keep` vocabulary for this feature (CE theme `!keep` remains a different act).

### Intended behaviors

| Context | `!pin` / pin act means |
|---------|------------------------|
| **In home-candidate eddy** (working doc present, or reply to the doc message) | Bind this eddy as home for the artifact; write/ensure Tier-1 file; post or refresh **river pin card**; pin that card on the river |
| **Offer button** (“Keep as working plan” / pin confirm) | Same binding as above |
| **River** — reply to an ordinary message | Degenerate case: Discord-pin that message (legacy moderation path), if still useful |
| **Already-home eddy** | Refresh river card / re-pin if missing; do not spawn a second home for the same artifact |
| **Stop pinning** (button or explicit) | Unpin river card; clear home binding; ask fate of artifact on full dissolve (keep file vs archive) |

### Eddy vs river

- **Home conversation** lives in the **eddy**.
- **Discovery** lives on the **river** (pin card).
- Pinning does **not** mean “pin every message inside the eddy.” The eddy is the room; the river card is the door.

### Implement-chapter notes (not this doc’s job)

- Registry: `home_eddy_id` ↔ `artifact_path` (practice-root scoped).
- Rename/thread title should track the artifact’s display name when practical.
- Conflict: second `!pin` for a different doc in an eddy that already has a home → refuse or offer new eddy (prefer new eddy).

---

## Discord mapping

| Need | Platform affordance |
|------|---------------------|
| Find without searching | Pinned **message** on the river (pin tray, limit 250) |
| “Pin the eddy” | No first-class pinned-thread object → **pointer card** with jump / Continue into the thread |
| Full document body | **Open** → existing artifact presenter / `PRACTICE_WEB_BASE` browser path (§11.5.5) |
| Update during perform | Edit Tier-1 file; optional edit of pin-card subtitle (last-touched); do not paste full plan into the pin |
| Permission | Bot needs pin permission on the river (`PIN_MESSAGES` / channel setup) |

**UX checklist exception:** [review-checklist.md](../ux/review-checklist.md) item 4 (“affordance visible without pins or hidden panels”) was written to stop burying **river chrome** and entry acts in the pin tray. **Home-plan river pins are a deliberate exception**: the pin *is* the discovery surface for working documents. Implementers cite this chapter when checklist item 4 would otherwise block the card.

---

## Flows

### Offer → pin

1. Practitioner and Turtle produce a clear working document in an eddy.
2. River/Turtle offers confirm (act, not long prose).
3. On confirm: ensure artifact on disk → bind home eddy → post river pin card → `pin()` the card.
4. Ack in eddy: short, hosted-safe (“Pinned on your river — Continue anytime”).

### Continue → attune

1. Practitioner opens pin tray → Continue (or thread jump).
2. Turtle attunement packet: artifact content (or structured summary) + recent slice / latest eddy note.
3. Dialogue resumes in the home eddy.

### Perform notes

1. Practitioner states a change or question mid-plan.
2. Turtle updates the artifact quietly; one-line ack (“Noted on row 3”).
3. No confirmation modal by default (gym tempo). Dogfood may tighten.

### Revise later

Same as Continue; edits are conversational; artifact remains canonical.

### Cool / dissolve

- **Sticky:** Home eddies are exempt from idle auto-cool, **or** the thread may cool but the **river pin remains** and Continue restores/reopens the home room. Day-one preference: prefer exemption; if cool wins for hygiene, pin must stay restorable (no dead pin).
- **Dissolve:** Explicit only. Ask: keep artifact file / archive with eddy / both.

---

## Recognition tests

A week of operator dogfood succeeds if:

1. Gym visit: river pin → Continue → walk plan — **no** sidebar search for the old eddy.
2. Mid-set note lands on the **artifact** (file truth), not only in chat scroll-back.
3. Weeks-later revise uses the **same** home eddy via the same pin.
4. Turtle never claims a side-panel shelf; copy matches river pin + home eddy + file.
5. Idle cool does not leave a pin pointing at an unrestorable void.
6. `!artifacts` still finds the file (corpus browse); pin is discovery, not a second filesystem.

---

## Relation to existing surfaces

| Surface | Relation |
|---------|----------|
| `!artifacts` / Recent | Corpus inventory — complementary; not replaced |
| CE `alive.yaml` / theme `!keep` | Memory themes — different job; do not conflate with home-plan `!pin` |
| Eddy Door / welcome pin | Orientation chrome — keep; home-plan cards are additional pins with distinct copy |
| Story layer §5 “pinned alive artifacts” | This chapter **is** the day-one productization of that line (home eddy + file + river pin). Contextual date offers and “untouched” nudges stay forward |
| `!focus` | Adjacent (narrowing); home binding is stronger and durable — do not overload focus as the home registry |

---

## Spec / code touch-list (later implement chapter)

| Area | Touch |
|------|--------|
| `TURTLE_SPEC.md` | §5 river pins as working-plan doors; §8 sticky/cool; §11.5 home binding |
| `commands.py` `cmd_pin` | Product semantics above |
| Cool / archive path | Sticky or restorable pin |
| Artifact write path | Perform-mode quiet edits + ack |
| Attunement | Packet on home-eddy re-entry |
| [artifact-access.md](../ux/artifact-access.md) | Point at this chapter (pinned-alive no longer “vague future”) |
| Shake | River pin → Continue → edit artifact → pin still valid after cool policy |

---

## Non-goals (forward)

- Portable load into an arbitrary new eddy
- Side-panel / eddy floor-card “shelf” (revisit only if mobile pin tray fails dogfood)
- Multi-artifact homes
- Story-layer staleness nudges and `offer_capture` life-domain offers
- Hosted-river ship before operator recognition tests pass

---

## Status

**Design locked 2026-07-17.** Implement chapter armed: [2026-07-17-implement-pinned-home-eddies.md](2026-07-17-implement-pinned-home-eddies.md) (slices 0–7). Code not started.
