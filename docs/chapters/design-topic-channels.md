# Design: Topic Channels

**Date:** 2026-08-04 · **revised 2026-08-05** (operator alignment: topics are channels, not thread-mode eddies) · **superseded 2026-08-17**  
**Status:** **SUPERSEDED in its surface recommendation** by [design-channel-primitives.md](design-channel-primitives.md). Do not read the "topic = channel" claim as current. The rest of this chapter is live reference — see the scope note directly below.  

> **Supersession, 2026-08-17.** The operator reversed the 08-05 alignment in a craft conversation on terminology: *"I am also not sure whether topic channels need to be entire channels or can just exist as eddies in an existing channel… a topic eddy would probably make more sense."* **A topic is an eddy that may graduate to a channel; it is not a primitive type.**
>
> **This chapter already contained the argument against itself.** § Week-N refuses a channel for the weekly rhythm and makes it a recurring eddy, and the sidebar section states the law — *"Structure is earned by recurrence"* — then exempts topics from it. The 08-17 position applies that law to topics too, which is why this is a generalization rather than a reversal of judgement.
>
> **Overturned:** the surface recommendation (topic = channel), and § The topic-channel primitive read as the *default* shape.
> **Still live and still correct, for a topic that has graduated:** the design laws, the purpose charter, the scoped-twine filter, creation paths, seeding and kind lineage, context export, lifetime/close/reopen, the nudge cadence, the sidebar layout (shipped and live), and Companion slice C (shipped). A graduated topic channel is built from this chapter.
>
> Nothing was implemented from the overturned half — this chapter's standing status was *do not implement* — so the supersession costs no code.


**Spec reference (candidate):** TURTLE_SPEC §15 (shared spaces — new topic-channel subsection), §8 (eddies inside topics are ordinary eddies), §6.2 (river acts)  
**Adjacent:** [design-family-shared-river.md](design-family-shared-river.md), [design-share-eddy.md](design-share-eddy.md), [design-admin-space-provisioning.md](design-admin-space-provisioning.md), [eddy-age-and-river-quiet.md](../design/eddy-age-and-river-quiet.md)  
**Stance:** [family-care-operating-model.md](../design/family-care-operating-model.md)  
**Origin:** Operator boom (member-made topics, alive until resolved) + field evidence: a member opened an unresolved-logistics container in the family river the same day; recurring "week N" eddies as soft topics.

> **Revision note.** The 2026-08-04 draft recommended topic = a mode of eddy/thread. Operator alignment (2026-08-05) overturned this: a topic is a **channel** — the family's co-working space for one purpose, collecting many eddies over time. The thread-mode draft's laws that survive are carried below; the surface recommendation did not.

---

## The need

Members need **co-working spaces**: a channel opened for one purpose — a concern, a project, a season — where everyone comes when they like, contributes thoughts, and Turtle uses the context the channel accumulates *in a purpose-specific way*.

Three shapes named by the operator:

1. **Concern** — "How to take a member's current overwhelm serious." Collects related eddies over weeks; the opener can ask *how am I doing?* and get an answer grounded in the channel's twine.
2. **Project/season** — a vacation channel per vacation, pre-seeded with proposed eddies for the subtopics worth talking through, informed by learnings from the previous vacation. The vacation is then planned with the channel's twine as context.
3. **Batch from conversation** — after a "week N" style session, Turtle proposes and batch-creates topic channels for the items that surfaced.

Making something a topic makes it **on everyone's mind**: the channel appears for all space members, announced by an act in the space river.

---

## The topic-channel primitive

Until now every channel was hand-shaped and unique (river, hosted-river, shared-river, craft). Topic channels are the first **repeatable** channel kind, so the primitive must be explicit:

**A topic channel is a child channel of a space, bound to a purpose.**

| Element | Definition |
|---------|------------|
| **Binding** | Registry row: `type: topic`, `space: <space-key>`, plus topic metadata. Inherits the space's members, permissions, practice root, and share policy. No new root — the space root owns all state. |
| **Purpose charter** | `<space-root>/topics/<slug>/charter.md` — why the channel exists, opened-by/when, what "no longer relevant" looks like in members' words, seed learnings it inherited. Written by Turtle from the founding conversation, confirmed at creation. |
| **Surface shape** | Same harness as a shared river: acts in the parent, dialogue in eddies, eddy bar at the floor. A topic channel is a *scoped mini-river*. |
| **Twine (scoped memory)** | The channel's accumulated context = charter + eddy notes of threads whose parent is this channel (+ optionally keyword-related space-wide notes). Thread registry already records parent channel; the topic twine is a **filter over existing story state**, not a second memory system. |
| **Attunement** | The charter shapes Turtle's stance in this channel (witness-first for a condition topic; planning for a vacation topic). Rides the existing per-channel context/attunement mechanism. |
| **Lifetime** | `status: open` until members close it. The channel exists as long as its purpose is relevant — quiet is not irrelevant. |
| **Close** | Member/operator act → harvest (essence to space story + kind-lineage learnings) → archive channel (existing archive-don't-delete machinery). |
| **Export** | Topic twine can be brought into other conversations — see § Context export. |

Everything above composes from existing mechanisms; the primitive is the *binding contract*, not a new engine.

---

## Design laws (carried + new)

1. **Member experience first.** Phone-first, zero new chores. If using a topic costs more than dumping into chat, the design failed.
2. **Say it in chat.** Create, contribute, ask, close — conversational or one tap. No settings screens.
3. **Purpose, not calendar.** The channel exists while its purpose is relevant. Quiet ≠ done. Nudges are ignorable (see law 6).
4. **Owning space = owning audience.** A family topic is visible to family members, nobody else. Topic content is space content — the space's share policy governs export.
5. **Witness before intake.** Topics about a member's condition open with what has already been heard, never a request that they define or log further.
6. **Nudge, never nag.** The river bot may post "close this channel?" into the topic channel at wide intervals when it has gone long-quiet. Ignoring it is a valid answer that costs nothing and delays the next nudge.
7. **Creation is announced.** A new topic posts an act in the space river — that's what "on everyone's mind" means mechanically.
8. **Care before operations.** A topic is a held concern/purpose, not a task list assigned to anyone.

---

## Creation paths

| Path | Who | Flow |
|------|-----|------|
| **From chat** | Any space member | "Make this a topic" (in river or inside an eddy) → Turtle drafts charter from the conversation → confirm card (title, purpose, who will see it) → channel created, act posted. |
| **Turtle offer** | Turtle | When an unresolved-purpose shape is clear, one Keep-style offer: "Keep this as a topic channel?" Once per concern; declining is calibration. |
| **Batch after session** | Turtle | After a week-N style session: "These came up — create topic channels for: A, B, C?" One confirm, N channels, N charters. |
| **Typed** | Practitioners | `!topic create <title>` · `!topics` lists open topics in the space. |
| **Seeded (kind lineage)** | Member or Turtle | "Open a vacation channel" → charter + proposed eddies seeded from the prior vacation topic's harvest. |

**Permission decision:** member-created channels are new — today only the operator creates channels (`!admin space create`). Recommendation: any **space member** may create a topic *within their space* (confirm card + river act as the transparency guard); the operator retains close/archive authority. The blast radius is a channel their family already sees.

---

## Seeding & kind lineage

For repeatable topics (vacations, weeks): when a topic closes, its harvest writes learnings to `<space-root>/topics/_lineage/<kind>.md` ("what we learned planning the last vacation"). A new topic of the same kind seeds its charter and **proposed eddies** from that lineage — posted as tappable offers in the fresh channel (reuse proposed-themes + blank-eddy spawn), not auto-opened threads.

v1 keeps kinds light: `kind` is a free string on the charter; lineage is one file per kind. No taxonomy, no rule engine.

---

## Context export (topic twine elsewhere)

Two directions, both consent-shaped:

1. **Share out** — extend the Share primitive (§15.6) with a **topic source**: from a topic channel, `!share` exports a twine digest (charter + recent eddy essences) to a practitioner or another space, same digest-first UX and transparency acts as Share eddy. Boundary: governed by the space's share policy; a member sharing family-topic twine into their own private river is fine (it is their space's content and their river); sharing to a non-member is not offered.
2. **Pull in** — in any conversation, a member asks "bring in the vacation topic" → Turtle loads the topic twine digest into that conversation's context, with a one-line transparency note of what was loaded. Only topics of spaces the asker belongs to.

"How am I doing?" needs no export at all: asked inside the topic channel, Turtle answers from the charter (what the opener wanted) + the scoped twine (what has actually happened) — the purpose-specific use of channel context is the charter's job.

---

## Lifetime & close

- `status: open | closed` in registry + charter.
- **Nudge:** long-quiet open topics may receive an in-channel "close this channel?" act (wide cadence, e.g. not before weeks of silence; each ignore/decline pushes the next one further out). Never in a member's private river, never as a demand.
- **Close:** member says so (or taps the nudge) → confirm → harvest: essence to space story, learnings to kind lineage → channel archived (locked/moved per existing archive machinery), registry row marked. History remains readable.
- **Reopen:** archived topics can be reopened (registry flip + unarchive) — cheaper than perfect close judgment.

---

## What exists vs what must be built

| Piece | Exists | Needed |
|-------|--------|--------|
| Channel creation (Discord + registry, atomic) | `space_provisioning.py` (operator, space+channel pair) | Factor into a topic-channel path: child-of-space, member-invokable with confirm, no new root |
| Channel types & routing | `river`/`hosted-river`/`shared-river`/`craft` in `mage.py`, river iteration, eddy bar deploy | New `topic` type included in river-surface iteration, bar deploy, rejoin |
| Per-channel memory | `render_scope_block` reads whole-root eddy notes | Parent-channel filter (thread registry has `parent_channel`) + charter injection |
| Purpose charter | — | New: `topics/<slug>/charter.md`, drafted by Turtle at creation, confirm flow |
| Per-channel attunement | Channel attunement override + `default_context` mechanism | Charter-driven stance wiring for topic channels |
| Proposed-eddy seeding | Proposed-themes machinery, blank-eddy spawn, flow offers | Seed-offer cards on topic creation; lineage read |
| Kind lineage | — | New: harvest-to-lineage on close; seed-from-lineage on create (one file per kind) |
| Batch creation | — | New: post-session offer listing N candidates, one confirm |
| Close/archive | Space close machinery (archive, lock, registry) | Adapt for single channel; harvest step; reopen path |
| Nudges | Scheduled per-root loops (daily-note heartbeat pattern) | Quiet-detection + wide-cadence nudge act with backoff on ignore |
| Context export | Share eddy (digest bundle, picker, transparency acts) | Topic source for Share; "pull in" loader with transparency note |
| Spec | §15 shared spaces | New topic-channel subsection (grill-first: after destination sanction) |

Rough shape: 3–4 bounded slices — (1) primitive + chat creation + charter + scoped twine, (2) seeding + batch + lineage, (3) close/nudge/reopen, (4) export (Share topic + pull-in). Slice 1 alone delivers the condition topic and the mental-clutter promotion.

---

## Not in first slice

- Discord Forum channels / category taxonomy
- Auto-create without confirm
- Cross-space topics
- Dashboard/console create flow
- Task semantics (owners, due dates)
- Kids as topic members
- Spec amendment before destination sanction

**The deferred half:** *Cross-space topics* and *kids as topic members* are both membership questions, and topics inherit space membership wholesale precisely because no relation model exists. That model is now designed — [relations-and-membership.md](../design/relations-and-membership.md) — and its slice 3 (kin space, member directory, relation-scoped topic invitations) is where these two items come back. Slice 1 needs nothing from it; the moment a topic must be visible to *some* of a wider family, it does.

---

## Companion slice C — shared-river announcements (**shipped 2026-08-05**)

**Finding (2026-08-04):** `announcements.py` fanout targeted `river` + `hosted-river` only. Family-care ships could miss the shared room where the need was expressed.

**Shipped:** front-matter `audience: shared` includes active `shared-river` channels in fanout; space-level registry `locale` resolves the copy (family room gets `de`). Detail in [design-update-announcements.md](design-update-announcements.md) § Amendment implemented. `2026-08-04-family-dates` tagged and delivered to the family river. Future family-care announcements (topics, fridge, Barometer) tag themselves. When topic channels exist, extending eligibility to type `topic` is a one-line audience addition.

---

## Decided (operator alignment, 2026-08-05)

1. **Member creation authority** — any space member creates topics in their space, from wherever they are, via confirm + river act. Operator keeps close/archive authority.
2. **Channel shape** — scoped mini-rivers: acts in parent, dialogue in eddies.
3. **Nudge cadence** — first "close this channel?" after ~3 weeks of silence; backoff ×2 per ignore.

---

## Sidebar & information architecture

**Context:** the server currently has no categories — a flat channel list. Permissions already scope each member's sidebar (a non-operator family member sees only their own river + family channels), so the sidebar taxonomy mostly serves the operator's view and the family category's internal order.

**Organize by purpose, not provenance.** Creator-based categories ("created by me / by member X") were considered and set aside: members find channels by what they're *about*, not by who opened them, and creator categories multiply as membership grows. Provenance lives where it's cheap and visible:

- the **channel topic line** (`opened by <member> · <purpose one-liner>`) — set at creation, visible on tap;
- the **charter** (`opened_by`);
- the **creation act** in the space river.

**Recommended layout (minimal, grows only when earned):**

```
RIVERS
  #river            (operator)
  #river-<member>   (each hosted/member river)
CRAFT
  #craft-turtle     (operator-only development surface)
FAMILY
  #family           (the shared river — stays the front door)
  #<topic>          (member-created topic channels, below the river)
```

Three categories. Rivers on top — system-provisioned conversation surfaces. **Craft** is the operator-only development shelf (not a river, not family). FAMILY holds member-made structure. Within FAMILY, `#family` holds position 0; topics sort alphabetically (Discord has no activity-sort for text channels; at family scale manual order is moot). Topic creation assigns `parent_id` to the space's category — one line in the create path.

**The family river does not split.** Operations / care / outfacing are the *operator's* lenses (they mirror the workshop's intention vocabulary), not the family's. Standing sub-channels would fragment the timeline and add a "where do I post this?" tax — the exact failure law 1 names. Care/ops/outfacing remain routing bins Turtle applies to what lands in the one river; topic channels are the only member-visible structure, and they label themselves by purpose at creation.

**Structure is earned by recurrence.** No standing structural channel (operations, care, etc.) until a purpose recurs hard enough that members keep reopening topics for it — then that purpose has earned a standing channel, and the registry shape above already accommodates it.

---

## Week-N

**A recurring eddy in the family river — not a channel, not a category.** Weeks are rhythm, not purpose; a channel per week is churn and archive noise, and a standing "operations" channel to host it is structure ahead of need (above).

Shape: Turtle seeds the week eddy on a schedule or on ask ("week #32") with a light two-beat charter — *review last week · plan the next* — reading the prior week eddy's note for continuity (story layer already provides this). Unresolved items surface as **batch topic-creation offers** at the eddy's close: the week eddy is the topic factory, not a topic itself. If the weekly ritual earns permanence, the pinned-home-eddy machinery (design-pinned-home-eddies) can pin it — still no new channel.

---

## Decided (operator alignment, 2026-08-05 — second pass)

4. **Sidebar layout adopted and live** (2026-08-05): categories `Rivers` and `Family` created on the server (ids in the operator's local connection notes); channels moved with per-channel permission overwrites intact (verified). Rivers above Family.
5. **Week-eddy seeding** — on-ask until the rhythm proves itself, then schedule.
6. **Family channel does not split**; operations/care/outfacing stay Turtle-side routing lenses. Structure earned by recurrence.

**Amended 2026-08-07:** third category **Craft** added; `#craft-turtle` moved out of Rivers. Order: Rivers → Craft → Family. Craft is operator-only (permission overwrites unchanged).

**Implementation note for slice 1:** `space_provisioning.py` currently looks for a category named "Practice" (which does not exist — new channels land uncategorized). The topic-create path must resolve the owning space's category (record `category_id` on the space registry entry, or resolve by name) so topics land under `Family` automatically; fix the provisioning default in the same pass.

---

## Verification expectations (when implementing)

TDD per slice: registry round-trip; creation idempotency; twine filter (family-root eddies from other channels do not leak into a topic twine unless keyword-related by design); charter injection; close/reopen; nudge backoff; share-out respects space policy. Suite green via `./scripts/spirit_verify.sh`. `shake_topics.py` before family dogfood (do not repeat the dates shake miss).
