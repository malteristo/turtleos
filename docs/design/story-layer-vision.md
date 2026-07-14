# The Story Layer — Vision & Design Direction

**Date:** 2026-07-14
**Status:** Direction-setting design chapter (practice-first; spec amendment proposed separately)
**Companion:** [continuity-engine-and-substrate.md](continuity-engine-and-substrate.md) (CE design v4) — the story layer is CE's narrative complement
**Sources:** Operator user research with an early hosted practitioner (raw notes private to the operator workshop), operator marination notes, TURTLE_SPEC v2.x

---

## 1. The one-sentence vision

> **turtleOS writes the context that tells your story while you live it — one eddy at a time — and uses that story to help you in the moment.**

The payoff is **personalized wisdom**: an LLM holds enormous general knowledge; the story is precisely the context that turns that knowledge into sound judgment for *this* person, *this* week, *this* decision. Wisdom is knowledge applied — the story is what it gets applied *to*.

The emotional engine is **reading your own story while writing it**. A practitioner who can see their own week take narrative shape — threads noticed, dots connected, small things dignified by context — has an intrinsic reason to return that no reminder system provides.

---

## 2. What the research established

A user-research session with an early practitioner (neurodivergent, life-organization pain — many competing concerns, exhausting to hold, hard to structure and prioritize) validated the platform's underlying practice patterns — and inverted them:

**She independently asked for the practice patterns, without the vocabulary:**

| She asked for | The pattern |
|---|---|
| "Braindump and the AI sifts, triages, prioritizes against what it knows I care about" | Capture + triage (boom pattern) |
| "AI structures my life *for* me and presents it so I can read and react" | Prepared surfaces (self-feed pattern) |
| "It should notice the thread running under my eddies and track it once I confirm" | Alive layer + confirm gate (CE Slice 2) |
| "Fresh perspective on my situation" | Fresh-eyes pass |
| "Pick something actionable and show me what tackling it unlocks — without pressure" | Eisenhower + quest framing |
| "It should know I've talked about this several times already" | Cross-eddy continuity (CE) |
| "I'm afraid a cloud provider has all my data. It must not have a second agenda" | Local-first sovereignty |

**The inversion:** deep practice frameworks are something a practitioner *does*, with an AI partner's help. Ordinary practitioners need it *done for them* and served as **surfaces they react to**. The reaction — read, confirm, redirect, ignore — *is* their practice. This is the product: the practice patterns, run by the platform, delivered as reactable surfaces.

**The trust finding:** fear of cloud AI holding one's life is not a feature request — it is the precondition. The story layer only works if the practitioner will actually pour their life into it. Local-first is not a technical preference; it is what makes the product possible.

---

## 3. The story layer

The story layer is the narrative half of what the Continuity Engine already began. CE (design v4) senses and injects: current coordinates, alive threads, sediment retrieval. The story layer **writes prose the practitioner reads** — and CE's state is both its source and its beneficiary.

Four kinds of writing, nested (capture → process → orient at every scale):

**1. Eddy notes — the sentences.** At checkpoint, Turtle writes a short description of what the eddy held *and how it relates to the eddies around it*. A tiny eddy ("is this mole worth checking?") may carry a one-line note; its *relation* to three other health-adjacent eddies may be the part worth writing. This extends §8.4 checkpoints from mechanical capture toward relational description.

**2. Daily notes — the paragraphs.** At day's end, Turtle describes the day in the context of the last few days. The birthday-cake recipe, the party shopping list, the difficult-relative dread — connected into one legible paragraph of a life. This is where "connect the dots" lives.

**3. Period notes — the chapters.** Weekly notes in the context of recent weeks; monthly in the context of recent months; yearly in the context of recent years. Each scale reads the scale below it, not raw transcripts — bounded, composable, honest about aging out detail (CE stance: trajectory, not database).

**4. Threads — the arcs.** CE Slice 2 already specifies this: Turtle notices themes recurring across eddies, proposes them in plain language, the practitioner confirms or edits before anything is tracked. The story layer gives confirmed threads a narrative surface — the practitioner can *read their arcs*, not just have them silently injected.

**The manuscript.** All of it — eddy notes, period notes, practice artifacts — accumulates in the practitioner's practice root under git (one repo per practitioner; hosted practitioners included). Versioned, exportable, theirs. The chronicle (§6) is the event skeleton; the story layer is the flesh. A story may one day be *written from* these writings — that is the horizon, not the v1 requirement.

**The reading surface.** The artifacts viewer (§11.5) gains its most important shelf: the story. Daily and period notes are Tier-1 practitioner corpus, browsable, exportable. "Present me a structured version of my life that I can read and think about" — this is that surface.

---

## 4. Ritual flows — the practice, productized

The flow library (§10.2) gains two:

**Fresh Eyes** — Turtle reads the practitioner's story surfaces (alive threads, recent period notes) and offers a first-arrival perspective: what's moving, what's stalled, what pattern the practitioner may have normalized. Illumination, not accusation.

**Quest** — Turtle assembles an Eisenhower read from threads + confirmed intentions, picks one quest, and presents it with the *reward framing*: what tackling it would achieve, unblock, or reveal — explicitly without pressure to act now. (The no-pressure clause is law for this flow, not tone advice: practitioners for whom pressure collapses executive function are the design case.)

Both run on existing flow rails. Both are cheap. Both are visibly valuable within days of install.

---

## 5. Life artifacts — small structures, contextually offered

Practitioners accumulate structured fragments that deserve better than scroll-back: important dates, a workout plan, a document corpus for a bureaucratic form. The pattern:

- **Contextual offers, not commands.** Mid-eddy, when a date is mentioned: a River act offers "add to your dates?" One tap. (Law of Acts Not Words already governs the surface; this extends the act catalog.)
- **Image intake counts.** A screenshot of a poster is a first-class source — vision preprocessing already exists; the offer pipeline is the missing piece.
- **Pinned alive artifacts.** The workout plan lives in a pin thread *and* as a Tier-1 artifact the story layer can reference ("three weeks since the plan was touched" is a thread waiting to be noticed).
- **Life-domain corpora** (medical, administrative) are Tier-1 artifacts with obvious privacy weight — sovereign-tier only until the hosted-privacy story is proven. The prefilled-form use case (the practitioner edits rather than authors) is the north-star demo of personalized wisdom applied.

---

## 6. What this is not (boundaries held)

- **Not mood inference.** CE non-goals stand: no `low_energy`, no psychographic surveillance. Threads are *content* the practitioner confirmed, not diagnoses.
- **Not timing-aware nudging — yet.** "Remind me at 23:30 that we talked about sleep; offer to continue tomorrow's topic on my commute" is real and lovely, and it is a later act: it needs the story layer to exist before timing-aware retrieval has anything to retrieve. Deferred, explicitly.
- **Not per-channel git repos.** One repo per practitioner; surfaces are directories. The manuscript stays whole.
- **Not a framework port.** Same translation discipline as CE v4: patterns, not files. No practitioner ever sees internal vocabulary — they see their story, their threads, their quests.
- **Not cloud memory.** The story is the most intimate artifact the platform will ever hold. It lives on the practitioner's machine, under their git, full stop. Cloud models may *talk* (opt-in §8.3); they never *own memory*.

---

## 7. Relation to existing law and design

| Existing | Relation |
|---|---|
| **CE design v4** | The story layer is CE's narrative complement. Slices 0–1a shipped; Slice 2 (thread proposals + confirm) is now *also* story-layer act one. Sediment (Slice 3) gains its purpose: it's the story's long-term memory policy. |
| **TURTLE_SPEC §6.4 (Sediment, deferred)** | This vision is the missing design chapter's direction: cross-eddy memory = story layer + CE retrieval policy. |
| **§8.4 checkpoint/release** | Checkpoints are the story's raw-material harvest — eddy notes extend the existing write targets. |
| **§11.4/§11.5 practice state + artifacts** | The "MV practice surface files" design chapter (v1.1, deferred) gets its answer: the story surfaces *are* the minimum viable practice surface. Story shelves land in the existing viewer. |
| **§10 flows** | Fresh Eyes + Quest are flow-library additions under the existing front-matter contract. |
| **Hardening backlog (T0/T1)** | Not competing — load-bearing. The story layer multiplies writes to shared state, grows the practitioner corpus, and raises the cost of data loss. T1 "split-bot integrity" is the story layer's foundation slab. |

---

## 8. Act structure (near-future build map)

Ranked; each act ships practitioner-visible value. Hardening (T0 remainder → T1) proceeds as the floor beneath all of it.

**Act One — the story begins (build next):**
1. **Eddy notes with relations** — checkpoint writes a relational description per eddy. Smallest unit of story; feeds everything downstream.
2. **Daily note** — end-of-day synthesis in context of recent days. First readable story surface; the daily "connect the dots."
3. **CE Slice 2** (already designed) — thread proposals + plain-language confirm. The arcs begin.
4. **Fresh Eyes + Quest flows** — practice moves as products, on existing rails.

**Act Two — the story deepens:**
5. Weekly/monthly period notes (yearly when there's a year).
6. Story shelf in the artifacts viewer + git-versioned practitioner root.
7. Contextual life-artifact offers (dates first; image-sourced dates second).
8. CE Slice 3 (sediment) — long-memory retrieval with provenance.

**Act Three — the story acts (deferred until One + Two prove out):**
9. Timing-aware surfacing (the commute moment).
10. Life-domain corpora + prefilled-form assistance (sovereign tier).
11. Story-written-from-the-writings (the composed narrative).

**Dogfood path:** the operator's own daily use is the first test — the story layer is the reason to come back to the river. Alongside it runs a **standing user-research loop with hosted practitioners**: the operator continues inviting practitioners to the server and running research sessions as acts ship. Their reactions recalibrate the act ranking — the research that seeded this vision becomes a rhythm, not a one-off. Research observation stays consent-based: practitioners know their feedback shapes the platform; their practice content itself remains theirs (§15.5 boundaries apply — research reads the conversation *with* them, not their corpus behind their back).

---

## 9. The identity line (proposed for §3.1)

The product promise grows a sentence:

> turtleOS is a **relational** practice space: it develops shared context with you over time — writing the context that tells your story while you live it, and applying what it knows to help you in the moment. Your story stays on your hardware.

"Local AI made accessible" remains the door. The story layer is why anyone stays.

---

*Spec changes are proposed separately (see `autoresearch/proposals/2026-07-14-story-layer-spec-amendment.md`) and land only with operator sanction.*
