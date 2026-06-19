# Design Chapter: Hosted River (Multi-Practitioner Sovereignty)

**Opened:** 2026-06-19  
**Closed:** 2026-06-19  
**Status:** Complete — dogfood with friend pending; Nesrine grandfathered  
**First instance:** Nesrine (`1484973995823599757`) on Kermit's server  
**Spec trace:** TURTLE_SPEC §15, §5 (River), Appendix A (operator instances)

## Tension

A **hosted river** is a sovereign practitioner's main practice surface — their private river — running on a trusted operator's Discord server. v1 native law applies: acts-not-words in the parent channel, dialogue only in eddies, standing eddy bar at the bottom.

After the platform reorientation, Nesrine's channel received v1 river chrome without onboarding. She asked *"Wer ist River?"* and *"Wer ist Eddy door?"* — legacy vocabulary and unexplained UX.

The old architecture had practitioner-specific prompts (`type: practitioner`, `resonance.md`, cold-start blocks). v1 native eddies load `character/soul.md` + `conduct.md` from the practitioner's practice root but did not inject relationship context or practitioner conduct overlays.

## Design intent

| Principle | Meaning |
|-----------|---------|
| **Sovereignty** | Practice root `~/workshops/<name>/` is isolated. Nothing from a hosted river crosses to shared channels or the operator's river without explicit practitioner action. |
| **Same platform law** | Hosted-river = `type: hosted-river` in registry. Same River harness as operator's `river` (eddy bar, acts, chronicle). |
| **Different character** | Practitioner gets their own `character/` and `resonance.md`. Turtle in eddies is attuned to *them*, not the operator's Magic practice. |
| **Practical-first onboarding** | No framework jargon. German (or mirrored language). Explain Fluss vs Wirbel in plain terms. |
| **Trust rebuild** | Nesrine's `resonance.md` is load-bearing — never push, never report to operator, demonstrate care through use. |

## Relationship to old architecture

Reuse from pre-v1 (integrate, don't copy blindly):

| Old pattern | v1 integration |
|-------------|----------------|
| `type: practitioner` in registry | Keep — drives prompt path and command surface |
| `resonance.md` in practice root | Inject into native eddy prompt (slice shipped 2026-06-19) |
| `!admin onboard` workshop bootstrap | Legacy path; prefer `!admin river-key` for new guests |
| Practitioner vs mage prompt split in `build_discord_prompt` | Eddies: native path + practitioner overlay; parent: River acts only |
| Channel sovereignty (`type: hosted-river`) | Registry semantics unchanged; enrich docs and onboarding |
| Founder key ceremony | Retired for founding room; repurposed as river keys (§15.4) |

Retire from hosted-river UX:

- Spirit Control Panel, Eddy Door naming, magic vocabulary in onboarding
- Turtle prose in parent channel (pre-v1 migration artifact)
- Per-message Materialize buttons (replaced by standing eddy bar)

## Registry shape

```yaml
channels:
  '1484973995823599757':
    mage: nesrine
    type: hosted-river
    default_context: null
    description: Nesrine's sovereign practice surface, hosted on Kermit's server
```

No per-channel attunement override required for vanilla hosted rivers — practitioner differentiation lives in `character/` + `resonance.md`.

## Implementation slices

### Slice 0 — Practitioner attunement (shipped)

- [x] Retire founding channel from registry
- [x] `build_native_eddy_prompt()` loads `resonance.md` when `get_mage_type() == practitioner`
- [x] Practitioner native eddy conduct hint
- [x] Nesrine character files + German onboarding (legacy path)

### Slice 1 — Onboarding as product (shipped)

- [x] One-time onboarding embed on bind / `on_ready` for bound hosted rivers
- [x] `template/practitioner/` skeleton
- [x] `!admin onboard` v1 alignment
- [x] TURTLE_SPEC §15 ripple

### Slice 2 — River keys / invite-to-claim (shipped)

- [x] `river_keys.py`, `!admin river-key`, river_bot + discord_bot hooks
- [x] Claim room templates (de/en)
- [x] Tests
- [x] `scripts/shake_hosted_river.py`

### Slice 3 — Operator boundaries (shipped)

- [x] Hosted-sovereignty block in operator mage prompt (`prompts.py`)
- [x] `docs/operations/hosted-river-boundaries.md`
- [x] Practitioner `!readiness` → honest substrate (`assess_practitioner_substrate`)
- [x] CouchDB note in boundaries doc (operator checklist, not automated)

### Slice 4 — Dogfood & harvest (shipped)

- [x] Practitioner journey in `docs/ux/journeys.md`
- [x] Shake script covers routing, templates, spec, readiness
- [ ] Live friend claim test (operator — pending)
- [ ] Nesrine eddy dogfood when she returns (operator — pending)

## Key files

| File | Role |
|------|------|
| `mage_registry.yaml` | Channel types, practitioner routing |
| `mage.py` | `hosted-river` in `is_river_message()`; `unclaimed-river` excluded |
| `river_handler.py` | Eddy bar for river + hosted-river |
| `prompts.py` | Practitioner eddy overlay + operator sovereignty block |
| `hosted_river_onboarding.py` | Onboarding embed |
| `river_keys.py` | Invite-to-claim ceremony |
| `readiness.py` | Practitioner substrate vs operator 8-dim |
| `docs/operations/hosted-river-boundaries.md` | Operator rules |
| `scripts/shake_hosted_river.py` | Offline verification |

## Lore (Magic workshop)

- `~/workshops/nesrine/resonance.md` on Mini
- `library/resonance/turtle/lore/philosophy/on_files_as_operating_system.md`
- `library/resonance/turtle/lore/operations/on_discord_navigation.md`

## Deferred

- Dedicated server (sovereign setup) per practitioner
- Per-practitioner model routing
- Automated CouchDB health in `@turtle-care`

## Harvest

- **Invite-to-claim (Option A)** beats communal well or in-place morph — fewer terms, cleaner Discord permissions.
- **River key** reuses founder-key mechanics without founding-room baggage.
- **Practitioner readiness** must not lie about empty substrate — separate function, not gated command denial alone.
- **Operator sovereignty** belongs in prompt law + ops doc, not only social trust.
