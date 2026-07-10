# turtleOS Development Learnings

Accumulated discoveries and anti-patterns across development sessions.
Append to this file after each research cycle — it persists across sessions.

---

## Session Log

<!-- Append entries below this line -->

### 2026-07-10 — `discord_bot.py` decomposition Slice 6 (`practice_dispatch.py`)

**Extract:** `on_message` branch tree → `practice_dispatch.dispatch_incoming_message`. Thin `@client.event` wrapper in `discord_bot.py`.

**Tests:** New `tests/test_practice_dispatch.py`.

**Gate:** `spirit_verify.sh` green. Forge-only until Mini deploy.

**Next:** Mini deploy (Slices 3–6) + offline shakes + Mage eddy dogfood; optional lifecycle-event slice as follow-on chapter.

### 2026-07-10 — `discord_bot.py` decomposition Slice 5 (`dialogue_runtime.py`)

**Extract:** Runtime env + thread cards → `dialogue_runtime.py` (~257 lines). Re-export from `discord_bot.py`. `dialogue_turn.py` fully decoupled from `discord_bot` — no lazy import.

**Tests:** New `tests/test_dialogue_runtime.py`; resume-eddy patch target updated.

**Gate:** `spirit_verify.sh` green. Forge-only until Mini deploy.

**Next:** Slice 6 — `practice_dispatch.py` (`on_message` branch tree).

### 2026-07-10 — `discord_bot.py` decomposition Slice 4 (`dialogue_attachments.py`)

**Extract:** Attachment pipeline → `dialogue_attachments.py` (~90 lines). Re-export from `discord_bot.py`. `dialogue_turn.py` now imports attachments directly — lazy `_discord_bot()` coupling removed for attachment path.

**Tests:** New `tests/test_dialogue_attachments.py`.

**Gate:** `spirit_verify.sh` green. Forge-only until Mini deploy.

**Next:** Slice 5 — runtime env builders or `on_message` dispatch tree.

### 2026-07-10 — `discord_bot.py` decomposition Slice 3 (`dialogue_turn.py`)

**Extract:** Turn execution → `dialogue_turn.py` (~580 lines). `handle_dialogue`, `continue_dialogue_turn`, `run_link_read_followup` moved; re-export from `discord_bot.py`. `dialogue_routing` now resolves handler via `dialogue_turn.handle_dialogue`.

**Coupling:** Lazy `_discord_bot()` for attachment gatherers + runtime-env builders — Slice 4 removes this.

**Tests:** Fixed `test_dialogue_routing` thread mocks (`spec=discord.Thread`) so `isinstance(..., discord.Thread)` passes.

**Gate:** `spirit_verify.sh` green. **Forge-only until Mini deploy** — restart both `com.turtle.discord` and `com.turtle.river` when shipped.

**Next:** Slice 4 — `dialogue_attachments.py`.

### 2026-07-10 — `discord_bot.py` decomposition Slice 2 (`dialogue_message.py`)

**Extract:** Message surface helpers → `dialogue_message.py` (~145 lines). Re-export from `discord_bot` preserves `craft_intake`, `canary`, test patch paths.

**Tests:** New `tests/test_dialogue_message.py`.

**Gate:** `spirit_verify.sh` green. Forge-only — no Mini deploy.

**Next:** Slice 3 — `handle_dialogue` + `_continue_dialogue_turn` (deploy consequence when shipped).

### 2026-07-10 — `discord_bot.py` decomposition Slice 1 (`dialogue_routing.py`)

**Extract:** `route_practice_dialogue`, `should_skip_native_starter`, `touch_flow_library_after_dialogue` → `dialogue_routing.py`. Lazy import of `discord_bot.handle_dialogue` at enqueue time avoids circular load.

**Tests:** New `tests/test_dialogue_routing.py`.

**Gate:** `spirit_verify.sh` green. Forge-only — no Mini deploy (routing-only).

**Next:** Slice 2 — `dialogue_message.py` (visible content + forward snapshot helpers).

### 2026-07-10 — Spirit maintainability sweep

**Test drift:** `test_close_delegates_action_first` expected legacy copy `1 entries`; `post_eddy_lifecycle_feedback` now reports `dissolved (N insights archived)`. Test updated to match product copy — not a runtime regression.

**Spirit verify:** `./scripts/spirit_verify.sh` — one-command unit gate for Forge/Mini chapters. Full deploy suite remains `docs/automation/functional-gate-protocol.md`.

**Matrix:** §8.4 checkpoint/release → **Aligned** (2026-07-04 live shake); test count ~437; `discord_bot.py` line estimate refreshed.

### 2026-07-10 — `share_eddy` decomposition Slice 1 (`share_targets.py`)

**Extract:** Registry addressing (`ShareTarget`, `SpaceShareTarget`, `list_*_targets`, river/runtime paths, space membership) moved to `share_targets.py` (~176 lines). `share_eddy.py` re-exports for backward compatibility — `commands.py` and existing tests unchanged at import sites.

**Tests:** New `tests/test_share_targets.py`; target tests removed from `test_share_eddy.py`. Patches for extracted functions must target `share_targets.get_registry` (not `share_eddy.get_registry`).

**Gate:** `spirit_verify.sh` 439 OK after Forge `venv` install. `shake_share_eddy.py` still invokes system `python3` when pytest absent — use venv for share-only unittest if shake flakes locally.

**Next:** Slice 2 — `share_transcript.py` (pure export/digest helpers).

### 2026-07-10 — `share_eddy` decomposition Slice 2 (`share_transcript.py`)

**Extract:** History filter, digest, export bundle builders, LLM enrich (`synthesize_share_metadata`), embed builders, and `label_shared_history` moved to `share_transcript.py` (~283 lines). `share_eddy.py` re-exports; export JSON schema unchanged.

**Tests:** New `tests/test_share_transcript.py`; transcript tests removed from `test_share_eddy.py`. Mock patches for enrich must target `share_transcript.synthesize_share_metadata`.

**Gate:** `spirit_verify.sh` 440 OK.

**Next:** Slice 3 — `share_storage.py` (inbox/pending/received paths).

### 2026-07-10 — `share_eddy` decomposition Slice 3 (`share_storage.py`)

**Extract:** Inbox/pending/received path helpers, JSON read/write, active river acts tracking, and `supersede_stale_share_acts` moved to `share_storage.py` (~193 lines). `share_eddy.py` now ~1,652 lines; re-exports preserve caller imports.

**Tests:** New `tests/test_share_storage.py`; storage tests removed from `test_share_eddy.py`.

**Gate:** `spirit_verify.sh` 442 OK.

**Next:** Slice 4 — `share_policy.py` (shared-eddy response + dissolve authority).

### 2026-07-10 — `share_eddy` decomposition Slice 4 (`share_policy.py`)

**Extract:** Context scaffolding, mention-gate, dissolve authority, witness/skip, and `_received_eddy_notify_config` moved to `share_policy.py` (369 lines). `share_eddy.py` now ~1,323 lines; `discord_bot.py` callers unchanged via re-export.

**Tests:** New `tests/test_share_policy.py` (16 tests). Registry patches must target `share_policy.get_registry` for `sharer_is_space_member` / `space_member_addresses`.

**Gate:** `spirit_verify.sh` 443 OK.

**Next:** Slice 5 — `share_delivery.py` (async delivery + notify; first slice with potential Mini deploy).

### 2026-07-10 — `share_eddy` decomposition Slice 5 (`share_delivery.py`)

**Extract:** Async delivery/materialize/notify paths + `ShareContinueView` moved to `share_delivery.py` (619 lines). `share_eddy.py` now ~766 lines (UI + `cmd_share` only).

**Tests:** New `tests/test_share_delivery.py`; `test_share_eddy.py` reduced to client smoke.

**Gate:** `spirit_verify.sh` 444 OK.

**Next:** Slice 6 — `share_ui.py` (final extraction; then chapter close + optional Mini deploy).

### 2026-07-10 — `share_eddy` decomposition Slice 6 (`share_ui.py`)

**Extract:** All `discord.ui` views/selects/modals, `get_share_bot_client`, `register_persistent_share_views`, and `cmd_share` moved to `share_ui.py` (~653 lines). `share_eddy.py` is now a thin re-export shim (~170 lines) — callers unchanged.

**Tests:** New `tests/test_share_ui.py`; retired `test_share_eddy.py`. `test_eddy_flow_library` dismiss-bar assertion targets `share_ui.py`.

**Gate:** `spirit_verify.sh` 445 OK.

**Chapter close (Forge):** decomposition complete. **Deploy:** Mini `03139c8`; restarted Turtle + River; offline shake PASS. Live gate: Mage S1 dogfood (`shake_share_eddy.py --live` not implemented).

### 2026-07-10 — `share_eddy` decomposition chapter released

**Close-out:** Doc drift fixed (acceptance, ARCHITECTURE, matrix, functional-gate-protocol). Chapter status → Released. §15.6 matrix row stays **Partial** until space S2–S6 dogfood — that is separate scope.

**Next chapter candidate:** `discord_bot.py` dialogue routing extraction.

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

### Phase D — magic-attuned code retirement (2026-07-08)

**Deleted modules:** `legacy_seneschal.py`, `proprioceptor.py`, `pulse.py`, `attunement.py`, `load_command.py`, `boom_thread.py`.

**Stripped gates:** `discord_bot.py` (proprioceptor, boom-thread, offer_eddy), `mage.py` (`workshop_root`, `attunement: magic`), `tos_tools.py` (workshop prefixes). Registry `attunement: magic` logs warning and runs native.

**Spec:** TURTLE_SPEC Appendix A marked retired. Native-only is the only deployment mode in code.

### Self-development authority ceiling (2026-07-08)

**Law:** `TURTLE_SPEC.md` §20 — inspect, propose, pre-defined self-healing only.

**Registry fix:** `self_heal.py` had stale LiveSync restart paths wired to a canary check that actually measured practice-file freshness (`boom.md` / `compass.md` age). Renamed check to `practice_freshness`; only `ollama` auto-heals.

**Native freshness (2026-07-10):** Aggressive purge — `magic_desk`/`hosted` topology branches removed. All rivers use `state/current.yaml` + `sessions/` only. Boom/compass/bright portable files, workshop_survey bridge, control panel auto-deploy, and `practice.append_boom` retired.

**Prompt/runtime alignment:** `global.CLAUDE.md` no longer grants ad-hoc `launchctl` shell healing — must match `HEAL_REGISTRY`.
