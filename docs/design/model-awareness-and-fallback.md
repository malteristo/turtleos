# Model awareness and the visible fallback — destination

**Date:** 2026-09-26  
**Status:** Destination, first slice building the same day.  
**Spec:** TURTLE_SPEC §3.1 (local-first promise), §8.1 (models by role).  
**Companion:** [atrium.md](atrium.md) § Models are a community choice.

Practitioner-visible change. Four artifacts first (`docs/development.md` §12).

---

## 1. Press release

Turtle knows what it is running on, and what kind of practice that model is good for. It tells you when that changes.

If a room's cloud model stops answering in the middle of something — the money ran out, the service is down — the local model takes over and says so plainly. It does not pretend to be the model you were talking to. It catches what was in the air, keeps it safe, and tells you where it is. When the cloud model is back, Turtle says so and reminds you what is waiting.

You can keep practising on the local model in the meantime. It will tell you what it can do well and what should wait.

---

## 2. Happy path

```
The house's cloud credit runs out on a Tuesday afternoon.

Alex:   (in the building room, mid-way through a change) …and then add the
        check that the old grant is revoked.
Turtle: -# ⚠️ The cloud model is unavailable (credit balance is out). This reply
        -# is from the local model. What you asked is parked.
        I'm the local model now, so I won't try the code change — that needs
        the cloud model. What was in the air: add the revoke check after the
        new grant is issued. It is kept safe, and I'll bring it back when the
        cloud model is available again.

Alex:   Fine. Can we talk through what the atrium should show meanwhile?
Turtle: -# ⚠️ Still on the local model — cloud unavailable since 14:10.
        Yes — conversation like this works well here. …

(credit is topped up)

Alex:   Right, where were we?
Turtle: -# ✅ Back on the cloud model. 1 parked item in this room.
        We were adding the revoke check after the new grant. …
```

---

## 3. Success criteria

| # | Experience | Can fail in week three | Re-run |
|---|------------|------------------------|--------|
| 1 | When a room's cloud model fails mid-conversation, the practitioner gets an answer that says it is from the local model and why. | A cloud failure produces a generic "couldn't get a thought together", or a local reply that reads as the cloud model. | Automated: a scripted cloud failure; the reply carries the notice. Live: next real outage. |
| 2 | What the practitioner had just asked is kept, in their words, and they are told it is kept. | The request is gone after the outage; nobody can say what it was. | Automated: the parked record holds the message verbatim. |
| 3 | When the cloud model returns, the practitioner hears it, with what is waiting. | Turtle silently switches back and the parked item is never mentioned. | Automated: first successful cloud turn after a hold names the parked count. |
| 4 | Turtle describes what the model it is running on is suited for, when asked, and it matches the model actually answering. | Turtle on the local model claims to be the cloud model, or offers work only the cloud model can do. | Automated: the model line in the prompt names the answering model. Live: ask in a room after a model change. |
| 5 | The house can say what the cloud cost, per room, for a month. | A month passes with cloud use and no figure. | Monthly: the usage report has rows for every room that called a cloud model. |

---

## 4. Abandon line

Stop calling the fallback visible if a practitioner ever learns after the fact that a reply came from a different model than they thought.

---

## The shape (for implementers)

- **Model profiles** name each model's backend, price, and what practice it suits. An unknown model gets an honest "unknown", never a guessed price.
- **Failure kinds:** *funds* (credit out) and *access* (key refused) hold the whole house on the local model until a periodic cloud try succeeds; *unavailable* (overload, network) falls back for that turn only.
- **Parking is done by code, not by the model.** The record is written before the local model is asked anything, so a local failure cannot lose it. It lives in the room's own practice root.
- **The notice is written by code**, not by the model, so no model can omit it.
- **Usage** is read from each cloud response and appended to a house-level ledger with its cost from the profile.

## Deliberately not in this slice

- Picking models from the atrium; updating the local model from inside turtleOS. Next slices ([atrium.md](atrium.md)).
- Auto-resuming parked work. The practitioner resumes it; Turtle reminds.
