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
| Spec/docs | §5.8, turtle-talk, principles |

## Verified (Mini)

- Spirit `!help` at 10:01 → **river** embed + bar repost (not turtle)
- 127 tests pass locally

## Remaining

- Seneschal act suggestion rows unified with lifecycle bar (River-owned, public timeline, act digest)
- Commit + push when ready
