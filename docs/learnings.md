# turtleOS Development Learnings

Accumulated discoveries and anti-patterns across development sessions.
Append to this file after each research cycle — it persists across sessions.

---

## Session Log

<!-- Append entries below this line -->

### 2026-06-30 — Generative UI E1.1 + standing bars + public artifact read

**Bars:** River bar = `new eddy` · `artifacts` · `help`. Eddy bar = `flows` · `checkpoint` · `share` (native + magic). Bar re-anchor **deferred** for `!artifacts` / `!share`; artifact select **edits in place** (Open + Export) so the bar is not sandwiched between related actions. Eddy bar activates on first practitioner message (`touch_eddy_lifecycle_bar` in `river_bot.py`).

**Public read:** `ARTIFACT_READ_TOKEN` + `PRACTICE_WEB_BASE=https://…` — Open URLs carry `?t=`; intake `/read/` rejects missing token when configured. See `deploy/caddy-practice-viewer.snippet` (public hostname + TLS; no Tailscale on practitioner device).

**E1.1 shipped:** Search embed + Open row (top 3 hits); River `present_artifacts` act type; shelf browse **Export** second button row (≤3 items); select follow-up adds Export .md; checkpoint progress embed.

**Dogfood (2026-06-30, Mage):** River bar buttons → Recent → select → Export .md **works** (thread archive landed correctly). Friction: (1) defer on `!artifacts` left bar **above** Recent when triggered from bar button; (2) `Act !… via button` ops embeds split output from standing bar. **Fix:** only `!share` defers re-anchor; drop success ops embeds for button acts (digest-only).

**Still backlog:** `generative-ui-kit.md`, optional TURTLE_SPEC §11.5.6.

### 2026-06-29 — Generative UI E1: artifact presenter (dogfood complete)

**What shipped:** `artifact_presenter.py` — intent → embed + Open actions. `!artifacts` default = **Recent** (mtime, empty shelves hidden); `!artifacts <shelf>` = shelf browse; `!artifacts --all` = full catalog (operator/shakedown). Post-checkpoint and `!read` use the same composer. Open = Discord **link buttons** (≤3) or **select menu** (>3) with URLs pre-resolved at compose time.

**Dogfood (2026-06-29, kermit practice):** All three journeys validated — `!checkpoint` → Open (session note in browser); `!artifacts` Recent + dropdown; `!artifacts sessions` link buttons. Fixes during dogfood: (1) link buttons instead of command buttons (one tap, no second embed); (2) select menu URLs must be built in `compose_artifact_surface()` — callbacks lack practice context and previously emitted `default/sessions/...` → practice viewer "Could not load"; (3) `-# Checkpointing…` ack before Ollama reflection (still ~1–2 min wait).

**Deploy lesson (critical):** River owns `!` commands in eddies (`river_bot.py` → `dispatch_direct_command`). **`com.turtle.river` and `com.turtle.discord` must both restart** when changing `cmd_sessions.py`, `cmd_practice_io.py`, or `artifact_presenter.py`. Restarting discord only left stale checkpoint UI on River until river was bounced.

**Friction (not blockers):** Checkpoint blocks on `REFLECTION_MODEL` (qwen3.5:27b) before reply; Tailscale IP triggers Discord "Leaving Discord" interstitial once; Recent >3 items uses dropdown (heavier than buttons).

**Docs:** `docs/chapters/design-generative-ui-e1-artifact-presenter.md`, `docs/ux/generative-ui-e1-experience.md`, `docs/ux/artifact-access.md` (E1 section).

**Next:** E1.1 — search Open row, River `present_artifacts` act type, export second row, hostname vs raw IP, stronger checkpoint progress UX; optional TURTLE_SPEC §11.5.6. **Strategic:** Mage validated generative UI as improvement — continue controlled-tier expansion in future sessions.

### 2026-06-28 — Native close startup unarchive anti-pattern

**Never unarchive dissolved threads on startup.** Practitioner "Close Thread" is a commitment — `on_ready` paths that call `edit(archived=False)` on every registry thread resurrect sidebar ghosts and break trust. Fix: skip unarchive when `thread_registry.is_dissolved()`; re-archive dissolved entries via `ensure_dissolved_threads_archived`. See `discord_reconcile.py` + Mini `7abf2f2`.

**S2 delete reconciliation:** Native thread delete → `remove_thread` + in-memory cleanup + parent ops log (Close ≠ Delete for essence). Native channel delete → `mark_channel_orphaned` on registry binding; workshop dirs kept.

**Opened eddy acts:** `on_thread_create` → `handle_thread_open` posts green 🌀 embed on parent river (symmetric to Closed eddy). `via_discord_ui=True` when no river `pending`; bar/`!thread` spawns pass pending so footer omits "Discord". System eddies (`vortex`, `boom`, …) skipped. Retired redundant `🌀 Thread created` parent message from `cmd_threads.py` — opened act replaces it.

**Deploy pitfall (2026-06-28):** `git pull` alone does not reload Python — verify `ps -p $(pgrep -f discord_bot.py) -o lstart=` is *after* the pull before dogfood. First kickstart after Opened eddy deploy left a 09:54 process running 10:06 code on disk; second kickstart at 10:11 fixed it. Always confirm restart, not assume.

**S3 channel create/update:** `on_guild_channel_create` posts dialogue ops notice for unregistered text channels with binding hints (no auto-bind). `on_guild_channel_update` logs rename + permission drift for registry-bound channels; syncs `discord_name`. Blessed creates use `expect_channel_registry_binding()` to skip duplicate notices.

### 2026-06-25 — Share eddy Slice 1 + flow library on-demand

**Share eddy:** Practitioner path shipped (`!share` → synthesize → preview/edit → confirm → recipient `@` + Continue → received eddy). Split-bot interaction bugs: defer/edit paths, modal must use `response.edit_message`, history filter for failed share acts. Dogfood chapter: `docs/chapters/2026-06-25-share-eddy-slice1-dogfood.md`.

**Flow library:** Standing bottom bar retired — cluttered share/rename contextual rows. Flow picker is on-demand via `!flows` / `!flow` only; legacy bars deleted on River startup and dismissed on `!share`.

### 2026-06-25 — Tier 1 idle wedge + registry save

**Idle wedge root cause:** `log_activity()` called `ensure_channel_bars()` while holding (or waiting on) the same per-channel `asyncio.Lock` as `dispatch_direct_command` — classic non-reentrant deadlock. Idle `checkpoint_session` → session note embed → `log_activity` was the common trigger after 15 min silence.

**Fixes:** Remove bar re-anchor from `log_activity` (callers own it); run idle checkpoint in a background task so `session_monitor` never blocks the event loop on reflection LLM; registry writes debounced + fsync + retry.

**Design:** Contextual River offers stay timeline-anchored. Standing flow library bar was retired 2026-06-25 — on-demand `!flows` keeps contextual rows uncluttered (share dogfood).
