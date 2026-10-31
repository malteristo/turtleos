# Tending the house — destination

**Date:** 2026-09-28
**Status:** Destination — sanctioned, nothing built. The build waits behind the first enchantment (chapter 73).
**Spec:** TURTLE_SPEC §15 (multi-practitioner). Amends atrium private-silence for acts of power only.
**Companions:** [atrium.md](atrium.md) · [relations-and-membership.md](relations-and-membership.md)

**His words, 2026-09-28.** Many people can hold admin on turtleOS. One user owns the Discord server. Transparency is how the house holds people with more power accountable: turtleOS makes admin acts visible to all. `.` on the four lines, calibrated by that sentence.

---

## 1. Press release

Some members of a turtleOS house can tend it. They can open a shared room, change who belongs in one, invite a person, or retire a membership. Every member can see that they did — who, what, and when — in the room where the house is run. A member who was not there can still find it later.

Most members cannot tend the house. They live in the rooms they belong to. Their private channel stays theirs, and their own work there stays quiet.

One person holds the house. Holding it is heavier than tending it. When that weight is used on a room the holder does not belong to, the house sees the visit: who went, whose room, what kind of act. The house does not see what was said there.

Anyone the house designates can tend. The record names them one by one. Power that leaves no trace is a broken house.

---

## 2. Happy path

```
Sam and Robin tend the house. Alex holds it. Jordan is a member and tends nothing.

Sam:    (where the house is run) Robin and I need a room for appointments. Just us.
Turtle: Done. The room is there, for Sam and Robin.
        (a line stays where every member can read it:
        Sam opened a shared room, appointments, for Sam and Robin.)

Jordan: (the next day, reading) Sam did that. I can see it was Sam.

Sam:    (from their own account, looking for Jordan's private channel)
        It is not in the list.

Alex:   (holding the house, repairing a permission on Robin's private channel)
        (a line stays, visible to every member, including Robin:
        Alex acted on Robin's private channel — permissions.
        Nothing Robin wrote appears in the line.)

Robin:  I see you were in my room.
Alex:   The repair is in the line. The visit is not something you hear about only from me.
```

*Invisible here: how a designation is stored, how a line is written, how the holder is one Discord user.*

---

## 3. Success criteria

| # | Experience | Can fail in week three | Re-run |
|---|------------|------------------------|--------|
| 1 | A member who does not tend the house never sees another member's private channel. | They can open it. | Each new member, and after any permission repair: their visible rooms are only the ones they belong to. |
| 2 | Two members can tend the house in the same week, and a third member can tell their acts apart. | The second tender cannot act, or both acts wear one name. | Two tenders, two acts, read by someone who did neither. |
| 3 | Every house act — a shared room opened, membership changed, someone invited or retired — can be found by any member, with who did it, without asking them. | The room changed and no member can find the act. | Each such act: the public record has a line, or the act is refused. |
| 4 | When someone with power to tend or to hold the house touches a private channel they do not belong to, every member can find who, whose channel, and what kind of act, and cannot find what was said there. | The touch is invisible, or the words appear in the public line. | A planted touch. Assert a public line. Assert the line has no message text. Positive control: the channel owner's own work there still leaves no line. |
| 5 | Exactly one person holds the house. | A second person can see every private channel. | Count of identities that can open every private channel. The count is one. |

Mechanism-blind: another transport could still be scored on *tenders are distinguishable, house acts are findable by every member, a private-channel visit by power is visible as a visit, and only one identity can see every room.*

---

## 4. Abandon line

Stop if a person who tends the house can read a private channel they do not belong to and the house has no line for that visit. The power is back, and the accountability is missing.

Stop if a public line carries what was said in a private channel. Accountability has eaten the room.

Stop if a second person can see every private channel. The house has grown a second holder.

---

## The line (for implementers)

Many members may be marked able to tend (`admin` on their own membership). One Discord user owns the server. Those are different facts. His question on 2026-09-28, answered here: yes.

The Discord permission called Administrator shows every channel and ignores channel privacy. Giving it to each tender would restore the god-view, and the public line would be a story told after the reading. Tenders act through turtleOS. The bot performs the change. The line is part of the act: an act with no line is a failed act.

Today `admin_discord_ids` is written onto every claimed home with view, history, and manage (`river_keys._claimed_overwrites`). That grant is the eyes. This destination splits it from the right to tend.

The server owner can open any channel in the Discord app. turtleOS does not see that browsing. The public line covers acts that pass through turtleOS. The owner's silent reading is the remaining hole, which is why that account is rare and why the operator's daily user is an ordinary member.

A member's own work in their own channel stays silent ([atrium.md](atrium.md)). An act of power on a channel the actor does not belong to is the exception, amended 2026-09-28.

---

## Enforcement owed (with the first slice, not now)

- A non-tender's overwrites exclude other homes. Positive control: their own home is visible.
- A tending act that writes no public line fails. Positive control: an act with a line passes.
- A line about a private-channel touch contains no message body. Positive control: a fixture message is absent from the line.
- Two tenders produce two names.
- One holder is an instance check, not a registry flag: the live guild has one owner, and that owner is not the operator's daily user. A schema field alone does not prove it.

## Out of scope

- Building it. Chapter 73 stays the waiting chapter.
- Transferring this server's ownership in this sitting.
- A TURTLE_SPEC amendment — owed when a slice is sanctioned.
- One shared login among the tenders. Discord would see one person, and changing the password would lock all of them out together.

## Decided (2026-09-28)

1. Many tenders, one holder of the house.
2. Transparency is the accountability. Acts of power are visible to every member.
3. The public line names whose private channel was touched and what kind of act. It carries nothing that was said.
4. The operator's daily account is a member. The build waits behind chapter 73.
