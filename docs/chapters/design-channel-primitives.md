# Design: Channel Primitives

**Date:** 2026-08-17
**Status:** Specification — decisions below are marked `decided` / `open` / `contradicts-prior`. **Open cells stay open.** Filling one with prose is a defect, not a completion.
**Spec reference (candidate):** TURTLE_SPEC §15 (shared spaces), §8 (eddies), §7.4 (attunement), §6.2 (river acts)
**Supersedes:** [design-topic-channels.md](design-topic-channels.md) — its surface recommendation only; see § The overturn.
**Origin:** an operator craft conversation on consistent terminology for users, 2026-08-16 – 2026-08-17. Target condition confirmed by the operator, revised once, direction held.

---

## What a channel primitive is

Until now every channel in turtleOS was hand-shaped: `river`, `hosted-river`, `shared-river`, `craft` exist as registry type strings with behaviour scattered across the modules that read them. A **channel primitive** is the binding contract that makes a channel kind repeatable — so a household that is not the operator's can choose one, or craft one, without reading Python.

**A primitive bundles three things that are currently specified in three different places, or not at all:**

| Component | What it declares |
|-----------|------------------|
| **Channel** | structure, membership rules, visibility boundaries |
| **Turtle** | attunement, memory scope, care orientation |
| **River** | posture, initiative level, which acts it offers |

**Each is described on four dimensions** — the shape the operator named on 2026-08-16 08:01:

- **Scope** — who it cares about (one person, a household, a team)
- **Attunement** — what it pays attention to (personal practice, shared rhythms, project delivery)
- **Memory boundary** — what it can see (private root, shared root, twine access)
- **Default posture** — how it initiates versus responds (ambient or summoned, reflective or operational)

The primitive is the contract, not a new engine. Everything below composes from mechanisms that already exist, except where a row says otherwise.

---

## The two axes, and the thing that is not an axis

**Relational primitives** are defined by membership and social structure: `private`, `family`, `wohngruppe`, `team`.

**Thematic primitives** are defined by domain and practice mode: `craft`, and plausibly `learning`, `creative`, `health`, `financial`.

`craft` is what makes the second axis necessary rather than decorative. It has the same membership shape as `private` — one practitioner — and a completely different Turtle attunement and River posture. Same scope, different activity. A taxonomy with only a relational axis cannot express it, which is why the live system has a `craft` channel type sitting awkwardly beside three membership types.

**Topics are not a third axis.** A topic is a subject scope, and a subject scope is what an eddy already is: something that spins off the flow, runs its course, and either dissolves or is checkpointed as sediment. A topic becomes a *channel* only when its volume earns one. See § The overturn and the graduation test.

---

## The overturn

`design-topic-channels.md` was revised 2026-08-05 with the note *"operator alignment: topics are channels, not thread-mode eddies."* On 2026-08-17 the operator reversed it: *"I am also not sure whether topic channels need to be entire channels or can just exist as eddies in an existing channel... a topic eddy would probably make more sense."*

**This is a generalization, not a contradiction — and the earlier document is where the argument for the reversal already lived.** Its own § Week-N section refused a channel for the weekly rhythm and made it a recurring eddy. Its own law reads *"Structure is earned by recurrence. No standing structural channel until a purpose recurs hard enough that members keep reopening topics for it."* The 08-05 alignment stated that rule and then exempted topics from it. The 08-17 position applies it to topics too.

**What that means for the old document:** its surface recommendation (topic = channel) is superseded. Its laws, its charter design, its scoped-twine filter, its close/reopen machinery and its sidebar layout are **not** — they describe a graduated topic channel correctly, and most of them describe a topic eddy correctly too. Nothing was implemented from it (`do not implement` was its standing status), so the supersession costs no code.

---

## Decision table

One row per load-bearing claim. `Observable` is what someone could check. `Enforced by` names the module or test that fails when the claim stops being true — or says *decided not to* with the reason, which is a different thing from *never got to*.

### Structure

| # | Claim | Status | Observable | Enforced by |
|---|-------|--------|-----------|-------------|
| S1 | A channel primitive bundles Channel + Turtle + River as one named unit | **decided** | a primitive is nameable in one registry field; nothing needs three fields to say `family` | **not yet** — registry today has `type` for the channel and `attunement` for Turtle, and nothing for River |
| S2 | Primitives divide on two axes: relational (who) and thematic (what mode) | **decided** | `craft` and `private` share a scope and differ in attunement; a taxonomy that cannot say this is wrong | **not yet** |
| S3 | Shipped defaults are **atomic** — `family` works out of the box without composition | **decided** | choosing `family` requires zero further choices | **not yet** |
| S4 | Relational × thematic composition (a `family` × `learning` channel) is an advanced crafting move | **open** — *decided not to ship in v1.* The operator named it as more powerful and more complex to craft and explain; atomic wins for defaults. The reason it is open rather than closed: nothing yet says how an overlay resolves a conflict between the two parents' postures. | — | *decided not to* |
| S5 | Crafting a new primitive means specifying the four dimensions, or forking an existing one and adjusting | **decided** | a new primitive is a data declaration, not a code change | **not yet** |
| S6 | Channel type names must not contain agent names | **contradicts-prior** | live registry types are `river`, `hosted-river`, `shared-river` — three channel types named after the agent that flows through them, which is exactly the collision D1 resolves | **not yet** — renaming is live registry state and is a migration, not a spec edit |

### Agents

| # | Claim | Status | Observable | Enforced by |
|---|-------|--------|-----------|-------------|
| A1 | **River is the agent, not the channel.** The channel is infrastructure and needs no metaphor — "your channel", "the family channel" | **decided** (operator, 2026-08-16 07:24) | no user-facing surface calls a channel "a river" | **not yet** — and S6 is the live counter-example |
| A2 | **Turtle stays Turtle.** No collision, no rename | **decided** | — | n/a |
| A3 | **Eddy stays eddy**, against Discord's "thread". It does real semantic work: spins off the main flow, lives briefly, dissolves back | **decided** | — | n/a |
| A4 | A **personal** Turtle/River is bound to the practitioner's own channel, attuned to them, knows their practice root, and has ambient awareness of shared spaces they belong to via twine | **decided** | a personal agent's memory scope is the practitioner's root plus shared twine | partially — `mage.get_pd`, `render_scope_block` |
| A5 | A **shared** Turtle/River is bound to the shared channel, attuned to the collective, knows the shared space's root, and **does not reach into any member's private root** | **decided** | a shared-space prompt contains no private-root material | **no — and it is currently violated.** See A7 |
| A6 | Neither agent crosses the boundary uninvited; explicit sharing (a link, a forward, `!share`) is the only bridge | **decided** | every crossing has a member act behind it | `test_daily_note_routing`, share machinery — partial |
| A7 | The A5 boundary needs a mechanism, not a sentence | **open — the operator's fork, and it stays his** | `dialogue_runtime.py` appends up to 3000 characters of a speaking member's personal `compass.md` into the shared family prompt when one exists. Contained today only by the absence of that file. Logged as INT-050 in the operator's issue record, where the choice is recorded as his: delete the branch, or gate it. | *not decided here.* A spec that states a memory boundary and ships no guard is this codebase's characteristic defect. Either the guard lands with the decision or the fork stays open — it stays open. |
| A8 | Who configures and tends a shared agent | **open** | for a family, the administrator. For a Wohngruppe or team, stewardship is not obvious and nothing in the record settles it. | — |

### Topics

| # | Claim | Status | Observable | Enforced by |
|---|-------|--------|-----------|-------------|
| T1 | A topic is **an eddy**, not a primitive type | **contradicts-prior** (supersedes `design-topic-channels.md` 2026-08-05) | the primitive schema has no `topic` member | this document; the old chapter's status header |
| T2 | A **topic eddy** differs from an ordinary eddy by declared subject scope — River stays on topic and surfaces relevant prior sediment | **decided** | a topic eddy names its subject; an ordinary one does not | **not yet** |
| T3 | **The graduation test:** a topic earns a channel when it is persistent and high-traffic enough that members keep reopening eddies for it. A daily-update garden in a Wohngruppe earns one; a quarterly finances check-in does not. | **decided** | a graduation is a recorded event with a stated reason, not a preference | **not yet** — and the threshold is a judgement, see T4 |
| T4 | Whether "persistent and high-traffic enough" is a computable threshold or a judgement | **open** | the honest position is that nobody has run this even once. A number invented before the first graduation is a number measuring the person who invented it. | — |
| T5 | A graduated topic channel inherits its space's primitive and narrows Turtle's and River's attention to the subject | **decided** | a `#garden` channel in a Wohngruppe is `wohngruppe` + a subject scope, not a new primitive | **not yet** |
| T6 | Everything `design-topic-channels.md` specified for a topic **channel** — charter, scoped twine filter, close/reopen, nudge backoff, kind lineage, sidebar placement — applies unchanged to a graduated topic and mostly to a topic eddy | **decided** | the old chapter is a live reference for the graduated case | the old chapter's supersession header, which scopes what was overturned |

---

## What another household can do with this

Three procedures. If any of them cannot be executed from this document plus the old chapter without a side conversation, the spec is not done.

### Add a relational channel

1. Choose the relational primitive: `private` (one person), `family` (intimate household), `wohngruppe` (residential community), `team` (delivery-oriented). If none fits, fork the nearest and change one of the four dimensions — that is a new primitive, and naming it is the whole act.
2. The primitive fixes membership and visibility: a family channel is visible to family members and nobody else. There is no per-channel permission decision to make; the primitive already made it.
3. Turtle in that channel is the **shared** agent for the space, not any member's personal Turtle. It knows the shared root. It does not read anyone's private root (subject to A7, which is open).
4. River's posture comes from the primitive: how readily it acts unprompted, and which acts it offers.

### Add a thematic channel

1. Choose the thematic primitive: `craft` today; `learning`, `creative`, `health`, `financial` are named but not shipped.
2. Decide the scope separately — a thematic channel can be single-practitioner (`craft` is) or shared. Scope and mode are independent, which is the point of the second axis.
3. Do **not** attempt a relational × thematic composition in v1 (S4). If a household wants a shared reading practice, open a relational channel and treat the reading as a topic eddy inside it until it earns graduation.

### Decide when a topic eddy becomes a channel

1. Start every topic as an **eddy**. This is the default and it needs no justification.
2. Let it run. An eddy that dissolves, or that gets checkpointed and revisited occasionally, has answered the question — it was never a channel.
3. Graduate only on **recurrence**: members keep reopening eddies for this subject, and the traffic is enough that a shared channel would be quieter than the river with it in. Record the reason when you graduate; a graduation with no reason is indistinguishable from a preference.
4. On graduation, the old chapter is the build sheet: charter, scoped twine, close/reopen, nudge cadence, sidebar placement.
5. There is no de-graduation path specified. That is a gap, not a decision.

---

## What exists versus what must be built

| Piece | Exists | Needed |
|-------|--------|--------|
| Channel types | `river`, `hosted-river`, `shared-river`, `craft` as registry strings (`mage._get_channel_type`) | A primitive field that bundles all three components; the type strings become one of its outputs |
| Attunement | `get_effective_attunement` resolves per-channel override → craft type → global | **Only two values are accepted** (`native`, `craft`, `mage.py:104`). A `family` primitive with its own attunement cannot be expressed today. This is the narrowest concrete gap in the whole document. |
| River posture | not modelled at all — River's behaviour is uniform across channel types | Posture as a declared dimension |
| Memory scope | `render_scope_block`, `get_pd`, twine assembly | Per-primitive memory boundary, and the A7 guard if the operator closes that fork |
| Topic eddy | ordinary eddies exist | Declared subject scope (T2); graduation as a recorded event (T3) |
| Graduated topic channel | — | `design-topic-channels.md` slice 1, unchanged |

---

## Verification expectations

When any of this is implemented: the decision table's `Enforced by` column is the test list. A row that moves from **not yet** to a named module must name a test that fails when the claim stops being true, with a positive control proving the test can fail. A row that stays **open** stays open; closing one by writing prose into it is the defect this table's shape exists to prevent.
