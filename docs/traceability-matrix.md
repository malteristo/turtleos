# turtleOS Traceability Matrix — the single development index

**Date:** 2026-06-20 · **absorbed the priority stack 2026-08-02** · **rows added 2026-08-14** (transport boundary, offer ledger, source-inspection window)  
**Status:** Living artifact — update at every chapter close  
**Purpose:** Spec § → implementation → verification → docs. Answers “can we rewrite from law?” by naming gaps explicitly. Since 2026-08-02 it also carries the **decision layer**: which tier, which gate, which scenario.

**How to use:** Each row is one load-bearing behavior. Status drives the next chapter. **Action** column: `Keep` | `Integrate` | `Strangle` | `Retire`.

**Verification tiers:** `unit` = `./scripts/spirit_verify.sh` (runs `venv/bin/python3 -m unittest discover -s tests`); `shake` = `scripts/shake_*.py`; `dogfood` = Discord acceptance (human).

*Use the script, not bare `python3`.* A bare interpreter without the venv cannot import `discord`, so five test modules fail to load and six more fail — 1477 tests run and eleven look broken, when nothing is. That reads exactly like a regression, and cost a detour on 2026-08-18.

**Companion:** [acceptance/README.md](acceptance/README.md) is the scenario **catalogue** — the definitions behind the H/R/D/J/S/O/X ids used here and across the chapters. It is reference data, not a second index; judgment lives in this file.

---

## Why there is only one index now

Three documents each claimed to consolidate this work, and each stated a cadence on its own face that nothing re-ran. Measured 2026-08-02:

| Doc | Its own claim | Behind |
|---|---|---|
| this file | *update at every chapter close* | 16 commits |
| `priority-stack.md` | *use this before starting a chapter* | 80 commits |
| `acceptance/README.md` (as priority filter) | *tag work against the stack* | 104 commits |
| `ARCHITECTURE.md` § Spec Traceability | *the implementation guide for a rebuild* | not counted until 2026-08-18 — removed |

There were four. The fourth was found on 2026-08-18 by someone asking why two files were both called architecture: a second spec→module table inside `ARCHITECTURE.md`, addressed to "TURTLE_SPEC v2.4" against a date-versioned spec, still calling `!diagnose` pending after it shipped, with one row carrying columns pasted from this file. A consolidation that counts the indexes it knows about does not find the one nobody named. The class is worth keeping: **when you consolidate views, enumerate by shape — every table whose columns are spec section and module — not by the names you already have.**

A view with no named reader goes stale, and three of them disagree in a way that is worse than one being late. The priority stack's **decision layer** is preserved below verbatim in substance; its per-capability tier tables — the part that drifted — are in git history at `e7c9b2f` if a specific old assignment is ever wanted.

No `Tier` column was added to the rows below. The stack's tiers are per *capability* and these rows are per *spec behavior*; the mapping is not one-to-one, and filling 48 cells by inference would manufacture priority rather than record it.

**Drift is now measured, not remembered:** `python3 scripts/turtleos_state.py` in the magic workshop counts commits since this file last changed, alongside open defects and story-layer coverage. That count is the named re-run this file never had.

---

## Choosing the next chapter

**Two axes, not one ladder.** Navigation (*what do I reach for while practicing?*) is separate from reliability (*what must not break silently?*).

| Tier | Meaning | Investment rule |
|------|---------|-----------------|
| **0** | Daily loop — must feel great | Dogfood first; hard problems are still Tier 0 |
| **1** | Must work reliably | Fix wedges before new affordances |
| **2** | When I want it | Don't preempt Tier 0–1 |
| **3** | Not the operator's primary loop | Plumbing OK; defer UX polish |

**Product layers (install story):** Layer 1 — install anywhere, Discord river, `new eddy`, talk, paste links, resume threads: sovereign ChatGPT-style daily use, **Tier 0**, must feel great for everyone. Layer 2 — flows and intentions depth, **Tier 2**, served when pulled. Do not lead with flows at install.

**Chapter gate — before implementing:**

1. **Tier?** (0 / 1 / 2 / 3)
2. **Axis?** (navigation / reliability / opt-in / other-population)
3. **Acceptance?** (an H/R/D/J/S/O row in the catalogue, or a new one)
4. **The operator's own loop?** (dogfoodable within the week without forcing it)
5. **Conflation?** (link-read vs `!fetch` · web vs Discord URL · Turtle vs River ingest · Magic release vs Discord thread)

If tier ≥ 2 while Tier 1 blockers remain, **default defer** unless the slice unblocks Tier 0–1.

**Two gates on every scenario** (2026-06-26): **Spirit** closes the functional gate — shake/unittest plumbing, verdict JSON — *before* the **Mage** tests feel, async, in practice. Spirit-green is not Mage-green. See [automation/functional-gate-protocol.md](automation/functional-gate-protocol.md).

### Known mis-prioritization patterns

| Pattern | Symptom | Redirect |
|---------|---------|----------|
| **Command inventory drift** | Polishing `!fetch` while paste-URL is the actual loop | Tier 0 link-read (H1) |
| **Magic release transplant** | Standing release/dissolve bar; idle checkpoint spam | Discord thread *is* the save; D1/D2/D3 |
| **River does Turtle's fetch** | Discord summary posted by River | Turtle self-feed, parity with web |
| **Pop 1 proxy** | Flow-first install, or a front-door flow as the demo | Layer 1 blank eddy + generic onboarding |
| **Spirit-green ≠ Mage-green** | Shake passes; the thing feels untested | D1 + H1 dogfood |
| **Hot-day slice** | No tier tag anywhere on the work | Re-read this section |

**Discord mastery (design stance):** compose with Discord, scaffold only where the model cannot reach. The human gets search, permalinks, thread list, re-entry. Turtle gets link-read, Discord-URL self-feed, practice-root `!search`. River gets structural acts. Do not reinvent Discord search; **do** make permalinks as legible to Turtle as URLs already are.

---

## Status legend

| Status | Meaning |
|--------|---------|
| **Aligned** | Native path matches spec; tested |
| **Partial** | Works under conditions; legacy coexistence |
| **Legacy** | Magic-attuned path still default on operator instance |
| **Gap** | Spec requires; not implemented on native path |
| **Retire-pending** | Spec forbids; code still reachable |

---

## Matrix

| Spec § | Behavior | Target module(s) | Current module(s) | Status | Tests / shake | Doc | Action |
|--------|----------|------------------|-------------------|--------|---------------|-----|--------|
| §5.1–5.2 | River silent witness; no prose | `river_handler.py`, `river_bot.py` | same | **Aligned** (native) | `test_river_handler` | `turtle-talk.md`, `ARCHITECTURE.md` | **Keep** |
| §5.3 | Standing eddy bar last in channel | `river_handler.post_river_eddy_bar`, `bar_anchor.py` | same | **Aligned** | `test_bar_anchor`, `shake_eddy_bar.py` | `docs/ux/eddy-lifecycle-bar.md` | **Keep** |
| §5.4 / §7.2 | Blank/flow eddy materialize; blank-eddy title is **not** a routing signal | `eddy_spawn.py` (`BARE_INTAKE_PATTERNS`), `river_handler.py` | same | **Partial** (INT-044 fixed 2026-07-28 — spec §7.2 mandates the title `new eddy` while `INTAKE_PATTERNS` reserved the same string; the guard `is_native_river_eddy` reads popped/cross-process state and loses routinely) | `test_river_handler` (blank-eddy-never-intake + emoji path pinned), `shake_spawn_eddy.py` live green | chapter `2026-06-18-eddy-bar.md`, learnings 2026-07-28 | **Integrate** — INT-045: identify intake threads positively from the registry, retire name matching |
| §5.5 | River owns `!` on parent channel | `commands.py`, `river_bot.py` | same | **Aligned** (native) | `test_command_dispatch`, `test_eddy_lifecycle_bar` | `turtle-talk.md` | **Keep** |
| §5.8 | River vs Turtle Discord identity | `river_bot.py`, `discord_bot.py` | same | **Partial** | `test_eddy_rename` (split-bot); dogfood acceptance ch. | chapter `2026-06-16-river-bot-split.md` | **Integrate** — duplicate lifecycle bars; Turtle posts bar via unlogged `river_client` |
| §5 / §15 | Multi-parent eddy rejoin after restart | `mage.practice_parent_channel_ids`, `river_bot._rejoin_practice_threads`, `discord_bot` on_ready, `river_add_turtle` on turn | same | **Aligned** (2026-07-16 INT-038) | `test_practice_parent_rejoin` | learnings 2026-07-16 Galactic Adventure | **Deploy** — restart both bots; verify shared-river inbound post-restart |
| §6.2–6.3 | Chronicle surface + deep.jsonl | `chronicle` modules | partial in `thread_registry`, handlers | **Partial** | sparse | `TURTLE_SPEC` §6 | **Integrate** — jump URLs incomplete |
| §6.4 | Sediment cross-eddy memory | deferred | — | **Gap** (deferred) | — | §6.4 | **Defer** — backlog, not v1 |
| §6.5 | Eddy note — voice branches on member cardinality (solo = 2nd person; 2+ members = attributed witness) | `story_notes.py` (`_transcript`, `_speaker_and_body`, `_WITNESS_SYSTEM_PROMPT`), `mage.space_members_for_practice_dir` | same | **Aligned** (2026-07-28, INT-040) | `test_witness_voice` (attribution, branch), `test_story_notes` | `design/per-member-periodic-notes.md` §2, charter §3.3 | **Keep** — spec §6.5 does not yet describe the branch; amendment pending |
| §6.5 | Per-utterance authorship survives into synthesis; entry records `participants` | `story_notes._participants`, `_compose_entry` front matter | same | **Aligned** (2026-07-28) | `test_witness_voice` transcript suite | design §4, §7 | **Keep** — history already carried `[name]:`; the fix was to stop discarding it |
| §6.5 | Daily note delivery routes to the **owning** river; shared-space roots post nowhere; unknown roots fail closed | `mage.river_channel_id_for_practice_dir` / `_for_mage_key`, `story_daily.post_daily_note_river_visibility` | same | **Aligned** (2026-07-28, INT-042) | `test_daily_note_routing` (states the regression directly) | learnings 2026-07-28, design §5 | **Keep** — spec §6.5 still says "on the river" (ambient singular); amendment pending |
| §6.5 | Scheduled/catchup daily notes are **root-explicit** — every registered practice root gets its own day; done-keys are per-root; catchup never falls back to primary | `story_daily.run_scheduled_daily_note`, `maybe_run_daily_note_catchup`, `mage.list_registered_practice_dirs`, `mage.current_practice_dir`, `river_bot.on_message` | same | **Aligned** (2026-07-29, INT-046) | `test_story_daily_triggers` (non-primary writes; done-key isolation; no-context no-op) | learnings 2026-07-29 INT-046 | **Keep** — Cluster A residual: other `get_pd()` ambient sites still fall back |
| §5 / river | Standing eddy-bar message ids are stored under the **owning** runtime root; foreign keys are dropped on rewrite | `river_handler._save_eddy_bar_message`, `_eddy_bar_state_path_for_channel` | same | **Aligned** (2026-07-29, INT-050) | `test_river_bar_floor::EddyBarOwnershipTests` | learnings 2026-07-29 INT-050 | **Keep** — deploy cleans kermit file on next operator bar post |
| §6.5 | Per-member daily notes — N readings of one attributed record, each to its member's own river | `story_daily.write_member_daily_notes`, `post_member_daily_notes`, `_MEMBER_SYSTEM_PROMPT` | same | **Aligned** (2026-07-28; live dry-run only — no note written for real yet) | `test_witness_voice` (one call per member), `test_daily_note_routing::MemberNoteRoutingTests` | design §4–5 | **Integrate** — dogfood a real day before weekly/monthly |
| §6.5 | Practitioner naming reconciled from `discord_id`, not curated handles | `mage.member_address_map`, `_discord_aliases` | same | **Aligned** (2026-07-28) | `test_witness_voice::AliasResolutionTests` | design §6.1 | **Keep** — 3 of 4 practitioners failed to map before this |
| §6.5 | Shared-space notes must not read a member's private alive layer / intentions | `story_daily.write_daily_note` (alive line suppressed when witness) | same | **Aligned** (2026-07-28) | covered by daily branch tests | charter §3.2, design §6.2 | **Keep** — standing crossing is forbidden; pull stays member-initiated |
| §6.5 | Period notes (week / month) | — | — | **Gap** | — | design §8 item 5 | **Defer** — dogfood daily first |
| §6.5 | Source-claim honesty — Turtle must not assert it read an unreachable space | — | — | **Gap** (INT-041) | — | `design/provenance-guard.md` §Source claims | **Integrate** — generation-layer refusal + distillation gate |
| §3.2 | The context packet a turn used persists as a practitioner-readable file; `!context` renders named injects, tools, files, empty slots, and the room-memory candidate set — not the alive layer | `turn_packet.py`, `continuity_engine.render_scope_block`, `dialogue_turn.continue_dialogue_turn`, `commands.cmd_context` | same | **Aligned** (2026-08-18 evening) | `test_turn_packet` (firewall + shared-root + dropped unknown keys + considered section, absent when nothing was on offer); `test_continuity_engine` (candidate set names what was *not* carried; focus reaches past the recency cut, with a control that the test fails under the old cut-then-rank order); `test_dialogue_turn_trunk.TurnPacketPersistenceTests` | TURTLE_SPEC §3.2, `docs/turtle-talk.md` | **Keep** — living verify: `!context` after one craft-turtle turn |
| — | Turtle can survey registered channels and eddies (read-only) | `space_survey.py`, `tos_tools.survey_space` / `survey_eddies` | same | **Aligned** (2026-08-18, Session 1 cut) | `test_space_survey` (populated fixture is non-empty; empty registry is empty; dispatch returns JSON) | `desk/proposals/turtle-space-awareness-tools.md` | **Keep** — remaining wrappers named not built: `get_channel_info`, members, `practice_freshness`. `read_alive` struck (would reopen the alive-layer firewall) |
| §7.1–7.2 | Turtle dialogue eddy-only | `discord_bot.handle_dialogue` | same + legacy river path | **Partial** | `test_native_prompts` | `native-harness.md` | **Strangle** magic main-channel dialogue |
| §7.4–7.5 | Turtle model + native character | `prompts.py`, `models.py` | same | **Aligned** (native eddy) | `test_native_prompts`, `test_flow_runner` | `template/character/` | **Keep** |
| §7.7 | Presence indicators | `eddy_lifecycle`, spawn | mixed legacy + native | **Partial** | `test_flow_runner` presence | `docs/ux/` | **Integrate** |
| §8.1 | Two-stack local models (River 4–9B, Turtle ~30B) | `models.py` | same + `triage.py`, `proprioceptor.py` | **Partial** | `models` via integration | §8.1 | **Strangle** triage/proprio on native; **Retire** as vanilla default |
| §8.1 | Proprioception pipeline | — (retired vanilla) | `proprioceptor.py`, `pulse.py`, `discord_bot.py` | **Retire-pending** | none dedicated | §8.1 | **Strangle** behind `attunement: magic` |
| §8.4 | Checkpoint (save, keep history; eddy note is the reflection artifact) | `sessions.py` + `story_notes.py`, lifecycle bar | same + `dialogue_store.py` | **Aligned** (2026-07-14b: eddy note absorbs session-note reflection; idle-only cooldown; day file assembled mechanically) | `test_sessions` (convergence + sliding-window suites), `test_story_notes`, `test_cmd_sessions`; `shake_lifecycle.py` live green (2026-07-04, pre-convergence) | `docs/ux/sessions.md`, issue 035 notes | **Keep** — deploy: restart **both** Turtle + River when lifecycle modules change; re-run `shake_lifecycle.py` at chapter close |
| §8.4 | Release (checkpoint + clear) | `sessions.py`, `cmd_sessions.py`, `cmd_dispatch.py` | same | **Aligned** | `shake_lifecycle.py` live green (2026-07-04); act-digest skip on `!release` | same | **Keep** — same deploy rule |
| §8.4 | Checkpoint visibility (eddy-note preview + browser link on manual checkpoint/release; idle stays quiet) | `cmd_sessions.py` (`_eddy_note_reply_parts`), `artifact_presenter` surfaces, `artifact_viewer` story allowlist | same | **Aligned** (2026-07-15, issue 036) | `test_cmd_sessions` (preview/link/degrade), `test_sessions` idle guard, `test_artifact_viewer` story tier; `shake_lifecycle.py` offline 036 check | issue 036 notes, spec §8.4 + §11.5.1 | **Keep** — lifecycle bar shares `cmd_checkpoint`; live shake at chapter close |
| §8.4 | Checkpoint proposal extraction (`proposals/*-reflection.md`) | — (retired, dyad-sanctioned 2026-07-15; spec §8.4 amended) | removed from `checkpoint_session` | **Aligned** (retirement is the spec) | — | issue 035 notes, spec version 2026-07-15 | **Keep** — dedicated proposal mechanism decoupled from checkpoint is backlogged practice-side |
| CE §11 Slice 2 | Checkpoint theme propose + plain-language confirm → alive | `continuity_confirm.py`, `story_notes` proposed-themes, `cmd_sessions`, `set_last_checkpoint` | same | **Aligned** (live her-river smoke 2026-07-16) | `test_continuity_confirm`, `test_story_notes` proposed-themes; Discord smoke on `#<practitioner>-dialogue` | `design-practitioner-ready.md` Ch 2, CE design §Slice 2 | **Keep** — stale demotion / per-theme edit deferred |
| §10.2 | Fresh Eyes flow (story surfaces → illumination) | `template/flows/fresh_eyes.md`, `fresh_eyes.py`, `flow_runner.prepare_flow_reads` | same | **Aligned** (live her-river smoke 2026-07-16) | `test_fresh_eyes`; Discord `!flow fresh_eyes` on `#<practitioner>-dialogue` | `design-practitioner-ready.md` Ch 3, story-layer vision §4 | **Keep** — Quest deferred; practitioner `!flow` alias allowlisted |
| §9.2 | No auto-dissolve eddies | `sessions.py`, lifecycle | same | **Aligned** | `test_eddy_lifecycle_bar` | §9.2 | **Keep** |
| §9.6 | Discord native UI reconciliation | `discord_reconcile.py`, `runtime/adapters/lifecycle.py`, `runtime/adapters/structural.py` | same | **Aligned** (S1–S5) | `test_discord_reconcile`, `test_lifecycle_adapters` | `docs/ux/discord-native-ui.md`, design chapter | **Keep** |
| §9.4 | Attachment preprocessing | `content_fetch.py`, pipeline | same | **Aligned** | `test_attachment_pipeline` | — | **Keep** |
| §9.5 / §5.8 | **Turtle silent link-read** (conversation) | `link_read.py` | same | **Aligned** (Slice 1) | `test_link_read`, `shake_link_read.py` | chapter harness-split | **Keep** |
| §9.5 / §5.8 | **River Save to library** (persistence) | `river_eddy_seneschal.py`, `commands.py` | same | **Aligned** (Slice 2) | `test_river_eddy_seneschal`, Mini dogfood | chapter harness-split | **Keep** |
| §9.5 | Seneschal via Turtle prose → buttons | — (retired runtime path) | `legacy_seneschal.py` (tests/canary only) | **Retired** | `test_legacy_seneschal` | harness-split ch. | **Retired** — River Save offer replaces fetch seneschal |
| §9.5 | Act digest as context bridge | `commands.py` inject | same | **Partial** | `test_command_dispatch` | handoff doc | **Strangle** — replace with cleaner harness contract |
| §10.3 | Flow front matter `reads:`/`writes:` | `flow_runner.py` | same | **Aligned** | `test_flow_runner`, `shake_flow.py` | `template/flows/` | **Keep** |
| §11.1 | Vanilla practice root `state/` | `flow_runner`, `practice_io`, `practice_freshness` | same | **Aligned** | `test_flow_runner`, `test_practice_freshness` | `PRACTICE.md` | **Keep** |
| §11 / §6.2 / §15 | Family dates registry + proactive reminders | `dates.py`, `!date`/`!dates`, scheduled hook in `run_scheduled_daily_note`, Keep confirm via seneschal | same | **Implementing** (2026-08-04) | `test_dates` | `design-family-dates.md` | **Integrate** — live dogfood on family shared-river; conversational capture heuristic |
| §5 / §8 / §11.5 | Pinned home eddies (working plan ↔ home eddy ↔ river pin card) | `home_plans.py`, `home_plan_ui.py`, `cmd_pin`, sticky cool, dialogue attunement | same | **Aligned** (2026-07-17 AFK) | `test_home_plans`, `test_cmd_pin_home`, `shake_home_plans.py` | `design-pinned-home-eddies.md`, implement chapter | **Keep** — live dogfood green |
| §5 / §11.5 | Artifact crystallization (offer Keep after plan-shaped Turtle reply) | `looks_like_working_plan`, `river_eddy_seneschal.maybe_offer_home_plan_*`, `offer_home_plan` (River client), `conduct.md` Working Documents | same | **Implementing** (2026-07-18) | `TestLooksLikeWorkingPlan`, `TestMaybeOfferHomePlan`, `shake_home_plans` plan_offer | `design-turtle-artifact-crystallization.md` | **Integrate** — both-bot deploy + dogfood; Slice 6 write-tool residual |
| §12 | River act catalog + JSON enforcement | `river_handler.py` | same | **Aligned** | `test_river_handler` | §12 | **Keep** |
| §4 | Attunement `native` / `craft` / `magic` | `mage.py`, `attunement.py` | same | **Partial** | `test_craft_attunement`, `test_flow_runner` | `mage_registry.example.yaml` | **Integrate** — operator instance attunement truth |
| §4 / App A | Magic-attuned overlay | — (retired 2026-07-08/10) | removed | **Retired** | — | Appendix A | **Done** |
| §3.1 roster | Discord humans ≡ turtleOS members (join admits, leave departs; doctor reports drift) | `roster_sync.py`, `discord_bot.py` join/leave, `admin_experience.collect_doctor_findings` | `on_member_remove` was log-only; join asked for `!admin invite` | **Partial** (2026-08-30) — join/leave + doctor landed; community-at-install still gap | `test_roster_sync` (empty-human leftover control + guild-mismatch skip), `test_admin_experience.test_doctor_reports_roster_drift` | `docs/design/practice-channels.md` | **Integrate** — install pair (criterion 1) still destination; do not claim two rooms at install |
| §13+ / §15.4 | Hosted river invite + host admin UX | `river_keys`, `admin_experience`, `cmd_admin` | same | **Aligned** (2026-07-28) — invite remains for pre-create; join no longer requires it | `test_admin_experience`, `test_river_keys`, `shake_hosted_river.py` | `design-admin-experience.md` | **Keep** |
| §13+ | Update announcements (river + hosted-river; `audience: shared[:<space>]` adds shared-river, optionally narrowed to named spaces) | `announcements.py`, `scripts/post_announcement.py` | same | **Aligned** (v1 manual fanout; shared audience + named-space targeting 2026-08-05) | `test_announcements` | `design-update-announcements.md` | **Keep** — return-visit subsumed; no auto on_ready |
| §15.6 | Share eddy (practitioner + space) | `share_eddy.py` shim + 6× `share_*` modules, `!share` | same | **Partial** — decomposition released; space S2–S6 dogfood remains | `test_share_*`, `shake_share_eddy.py` | `2026-07-10-decomposition-share-eddy.md` | **Integrate** — space Slice 3 dogfood |
| §15, §7.4 | Channel primitives — a named primitive bundles Channel + Turtle + River on four dimensions; relational and thematic axes; topics are eddies that may graduate | — | `mage._get_channel_type` (4 hand-shaped type strings), `mage.get_effective_attunement` (**accepts only `native` / `craft`**, so a `family` attunement is inexpressible); River posture unmodelled | **Gap** | `test_channel_primitives_doc` (chapter contract + supersession; predicate positive controls) | `design-channel-primitives.md`; `design-topic-channels.md` (superseded in its "topic = channel" default, live for the graduated case) | **Integrate** — narrowest first: widen attunement beyond two values |
| §15.2, §15.6.4 | Member relations — `relation` (household/kin/guest, guest default) governs practitioner share targets; `admin` as orthogonal capability | `mage.py` (`relation_for_mage`, `may_reach`, `admin_discord_ids`), `share_targets.py`, `admin_experience.py` | same | **Aligned in code, ahead of spec** — §15.2 names only `type: practitioner`; amend after slice 1 dogfood (grill-first) | `test_mage_relations`, `test_share_targets` | `relations-and-membership.md` | **Integrate** — spec §15.2 amendment; slices 2–3 unbuilt |
| §20.2 | Inspect lane (shell harness, update check/plan) | `shell_harness.py`, `runtime/update.py`, `cli.py` | same | **Aligned** | `test_runtime_update`, harness tests | `development.md`, `procedures/` | **Keep** |
| §20.3 | Propose lane (practice proposals, patch plans) | `runtime/capabilities/practice.py`, `procedures/` | same — checkpoint-borne proposals retired from `sessions.py` (issue 035; dyad-sanctioned, replacement mechanism backlogged) | **Aligned** (runtime lane) | proposal tests | §11 proposals policy | **Keep** — runtime lane only |
| §20.4 | Self-heal registry | `self_heal.py`, `background.py` | same | **Aligned** | `test_self_heal` | `TURTLE_SPEC.md` §20.4 | **Keep** |
| — | Runtime task/audit slice | `runtime/*`, `cli.py` | same | **Partial** | `test_runtime_update` | `ARCHITECTURE.md` | **Integrate** — expand per development.md backlog |
| — | `commands.py` god-object | decomposed modules | `commands.py` (~918), 5× `cmd_*` | **Aligned** (Slice 5) | full test suite | chapter decomposition-commands | **Keep** — Slice 6 seneschal retire optional |
| — | `discord_bot.py` orchestration | thin handler + harness libs | `discord_bot.py` (~730) + 5× `dialogue_*` + `practice_dispatch` (Slices 1–6) | **Aligned** | `test_dialogue_*`, `test_practice_dispatch`, scattered | `docs/chapters/2026-07-10-decomposition-discord-bot.md` | **Keep** — chapter released 2026-07-10; split-bot regressions fixed post-deploy |
| — | Dialogue queue (reliability) | `dialogue_queue.py` — per-channel serial **+ coalescing** | same | **Aligned** | `test_dialogue_queue`, `test_inference_gate` | `docs/chapters/design-inference-queue.md` | **Keep** — coalescing added 2026-08-07 |
| — | Local inference gate (reliability) | one in-flight call per Ollama slot; no byte-gap deadline on a queued turn | `llm.py` `_InferenceGate`, `OLLAMA_MAX_INFLIGHT` | **Aligned** | `test_inference_gate` | `docs/chapters/design-inference-queue.md` | **Keep** — living verify owed after deploy |
| — | SSRF / URL safety | `url_validate.py` | same | **Aligned** | `test_url_validate` | — | **Keep** |
| — | Craft intake channel | `craft_intake.py` | same | **Aligned** | `test_craft_intake` | `design-craft-channel.md` | **Keep** (craft attunement) |
| — | Vortex/prism intake embed | — (retired vanilla) | `eddy_spawn.py`, `intake_server.py`, `discord_bot.py` | **Retire-pending** | none | §3.3, ARCHITECTURE | **Strangle** magic-only or **Retire** |
| — | Interoception loop → river | — (not vanilla) | `background.py`, `pulse.py` | **Retire-pending** | none | §8.1 | **Strangle** magic attunement |
| — | Triage in native eddy path | skip on native | `triage.py`, `discord_bot.py` | **Partial** | none for skip | §8.1 | **Strangle** — verify native path skips |
| — | LiveSync / CouchDB sync | git-canonical (Magic 2026-06-19) | — (pruned 2026-08-02) | **Retired** | — | `docs/live-runtime.md`, learnings fossil prune | **Keep** — do not resurrect |
| — | Transport boundary — runtime imports no platform SDK | `runtime/messages.py` value objects; `runtime/adapters/` sole translators | **The guard holds and the boundary is not load-bearing: zero production importers of the value objects, 466 lines across 5 `runtime/` modules tested and never executed** (found by outside review 2026-08-14). Repo-scale counts are generated by `scripts/quality_baseline.py` rather than restated here, because this cell said 47 while the AST count said 45 | **Partial** (defined, not adopted, 2026-08-14) | `test_transport_boundary` (AST walk + stale-exemption check + positive control); `test_runtime_adoption` (records the unwired count so it ratchets; asserts the chapter admits it) | `docs/chapters/design-transport-abstraction.md` §*What "shipped" did and did not mean* | **Integrate** — one production path from `discord.Message` → `IncomingMessage` → `OutgoingMessage`. A single command is enough and is the smallest thing that makes this real |
| — | Link offer kind + label chosen by the runtime | `runtime/link_offers.py`; `link_read.py` renders; `content_fetch.detect_platform` delegates | same | **Aligned** (2026-08-14 — closed three operator reports: YouTube mislabel, unjudgeable `host (+N more)`, Skip button) | `test_link_read` (`LinkKindAndLabelTests`, incl. media/article negative control), `shake_link_read.py` pass | chapter `design-transport-abstraction.md` §slice 2 | **Keep** — living verify owed: paste a YouTube link with a sentence in craft-turtle |
| — | Offer ledger records what was offered | `offer_ledger.py` per-root `chronicle/offers.jsonl` | same | **Aligned** (2026-08-14 — recorded nothing for 8 days: root resolved from the eddy thread id against a parent-only registry) | `test_offer_ledger` (`RootResolutionTests`, incl. end-to-end through the seneschal logger) | learnings 2026-08-14 | **Keep** — living verify owed: one real offer writes one row |
| — | Source-inspection window for craft surveys | `tos_tools.inspect_turtleos_module` — numbered window, arbitrary `start_line`, max 400 | same | **Aligned** (2026-08-14) | `test_shell_harness_survey` (positive control = the refused 280–519 read) | learnings 2026-08-14 | **Keep** — `sed` deliberately still refused |
| — | Attunement resolves through an eddy to its parent | `mage.get_effective_attunement` via `resolve_registry_channel_id` | same | **Aligned** (2026-08-14 — third instance of one shape in a day: a thread id looked up in a parent-only registry; a craft eddy answered `native`) | `test_mage_channel_resolution` (`EffectiveAttunementThroughThreadsTests`, incl. negative control) | learnings 2026-08-14 | **Keep** — 18 of 22 call sites were right only by passing `parent_id` by hand |
| — | Tools are scoped to the surface that asked for them | `tos_tools.tools_for_channel` + `_TOOL_SCOPES`; all 6 assembly sites | same | **Aligned** (2026-08-14 — `exa_search` craft-only; fails closed) | `test_tool_scoping` (AST guard on `tos_tools=TOS_TOOLS` + positive control; schema-wrapper and dispatch-coverage checks) | learnings 2026-08-14 | **Keep** — scope decides what the model is *shown*, so offer point = enforcement point |
| — | Web search available in craft | `tos_tools._exa_search` (Exa `search_and_contents`, highlights) | needs `exa-py` + `EXA_API_KEY` on the Mini | **Partial** (2026-08-14 — code shipped, key not yet installed; returns "unavailable" until then) | `test_tool_scoping` (`ExaSearchTests` — missing key, empty query, retry budget) | learnings 2026-08-14 | **Integrate** — one operator paste installs the dep and the key |
| — | Offer labels and kinds live in the runtime | `runtime/offers.py` registry; 5 views + 4 seneschal sites read it; `offer_ledger.KINDS` derives from `counted_kinds()` | 2 offers remain uncounted, each with a stated reason (`UNCOUNTED`) | **Aligned** (slice 3, 2026-08-14) | `test_offer_registry` (label/locale/dynamic-delegate, ledger agreement, no-label-in-views guard, boundary), `test_offer_ledger` (split ledger-write vs registry-lookup scans, both with positive controls) | `docs/chapters/design-transport-abstraction.md` §slice 3 | — |
| — | Every offer a practitioner sees is counted, or says why not | `link_read` + `themes_keep` record offered/accepted via `offer_ledger.record_for_channel`; `flow_intake` and `flow_rename` uncounted by decision, reason in `runtime/offers.UNCOUNTED` | Take rate is offered-vs-accepted within a report window, so an offer taken after the window reads as no answer | **Aligned** (2026-08-14) | `test_offer_ledger` (accept-instrumentation guard caught `date_keep` claiming a take rate the scan could not see; helper added to the kind scan with a positive control), `test_offer_registry` (counted set frozen at 8) | `docs/learnings.md` | — |
| — | A CLI backend reports ready only if it can run | `content_fetch._runnable` reads the shebang and checks the interpreter exists; `_cli_path` falls through to PATH when the venv copy is broken; readiness says "not runnable" | Shebang-only check — a tool that execs and then fails for its own reasons still reads as ready | **Aligned** (2026-08-14) | `test_cli_discovery` (live failure reproduced exactly, incl. X_OK-is-not-enough assertion; binary/empty/missing controls; PATH fallback both directions) | `docs/learnings.md` | — |
| — | Web search cannot hang the runtime | `_exa_search` bounds the call on a daemon thread at `EXA_TIMEOUT_SECONDS` (8s vs 1.1–1.6s measured); `exa_py` accepts no timeout of its own; attempt cap restored to 2 once the tool loop stopped blocking | Two attempts can cost this turn 16s of latency — bounded, and nobody else waits | **Aligned** (2026-08-14) | `test_tool_scoping` (hanging client returns within bound and does not wait on the abandoned worker; working client unaffected; wiring asserted by AST against any waiting call rather than a named mechanism; the old cap-of-1 test named its own precondition, so its failure said what to do) | `docs/learnings.md` | — |
| — | Quality is judged by stated measures, not by mood | `docs/quality-measures.md` (time-to-detection, recurrence of a fixed class, claim coverage, deletability); structural numbers generated by `scripts/quality_baseline.py`; `AGENTS.md` § *Who directs this codebase*; claim coverage added to the Production Standard | Two of four measures are hand-kept by necessity — dating a defect needs judgement no script has | **Aligned** (2026-08-14) | `test_quality_measures` (doc↔script column correspondence both directions, `--row` paste order, ledger completeness, transport imports counted by AST not grep so the goal number cannot be moved by editing a comment) | `docs/quality-measures.md` | — |
| — | Nothing red leaves the machine, and nothing uninstallable reaches the host | `hooks/pre-push` runs `scripts/spirit_verify.sh`; `scripts/install_hooks.sh` installs without clobbering the machine-local sanitation hook; `.github/workflows/verify.yml` reruns the same gate from pinned `requirements.txt` on 3.11 and 3.14 | Hook lives in untracked `.git/hooks`, so an uninstalled clone is ungated locally — which is why CI is not optional | **Aligned** (2026-08-14) | `test_verification_gate` (both gates name the same entrypoint; skip path must require refs read AND all deletions after the first version allowed every push on empty stdin; no other `exit 0` above the gate; requirements fully pinned; CI covers the host's Python) — verified live with a red-suite positive control, a green negative control, and a deletion-only skip | `docs/learnings.md` | — |
| — | Importing a module never constructs a Discord client, so no process holds a client it cannot log in | `state.client` / `river_state.river_client` built on first access via module `__getattr__`; internal use goes through `_ensure_client()`; `owning_process()` derived from the entry point; first wrong-process access reported to stderr with a stack | Report, not raise — whether a live River path touches Turtle's client is a question the logs answer, and crashing a practitioner's turn to find out is the wrong trade. `state.client` is not yet process-correct | **Aligned** (2026-08-14) | `test_client_laziness` (construction *count* is 0 at import and 1 after access; AST scan for module-level bindings with a planted-violation control; whole-tree subprocess probe measured 2 → 0 and refuses to pass if it imported fewer than 50 modules) | `docs/learnings.md` | — |
| — | A slow tool costs one turn, not every channel | `offload.run_blocking` runs blocking work on a daemon thread and awaits it; both tool loops in `llm.py`, `cmd_practice_io.cmd_search`, and the `!diagnose` canary board go through it | No ceiling here by decision — the bound lives in the handlers (`urlopen(timeout=180)`, Exa's 8s join), and a second ceiling would fire on a legitimately slow edit. A timed-out thread cannot be interrupted, so its result is discarded rather than cancelled | **Aligned** (2026-08-14) | `test_offload` (loop-tick measurement with a direct-call negative control proving it can fail; daemon-thread assertion because `asyncio.to_thread` joins at exit; AST scan for blocking entrypoints in any `async def`, which found the two beyond `llm.py`; every tool-layer network call must carry a timeout), `test_llm_tool_loop_offloaded` (both backends driven end to end; the Ollama path had no test before) | `docs/learnings.md` | — |
| — | The River process never builds Turtle's client to answer a question it cannot answer | `state.get_channel` returns None in the River process without constructing; first occurrence reported to stderr with a stack | Only `get_channel` is guarded — a direct `state.client` access from River still constructs, and is still reported | **Aligned** (2026-08-14) | `test_client_laziness` (construction count stays 0 in River, Turtle still resolves as a negative control, report fires once, and the `mage.py` call site is pinned to its None-tolerant form) | `docs/learnings.md` | — |
| — | A practitioner-visible feature crosses the transport seam, so the boundary is load-bearing on a real route | Incidental-link offer: `incoming_from_discord` builds an `IncomingMessage`, `runtime.link_offers.link_offer_for` returns an `OutgoingMessage`, `discord_render.send_outgoing` renders it; button `custom_id` format preserved so already-posted offers keep working | One route only — ~45 modules still handle raw `discord.Message`; `runtime/events.py`, `policy.py`, `capabilities/` still unimported by production (3 modules / 241 lines, down from 5 / 466) | **Aligned** (2026-08-14) | `test_seam_link_offer` (value objects are constructed, not merely mentioned; failed post records no offer; `custom_id` unchanged; button labelled for the link kind), `test_runtime_adoption` (ratchet inverted to assert which paths cross, plus that each one *calls* into the seam) | `docs/chapters/design-transport-abstraction.md` | Second route; `state.client` process-correctness |
| — | No offer carries a decline button | five views swept; `practitioner_message_ends_intake_wait` moves the intake click onto the silence path | same | **Aligned** (2026-08-14 — operator principle applied as a class; the guard found a fifth view a name-based sweep missed) | `test_no_decline_buttons` (AST label+custom_id guard, per-shape positive controls, accept-button negative control), `test_flow_intake_handler` (`TalkingEndsTheIntakeWaitTests`, incl. `skippable: false` control) | learnings 2026-08-14 | **Keep** — a required step is not an offer; `intake.skippable: false` deliberately unaffected |
| — | Offer take rate is reported only where accept is instrumented | `offer_ledger.ACCEPT_INSTRUMENTED`; `home_plan` accept wired | `save` / `checkpoint` / `turtle_*` accept via River command, unmatched to a pending offer | **Partial** (2026-08-14 — 4 of 6 kinds print `not recorded` instead of a false 0%) | `test_offer_ledger` | learnings 2026-08-14 | **Integrate** — match command execution against a pending offer, then delete the exemption |
| — | Acceptance catalogue matches what is actually gated | `docs/acceptance/README.md` ↔ `shake_report.SHAKE_ARTIFACTS` / `MAGE_UX_SCENARIOS` | same | **Aligned** (2026-08-14 — two features had shakes in the nightly gating *zero* scenarios for 41 commits) | `test_acceptance_catalogue` (bidirectional join, `UNVERIFIED` inventory with reasons, parse positive controls) | learnings 2026-08-14 | **Keep** — status and run commands now point at the executable copy, not a prose duplicate |

---

## Classification summary (Consolidation 2026-06-20)

### Retire (incompatible with vanilla spec — remove paths when native proven)

| Item | Rationale |
|------|-----------|
| Seneschal pre-fetch before dialogue | Superseded by harness-split architecture |
| Turtle prose → River button extraction (v1) | Wrong seam; duplicate buttons |
| Proprioceptor as vanilla default | §8.1 explicitly replaces |
| Turtle prose in River channel (native) | §5.2 No-Prose Law |
| Auto-dissolve eddies | §9.2 forbids (verify no regressions) |
| Vortex/prism as vanilla intake UX | Retired in platform law |

### Strangle (keep for `attunement: magic` until Mage migrates daily practice)

| Item | Rationale |
|------|-----------|
| Magic main-channel dialogue | Operator instance still may need until native complete |
| legacy portable surfaces (`boom`/`compass`/`bright`) | Retired 2026-07-10; native uses `state/` + `sessions/` |
| `!thread` legacy spawn | Magic overlay in turtle-talk |
| triage + proprio on magic path | Legacy stack |
| interoception / pulse river posts | Magic-attuned texture |
| Act digest context bridge | Temporary until harness contract clean |

### Integrate (compatible; needs controlled chapter)

| Item | Next chapter |
|------|----------------|
| Harness Save offer (Slice 2) | Done — Mini dogfood pass (H2/H3) |
| Acceptance harness (H1–H5) | Done — `2026-06-20-acceptance.md` |
| Split-bot lifecycle (R4–R5) | Live green 2026-07-04 (`shake_lifecycle.py --live`); restart **both** `com.turtle.discord` + `com.turtle.river` on deploy |
| TURTLE_SPEC cross-refs (Slice 3) | Done |
| `commands.py` decomposition | Complete (Slice 5) — seneschal retire optional |
| Attunement profile cleanup | After harness green |
| Chronicle jump URLs | Platform ch. |
| `docs/architecture.md` refresh | Done 2026-08-18 — renamed `docs/live-runtime.md` and scoped to one deployment |
| Magic resonance bundle freshness | Magic `@sunday` / bundle pass |
| CouchDB/LiveSync audit | Infrastructure ch. |

### Keep (aligned — maintain, index tests to §)

Rows marked **Aligned** above. Priority: link-read, river handler, flow_runner, lifecycle, bar_anchor, url_validate.

---

## Documentation sufficiency (rewrite readiness)

| Layer | Sufficient for rewrite? | Gap |
|-------|-------------------------|-----|
| **TURTLE_SPEC** | **Yes** for product law | §5.8 / §9.5 harness split aligned (Slice 3) |
| **ARCHITECTURE.md** | **Mostly** — migration table honest | 2026-08-18: line counts, the legacy flow diagram, and the duplicate spec table removed; scoped to the software |
| **docs/live-runtime.md** | **Yes** for one deployment | Renamed from `docs/architecture.md` 2026-08-18; sole home of the Mini↔Forge sync mapping |
| **docs/turtle-talk.md** | **Mostly** | Update after harness green |
| **docs/chapters/** | **Yes** for acceptance | Needs `docs/acceptance/` index (created) |
| **tests/** | **Aligned** — `./scripts/spirit_verify.sh` (count omitted on purpose; it was ~437 here against a suite of 1504) | Not spec-indexed per row; dogfood scenarios in `docs/acceptance/` |
| **library/resonance/turtle/** | **Partial** | Freshness labels; product law = turtleos repo |

**Verdict:** Top-down rewrite is viable **after** harness chapter closes and decomposition chapter splits monoliths — not before. Spec is adequate; **module boundaries + acceptance catalog** were the missing pieces (now started).

---

## Maintenance ritual

At each chapter close:

1. Update affected rows (Status, Tests, Action).
2. Run drift sweep (`docs/development.md`).
3. Run `./scripts/spirit_verify.sh` + relevant `shake_*.py`.
4. Append harvest to `docs/chapters/YYYY-MM-DD-*.md`.

**The re-run that checks the re-run:** `python3 scripts/turtleos_state.py` (magic workshop) reports how many commits have landed since this file last changed. A cadence nothing measures is the failure mode that retired the priority stack — this file does not get to be the next one.

---

*Harness + Decomposition + Acceptance dogfood complete 2026-06-20. Next: split-bot lifecycle capture chapter; doc sovereignty.*
