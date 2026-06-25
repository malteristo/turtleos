# Chapter — Share eddy Slice 1 dogfood + flow library on-demand

**Date:** 2026-06-25  
**Status:** Slice 1 shipped · practitioner path dogfooded · space share deferred  
**Design:** [design-share-eddy.md](design-share-eddy.md) · **Acceptance:** S1 in [acceptance/README.md](../acceptance/README.md)  
**Spec:** TURTLE_SPEC §15.6 (practitioner target), §5.6 (flow on-demand)

---

## Harvest

**Share eddy (thinking together)** shipped as a single primitive with practitioner routing. Kermit dogfooded multiple shares to Nesrine (birthday heat logistics, fungal networks, install test eddy). The core loop works: synthesize → preview → confirm → recipient `@` + digest + Continue → received eddy with seeded history.

**Flow library UX pivoted** during the same dogfood arc: the standing bottom “Load a guided flow…” bar cluttered contextual River actions (share preview, rename nudges). Flow picker is now **on-demand only** via `!flows` / `!flow` — same opt-in pattern as `!share`.

---

## Shipped UX (practitioner share)

| Step | What the practitioner sees |
|------|----------------------------|
| Entry | `!share` inside a live eddy (minimum ~2 dialogue turns) |
| Picker | Practitioners section — registry targets, not Discord membership |
| Synthesize | Pause while LLM generates `display_title` + digest from history |
| Preview | **Confirm share** embed — title, digest, Edit / Cancel / Share |
| Edit | Modal (title + digest); dismiss = cancel edit only |
| Rename nudge | Optional contextual thread rename when placeholder title lags share label; **supersedes** prior nudge on edit |
| Confirm | Sender message updates to “Shared … with …”; sender chronicle act |
| Recipient | `@` + digest River act + **Continue** button |
| Received eddy | Opening embed + attribution line; full transcript in Turtle context only (not replayed as Discord spam) |
| First reply | Sharer `@` + River act when recipient first speaks in received eddy (1:1, not only space) |

**Not shipped (deferred):** Spaces picker, shared-river target, re-share transparency, dissolve creator-only, “Show full transcript” expand.

---

## Implementation map

| File | Role |
|------|------|
| `share_eddy.py` | Export bundle, picker/preview/modal, deliver, Continue, rename offer hook, stale act cleanup |
| `commands.py` | `!share` in `DIRECT_COMMANDS` |
| `cmd_dispatch.py` | River executes `!` in eddies |
| `river_bot.py` | Share views on River client; legacy flow bar retirement on startup |
| `discord_bot.py` | `maybe_notify_sharer_on_first_peer_reply` in dialogue path |
| `eddy_flow_library.py` | Rename offer supersede; `retire_standing_flow_library_bars` |
| `scripts/shake_share_eddy.py` | Offline verification |
| `tests/test_share_eddy.py` | Unit coverage |

---

## Split-bot gotchas (save the next implementer time)

| Symptom | Cause | Fix |
|---------|-------|-----|
| Picker select does nothing useful | `message.client.add_view` on River-owned message | `get_share_bot_client()` |
| Preview never appears after target pick | `interaction.edit_message` after `defer()` | `interaction.message.edit()` or `edit_original_response()` |
| Modal submit flashes error, preview still updates | `interaction.message.edit()` without acknowledging modal | `interaction.response.edit_message()` |
| Continue fails / polluted received eddy | Failed share act in history; wrong `sync_history` signature | `filter_share_history()`; set history then `sync_history(id)` |
| Raw snippet digest | Sync fallback only | LLM `synthesize_share_metadata()` |
| Duplicate digest in received thread | Full embed repeated | One-line `-#` attribution inside eddy |
| Stale rename nudges stacked | New `channel.send` each time | Delete prior rename message before repost |
| Flow picker between share actions | Legacy standing bar + re-anchor | On-demand `!flows`; dismiss on `!share`; retire on River startup |

---

## Flow library on-demand (2026-06-25)

**Before:** Bottom flow library bar auto-activated on first practitioner message and re-anchored to thread bottom on activity.

**After:**
- No standing flow bar on eddy activity
- `!flows` or `!flow` in an eddy posts inline **Flow library** embed + picker
- `!share` dismisses any legacy bar in that thread before opening picker
- River `on_ready` deletes tracked legacy bar messages and clears thread state
- `bar_anchor` no longer re-anchors flow library bars

**Rationale:** Contextual River affordances (share, rename, seneschal offers) stay timeline-anchored; a standing bar between them was distracting in dogfood.

---

## Dogfood status

| Scenario | Status |
|----------|--------|
| S1 — Share to practitioner (sender path) | **Dogfooded** 2026-06-25 — multiple eddies, edit modal, rename, confirm |
| S1 — Recipient Continue + first-reply notify | **Pending** — awaits Nesrine-side completion |
| S2–S6 — Space share, re-share, dissolve | **Not started** — requires `shared-river` ([design-family-shared-river.md](design-family-shared-river.md)) |

---

## Deploy verification

```bash
cd ~/turtleos && git pull origin main
~/turtleos/venv/bin/python3 scripts/shake_share_eddy.py
launchctl kickstart -k gui/$(id -u)/com.turtle.discord
launchctl kickstart -k gui/$(id -u)/com.turtle.river
```

---

## Open threads (next chapter)

1. **Slice 2** — `shared-river` harness per family design chapter  
2. **Slice 3** — Space picker, member notify, sharer notify on first peer reply in space, transparency acts  
3. **Slice 4** — Guest → Family share without Discord channel membership  
4. **Acceptance close-out** — Mark S1 fully passed after recipient dogfood  
5. **Install journey ripple** — onboarding copy already says flows optional; remove “bottom bar appears” step  

---

## Related doc updates (this release)

- `TURTLE_SPEC.md` §5.6 — flow on-demand  
- `docs/turtle-talk.md` — `!share`, `!flow`, flow on-demand  
- `docs/learnings.md` — session log  
- `docs/acceptance/README.md` — S1 status  
- `docs/traceability-matrix.md` — §15.6 Slice 1 complete  
