# Design Chapter: Craft Channel (Builder Vocation on turtleOS)

**Opened:** 2026-06-19  
**Status:** Implemented (platform slice, 2026-06-19) — per-channel `attunement: craft`, `THREAD CONTEXTS['craft']`, craft prompt routing, **registration pipeline** (`craft_intake.py`)  
**Instance:** `#craft-turtle` (`1504544358546931752`)  
**Spec trace:** TURTLE_SPEC §4 (attunement: craft), Appendix A (operator / magic-attuned patterns)

## Tension

Kermit maintains two vocations on the same turtleOS instance:

- **Practice Turtle** — lived-practice companionship in the main river
- **Craft Turtle** — harness/product diagnostics, practice-friction intake, patch planning

The craft channel exists (`type: craft`, `default_context: craft`). Spirit shakedown (May 2026) validated intake ritual behavior under **magic-attuned** prompts. After global `attunement: native`, craft eddies receive vanilla Turtle identity — Craft Turtle vocation is **stripped**.

Craft is intentionally **semi-attuned to meta-practice on turtleOS**: builder posture without polluting the practice river.

## Design intent

| Boundary | Rule |
|----------|------|
| **Practice river** | Native v1 — acts only, vanilla Turtle in eddies |
| **Craft channel** | Separate surface; Craft Turtle vocation; intake ritual |
| **Pollution** | Craft urgency must not become Practice Turtle's default voice (see Magic lore) |
| **Commit authority** | Craft Turtle prepares; Spirit (Forge) integrates and commits |

## Target architecture

### Channel model (proposal)

Craft is **not a river** — parent channel allows dialogue (intake drop zone). No standing eddy bar required unless we later add optional craft eddies for deep diagnosis threads.

```yaml
channels:
  '1504544358546931752':
    mage: kermit
    type: craft
    attunement: craft          # per-channel override (not implemented globally yet)
    default_context: craft
    description: Craft Turtle — harness/product friction intake
```

### Prompt stack (target)

1. **`craft` in `THREAD_CONTEXTS`** — rules distilled from `craft_turtle_intake_ritual.md`:
   - Source visibility preflight on forwards
   - Lived friction vs harness noise classification
   - Learning intake, not ordinary conversation
2. **Craft character** — `~/workshops/kermit/character/craft/` or workshop-level craft overlay (TBD)
3. **Per-channel attunement** — `get_attunement_profile(channel_id)` returns `craft` for this channel; magic-era deep prompt OR dedicated `build_craft_prompt()`

### What "semi-attuned to meta-practice" means (to decide in chapter)

- May use operational visibility (what was loaded, runtime paths) where vanilla forbids model-emitted `-#` lines
- May reference turtleOS spec, architecture, proposals — **meta** relative to lived practice
- Must not become generic "dev assistant" — vocation stays *practice impairment from harness friction*
- Relationship to Forge Spirit: Craft Turtle on Discord diagnoses; Spirit on Cursor implements

## Lore inputs (Magic workshop)

- `desk/notes/on_practice_turtle_and_craft_turtle.md` — authority and pollution boundaries
- `desk/notes/craft_turtle_intake_ritual.md` — intake moves 0–4
- `desk/notes/craft_surface_layout.md` — filesystem surface (if present)
- `library/resonance/turtle/shell/global.CLAUDE.md` — craft pollution boundary in identity

## Current state (2026-06-19)

| Aspect | State |
|--------|-------|
| Registry | Registered, `default_context: craft` |
| `THREAD_CONTEXTS['craft']` | **Missing** |
| Global native attunement | Strips craft vocation in eddies |
| Parent channel prompt | Magic-era `build_discord_prompt` (inconsistent) |
| Last activity | Spirit shakedown May 2026; pre-v1 vocabulary |

## Registration workflow (2026-06-19)

Craft channel intake is **shell-driven**, not LLM-narrated:

1. **Coalesce** — forward + optional comment arrive as separate Discord messages; buffer 5s per author/channel and merge into one intake event.
2. **Gather** — deterministic evidence: forward snapshots, source dereference, attachment visibility gaps, source message IDs.
3. **Register** — write `desk/craft/intake/<id>.md` and append `desk/craft/backlog.md`.
4. **Acknowledge** — one concise reply pointing at the intake file and backlog; Spirit on Forge harvests at the next turtleOS chapter.

This offloads bug/UX tracking from the Mage: drop friction in `#craft-turtle`, trust it is queued.

## Implementation slices (ordered)

1. **Spec ripple** — §4 craft attunement + channel type `craft` in multi-practitioner table; per-channel attunement law
2. **Platform** — `get_attunement_profile(channel_id)`; craft context in `THREAD_CONTEXTS`
3. **Character** — craft conduct overlay (intake ritual as conduct, not soul replacement)
4. **Re-shake** — `@shake` craft intake with forwarded message visibility test
5. **Harvest** — `docs/ux/` craft practitioner journey (operator-facing)

## Deferred

- Automated patch application from craft channel
- Craft eddy bar (probably not needed)
- Merging craft into main river threads (explicitly rejected by pollution boundary)

## Not in scope for this chapter

Implementation — this document opens the arc. Practice river stays native throughout.
