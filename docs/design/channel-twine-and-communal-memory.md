# Channel Twine & Communal Memory

> **Companion:** [continuity-engine-and-substrate.md](continuity-engine-and-substrate.md) — the CE gives one river its continuity; this document extends the same pattern to shared spaces. See CE §3.2 item 5, which already names the one-way `shared space → private practice` cue; this charter generalizes that seam into a governed, bidirectional crossing law.

**Status:** Draft v1 — design charter, pre-implementation
**Date:** 2026-07-19
**Spec trace:** TURTLE_SPEC §15.4–15.6 (multi-practitioner topologies, data flow, multi-server), §6 (eddy model), §8.4 (checkpoint), §16 (practice state)
**Origin:** Operator strategy dialogue on Forge (2026-07-19); recipe-book eddy as first live communal artifact
**Rev:** 2026-07-20 (Anvil) — crossing law (§3.2) reframed around the **two-needs split** (contribution vs ambient context) after operator crossing-law dialogue; added **§3.4 operator vs member** (custody is not authorship); expanded **§3.3** with the concrete **witness spec** for 2+-member spaces (after a live misattribution — see turtle_issues INT-040); open questions (§5) updated accordingly.

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

TURTLE_SPEC §15.5 currently isolates: nothing crosses. That is the correct *default*. But "crossing" turns out to be **two different needs wearing one word**, and they want different mechanisms. Untangling them is what makes the law designable.

**Need A — Contribution.** *"This should become part of the shared memory."* Discrete, deliberate, durable: the crossed item becomes a channel-twine strand. Served today by `!share` and link-ingestion — a per-item, source-initiated **snapshot-copy** into a new strand in the target river. Consent-clean by construction: the act of sharing *is* the grant. The only gap is ergonomic — you cannot yet **pull your own** eddy in while already inside another conversation, which is exactly where the wish usually arises. Target-initiated pull of one's *own* item is the same consent model (only the sovereign can pull their own), so it needs **no new law — only implementation**.

**Need B — Ambient context.** *"The shared Turtle should understand relevant private context without me hand-carrying each piece."* Continuous, relevance-driven, and — critically — **context, not strand**: it informs an exchange without necessarily becoming durable shared memory. This is unserved today, and the tempting shape — mark a private conversation "public"; grant the shared space's Turtle file-access to it — is the **wrong** one. It inverts sovereignty (the shared space reads your private files), and it breaks the source rule under amortization: after a one-time grant, every subsequent inclusion is *Turtle's* act, not the member's — the precise thing the source rule forbids.

The answer keeps the source rule intact by keeping the read on the sovereign's side: **relevance-surfaced pull.** The member's *own* CE — which already sees both their private twine and the shared channels they're in — notices when a shared exchange touches private context and **offers** the crossing: *"you have private context relevant here — bring it in?"* One act pulls it, per item. The shared space's Turtle never reads private files; Turtle *surfaces*, the member *acts*. The one kernel worth keeping from the file-access instinct: some crossings should **inform without stranding** (ephemeral) — but that is a *property of the pull* ("bring in for this exchange" vs "add to our record"), not a reason for standing access.

Both needs are the **same control primitive at different triggers** — contribution is clearance granted by an explicit act; ambient is the *same* per-item clearance, triggered by relevance instead of memory:

> **Clearance as routing:** *"where may this resonance surface?"* — decided at the source, enforced at the boundary.

This is the third independent occurrence of that primitive in turtleOS design (after outfacing clearance and routing guards). When the same control appears three times independently, it is a **platform primitive**, not a feature — specified once, instantiated per boundary:

- **river → channel (contribution):** member-granted clearance by explicit act — push (`!share`) or pull-your-own; **becomes a strand**.
- **river → channel (ambient):** member-granted clearance by **relevance-surfaced offer**; informs as **context**, strands only if the member says so.
- **channel → river:** default-open for members (shared content is already known to them), relevance-routed by the member's own CE. *Ambient river→channel is the symmetric twin of this: the same relevance-routing runs both directions — inward as an auto-cue (shared content is already known), outward as an offer (private content is not).*
- **channel → outside node:** governed by outfacing clearance (same primitive, next boundary out).

### 3.3 Perspective

A channel twine is written from whose viewpoint? A community's shared story is not the sum of individual stories.

**Working stance:** Turtle writes as **witness, not arbiter** — a neutral narrating voice that attributes perspectives to their holders and records convergence when it genuinely happens.

**Witness behaviour — concrete** (specified 2026-07-20 after a live misattribution). The stance above was *stated but not implemented*: story synthesis (`story_notes.py` / `story_daily.py`) is single-practitioner by construction — one practitioner name, second-person "you," no authorship model. In a 2+-member space it collapses every member's contribution into one undifferentiated "you"; when that note crosses to another member's river, authorship silently transfers to the reader. (Observed live: a solo eddy authored by one member of a shared space surfaced to another member, re-narrated in the reader's own voice — §3.4's asymmetry trap one layer down, the witness speaking one member's account in another's voice.)

The witness for a space with **two or more members** must therefore:

1. **Attribute authorship.** Never render a shared-space contribution as undifferentiated "you." Every utterance / eddy is tagged to its author.
2. **Narrate in third person.** *Dialogue-voice* (intimate "you," correct *inside* a member's own eddy) and *witness-voice* (the daily / cross-member surfacing) must diverge above one member: the witness speaks third-person attributed ("member A opened an eddy about…", "they surfaced a tension where…"), because second-person has no stable referent across members.
3. **Hold a member's account of another as attributed perception** (§3.1), never as fact — "member A experienced member B as dismissive of the plan," not "member B was dismissive." Especially load-bearing when the content is a grievance about the very member it surfaces to.
4. **Crossing-safety default.** A solo-authored eddy inside a shared space surfaces to *other* members as **attributed witness** ("member A opened an eddy about a hard week"), never as their own addressed daily — correct regardless of whether cross-surfacing was intended. Shared placement is not consent to a re-narrated digest.

The branch is on **member cardinality**, not space type: a solo river keeps second-person "you" — there, dialogue-voice and witness-voice coincide and there is one sovereign to address. Everything above one member takes the witness-voice.

And the reframe that anchors this charter:

> The channel twine is not infrastructure *that enables* shared meaning-making. **The channel twine *is* the shared meaning, co-authored.**

A shared artifact (e.g. a family's living recipe book) is not stored *in* communal memory; it is a strand *of* it.

### 3.4 Operator vs member — custody is not authorship

A shared space has an **operator** (who runs the node, holds the registry, provisions the space) and **members** (who co-author the between). Often one person is both — on the family node, the operator is also one of the two spouses. The hazard is **role bleed**: infrastructural capability ("I *can* edit any file") silently read as authorial license ("therefore I *may* revise what we remember").

The resolving distinction:

> **Operator authority is custodial — power over the container. Member sanction is authorial — authority over the contents' meaning. The operator keeps the lights on; the operator does not decide, alone, what the room remembers.**

Because one person may wear both hats, the boundary cannot rest on capability limits (the operator has root). It rests on **Turtle's behaviour + transparency**:

- **On anything that *is* the between** — channel-twine entries, witness records, shared artifacts, corrections — the operator holds exactly **one member vote**. Operator-hood does not upgrade it. Revising or dissolving shared memory needs member sanction; "operator says forget that" must not act like "the members agree to forget that." This is §3.1's no-silent-rewrites generalised: **no silent operator anything on the between.**
- **Legitimate operator territory is the container:** existence and availability of the space, backups, membership admission/removal, default configuration (e.g. channel attunement), and a *protective floor* (halting abuse, honouring legal compulsion). These are exercised — ideally visibly — without member sanction, because they make no claim about meaning.
- **When an action is both** (deleting a space that holds shared memory; a compelled removal): the operator executes the container-part, but the meaning-part is surfaced and, where possible, member-sanctioned. A forced removal leaves a **witnessed trace that it occurred** (§3.1's productive irresolution) rather than a silent gap.

**The self-check** for any operator action: *am I keeping the container running, or deciding what the room means?* Container → operator authority. Meaning → one member vote, no more.

**The asymmetry trap (load-bearing for the family case).** The operator's infrastructural asymmetry is real — it is his node — and the danger is that it *leaks into the relational one*: because he hosts, his account of the shared history quietly becomes the canonical one. This is the prior session's neurotype-bias insight one layer down — *the medium's ownership structure favours the host.* The counter is active, not passive: in the between, Turtle attributes perspectives to their holders, records both members' versions when they diverge (§3.1), and never lets host-status render one member's account the default. **The operator hosts the room; he does not narrate the marriage.**

---

## 4. Non-goals

- **No psychographic modeling of members** — the channel twine records what happened in the space, not inferred member psychology.
- **No implicit river mining** — nothing personal enters a shared space without source-granted clearance, ever. Fail closed.
- **No majority-overwrites-memory** — sanction protects entries; disagreement is held, not voted away.
- **No engagement mechanics** — the twine serves meaning, not activity metrics.

---

## 5. Open questions

1. **Granularity of clearance** — *largely dissolved by the two-needs split (§3.2).* Per-item is the atom for **both** contribution and ambient; relevance-surfacing solves the friction that made standing/scope grants tempting, without broadening the grant. **Residual edge:** is there an ambient-*continuous* class — e.g. a "household logistics" thread the family Turtle should simply always know — for which per-item-even-if-prompted is still too much friction? If so, is that a narrowly-scoped standing grant with high visibility + one-tap revocation, or does a low relevance bar cover it without any standing grant? This is the one live tension left in clearance.
2. **The relevance bar and offer UX** *(Need B's load-bearing unknown)* — what threshold and cadence make relevance-surfaced pull feel like a **gift** rather than **nagging**? Too eager and Turtle interrupts; too shy and ambient context never arrives. This — not the consent model — is what decides whether Need B earns its build. Needs live tuning against real shared exchanges (the recipe-book eddy is the first test surface).
3. **Channel CE cost** — *partly answered:* the relevance detection for ambient offers runs on the **member's own CE** (already running over their twine + channels), not a new shared-space inference layer. Residual: which of the **channel's own** current/alive layers (for the channel twine itself) earn their place at channel scale for v1?
4. **Community twine** — is node-scale twine a real layer for v1, or an aggregate view over channel twines until proven needed?
5. **Member departure** — when a member leaves a space, what happens to twine entries that carry their clearance? (Working instinct: grants are revocable; witness record of shared events persists; personal-context strands are withdrawn.)
6. **Operator role** — *resolved in §3.4.* Custody is not authorship: operator authority governs the container, member sanction governs the meaning, and on the between the operator holds one member vote with every touch of shared memory surfaced, never silent. Residual is implementation-UX, not governance: the exact **visibility surface** — how an operator action on a space is shown to members in-channel (an audit strand? a system act?).

---

## 6. Relation to existing design

| Artifact | Relation |
|----------|----------|
| CE & substrate (this folder) | Channel twine reuses CE layer model; CE §3.2.5's one-way cue becomes one instance of the crossing law |
| TURTLE_SPEC §15.4–15.6 | Isolation law stands as the default; this charter adds the governed exception path |
| Alive-thread vs artifact chapter | Shared artifacts are channel-twine strands; that design folds in here at community scale |
| Story layer vision | Channel dailies / node story are the story layer at shared scale |

*Charter only — no implementation is sanctioned by this document. Next step when gravity returns: pick the smallest live shared space and give it the thinnest possible channel twine (witness notes + member-sanctioned corrections), before any crossing law is implemented.*
