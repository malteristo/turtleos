# turtleOS UX Principles

**Status:** Living document — describes UX we **apply in the shell today**, not aspirational spec alone.  
**Canonical law:** [TURTLE_SPEC.md](../TURTLE_SPEC.md) (platform rewrite, 2026-06).  
**Use this doc when:** reviewing behavior, designing a slice, dogfooding friction, or deciding whether a change belongs in River acts vs Turtle dialogue.

When implementation and this doc disagree, **implementation wins until someone updates this doc on purpose.** When this doc and TURTLE_SPEC disagree, **propose a spec amendment** — do not silently drift.

---

## 1. How to read this document

| Layer | What it holds |
|-------|----------------|
| **Principles** | Stable intent — why the UX feels the way it does |
| **Patterns** | Concrete behaviors the shell implements now |
| **Rejected** | UX we tried or considered and explicitly do not want |
| **Review checklist** | Questions to run before merging UX-touching changes |

**Traceability:** Each pattern lists primary code paths. Spirit/Mage edits to UX should start here, then code, then (if law-level) TURTLE_SPEC.

---

## 2. Foundational principles

### 2.1 River and Turtle are different voices

The **river** is the main channel — ambient, act-only, never conversational.  
**Turtle** exists only in **eddies** (threads) — dialogue, think-aloud, tools, flows.

Practitioners should never wonder whether the river is “talking to them.” If it reads like chat, it’s wrong.

**Metaphor:** the sea in *Moana* / the casita in *Encanto* — care expressed through **acts**, not words.

### 2.2 Acts, not words (River)

River output is **structured acts** rendered as Discord-native affordances:

- Emoji / reactions (acknowledge)
- Embeds (errors, status — not chatty)
- Buttons and select menus
- Chronicle lines (structural memory)
- Discord’s own thread-list UI (thread cards)

The River model outputs JSON acts only. Prose from the River model is **rejected** by the harness.

### 2.3 Consent before spawn

Eddies never open automatically from river text alone. The practitioner **clicks** to materialize (standing bar, contextual flow button, or legacy per-message button where still wired).

### 2.4 Prefer Discord-native surfaces

When Discord already renders something well, **use it** — do not rebuild for aesthetics.

Example: thread history in the river channel uses Discord’s **default thread-list embed** (the card showing thread title, message count, and app avatar). We spawn threads from anchor messages so that UI appears naturally.

### 2.5 Visibility in the channel, not in side drawers

Affordances must live **in the timeline the practitioner is watching**.

**Rejected:** pinned “doors” or controls that only appear in Discord’s separate pinned-messages panel — easy to miss, breaks the “always at the bottom” mental model.

### 2.6 Two-bot identity (native)

When `RIVER_BOT_TOKEN` is configured:

| Bot | River channel | Eddies |
|-----|---------------|--------|
| **River** | Acts only | Creates thread anchor; no Turtle prose |
| **Turtle** | Silent | Dialogue, presence, tools |

Practitioners distinguish **who is acting** by app name and avatar. Single-bot mode is a migration fallback, not the target native UX.

### 2.7 Minimal chrome in vanilla eddies

Native eddies ship without Magic-era control panels, model pickers, or config cards on entry. The shell stays quiet until the practitioner speaks; Turtle’s first reply may be preceded by a compact presence embed.

---

## 3. River UX patterns (current)

### 3.1 Standing eddy bar (bottom anchor)

**Principle:** One persistent affordance at the **bottom** of the river timeline. Eddies accumulate above it; the control always stays last.

**Pattern:**

```
… practitioner drops …
… Discord thread cards for past eddies …
[ 🌀 new eddy ] [ flow menu ]   ← always last message
```

**On `new eddy` click:**

1. Bar message **deletes**
2. River bot posts a silent anchor message and creates a thread named **`new eddy`**
3. Discord renders the **native thread-list embed**
4. Fresh bar posts **below** the new thread card

**On `flow menu` click:**

1. Bar **edits in place** to a flow picker (select + Back)
2. Choosing a flow runs the same spawn path with `flow_id` set
3. Bar reposts at bottom after spawn

**After every practitioner river message:** the harness re-checks that the bar is still the last message; if not, it removes the stale bar and posts a new one at the bottom.

**Implementation:** `river_handler.py` — `RiverEddyBarView`, `RiverFlowPickerView`, `ensure_river_eddy_bar`, `ensure_bar_at_bottom`, `_spawn_eddy_from_anchor`.

**State:** `thread-state/river/eddy_bar.json` maps channel id → bar message id.

### 3.2 River classification acts (per message)

The River model classifies each practitioner message into acts. **Parent channel** acts today:

| Act | When | Rendered as |
|-----|------|-------------|
| `acknowledge` | Thin input (hi, emoji) | Often suppressed in render — low signal |
| `offer_flow_menu` | User asks about flows / programs | Reply with flow buttons on **that message** |
| `offer_flow` | One flow clearly named | Reply with “Open {flow}” button on **that message** |
| `error` | Degraded / parse failure | Red embed in channel |

**Not emitted in parent channel:** `offer_eddy`, `revise_offer` — materialize is the standing bar’s job.

**Implementation:** `classify_river_acts`, `finalize_parent_river_acts`, `render_acts`; prompt in `template/character/river_prompt.md`.

### 3.3 Contextual flow offers (optional)

When the River model detects flow-browse intent on a **specific message**, it may attach a **contextual** flow menu or single-flow button to that message (spawn thread from the practitioner’s message — still uses Discord thread embed).

This coexists with the standing bar: bar = always available; contextual = “you asked about flows in this drop.”

### 3.4 Chronicle

Structural events append to practice chronicle (surface + deep). Materialized eddies log with jump URLs so practitioners can walk backward along the river when sidebar threads age out.

**Implementation:** `_append_chronicle` in `river_handler.py`; spec §6.

### 3.5 Errors

River errors are **embed acts**, never apologetic chatbot paragraphs.

---

## 4. Eddy UX patterns (current)

### 4.1 Blank eddy entry (default from bar)

**Principle:** Opening an eddy should feel like walking into an empty room — no seed, no Turtle monologue, no config UI.

| Step | What the practitioner sees |
|------|----------------------------|
| Materialize | Thread titled **`new eddy`**; Discord thread card in river |
| First message | They speak first — that message **is** the opening |
| Rename | River harness retitles thread from first message content (`generate_topic`) |
| First Turtle reply | `river added turtle` system line, then dialogue |

**Implementation:** `spawn_river_eddy`, `handle_eddy_first_message`, `write_awaiting_title` / `pop_awaiting_title` in `eddy_spawn.py` + `river_handler.py`.

### 4.2 Seeded eddy (contextual / legacy)

When materializing **from a practitioner’s river message** (contextual flow button), the thread still opens as `new eddy` until first in-eddy message renames it. Legacy intake/vortex paths may post a seed embed — not the default bar path.

### 4.3 Deferred presence

`Turtle joined` posts **once**, immediately before Turtle’s **first reply** — not at thread creation.

- **Split-bot:** River adds the practitioner at materialize (`river added you`). On first in-eddy message, River adds Turtle (`river added turtle`) — same native Discord system line, no green embed.
- Turtle does not join at thread create; entry is deferred until the practitioner speaks.
- Flow context loads in the Turtle prompt; no separate flow presence embed (shell truth stays in prompt/tools, not `-#` model lines).

**Implementation:** `ensure_native_presence` in `eddy_spawn.py`; `flow_runner.flow_presence_line`; `conduct.md`.

### 4.4 Turtle dialogue shape

Inside eddies (character layer — `template/character/conduct.md`):

- One grounded opening move — not a menu, not a monologue
- Think-aloud (italic) on substantive turns; skip on trivial exchanges
- Substrate honesty — no fabricated cross-eddy memory (v1)
- No river speech, no `*stage directions*`, no therapy-speak defaults

### 4.5 Flow inside an eddy

Flows are prompt programs loaded when `context_type` / `flow_id` is set at spawn (from flow menu). Flow front matter governs reads/writes under `state/`.

---

## 5. Practitioner journeys (reference)

### 5.1 Open blank eddy from bar

```
River timeline: … → click [new eddy]
  → bar gone → thread card "new eddy" appears
  → fresh bar below
  → enter thread → first message
  → thread renames → Turtle joined → reply
```

### 5.2 Open flow eddy from bar

```
Click [flow menu] → select Shelter → same as above with flow loaded
```

### 5.3 Drop text in river (no eddy yet)

```
Practitioner posts in river
  → River acts (ack / flow offer / error only)
  → bar moves to bottom
  → practitioner uses bar or contextual button when ready
```

---

## 6. Rejected UX (do not reintroduce without explicit decision)

| Pattern | Why rejected |
|---------|----------------|
| **Pinned Eddy Door** | Discord pins live in a separate panel — not always visible |
| **Per-message Materialize on every river post** | Clutters timeline; superseded by standing bar (materialize always available at bottom) |
| **Turtle speaking in the river** | Collapses River/Turtle identity |
| **River conversational prose** | Breaks acts-not-words law |
| **Config / Spirit Control Panel on native eddy open** | Magic-era chrome; violates minimal entry |
| **“Turtle joined” before practitioner speaks** | Feels like the bot started without them |
| **Custom thread-card embeds** | Reinvent Discord’s thread list UI |
| **Auto-spawn eddy from river text** | Violates consent law |
| **Semantic routing to existing eddies (v1)** | Deferred — each materialize is a new thread |

---

## 7. Spec alignment (intentional drift)

Some TURTLE_SPEC sections predate shipped UX. **Current shell behavior:**

| TURTLE_SPEC | Spec text (summary) | Applied UX (2026-06) |
|-------------|---------------------|----------------------|
| §5.3 | Every river message includes `offer_eddy` | **Standing bar** satisfies “always offer eddy” globally; not per-message buttons |
| §5.4 | Button on each offer with inferred title | **Bar uses generic `new eddy`**; title inferred on **first in-eddy message** |
| §7.2 | “Eddy Door” blank eddy | **Eddy bar** — same blank-entry semantics, different placement |
| §17 Always Offer Eddy | Per-message affordance | **Always at bottom** via bar — amend spec when sanctioned |

When dogfooding confirms the bar model, update TURTLE_SPEC §5.3–5.4 and §17 to match.

---

## 8. UX review checklist

Before merging a change that touches practitioner-facing behavior:

1. **Voice:** Does this add prose to the river? (If yes — stop or reframe as an act.)
2. **Identity:** Which bot posts it? Should it be River or Turtle?
3. **Consent:** Does this open an eddy without a click?
4. **Surface:** Is the affordance visible in the main timeline without pins or hidden panels?
5. **Discord-native:** Are we rebuilding something Discord already renders?
6. **Entry chrome:** Does this add UI before the practitioner speaks in a new eddy?
7. **Bottom bar:** After river activity, does the eddy bar remain the last message?
8. **Failure:** On error, do we show an embed/act — not chat?
9. **Character:** Does Turtle behavior still match `conduct.md` / `soul.md`?
10. **Document:** Update this file if the principle or pattern changed.

---

## 9. Key files

| Concern | Files |
|---------|--------|
| River acts + bar | `river_handler.py`, `river_bot.py` |
| Eddy spawn + presence | `eddy_spawn.py` |
| Flow loading | `flow_runner.py`, `practice_root/flows/` |
| River model prompt | `template/character/river_prompt.md` |
| Turtle character | `template/character/soul.md`, `conduct.md` |
| Platform law | `TURTLE_SPEC.md` §5, §7, §17 |
| Shakedown | `scripts/shake_river.py`, `scripts/shake_flow.py` |
| Chapters (history) | `docs/chapters/2026-06-16-*.md` |

---

## 10. Evolution log

| Date | Change |
|------|--------|
| 2026-06-16 | Native river acts; two-bot split; Eddy Door (pinned) + blank eddy + deferred presence |
| 2026-06-17 | Shell-inject flow presence; model no longer emits operational `-#` lines |
| 2026-06-18 | **Eddy bar** replaces pinned door — bottom anchor, Discord thread embed, flow menu on bar; per-message `offer_eddy` removed from parent river |
| 2026-06-18 | Split-bot handoff fix — River `add_user` on materialize; Turtle presence embed title; no Turtle `add_user` on river eddies |

---

*This document is the resonance surface for turtleOS UX — review it when the product should feel different, not only when code changes.*
