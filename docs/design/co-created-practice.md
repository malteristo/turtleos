# Co-created practice — Wizard of Oz, with the curtain visible

**Status:** Draft 2026-09-24 · practice-design approach, independent of transport
**Spec reference:** TURTLE_SPEC §20 (self-development), §15.5 (multi-practitioner data flow)
**Related:** `docs/design/intentions-offered-not-asked.md`, `docs/design/role-needs.md`, `docs/chapters/design-hosted-river.md`

---

## 1. The approach

A member's practice is shaped by what they ask for, not by what someone designs for them. The member talks to their Turtle:

> *"Turtle, I want you to be able to do X."* · *"I want to be able to do X."*

and the system works out how to enable it in their practice.

At first a person does that work behind the scenes: a **practice researcher**, typically the family administrator. They act as QA and user-experience researcher, think about what the practice should look and feel like, and build what the wish needs. The member just talks to their Turtle. As the practice matures, the researcher takes themselves out of the loop, and Turtle practises the personalised practice with the member on its own.

This is the Wizard of Oz method from HCI research, with one change.

## 2. The curtain is visible

In a classic Wizard of Oz study the participant does not know a person is behind the curtain. Here they do. The member is a **voluntary co-creator**, never a test subject:

- The member knows who builds behind "Turtle, I want X".
- The member knows exactly what crosses to that person: **the wish, in the member's words, and nothing else.** Their river, their health rooms and their notes are not read by the researcher, as the hosted river already declares.
- The member sees every wish's status in their own river.
- Not asking is a valid answer. A wish nobody spoke is not a gap to fill from observation.

What the researcher observes is what the member asks for and how it feels when it arrives, not the member's private material.

## 3. The wish path

| Step | Where | What |
|---|---|---|
| Spoken | member's river or any of their rooms | Turtle recognises a wish ("I want…", "can you…", "I wish Turtle could…") and offers to record it; or the member says `!wish …` |
| Recorded | member's root, `state/wishes.jsonl` | `{id, ts, words, room, status: open}`. The member's words, verbatim; Turtle's paraphrase is never the record |
| Crossed | researcher's craft surface | **the words and the id only.** No room excerpt, no note, no context |
| Built | behind the curtain | whatever the wish needs: attunement, a capability, a flow, a setting |
| Returned | member's river | status `doing` → `done` with one plain sentence about what changed; the member confirms or says it is not it yet |
| Fulfilled without the wizard | Turtle, directly | a wish Turtle can enable itself (a setting, an existing capability, a flow it already has) is marked `self` and never crosses |

## 4. The measure

**Wishes fulfilled without the researcher ÷ wishes spoken**, per member, rolling 90 days. The approach succeeds when this rises. It is the out-of-the-loop measure the method exists for.

Deliberately not measured: how often the member talks to Turtle, time in practice, number of wishes. All of those rise and fall for reasons unrelated to whether the practice fits.

## 5. Enforcement owed

- **Crossing carries words only** — plant a fact in the member's root; assert the crossed card contains the wish words and not the fact.
- **Verbatim record** — the stored `words` equal the member's message text for `!wish`; a Turtle-offered record stores the member's sentence, not Turtle's summary.
- **Return reaches the member** — a status change to `done` posts in the member's river; positive control: a status change on another member's wish does not.
- **`self` never crosses** — a wish marked `self` produces no card.

## 6. Relation to other access points

The approach works through any surface the member already uses. The MCP access point (`docs/design/mcp-access-point.md`) is one enabler. It lets the member practise from their own AI client with their own model, which may be what a wish asks for. It is not part of this design, and this design does not depend on it.
