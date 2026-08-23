# What a Shared Room Remembers

> **Supersedes** [`carried-context-and-the-confirm-moment.md`](carried-context-and-the-confirm-moment.md) **§4–§5** (confirm-at-re-entry; attributed standing threads). That note's §1–§3 — the finding, why wiring the idle path to the existing gate fails, and the split between a recency pointer and an ongoing claim — stand unchanged and are the reason this document exists.
>
> **Companion:** [provenance-guard.md](provenance-guard.md) — INT-041 moves from a later slice to this design's **prerequisite**. See §6.
>
> **Companion:** [story-layer-vision.md](story-layer-vision.md) §3 — eddy notes as "the sentences". This is what finally *reads* them.

**Status:** **As built 2026-07-29** (`bd648fc`, `ed77360`) — see §4a. Not yet live; awaiting a restart.
**Date:** 2026-07-29
**Spec trace:** TURTLE_SPEC §6.5 (story surfaces), §7.1 (CE composition), §8.4 (checkpoint), §15.5
**Origin:** Operator challenge on Anvil, 2026-07-29 — *"I have difficulties thinking through how this feature should work, and I want to treat this as signal."*

---

## 1. Why this revision exists

The operator could not think the confirm design through, and treated that as signal rather than as his own failing. It was signal. The design had folded two different problems into one mechanism:

| | Problem | Whose | State |
|---|---|---|---|
| **P1** | The room does not remember what it has been about | the other member's, felt directly | **unsolved** |
| **P2** | The room's memory may put words in someone's mouth and calcify | the operator's | **fix was in the wrong layer** |

A consent gate is a plausible answer to P2 — *have a human approve it*. But adopting consent imports its whole dependency chain: who consents, on whose behalf, what happens when one member confirms something the other never saw. **The audience-cardinality question was not a property of the problem. It was a property of the solution.** That is precisely why it resisted thinking: it answers a question the practice never asked.

## 2. The assumption chain

Four assumptions, each inherited rather than derived:

1. Memory is **standing curated state** (`alive.yaml`) ← load-bearing
2. The unit of memory is a **confirmed theme**
3. Nothing carries **unconfirmed**
4. Therefore: **who confirms**, in a room of two?

Strike (1) and 2–4 evaporate.

(1) arrived from **CE Slice 2, which was designed for a solo practitioner** — where consent costs one tap, the referent is stable, and there is no second person to ventriloquize. It was carried into a shared space without being re-derived there. Every subsequent difficulty was the cost of that unexamined move.

## 3. Consent does not buy accuracy

Worth stating plainly, because it was the design's central claim and it does not hold.

Pressing **Keep these** on a three-word label does not verify that the synthesis beneath it was faithful to what anyone actually said. It signs off on a label. The guarantee is weak; the interaction cost is high; and the cost lands on exactly the practitioners the platform exists to unburden — the design case is someone for whom pressure collapses executive function ([story-layer-vision.md](story-layer-vision.md) §4).

A gate that asks a human to underwrite a machine's synthesis, without showing them the synthesis, is theatre with a consent form attached.

## 4. The design: retrieve, do not curate

**The room already has a memory. Nothing reads it.**

There are 46 eddy note entries in the family root — each dated, topic-tagged, and (since the witness fix) attributed. They are written on every checkpoint and consumed by nothing at conversation time. The bug is **write-only memory**, not absent memory.

So: at turn time, compose the room's context by reading its own recent eddy notes. Recency-bounded, capped, regenerated every turn. Nothing promoted, nothing standing, nobody asked anything.

### Mechanism

| | |
|---|---|
| **Source** | `story/eddies/*.md`, via the existing `parse_eddy_file_entries` / `EddyEntry` parser |
| **Window** | entries from the last N days (start: 7), most recent first |
| **Cap** | M entries (start: 5) and a char budget (start: ~5K) |
| **Exclusion** | **the current eddy's own note** — that conversation is already in the prompt as history; what is missing is *cross-eddy* memory |
| **Content** | the entry's `held` opening sentences + its `related-topics`, as written |
| **Attribution** | inherited from the note, not recomputed — post-fix notes already name who said what |
| **Hook** | alongside the CE substrate packet in `dialogue_turn`, as a sibling renderer |

### What falls out for free

- **Zero member decisions.** Not a simpler question — no question.
- **Attribution costs nothing.** The notes are already in witness voice; retrieval carries "Kermit said / the hosted practitioner said" with it. No `confirmed_by`, no cardinality branch, no name-space work beyond §6.1 which is already done.
- **Calcification is structurally impossible.** Calcification is a property of *promotion into standing state*. With no promotion there is nothing to calcify. A topic that stops appearing in notes stops being surfaced — memory decays by itself, which is exactly what `eddy-age-and-river-quiet.md` already argues eddies should do.
- **Bad syntheses self-correct.** One wrong note is diluted by its neighbours and ages out of the window, instead of being crowned permanent truth by a button press.
- **It dissolves the 42-entry question.** The pre-fix, collapsed-voice entries simply never enter a window bounded to recent attributed notes. They remain as history, surfaced by nothing. No decision required of the operator, and none required of the member whose voice was collapsed.
- **No solo/shared branch.** The same mechanism serves a personal river (second-person notes) and a shared space (witness notes) without a cardinality test. The voice was already resolved one layer down, at write time.

### Cost

~1.8KB per note × 5 ≈ 9KB per turn, the same order as the packet already injects. Cacheable by directory mtime if it proves hot.

## 4a. As built — the reader already existed

§4 said to add retrieval "alongside the CE substrate packet, as a sibling renderer." That was wrong in an instructive way: **there was no need for a sibling.**

`render_scope_block` already pulled practice files into turn-time context, ranked them by keyword, and degraded honestly when it found nothing. It had two defects, neither of them missing capability:

1. It read `sessions/*.md` — a genre retired 2026-07-15. Newest session note in the family root: **April 11**. In the hosted practitioner's: **March 26**.
2. It ran only when `scope` was set, i.e. only under `!focus` — a command that, across five practice roots and four weeks, **has never been used**. `scopes.yaml` exists in one root and contains `eddies: {}`.

A working reader, aimed at a dead corpus, switched off by default, while the live corpus accumulated beside it. So the build was: repoint the source, delete the gate.

| | As built |
|---|---|
| **Source** | `story/eddies/*.md` via `collect_recent_eddy_entries` |
| **Trigger** | **unconditional** — every turn. `scope` now *narrows* what is already there instead of switching it on |
| **Window** | 7 days |
| **Cap** | 5 entries, ~5K chars |
| **Diversity** | **1 entry per eddy** — the last five *conversations*, not the last five checkpoints |
| **Exclusion** | the current eddy, passed as `current_thread` from `dialogue_turn` |
| **Content** | body excerpt + `proposed-themes` |
| **Thin case** | names what it *cannot* see, not just what it lacks — §6's refusal, in the sentence already in the right place |

**On `proposed-themes`:** `related-topics` is the field the schema advertises for topical linking and it is empty in **all 46** family entries. `proposed-themes` is populated in **all 46**, written on every checkpoint, and was read by nothing. It is now what the entries are labelled with. A fifth write-only artifact, found by asking what already exists.

**The diversity cap came from the first render, not from theory.** Against the live family corpus the flat recency window returned the same eddy twice and the room appeared to remember only its loudest week. One entry per thread restored the birthday plan to a room whose week was otherwise a marital conflict.

**`!focus` is not retired yet, deliberately.** Nobody reaches for it and room memory replaces its purpose, but removing a fallback in the same change that replaces it is how you end up with neither. One dogfood cycle, then retire.

## 5. What this supersedes, and what stands

| Slice | Was | Now |
|---|---|---|
| 1 — suppress ungated carry in shared roots | shipped `85c0370` | **stands** — it removed one unconfirmed line pretending to be the room's memory |
| 2 — checkpoint line ages honestly | shipped `5ed8f7a` | **stands** — independent of all this; a recency pointer is still a recency pointer |
| 3 — `confirmed_by` + attributed rendering | shipped `5ed8f7a` | **demoted, not reverted.** Correct for anything confirmed manually via `!checkpoint`, and harmless. It is **no longer the foundation of shared memory**; it was built as that, and the better design does not need it. |
| 4 — confirm-at-re-entry | designed | **dropped.** Replaced by §4 above. |

Slice 3 is named as design momentum rather than requirement. It was built because the shape it belonged to had not yet been questioned. Leaving it in place is cheaper than reverting it and it does no harm; new work should not build on it.

## 6. P2 belongs to the honesty gates

The fear of Turtle ventriloquizing a member is an **accuracy problem in the synthesis**, not a consent problem in the carry. Its proper home is INT-041 — generation-layer refusal for unreachable spaces, and the assertion/testimony split so Turtle's own claims are never recorded as a practitioner's words.

Consent-on-carry was treating bad synthesis by asking a human to sign it. The correct order is: **make the synthesis honest, then let carry be automatic and boring.**

This reorders the backlog. **INT-041 stops being a later slice and becomes this design's prerequisite** — retrieval amplifies whatever the notes contain, so the notes must be trustworthy before anything reads them at turn time.

## 7. Revised sequencing

| | Slice | State |
|---|---|---|
| 1–3 | containment, ageing, attribution schema | ✅ shipped 2026-07-29 |
| **4** | **INT-041** — source-claim refusal + assertion/testimony split | **prerequisite** |
| 5 | Room memory by retrieval (§4 above) | after 4 |
| 6 | INT-046 root-blind scheduler → per-member daily dogfood | after 5 |
| 7 | Widened §6.5 amendment — now describing retrieval, not consent | last |

The §6.5 amendment must not be sanctioned describing the confirm design. Its "nothing carries unconfirmed" clause was drafted from the superseded shape and would write a discarded mechanism into law.

## 8. Open, and what would falsify this

- **Transition window.** Only 4 of 46 family entries are post-fix. A window bounded to attributed notes leaves the room cold for several days while the corpus turns over. Judged the right trade — cold and honest beats warm and ventriloquized — but it means the frustration that started this does not resolve immediately, and that should be said out loud rather than discovered.
- **Recital risk.** More injected content is more surface for the model to recite back. The existing conduct line ("surface these only when they serve the reply, never as a recital") is the mitigation; if it proves insufficient, the fix is prompt-side, not a return to curation.
- **Window and cap are guesses.** 7 days / 5 entries / 5K chars are starting values, not findings. Dogfood should move them.
- **What would falsify the whole approach:** if retrieved notes turn out to be too noisy to be useful without curation — i.e. if the room's memory needs *selection* rather than *recency* to be legible. That is a real possibility for a busy space. The answer then is better ranking (topic overlap with the current eddy), **not** a human gate.
  - *Partially fired on day one, and the answer held.* The failure was monotony rather than noise — one loud conversation filling the window. Fixed by a deterministic per-eddy cap, no gate. The prism was considered as a ranker and rejected: it answers a different question (route this message to one eddy, or NEW) with a model call and a timeout, and putting that on every turn buys latency for the wrong answer.
- **INT-041's second half is now load-bearing at turn time.** Retrieval reads eddy notes, and eddy notes still cannot distinguish *Turtle asserted this* from *the practitioner said this*. A live note in the hosted river reads *"a previous error in perspective had mistaken you for someone else"* — Turtle's own invention, recorded agentlessly, and now recited into every turn in that room. The refusal half of INT-041 shipped with this design (the thin-case line names unreachable spaces). The assertion/testimony split did not, and it is the next thing that limits this design's quality.

## 8a. Retrieval is the room's only reader (2026-07-29)

Same day, one layer over: the communal daily note was also write-only — synthesized every day into the space root and posted nowhere, because shared roots resolve to no owning river. The per-member note had been built to carry the space's day to its members and inverted whose day it was telling (INT-048).

The operator's decision: **do not deliver either.** The communal record stays on disk as the space's record; per-member notes stay withheld; nothing is posted into the space. Continuity in a shared room comes from retrieval at turn time and from nothing else.

This sharpens §4 rather than changing it. The window reads `story/eddies/*.md` — **not** the dailies, deliberately. A daily is a synthesis of the same eddies; admitting both would double-count the material and re-open the synthesized-artifact-as-memory path this design exists to close. Primary material, not the summary of it.

See [per-member-periodic-notes.md](per-member-periodic-notes.md) §Delivery withdrawn for the full trace.

## 9. What this does not do

- **Not a replacement for `!focus`.** Deliberate narrowing to one thread already exists (`scopes.yaml`) and stays practitioner-initiated. Retrieval is ambient; focus is chosen.
- **Not cross-root.** A room's memory is its own notes. Nothing reads another root, ever (§15.5, charter §3.2).
- **Not mood or state inference.** Retrieval surfaces what was written, attributed, and nothing else.
- **Not permanent.** Nothing retrieved becomes state. If it is not in the window, it is not in the room.

---

*The room was never missing a memory. It was missing a reader — and we nearly built a consent form instead of one.*
