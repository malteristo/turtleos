# Deploy touchpoints — Turtle + River as one unit

**Law:** `TURTLE_SPEC.md` §5.8 (two Discord apps).  
**Ritual:** `./restart.sh` kickstarts **both** `com.turtle.discord` and `com.turtle.river` when River is loaded.

When shared modules change, restarting Turtle alone leaves stale River code (and vice versa). Prefer the script over ad-hoc `launchctl` of one label.

## The deploy waits for quiet

`restart.sh` runs `scripts/deploy_guard.py` first and **refuses while a conversation is live** (default: any turn in the last 10 minutes, or an eddy write in flight).

This is not caution. A restart is not a pause — the bot identifies fresh, Discord does not replay what it missed, and nothing backfills practitioner messages at boot. A message sent in the ~15s window is never seen and never answered, and only the sender knows it happened.

```bash
python3 scripts/deploy_guard.py          # QUIET / BUSY, exit 0 / 1
./restart.sh                             # waits for quiet
./restart.sh --force                     # bypass — logged to logs/self-dev.log
```

`--force` is for the one case the rule does not cover: shipping a fix for something already broken, where fifteen seconds of gap beats leaving it broken. Bypasses are logged so they can be counted; if they become routine the threshold is wrong, not the rule.

Ad-hoc `launchctl kickstart` skips the guard entirely. Use the script.

## Module ownership (restart guidance)

| Tag | Meaning | Restart |
|-----|---------|---------|
| **both** | Imported or used by Turtle and River entrypoints | Always both |
| **river** | Acts path only (`river_bot.py`, bars, `!`, seneschal) | Both if any shared lib also changed; else River |
| **turtle** | Dialogue path only (`discord_bot.py`, dialogue stack) | Both if any shared lib also changed; else Turtle |

### both (default suspicion)

Shared libraries and state seams — treat as **both** unless proven entrypoint-local:

- `cmd_dispatch.py`, `commands.py`, `sessions.py`, `eddy_*`, `share_*`
- `dialogue_store.py`, `river_turn_signal.py`, `act_offer_signal.py`, `mage.py`, `bar_anchor.py`
- `artifact_presenter.py`, `link_read.py`, `home_plans.py` / `home_plan_ui.py`
- Continuity / practice-root writers read by either process

### river

- `river_bot.py`, `river_handler.py`, `river_eddy_seneschal.py`, `river_state.py`
- River-only act presenters that Turtle never imports

### turtle

- `discord_bot.py`, `practice_dispatch.py`, dialogue turn stack modules Turtle-only
- Background loops that only run in the Turtle process
- `offer_river_act` tool + `[[act-offer:…]]` trailer emit (signal consumed by River)

**When unsure → both.** The cost of an extra kickstart is lower than a silent wrong-bot deploy.

## Health parity

| Surface | Split-bot requirement |
|---------|----------------------|
| `canary.py` | `river_bot_alive` (high) when `RIVER_BOT_TOKEN` set |
| `runtime/readiness.py` | `com.turtle.river` in required labels when token set |
| `restart.sh` | Kickstarts River when label is loaded |

Single-bot fallback (`RIVER_BOT_TOKEN` unset): River checks skip; restart is Turtle-only.
