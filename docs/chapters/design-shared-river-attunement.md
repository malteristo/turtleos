# Design Chapter: Shared-River Attunement

**Opened:** 2026-07-04  
**Status:** Design — dedicated session required before automating shared practice content  
**Spec trace:** TURTLE_SPEC §15.1 (shared rivers), §15.5 (boundaries)

## Why this chapter exists

Shared rivers share platform law (acts in parent, dialogue in eddies) but **need not share identical Turtle conduct**. Today:

| Space | Channel | `default_context` | Eddy conduct today |
|-------|---------|-------------------|-------------------|
| **family** | `#family` | `family` | `THREAD_CONTEXTS['family']` — warm, bilingual, ND-aware, inclusive; **plus** speaking member's personal compass loaded from sovereign workspace (`discord_bot.py`) |
| **<practitioner-2>_sandbox** | `#<practitioner-2>-sandbox` | `shared` | No `THREAD_CONTEXTS['shared']` entry → **generic native Turtle** + `shared-river-orientation` flow seed |
| **<practitioner-2>_play** (archived) | `#<practitioner-2>-play` | `shared` | Same generic path |

Family conduct is **intentionally richer** than sandbox — not an accident of migration drift alone. Whether sandbox spaces should stay generic, inherit a new `shared` context, or pick per-space contexts is **unsettled product law**.

## Design questions (for practitioner session)

1. **Should family stay a special case?** Load-bearing rules (privacy firewall, age-appropriate, compass-from-speaker) may never belong in a generic `shared` template.
2. **What is `default_context: shared` for?** Provisioning default (`space_provisioning.py`) vs meaningful attunement — today it is mostly a registry label without `THREAD_CONTEXTS` backing.
3. **Per-channel attunement overrides:** Craft uses `attunement: craft` on the channel entry. Should shared rivers support `attunement: family` / custom bundles without new code paths each time?
4. **Shared practice substrate:** Family workshop may stay intentionally empty until a live compass session. Readiness on empty space = **fresh**, not scored (implemented 2026-07-04).

## Implementation hooks (already in code)

| Mechanism | Location |
|-----------|----------|
| Channel `default_context` → eddy prompt | `mage.get_channel_default_context()`, `prompts.build_native_eddy_prompt()` |
| Context rules + resonance | `state.THREAD_CONTEXTS` |
| Family-only compass injection | `discord_bot.py` (speaking mage workspace) |
| Space provisioning template | `template/flows/shared-river-orientation.md` |
| Valid provision contexts | `space_provisioning.VALID_CONTEXTS = {"family", "shared"}` |

## Options (not decided)

**A — Keep family special, sandbox generic**  
Minimal change. Document that new sandbox/play spaces get vanilla Turtle until a design pass adds `THREAD_CONTEXTS['shared']` or space-specific contexts.

**B — Add `THREAD_CONTEXTS['shared']`**  
Neutral multi-member conduct (mention-gated defaults, no family compass loading). Family keeps `family` context as strict superset.

**C — Per-space attunement registry**  
Extend channel/space entries with optional `attunement_profile` or `conduct_bundle` path — mirrors craft override pattern, scales beyond two hard-coded contexts.

## Out of scope until session

- Automating family compass / shared intentions
- Boys' participation boundaries
- Content migration from private rivers
- Renaming Discord **Practice** category (operational hygiene — separate from attunement)

## Related chapters

- [design-family-shared-river.md](design-family-shared-river.md) — family migration + privacy firewall
- [design-admin-space-provisioning.md](design-admin-space-provisioning.md) — `!admin space create`
- [design-craft-channel.md](design-craft-channel.md) — specialized attunement precedent
