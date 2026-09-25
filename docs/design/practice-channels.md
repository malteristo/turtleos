# Practice channels — destination

**Date:** 2026-08-30  
**Status:** Destination — install pair (criterion 1) not built. Join/leave roster (criteria 2–3) landed 2026-08-30. Resolved practice presets landed 2026-09-07.
**Spec:** TURTLE_SPEC §3.1 (promise). Current install topology remains §13.3 until a later slice.  
**Companion:** [design-channel-primitives.md](../chapters/design-channel-primitives.md) (relational / thematic types). This file is the *container* those types sit in. The *process* that is supposed to leave you in this house: [install-experience.md](install-experience.md) (administrator) · [member-onboarding.md](member-onboarding.md) (everyone after).

Practitioner-visible change. Four artifacts first (`docs/development.md` §12). No mechanism in the press release.

---

## 1. Press release

You install turtleOS. You have a channel that is only yours, and a channel that is everyone’s.

When someone joins your server, they get their own private channel and they are already in the community channel. When they leave the server, they are gone from turtleOS. If those two facts ever disagree, something is wrong.

Craft, a relationship practice, a game — those are practices you add. Each is a channel with its own Turtle and River. Your private channel and the community channel are not practices. They are the two rooms the house comes with.

---

## 2. Happy path

```
Alex installs turtleOS, creates a Discord server, starts the shell.
Alex:        (sees two channels: one private, one called community)
Alex:        (opens an eddy in private, talks. Turtle is there.)
Alex:        (opens an eddy in community, talks. Turtle is there. Nobody else is. That is fine.)

Alex invites Sam to the Discord server.
Sam:         (joins)
Sam:         (already has a private channel. already in community.)
Sam:         (does not wait for an admin command, does not drop an emoji in a claim room)

Alex later adds a craft channel for building.
Alex:        (craft is a practice — solo. Sam is not in it unless Alex adds Sam.)
```

*Invisible: Discord membership and turtleOS membership are the same list. Bots that run the house are not on that list.*

---

## 3. Success criteria

| # | Experience | Can fail in week three | Re-run |
|---|------------|------------------------|--------|
| 1 | After install, the operator can find a private channel and a community channel without being taught a second “household” pass. | A new install still has only one river. | Next vanilla install, or `!admin doctor` once it checks the pair. |
| 2 | A person who is on the server can talk in their private channel and in community the same day they joined, without a further admit step. | Join still produces “use `!admin invite`”. | Next real join. |
| 3 | After someone leaves the server, they have no private channel and they are not in community. | A leftover river or registry row remains. | Next real leave. |
| 4 | A practice channel (craft, or a shared practice) is visibly *added*, not confused with the install pair. | New members land in craft by default, or community is named “family” as if it were the product. | After the next practice channel is created. |

Mechanism-blind: a different transport could still be scored on “two rooms at install, join = member, leave = gone, practices are extra.”

---

## 4. Abandon line

Stop claiming the install pair if, after someone is already on the server, an operator still has to run an admit command before that person has a private channel and a seat in community.

---

## The stack (for implementers)

| Layer | What |
|-------|------|
| **Topology** | solo · shared |
| **Install pair** | **Private** (solo, one per member) · **Community** (shared, all members) |
| **Practice presets** | Atomic validated recipes: private, shared, craft, partnership, health, team. |
| **Practice channels** | Instances of a preset with one root, audience and role assignment. Craft is solo work; partnership is a two-person relationship room; Quest is the user-facing name of the first live team instance. |
| **Roster** | Discord server member (humans) ≡ turtleOS member. One without the other is an error. Bots that run the house are not members. |

`household` / `kin` may still distinguish *among* members. They do not decide whether someone is one. Today’s **guest** — on Discord, not a member — is that error wearing a name.

**Live today (do not contradict):** one river at install; community-at-install is still destination. **This instance** has `#community` (2026-09-12) — the house shared room. Join seats a new member there. `find_community_space` is fail-closed on that explicit key; partnership / health / team are not a fallback. The existing two-person `#family` channel is a partnership practice instance; its display name is not an architectural promise that children or a whole household share its historical memory. Leave archives the private river and drops the community seat. `!admin doctor` reports Discord humans ≠ registry. `!admin invite` remains for pre-creating a claim room before someone joins.

A **coach studio** is a private river for a house-bot identity (`roster: false` on the mage row). It is not a member seat. Doctor must stay clean when the studio exists. Spirit uses it for live testing only; collaboration with Craft Turtle stays in the craft channel. Community remains observe-first. Provision: `scripts/provision_spirit_studio.py`.

---

## Out of scope this destination

- Creating community at install (criterion 1)
- Renaming live `#family` or craft
- Rewriting relations code
- Flows, topics, fridge, barometer
