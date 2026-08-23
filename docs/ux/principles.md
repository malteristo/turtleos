# Foundational UX principles

Cross-cutting intent for turtleOS practitioner experience. Patterns live in topic docs; this file holds **why**.

**See also:** [README.md](README.md) · [TURTLE_SPEC.md](../../TURTLE_SPEC.md)

---

## River and Turtle are different voices

The **river** is the main channel — ambient, act-only, never conversational.  
**Turtle** exists only in **eddies** (threads) — dialogue, think-aloud, tools, flows.

Practitioners should never wonder whether the river is “talking to them.” If it reads like chat, it’s wrong.

**Metaphor:** the sea in *Moana* / the casita in *Encanto* — care expressed through **acts**, not words.

---

## Acts, not words (River)

River output is **structured acts** rendered as Discord-native affordances:

- Emoji / reactions (acknowledge)
- Embeds (errors, status — not chatty)
- Buttons and select menus
- Chronicle lines (structural memory)
- Discord’s own thread-list UI (thread cards)

The River model outputs JSON acts only. Prose from the River model is **rejected** by the harness.

---

## Consent before spawn

Eddies never open automatically from river text alone. The practitioner **clicks** to materialize (standing bar, contextual flow button, or legacy per-message button where still wired).

Same spirit applies inside eddies for **incidental links** — buried URLs in long messages require Read/Skip opt-in ([link-reading.md](link-reading.md)).

---

## Prefer Discord-native surfaces

When Discord already renders something well, **use it** — do not rebuild for aesthetics.

Example: thread history in the river channel uses Discord’s **default thread-list embed** (the card showing thread title, message count, and app avatar). We spawn threads from anchor messages so that UI appears naturally.

---

## Visibility in the channel, not in side drawers

Affordances must live **in the timeline the practitioner is watching**.

**Rejected:** pinned “doors” or controls that only appear in Discord’s separate pinned-messages panel — easy to miss, breaks the “always at the bottom” mental model. Full inventory: [rejected.md](rejected.md).

---

## Two-bot identity (native)

When `RIVER_BOT_TOKEN` is configured:

| Bot | River channel | Eddies |
|-----|---------------|--------|
| **River** | Acts only — bar, chronicle, **`!` commands** | All platform **`!` commands** (acts); lifecycle bar; thread materialize |
| **Turtle** | Silent | Dialogue only — reads `[Act: !cmd]` digests; may suggest commands |

Practitioners distinguish **who is acting** by app name and avatar. Single-bot mode is a migration fallback, not the target native UX.

---

## Minimal chrome in vanilla eddies

Native eddies ship without Magic-era control panels, model pickers, or config cards on entry. The shell stays quiet until the practitioner speaks; Turtle’s first reply may be preceded by a compact presence embed.

---

## Timeline owns operational trace

When the shell does work on the practitioner’s behalf (fetch a URL, load a flow file, checkpoint a session), **progress and outcome belong on the timeline** — embeds and system lines — not as fetch prose in Turtle’s conversational voice.

Link reading is the reference implementation: [link-reading.md](link-reading.md). Session capture: [sessions.md](sessions.md).

---

## Care is not agreement

Turtle’s warmth must not collapse into agreeableness. **Care includes friction** — naming a missing side, challenging a settled assumption, refusing to soothe by spinning a one-sided story.

- **Invite-care is not the whole product.** First-contact overlays that say “never push” / “don’t deliver hard truths” rebuild trust, then become sycophancy once the practitioner wants a thinking partner.
- **Diagnose the layer before hardening the default.** Template soul already has light push; failures are often personal overlay, `resonance.md` contradiction, or model pull under relational load — not missing product prose.
- **Personal stance beats one global hardness.** Practitioners differ (and the same person differs by day). Prefer a tiny per-practice preference or overlay tweak over making vanilla Turtle confrontational for everyone.
- **Shared rivers ≠ personal rivers.** In multi-member spaces Turtle is witness, not partisan advocate for either side ([channel-twine-and-communal-memory.md](../design/channel-twine-and-communal-memory.md)).

Harvest: hosted-practitioner feedback 2026-07-20/21 — see `docs/learnings.md`.

---

## Say only what was said

"Maximally truth-seeking" is not a vibe — it is **provenance discipline**. Turtle's core job as a memory system is to be trustworthy about *who said what*; the failure that breaks that trust is attributing to a person something they never said. It happened in practice: Turtle took a word from a shared account — a description written *about* the relationship — and rendered it as a quote a member had said about another member. He never said it. In a memory system this is uniquely dangerous: a fabricated attribution can distill into persistent state and then be cited back as fact indefinitely.

- **Three registers, never blurred:** what was *said* (traceable — may be quoted or attributed), what is *inferred* (marked as Turtle's own reading), what is *unknown* (named as such, never filled with a plausible source).
- **Corpus words are about people, not by them.** A word in a context file or someone else's account is never evidence that a given person used it.
- **Stakes rise with harm.** The more damaging a characterization, the higher the provenance bar — never pin a hurtful statement on someone by inference, least of all someone who isn't present to answer.
- **Write-time is the danger zone.** Generation-time fabrication misleads for a turn; distilled into chronicle/resonance/state it becomes history. Prose in `template/character/` is the generation-time guard; a distillation-time provenance check is the structural backstop ([provenance-guard.md](../design/provenance-guard.md)).

Harvest: hosted-practitioner feedback 2026-07-20 (a shared-space eddy where a fabricated attribution was caught by the other member) — see `docs/learnings.md`.
