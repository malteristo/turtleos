# Proposal: TURTLE_SPEC amendments — story-layer delivery, voice, and blank-eddy naming

**Date:** 2026-07-28
**Spec reference:** §6.5 (Story Surfaces), §7.2 (Eddy Entry Behavior), §15.5 (Cross-practitioner boundaries)
**Status:** **Draft — awaiting operator sanction. Not applied.**
**Warrant:** INT-040 through INT-045, diagnosed and fixed 2026-07-28. Implementation now differs from law in three places.

> **Widening proposed before sanction (2026-07-28 evening, additive — wording below unchanged).** Two further faces of the same ownership law surfaced after this draft was written: **INT-046** (which practice root a scheduled artifact is *written for* resolves from ambient context) and **INT-047** (what carries into a shared room between eddies is unconfirmed and unattributed, and `alive.yaml` has no author field). The "Whose is this?" law below reaches *delivery*; it does not yet reach *selection* or *carry*, and the voice law governs prose records but not structured carried state. Proposed additional clauses: [`carried-context-and-the-confirm-moment.md`](carried-context-and-the-confirm-moment.md) §6 — **but read [`what-a-shared-room-remembers.md`](what-a-shared-room-remembers.md) first.** The "nothing carries unconfirmed" clause has been **withdrawn** (2026-07-29): it was drafted from a consent design that has since been dropped, and sanctioning it would write a discarded mechanism into law. The surviving requirements are attribution and non-persistence, not confirmation. Sanction should either fold those in or explicitly defer them.

---

## Finding

Behaviour shipped today that the spec does not describe, and in two places actively contradicts.

1. **§6.5 says delivery is ambient.** The Daily note row reads: *"after a fresh synthesis (`created=True`), post inline preview + **Open note** on the river."* "The river" — singular, definite, unqualified. On a single-practitioner node that is unambiguous. On a node hosting four practitioners and three shared spaces it is undefined, and the implementation resolved it to a global constant: every practice root's daily note published into the operator's river. Four foreign notes accumulated there, including two of a hosted practitioner's **private** daily syntheses (INT-042).

2. **§6.5 is single-practitioner by construction.** The Eddy note row reads from *"the practitioner's"* alive threads; there is no member model and no voice law. In a 2+-member space this collapsed every member's contribution into one undifferentiated "you" (INT-040). Per-member notes do not exist in law at all.

3. **§7.2 mandates a string that is also a routing keyword.** *"Thread title starts as `new eddy`"* — and `eddy_spawn.INTAKE_PATTERNS` reserved `"new eddy"`. Law and implementation collided on a literal, and a practitioner's first message in a fresh eddy was rerouted into a Turtle-titled child eddy (INT-044).

4. **§15.5 was right and evadable.** It already forbids the operator surfacing hosted-river **message content** in their river. INT-042 surfaced a *synthesized note* — derived, not message content. The spirit was correct; the letter had a gap.

## Gap

The spec assumes a single sovereign wherever it describes the story layer, and names a title where it means an identity. Both assumptions were safe when written and became privacy boundaries when the node became multi-practitioner.

## Proposal

### §6.5 — Story Surfaces

**Amend the Daily note row's river-visibility clause:**

> **River visibility:** after a fresh synthesis (`created=True`), post inline preview + **Open note** to the river that **owns the practice root the note was synthesized for**, resolved through the registry — never through a global dialogue channel. A practice root that resolves to no owning river MUST NOT be posted anywhere; resolution failure fails closed. A **shared-space** root has no owning river and MUST NOT post its communal note to any single member's river.

**Add a surface row:**

> | **Per-member period note** | Period close, one per member of a shared space | The space's own attributed record for that period. Second person to its single recipient; every other member named in attributed third person. Delivered to that member's own river, never to the shared channel. |

**Add to Laws:**

> - **Voice branches on audience cardinality.** A record read by exactly one person MAY address them as "you". A record read by more than one MUST narrate in third person with every contribution attributed to its author, MUST NOT merge two members into one voice, and MUST hold one member's account of another as that member's perception rather than as fact. A solo river and a per-member note fall under the same rule for the same reason: referent stability.
> - **Whose is this?** Any resolution of ownership — which root, which river, which author — MUST fail closed rather than fall back to ambient context. Ambient fallback resolves toward the operator, who already holds the most access.
> - A shared-space note MUST NOT read a member's private alive layer, intentions, or profile notes. Crossings stay member-initiated and per-item (charter §3.2).

### §7.2 — Eddy Entry Behavior

**Append to item 1:**

> The blank-eddy title (`new eddy`) is a **placeholder for display only**. It MUST NOT be used as a routing, classification, or identity signal. Eddy identity is resolved from durable registry state, never from a title — titles are practitioner-facing text: auto-generated, practitioner-editable, and unconstrained.

### §15.5 — Cross-practitioner boundaries

**Amend the second paragraph:**

> The operator MUST NOT surface hosted-river message content — **or any artifact derived from it, including synthesized notes, summaries, and digests** — in the operator's river, proposals, or session notes. **A derived artifact inherits the boundary of its source.**

## Risk

- **§6.5 voice law** is the only amendment that constrains unbuilt work (weekly/monthly). It is written to apply at any scale, so it should not need revisiting.
- **§7.2** forbids something the implementation no longer does; the risk is discovering another name-keyed code path that now contradicts law. That is the point — INT-045 tracks the sweep.
- **§15.5** broadens an existing MUST NOT. It could in principle forbid a legitimate operator surface (e.g. an aggregate health read that counts hosted eddies without quoting them). Counts and pattern observations remain allowed under the existing first paragraph; only content and its derivations are barred. Worth a second read on that line specifically.
- Amending law after shipping inverts the grill-first order `docs/development.md` prescribes. Noted as a deviation: the fixes were urgent (a live privacy leak), the spec work is catching up. Sanction should cover both the amendment and the inversion.

## Verification

All four behaviours have tests and traceability rows as of 2026-07-28 (`test_daily_note_routing`, `test_witness_voice`, `test_river_handler`, matrix §6.5 rows). The amendment describes what is already verified — with the exception of per-member notes, which are green in test and dry-run but have not yet written a real note.
