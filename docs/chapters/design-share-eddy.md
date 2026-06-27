# Design Chapter: Share Eddy (Thinking Together)

**Opened:** 2026-06-25  
**Status:** Slice 1 implemented (practitioner target); Slice 3a (space share core) implemented; 3b–3d deferred  
**Dogfood:** [2026-06-25-share-eddy-slice1-dogfood.md](2026-06-25-share-eddy-slice1-dogfood.md)
**Spec trace:** TURTLE_SPEC §15.6  
**Depends on:** §15 multi-practitioner law; **space target** requires `shared-river` harness ([design-family-shared-river.md](design-family-shared-river.md))  
**First dogfood targets:** Share to practitioner (1:1); Share to family (space invitation)

---

## Tension

Hosted practitioners each have a **sovereign private river**. Cross-practitioner boundaries (§15.5) forbid the operator from quoting guest content without **explicit practitioner action**. That protects sovereignty — but it also blocks **thinking together**: async handoff of a good eddy conversation, or opening a family planning thread without re-explaining context.

Two related desires surfaced in product thinking (2026-06-25):

1. **Send a conversation** — recipient gets their own copy (or a shared space copy) with digest-first UX; sender keeps the original eddy.
2. **Invite into the same thread** — multi-party eddy with shared conduct (experimental; family channel first).

This chapter defines **Share eddy** — one primitive covering (1). **Invite to existing private eddy** remains deferred until shared-river conduct is proven in the family channel.

---

## Design intent

| Principle | Meaning |
|-----------|---------|
| **One primitive** | Share eddy — same export, packaging, and confirm flow; **target** selects routing (practitioner \| space). |
| **Share = creation** | On confirm: export bundle written, digest act posted, destination eddy exists (received or shared). Notifications fire at creation. |
| **Digest first** | Parent river shows digest card; full transcript loads into Turtle context on continue — not replayed as dozens of Discord messages. Optional “Show full transcript” for explicit expand. |
| **Async invitation (space)** | Sharer is **not** auto-joined to the space shared eddy. Space members notified; sharer notified when a **peer first replies** (not Turtle’s opening embed alone). |
| **Registry targets, not Discord membership** | Picker lists practitioners and spaces the sender may share **to** per `mage_registry.yaml` — not whether they can see the Discord channel. A hosted guest may share **to Family** without joining `#family`. |
| **Transparency on outbound re-share** | From a **space-tagged** shared eddy, **any space member** may share to a practitioner target; space parent channel gets a **transparency act** (who shared, with whom, digest/title). |
| **Dissolve: creator only** | Only the practitioner who created the share may dissolve that shared/received eddy (v1). |
| **Confirm before send** | Picker → confirmation screen — mis-click protection. |
| **Notify: @ + River act, no DM** | No direct messages for share lifecycle (v1). |
| **Social opt-out** | Server norm: thinking together is encouraged; practitioners may set boundaries privately with the operator. |

---

## Share eddy — behavior

### Source

Practitioner initiates **`!share`** inside a live eddy (minimum dialogue before export). Source eddy remains unchanged.

### Export bundle

Reuses dissolve/archive pipeline concepts (`sessions.py` essence + transcript):

| Field | Purpose |
|-------|---------|
| `title` | Thread name or generated label |
| `digest` | 2–4 lines for river act |
| `transcript` | Full dialogue for Turtle context on continue |
| `source_thread_id` | Audit / attribution (not live sync) |
| `sharer_id` | Discord user id |
| `created_at` | Timestamp |

### Targets

#### A. Practitioner (1:1)

1. Digest **River act** in recipient’s parent channel.
2. **Received eddy** metadata: `origin: received`, `from_sharer`, distinct visual language from own eddies.
3. Recipient taps **Continue** (or equivalent) → new eddy in **their** river; opening embed + transcript in Turtle context only.
4. Recipient notified at creation (`@` + act). Sharer gets chronicle act in **sender’s** river.

Optional v1: notify sharer on recipient’s **first human message** in received eddy (conversation started).

#### B. Space (e.g. family)

1. Digest **River act** in **space parent channel** (acts-only law preserved).
2. **Shared eddy** created immediately in that channel — space-tagged, `THREAD_CONTEXTS[family]` (or space default).
3. **Space members** notified at creation (`@` + act). Sharer **not** auto-added to thread.
4. Opening embed attributes sharer; Turtle orientation only — does not count as “peer replied.”
5. On **first human message** by any space member other than notification-only paths → notify **original sharer** (`@` + act in sharer’s river + optional jump).
6. Sharer opens thread when ready; reads peer + Turtle since share.

**Prerequisite:** `shared-river` channel type deployed ([design-family-shared-river.md](design-family-shared-river.md)).

### Re-share from space to practitioner

- **Who:** Any **space member** (not sharer-only).
- **From:** Eddy tagged `space: <name>`.
- **To:** Practitioner target (confirm step).
- **Transparency:** Space parent channel posts act, e.g.  
  `**Kermit** shared this conversation with **Alex** · “Birthday party — heat & sprinkler”`  
  (digest; not recipient’s private continuation).
- Private eddy → practitioner share does **not** post to family (source not space-tagged).

### Dissolve

Only **share creator** may dissolve shared/received eddy created by that share (v1). Participants may checkpoint/release per normal eddy law.

### Sender chronicle (operator / any sharer)

In **sender’s** parent river after confirm:

`📤 Shared to family: “Birthday party — heat & sprinkler”`

After peer first reply in space share:

`💬 Nesrine replied in shared eddy · [jump to family thread]`

---

## UX — picker and confirm

### Picker (single entry: Share…)

```
Practitioners
  ○ Nesrine
  ○ Alex

Spaces
  ○ Family
```

- Sections visually separated (headers or divider).
- Population: registry `mages` with `type: practitioner` + spaces where sender satisfies `share_policy`.

### Confirm

Preview embed after target selection (LLM-synthesized title + digest):

> Share **“Birthday party — heat & sprinkler”** with **Family**?  
> [digest body]  
> They get this digest in their river and can open a received eddy when ready.

[ Edit ] [ Cancel ] [ Share ]

**Edit** opens modal (title + digest). Optional contextual **rename thread** nudge when eddy title is still a placeholder.

Practitioner variant names recipient and received-eddy behavior.

---

## Registry shape

```yaml
spaces:
  family:
    practice_dir: ~/workshops/family
    runtime_dir: ~/workshops/family
    members:
      - kermit
      - nesrine
    share_policy: all_practitioners   # who sees Family in Spaces picker
    # share_policy alternatives: members_only | explicit: [alex, kermit]

channels:
  'FAMILY_CHANNEL_ID':
    mage: family
    type: shared-river          # required for space share target
    default_context: family
    description: Family shared practice
```

**Picker rule:** `share_policy: all_practitioners` → every hosted practitioner on the node may share **to** Family without Discord channel membership.

---

## Notifications (v1)

| Event | Mechanism | Audience |
|-------|-----------|----------|
| Share to practitioner | `@` mention + River act | Recipient |
| Share to space (creation) | `@` mention + River act | All space **members** |
| First peer reply in space shared eddy | `@` + River act in sharer’s river | Original sharer |
| Re-share space → practitioner | Transparency River act in space parent | All space members |
| Share confirm | Chronicle act | Sender’s river |

**No DMs** in v1.

---

## Relationship to other patterns

| Pattern | Relationship |
|---------|----------------|
| **Hosted river boundaries** | Share **is** explicit practitioner action; operator still must not scrape without action |
| **Family shared-river** | Space share target requires shared-river refurb; digest + shared eddy is the v1 “thinking together” surface |
| **Invite to private eddy** | Deferred — multi-party in one thread needs shared conduct; experiment in family after refurb |
| **Discord forward** | Existing forward snapshot in `discord_bot.py` is message-level, not eddy export — do not conflate |
| **Dissolve essence** | Share export may call same essence/transcript helpers as `dissolve_eddy()` |

---

## Implementation slices (proposed)

### Slice 0 — Spec + types (this chapter + §15.6)

- [x] Design chapter
- [x] TURTLE_SPEC §15.6
- [x] Acceptance scenarios S1–S6 in `docs/acceptance/README.md`

### Slice 1 — Export + share to practitioner

- [x] `share_eddy.py` — export bundle, metadata types (`received`)
- [x] River act + materialize received eddy
- [x] Picker + confirm UI (practitioners section only) — entry via **`!share`**
- [x] Preview + Edit modal; LLM synthesize; rename nudge supersede
- [x] Sender chronicle; sharer notify on recipient first reply (1:1)
- [x] Tests + `scripts/shake_share_eddy.py` (offline)

### Slice 2 — Family shared-river prerequisite

- [x] Implement `shared-river` per [design-family-shared-river.md](design-family-shared-river.md)
- [ ] Family session / compass refresh (operator)

### Slice 3 — Share to space

- [x] **3a — S2 core:** Spaces section in picker (`share_policy`); space parent digest + shared eddy at confirm; member `@`+act; sharer not auto-added
- [x] **3b — S3:** Sharer notify on first peer reply in space shared eddy
- [ ] **3c — S4:** Re-share transparency acts
- [ ] **3d — S6:** Dissolve creator-only enforcement

### Slice 4 — Dogfood

- [x] Kermit → Nesrine (1:1) — multiple eddies 2026-06-25 (sender path)
- [ ] Nesrine Continue + first-reply notify (recipient path)
- [ ] Kermit → Family birthday logistics
- [ ] Guest → Family (picker without channel membership)

---

## Acceptance scenarios (draft)

| # | Scenario | Pass criteria |
|---|----------|---------------|
| S1 | Share to practitioner | Recipient river digest act; received eddy on continue; sender chronicle; original eddy unchanged |
| S2 | Share to space | Space digest act + shared eddy at confirm; members `@`+act; sharer not in thread until chooses |
| S3 | First peer reply | Sharer `@`+act in own river when space member first speaks |
| S4 | Re-share transparency | Space member shares space eddy to practitioner; space parent transparency act |
| S5 | Picker policy | Non-member practitioner sees Family in Spaces; confirm works; no Discord channel join required |
| S6 | Dissolve | Only share creator can dissolve; participant cannot |

---

## Key files (planned)

| File | Role |
|------|------|
| `share_eddy.py` | Export, routing, metadata, dissolve authority |
| `river_handler.py` | Share acts, chronicle, transparency acts |
| `eddy_spawn.py` | Received / shared eddy spawn with opening embed |
| `mage_registry.yaml` | `spaces.*.share_policy`, `shared-river` channels |
| `prompts.py` | Turtle overlay for received eddy + space shared eddy |
| `docs/operations/hosted-river-boundaries.md` | Share as explicit action |
| `scripts/shake_share_eddy.py` | Offline verification |

---

## Deferred

- Live sync between source and fork
- DMs for share notifications
- Invite others into **private** river eddy (join pattern)
- Auto-join sharer to space shared eddy
- Dissolve rights for space members other than creator
- “Show full transcript” expand button (optional v1.1)

---

## Harvest (design session)

- **Thinking together** is one primitive with two targets — not separate “send” and “family post” features.
- **Async invitation** fits digest-first UX: create shared eddy at share time, notify members, notify sharer only when conversation actually starts.
- **Registry share_policy** decouples “share to space” from Discord channel membership — required for tomorrow’s hosted guest sharing into Family.
- **Transparency acts** on outbound re-share preserve space trust without leaking recipient private continuation.
- **Sequence:** practitioner share (Slice 1) can ship before family refurb; space share (Slice 3) depends on `shared-river`.
