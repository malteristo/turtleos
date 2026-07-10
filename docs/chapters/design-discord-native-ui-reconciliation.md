# Design Chapter: Discord Native UI Reconciliation

**Opened:** 2026-06-28  
**Status:** S1–S5 implemented  
**Spec trace:** TURTLE_SPEC §5 (eddies / lifecycle), §9.2 (session law)  
**Sanctioned proposal:** Magic `desk/proposals/2026-06-28-discord-native-ui-reconciliation.md`  
**Sibling:** `design-admin-space-provisioning.md` (same adapter pattern for blessed commands)

---

## Tension

Practitioners use Discord's native context menus (Close Thread, Delete Channel, etc.). turtleOS today is command-centric: `!dissolve` runs the full lifecycle pipeline, but native "Close Thread" only sets `archived=true` in Discord — essence, chronicle, and registry cleanup are skipped.

Discord does not emit menu-click events. It emits **Gateway state changes**. Reconciliation must be event-driven, not UI-mirroring.

---

## Design intent

| Principle | Meaning |
|-----------|---------|
| **Three tiers** | Tier 1: ignore user-local prefs. Tier 2: structural registry sync. Tier 3: semantic lifecycle pipelines. |
| **Shared pipelines** | Blessed `!` commands and native UI converge on the same functions via command vs event adapters. |
| **Policy C (Close Thread)** | Registered thread + ≥2 messages → full `dissolve_eddy()`. Otherwise → light archive (registry + memory only). |
| **Idempotency** | Skip if `harvest_status == dissolved` (command path marks before archiving). |
| **Close ≠ Delete** | Delete handlers (S2) are cleanup-only; essence requires cached history or prior close. |

---

## Architecture

```
!dissolve / !admin space close ──► Command adapter ──┐
                                                      ├──► dissolve_eddy / light_archive_eddy / …
on_thread_update (archived)      ──► discord_reconcile ─┘
on_thread_delete (S2)            ──► discord_reconcile
on_guild_channel_* (S2–S3)       ──► discord_reconcile
```

**Module:** `discord_reconcile.py` — keeps `discord_bot.py` thin.

**`dissolve_eddy(..., native_close=True)`** — thread may already be archived when the user closed via Discord UI; skip early return and skip re-archive at end.

---

## S1 — Native Close Thread (implemented)

**Trigger:** `on_thread_update` where `before.archived=False` and `after.archived=True`, parent channel registered.

**Flow:**

1. If registry entry has `harvest_status == dissolved` → skip (idempotent).
2. Load history (`reload_history` or `load_thread_history` from Discord).
3. If thread in registry and message count ≥ 2 → `dissolve_eddy(..., native_close=True)`.
4. Else → `light_archive_eddy()` (mark dissolved, clear configs/history, no essence) + **river act** via `log_activity`.

**River feedback:** Native close posts a silent 🍃 embed on the parent river (via the River bot in split mode) — same path as other lifecycle acts. Light archive: `closed via Discord — eddy archived (nothing captured)`. Full dissolve: `dissolved via Discord — N insights archived`.

**Lock transition:** logged only in S1; registry flag deferred.

---

## S3 — Channel create/update (implemented)

**Create (`on_guild_channel_create`):** Unregistered text/forum channels → ops notice in dialogue with binding hints (Practice category, `*-dialogue`, `river-*`, play sandbox). No auto-register. Blessed paths (`!admin onboard`, `!admin space create`, `!admin river-key`) call `expect_channel_registry_binding()` to suppress duplicate notices.

**Update (`on_guild_channel_update`):** Registered channels → log rename (sync `discord_name` in registry), category moves, permission drift (hosted/shared heuristics aligned with `!admin audit`). Orphaned entries skipped.

---

## S4 — Adapter extraction (implemented)

**Modules:**
- `runtime/adapters/lifecycle.py` — `close_eddy(source=…)`, `close_eddy_from_archive_transition`, `open_eddy`, `reconcile_thread_delete`
- `runtime/adapters/structural.py` — `reconcile_channel_create/update/delete`, `expect_channel_registry_binding`

**`discord_reconcile.py`** — thin facade; Gateway handlers delegate to adapters.

**Entry points:**
| Source | Adapter |
|--------|---------|
| `!dissolve` / lifecycle bar | `close_eddy(source="command" \| "lifecycle_bar")` |
| Native Close Thread | `close_eddy_from_archive_transition` (policy C) |
| `!admin space close --dissolve-eddies` | `close_eddy(source="admin")` |
| Channel create/update/delete | `reconcile_channel_*` |

---

---

## S5 — Spec ripple + operator docs (implemented)

**Practitioner doc:** [docs/ux/discord-native-ui.md](../ux/discord-native-ui.md) — three tiers, policy C, Close ≠ Delete, channel operator guidance.

**Journey:** [docs/ux/journeys.md](../ux/journeys.md) — "Close eddy via Discord UI".

**Spec:** TURTLE_SPEC §9.6 — native UI reconciliation law.

**Traceability:** `docs/traceability-matrix.md` §9.6 row.

---

## Acceptance (S1–S5)

- [x] Native close on registered eddy with ≥2 messages captures essence + chronicle
- [x] Native close on empty / unregistered thread → light archive only
- [x] `!dissolve` then archive event → no double dissolve
- [x] Rename via native UI still updates registry
- [x] Blessed commands and Gateway events share adapter pipelines (S4)
- [x] Practitioner guidance: use Discord UI; turtleOS catches up (S5)
