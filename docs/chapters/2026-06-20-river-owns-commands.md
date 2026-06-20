# Chapter — River owns turtle-talk (split-bot)

**Date:** 2026-06-20

## Intent

Align split-bot identity with platform law: **River executes acts** (bars, embeds, `!` commands); **Turtle speaks prose** in eddies. Fix bar repost regression where Turtle posted the river bar after command output.

## Changes

| Area | What |
|------|------|
| `bar_anchor.channel_for_client` | Sends use the bar client's channel object (correct bot identity) |
| `river_bot.py` | Universal `!` handler — river + eddies; Spirit + Mage + practitioners |
| `discord_bot.py` | Defers all `!` to River when `river_bot_enabled()` |
| `commands.dispatch_direct_command` | Command → act digest → bar re-anchor |
| `inject_act_digest` | `[Act: !cmd]` lines in Turtle dialogue history (not assistant prose) |
| `cmd_status` | Fixed missing `reply()` (broken since sovereignty handler removal) |
| `helpers.log_activity` | Ops embeds post as River in split-bot |
| `eddy_lifecycle_bar.py` | `RiverActSuggestionView` — seneschal rows share lifecycle execution path |
| Native seneschal | `SENESCHAL_ACTION_COMMANDS` excludes lifecycle trio; enabled on native eddies |
| Spec/docs | §5.8, turtle-talk, principles, eddy-lifecycle-bar |

## Verified

- Spirit `!help` → **river** embed + bar repost (not turtle)
- 134 tests pass locally
- Mini deploy: `d3d4516` (pull + restart + offline shake)

## Status

**Paused (2026-06-20)** — dogfood incomplete. See [2026-06-20-river-turtle-split-handoff.md](2026-06-20-river-turtle-split-handoff.md) for rethink options. Do not add more Turtle-side seneschal patches without architectural decision.
