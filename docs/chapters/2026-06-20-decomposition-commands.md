# Chapter — Decomposition: `commands.py`

**Date:** 2026-06-20  
**Status:** Complete — all slices including seneschal retire  
**Deciders:** Kermit + Spirit (Forge)  
**Builds on:** Consolidation traceability matrix, Harness chapter

---

## Problem

`commands.py` (~2030 lines) is the first gravity well in the traceability matrix: dispatch, session lifecycle, practice browse, link cache, views, and legacy magic handlers in one module. Harness split clarified boundaries; decomposition makes them enforceable without a big-bang rewrite.

---

## Principles

1. **No behavior change per slice** — move code, re-export from `commands.py` until callers migrate.
2. **Cohesion over line count** — extract domains that share imports and spec rows.
3. **Tests travel with extraction** — each slice adds or moves unit tests.
4. **Traceability updates** — matrix row moves from Gap → Partial → Aligned per slice.

---

## Slice map

| Slice | Module | Lines (approx) | Spec rows | Status |
|-------|--------|----------------|-----------|--------|
| **0** | `eddy_spawn.py` — `thread.remove_user` fix | 1 | — | ✅ Mini dogfood blocker |
| **1** | `cmd_link_resonance.py` — `!fetch`, cache, digest | ~180 | §9.5 distill | ✅ |
| **2** | `cmd_dispatch.py` — registries, `try_direct_command`, act digest | ~140 | §5.5 | ✅ |
| **3** | `cmd_sessions.py` — checkpoint / release / dissolve | ~125 | §8.4 | ✅ |
| **4** | `cmd_practice_io.py` — read / ls / search | ~110 | §5.5 | ✅ |
| **5** | `cmd_threads.py` — thread, rename, eddy-check, views | ~470 | §9.2 | ✅ |
| **6** | Retire seneschal prose-parse runtime path | — | §9.5 retire | ✅ |

---

## Slice 0 — `thread.remove_user` ✅

**Finding:** shake-spawn first message crashed River in `river_add_turtle_to_eddy` — `Thread` has no `.remove` in discord.py 2.7.

**Fix:** `await thread.remove_user(discord.Object(id=turtle_id))`.

**Acceptance:** shake-spawn first message completes `handle_eddy_first_message` without AttributeError.

---

## Slice 1 — Link resonance ✅

**Extracted to `cmd_link_resonance.py`:**

- `get_cached_resonance` / `cache_resonance`
- `fetch_act_digest`, `cmd_fetch`
- Back-compat aliases `_get_cached_resonance`, `_cache_resonance`

**Callers updated:**

- `river_eddy_seneschal.py` → imports cache probe directly (harness boundary)
- `commands.py` → re-exports for legacy imports

**Tests:** `tests/test_cmd_link_resonance.py` + existing `test_command_dispatch` / `test_river_eddy_seneschal`.

---

## Slice 2 — Dispatch ✅

**Extracted to `cmd_dispatch.py`:**

- `COMMAND_ACT_FALLBACK`, practitioner/contextual/seneschal registries
- `inject_act_digest`, `try_direct_command`, `dispatch_direct_command`
- `send_with_actions` (seneschal → River act row bridge)

**`DIRECT_COMMANDS` registry** remains in `commands.py` until handler modules extract (Slice 3+); `try_direct_command` lazy-imports it to avoid circular init.

**Callers:** `commands.py` re-exports; `river_bot.py` unchanged.

**Tests:** `tests/test_cmd_dispatch.py`; `test_command_dispatch` patch target updated.

---

## Slice 3 — Session lifecycle ✅

**Extracted to `cmd_sessions.py`:**

- `cmd_checkpoint`, `cmd_release`, `cmd_dissolve`
- Delegates to `sessions.checkpoint_session` / `dissolve_eddy` (logic stays in `sessions.py`)

**Bugfix:** restored truncated `cmd_ls` reply (missing `message.reply` after Slice 1 edit).

**Tests:** `tests/test_cmd_sessions.py` (5 cases).

---

## Slice 4 — Practice browse ✅

**Extracted to `cmd_practice_io.py`:**

- `cmd_read`, `cmd_ls`, `cmd_search`
- Practice-root file access via `practice_io` + `tos_tools.search_practice_files`

**Tests:** `tests/test_cmd_practice_io.py` (5 cases).

---

## Slice 5 — Threads + views ✅

**Extracted to `cmd_threads.py`:**

- `cmd_thread`, `cmd_thread_type`, `cmd_rename`, `cmd_threads`, `cmd_new`
- `cmd_eddy_check`, `eddy_dissolution_check`, `EddyDissolutionView` (Magic legacy)
- `ThreadConfigView`, `ControlPanelView`, `ThreadTopicModal`, `build_config_line`
- Panel buttons lazy-import `cmd_status` / `cmd_diagnose` from `commands`, `cmd_release` from `cmd_sessions`

**`commands.py`:** 1593 → **918 lines** (−55% from original 2030).

**Tests:** `tests/test_cmd_threads.py` (4 cases).

---

## Slice 6 — Seneschal prose retire ✅

**Runtime change:** removed Turtle prose → River button extraction from `discord_bot.handle_dialogue` (native **and** legacy magic eddies).

**Platform acts on native eddies:** lifecycle bar, typed `!`, post-Turtle **Save to library** (`river_eddy_seneschal`) — not prose parsing.

**Preserved in `legacy_seneschal.py`:** extraction + filter helpers for canary smoke and unit tests only (`attunement: magic` strangle archive).

**Tests:** `tests/test_legacy_seneschal.py` (replaces `test_seneschal_actions.py`).

---

## Acceptance (full chapter)

1. `commands.py` under ~1200 lines (views + remaining commands only)
2. Each extracted module has dedicated tests
3. `python -m unittest discover -s tests` green
4. Matrix row `commands.py god-object` → **Aligned**
5. No regression in River `!` dispatch or Save offer cache probe

---

## Non-goals

- `discord_bot.py` decomposition (separate chapter)
- Seneschal prose → button retirement (Slice 6, needs dispatch slice first)
- Generated command reference (development.md backlog)

---

*Decomposition follows harness template: slice → test → traceability → next slice.*
