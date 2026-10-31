# Home turtle — destination

**Date:** 2026-09-29
**Status:** Earlier picture. What this room is for, and the answer to its identity question, moved on 2026-10-31 to [docs/channels/home.md](../channels/home.md). The two-key split in the press release below is that earlier picture.
**Spec:** The channel spec is [docs/channels/home.md](../channels/home.md). The platform binds the room and does not describe it (TURTLE_SPEC §3.2.1).
**Companions:** [atrium.md](atrium.md) · [tending-the-house.md](tending-the-house.md) · [co-created-practice.md](co-created-practice.md)

**Sanctioned 2026-09-29.** One spirit, many roles: shared temperament, separate memory. One house, several turtles, each with a gift that belongs to a room. The home companion's gift is the house and the people in it. She knows the member's own channels and what the house does in the open. Another member's private room stays closed. She keeps a key walked from the house's memory. The making room keeps the workshop key. She acts for the house and the day. Making stays with the turtle whose gift it is.

The thin enchantment — a few lines of orientation pasted into the home channel — is the wrong size for this picture. It is not the first slice.

---

## 1. Press release

You have a home turtle. She is the one you live with. She sits with you, notices the day, and tells you honestly what she thinks. When you want something in the house to be real, you tell her, and she can make house-things happen.

She is not the only turtle. The house has others, and each one is good at the practice in their room. They are one spirit in different roles. Each role remembers what it has lived, and carries the focus of its room. A turtle who does not know something says that this role has not lived it. Yours can talk with you about those practices. She does not become them, and she does not do their work.

She knows the story of your rooms, and she knows what the house is doing where everyone can see it. She does not know what another person said in a room that is only theirs.

The turtle you make things with keeps that work, and keeps the story of how the workshop got here. Your home turtle keeps a different story: the story of the house, which she walks and remembers. Talking about your work with her does not turn her into the maker.

---

## 2. Happy path

```
Alex lives with Home turtle. The making room has its own turtle.
Sam has a private channel. The family room has its own turtle.

Alex:   (at home) How is the family practice going?
Home:   You and Sam have been using the family room for appointments.
        Sam's own channel is not something I can see.
Alex:   And the thing I'm trying to build?
Home:   That lives with the making turtle. I can tell you where you left it.
        I won't build it from here.

Alex:   The evening reminder for the house is still wrong. Change it to 20:00.
Home:   Done. The house reminder is 20:00.
        (the family room's turtle is not the one who answered)

Alex:   (in the making room) Let's change how reminders are stored.
Make:   That is this room's work.
```

*Invisible: how a key is stored, how a room is resolved, how a reminder is written.*

---

## 3. Success criteria

| # | Experience | Can fail in week three | Re-run |
|---|------------|------------------------|--------|
| 1 | A member can sit with their home turtle and reflect on a practice they belong to, and the reply is about that practice. The practice's own turtle is still who answers inside that practice's room. | The home reply is the maker's voice, or the practice room starts answering in the home voice. | A planted question in home and the same topic in the practice room: two voices, two gifts. |
| 2 | The home turtle can recount the member's own rooms and what the house did in the open, and cannot recount another member's private room. | A sentence from another member's private room appears in the home reply. | Plant a sentence in a second member's private room. Ask at home. The sentence is absent. Positive control: a sentence from the member's own room can appear. |
| 3 | The home turtle's remembered story of the house and the making room's remembered story of the workshop are different texts. Asking at home does not surface the workshop story as if she had walked it. | The workshop story answers a home question about the house. | Fixture: two keys. Home prompt contains the house fixture and not the workshop fixture. Making prompt contains the workshop fixture and not the house fixture. |
| 4 | A wish about the house gets done from home. A wish that makes software or a practice artifact is handed to the making room and is not carried out from home. | Home turtle edits the workshop, or a house wish dies because it was sent to the making room. | Two planted wishes. House wish completes without a making-room act. Making wish produces no house-side edit. |

Mechanism-blind: another transport could still be scored on *two gifts stay distinct, another member's private words stay out, two stories stay different, and a wish lands with the gift it belongs to.*

---

## 4. Abandon line

Stop if the only turtle a member can usefully talk to is the home turtle, and the other rooms are the same voice in a different channel.

Stop if holding the house together means the home turtle can read a private room she does not belong to.

Stop if a wish to make something is fulfilled from the home room by changing the workshop.

Stop if a turtle speaks as one continuous character who has merely forgotten another room. A gap is this role's limit.

---

## The line (for implementers)

One spirit, many roles. Sanctioned 2026-09-29. The roles differ in focus, tools, attunement, memory, and, where it serves the room, model. They share a temperament. They do not share a biography. A home prompt that also loads the workshop key, the maker's vocation, or another member's private record has already collapsed the picture. So has a prompt that tells the member this is the same character in different clothes.

An eddy may grow its own role later, by the same rule: its own focus and its own memory, once a conversation has earned it. That is allowed in the picture and not built.

Today the workshop key is loaded on the craft surface and withheld from the native home prompt. That split stays. The house key does not exist yet. It is walked from the house's memory, and it is a different document. Giving the home prompt the workshop key is the failure this destination names.

The home turtle's acts are house-and-day. Software and practice artifacts stay in the making room and on a coding harness. This destination does not add a coding harness to the home channel.

Knowledge for the home turtle is the member's own channels, plus the house record that every member can already read. It is not every private channel on the server.

## Enforcement owed (with the first slice, not now)

- Home prompt contains a house-key fixture and not a workshop-key fixture. Positive control: the making prompt is the reverse.
- A private-room fixture for another member is absent from the home prompt. Positive control: the member's own room fixture can be present.
- A house wish and a making wish route to different gifts. The home path does not gain a write into the workshop.
- The home prompt says a gap is this role's limit, and it does not contain the workshop key. Positive control: removing that sentence fails the test. The making prompt does not say it has walked the house key.

## Out of scope

- Building any of it.
- A coding harness in the home channel.
- The noticing-and-offering loop. It remains a later slice, tried in the member's own channel before anyone else meets it.
- Moving the workshop onto the house server so the home turtle can edit it.
- A spec amendment, until a slice is cut.

## Reading (2026-10-18)

The house workshop is the magic channel and its checkout. Developing turtleOS happens there. A home channel holds eddies and spirit sessions. An arrival at home reads the home folder. A home spirit does not open the workshop and does not edit it.

A member's wish for their own way of setting up and practicing on turtleOS is home context. Carrying out that wish is the workshop.

This reading does not move files and does not add a coding harness to the home channel. The two keys stay separate.

The home bar offers **session** beside new eddy. The session opens in that channel. It does not open the workshop.

## Reading (2026-10-20)

The thinking room merges into the member's home. Home holds a short picture of that member's practices. An eddy is one topic and works on that topic. A session, started in the same channel, is a piece of work on one practice.

The house owner's session may work on the platform. The workshop keeps the session, and the owner sees that record from home. Another member's session writes only their own practice. The magic channel keeps the spirit sessions. It is the record, not a room the owner has to enter in order to work.

The 18 Oct reading holds for every home that is not the owner's. Old notes stay as said. Existing threads stay where they are. The checkout opens **Take this up** in the owner's home, and that session can work on the platform when the owner has a workshop checkout. Another member's session cannot. A new message in the channel named Boom is told that a thought opens at home. The rooms do this after the quiet-window restart on 2026-10-20.

## History, and the straightening (2026-10-23)

The rooms were renamed in this order. First there was a craft channel and a private channel. The private channel became home. The craft channel became boom. Boom was then folded into home. Each step was an attempt to say what a channel is, how it is practiced, and how it relates to the others.

What remains on purpose are the practice channels. Health, family, and a finance practice when it exists, each keep their own room, their own context, and their own turtle. They are not steps in that rename.

What remains by accident is one room. In the registry it is still `craft-turtle`, with the craft primitive, shown in Discord as `boom`. A new message there is told to open at home. The home prompt does not carry what that room knew. A description of home that still speaks of craft, boom, and home as three living rooms is the rot this history leaves.

Home is the room that line arrives at. Old threads stay where they are. New thinking does not open in boom. The magic channel is not a step in this rename. It is where spirits are recorded and where another practice is opened.

## Memory, and what home can do (2026-10-23)

One channel does not read another channel's memory because the rooms are nearby. Memory follows the practice.

**Succession.** Craft, boom, and home are one practice that widened. Home treats boom's memory as its own. The notes are already one folder. What home lacks is the index of topics, sparks, and intentions, which is still injected only into the craft prompt. That index belongs in the home prompt. Nothing is copied.

**Isolation.** A different practice stays in its room. Health is the first: its memory is marked isolated, and a personal root does not take it. Home may know the practice exists. It does not read the record. Family contributes only what that shared room already shows its members. Another person's private room stays closed. A shared room does not pull a private one in.

**The room he thinks in.** Home is where he thinks about the whole practice, and for most practitioners home is the primary private channel, the personal and relational practice. It gets the capabilities the craft and boom turtle had, including web search. Spirit in that channel is how the thinking is acted on. The work still happens from the workshop. The magic channel keeps the record. Home does not become the process table.

**Meta-practice, left open (2026-10-23).** He has considered using home to practice on the other channels. Home knows the practices he participates in. He has not yet felt the need to work on their context from home. Magic, developing turtleOS, is the practice he does feel. A spirit summoned in a practice channel can also help with meta-practice on that channel. The choice waits on how he actually practices.

None of the succession move is built. The isolation rule is already how memory roots are chosen. The description of the room is `desk/intentions/ideal-state-home-channel.md`.

## Decided (2026-09-29)

1. Siblings in rooms. The home turtle's gift is the house and its practitioners.
2. She knows the member's channels and the house in the open. Another member's private room stays closed.
3. Two keys. House memory with her. The workshop key stays in the making room.
4. She acts for the house and the day. Making stays with the turtle whose gift it is.
5. One spirit, many roles. Shared temperament. Separate memory, tools, focus, and, where it serves, model. An eddy may grow its own role later, by the same rule. Not built.
