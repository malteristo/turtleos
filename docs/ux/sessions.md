# Session capture — checkpoint and release

Three operations — do not conflate them:

| Operation | Trigger | Clears history | What it saves |
|-----------|---------|----------------|---------------|
| **`checkpoint_session`** | 15 min idle (automatic) or `!checkpoint` (manual) | **No** | Flow writes (≥2 exchanges); eddy note (≥4 — **the** reflection artifact, `story/eddies/`; cooldown applies to **idle** triggers only, manual/release always reflect); `sessions/YYYY-MM-DD.md` assembled mechanically from the day's eddy-note entries |
| **`release`** (`!release` only) | Practitioner explicit | **Yes** | Runs checkpoint first, then clears history + release embed |

Idle marks the session **paused** (`active_sessions.closed`) so the monitor does not re-fire; the next message reopens it. Manual `!checkpoint` does **not** pause — practitioner continues.

River records successful checkpoints in **chronicle** (`💾 checkpoint (idle|manual|release): …`) — structural memory, not eddy dialogue.

Regular eddies: eddy notes today (a manual `!checkpoint` weights the note toward exchanges since the last checkpoint); **sediment** (cross-eddy resonance) deferred. Flow eddies: mechanical writes to flow `writes` paths.

**Implementation:** `sessions.py` (`checkpoint_session`, `CheckpointResult`), `story_notes.py` (`write_eddy_note`); `commands.py` (`cmd_checkpoint`, `cmd_release`, `cmd_dissolve`); chronicle via `_append_resonance_chronicle`.

**Accessible path:** in-thread lifecycle bar — [eddy-lifecycle-bar.md](eddy-lifecycle-bar.md). Same handlers as `!checkpoint` / `!release` / `!dissolve`.

**Native Discord UI:** **Close Thread** in the thread menu runs the same dissolve pipeline (policy C) — see [discord-native-ui.md](discord-native-ui.md). Prefer Close over Delete for substantive eddies.

**Spec:** TURTLE_SPEC §8.4

**Journeys:** [journeys.md](journeys.md)
