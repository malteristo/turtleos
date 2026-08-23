# Chapter: Eddy Door + Native Entry Polish (slices 2.5–2.6)

**Date:** 2026-06-16  
**Status:** Shipped — dogfooded on Mac Mini (`attunement: native`, two-bot)

## Problem

Per-message Materialize buttons tied eddy opening to river text. Blank eddies needed an awkward “type in river first” flow. Native `#river` still showed magic-era chrome (Spirit Control Panel, model/config cards, early “Turtle joined” before the practitioner spoke).

## Solution

### Standing Eddy Door (slice 2.5)

- River `on_ready`: pin **🌀 Eddy Door** with persistent **Materialize eddy** button
- Click → blank thread (`…`), no seed embed
- First practitioner message → River renames via `generate_topic` + chronicle
- Parent river acts → acknowledge / flow only (no per-message `offer_eddy`)

### Native entry polish (slice 2.6)

| Rough edge | Fix |
|------------|-----|
| Spirit Control Panel in `#river` | No deploy in native; auto-retire pinned/history panels on startup |
| Config card on materialize | Removed for `native_vanilla` eddies |
| “Turtle joined” before first message | Deferred until first reply (`ensure_native_presence`) |

## Practitioner journey (target)

```
#river: pinned Eddy Door only
  → Materialize eddy
  → blank thread
  → first message (content + title)
  → [Turtle joined] + Turtle reply
```

## Key files

| File | Role |
|------|------|
| `river_handler.py` | Eddy Door view, `ensure_eddy_door`, `finalize_parent_river_acts`, rename-on-first-message |
| `river_bot.py` | Door deploy, eddy rename routing |
| `eddy_spawn.py` | `spawn_blank_river_eddy`, `ensure_native_presence`, silent finalize |
| `discord_bot.py` | Retire control panel, deferred presence in `handle_dialogue` |
| `template/character/river_prompt.md` | Standing door — no per-message offer_eddy |
| `template/character/conduct.md` | Blank eddy entry, deferred presence |
| `TURTLE_SPEC.md` §7.2 | Blank vs seeded eddy law |

## Shake

```bash
~/turtleos/venv/bin/python3 ~/turtleos/scripts/shake_river.py
~/turtleos/venv/bin/python3 ~/turtleos/scripts/shake_river.py --live  # optional Ollama
```

## Next slice

**Practice root `state/`** — flow runner reads/writes; retire remaining magic persistence paths in native eddies.
