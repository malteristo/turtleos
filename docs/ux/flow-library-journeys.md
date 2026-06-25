# Flow library journeys (target UX)

**Status:** Target spec — **Slices 1–3 shipped** in shell (2026-06-20); Slices 4–5 pending  
**Supersedes:** river-bar `flow menu`, River modal intake (Navigator Prepare/Begin), Shelter as demo flow — **shipped 2026-06-23**
**North star:** [priority-stack.md](../priority-stack.md) · **Current shell:** [journeys.md](journeys.md) legacy section · [flows-and-intake.md](flows-and-intake.md)

---

## Product layers

| Layer | Experience |
|-------|------------|
| **Default (Layer 1)** | Sovereign **ChatGPT-style** use — install anywhere, open Discord, `new eddy`, talk to Turtle. Fine for regular daily LLM work: follow-ups, paste links, multiple threads. |
| **Optional (Layer 2)** | **Flows** — guided conversations for people who want structure. Expert process encoded; **guided emergence** without prompt engineering. |

First install and onboarding stay **generic and longer** — see [onboarding.md](onboarding.md). Flows are a short optional section at the end, not the headline.

**Navigator** is the **sample flow** for people exploring Layer 2: load it once to see what a flow is and how bootstrap + checkpoint feel. It also suits clarity work (*what do I want?* → one next step) when you choose it — not a required Day 1 path.

**Discoverability, not nagging:** flows appear in the in-eddy library picker. Turtle and River do **not** proactively offer flows (same stance as intentions-on-demand).

---

## Concepts (user-facing)

| Term | Meaning |
|------|---------|
| **Eddy** | A focused Discord thread — your private conversation room |
| **Flow** | A guided conversation program you load when you want structure |
| **Flow library** | Installed flows available from inside an eddy — intro embed at materialize, **bottom bar** after first message (native) |
| **Bootstrap** | Turtle's opening when a flow loads — connects the flow to what you already have |
| **Checkpoint** | Where a flow saved your last outcome (e.g. `state/notes/navigator-last.md`) |

Flows take **initial state** (nothing yet, prior checkpoint, current thread, a file, a URL) and run a **process** toward an **outcome** (artifact, insight, commitment, perspective shift). Same format supports **ritual eddies** (devote a thread) and **lens loads** (switch mid-conversation — see Journey 4).

---

## River vs Turtle (split)

| Actor | Role in these journeys |
|-------|------------------------|
| **River** | Materialize eddy · provisional rename · `river added turtle` · optional rename after bootstrap · chronicle |
| **Turtle** | Dialogue · flow bootstrap · conversational intake · link-read · checkpoint content |

River bar: **`[ 🌀 new eddy ]` only** — no flow menu on the river.

---

## Journey 1 — Default: open an eddy and talk

*When you have something on your mind, or you're exploring.*

```
River: click [new eddy]
  → thread card "new eddy"
  → enter thread — empty room (no orientation embed)
  → you send first message
  → river added turtle
  → thread may rename from your message (generate_topic)
  → bottom flow library bar appears (compact picker)
  → Turtle replies — open dialogue, no flow loaded
  → flow library bar **follows** new messages to the thread bottom
  → contextual offers (Save / Checkpoint) **stay** on the turn that triggered them
```

**Two chrome layers:** the flow library is standing bottom UI (always reachable). Save-to-library and checkpoint rows are situational — they appear once, next to the link or ask that earned them, and do not chase the bottom.

**What good feels like:** walking into an empty room. No modal, no orientation embed, no Turtle monologue before you speak.

**Intentions:** if you ask to attune to an intention, Turtle draws on practice files on demand — no proactive "you haven't worked on X" nudges.

→ [eddy-entry.md](eddy-entry.md)

---

## Journey 2 — Explore flows: Navigator (fresh eddy)

*Optional — try once to learn what a flow is, or when you want structured clarity → one next step.*

```
River: [new eddy] → enter empty thread
  → you open flow library → select Navigator
  → river changed the channel name: navigator   (provisional)
  → river added turtle
  → Turtle bootstrap (self-feed):
       · what Navigator is for (plain language — "find the next right step")
       · entry contract: one step, doable in a day or two
       · if navigator-last.md exists: read it, ask what happened since
       · else: short conversational interview (one question at a time)
           — "What are you working toward?" (intention)
           — "Where are you with this right now?" (territory, optional)
           — may ask for files, past eddy permalinks, or URLs if relevant
       · writes intake to state/notes/navigator-intake.md as you answer
  → dialogue continues through Navigator phases
  → optional: river renames thread after bootstrap when topic is clear
  → on checkpoint / release: navigator-last.md updated
```

**Skip setup:** if you don't want the interview, say so or use **Skip** on the picker — Turtle meets you where you are (same as `skippable: true` in front matter).

**Outcome (written down):**

```
[Date] — Working toward: [intention]. Next step: [specific thing]. Because: [why it matters].
```

**Shell trace (not Turtle voice):** `-# Navigator · continuing from last time` once before first flow reply when a checkpoint exists; `-# Navigator` on a fresh start. The model must not echo these lines.

**What this replaces:** river `flow menu` → Navigator → Prepare modal → Begin embed handoff.

---

## Journey 3 — Return visit: Navigator with checkpoint

*You’ve run Navigator before; the thread remembers via files, not Magic `@release`.*

```
[new eddy] → load Navigator
  → Turtle bootstrap reads navigator-last.md + navigator-intake.md
  → "Last time you committed to X. What happened?"
  → skips re-asking captured intake fields
  → continues from Territory / Next right thing — not Phase 1 from scratch
  → new checkpoint overwrites navigator-last.md when session ends
```

**Title:** provisional `navigator` → rename to topic after bootstrap if clear; never required to be perfect.

---

## Journey 4 — Lens load mid-conversation (target)

*Flow as thinking hat — initial state = current thread context.*

```
Eddy: you've been talking for a while (no flow, or different flow)
  → you open flow library → select Navigator (or another flow)
  → river added turtle (if not already present)
  → Turtle bootstrap:
       · summarizes what the thread already holds (self-feed from history)
       · explains how the flow will work *on this* conversation
       · interview only for gaps the flow still needs
  → NO automatic thread rename (would be confusing)
  → optional [Rename thread] button with suggested title — explicit opt-in only
  → flow process runs toward outcome using thread + any checkpoints
```

Same harness as Journey 2; difference is **bootstrap input** and **rename policy**.

**Example — Feedback:** User loads **Feedback** mid-thread when something felt good or wrong. Bootstrap pulls thread excerpt; Turtle asks only what's missing (kind, moment, worked / didn't). Outcome: structured summary for the operator — user-initiated, never prompted by River or Turtle. See [hosted-tester-program.md](hosted-tester-program.md).

---

## Journey 5 — Drop a URL in an eddy (with or without flow)

*Link-read is Tier 0; independent of flow load.*

```
Paste URL + comment in eddy (Navigator loaded or not)
  → Reading… / Read status embed
  → Turtle reply grounded in extract (with honest truncation/spill — see link-reading.md)
  → if Navigator active: URL content becomes part of territory / intention work
```

Flow bootstrap may also pull URLs already in the thread when loading mid-conversation.

→ [link-reading.md](link-reading.md)

---

## Journey 6 — Forward content to river (future)

*Not part of this chapter's implementation — listed for continuity with priority stack.*

```
Forward tweet / PDF / YouTube link to river (no eddy open)
  → River contextual offer (spawn eddy + seed context)
  → enter eddy → talk or load flow
```

Pull-only: River does not nag with flow suggestions on forwards.

---

## Title policy (all flow journeys)

| Moment | Behavior |
|--------|----------|
| Flow loaded (fresh eddy) | Provisional title = flow name or short slug |
| After bootstrap | River **may** rename to topic when confidence is high |
| Mid-conversation load | **No** auto-rename; offer explicit **[Rename thread]** only |
| Imperfect title | Acceptable — do not block UX for naming |

---

## What we are not doing (target)

| Retired / rejected | Why |
|--------------------|-----|
| **Shelter** as shipped demo flow | Blank eddy + Turtle identity already holds space; Shelter rules risk performance over presence |
| **`flow menu` on river bar** | Flow choice is intentional — belongs inside the eddy |
| **River modal intake** | Information gathering is conversational; Turtle owns interview |
| **Proactive flow offers** | Same as intentions — discoverable, user-initiated |
| **"Turtle Practice"** (user-facing) | Say **flows** / **flow library** |

---

## Acceptance mapping (when implemented)

| ID | Journey | Pass criteria |
|----|---------|---------------|
| **J1** | Open eddy and talk | Bar spawns blank eddy; first message → Turtle; no flow required |
| **J2** | Navigator fresh | In-eddy load → bootstrap → interview or skip → dialogue in flow voice |
| **J3** | Navigator return | Prior checkpoint read; no duplicate intake questions |
| **J4** | Mid-load lens | Bootstrap from thread history; no auto-rename |
| *(replaces F1–F3 Shelter)* | | Repoint shakedown to Navigator + J2/J3 |

**Verification (target):** `shake_flow.py navigator` · dogfood J2/J3 on Mini after deploy.

---

## Implementation notes (for the chapter)

| Area | Current | Target |
|------|---------|--------|
| Flow picker | `RiverFlowPickerView` on bar | In-eddy picker view |
| Intake | `flow_intake_handler.py` modal | Turtle conversational + write to intake path |
| Opening | `flow_intake_opening.py` handoff | Turtle bootstrap in `handle_dialogue` / flow load handler |
| Navigator prompt | "River already captured" CRITICAL block | "Intake loaded below" from file or interview |
| Demos / shakes | `shake_flow.py shelter` | `navigator` + J2 |
| Spec / README | Turtle Practice, Shelter in template | Flows language; Shelter removed from ship set |

**Chapter:** [2026-06-20-in-eddy-flow-library.md](../chapters/2026-06-20-in-eddy-flow-library.md) · **Onboarding:** [onboarding.md](onboarding.md)

---

*Target journeys for Mage Pop 2 dogfood. Update when shell matches or dogfood contradicts.*
