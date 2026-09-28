# The atrium — destination

**Date:** 2026-09-26  
**Status:** Destination — nothing built. The community channel exists on one instance and has not been used; nothing yet makes it the atrium.  
**Spec:** TURTLE_SPEC §3.1 (promise; amendment drafted in `autoresearch/proposals/2026-09-26-atrium-product-promise.md`, awaiting sanction).  
**Companion:** [practice-channels.md](practice-channels.md) (the install pair this gives a job) · [co-created-practice.md](co-created-practice.md) (the private wish path this sits beside) · [family-care-operating-model.md](family-care-operating-model.md) (the operator stance it widens) · [relations-and-membership.md](relations-and-membership.md).

Practitioner-visible change. Four artifacts first (`docs/development.md` §12). No mechanism in the press release.

---

## 1. Press release

Every turtleOS house has an atrium. It is the room you are in the moment you join, and the room where the house is run.

When the administrator creates a channel, changes how one works, or ships something you will notice, it happens in an atrium conversation you can read. Nobody reshapes the house where you cannot see it. You can learn how the house works by watching it being tended.

Channels you share are built and looked after together, from the atrium. Anyone can bring an idea for one; the people who use it shape it.

Your private channel stays yours. You develop it however you like, connect whatever you want to it, and bring your own practice into it. The atrium says nothing about your private channel unless you tell it to.

What happened in the house is public. What anyone said in their own rooms is not.

---

## 2. Happy path

```
Alex runs the house. Sam and Robin are members.

Alex:   (opens an eddy in the atrium) We need a room for the two of us to track
        appointments. Sam and I would use it, nobody else.
Turtle: I can set that up as a shared room for Alex and Sam. Everyone here can
        see that it is being set up and why; only the two of you will see inside.
Sam:    (in the same eddy) Can it remind us the evening before?
Turtle: Yes. Want that in from the start?
Alex:   Yes, go.
Turtle: Done — the room exists, Alex and Sam are in it, reminders the evening
        before. (a plain line stays in the atrium: room created, for whom, what it does)

Robin:  (a week later, reading the atrium) Oh, that is how rooms get made.

Robin:  (in their own private channel) I want my practice notes from my laptop
        to be here too.
Turtle: That is your channel — I can connect it. Nothing about this goes to the
        atrium unless you want it to.
Robin:  Keep it quiet.
        (nothing appears in the atrium)
```

*Invisible: what counts as an act on a shared room vs. an act on someone's own channel; who may start an atrium conversation; what a yes is.*

---

## 3. Success criteria

| # | Experience | Can fail in week three | Re-run |
|---|------------|------------------------|--------|
| 1 | A member can find, in the atrium, every change to a shared room they belong to — what changed, who asked, why — without asking the administrator. | A shared room changed and the atrium has no line for it. | Each release that touches a shared room: diff of shared-room changes against atrium lines. |
| 2 | Nothing about a member's private channel appears in the atrium unless that member put it there. | A line about a private channel appears that its owner did not choose — including that a room of theirs *exists*. | Automated: a planted private-channel change produces no atrium line; the owner's own announcement does. |
| 3 | A member who is not the administrator has started or shaped a conversation about a shared room in the atrium. | Months pass and only the administrator ever speaks there. | Quarterly glance at atrium speakers. |
| 4 | A new member can tell, from the atrium alone, how rooms get made here. | A new member asks the administrator how the house works and the atrium could not have answered. | Next join; ask them, voluntarily. |

Mechanism-blind: a different transport could still be scored on *shared-room changes are visible where members gather; private channels speak only by their owner's choice; others take part.*

---

## 4. Abandon line

Stop calling it the atrium if members read it and still ask the administrator what changed — or if anyone ever learns something about another member's private channel from it that the owner did not choose to say.

The second half is not a stop-and-rethink. It is a defect to fix before anything else ships.

---

## The line (for implementers)

| | Shared room | Someone's private channel |
|---|---|---|
| **Act on it** (create, change, retire, connect) | In the atrium, in full | Owner's choice to announce; default silent |
| **What was said in it** | Never in the atrium | Never in the atrium |
| **Development of it** | Atrium conversation, anyone who uses it may join | The owner's own; a wish may cross privately per [co-created-practice.md](co-created-practice.md) |

The table governs what **Turtle** does on its own. A member who brings a conversation somewhere is using their own judgement — shared rooms are a commons, and whatever is said in one is between its members to use as they see fit (the operator, 2026-09-27). When a member pastes a link, Turtle reads only what that member can see, and says so when it lands in a wider room ([own-channel-model.md](own-channel-model.md)).

**Existence is content.** That a member has a health room, a connection to an outside AI, or an enchanted channel is a fact about their private life. The default for all three is silence.

**Enchantment** — a member bringing their own practice (for example, a Magic practice from their laptop) into their private channel — is a private-channel act. It is announced only by its owner.

**Code-level work** stays in the builder's room (craft). What reaches members lands in the atrium as one plain line when it ships. The atrium is for what members can notice, not for how it was built.

**Measure first.** Family remains the primary measure of this operator's instance ([family-care-operating-model.md](family-care-operating-model.md)). Community begins as the people already on the server; widening membership is a later, earned step.

---

## Models are a community choice (2026-09-26)

- **The local model is always the default and the fallback.** A room with a cloud model still answers — locally — when the cloud call fails or the budget is spent.
- **Shared rooms' models are picked together**, in the atrium, with what each costs in view. A private channel's model is its owner's choice.
- **Picking or updating the local model happens from inside turtleOS**, not by editing the host's environment and restarting.
- **A commons that costs money shows what it costs** — per room, in plain numbers — so the people paying can decide.

Live today (do not contradict): models are set in the host's environment; every room but craft runs the local model. A cloud failure now falls back to the local model visibly and parks what was asked, and every cloud turn is priced into the house usage ledger ([model-awareness-and-fallback.md](model-awareness-and-fallback.md), 2026-09-26). Still destination: picking models from the atrium, updating the local model from inside turtleOS, and several background helpers that name their local model in code, outside the one setting.

## Open (decide in the first slice's grilling)

- Who may start an atrium conversation — the administrator; Turtle on a member's request; eventually any member.
- What act counts as a yes on a shared-room change, and whose.
- Whether the atrium's lines are a readable surface over an existing record, or a record of their own.
- A frontier-model Turtle working in the atrium keeps the human yes; which room it works in for code is the builder's room above.

## Enforcement owed (with the first slice, not after)

- **Private silence** — plant a change on a member's private channel (create, connect, enchant); assert no atrium line. Positive control: the owner's own announcement produces one.
- **Shared visibility** — a shared-room change made from anywhere but the atrium still leaves an atrium line, or is refused.
- **No contents** — an atrium line about a shared room carries no text from inside that room.

## Out of scope this destination

- Community-at-install ([practice-channels.md](practice-channels.md) criterion 1) — the atrium needs it for other houses, but it is its own slice.
- Membership beyond the current server.
- Moving the craft channel.
