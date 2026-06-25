# turtleOS Development Learnings

Accumulated discoveries and anti-patterns across development sessions.
Append to this file after each research cycle — it persists across sessions.

---

## Session Log

<!-- Append entries below this line -->

### 2026-06-25 — Tier 1 idle wedge + registry save

**Idle wedge root cause:** `log_activity()` called `ensure_channel_bars()` while holding (or waiting on) the same per-channel `asyncio.Lock` as `dispatch_direct_command` — classic non-reentrant deadlock. Idle `checkpoint_session` → session note embed → `log_activity` was the common trigger after 15 min silence.

**Fixes:** Remove bar re-anchor from `log_activity` (callers own it); run idle checkpoint in a background task so `session_monitor` never blocks the event loop on reflection LLM; registry writes debounced + fsync + retry.

**Design:** Contextual River offers stay timeline-anchored; flow library bar re-anchors to bottom — intentional (Mage dogfood 2026-06-25).
