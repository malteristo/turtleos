# Hosted river operator boundaries

Operational rules when Kermit's turtleOS instance hosts sovereign practitioners (Nesrine, friends via river keys).

## Content boundaries

| Allowed | Not allowed |
|---------|-------------|
| Pattern observations in operator proposals ("hosted rivers need X") | Quoting hosted-river messages verbatim in operator river or proposals |
| Infrastructure health checks | Surfacing Nesrine's conversation content to Kermit without her action |
| Spirit dyad work on turtleOS product | Using hosted practice as dogfood evidence with identifiable content |

**Prompt law:** Operator mage prompts include a hosted-sovereignty block (`prompts.py`). Spirit on Forge should follow the same rule when writing proposals from Discord digests.

## Readiness

- **Operator river:** full 8-dimension practice-readiness (`!readiness`).
- **Hosted practitioner:** substrate check only — empty space reports *fresh*, not *practice-ready* (`readiness.assess_practitioner_substrate`).

Practitioners have `!readiness` in their minimal command set with the honest substrate wording.

## River keys

- River key = invitation token, not authentication. Visible in chat is acceptable in private claim rooms.
- One bind per key. Operator assigns emoji out of band after guest picks it.
- Claim room (`unclaimed-river`) → `hosted-river` on successful drop.

## Optional: CouchDB sync

If a practitioner has `couchdb_database` in registry (e.g. `nesrine_sync`), verify during `@turtle-care`:

- Database exists and replicates
- Practice dir is not accidentally shared with operator LiveSync root

Not required for Tier 1 hosted (Discord-only) practitioners.

## Share eddy (§15.6)

**Share** is explicit practitioner action — it satisfies the content-boundary rule when a guest exports an eddy to another practitioner or to a registered space.

| Allowed | Not allowed |
|---------|-------------|
| Guest shares their eddy to another practitioner or to Family (per `share_policy`) | Operator quoting guest content in operator river without guest share |
| Transparency act in space when a member re-shares space content outward | Surfacing recipient's private continuation in space parent channel |
| Pattern observations in proposals about share UX | Using share transcripts as dogfood evidence with identifiable content without consent |

Notifications: `@` mention + River act only (no DM in v1). See `docs/chapters/design-share-eddy.md`.

## Verification

```bash
~/turtleos/venv/bin/python3 ~/turtleos/scripts/shake_hosted_river.py
```

See `docs/chapters/design-hosted-river.md` for full design chapter.

**Share to family:** Once `shared-river` ships, use **Share eddy** (space target) per [design-share-eddy.md](design-share-eddy.md) — digest act in parent + shared eddy invitation; sharer not auto-joined; notify on first peer reply. Does not require duplicating share mechanics in this chapter.
