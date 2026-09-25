# Design: Channel Primitives

**Date:** 2026-08-17
**Status:** Implemented resolved-contract spine (2026-09-07); health is the first complete sensitive preset. Decisions below remain `decided` / `open` / `contradicts-prior`. **Open cells stay open.**
**Container (2026-08-30):** [practice-channels.md](../design/practice-channels.md) — solo/shared primitives, install pair, roster. This chapter names *kinds* of practice channel; that file names the house they sit in.
**Spec reference (candidate):** TURTLE_SPEC §15 (shared spaces), §8 (eddies), §7.4 (attunement), §6.2 (river acts)
**Supersedes:** [design-topic-channels.md](design-topic-channels.md) — its surface recommendation only; see § The overturn.
**Origin:** an operator craft conversation on consistent terminology for users, 2026-08-16 – 2026-08-17. Target condition confirmed by the operator, revised once, direction held.

---

## What a channel primitive is

Until now every channel in turtleOS was hand-shaped: `river`, `hosted-river`, `shared-river`, `craft` exist as registry type strings with behaviour scattered across the modules that read them. A **channel primitive** is the binding contract that makes a channel kind repeatable — so a household that is not the operator's can choose one, or craft one, without reading Python.

**A primitive bundles four things:**

| Component | What it declares |
|-----------|------------------|
| **Channel** | structure, membership rules, visibility boundaries |
| **Turtle** | attunement, memory scope, care orientation |
| **River** | posture, initiative level, which acts it offers |
| **Practice** | owned artifacts, capabilities, data locality, mutation authority, provenance, retention and verification |

**Each is described on four dimensions** — the shape the operator named on 2026-08-16 08:01:

- **Scope** — who it cares about (one person, a household, a team)
- **Attunement** — what it pays attention to (personal practice, shared rhythms, project delivery)
- **Memory boundary** — what it can see (private root, shared root, twine access)
- **Default posture** — how it initiates versus responds (ambient or summoned, reflective or operational)

The primitive is the contract, not a new engine. `channel_primitives.py` resolves
that contract from the parent channel or eddy identity. Unknown or incoherent
declarations receive no capabilities. A root is not an authority identity:
private and craft can share one root. Legacy registry types pass through an
adapter while they migrate.

The conceptual axes below are inputs to design, not a free-form configuration
surface. Practitioners choose an atomic preset. The preset may expose a narrow
validated variant where the practice requires it (health permits solo or
shared); memory, data policy, capabilities and authority cannot be mixed
independently.

### Primitive development law

- Compose existing platform capabilities before adding domain mechanisms.
- Put a requirement in core when another plausible primitive can reuse it; keep
  only irreducibly domain-specific policy in the extension.
- Design synergy at capability seams — intake, retrieval, authority,
  provenance, artifacts and acts — never through cross-practice private reads.
- Core owns mechanism and enforcement; the primitive declares policy and
  experience; the practice root holds member-owned state.

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
| S1 | A channel primitive bundles Channel + Turtle + River + Practice as one named unit | **decided** | a primitive is nameable in one registry field; capability, authority and data policy are resolved with its agent behavior | `channel_primitives.py`; `test_channel_primitives` |
| S2 | Primitive design considers two axes: relational (who) and thematic (what mode) | **decided** | `craft` and `private` share a scope and differ in attunement; presets retain the distinction without exposing unsafe composition | `channel_primitives.py`; `test_channel_primitives` |
| S3 | Shipped defaults are **atomic** | **decided** | choosing `private`, `shared`, `craft`, `partnership`, `health`, or `team` returns one complete contract | `channel_primitives.py`; `test_channel_primitives` |
| S4 | Relational × thematic composition is not a v1 configuration API | **decided** — health exposes only the topology variants its validator names. Arbitrary overlays would permit sensitive data with generic tools or shared rooms with personal memory. | invalid combinations fail closed | `primitive_is_valid`; `test_presets_reject_unsupported_topology` |
| S5 | Crafting a new preset means specifying and validating the complete contract | **decided** | a new preset is a declaration plus runtime capability binding, not scattered routing checks | `channel_primitives.py`; `primitive_runtime.py`; `test_primitive_architecture` |
| S6 | Channel type names must not contain agent names | **contradicts-prior** | live registry types are `river`, `hosted-river`, `shared-river` — three channel types named after the agent that flows through them, which is exactly the collision D1 resolves | **not yet** — renaming is live registry state and is a migration, not a spec edit |
| S7 | Sidebar category is channel-instance navigation, not primitive semantics | **decided** | an instance may declare `discord_category`; audit reports when the live channel moves elsewhere, while the resolved preset and authority remain unchanged | `runtime/adapters/structural.py`; `test_discord_reconcile` |

### Agents

| # | Claim | Status | Observable | Enforced by |
|---|-------|--------|-----------|-------------|
| A1 | **River is the agent, not the channel.** The channel is infrastructure and needs no metaphor — "your channel", "the family channel" | **decided** (operator, 2026-08-16 07:24) | no user-facing surface calls a channel "a river" | **not yet** — and S6 is the live counter-example |
| A2 | **Turtle stays Turtle.** No collision, no rename | **decided** | — | n/a |
| A3 | **Eddy stays eddy**, against Discord's "thread". It does real semantic work: spins off the main flow, lives briefly, dissolves back | **decided** | — | n/a |
| A4 | A **personal** Turtle/River is bound to the practitioner's own channel, attuned to them, knows their practice root, and has ambient awareness of non-isolated shared spaces they belong to via twine | **decided** | a personal agent's memory scope is the practitioner's root plus permitted shared twine | `memory_roots_for`; resolved memory policy |
| A5 | A **shared** Turtle/River is bound to the shared channel, attuned to the collective, knows the shared space's root, and **does not reach into any member's private root** | **decided** | a shared-space prompt contains no private-root material | `dialogue_runtime`; `memory_roots_for`; `test_shared_prompt_boundary` |
| A6 | Neither agent crosses the boundary uninvited; explicit sharing (a link, a forward, `!share`) is the only bridge | **decided** | every crossing has a member act behind it | `test_daily_note_routing`, share machinery — partial |
| A7 | The A5 boundary needs a mechanism, not a sentence | **decided** (2026-09-07) | the speaking member's identity does not grant a shared room their private compass or workspace | private-compass branch removed; `test_shared_prompt_boundary`; `test_primitive_architecture` |
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

1. Choose an atomic preset: `private` (one person), `shared` (community), `partnership` (exactly two partners), or `team` (shared work). A household with a wider audience needs its own designed preset; it is not an automatic widening of partnership history.
2. The preset fixes membership semantics and visibility. There is no per-field memory or authority decision to make; the validator already made it.
3. Turtle in a shared channel is the **shared** agent for the space, not any member's personal Turtle. It knows the shared root and does not read anyone's private root.
4. River's posture comes from the primitive: how readily it acts unprompted, and which acts it offers.

### Add a thematic channel

1. Choose the thematic preset: `craft` or `health` today; `learning`, `creative`, and `financial` are not shipped.
2. Use only its named topology variants: craft is solo; health validates solo or shared. Do not compose scope and mode freely.
3. Do **not** attempt a relational × thematic overlay in v1 (S4). If a household wants a shared reading practice, use a shared channel and treat reading as a topic eddy until it earns graduation.

### Decide when a topic eddy becomes a channel

1. Start every topic as an **eddy**. This is the default and it needs no justification.
2. Let it run. An eddy that dissolves, or that gets checkpointed and revisited occasionally, has answered the question — it was never a channel.
3. Graduate only on **recurrence**: members keep reopening eddies for this subject, and the traffic is enough that a shared channel would be quieter than the river with it in. Record the reason when you graduate; a graduation with no reason is indistinguishable from a preference.
4. On graduation, the old chapter is the build sheet: charter, scoped twine, close/reopen, nudge cadence, sidebar placement.
5. There is no de-graduation path specified. That is a gap, not a decision.

---

## Team preset and the first Quest channel

`team` is shared work, not a D&D primitive. A valid instance has one shared
root, an explicit coordinator among two or more members, attributed
contributions, restart-safe eddies, and executable goal, task, decision,
artifact, member-lane and intersection state. Cross-root sharing is explicit.
River has an operational posture; Turtle holds dialogue in eddies.

Team alignment uses **one shared horizon plus member-owned fronts**. Every
active member confirms the broad horizon. Each member alone confirms how their
current sub-goal, exploration, support, challenge or pause relates to it.
Coordinator means tending the surface and process, not assigning another
member's intent. Proposals remain visibly proposals until the authority named
by their scope confirms them.

**Quest** is the practitioner-facing name of the first live team instance. The
existing personal Quest flow keeps its current meaning. The established
sandbox channel/root become Quest in place: same audience, root and
history, explicit team contract. Discord cannot split or move the old shared
thread, so Galactic Adventure preserves it as a read-only prologue and
continues in one readable, owner-enforced eddy per member.

The campaign is a team activity, not the source of team governance. Its runtime
records raw exchanges before reduction, advances lanes independently, offers
bounded sibling developments, and reconciles at natural scene boundaries. The
general team mechanism remains useful for non-game goals, tasks, decisions,
artifacts, handoffs and reflection.

`test_channel_conformance`, `test_team_state`, `test_team_lanes`,
`test_team_federation`, `test_campaign_state`, and `shake_team_work.py` are the
proof surface.

---

## What exists versus what must be built

| Piece | Exists | Needed |
|-------|--------|--------|
| Channel primitive | `channel_primitives.py` resolves atomic presets and narrow variants; legacy types adapt | Migrate remaining registry rows after established presets prove the contract |
| Attunement | `get_effective_attunement` resolves primitive attunement (`native`, `craft`, `health`) | Future primitive-specific prompt composition |
| River posture | `primitive_runtime.py` dispatches `ambient`, `operational`, `governed_intake`, and `deterministic_intake`; all parents belong to River | Additional posture handlers only when a preset earns one |
| Practice | data policy, capabilities, roles, memory boundary and authority resolve together | Continue retiring root/name-derived consumers |
| Team state | `governed_state.py` + `team_state.py`: attributed ledger, scoped confirmation, rebuildable board | Learn from the first live team's ordinary use |
| Member lanes | `team_lanes.py` enforces owner writes; `team_federation.py` carries bounded sibling developments | Add new activity reducers only when another activity earns one |
| Campaign activity | `campaign_state.py` composes raw-first events and derived shared/per-member views | Multiplayer mechanics emerge from play; no round-robin gate |
| Topic eddy | ordinary eddies exist | Declared subject scope (T2); graduation as a recorded event (T3) |
| Graduated topic channel | — | `design-topic-channels.md` slice 1, unchanged |

---

## Verification expectations

When any of this is implemented: the decision table's `Enforced by` column is the test list. A row that moves from **not yet** to a named module must name a test that fails when the claim stops being true, with a positive control proving the test can fail. A row that stays **open** stays open; closing one by writing prose into it is the defect this table's shape exists to prevent.
