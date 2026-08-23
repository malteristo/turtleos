# Chapter: River Bot Split (slice 1.5)

**Date:** 2026-06-16  
**Status:** Implemented — awaiting Discord app + token on operator instance

## Problem

Native river acts (reactions, Materialize eddy buttons) posted as **turtle APP** confuse practitioners — Turtle should only appear inside eddies.

## Solution

Two Discord applications:

| Process | Token | Channel behavior |
|---------|-------|------------------|
| `discord_bot.py` | `DISCORD_BOT_TOKEN` | Eddies, `!commands`, background loops |
| `river_bot.py` | `RIVER_BOT_TOKEN` | Parent river only — acts, no prose |

When `RIVER_BOT_TOKEN` is unset, single-bot fallback preserves slice 1 behavior.

## Materialize handoff

1. River bot: `create_thread` + seed embed + pending config file
2. Turtle bot: `on_thread_create` → read pending → "Turtle joined" + config line

## Operator setup

1. Create a second Discord application (e.g. name **River**, ambient avatar).
2. Invite to river channels with: View, Send Messages, Add Reactions, Create Public Threads, Embed Links.
3. Add to `~/turtleos/.env`: `RIVER_BOT_TOKEN=...`
4. Install launchd plist from `docs/install/com.turtle.river.plist.example`
5. Restart both services.

## Shake

```bash
~/turtleos/venv/bin/python3 ~/turtleos/scripts/shake_river.py --live
```

Live Discord: river message → acts from **River** bot; materialize → seed from River, presence from Turtle.

## Remaining gap

~~Proactive embeds (interoception, practice invitations) still post from Turtle in the river~~ — gated via `suppress_turtle_river_voice()` (2026-06-16). See `2026-06-16-eddy-door-and-native-entry.md` for current native river UX.
