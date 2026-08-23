# Family Care — Operating Model

**Date:** 2026-08-04  
**Status:** Active stance — governs family-facing turtleOS craft  
**Spec reference:** TURTLE_SPEC §1.4 (platform vs attunement), §15 (shared spaces), §6–8 (river / eddy)  
**Companion chapters:** [design-family-dates.md](../chapters/design-family-dates.md), [design-topic-channels.md](../chapters/design-topic-channels.md), [relations-and-membership.md](relations-and-membership.md), [eddy-age-and-river-quiet.md](eddy-age-and-river-quiet.md), [design-update-announcements.md](../chapters/design-update-announcements.md)

---

## Vision kernel

turtleOS, under this operator's intention, is a **family care and operations system** — care before operations. Interpersonal AI: supports family dynamics and relational well-being, not individual productivity cosplay.

- **Members, not users.** Even the administrator is a member with special rights.
- **Co-Creation Law.** Non-operator members are voluntary co-creators, never test subjects. Expressed needs are design input on their terms; non-participation is a valid design answer; features *about* a member require that member's voice, not only their data.
- **Metric.** Practical value within family matters; quality of conscious experience with loved ones. Not engagement, not usage frequency, not mood scores.

Requirements are mined from the **family shared river** (and private rivers when freely offered). The operator's private practice workshop may hold an audit / needs registry; this file is the product stance the public repo can carry.

---

## Needs map (current)

### Member practice (shared river)

| Cluster | What shows up | Product shape |
|---------|---------------|---------------|
| Witness / load | Overwhelm, proof-demand allergy, asymmetric scrutiny | **Family Barometer** — derived, zero-input, symmetric (both parents or neither) |
| Hold what matters | Dates, unresolved logistics, "keep this alive" | **Dates** (shipped) → **Topics** (alive until members resolve) |
| See the household | Plans, parties, invisible labor | Working plans (live) → read-only **family surface** ("fridge") |
| Mediation that holds | Conflict witnessed in-room; tool trusted mid-friction | Steward as proven core — never market as referee |
| Cheap input | Phone-first, voice when distressed | Voice notes when Discord path is cheap |

### Operator practice (admin-member)

| Need | Product shape |
|------|---------------|
| Ops without a craft IDE | Topics + fridge first; full admin console only if conversational ops fail |
| Craft serves the kingdom | Family thesis gates every family-facing slice |
| Offering that isn't self-cancelling | Family-administrator pattern — after *this* family works |
| Guest rivers | Hosted research lane — do not conflate with family redesign |

Parked (seed, not need): multiplayer adventure experiments, oracle/research offers, install skills, README/privacy publication — revisit when a Care or Need pulls the same shape, or when an offering chapter opens.

---

## Daily impulses — three bins

Every signal from turtleOS practice (Discord digest, arrival, boom, in-room noticing) lands in exactly one bin:

| Bin | When | Action |
|-----|------|--------|
| **Care now** | Someone is overloaded, unheard, or blocked *in the room* | Respond in the room (witness). No Forge chapter. No backlog row until heat drops. |
| **Need noticed** | Recurring or explicit want with evidence | One line: *who · what · evidence · date* → needs registry / craft backlog. Build only if it is already the active slice. |
| **Seed** | Interesting idea, no member pain | Park (boom / feature seeds). Revisit only when Care or Need pulls the same shape. |

**Laws:**

1. The family river outranks the backlog. A backlog item without a river citation is a candidate for release.
2. One active family-facing **build** at a time. Impulses accumulate; they do not fork the chapter.
3. Waiting on voluntary use is work — it *is* the metric. Design-only and infrastructure may proceed; new member-facing ships do not jump the queue ahead of an open voluntary-use clock (e.g. dates awaiting first keep).
4. Member-invented shapes beat operator-invented ones. A member opening an unresolved-topic container in chat is stronger evidence than a clean design doc.

---

## Progress clocks

Not "did we ship." Three clocks:

| Clock | Cadence | Progress looks like |
|-------|---------|---------------------|
| **Practical-value events** | Each release when family scope is active | Harvested moments turtleOS carried something (date kept, plan executed, mediation returned to, topic resolved by members) — or an honest zero |
| **Needs latency** | Same glance | Time from expressed need → noticed → shipped → voluntarily used is shortening on *something* |
| **Felt report** | Quarterly | Each parent, in their own words, voluntary: *did family life get better?* Operator anchors to conscious experience with loved ones. Invite non-operator members; never require. |

**Related intentions** (livelihood, network, partnership practice): score the *family face* — would you offer this family-admin pattern to someone you care about? Did a member shape a boundary? — not feature count.

**Anti-progress:** shipping ahead of voluntary use; self-report instrumentation; craft chapters that never touch the room; measuring a member's engagement.

---

## Build order (living)

1. **Dates** — shipped; clock open on first voluntary keep.
2. **Topics** — **rescoped 2026-08-17.** A topic is an eddy, not a channel ([design-channel-primitives.md](../chapters/design-channel-primitives.md) § T1–T6); a topic *channel* is what an eddy graduates to on recurrence, and [design-topic-channels.md](../chapters/design-topic-channels.md) is its build sheet, superseded only in its "topic = channel" default. Nothing here waits on dates any more: the eddy shape needs no channel provisioning.
3. **Family Barometer** — design with the operator after condition-topic material exists in the room; zero-input, symmetric.
4. **Family surface (fridge)** — read-only first; defer full admin console.
5. **Consent wiring** — gated on operator decisions already queued.
6. **Voice notes** — when cheap.
7. **System constitution in shared space** — draft *with* members, not for them.

**Companion infrastructure (may ride):** shared-river eligibility for family-relevant announcements — see topic-channels chapter § Companion slice C and amend [design-update-announcements.md](../chapters/design-update-announcements.md).

---

## Development loop

Family river → notice (M1) → design on Forge/Anvil against this stance + chapter docs → bounded TDD slice → verify (`spirit_verify.sh`, relevant shake) → deploy only with dyad sanction when live → validate only by voluntary use and felt report.

Craft chapters on the family scope open from the river, not from a wishlist.
