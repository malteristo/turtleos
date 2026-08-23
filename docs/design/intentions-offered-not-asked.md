# Intentions — Offered, Not Asked

**Prepared:** 2026-08-05 · **Status:** destination only — press release, happy path, criteria, abandon line
**Not yet:** design doc, slices, code. Per [development.md](../development.md) §12, these four ship first.

---

## 0. Where this comes from

Two facts met on the same day.

The operator said he forgets to press `!checkpoint`, *including on conversations that mattered*, and drew the rule from it: **the twine has to hold on its own, and any deliberate act should enrich a record that already works rather than be the thing that starts it.**

The same morning's audit found the alive layer had been waiting three weeks for a button nobody pressed, while three consumers read a frozen snapshot as the present. Same shape, one layer down. That half is fixed: themes now enter on their own and decay on their own, and the layer no longer speaks to a turn.

This document is the rung above. An intention is not a topic — it is something a member has decided is theirs. The question is how one comes to exist without anybody being asked to do homework.

**Two boundaries, settled before design:**

1. **The offer interrupts once, quietly, then never again for that thread.** A member who forgets to act cannot be served by a surface that waits to be visited. But an offer that returns is nagging, and nagging is what makes a member stop reading. One shot per thread, ever.
2. **Intentions are personal.** They are offered only in a member's own river, and a shared space never holds one. A room accumulating intentions "on behalf of" its members is precisely the ventriloquism the witness law forbids (charter §3.3). A room can hold topics. An intention belongs to a person.

---

## 1. Press release

> **Your practice notices what you keep coming back to.**
>
> Some things you talk about once. Others you find yourself returning to — three weeks apart, from a different angle, without ever deciding to. Those are usually the things that matter, and they are the hardest to see from inside your own week.
>
> turtleOS now notices them, and says so. Once, when it is fairly sure, in your own room: *"You've come back to this four times since the middle of July. Is this something you're working on?"*
>
> If it is, say so, and it becomes yours — written down where you can read it, change it, or set it down later. If it isn't, say no, and you will not be asked about it again.
>
> Nothing is required of you for this to work. You do not tag conversations, keep a list, or run a weekly review. If you *want* to name something directly you can, and it goes in the same place. And when something you named stops showing up in how you actually spend your time, your practice will tell you that too — not as a failure, just as a fact you might want to know: *"You haven't come back to this in five weeks. Still yours?"*
>
> It reads what you already do. You do not feed it.

*(Mechanism named nowhere above, deliberately. If a paragraph here could only be true of one implementation, it is written wrong.)*

---

## 2. Happy path

One member, one arc, start to finish. House style: [continuity-engine-and-substrate.md](continuity-engine-and-substrate.md) §3.5.

**Week 1 — an ordinary conversation, in an eddy.** Nothing happens that the member sees.

> **Member:** I keep thinking the family should have somewhere the unresolved stuff can just sit.
> **Turtle:** Somewhere it can stay open without someone having to carry it?
> **Member:** Right. Not a to-do list. More like — this is unresolved, and that's fine.

**Week 2 — a different conversation, different framing.**

> **Member:** The camping thing came up again and nobody answered it. It just evaporated.
> **Turtle:** Same shape as the place-for-unresolved-things you were describing a couple of weeks ago?
> **Member:** Huh. Yeah, it is.

Turtle can say this because the room's own recent notes are in front of it. Ordinary retrieval. Still nothing offered.

**Week 4 — it comes back a fourth time. Now the offer, once.**

> **Member:** …and honestly that's the same problem again.
> **Turtle:** It is — and I want to name something before we go on.
>
> This has come back four times since the middle of July, in four different conversations. Places for unresolved things, the camping question, the cat logistics, and now this.
>
> That looks less like a topic and more like something you're working on. Do you want me to hold it as one?
>
> **Member:** Yes.
> **Turtle:** Held. I'll keep it in view when it's relevant, and I'll tell you if it goes quiet for a while.

**Any time — the member wants to name one directly.**

> **Member:** I want to work on getting the family to actually talk about money.
> **Turtle:** Held. Same shelf as the other one.

No difference in what results. One arrived by being noticed, one by being said.

**Week 12 — the check that runs the other way.**

> **Turtle:** One thing before you go — the money conversation hasn't come up in five weeks. That's not a nudge; sometimes a thing is finished and nobody says so out loud. Still yours, or can I set it down?
> **Member:** Set it down. We actually sorted it.
> **Turtle:** Done.

**And the one that has to work too — the offer is wrong.**

> **Turtle:** …Do you want me to hold it as one?
> **Member:** No, that's just work stuff bleeding in.
> **Turtle:** Understood — I won't raise it again.

And it does not. Not next month, not from a different angle.

---

## 3. Success criteria

Experience-shaped. Each passes the three tests in [development.md](../development.md) §12 — mechanism-blind, failable in week three, and with a named re-run.

**S1 — The offer lands as recognition, not as a suggestion.**
A member's reaction to an offer is *"huh, yes"* rather than *"why is it asking me that."* Measured by what they say next, in their own words, in the transcript.
*Re-run:* every offer, scored at the monthly harvest. There are few enough to read all of them.

**S2 — A member who does nothing still has a practice that knows what they are working on.**
Take a member who has never typed a command. A month in, the intentions held for them are ones they would recognise as theirs if read aloud.
*Re-run:* asked directly, once a quarter, of one member who is not the operator.

**S3 — Nothing held has gone quiet unnoticed.**
No intention sits in the record, unmentioned, past the point where the member has visibly stopped returning to it. The failure this prevents is the alive layer's own: state that outlives its truth because nothing was watching it age.
*Re-run:* the check is itself part of the mechanism, so this is scored by *its* absence — any intention older than the quiet threshold with no surfaced check is a defect.

**S4 — A declined offer stays declined.**
Zero repeat offers for a thread a member has said no to, across all time.
*Re-run:* continuously; a repeat is a bug report, not a metric.

**S5 — No intention ever exists on behalf of more than one person.**
Boundary, not a gradient: the attribution floor from the practice-side CE criteria (2026-08-02) §1 applies unchanged. Never traded at any score.
*Re-run:* every scoring pass, as a floor check.

---

## 4. Abandon line

> **If two consecutive offers are declined and no member has adopted an intention that they did not first state themselves, stop.**

That observable means the inference is not good enough to be worth a member's attention, and the honest product is the direct-statement path alone — a place to write down what you are working on, and a check that tells you when it has gone quiet. That is a smaller feature and possibly the right one.

**Falsifier for this document:** if the feature ships and no line in the press release ever killed or reshaped part of it, §12 is ceremony here and this file should be deleted rather than imitated.

---

## 5. What is deliberately not decided here

- How recurrence is detected, and over what horizon.
- Where an adopted intention is stored, and in what form.
- What "gone quiet" is measured against.
- Whether the check surfaces in conversation or somewhere else.

All four are mechanism. If any of them turns out to be *load-bearing for the experience above*, that is a finding, and it belongs in the design doc that follows this one — not smuggled in here.
