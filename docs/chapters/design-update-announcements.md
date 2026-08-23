# Design Chapter: Update Announcements (practitioner rivers)

**Opened:** 2026-07-16  
**Status:** Destination sanctioned — implement + first fanout  
**Spec trace:** Hosted / onboarding adjacency (River-owned parent posts)  
**Related:** [design-practitioner-ready.md](design-practitioner-ready.md), [design-hosted-river.md](design-hosted-river.md)

---

## Destination

After each meaningful ship, operators run one command that posts a plain-language “what’s new / how to use it” card into every `river` and `hosted-river` channel. Hosted guests and the operator get the same product surface (locale-adapted). Return-visit is the first announcement in the series, not a separate system.

---

## Decisions

| Choice | Decision |
|--------|----------|
| Trigger | **Manual** after ship (`scripts/post_announcement.py`) — not auto on bot ready |
| Scope | Versioned announcements; return-visit subsumed |
| Audience | `type: river` + `type: hosted-river` (skip `shared-river`, `archived`, craft) |
| Poster | River bot (`RIVER_BOT_TOKEN`), silent embed, **no pin** (onboarding stays the pin) |
| Locale | From `mages.*.locale` via `_practitioner_locale` |
| Idempotency | Per-channel per-announcement-id state; `--force` re-posts |

---

## Content model

```
template/announcements/
  YYYY-MM-DD-slug.en.md
  YYYY-MM-DD-slug.de.md
  _example.md
```

Front matter: `id`, `title`. Body = practitioner-facing markdown (short, no Magic jargon).

First id: `2026-07-16-nesrine-ready` (migrated from return-visit copy).

---

## Runtime state

Per practice root / channel runtime:

`{runtime_dir}/thread-state/river/announcements.json`

```json
{
  "posted": {
    "2026-07-16-nesrine-ready": { "message_id": 123, "at": "ISO-8601" }
  }
}
```

One ledger file per channel’s runtime — hosted isolation holds.

---

## Operator runbook

```bash
# After a ship — fanout to all rivers
~/turtleos/venv/bin/python3 scripts/post_announcement.py --id 2026-07-16-nesrine-ready

# Preview
~/turtleos/venv/bin/python3 scripts/post_announcement.py --id 2026-07-16-nesrine-ready --dry-run

# One channel
~/turtleos/venv/bin/python3 scripts/post_announcement.py --id 2026-07-16-nesrine-ready --channel <practitioner-channel-id>

# List known ids + per-channel state
~/turtleos/venv/bin/python3 scripts/post_announcement.py --list
```

Legacy: `scripts/post_return_visit.py <channel_id>` forwards to `2026-07-16-nesrine-ready`.

Exit non-zero if any post fails; prints per-channel ok/skip/fail.

---

## Out of scope (v1)

- Auto-post on `river_bot.on_ready`
- Pin / edit previous announcement messages
- Shared-river fanout *(amended 2026-08-04 — see below)*
- Admin Discord command (`!admin announce`)
- Per-mage custom override files

---

## Amendment implemented (2026-08-05) — shared-river audience

**Finding (2026-08-04):** Family-care ships (e.g. dates) fanned out to practitioner/hosted rivers and missed `shared-river` — the room where shared-root state surfaces.

**Shipped:** front-matter `audience: shared` on an announcement adds active `shared-river` channels to the fanout targets. Default (`audience: rivers`, or no tag) is unchanged — shared rooms are never reached by untagged product notes. Locale for shared channels resolves from the owning space's registry `locale` (e.g. a German-speaking family room), falling back to `en`. Idempotency ledger unchanged (per-channel `announcements.json`), so re-running a fanout after tagging reaches only the newly eligible rooms.

Origin: [design-topic-channels.md](design-topic-channels.md) § Companion slice C · stance: [family-care-operating-model.md](../design/family-care-operating-model.md) · tests: `test_announcements` (audience parsing, iterator, fanout targets, space locale).

### Follow-up (2026-08-05) — named-space targeting

**Finding:** the first `audience: shared` fanout delivered a *family* feature note into a friend's sandbox, because `shared` means "every active shared room." Consistent with the shipped semantic, wrong for anything addressed to one family.

**Shipped:** `audience` now accepts `shared:<space-key>` (comma-separated for several, e.g. `shared:family,band`), narrowing shared-river targets to those registry spaces. Bare `shared` keeps its meaning — every active shared room — and stays correct for platform-wide notes. Solo rivers are never affected by the narrowing. An unparseable or unknown audience kind still falls back to `rivers`: a bad tag must never widen delivery. The family-dates announcement is re-tagged `shared:family`; the idempotency ledger means no re-delivery.

Relation-class targeting (`audience: household`) is deliberately *not* built here — it belongs to [relations-and-membership.md](../design/relations-and-membership.md) once relations exist in the registry.

---

## Implementation

| Piece | Role |
|-------|------|
| `announcements.py` | Load / locale / state / iter / post / fanout |
| `scripts/post_announcement.py` | CLI |
| `template/announcements/` | Content |
| Reuse | `_markdown_to_embed`, `_practitioner_locale`, `reconcile_river_bar_floor` |

---

*Ship the card when the product changed enough that practitioners need a plain-language onboard — not on every commit.*
