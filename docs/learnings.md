# turtleOS Development Learnings

Accumulated discoveries and anti-patterns across development sessions.
Append to this file after each research cycle — it persists across sessions.

---

## Session Log

<!-- Append entries below this line -->

### 2026-06-30 — Generative UI E1.1 dogfood: artifact browse + export UX

**Bars:** River bar = `new eddy` · `artifacts` · `help`. Eddy bar = `flows` · `checkpoint` · `share`. Bar re-anchor deferred for `!artifacts` and `!share`. On **artifacts** bar press: bar **edits in place** (artifacts highlighted, others greyed) instead of delete+repost — avoids "deleted message" confusion and shows which flow started.

**Public read:** `ARTIFACT_READ_TOKEN` + `PRACTICE_WEB_BASE=https://…` — Open URLs carry `?t=`; see `deploy/caddy-practice-viewer.snippet`.

**E1.1 shipped:** Search Open row; River `present_artifacts`; shelf Export row (≤3); checkpoint progress embed; standing bars; public read token.

**UX learnings (Mage dogfood — artifact browse + export):**

| Pattern | Lesson |
|---------|--------|
| **One file, one surface** | Stacking instructional embed + code block + attachment + action row for the same artifact reads as clutter. Pick one primary representation. |
| **Attachment = preview + download** | Discord's `.md` attachment bar is the preview (expandable) *and* the download affordance (`⋯` → Download). No separate Download button or duplicate ` ```md ` block needed. |
| **No redundant titles** | Filename on the attachment bar is enough — drop bold display-name lines above the preview. |
| **Export handoff compression** | Iterated: ops embed → full Phone/Desktop envelope → `-#` hint line → **attachment only**. Each step was still heavy until the last. |
| **Bar during browse** | Delete+repost bar mid-flow breaks continuity. Edit bar to **active state**, defer re-anchor until artifact pick completes. |
| **Select → replace, don't layer** | Dropdown pick should **replace** the Recent browse message — not "tap below to open" + Recent embed + buttons underneath. |
| **Open in browser** | Keep as optional link button below attachment when web read is configured — secondary to in-chat preview, not a third copy of the content. |

**Final select flow (Mini `7cd65dd`):** Recent embed + select → pick → message becomes `.md` attachment preview + optional **Open in browser** → river bar re-anchors at bottom.

**Deploy lesson (unchanged):** Restart **`com.turtle.river` and `com.turtle.discord`** when changing shared command/presenter modules.

**Still backlog:** `generative-ui-kit.md`, optional TURTLE_SPEC §11.5.6, HTTPS dogfood on public hostname.

**Release hygiene (2026-06-30):** `shake_eddy_bar.py` live checks updated for standing lifecycle bar (`flows` · `checkpoint` · `share`) — old script expected flow library bar. Design doc acceptance criteria marked complete.

**Implementation notes:** Eddy bar activates on first practitioner message (`touch_eddy_lifecycle_bar`). Success ops embeds dropped for button acts (digest-only). Export iteration: ops embed → download envelope → `-#` hint → attachment-only.

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

### 2026-07-04 — Maintenance chapter: ops harvest + lifecycle status

**Ops loop:** `e436667` fixed stale ops-gate tests; kickstart → `LastExitStatus=0`. Mini tests: use `./venv/bin/python3` (system python lacks venv deps). Native topology harvest: Forge pulls `state/notes/automation-reports/` via Magic `sync_practice_root.sh` — no `~/workshop` clone required.

**R4/R5 lifecycle:** `dialogue_store` + `reload_history` + honest release embed already shipped; `shake_lifecycle.py` offline green. Remaining: live Discord re-dogfood. Checkpoint copy now names exchange counts and reflection threshold.

**R4/R5 live (2026-07-04):** `shake_lifecycle.py --live` pass after fixing act-digest re-write on `!release` (`COMMANDS_SKIP_ACT_DIGEST`). **Deploy pitfall:** split-bot deploy must restart **both** `com.turtle.discord` and `com.turtle.river` — River-only code changes silently persist if only Turtle is kickstarted.

**S3 channel create/update:** `on_guild_channel_create` posts dialogue ops notice for unregistered text channels with binding hints (no auto-bind). `on_guild_channel_update` logs rename + permission drift for registry-bound channels; syncs `discord_name`. Blessed creates use `expect_channel_registry_binding()` to skip duplicate notices.

### 2026-06-25 — Share eddy Slice 1 + flow library on-demand

**Share eddy:** Practitioner path shipped (`!share` → synthesize → preview/edit → confirm → recipient `@` + Continue → received eddy). Split-bot interaction bugs: defer/edit paths, modal must use `response.edit_message`, history filter for failed share acts. Dogfood chapter: `docs/chapters/2026-06-25-share-eddy-slice1-dogfood.md`.

**Flow library:** Standing bottom bar retired — cluttered share/rename contextual rows. Flow picker is on-demand via `!flows` / `!flow` only; legacy bars deleted on River startup and dismissed on `!share`.

### 2026-06-25 — Tier 1 idle wedge + registry save

**Idle wedge root cause:** `log_activity()` called `ensure_channel_bars()` while holding (or waiting on) the same per-channel `asyncio.Lock` as `dispatch_direct_command` — classic non-reentrant deadlock. Idle `checkpoint_session` → session note embed → `log_activity` was the common trigger after 15 min silence.

**Fixes:** Remove bar re-anchor from `log_activity` (callers own it); run idle checkpoint in a background task so `session_monitor` never blocks the event loop on reflection LLM; registry writes debounced + fsync + retry.

**Design:** Contextual River offers stay timeline-anchored. Standing flow library bar was retired 2026-06-25 — on-demand `!flows` keeps contextual rows uncluttered (share dogfood).
