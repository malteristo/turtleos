# Chapter — Decomposition: `share_eddy.py`

**Date:** 2026-07-10  
**Status:** In progress — Slice 3 **complete**; Slice 4 next  
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
| **4** | `share_policy.py` — shared-eddy response, dissolve authority | ~200 | §15.6 + space policy | Medium | ⏳ next |
| **5** | `share_delivery.py` — deliver + materialize async paths | ~400 | §15.6 delivery | Medium | pending |
| **6** | `share_ui.py` — views, modals, `cmd_share` entry | ~500 | §15.6 UX | Medium-high | pending |

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

## Slice 4 — `share_policy.py` ⏳ ready to execute

**Risk:** Medium — touches live dialogue path via `discord_bot.py` lazy imports (`maybe_skip_shared_eddy_dialogue`, context line builders). Re-export from `share_eddy` avoids caller churn.

### Extract (~365 lines from `share_eddy.py`)

| Group | Symbols |
|-------|---------|
| **Thread cfg merge** | `resolve_eddy_thread_cfg`, `_received_eddy_notify_config` |
| **Prompt scaffolding** | `received_eddy_context_lines`, `shared_eddy_context_lines`, `shared_eddy_source_for_thread` |
| **Space membership (policy)** | `sharer_is_space_member`, `space_member_addresses` |
| **Mention gate** | `SharedEddyResponseDecision`, `_message_guild`, `_turtle_user_id_for_message`, `message_mentions_turtle`, `message_mentions_other_humans`, `message_is_reply_to_turtle`, `content_explicitly_invokes_turtle`, `content_looks_like_peer_thanks`, `_EXPLICIT_TURTLE_INVOKE_RE`, `_PEER_THANKS_RE`, `shared_eddy_response_decision` |
| **Dissolve authority** | `ShareDissolveDecision`, `share_dissolve_denial_message`, `check_share_dissolve_authority` |
| **Witness / skip** | `append_shared_eddy_witness_turn`, `maybe_skip_shared_eddy_dialogue` |

**Leave in `share_eddy.py` (later slices):**

- `post_reshare_transparency_act` → Slice 5 (delivery)
- `should_notify_*`, `maybe_notify_*`, `notify_sharer_*` → Slice 5
- All `discord.ui` views + `cmd_share` → Slice 6

### Dependencies

```python
# share_policy.py imports
from share_storage import load_received_thread_config
from share_targets import mage_is_space_member, mage_key_for_discord_id
from mage import get_registry, set_practice_context_for_channel, get_runtime_dir
```

`_received_eddy_notify_config` moves with policy — it merges `thread_configs` with `load_received_thread_config` (split River/Turtle bots).

### Callers (re-export sufficient)

| Caller | Imports today |
|--------|----------------|
| `discord_bot.py` | `resolve_eddy_thread_cfg`, `received_eddy_context_lines`, `shared_eddy_context_lines`, `maybe_skip_shared_eddy_dialogue` |
| `cmd_threads.py`, `cmd_sessions.py` | `check_share_dissolve_authority` |
| `test_cmd_sessions.py` | patches `share_eddy.check_share_dissolve_authority` — keep working via re-export |
| `scripts/shake_share_eddy.py` | `shared_eddy_response_decision`, `check_share_dissolve_authority` |

### Tests to add/move → `tests/test_share_policy.py`

Lift from `test_share_eddy.py`:

- `ShareReceivedContextTests`
- `ShareSharedEddyContextTests` (patch `share_eddy.get_registry` → `share_policy.get_registry` for `sharer_is_space_member` / `space_member_addresses`)
- `ShareEddyMentionGateTests` (patch `share_eddy._turtle_user_id_for_message` → `share_policy._turtle_user_id_for_message`)
- `ShareDissolveAuthorityTests` (dual-patch `share_eddy.get_registry` + `share_targets.get_registry` unchanged)
- Re-export smoke test

**Keep in `test_share_eddy.py`:** `ShareNotifyPolicyTests`, `ShareNotifyTests` (notify flow → Slice 5).

### Acceptance

1. `./scripts/spirit_verify.sh` green
2. `python scripts/shake_share_eddy.py` offline import smoke
3. No behavior change in mention-gate or dissolve paths
4. Matrix §15.6 note: decomposition Slice 4 complete

**Deploy:** Forge-only repo edit; no Mini restart until delivery/UI slices land.

---

## Slice 4 — `share_policy.py` (reference)

**Extract:** `SharedEddyResponseDecision`, `shared_eddy_response_decision`, mention/reply heuristics, `check_share_dissolve_authority`, `shared_eddy_context_lines`, witness turn append, `maybe_skip_shared_eddy_dialogue`.

**Callers:** `discord_bot.py` lazy imports — update to `share_policy` or keep re-export.

**Acceptance:** All `shared_eddy_response_decision` and dissolve tests green.

---

## Slice 5 — `share_delivery.py`

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
