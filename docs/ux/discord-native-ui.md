# Discord native UI — use Discord; turtleOS catches up

**Status:** Shipped (S1–S5, 2026-06-28)  
**Spec:** TURTLE_SPEC §9.6  
**Design:** `docs/chapters/design-discord-native-ui-reconciliation.md`  
**Code:** `discord_reconcile.py` → `runtime/adapters/lifecycle.py`, `runtime/adapters/structural.py`

---

## Principle

Practitioners should use **Discord's own controls** — context menus, channel settings, thread Close — not memorize turtle-talk for everyday actions. turtleOS does not mirror Discord admin UI in custom components. It **subscribes to Gateway state changes** and runs the same pipelines as blessed `!` commands where practice semantics matter.

**Mental model:** Discord owns the surface; turtleOS reconciles practice state.

---

## Three tiers

| Tier | Examples | turtleOS |
|------|----------|------------|
| **1 — User-local** | Mute, notifications, mark read, copy link | **Ignore** — no practice state |
| **2 — Structural** | Create/rename/delete channel, permission edits | Registry sync, ops notices, orphan flags |
| **3 — Semantic lifecycle** | Close Thread, Delete Thread, `!dissolve` | Shared dissolve/archive pipelines |

Tier 1 stays entirely in Discord. Tiers 2–3 converge on the same adapter functions whether the trigger was a native UI action or a command.

---

## Close Thread (eddy)

**Discord:** Thread menu → **Close Thread** (archives the thread).

**turtleOS:** `on_thread_update` detects `archived: false → true` and runs **policy C**:

| Condition | Behavior |
|-----------|----------|
| Thread in `thread_registry` **and** ≥2 messages | Full **`dissolve_eddy()`** — essence → boom, file archive, chronicle, registry mark |
| Otherwise | **Light archive** — registry + in-memory cleanup only; river act notes nothing substantive captured |

**Equivalent paths:** `!dissolve`, lifecycle bar **Dissolve** (after confirm), native **Close Thread** (policy C applies only to native close).

**River feedback:** Parent river gets a silent lifecycle act — e.g. `dissolved via Discord — N entries captured` or `closed via Discord — eddy archived (nothing captured)`.

**Idempotency:** If the eddy was already dissolved (e.g. `!dissolve` ran first), the archive event is skipped — no double capture.

**Prefer Close over Delete:** Close runs the lifecycle pipeline when substantive. **Delete Thread** removes Discord state immediately; essence capture depends on cached history (see below).

---

## Delete Thread

**Discord:** Thread menu → **Delete Thread**.

**turtleOS:** Registry entry removed, in-memory harness state cleared, ops notice on parent river. Essence/chronicle only if history was already loaded or a prior close captured it.

**Guidance:** For practice eddies you want in boom/chronicle, **Close Thread** (or `!dissolve`) before delete, or use dissolve paths explicitly.

---

## Rename / lock thread

| Native action | turtleOS |
|---------------|----------|
| **Edit Thread** → rename | `thread_registry` name synced |
| **Lock Thread** | Logged; registry lock flag deferred in v1 |

---

## Channels (operators)

### Create channel

Unregistered text/forum channels under Practice (or matching naming heuristics) → **ops notice** in dialogue with binding hints (`!admin space create`, `!admin onboard`, `!admin river-key`). **No auto-register.**

Blessed provisioning (`!admin space create`, onboard, river-key) suppresses duplicate notices via `expect_channel_registry_binding()`.

### Edit channel

Registered channels: rename syncs `discord_name` in `mage_registry.yaml`; category moves and permission drift are logged with `!admin space sync` / `!admin audit` repair hints.

### Delete channel

Registry-bound channel deleted in Discord → entry marked **orphaned**; workshop files kept; ops notice posted. Run `!admin space sync` or audit to repair topology.

**Space close:** `!admin space close <key> --confirm` remains the blessed path for intentional retirement (lock/archive + registry inactive). Native delete is reconciliation, not the primary operator workflow.

---

## Close ≠ Delete (summary)

| Action | Discord | Essence / chronicle | Registry |
|--------|---------|---------------------|----------|
| **Close Thread** | Archived, readable | Policy C — full dissolve when substantive | Updated |
| **Delete Thread** | Gone | Only if history cached | Cleaned up |
| **`!dissolve`** | Archived | Always full dissolve path | Updated |
| **Delete channel** | Gone | N/A (channel-level) | Orphaned, not silent delete |

---

## Safety net

- **`!admin audit`** — one-way registry ↔ Discord check  
- **Startup backfill** — missed Gateway transitions during deploy  
- **Deploy habit:** verify service restart after `launchctl kickstart` (`ps lstart`)

---

## Related docs

| Topic | Doc |
|-------|-----|
| End-to-end journeys | [journeys.md](journeys.md) |
| `!dissolve` / checkpoint / release | [sessions.md](sessions.md) · [turtle-talk.md](../turtle-talk.md) |
| Lifecycle bar buttons | [eddy-lifecycle-bar.md](eddy-lifecycle-bar.md) |
| Shared spaces | `docs/chapters/design-admin-space-provisioning.md` |
