# Your own channel, your model, the rest of the house in view — destination

**Date:** 2026-09-26  
**Status:** Destination, first slice building the same day.  
**Spec:** TURTLE_SPEC §3.1 (the practitioner owns their practice), §8.1 (models by role).  
**Companions:** [atrium.md](atrium.md) (models are a community choice; the privacy line), [model-awareness-and-fallback.md](model-awareness-and-fallback.md).

Practitioner-visible change. Four artifacts first (`docs/development.md` §12).

---

## 1. Press release

Your private channel runs the model you pick. The house default is the local model; if you want a frontier model for your own practice, you say so in your channel and from then on that is what answers you there.

From your private channel you can bring in what happened elsewhere in the house — one message, one eddy, or a whole channel's recent activity — by pasting its Discord link. Turtle reads it and talks it over with you on your channel's model, whatever model that other room runs on. You can bring in anything you can already see. What you do with it is yours to judge; Turtle tells you when you bring something into a room where some people couldn't see it before.

---

## 2. Happy path

```
Sam, in her private channel:

Sam: !model
Turtle:  This channel runs Gemma 4 31B (local, on the house machine).
         Good for: conversation, reflection, recall, short drafts.
         You can pick: `!model sonnet` (Claude Sonnet 5, cloud) ·
         `!model opus` (Claude Opus 5.5, cloud) · `!model local`.
         Cloud models are paid from the community account.

Sam: !model sonnet
Turtle:  This channel now runs Claude Sonnet 5. It reads what you say here
         on Anthropic's servers. `!model local` goes back.

Sam: What happened in family this week? https://discord.com/channels/…/<family>
Turtle:  [Read #family — 6 eddies, 84 messages since Monday]
         Three threads carried most of it: …

Sam: And this one about the Antrag? https://discord.com/channels/…/<eddy>
Turtle:  [Read eddy "Antrag Unterlagen" — 23 messages]
         …
```

---

## 3. Success criteria

| # | Experience | Can fail in week three | Re-run |
|---|------------|------------------------|--------|
| 1 | The owner of a private channel picks its model from inside the channel, and it answers on that model from the next message — in the channel and in every eddy under it, including eddies opened before the change. | The pick is accepted but an older eddy still answers on the previous model. | Automated: a pick changes the model resolved for an existing eddy. Live: her first `!model`. |
| 2 | Nobody but the owner can change a private channel's model. A health channel is private to its owner even with a support person in it: the owner picks, support cannot, and the picker says what the provider would read. A shared room's model is its members' choice: any member changes it from inside the room, the room is told who did, and nobody picks for a room they are not in. | Someone else's `!model` changes her channel; her support person changes her health channel's model; a non-member changes a shared room, or a member changes one silently. | Automated: a non-owner pick is refused and nothing is written; health owner picks, support refused; a health turn answers on the pick; shared: member picks and is named, non-member refused, an eddy change is also said in the room. Mutation-checked. |
| 3 | A pasted link to a message, an eddy, or a whole channel is read and talked over — on the destination room's model. | A channel link reads nothing; a long eddy is cut to a local summary in a frontier room. | Automated: channel link returns recent eddies; frontier budget is larger than local. |
| 4 | A link is read only if the person who pasted it can see its source. Anything they can see, they may bring anywhere; when the room it lands in is wider than its source, the read says so, to the room and to Turtle. | Someone pastes a link to another person's private channel and Turtle reads it out — or a member is refused what they could have copied and pasted. | Automated: unreadable source refused; a readable source into a wider room is read and flagged. Mutation-checked. |
| 5 | The practitioner always knows which model is reading. | A frontier-model reading of shared material with no sign which model read it. | Automated: model named in the prompt (existing); pick confirmation names the provider. |

---

## 4. Abandon line

Stop calling pull-in safe if Turtle ever reads out something the person who asked could not see themselves — or if a member learns only afterwards that what they brought in reached people outside its room.

---

## The shape (for implementers)

- **A room's model is resolved at every turn**, not stamped when an eddy opens: an explicit per-eddy override (`!thread --model`) → the room's pick → the room's default (craft → `CRAFT_MODEL`, otherwise the local model). A stamp written at spawn is a default, not a choice, so it no longer pins an eddy to the model of the day it opened.
- **Picks live in the house** (`house/room_models.json`), written only through the owner check. Authority comes from the resolved primitive: solo rooms (home, private, craft) are their member's; health is its subject's; shared rooms (the atrium included) are their members'. A room is changed from inside it (the operator, 2026-09-27: picking from the atrium would show every member rooms they are not in).
- **The pull guard** runs before any Discord read, in dialogue and in craft intake: the puller can view the source, per Discord's own permissions for that member. Unknown fails closed; a refusal names no room. That is the whole guard — it stops the bot's reach standing in for the person's, and nothing more.
- **Awareness, not restriction** (the operator, 2026-09-27): a shared room is a commons, and what a member does with what was said there is their judgement — they could copy and paste it anyway. When a read lands in a room where someone cannot see the source, the read is flagged: a heads-up on the visible read card, and a note to Turtle so it knows who is reading.
- **Budget follows the reader.** A frontier room reads more of a thread and does not pre-summarise it with a local model; a local room keeps the current caps.

## Other people's words and the cloud

When she pulls a shared room into her frontier-model channel, the other members' words from that room are read by the cloud provider. **Settled** (the operator, 2026-09-27): permitted, at each member's discretion — she can already read and quote them, and every reply names its model. Members bring good judgement; turtleOS does not try to enforce it, and could not succeed if it tried.

## Deliberately not in this slice

- Picking the local model itself from inside turtleOS.
- "Recent activity across all my rooms" without a link — the link is the ask; a gathering tool can follow when practice shows the need.
