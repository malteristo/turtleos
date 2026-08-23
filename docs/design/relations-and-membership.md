# Relations and Membership

**Date:** 2026-08-05
**Status:** Destination proposed — awaiting operator sanction on the registry schema
**Spec reference:** TURTLE_SPEC §15 (multi-practitioner), §15.6 (share eddy)
**Companion chapters:** [family-care-operating-model.md](family-care-operating-model.md), [design-topic-channels.md](../chapters/design-topic-channels.md), [design-admin-space-provisioning.md](../chapters/design-admin-space-provisioning.md)

---

## The need

Once a node's purpose is **family care**, "who is this for" stops being rhetorical. A real node accumulates people who are not the family: a close friend with a hosted river, a teenage relative onboarded while testing the invite mechanism, a sibling who has not been invited yet and whose invitation now means something different than it did under the personal-AI framing.

The platform has no vocabulary for any of this. It knows two kinds of person (`mage`, `practitioner`), one privileged flag (`primary`), and one grouping mechanism (`spaces.*.members`). Everything else — who is family, who is a guest, who may reach whom — is either unrepresented or implicitly "everyone".

This document defines the missing layer. It is the half of [topic channels](../chapters/design-topic-channels.md) that slice 1 deferred: topics inherit their space's members and permissions wholesale, which is correct only as long as every space has exactly one obvious membership.

---

## What exists today (verified 2026-08-05)

| Mechanism | Where | What it actually governs |
|---|---|---|
| `type: mage \| practitioner` | `mage_registry.yaml` → `mage.get_mage_type()` | A 22-entry command allowlist (`cmd_dispatch._PRACTITIONER_COMMANDS`), artifact shelf visibility (`artifact_viewer.py`), a history-length branch in `sessions.py` |
| `primary: true` | registry → `commands.py` | Every `!admin` command (registry, invite, rivers, space provisioning) |
| `spaces.*.members` | registry | Who is auto-joined to shared eddies; who satisfies `share_policy: members_only` |
| `share_policy` | registry, per space | Who may share **into** a space |
| Channel permission overwrites | `space_provisioning.build_shared_space_overwrites` | Discord-enforced visibility — written **one member at a time** |
| Discord roles | — | **Nothing.** The only `.roles` read in the runtime is a diagnostic that prints role names (`commands.py`, seneschal readout) |

**Two consequences fall straight out of that table.**

**1. Membership is enforced per member, not per class.** Every shared channel carries an explicit overwrite for each member. Adding a person to a class means editing every channel that class can see, and there is nothing to reconcile against — drift is invisible until someone cannot see a room.

**2. Member-to-member reach is undifferentiated.** `share_targets.list_practitioner_targets` returns *every other registered mage with a river channel* — its docstring says so plainly. There is no relation filter, no policy field, no opt-out. On a node with a partner, a friend, and a teenage relative, all three appear in each other's `!share` pickers and can each deliver a conversation digest plus an `@`-mention into any of the others' private rivers. Spaces got a `share_policy`; practitioners never did. Spec §15.6.4 already asks for registry-governed targets ("**not** Discord channel membership alone") — the space half honors it, the practitioner half does not.

Nobody has exercised this. That is exactly why it is cheap to close now.

---

## Design laws

1. **The registry is the authority; Discord roles are a projection.** Rights are decided in files that ship, lint, test, and travel to a second node. A rights model that lives in one server's UI config does none of those things.
2. **Relations are circles, not a ladder.** A relative is not "less trusted" than a partner — they are in a different room. Any model that sorts people by trust level will eventually rank family members against each other, which is the opposite of the point.
3. **Admin is a capability, not a tier.** The operator is a household member who additionally holds provisioning rights. This is what makes "even the administrator is a member with special rights" true in code rather than in prose.
4. **Default deny across circles.** A member reaches members of their own circles. Reaching across circles is a thing the operator arranges deliberately, not a default the platform grants.
5. **Relation is descriptive, not evaluative.** `guest` is not a demotion and must never be surfaced as one. Members see rooms and people; they do not see their own classification rendered as a rank.

---

## The model

| Relation | Who it names | Rooms | Reach |
|---|---|---|---|
| `household` | The people whose daily life the family river carries | Family river, all family topics, dates, barometer, family surface | Household + kin |
| `kin` | Extended family on **either** side — siblings, their partners, nieces and nephews | Own river (optional) + kin space + topics they are invited into | Household + kin |
| `guest` | Friends, hosted practitioners, research participants | Own hosted river + any sandbox space they were provisioned into | Nobody by default; the operator only |
| `admin` | **Orthogonal capability**, held alongside a relation | Provisioning, registry, invites, doctor | — |

**Kin is bilateral** (operator decision, 2026-08-05). The class is defined from the standpoint of the whole family, not the operator's side of it. A partner's nephew is kin exactly as a sibling is; the model has no notion of "his side" and "her side," and adding one would encode a split that the family thesis exists to avoid.

**Household is not a household-size claim.** It names whose ordinary week the shared river is about. Children enter it when child membership is designed — deferred, and tracked in the topics chapter.

### Registry shape

```yaml
mages:
  operator:
    type: mage
    relation: household
    admin: true            # replaces the load-bearing meaning of `primary`
  partner:
    type: practitioner
    relation: household
  sibling:
    type: practitioner
    relation: kin
  friend:
    type: practitioner
    relation: guest
```

`relation` defaults to `guest` when absent — an unclassified person must never fall into the family by omission. `type` keeps its current job (command surface and artifact shelves); `relation` governs reach and rooms. They are orthogonal on purpose: a kin member and a guest may both be `type: practitioner` while belonging to entirely different parts of the node.

`primary: true` stays as the boot-time "whose practice root is the default" marker. The **authority** meaning moves to `admin: true`, so that a second administrator becomes possible without two people claiming to be primary.

### Discord roles as projection

turtleOS syncs one Discord role per relation (`Household`, `Kin`, `Guest`) and switches shared-channel overwrites from per-member to per-role. Roles then do three things the registry cannot:

- **Legibility** — a member opens the member list and sees who is family. Today that is invisible.
- **Cheap enforcement** — one overwrite per channel instead of one per member; membership changes stop requiring channel edits.
- **Drift detection** — `!admin doctor` compares roles against the registry and reports divergence, the same way it already reports river-name divergence.

Roles never *grant*. A role added by hand in the Discord UI is drift to be reported, not a rights change to be honored. Sync is one-directional: registry → Discord.

---

## Member-to-member: the actual gap

Naming this precisely, because "underdeveloped" understates it. turtleOS knows how to do two things with two people:

- **Co-presence** — put them in a shared room, where Turtle is mention-gated and peer messages are recorded as witness history.
- **Handoff** — `!share` a conversation across, digest-first, with a transparency act when it crosses a space boundary.

It does not know how to hold a **relationship between two members who are not in the same room**. There is no member directory, no way to be aware that a relative is even on the node, no way to address another member through Turtle, and nothing that lets Turtle speak *about* a member's likely view without speaking *as* them.

That absence is why a teenage relative's river went quiet after the day it was claimed: the only thing the platform knew how to offer a new person was a private room with an AI in it. For someone who is on the node because of who they are related to, the private river is the wrong primitive. What was missing was the kin space and the awareness that an aunt is one channel away.

**The minimum that closes it** (not a full social layer):

1. **Relation-scoped share targets.** The picker offers members of your own circles. Guests see the operator only.
2. **A kin space.** One `shared-river` with `relation: kin` membership, provisioned the same way family was. This is the room that makes a relative's presence mean something.
3. **A member directory act.** `!members` — who is on this node that you may reach, scoped by relation, addresses only, no activity data. The cheapest possible answer to "who else is here."

Relational proxy — Turtle speaking with knowledge of an absent member's likely view, never as them, never consequentially — stays a seed. It belongs to the mediation and barometer orbit and needs the consent laws worked out first.

---

## Minors

A member under 18 requires **guardian consent recorded before provisioning**, and the guardian is the parent, not the operator.

The case that produced this rule: a 15-year-old relative was onboarded during an invite-mechanism test, on the same visit at which his own father declined a river for himself. A parent declining for themselves is not consent for their child, and enthusiasm from a teenager at a birthday party is not either. The river was provisioned, claimed, used once, and has been silent since.

Rules:

- **No hosted river for a minor without a recorded guardian yes.** The private-river shape — a young person alone with a language model, in a room nobody else can see, on infrastructure a relative operates — is the shape that most needs a guardian's actual decision.
- **A shared room is the safe default.** Co-presence in a kin space is visible, is what the relative is there for anyway, and does not create a private channel between a minor and an AI.
- **`relation: kin` does not imply a river.** Membership and a private surface are separate grants. Most kin want the room, not the river.
- **Retire, don't accumulate.** An unclaimed or long-silent minor river is closed, not left standing in case they come back.

---

## Slices

**Slice 1 — close the reach gap** — **shipped 2026-08-05**
`relation` with a `guest` default and `may_reach` in `mage.py`; `list_practitioner_targets` filtered by it; `admin: true` alongside `primary`, with `admin_discord_ids` as the single source for admin gates (`river_keys` and `founder_keys` had duplicate copies of the rule and now delegate); malformed relation values fall back to `guest` and are reported by `!admin doctor` rather than honored. 27 tests, suite 835 green. No Discord changes.

**Slice 2 — roles as projection**
Role creation and sync, role-based overwrites in `space_provisioning`, `!admin doctor` reconciliation. Migration converts existing per-member overwrites.

**Slice 3 — kin space and directory**
Provision the kin space; `!members` act; relation-scoped topic invitations. Lands with or after topics slice 1, since it is the first thing that needs cross-space topic membership.

### Not in these slices

- Children as members (tracked in the topics chapter)
- Relational proxy / speaking about an absent member
- Per-member deny lists inside a relation
- Multiple administrators in practice (the schema allows it; nothing is built for it)
- Spec amendment — after slice 1 dogfood, per grill-first

---

## Decided (operator alignment, 2026-08-05)

1. **Kin is bilateral** — whole family, both sides, no asymmetry in the model.
2. **Friends stay guests.** A close friend with a hosted river and a sandbox was never on the family path; nothing about the family thesis changes what he has.
3. **Announcement targeting narrowed** — `audience: shared:<space>` ships with this document, after a family-dates note reached a friend's sandbox because `shared` meant "every shared room."
