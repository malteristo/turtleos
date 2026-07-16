# Eddy lifecycle bar

**Status:** Implemented (2026-06-19) · **Native attunement:** standing bar **retired** (2026-06-24) — use typed `!checkpoint` / `!release` / `!dissolve` + bottom **flow library** bar + contextual act rows (D3)  
**Principles:** [principles.md](principles.md) · **Sessions:** [sessions.md](sessions.md) · **River bar:** [river.md](river.md)

---

## Purpose

Make **eddy core lifecycle** accessible without teaching `!` syntax — the same way the **river bar** makes materialize and flow entry accessible without `!thread` / `!flows`.

| Bar | Channel | Owner | Job |
|-----|---------|-------|-----|
| **River bar** | Parent river | River bot | Materialize — `new eddy` only |
| **Lifecycle bar** | Inside eddy (thread) | River bot | Session — Checkpoint · Release · Dissolve |

Power users keep turtle-talk (`!checkpoint`, `!release`, `!dissolve`). Buttons call the **same handlers** as commands.

**Inventory cross-ref:** [docs/turtle-talk.md](../turtle-talk.md) — eddy core surface.

---

## Design law

1. **River owns structural UI** — lifecycle bar is an act surface, not Turtle dialogue.
2. **Timeline, not pins** — bar stays the **last message** in the thread (same bottom-anchor pattern as the river bar).
3. **No chrome on empty eddies** — bar appears only after the eddy is in use (see **When it appears**).
4. **Small curated set** — lifecycle verbs only; not a command catalog.
5. **Dissolve is destructive** — confirm sub-row with explicit Cancel (see **Dissolve confirm**).
6. **Seneschal act rows use the same River path** — Turtle suggests moment-specific acts in prose; River posts a temporary button row after the reply (native: excludes checkpoint / release / dissolve — lifecycle bar owns those). Lifecycle bar content stays constant; one re-anchor per turn keeps it last.

---

## When it appears

**Rule:** First **practitioner** activity in a live eddy.

| Eddy path | Bar posts after |
|-----------|-----------------|
| **Blank eddy** (bar `new eddy`) | First practitioner message in thread |
| **Flow eddy, no intake** (e.g. Shelter) | First practitioner message after orientation |
| **Flow eddy with intake** (e.g. Navigator) | First practitioner message **after** intake completes (`Begin` path) — not during Prepare/modal/orientation-only phase |
| **Legacy / Magic spawn** | First practitioner message when thread is in native dialogue mode |

**Not before:**

- Empty thread at materialize
- Intake-only phase (Prepare, Skip-waiting, pre-Begin)
- Operator-only system lines (`river added you`, orientation embed alone)

**Rationale:** An unused eddy does not need checkpoint, release, or dissolve. Matches [eddy-entry.md](eddy-entry.md) minimal entry and [rejected.md](rejected.md) (no Control Panel on open).

---

## Normal bar layout

Silent message (zero-width space), three buttons:

```
[ 💾 Checkpoint ] [ 🌙 Release ] [ 🍃 Dissolve ]
```

| Button | Maps to | Immediate? | Effect (summary) |
|--------|---------|------------|------------------|
| **Checkpoint** | `!checkpoint` | Yes | Save resonance; keep history |
| **Release** | `!release` | Yes | Checkpoint + clear history; thread stays open |
| **Dissolve** | `!dissolve` | No — opens confirm | Archive thread + chronicle |

**Native Close Thread:** Discord's thread menu **Close Thread** also archives — turtleOS runs policy C on the archive transition (same dissolve/light-archive semantics). See [discord-native-ui.md](discord-native-ui.md).

Button labels are practitioner language, not command names. Help text may still document `!` aliases.

---

## Bottom anchor (keep bar last)

After **any timeline activity** in the thread (practitioner, Spirit, Turtle command output, ops embeds, dialogue replies):

1. If lifecycle bar message is already last → refresh view if needed (re-register persistent custom_ids).
2. Else → delete stale bar message (if tracked) → post fresh bar at bottom.

River parent channels use reconciled-floor debounce ([river.md](river.md)); eddy lifecycle bars still ensure-at-bottom when active. Unified entry point: `bar_anchor.ensure_channel_bars(channel)`.

**State file:** `thread-state/eddy/lifecycle_bar.json` — maps `thread_id → bar_message_id`.

**Who triggers ensure:** Turtle/discord harness after in-thread messages in native eddies; River bot posts/edits the bar (split-bot). Single-bot fallback: same pattern, one client.

---

## Dissolve confirm (Option A — expand in place)

First click on **Dissolve** does **not** archive. It **replaces** the button row:

```
[ Archive this eddy? ] [ Cancel ]
     (danger/red)      (secondary)
```

| Action | Result |
|--------|--------|
| **Archive this eddy?** | Run `dissolve_eddy` (same as `!dissolve`); clear bar state; thread archives |
| **Cancel** | Restore normal three-button bar |
| **Timeout (15s)** | Auto-restore normal bar if neither confirm button pressed |

**Rejected for vanilla v1:**

- Single mutating button (`Dissolve` → `Really?`) with no Cancel — abort is only implicit via timeout.
- Modal “type DISSOLVE” — too heavy for ordinary practitioners.
- Ephemeral-only confirm — hides structural act from the shared timeline (acceptable for operator tools, not default here).

**Release vs Dissolve copy:** Confirm button says **Archive this eddy?** — not “Dissolve again” — to distinguish from Release (“done for now, thread stays”).

---

## Relationship to other affordances

| Affordance | Scope | Relationship |
|------------|-------|--------------|
| **River bar** | Parent channel only | Opens eddies; no lifecycle buttons |
| **Lifecycle bar** | In-thread | Session end; no `flow menu` / `new eddy` |
| **River seneschal act row** | After Turtle dialogue (native + legacy) | Moment-specific extensions; same handlers as lifecycle bar; native excludes lifecycle trio |
| **`!` commands** | Eddy (River harness when split-bot) | Power-user instant path; same handlers |
| **Magic `ThreadConfigView` / `!panel`** | Magic-attuned | Model/eddy-type chrome — **not** on vanilla lifecycle bar |

---

## Split-bot identity

| Event | Bot |
|-------|-----|
| Lifecycle bar post/edit/delete | **River** |
| Bar button interactions | **River** (delegates to shared command handlers) |
| Seneschal act suggestion rows | **River** (posted after Turtle prose; not Turtle-owned buttons) |
| Turtle dialogue | **Turtle** (prose + backtick suggestions only) |

Practitioners should read lifecycle controls as **River structure**, Turtle as **conversation**.

---

## Failure and edge cases

| Case | Behavior |
|------|----------|
| Dissolve on thread with &lt;2 messages | Same as `!dissolve` — still archives; essence capture may be minimal |
| Release with thin history | Same as `!release` — gentle “not enough to release” if applicable |
| Thread already archived | Bar interactions no-op or “thread closed” ephemeral |
| Bar message deleted manually | Next ensure pass reposts bar |
| Intake eddy, user never reaches Begin | No lifecycle bar until dialogue is live |

Errors: embed or ephemeral act — not Turtle conversational apology ([principles.md](principles.md)).

---

## Implementation

Shipped through `d3d4516` (`eddy_lifecycle_bar.py`, `bar_anchor.py`, seneschal act rows).

| Piece | Location |
|-------|----------|
| Views | `eddy_lifecycle_bar.py` — `EddyLifecycleBarView`, `EddyDissolveConfirmView` |
| Ensure/repost | `ensure_eddy_lifecycle_bar_at_bottom(thread, client)` |
| Unified hook | `bar_anchor.ensure_channel_bars(channel)` — river + lifecycle |
| Appear hook | `touch_eddy_lifecycle_bar` after qualifying practitioner activity — wired from `discord_bot.py` / `river_bot.py` |
| Handlers | Reuse `cmd_checkpoint`, `cmd_release`, `cmd_dissolve` via interaction adapter (`from_lifecycle_bar`, `discord_client` on adapter message) |
| State | `thread-state/eddy/lifecycle_bar.json` |
| Tests | `tests/test_eddy_lifecycle_bar.py` |
| Shakedown | `scripts/shake_eddy_bar.py` (lifecycle covered in dogfood); dedicated `shake_eddy_lifecycle_bar.py` deferred |

**Spec:** TURTLE_SPEC §8.4 — accessible lifecycle path alongside turtle-talk.

---

## Review checklist additions

When merging lifecycle bar work:

1. Bar does **not** appear on empty materialized eddy.
2. Navigator (etc.) bar waits until post-intake dialogue.
3. Dissolve confirm has **Cancel** + timeout revert.
4. River bot posts bar; Turtle does not.
5. After eddy activity, lifecycle bar is **last message** in thread.
6. Handlers match `!checkpoint` / `!release` / `!dissolve` — no duplicate logic.

See [review-checklist.md](review-checklist.md).

---

## Evolution log

| Date | Change |
|------|--------|
| 2026-06-19 | Pattern specified — appear on first practitioner activity; dissolve confirm Option A |
| 2026-06-20 | Shipped — `eddy_lifecycle_bar.py`; dogfood fixes through `21d1ea2` (persistent confirm view, single dissolve handler) |
