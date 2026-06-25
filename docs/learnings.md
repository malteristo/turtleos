# turtleOS Development Learnings

Accumulated discoveries and anti-patterns across development sessions.
Append to this file after each research cycle — it persists across sessions.

---

## Session Log

<!-- Append entries below this line -->

### 2026-06-25 — Share eddy Slice 1 + flow library on-demand

**Share eddy:** Practitioner path shipped (`!share` → synthesize → preview/edit → confirm → recipient `@` + Continue → received eddy). Split-bot interaction bugs: defer/edit paths, modal must use `response.edit_message`, history filter for failed share acts. Dogfood chapter: `docs/chapters/2026-06-25-share-eddy-slice1-dogfood.md`.

**Flow library:** Standing bottom bar retired — cluttered share/rename contextual rows. Flow picker is on-demand via `!flows` / `!flow` only; legacy bars deleted on River startup and dismissed on `!share`.

### 2026-06-25 — Tier 1 idle wedge + registry save

**Idle wedge root cause:** `log_activity()` called `ensure_channel_bars()` while holding (or waiting on) the same per-channel `asyncio.Lock` as `dispatch_direct_command` — classic non-reentrant deadlock. Idle `checkpoint_session` → session note embed → `log_activity` was the common trigger after 15 min silence.

**Fixes:** Remove bar re-anchor from `log_activity` (callers own it); run idle checkpoint in a background task so `session_monitor` never blocks the event loop on reflection LLM; registry writes debounced + fsync + retry.

**Design:** Contextual River offers stay timeline-anchored. Standing flow library bar was retired 2026-06-25 — on-demand `!flows` keeps contextual rows uncluttered (share dogfood).
