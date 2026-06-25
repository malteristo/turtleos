# Design Chapter: Family Shared River

**Opened:** 2026-06-19  
**Status:** Design — dedicated practice session + implementation chapter  
**Instance:** Family channel (`1491163697278881836`)  
**Spec trace:** TURTLE_SPEC §15 (multi-practitioner / shared channels)

## Tension

The family channel was registered as `type: shared` with `default_context: family`. Kermit and Nesrine use it for **shared practice** — coordination, parenting, connection — with eventual participation from the boys.

After v1 reorientation:

- Parent channel still runs magic-era dialogue (proprioception, readiness, outfacing)
- Eddies under global native ignore `family` context rules in `THREAD_CONTEXTS`
- Practice root `~/workshops/family/` is stale (empty compass/boom since ~April 2026)
- Last meaningful session identified readiness scoring on empty substrate as misleading

**Decision (2026-06-19):** Family becomes a **shared river** — same platform law as individual rivers (acts in parent, dialogue in eddies), but with **shared eddies** both parents (and eventually children) can enter.

**Share eddy (2026-06-25):** Cross-eddy “thinking together” is specified in [design-share-eddy.md](design-share-eddy.md) (TURTLE_SPEC §15.6). **Share to family** (space target) posts a digest act + creates a shared eddy at confirm; members notified; sharer notified on first peer reply. Implementation of space share depends on this chapter’s `shared-river` slice.

## Design intent

| Principle | Meaning |
|-----------|---------|
| **Shared river** | Parent channel: River acts, not Turtle prose. Shared timeline for drops and coordination. |
| **Shared eddies** | Threads both parents auto-join; Turtle facilitates in family context |
| **Privacy firewall** | No content from private rivers (Kermit, Nesrine) crosses into family — load-bearing |
| **Family context** | Inclusive, bilingual (DE/EN), age-appropriate, neurodivergent-aware — rules exist in `state.py` |
| **Dedicated session** | Fresh compass / shared intentions warrant a live family session before heavy automation |

## Target registry shape

```yaml
spaces:
  family:
    practice_dir: ~/workshops/family
    runtime_dir: ~/workshops/family
    members: [kermit, nesrine]   # boys: future

channels:
  '1491163697278881836':
    mage: family
    type: shared-river           # new type — river harness + space membership
    default_context: family
    description: Family shared practice — shared river and shared eddies
```

## Code changes required

1. **`shared-river` channel type** — include in `is_river_message()`, `river_handler._iter_river_channels()`, eddy bar deploy
2. **Practice root routing** — already maps to `spaces.family` via `mage: family`
3. **Thread auto-add** — `get_thread_member_ids()` already expands space members ✅
4. **Native eddy context** — `build_native_eddy_prompt()` must honor `default_context: family` (or `get_channel_default_context()`)
5. **Retire magic parent dialogue** — shared channel parent must not use proprioception/readiness/outfacing under native

## Lore already established

| Source | Content |
|--------|---------|
| `state.py` `THREAD_CONTEXTS['family']` | Inclusive, private-stays-private, bilingual, ND-aware |
| `library/resonance/turtle/lore/operations/on_thread_eddies.md` | Channel `default_context` inheritance |
| `~/workshops/family/context/` on Mini | Relationship patterns for shared space (April seed) |
| Magic intention `turtle.md` | Multi-practitioner sovereignty, family as pattern proof |

## Migration from current `type: shared`

| Phase | Action |
|-------|--------|
| **Design session** | Kermit + Nesrine: family compass, what shared practice means now, Noah/boys boundaries |
| **Registry** | Change `shared` → `shared-river` when code supports it |
| **River harness** | Deploy eddy bar to family channel; verify acts-only parent |
| **Context loading** | Family rules in native eddies |
| **State refresh** | Seed compass or accept intentional empty start with honest UX |
| **Archive** | April magic-era threads optional; no content migration from private rivers |

## Practitioner session agenda (proposed)

1. What belongs in the **shared river** vs private rivers?
2. Lightweight shared compass — domains that are genuinely family (logistics, trips, rituals, check-ins)
3. Language and tone for when kids are present
4. First shared eddy — low stakes (planning, not processing)
5. Explicit privacy reaffirmation for Nesrine

## Implementation slices (after session)

1. Spec ripple — `shared-river` type in §15
2. Code — type routing + family context in native eddies
3. Deploy eddy bar to family channel
4. Shake — both parents materialize eddy, verify auto-add
5. Harvest — family journey in `docs/ux/`

## Deferred

- Children's Discord accounts and permissions
- Family flows (check-in thread context already exists for partnership — relate but distinct)
- CouchDB sync for family practice root

## Not in scope for this chapter

Implementation and family session — this document opens the arc. Current channel remains `type: shared` until the shared-river slice ships.
