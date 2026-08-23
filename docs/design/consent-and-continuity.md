# Consent and Continuity

**Status:** Destination artifacts written first (press release, happy paths, criteria, abandon line). **Slice 1 built:** `consent.py` — the resolver, fail-closed, unanimity for rooms, refusal-as-two-answers. **Not wired to the runtime and not deployed:** the asking surface, the delete sweep, and the fail-closed flip on live roots all ship together with the eddy (§11 B of the practice-side proposal), so that the room going quiet and the way to turn it back on arrive in the same moment.
**Written:** 2026-08-02, as the first run of `docs/development.md` §12.
**Companions:** [`what-a-shared-room-remembers.md`](what-a-shared-room-remembers.md) · [`carried-context-and-the-confirm-moment.md`](carried-context-and-the-confirm-moment.md)

---

## 1. Press release

> ### turtleOS asks before it remembers — and "no" is a real answer
>
> **Local-first practice infrastructure, now with consent as a first-class part of the practice.**
>
> A practice partner that remembers is the whole point of turtleOS. It knows roughly when it is, what you have been circling, what the room has been about. That memory is what makes it a partner rather than a chat window.
>
> Until now, it simply started. Everyone whose practice runs on turtleOS was being remembered because remembering is what the software does, and nobody was ever asked.
>
> From today, turtleOS asks. In your own river, in your own language, in a conversation you can take at your own pace — not a checkbox, not a banner, not a wall you have to get through before you can use anything. It tells you what it already holds before it asks what it may keep. You can say yes to some of it and no to the rest. You can change your mind later, in either direction. And if you say no, it forgets — not "stops showing you," forgets.
>
> Nothing you say no to costs you anything you were promised. Whether a host may read your practice to improve the software is a separate question from whether the software may remember you, and answering no to the first changes nothing about the second. A practice you keep private is not a degraded practice.
>
> Shared spaces work the same way, one step further out. A room remembers only while everyone in it has agreed that it may. Nobody is kept out of a room for not answering — the room simply stays in the present until the last person says yes. What you see is that the room is not keeping memory; you never see who has not answered. That stays between each person and their own practice.
>
> "The thing we kept finding is that our software knew more about people than they had agreed to," said the host of the first turtleOS node. "Not through anything sinister — just because remembering is what it does, and nobody built the moment where someone gets to say how much."
>
> turtleOS is local-first: inference runs on your own hardware, and your practice lives in files you can read. Consent is the part that was missing, and it is now the first conversation you have.

*Mechanism named in the above: none. That is the test.*

---

## 2. Happy paths

House style per §3.5: one person, one task, start to finish, as dialogue. The practitioner's side stays plain; anything the system is doing is in *italics* and never visible.

### 2.1 Disclosure and yes — a practitioner already here

*An eddy appears in the practitioner's own river. It does not interrupt anything; it waits.*

> **Turtle:** There's something the host asked me to bring you, whenever you have a minute. No rush — this eddy will keep.
>
> **Practitioner:** go ahead
>
> **Turtle:** I've been keeping notes on our conversations since the sixteenth of July — twenty-two of them, plus eight summaries of how days went. I use them so you don't have to re-explain things. Nobody ever asked whether that was alright with you, and that's the part we're fixing.
>
> Three separate questions, and they don't have to have the same answer:
>
> First — should I keep remembering your practice, for you?
> Second — the family room: should what you say there be held in the room's memory, where the other people in that room will see it resurface?
> Third — may the host read your practice, to find bugs and see whether the software is actually working? That one is for their benefit, not yours. Saying no to it changes nothing else.
>
> **Practitioner:** what does it look like if I say no to the third one
>
> **Turtle:** Exactly the same as if you said yes. The host stops being able to read your notes for that purpose, and nothing about your practice changes.
>
> **Practitioner:** ok. yes to the first two, no to the third
>
> **Turtle:** Got it. I'll keep remembering your practice and the room keeps its memory once everyone there has answered. Your notes stay yours.
>
> Your words go in the record as you said them, with today's date, and the host reads them. You can change any of these whenever you want — just say so here.

*Three values recorded separately. The third is a no and costs nothing. Nothing else in the practitioner's experience changes.*

### 2.2 No — and the two things "no" can mean

> **Practitioner:** actually no. I don't want any of this kept.
>
> **Turtle:** Understood. Two different things you might mean, and I don't want to guess:
>
> Stop from here — I keep nothing new, and what's already written stays on disk in case you want it later.
> Or stop and remove — I keep nothing new, and the twenty-two notes and eight summaries are deleted. That one can't be undone.
>
> Your own messages in Discord are yours either way; those aren't mine to remove.
>
> **Practitioner:** stop and remove
>
> **Turtle:** Done — I'll confirm when it's finished. From now on I'll be here for each conversation as it happens and won't carry anything between them.
>
> One last thing, and I'd rather say it than have you find it: I'm keeping *this* answer. Your words, today's date. It's the only way I know not to start again.
>
> **Practitioner:** that's fine

*Later, a new conversation:*

> **Practitioner:** morning
>
> **Turtle:** Morning. What's on your mind?

*No mention of what it does not have. Turtle is a fresh, attentive presence and never narrates the absence unless asked directly.*

### 2.3 A shared room where someone has not answered

*Two members in a room. One has said yes; the other has not opened their eddy yet.*

> **Member A:** do you remember what we decided about the trip
>
> **Turtle:** I don't — this room isn't keeping memory at the moment. Everyone here needs to have said it's alright before I hold on to what's said, and that's still open. It'll start keeping once it's settled.
>
> **Member A:** who hasn't answered?
>
> **Turtle:** That's between each person and their own practice. It's a question waiting in a river, not something the room decides.

*Meanwhile, in the other member's own river, the eddy sits unanswered. It does not re-ask.*

*When they answer yes, in that room, on the next turn:*

> **Turtle:** *(no announcement — the room simply begins holding its memory again)*

### 2.4 A new member joins a room that had memory

> **Turtle:** *(in the room, when the third member is added)* Heads up — I've paused this room's memory while the newest person decides whether it's alright with them. Nothing's lost; it just isn't in play until then.

*The pause is stated. The person is not named. The eddy goes to the new member's own river.*

---

## 3. Success criteria

Experience-shaped. Each passes the three tests in `development.md` §12: mechanism-blind, able to fail in week three, named re-run.

| | Criterion | Re-run |
|---|---|---|
| **C1** | Every practitioner whose material is retained has, in the record, an answer in their own words with a date — and the count of retained-without-an-answer is **zero**. | Scored weekly with the CE judge; also a startup check. |
| **C2** | A practitioner who refuses operator-access experiences no difference in their practice, on any axis the CE judge measures. | Judge run, comparing refusing and consenting roots. |
| **C3** | A refusal that asked for removal leaves nothing retrievable — verified by looking, not by a flag's value. | Positive control each judge run: plant a refusal in a scratch root, confirm the sweep finds nothing. |
| **C4** | A shared room holds memory only while every member has agreed, and no member can learn from the room who has not answered. | Judge run over shared-room turns. |
| **C5** | An unanswered question never re-asks, never escalates, and never degrades anything beyond the memory it governs. | Judge run; the absence of nagging is the thing being checked. |
| **C6** | A practitioner can state the three questions back in their own words after answering them. | Asked directly, at the first hosted-practitioner check-in. |

**C6 is the one that can embarrass us**, and it is the only one a machine cannot score. Consent that cannot be restated was not understood, and consent that was not understood is a record, not a permission.

---

## 4. Abandon line

> If the first three practitioners asked cannot restate the three questions after answering them (**C6**), the eddy is not a consent surface — it is a disclosure ritual with a yes attached. Stop building it out, and go back to the question of whether a host should be reading practitioner material at all, rather than improving the wording of the ask.

The failure mode this guards against is a mechanism that gets more elaborate as it works less — the shape `carried-context-and-the-confirm-moment.md` §4 already found once, where the gate kept being redesigned and the right answer was that the gate should not exist.

---

## 5. What writing this changed — protocol §12, first run

The prediction attached to §12 before writing: *the happy path will expose that the refusal path has never been walked.* It held, and produced four changes to the build that the design conversation had not reached.

1. **"No" is two answers, not one.** *Stop from here* and *stop and remove* are different intentions, and the second is irreversible. Bundling them makes refusal more destructive than the person may mean. §2.2 asks. **Changes the build:** the record needs two fields, not a boolean.

2. **The refusal record is itself retained material, and the paradox has to be spoken.** Keeping someone's words asking us not to keep their words is the only way to honour the request — but it must be said out loud in the eddy, not quietly assumed. **Changes the build:** the disclosure text, and the sweep must exempt the consent record from its own deletion.

3. **Turtle must never narrate the absence.** After a refusal, a partner that says *"I don't remember, you didn't let me"* every turn is nagging with better manners. It behaves as a fresh, attentive presence and mentions the gap only if asked. **Changes the build:** a conduct rule, and a negative test.

4. **A new member joining a room with memory is an unhandled moment.** The existing members lose the room's memory because someone else arrived. Silent degradation is the wrong answer; §2.4 states the pause without naming the person. **Changes the build:** membership change is a trigger, not just space creation.

One further consequence, upstream of all of it: **C2 makes the toll test executable.** "Refusing operator-access costs nothing" was an ethical assertion in the proposal; as a criterion scored by the same judge across a refusing root and a consenting root, it is now a thing that can be shown false.

*Four changes, before any code. The protocol's falsifier is not yet discharged — it asks for a press release that kills or reshapes a feature, and this reshaped one. One more to go.*
