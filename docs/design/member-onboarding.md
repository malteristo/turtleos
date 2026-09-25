# Member onboarding — destination

**Date:** 2026-08-30  
**Status:** Sanctioned 2026-08-30. Criterion 3 first-run live on Mini (`be2a406`, 15:50 CEST). Criterion 4 member-path teaching retired 2026-09-13.  
**Spec:** TURTLE_SPEC §3.1 (roster) · §15.4 (river keys — leftover hosted path, not this door).  
**Companions:** [practice-channels.md](practice-channels.md) (the rooms) · [install-experience.md](install-experience.md) (the administrator’s afternoon) · [onboarding.md](../ux/onboarding.md) (live first-success is still the installer).

This is the practitioner-visible *process* for everyone after the administrator: from “I got a Discord invite” to “I am in my room and I have spoken.” The rooms themselves are [practice-channels.md](practice-channels.md). This file does not reopen that stack.

Four artifacts first (`docs/development.md` §12). No mechanism in the press release.

The quality bar is **straightforward, excellent**. Short. Familiar. They act before they are taught. If they have to ask the person who invited them what to do, this dest has failed.

---

## Claim class

| Claim | Class | Who can establish it |
|-------|--------|----------------------|
| After accepting a Discord invite, a new member can find their private room and talk to Turtle the same day, without a host command, a key, or a message to the administrator. | **Interaction contract** | Independent probes, against the criteria below. |
| The first minute felt like joining a Discord server they already understand, not like being handed a kit. | **Experience judgment** | Agents may score a rubric only after it is calibrated against Kermit’s judgments. |

---

## 1. Press release

Someone sent you a Discord invite. You accepted it.

You are in the house. There is a room that is only yours. If the house has a community room, you are already in it.

You open your room. You can see what to do next without asking anyone. You start a conversation. Turtle answers.

The person who invited you did not do anything after sending the link.

---

## 2. Happy path

```
Alex:   (sends the Discord invite)
Sam:    (opens the link on their phone)
Sam:    (accepts — the join feels like any other Discord server)
Sam:    (sees their private room. community is there if the house has it.)
Sam:    (opens private. one next step is obvious.)
Sam:    (starts a conversation)
Turtle: (replies)
Sam:    (does not message Alex. does not wait. does not hunt for a key.)
```

*Invisible: accepting the invite is membership. A different implementation that left Sam in the same place would still pass. Seating in community is the roster rule — already live when a shared room exists.*

---

## 3. Success criteria

| # | Experience | Can fail in week three | Re-run |
|---|------------|------------------------|--------|
| 1 | After the invite, they can point at a private room without a host step or a key. | They wait for `!admin invite`, drop an emoji, or sit in an empty server. | Next real join on a throwaway server. |
| 2 | The same day, they start a conversation in that room and Turtle replies. | The room exists but they cannot find the next step, or Turtle never answers. | Same join. |
| 3 | The first minute is one obvious action — not a page of instructions. They talk before they are taught. | First screen is a manual. They ask the administrator what to do. | Re-read the first-run surface after each copy change. |
| 4 | The administrator’s only act was the Discord invite. | A second ceremony is taught as how you finish joining. | Re-read FAQ / SKILL member path. |

Mechanism-blind: a different transport could still be scored on “invite → own room → spoken, no host, no key.”

**Excellent, here, means:** they never wonder whether they are in the right place; the next tap is obvious on a phone; nothing they need is behind a command they have not been taught; teaching arrives after they have already succeeded, or not at all.

---

## 4. Abandon line

Stop claiming join is how you become a member if the first minute still requires a host command, a key, an empty channel list, or a question to the person who invited them.

---

## Live today (do not contradict)

- Join on a practice server already admits: private river + seat in `#community` when that room exists. No `!admin invite`. This instance minted `#community` on 2026-09-12.
- `!admin invite` and the emoji key remain the **hosted-guest** path (`TURTLE_SPEC` §15.4). Member-path docs (FAQ, SKILL, onboarding, README household) do not teach them.
- Discord Community Onboarding is **not** this dest. It needs seven default channels, five of them world-writable. It can grant existing rooms; it cannot mint a unique private river.
- Community is **not** created at install. A new clone has no community to land them in. That is [install-experience.md](install-experience.md).
- Join first-run is live: `template/practitioner/first_run_en.md` — one action (`new eddy`). Posting it marks onboarding posted, so the hosted welcome embed does not follow on the same channel. Mini `be2a406`.
- First message in a blank eddy reaches Turtle on the split-bot path via `first_eddy_handoff.py`. The hosted walkthrough no longer teaches a silent first message.
- The hosted welcome embed still exists for the hosted-guest door. It is longer than criterion 3 allows. Do not use it as the member first minute.
- Criterion 4 leftover closed 2026-09-13: member-path docs no longer teach `!admin invite`. Hosted-tester still does — that is a different door.

---

## Out of scope

- Building community-at-install (the other half of the house).
- Enabling Discord Community Onboarding as the product.
- Renaming live `#family`.
- Using the household Discord as the probe.
- Hosted guests who were never meant to be members — their key path is a different door until we retire it on purpose.
