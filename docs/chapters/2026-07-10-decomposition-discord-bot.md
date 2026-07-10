# Chapter — Decomposition: `discord_bot.py` (dialogue routing)

**Date:** 2026-07-10  
**Status:** Released — Slices 1–6 deployed Mini `c0c1b49`, Mage dogfood green (2026-07-10)  
**Deciders:** Kermit + Spirit (dyadic maintainer)  
**Builds on:** `share_eddy` decomposition chapter (released 2026-07-10)

---

## Problem

`discord_bot.py` (~1,742 lines) is the Turtle shell orchestrator: dialogue turns, message dispatch, Discord lifecycle events, and startup. The traceability matrix marks it **Partial** — next Integrate target after `share_eddy` decomposition.

Spirit is principal maintainer. Editing dialogue routing inside a god-module couples enqueue policy, native starter guards, and multi-hundred-line `handle_dialogue` / `_continue_dialogue_turn` logic — high regression cost despite broad test coverage.

**Scope decision (2026-07-10):** Slice 1 is **routing-only** — message → handler dispatch. Eddy lifecycle hooks and `on_message` branch extraction stay in later slices.

---

## Principles

Same as `2026-07-10-decomposition-share-eddy.md`:

1. **No behavior change per slice** — move code; re-export from `discord_bot.py` until callers migrate.
2. **Cohesion over line count** — routing before turn execution before event handlers.
3. **Tests travel with extraction** — `./scripts/spirit_verify.sh` green after each slice.
4. **Traceability updates** — matrix `discord_bot.py` row notes slice progress.
5. **Deploy consequence named** — routing-only slices are Forge-only; slices touching turn logic need Mini deploy + **both** `com.turtle.discord` and `com.turtle.river` restart when shared modules change.

---

## Slice map

| Slice | Module | Concern | Risk | Status |
|-------|--------|---------|------|--------|
| **1** | `dialogue_routing.py` — enqueue path, native starter skip, flow-library touch | Dispatch | **Low** | ✅ complete |
| **2** | `dialogue_message.py` — visible content, forward snapshots, ref helpers | Message surface | Low | ✅ complete |
| **3** | `dialogue_turn.py` — `handle_dialogue`, `continue_dialogue_turn`, `run_link_read_followup` | Turn execution | Medium-high | ✅ complete (Forge) |
| **4** | `dialogue_attachments.py` — gather attachments, forward chain, display names | Attachment pipeline | Medium | ✅ complete (Forge) |
| **5** | `dialogue_runtime.py` — runtime env, thread cards, source trace | Runtime context | Medium | ✅ complete (Forge) |
| **6** | `practice_dispatch.py` — `on_message` practice-channel branch tree | Event routing | Medium-high | ✅ complete (Forge) |

**Out of scope for this chapter:** `eddy_spawn.py` (~1,619 lines) — separate decomposition candidate.

---

## Slice 1 — `dialogue_routing.py` ✅ complete (2026-07-10)

**Extracted:**

- `route_practice_dialogue` — serializes via `dialogue_queue.enqueue_dialogue`
- `should_skip_native_starter` — native eddy starter guard
- `touch_flow_library_after_dialogue` — River turn signal after dialogue

**Left in `discord_bot.py` (re-export aliases):**

```python
from dialogue_routing import (
    route_practice_dialogue as _route_practice_dialogue,
    should_skip_native_starter as _should_skip_native_starter,
    touch_flow_library_after_dialogue as _touch_flow_library_after_dialogue,
)
```

**Lazy handler import:** `route_practice_dialogue` resolves `dialogue_turn.handle_dialogue` at call time to avoid circular import at module load.

**Tests:** `tests/test_dialogue_routing.py` — starter skip + enqueue wiring.

**Acceptance:**

1. `./scripts/spirit_verify.sh` green
2. No change to dialogue turn behavior (routing-only)
3. Forge-only — no Mini deploy

**Deploy:** None required for Slice 1.

---

## Next slice — `dialogue_message.py` ✅ complete (2026-07-10)

**Extracted:** `dialogue_message.py` (~145 lines) — `visible_message_content`, forward snapshot helpers, permalink ref extraction, `fetch_discord_message_context` (lazy `state.client`).

**Re-export:** All symbols as `_`-prefixed aliases from `discord_bot.py` — `craft_intake.py`, `canary.py`, tests unchanged.

**Tests:** `tests/test_dialogue_message.py` — visible content, forward ref, partial snapshot.

**Verified:** `spirit_verify.sh` green. Forge-only — no Mini deploy.

---

## Slice 3 — `dialogue_turn.py` ✅ complete on Forge (2026-07-10)

**Extracted:** `dialogue_turn.py` (~580 lines) — `handle_dialogue`, `continue_dialogue_turn`, `run_link_read_followup`.

**Re-export:** `handle_dialogue`, `run_link_read_followup`, `continue_dialogue_turn as _continue_dialogue_turn` from `discord_bot.py` — `link_read.py`, lifecycle seams, test patches unchanged.

**Coupling note:** `dialogue_turn.py` no longer imports `discord_bot` — fully decoupled turn path.

**Tests:** `test_dialogue_routing.py` mock fix (`spec=discord.Thread` for starter-skip). Full suite via `spirit_verify.sh`.

**Line count:** `discord_bot.py` 1,742 → ~1,115 lines.

**Verified:** `spirit_verify.sh` green.

**Deploy:** **Not yet shipped** — first slice with live consequence. When deployed: restart **both** `com.turtle.discord` and `com.turtle.river`; offline lifecycle/share shakes + Mage eddy dogfood before chapter close.

---

## Slice 4 — `dialogue_attachments.py` ✅ complete on Forge (2026-07-10)

**Extracted:** `dialogue_attachments.py` (~90 lines) — `attachment_display_names`, `gather_dialogue_attachments`, `attachments_from_forward_chain`.

**Re-export:** All symbols as `_`-prefixed aliases from `discord_bot.py`.

**Decoupling:** `dialogue_turn.py` imports attachment helpers directly — no lazy `_discord_bot()` for attachments.

**Tests:** New `tests/test_dialogue_attachments.py`.

**Line count:** `discord_bot.py` ~1,115 → ~1,044 lines.

**Verified:** `spirit_verify.sh` green. Forge-only until turn logic deploys.

---

---

## Slice 5 — `dialogue_runtime.py` ✅ complete on Forge (2026-07-10)

**Extracted:** `dialogue_runtime.py` (~257 lines) — `build_runtime_env`, `build_native_runtime_env`, `update_thread_state`, `build_source_trace`, `thread_card_excerpt`.

**Re-export:** All public symbols as `_`-prefixed aliases from `discord_bot.py` — `flow_bootstrap.py`, `test_resume_eddy.py` unchanged.

**Decoupling:** `dialogue_turn.py` imports runtime helpers directly — `_discord_bot()` lazy import removed entirely.

**Tests:** New `tests/test_dialogue_runtime.py`; `test_resume_eddy` patch target updated to `dialogue_runtime.read_thread_state`.

**Line count:** `discord_bot.py` ~1,044 → ~839 lines.

**Verified:** `spirit_verify.sh` green. Forge-only until turn logic deploys.

---

## Slice 6 — `practice_dispatch.py` ✅ complete on Forge (2026-07-10)

**Extracted:** `practice_dispatch.py` (~130 lines) — `dispatch_incoming_message` (full `on_message` branch tree).

**Thin handler:** `discord_bot.on_message` delegates to `practice_dispatch.dispatch_incoming_message`.

**Tests:** New `tests/test_practice_dispatch.py` — own-message skip, non-practice no-op, dialogue route wiring.

**Line count:** `discord_bot.py` ~839 → ~730 lines.

**Verified:** `spirit_verify.sh` green. Forge-only until Mini deploy.

---

## Chapter close criteria

- Slices 1–6 complete (`discord_bot.py` ≤ ~900 lines of orchestration + events) ✅
- Matrix row **Partial** → **Aligned** for dialogue routing + turn modules — after Mini deploy + dogfood
- Mini deploy after Slice 3–6 — **both** `com.turtle.discord` + `com.turtle.river` restart
- Harvest appended to `docs/learnings.md` ✅

---

## Mini deploy — Slices 3–6 (pending push)

**Blast radius:** `dialogue_turn`, `practice_dispatch`, and re-export shims — Turtle dialogue path + message dispatch. River shares `dialogue_routing` / command surface; restart **both** bots.

**Precondition:** Forge commit + push to `origin/main` (chapter files not yet on remote as of prep).

**Changed surface → shakes:**

| Surface | Offline | Live (Mini) |
|---------|---------|-------------|
| Turn execution / eddy reply | `spirit_verify.sh`, `shake_flow.py navigator` | `shake_flow.py navigator --live` |
| Dispatch / river routing | `shake_river.py` | (offline usually enough) |
| Eddy spawn / rename path | `shake_eddy_bar.py` | `shake_eddy_bar.py --live` |
| Link read in turn | `shake_link_read.py` | optional `--live` |
| Permalink self-feed | `shake_discord_ref.py` | optional `--live` |
| Lifecycle | `shake_lifecycle.py` | optional `--live` |

**Mage dogfood (UX gate):** one native eddy — send message, attachment-only message, edit message, `!checkpoint` / `!release` smoke.

### Step 1 — Forge: commit + push

Run on Forge (`/Users/kermit/Documents/turtleos`):

```bash
cd /Users/kermit/Documents/turtleos && \
git add \
  discord_bot.py \
  dialogue_routing.py \
  dialogue_message.py \
  dialogue_turn.py \
  dialogue_attachments.py \
  dialogue_runtime.py \
  practice_dispatch.py \
  tests/test_dialogue_routing.py \
  tests/test_dialogue_message.py \
  tests/test_dialogue_attachments.py \
  tests/test_dialogue_runtime.py \
  tests/test_practice_dispatch.py \
  tests/test_resume_eddy.py \
  docs/chapters/2026-07-10-decomposition-discord-bot.md \
  docs/learnings.md \
  docs/traceability-matrix.md && \
git commit -m "$(cat <<'EOF'
Decompose discord_bot dialogue stack into six modules.

Extract routing, message surface, attachments, runtime env, turn execution,
and practice dispatch so the shell is lifecycle events plus thin handlers;
spirit_verify green on Forge.
EOF
)" && \
git push origin main && \
echo "=== Forge: pushed ==="
```

### Step 2 — Mini: pull, verify, restart both bots

Run via SSH (Tailscale):

```bash
ssh turtle@100.110.46.104 'bash -s' << 'ENDSSH'
set -euo pipefail
cd ~/turtleos
git pull origin main
./scripts/spirit_verify.sh
launchctl kickstart -k "gui/$(id -u)/com.turtle.discord"
launchctl kickstart -k "gui/$(id -u)/com.turtle.river"
sleep 5
./scripts/shake_after_deploy.sh
echo "=== Mini: pull + restart + offline shakes OK ==="
ENDSSH
```

### Step 3 — Mini: live shakes (Spirit gate)

```bash
ssh turtle@100.110.46.104 'bash -s' << 'ENDSSH'
set -euo pipefail
cd ~/turtleos
export SHAKE_LIVE=1 SHAKE_WAIT=50
~/turtleos/venv/bin/python3 scripts/shake_flow.py navigator --live --wait "$SHAKE_WAIT"
~/turtleos/venv/bin/python3 scripts/shake_eddy_bar.py --live --wait "$SHAKE_WAIT"
echo "=== Mini: live shakes OK ==="
ENDSSH
```

### Step 4 — Mage dogfood

In `#river` (or a test eddy): one conversational turn, one attachment-only turn, edit a prior message, then `!checkpoint` and `!release` smoke. Felt-sense: same Turtle, no duplicate replies, no amnesia on edit.

### Step 5 — Chapter close (after green gates)

Update chapter **Status** to **Released**, matrix row to **Aligned**, append deploy commit hash to `docs/learnings.md`.
