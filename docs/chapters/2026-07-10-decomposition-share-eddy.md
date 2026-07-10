# Chapter — Decomposition: `share_eddy.py`

**Date:** 2026-07-10  
**Status:** Complete — all 6 slices landed (Forge); Mini deploy pending dyad approval  
**Deciders:** Kermit + Spirit (dyadic maintainer)  
**Builds on:** Spirit maintainability sweep (`674888e`), `commands.py` decomposition chapter

---

## Problem

`share_eddy.py` (~2,186 lines) is the largest module in turtleOS. It holds TURTLE_SPEC §15.6 practitioner share (Slice 1 complete) plus shared-eddy policy, storage, delivery, and Discord UI in one file. The traceability matrix marks it **Partial** — practitioner slice dogfood-complete; space Slice 3 deferred.

Spirit is the principal maintainer. Every edit to share touches a gravity well: registry resolution, transcript shaping, filesystem I/O, async Discord delivery, and persistent views — mixed cohesion, high regression cost despite `test_share_eddy.py` (~1,037 lines).

---

## Principles

Same as `2026-06-20-decomposition-commands.md`:

1. **No behavior change per slice** — move code; re-export from `share_eddy.py` until callers migrate.
2. **Cohesion over line count** — extract domains that share imports and spec rows.
3. **Tests travel with extraction** — move or add unit tests per slice; `./scripts/spirit_verify.sh` green after each.
4. **Traceability updates** — matrix §15.6 row advances Partial → Aligned per slice completion.
5. **Shake after delivery/UI slices** — `scripts/shake_share_eddy.py` offline; `--live` on Mini when Discord surfaces change.

---

## Slice map

| Slice | Module | Lines (approx) | Spec / concern | Risk | Status |
|-------|--------|----------------|----------------|------|--------|
| **1** | `share_targets.py` — registry targets, dataclasses | ~176 | §15.6 addressing | **Low** | ✅ complete |
| **2** | `share_transcript.py` — history filter, digest, export bundle | ~283 | §15.6 export shape | Low | ✅ complete |
| **3** | `share_storage.py` — inbox/pending/received paths + JSON I/O | ~195 | §15.6 persistence | Low | ✅ complete |
| **4** | `share_policy.py` — shared-eddy response, dissolve authority | ~369 | §15.6 + space policy | Medium | ✅ complete |
| **5** | `share_delivery.py` — deliver + materialize async paths | ~619 | §15.6 delivery | Medium | ✅ complete |
| **6** | `share_ui.py` — views, modals, `cmd_share` entry | ~653 | §15.6 UX | Medium-high | ✅ complete |

**Deferred (separate chapter):** space Slice 3a (`materialize_space_shared_eddy` full dogfood) — needs `shared-river` topology; do not expand scope inside decomposition slices.

---

## Slice 1 — `share_targets.py` ✅ complete (2026-07-10)

**Extracted:** `share_targets.py` (176 lines); `share_eddy.py` now ~2,048 lines (re-exports public surface).

**Tests:** `tests/test_share_targets.py` (149 lines) — registry target tests lifted from `test_share_eddy.py`; dissolve/notify patches updated to `share_targets.get_registry` where needed.

**Verified:** `./scripts/spirit_verify.sh` — 439 tests OK (Forge venv). Import smoke: `share_targets` + `share_eddy` re-exports.

**Deploy:** Forge-only — no Mini restart.

---

## Slice 1 — `share_targets.py` (reference — execute first)

**Extract:**

- `ShareTarget`, `SpaceShareTarget`
- `river_channel_for_mage`, `runtime_dir_for_mage`, `practice_dir_for_mage`
- `list_practitioner_targets`, `list_space_targets`
- `runtime_dir_for_space`, `shared_river_channel_for_space`
- `_sender_may_share_to_space`, `space_member_discord_ids`
- `mage_key_for_discord_id`, `mage_is_space_member`

**Leave in `share_eddy.py` (re-export):**

```python
from share_targets import (
    ShareTarget,
    SpaceShareTarget,
    river_channel_for_mage,
    list_practitioner_targets,
    list_space_targets,
    # … full public surface
)
```

**Callers today (no import changes required if re-export holds):**

- `commands.py` → `cmd_share`
- `cmd_threads.py`, `cmd_sessions.py` → dissolve authority (Slice 4 later)
- `test_share_eddy.py`, `test_admin_space.py` — may import from `share_targets` directly after slice

**Tests to add/move:** `tests/test_share_targets.py` — lift pure registry tests from `test_share_eddy.py` (list targets, river channel resolution, space membership).

**Acceptance:**

1. `./scripts/spirit_verify.sh` green
2. `python scripts/shake_share_eddy.py` offline green (import smoke)
3. No diff in share export JSON shape (Slice 1 is addressing only)
4. Matrix note: §15.6 decomposition Slice 1 complete

**Estimated blast radius:** Forge-only repo edit; no Mini deploy until a later slice touches delivery/UI.

---

---

## Slice 2 — `share_transcript.py` ✅ complete (2026-07-10)

**Extracted:** `share_transcript.py` (283 lines) — `filter_share_history`, digest/bundle builders, LLM enrich, embed builders, `label_shared_history`. `share_eddy.py` now ~1,805 lines (re-exports).

**Tests:** `tests/test_share_transcript.py` — bundle/filter/preview/enrich/label tests lifted from `test_share_eddy.py`.

**Verified:** `spirit_verify.sh` — 440 tests OK. Export bundle schema unchanged.

**Deploy:** Forge-only — no Mini restart.

---

## Slice 2 — `share_transcript.py`

**Extract:** `filter_share_history`, `_transcript_from_history`, `label_shared_history`, `build_digest`, `build_export_bundle`, `build_export_bundle_from_draft`, `enrich_export_bundle`, `share_label`, `is_placeholder_eddy_title`, embed builders that are pure (`build_received_share_embed`, `build_space_share_embed`, `build_preview_embed` if no discord client deps).

**Acceptance:** Existing `test_share_eddy.py` bundle/digest tests green; export bundle schema unchanged.

---

---

## Slice 3 — `share_storage.py` ✅ complete (2026-07-10)

**Extracted:** `share_storage.py` (~193 lines) — path helpers, inbox/pending/received JSON I/O, active river acts, `supersede_stale_share_acts`. `share_eddy.py` now ~1,652 lines (re-exports).

**Tests:** `tests/test_share_storage.py` — inbox round-trip, received config, pending draft, active acts lifted from `test_share_eddy.py`.

**Verified:** `spirit_verify.sh` green.

**Deploy:** Forge-only — no Mini restart.

---

## Slice 3 — `share_storage.py`

**Extract:** `_share_dir`, path helpers, inbox/pending/received config read/write, active share acts persistence.

**Acceptance:** Inbox round-trip tests in `test_share_eddy.py` pass without mock changes.

---

## Slice 4 — `share_policy.py` ✅ complete (2026-07-10)

**Extracted:** `share_policy.py` (369 lines) — thread cfg merge, context scaffolding, mention gate, dissolve authority, witness/skip. `share_eddy.py` now ~1,323 lines (re-exports).

**Tests:** `tests/test_share_policy.py` (16 tests); policy tests lifted from `test_share_eddy.py`. Registry patches target `share_policy.get_registry`.

**Verified:** `spirit_verify.sh` — 443 tests OK. `discord_bot.py` callers unchanged via re-export.

**Deploy:** Forge-only — no Mini restart.

---

## Slice 4 — `share_policy.py` (reference — executed 2026-07-10)

**Extract:** `SharedEddyResponseDecision`, `shared_eddy_response_decision`, mention/reply heuristics, `check_share_dissolve_authority`, `shared_eddy_context_lines`, witness turn append, `maybe_skip_shared_eddy_dialogue`.

**Callers:** `discord_bot.py` lazy imports — update to `share_policy` or keep re-export.

**Acceptance:** All `shared_eddy_response_decision` and dissolve tests green.

---

---

## Slice 5 — `share_delivery.py` ✅ complete (2026-07-10)

**Extracted:** `share_delivery.py` (619 lines) — deliver/materialize/notify/rename + `ShareContinueView` (delivery-coupled). `share_eddy.py` now ~766 lines (UI + `cmd_share` remain).

**Tests:** `tests/test_share_delivery.py` (11 tests); delivery tests lifted from `test_share_eddy.py`.

**Verified:** `spirit_verify.sh` — 444 tests OK. `discord_bot.py` notify import unchanged via re-export.

**Deploy:** Forge-only until dyad approves Mini deploy + restart both Turtle + River.

---

## Slice 6 — `share_ui.py` ✅ complete (2026-07-10)

**Extracted:** `share_ui.py` (~653 lines) — picker/select/modal views, `get_share_bot_client`, `register_persistent_share_views`, `cmd_share`. `share_eddy.py` now a thin re-export shim (~170 lines).

**Tests:** `tests/test_share_ui.py` (client smoke + re-export); `test_share_eddy.py` retired. `test_eddy_flow_library` flow-bar dismiss assertion now targets `share_ui.py`.

**Verified:** `./scripts/spirit_verify.sh` — 445 tests OK.

**Deploy:** Dyad approval → restart **both** `com.turtle.discord` and `com.turtle.river`; `shake_share_eddy.py --live`; Mage async dogfood S1.

---

## Slice 6 — `share_ui.py` ⏳ ready to execute

**Risk:** Medium-high — `cmd_share`, persistent views, all `discord.ui` classes (~600 lines).

### Extract from `share_eddy.py`

| Group | Symbols |
|-------|---------|
| **Picker / confirm** | `ShareTargetSelect`, `ShareSpaceSelect`, `ShareEditModal`, `SharePreviewView`, `ShareConfirmView`, `SharePickerView` |
| **Entry + registration** | `get_share_bot_client`, `register_persistent_share_views`, `cmd_share` |

**Leave:** Thin `share_eddy.py` re-export shim only (or retire module name after callers migrate).

### Acceptance

1. `spirit_verify.sh` green
2. `shake_share_eddy.py --live` on Mini after deploy
3. Mage async dogfood S1 scenario

---

## Slice 5 — `share_delivery.py` (reference — executed 2026-07-10)

**Extract:** `deliver_practitioner_share`, `deliver_space_share`, `materialize_received_eddy`, `materialize_space_shared_eddy`, `continue_received_share`, notify/post helpers that touch Discord API.

**Acceptance:** `shake_share_eddy.py` offline; consider `--live` on Mini after dyad approval.

---

## Slice 6 — `share_ui.py`

**Extract:** All `discord.ui` views/selects/modals, `register_persistent_share_views`, `cmd_share`.

**Acceptance:** `shake_share_eddy.py --live` on Mini; Mage async dogfood S1 scenario.

---

## Chapter-close checklist

Per `docs/development.md`:

1. `./scripts/spirit_verify.sh`
2. Relevant `shake_*.py` (share slice: `shake_share_eddy.py`)
3. Update `docs/traceability-matrix.md` §15.6 row
4. Append harvest to `docs/learnings.md`
5. If runtime Python changed: dyad approval → restart **both** Turtle + River

---

## Why not `discord_bot.py` first?

Matrix lists both god-modules. `share_eddy.py` wins because:

- **Clearer slice boundaries** — commands decomposition proved the pattern; share has natural pure-function layers at the top.
- **Heavier test harness already exists** — `test_share_eddy.py` isolates regressions.
- **`discord_bot.py` extraction** (dialogue routing) touches live dialogue path on every message — higher consequence per line moved.

After share decomposition Slice 3–4, reassess `discord_bot.py` dialogue routing extraction as the next chapter.

---

*Prepared after Spirit maintainability sweep. Execute Slice 1 on Mage `.` or explicit go.*
