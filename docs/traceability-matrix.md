# turtleOS Traceability Matrix (v0)

**Date:** 2026-06-20  
**Status:** Living artifact — update at every chapter close  
**Purpose:** Spec § → implementation → verification → docs. Answers “can we rewrite from law?” by naming gaps explicitly.

**How to use:** Each row is one load-bearing behavior. Status drives the next chapter. **Action** column: `Keep` | `Integrate` | `Strangle` | `Retire`.

**Verification tiers:** `unit` = `python -m unittest discover -s tests`; `shake` = `scripts/shake_*.py`; `dogfood` = Discord acceptance (human).

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
| §5.4 | Blank/flow eddy materialize | `eddy_spawn.py`, `river_handler.py` | same | **Partial** | `test_eddy_rename`, `shake_spawn_eddy.py` | chapter `2026-06-18-eddy-bar.md` | **Integrate** — first-message + split-bot edge cases |
| §5.5 | River owns `!` on parent channel | `commands.py`, `river_bot.py` | same | **Aligned** (native) | `test_command_dispatch`, `test_eddy_lifecycle_bar` | `turtle-talk.md` | **Keep** |
| §5.8 | River vs Turtle Discord identity | `river_bot.py`, `discord_bot.py` | same | **Partial** | `test_eddy_rename` (split-bot); dogfood acceptance ch. | chapter `2026-06-16-river-bot-split.md` | **Integrate** — duplicate lifecycle bars; Turtle posts bar via unlogged `river_client` |
| §6.2–6.3 | Chronicle surface + deep.jsonl | `chronicle` modules | partial in `thread_registry`, handlers | **Partial** | sparse | `TURTLE_SPEC` §6 | **Integrate** — jump URLs incomplete |
| §6.4 | Sediment cross-eddy memory | deferred | — | **Gap** (deferred) | — | §6.4 | **Defer** — backlog, not v1 |
| §7.1–7.2 | Turtle dialogue eddy-only | `discord_bot.handle_dialogue` | same + legacy river path | **Partial** | `test_native_prompts` | `native-harness.md` | **Strangle** magic main-channel dialogue |
| §7.4–7.5 | Turtle model + native character | `prompts.py`, `models.py` | same | **Aligned** (native eddy) | `test_native_prompts`, `test_flow_runner` | `template/character/` | **Keep** |
| §7.7 | Presence indicators | `eddy_lifecycle`, spawn | mixed legacy + native | **Partial** | `test_flow_runner` presence | `docs/ux/` | **Integrate** |
| §8.1 | Two-stack local models (River 4–9B, Turtle ~30B) | `models.py` | same + `triage.py`, `proprioceptor.py` | **Partial** | `models` via integration | §8.1 | **Strangle** triage/proprio on native; **Retire** as vanilla default |
| §8.1 | Proprioception pipeline | — (retired vanilla) | `proprioceptor.py`, `pulse.py`, `discord_bot.py` | **Retire-pending** | none dedicated | §8.1 | **Strangle** behind `attunement: magic` |
| §8.4 | Checkpoint (save, keep history) | `sessions.py`, lifecycle bar | same + `dialogue_store.py` | **Partial** | `shake_lifecycle.py` live green (2026-07-04) | `docs/ux/eddy-lifecycle-bar.md` | **Integrate** — live dogfood pass; matrix/doc refresh |
| §8.4 | Release (checkpoint + clear) | `sessions.py`, `cmd_sessions.py`, `cmd_dispatch.py` | same | **Partial** | `shake_lifecycle.py` live green; act-digest skip on release | same | **Integrate** — live pass; deploy must restart **both** Turtle + River |
| §9.2 | No auto-dissolve eddies | `sessions.py`, lifecycle | same | **Aligned** | `test_eddy_lifecycle_bar` | §9.2 | **Keep** |
| §9.6 | Discord native UI reconciliation | `discord_reconcile.py`, `runtime/adapters/lifecycle.py`, `runtime/adapters/structural.py` | same | **Aligned** (S1–S5) | `test_discord_reconcile`, `test_lifecycle_adapters` | `docs/ux/discord-native-ui.md`, design chapter | **Keep** |
| §9.4 | Attachment preprocessing | `content_fetch.py`, pipeline | same | **Aligned** | `test_attachment_pipeline` | — | **Keep** |
| §9.5 / §5.8 | **Turtle silent link-read** (conversation) | `link_read.py` | same | **Aligned** (Slice 1) | `test_link_read`, `shake_link_read.py` | chapter harness-split | **Keep** |
| §9.5 / §5.8 | **River Save to library** (persistence) | `river_eddy_seneschal.py`, `commands.py` | same | **Aligned** (Slice 2) | `test_river_eddy_seneschal`, Mini dogfood | chapter harness-split | **Keep** |
| §9.5 | Seneschal via Turtle prose → buttons | — (retired runtime path) | `legacy_seneschal.py` (tests/canary only) | **Retired** | `test_legacy_seneschal` | harness-split ch. | **Retired** — River Save offer replaces fetch seneschal |
| §9.5 | Act digest as context bridge | `commands.py` inject | same | **Partial** | `test_command_dispatch` | handoff doc | **Strangle** — replace with cleaner harness contract |
| §10.3 | Flow front matter `reads:`/`writes:` | `flow_runner.py` | same | **Aligned** | `test_flow_runner`, `shake_flow.py` | `template/flows/` | **Keep** |
| §11.1 | Vanilla practice root `state/` | `flow_runner`, `practice_io`, `practice_freshness` | same | **Aligned** | `test_flow_runner`, `test_practice_freshness` | `PRACTICE.md` | **Keep** |
| §12 | River act catalog + JSON enforcement | `river_handler.py` | same | **Aligned** | `test_river_handler` | §12 | **Keep** |
| §4 | Attunement `native` / `craft` / `magic` | `mage.py`, `attunement.py` | same | **Partial** | `test_craft_attunement`, `test_flow_runner` | `mage_registry.example.yaml` | **Integrate** — operator instance attunement truth |
| §4 / App A | Magic-attuned overlay | — (retired 2026-07-08/10) | removed | **Retired** | — | Appendix A | **Done** |
| §13+ | Hosted river onboarding | `river_keys`, spawn | same | **Aligned** | `test_hosted_river_onboarding`, `shake_hosted_river.py` | `design-hosted-river.md` | **Keep** |
| §15.6 | Share eddy (practitioner + space) | `share_eddy.py`, `!share` | same | **Partial** — Slice 1 **complete** (practitioner); space deferred | `test_share_eddy`, `shake_share_eddy.py` | `design-share-eddy.md`, `2026-06-25-share-eddy-slice1-dogfood.md` | **Integrate** — Slice 3 needs `shared-river` |
| §20.2 | Inspect lane (shell harness, update check/plan) | `shell_harness.py`, `runtime/update.py`, `cli.py` | same | **Aligned** | `test_runtime_update`, harness tests | `development.md`, `procedures/` | **Keep** |
| §20.3 | Propose lane (practice proposals, patch plans) | `runtime/capabilities/practice.py`, `sessions.py`, `procedures/` | same | **Aligned** | session/proposal tests | §11 proposals policy | **Keep** |
| §20.4 | Self-heal registry | `self_heal.py`, `background.py` | same | **Aligned** | `test_self_heal` | `TURTLE_SPEC.md` §20.4 | **Keep** |
| — | Runtime task/audit slice | `runtime/*`, `cli.py` | same | **Partial** | `test_runtime_update` | `ARCHITECTURE.md` | **Integrate** — expand per development.md backlog |
| — | `commands.py` god-object | decomposed modules | `commands.py` (~918), 5× `cmd_*` | **Aligned** (Slice 5) | full test suite | chapter decomposition-commands | **Keep** — Slice 6 seneschal retire optional |
| — | `discord_bot.py` orchestration | thin handler + harness libs | `discord_bot.py` (~1890 lines) | **Partial** | scattered | `ARCHITECTURE.md` | **Integrate** — follow harness boundaries |
| — | Dialogue queue (reliability) | `dialogue_queue.py` | same | **Aligned** | `test_dialogue_queue` | handoff doc | **Keep** |
| — | SSRF / URL safety | `url_validate.py` | same | **Aligned** | `test_url_validate` | — | **Keep** |
| — | Craft intake channel | `craft_intake.py` | same | **Aligned** | `test_craft_intake` | `design-craft-channel.md` | **Keep** (craft attunement) |
| — | Vortex/prism intake embed | — (retired vanilla) | `eddy_spawn.py`, `intake_server.py`, `discord_bot.py` | **Retire-pending** | none | §3.3, ARCHITECTURE | **Strangle** magic-only or **Retire** |
| — | Interoception loop → river | — (not vanilla) | `background.py`, `pulse.py` | **Retire-pending** | none | §8.1 | **Strangle** magic attunement |
| — | Triage in native eddy path | skip on native | `triage.py`, `discord_bot.py` | **Partial** | none for skip | §8.1 | **Strangle** — verify native path skips |
| — | LiveSync / CouchDB sync | git-canonical (Magic 2026-06-19) | `canary.py`, launchd | **Legacy infra** | canary | `docs/architecture.md` (stale) | **Integrate** — audit strangle vs retire |

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
| `docs/architecture.md` refresh | This consolidation + Sunday |
| Magic resonance bundle freshness | Magic `@sunday` / bundle pass |
| CouchDB/LiveSync audit | Infrastructure ch. |

### Keep (aligned — maintain, index tests to §)

Rows marked **Aligned** above. Priority: link-read, river handler, flow_runner, lifecycle, bar_anchor, url_validate.

---

## Documentation sufficiency (rewrite readiness)

| Layer | Sufficient for rewrite? | Gap |
|-------|-------------------------|-----|
| **TURTLE_SPEC** | **Yes** for product law | §5.8 / §9.5 harness split aligned (Slice 3) |
| **ARCHITECTURE.md** | **Mostly** — migration table honest | Module line counts drift; needs matrix sync |
| **docs/architecture.md** | **No** — stale (2026-03-21) | Replace with pointer to ARCHITECTURE + matrix |
| **docs/turtle-talk.md** | **Mostly** | Update after harness green |
| **docs/chapters/** | **Yes** for acceptance | Needs `docs/acceptance/` index (created) |
| **tests/** | **Partial** — 147 unit tests | Not spec-indexed; dogfood scenarios separate |
| **library/resonance/turtle/** | **Partial** | Freshness labels; product law = turtleos repo |

**Verdict:** Top-down rewrite is viable **after** harness chapter closes and decomposition chapter splits monoliths — not before. Spec is adequate; **module boundaries + acceptance catalog** were the missing pieces (now started).

---

## Maintenance ritual

At each chapter close:

1. Update affected rows (Status, Tests, Action).
2. Run drift sweep (`docs/development.md`).
3. Run `python -m unittest discover -s tests` + relevant `shake_*.py`.
4. Append harvest to `docs/chapters/YYYY-MM-DD-*.md`.

---

*Harness + Decomposition + Acceptance dogfood complete 2026-06-20. Next: split-bot lifecycle capture chapter; doc sovereignty.*
