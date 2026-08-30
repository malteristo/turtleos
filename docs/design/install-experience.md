# Install experience — destination and verification contract

**Date:** 2026-08-30  
**Status:** Sanctioned 2026-08-30 (brief QA gate). Clarification: Turtle answers in community from the first afternoon; a second person is seated there on join. Not built (community-at-install).  
**Spec:** TURTLE_SPEC §13 (install) · §3.1 (the house the install is supposed to leave you in).  
**Companions:** [practice-channels.md](practice-channels.md) (the two rooms, once you are in) · [onboarding.md](../ux/onboarding.md) (live first-success is still one river + an eddy) · [install-journey.md](../ux/install-journey.md) (June draft; names a CLI that does not exist — do not treat as live).  
**Method:** experience verification — `desk/craft/synthetic_research_practice.md` · study-zero Phase B form in `desk/craft/plans/2026-08-28-experience-verification-study-zero.md`.

This is the practitioner-visible *process*: from “I have heard of turtleOS” to “I am standing in the house and I have spoken.” The rooms themselves are [practice-channels.md](practice-channels.md). This file does not reopen that stack.

Four artifacts first (`docs/development.md` §12). No mechanism in the press release.

---

## Claim class

| Claim | Class | Who can establish it |
|-------|--------|----------------------|
| After the published install steps, the operator can find a private channel and a community channel, and can talk to Turtle in either, without a second ceremony. A later join seats the new person in community without an admin add. | **Interaction contract** | Independent probes, against explicit pass rules. |
| The path felt like arriving in a house, not like assembling a bot. | **Experience judgment** | Agents may score a rubric only after it is calibrated against Kermit's judgments. Model agreement is not human evidence. |
| Early adopters will finish. Families will adopt. | **Human / market** | Real behavior or human research. Synthetic agents cannot establish this. Out of this study. |

---

## 1. Press release

You set aside an afternoon. You follow the steps the product publishes.

When you are done, you open your Discord server and you can see two rooms: one that is only yours, and one called community. You can talk to Turtle in either. Nobody else is in community yet. That is fine.

When someone joins your server, they are already in community. You did not add them.

You were not taught a second setup. You did not add a household room. You did not run a host command to finish becoming a member. That was install.

---

## 2. Happy path

```
Riley has a Mac, a Discord account, and an afternoon. They have never seen turtleOS.

Riley:   (follows the published install steps)
Riley:   (does the Discord parts a person has to do)
Riley:   (opens their server)
Riley:   (sees two channels — one private, one called community)
Riley:   (opens a conversation in private, says hello)
Turtle:  (replies, in that conversation)
Riley:   (opens a conversation in community, says hello)
Turtle:  (replies, in that conversation)
Riley:   (community has no other people. That is fine.)

Later, Sam joins the server.
Sam:     (already in community. Riley did not add Sam.)
```

*Invisible: the published steps are the whole ceremony. A different implementation that left Riley in the same place would still pass. Seating Sam is the roster rule — already live; the install afternoon does not wait on it.*

---

## 3. Success criteria

| # | Experience | Can fail in week three | Re-run |
|---|------------|------------------------|--------|
| 1 | After the published steps, the operator can point at a private channel and a community channel without being taught a second pass. | A new install still has only one river, or community arrived through a later admin command. | Next vanilla install against the published path. |
| 2 | The same afternoon, they can start a conversation in private **and** in community, and Turtle replies in both. Community may have no other people. | Turtle answers only in private, or community is a room you cannot talk in. | Same install; also the next one. |
| 3 | They do not need a host command, an emoji, or a “now set up household” step to be a member in those two rooms. | First-success copy still sends them to `!admin invite` or `!admin space create` to finish install. | Re-read the published path after each install-doc change. |
| 4 | When a second person joins the server, they are already in community. | An operator still has to add them to the shared room. | Next real join. Already live on the practice server (`99df73e`). |

Mechanism-blind: a different transport could still be scored on “two rooms, Turtle in both, no second ceremony, join seats them.”

---

## 4. Abandon line

Stop claiming install is finished if, after the published steps, the operator still has only one channel, or still cannot talk to Turtle in both rooms without being taught a ceremony that is not in those steps.

---

## Live today (do not contradict)

- Published path: clone + agent skill (`docs/install/SKILL.md`) + Discord portal work a human must do. There is no `turtle install` CLI.
- First success on that path: one river, `new eddy`, Turtle replies. [onboarding.md](../ux/onboarding.md) still says a second adult and a family room are *after* first success, and still names `!admin invite` for that adult (stale — join now admits).
- Community is not created at install. This household's shared room is still `#family`, not renamed.
- Join/leave roster is live (`99df73e`). That is not the install process.

The June [install-journey.md](../ux/install-journey.md) is a feel-draft. Where it disagrees with this file, this file wins.

---

## Verification contract (Phase B)

This is the form study zero required before a prospective run. Sanction landed 2026-08-30, with the community-talk clarification.

| Field | This study |
|-------|------------|
| **Actor** | First-time installer: comfortable with Discord and copy-paste; not a daily developer; has never seen this product. |
| **Situation** | Clean Discord server created for the run. Public product surface only (README, published install path). No workshop lore, no live household, no source beyond what a newcomer would open. |
| **Start** | “I want to install turtleOS.” |
| **Journey** | Published steps → two rooms visible → conversation in private (Turtle replies) → conversation in community (Turtle replies; no other people). Join-seats-in-community is criterion 4, already live — not required in the known-bad install session. |
| **Intended experience** | The press release. |
| **Observable evidence** | Screenshot or channel list showing private + community; transcript of a private conversation with a Turtle reply; transcript of a community conversation with a Turtle reply; session log of every step taken and every time the participant looked for a step that was not published. |
| **Verdict rule (interaction)** | Known-bad / repair sessions pass only if criteria 1–3 all hold. Abandon or “I had to be told X” is fail, not a partial. Criterion 4 is scored on a real or staged join, not on Riley alone. |
| **Known-bad / positive control** | Today's published install (one river). A probe against current GitHub + SKILL must fail criterion 1. If it passes, the contract is wrong or the probe cheated. |
| **Sound baseline** | The same contract after community-at-install exists in the published path. Must pass criteria 1–3 (Turtle in both rooms; community may still have only the installer). |
| **Rerun** | After any change to the published install path or to what a new clone creates. After the repair. |
| **Environment** | A throwaway server and a throwaway clone. **Not** the household Discord. **Not** the Mini's live workshops. |
| **Human-evidence boundary** | Probes do not speak to desire, adoption, or whether a real early adopter would finish. Those claims stay out. |
| **Product decision on fail** | Do not write community-at-install as live. Do not change first-success copy to claim two rooms. |
| **Product decision on pass (after repair)** | First-success checklist and SKILL outcome become the two-room house. `!admin space create` leaves the install story. |
| **Product decision on ambiguity** | Narrow the contract; do not ship the ambiguous part as verified. |

### What this run is not

- Not Phase A (Craft Turtle identity). That calibrates a different claim. It does not have to finish before this brief is written. It does have to finish before we treat *experience-judgment* scores as calibrated. This study ships as an interaction contract unless Kermit later adds a rubric and scores it himself.
- Not the Reed exploration (Alex/Morgan). That run had no protocol; its data stays out. Its *forms* (first-timer texture, abandon line) are prior art for this file.
- Not a test of Grok Bot. If the substrate cannot operate Discord, that is a deviation and a substrate fact — the contract does not change. Fallback: an independent agent on Forge, given only the public path, same evidence rules, same reset.

### Independence and reset

Fresh Discord server per run. Fresh browser profile if the probe uses a browser. No cookies from the household. Attestation in the study repo before aggregation. A run without reset is excluded.

---

## Out of scope

- Building community-at-install (the repair). The known-bad probe comes first, so the contract has a baseline verdict to reverse.
- Renaming live `#family`.
- Localizing the path.
- Proving anyone will pay for experience verification.
- Using the household as a dogfood install.
