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
| **River** | Acts only | Creates thread anchor; no Turtle prose |
| **Turtle** | Silent | Dialogue, presence, tools |

Practitioners distinguish **who is acting** by app name and avatar. Single-bot mode is a migration fallback, not the target native UX.

---

## Minimal chrome in vanilla eddies

Native eddies ship without Magic-era control panels, model pickers, or config cards on entry. The shell stays quiet until the practitioner speaks; Turtle’s first reply may be preceded by a compact presence embed.

---

## Timeline owns operational trace

When the shell does work on the practitioner’s behalf (fetch a URL, load a flow file, checkpoint a session), **progress and outcome belong on the timeline** — embeds and system lines — not as fetch prose in Turtle’s conversational voice.

Link reading is the reference implementation: [link-reading.md](link-reading.md). Session capture: [sessions.md](sessions.md).
