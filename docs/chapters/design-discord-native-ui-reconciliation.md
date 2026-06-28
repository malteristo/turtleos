# Design Chapter: Discord Native UI Reconciliation

**Opened:** 2026-06-28  
**Status:** S1 implemented — archive transition  
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
4. Else → `light_archive_eddy()` (mark dissolved, clear configs/history, no essence).

**Lock transition:** logged only in S1; registry flag deferred.

---

## Slices remaining

| Slice | Scope |
|-------|-------|
| S2 | `on_thread_delete`, `on_guild_channel_delete` |
| S3 | `on_guild_channel_create/update` — unregistered channel notices |
| S4 | Extract shared adapters; dedupe command/event entry points |
| S5 | Spec ripple + `docs/ux/journeys.md` |

---

## Acceptance (S1)

- [ ] Native close on registered eddy with ≥2 messages captures essence + chronicle
- [ ] Native close on empty / unregistered thread → light archive only
- [ ] `!dissolve` then archive event → no double dissolve
- [ ] Rename via native UI still updates registry
