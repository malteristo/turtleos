# Channel Twine & Communal Memory

> **Companion:** [continuity-engine-and-substrate.md](continuity-engine-and-substrate.md) — the CE gives one river its continuity; this document extends the same pattern to shared spaces. See CE §3.2 item 5, which already names the one-way `shared space → private practice` cue; this charter generalizes that seam into a governed, bidirectional crossing law.

**Status:** Draft v1 — design charter, pre-implementation
**Date:** 2026-07-19
**Spec trace:** TURTLE_SPEC §15.4–15.6 (multi-practitioner topologies, data flow, multi-server), §6 (eddy model), §8.4 (checkpoint), §16 (practice state)
**Origin:** Operator strategy dialogue on Forge (2026-07-19); recipe-book eddy as first live communal artifact

---

## 1. Purpose

turtleOS is developing toward a **community AI operating system**: each practitioner has their own river; a community of practitioners meets in shared spaces on one node. The mission in one line:

> **Enable understanding in an individual and shared meaning-making in a community.**

The Continuity Engine answers the first half for a single river. This charter frames the second half: what memory a *shared space* has, and who governs it.

A human–AI dyad is a community of one. On a shared community node, the dyads intertwine. This document is about what "intertwine" means precisely.

---

## 2. The core claim: twine is fractal

A practitioner's twine is already layered (eddy notes → daily notes → chapters). The same pattern extends upward:

| Scale | Space | Twine |
|-------|-------|-------|
| Thread | eddy | eddy notes / checkpoint residue |
| Practitioner | river | river twine (CE: current, alive, scopes) |
| Shared purpose | channel (shared space) | **channel twine** |
| Community | server / node | community twine (aggregate of channel twines + node story) |

A channel is structurally a purpose-crafted river: it warrants its own continuity tracking, its own current/alive layers, its own story sediment. **The CE engineering largely transfers.** That is the good news, and roughly 80% of the work.

## 3. The hard 20%: ownership semantics differ

A river twine has **one sovereign**. The practitioner owns it; consent is bilateral within the dyad. A channel twine is memory of a ***between*** — and the between belongs to no single member. Same data structures, fundamentally different authority. Three governance problems fall out:

### 3.1 Authority

Who may revise, correct, or dissolve entries in a channel twine? Who can say "forget that"?

**Working stance:** *Turtle proposes, members sanction* — the proposal pattern already proven in single-practitioner self-development (TURTLE_SPEC §20), extended to multi-party spaces. No silent rewrites of shared memory.

The twine must also be able to **hold disagreement without flattening it**: "member A remembers it this way; member B that way" is a recordable state, not an error to resolve. Productive irresolution as a data-structure property. This is the immune function against a community's shared blind spot: a communal memory that only harmonizes will calcify consensus.

### 3.2 Crossing law

What of a river twine may inform a shared space, and what of a channel twine flows back into member rivers?

TURTLE_SPEC §15.5 currently isolates: nothing crosses. That is the correct *default*, but shared meaning-making often depends on personal context — a shared space serves better when it knows what a member has chosen to let it know. The crossing must be **granted at the source, per item, by its sovereign** — never inferred, never filtered after the fact.

This is the third independent occurrence of the same control primitive in turtleOS design (after outfacing clearance and routing guards):

> **Clearance as routing:** *"where may this resonance surface?"* — decided at the source, enforced at the boundary.

When the same control appears three times independently, it is a **platform primitive**, not a feature. The crossing law should be specified once and instantiated per boundary:

- **river → channel:** member-granted clearance (explicit, revocable, per item or per scope)
- **channel → river:** default-open for members (shared content is already known to them), relevance-routed by the member's own CE
- **channel → outside node:** governed by outfacing clearance (same primitive, next boundary out)

### 3.3 Perspective

A channel twine is written from whose viewpoint? A community's shared story is not the sum of individual stories.

**Working stance:** Turtle writes as **witness, not arbiter** — a neutral narrating voice that attributes perspectives to their holders and records convergence when it genuinely happens. And the reframe that anchors this charter:

> The channel twine is not infrastructure *that enables* shared meaning-making. **The channel twine *is* the shared meaning, co-authored.**

A shared artifact (e.g. a family's living recipe book) is not stored *in* communal memory; it is a strand *of* it.

---

## 4. Non-goals

- **No psychographic modeling of members** — the channel twine records what happened in the space, not inferred member psychology.
- **No implicit river mining** — nothing personal enters a shared space without source-granted clearance, ever. Fail closed.
- **No majority-overwrites-memory** — sanction protects entries; disagreement is held, not voted away.
- **No engagement mechanics** — the twine serves meaning, not activity metrics.

---

## 5. Open questions

1. **Granularity of clearance** — per item, per scope/theme, or per standing grant? (Standing grants risk consent fatigue in reverse: over-broad early grants forgotten later. Revocability and visibility are load-bearing.)
2. **Channel CE cost** — per-channel current/alive layers multiply background inference; which layers earn their place at channel scale for v1?
3. **Community twine** — is node-scale twine a real layer for v1, or an aggregate view over channel twines until proven needed?
4. **Member departure** — when a member leaves a space, what happens to twine entries that carry their clearance? (Working instinct: grants are revocable; witness record of shared events persists; personal-context strands are withdrawn.)
5. **Operator role** — the operator administers the space but must not thereby own the between. Where does operator authority end and member sanction begin?

---

## 6. Relation to existing design

| Artifact | Relation |
|----------|----------|
| CE & substrate (this folder) | Channel twine reuses CE layer model; CE §3.2.5's one-way cue becomes one instance of the crossing law |
| TURTLE_SPEC §15.4–15.6 | Isolation law stands as the default; this charter adds the governed exception path |
| Alive-thread vs artifact chapter | Shared artifacts are channel-twine strands; that design folds in here at community scale |
| Story layer vision | Channel dailies / node story are the story layer at shared scale |

*Charter only — no implementation is sanctioned by this document. Next step when gravity returns: pick the smallest live shared space and give it the thinnest possible channel twine (witness notes + member-sanctioned corrections), before any crossing law is implemented.*
