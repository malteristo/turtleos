# Session capture — checkpoint and release

Three operations — do not conflate them:

| Operation | Trigger | Clears history | What it saves |
|-----------|---------|----------------|---------------|
| **`checkpoint_session`** | 15 min idle (automatic) or `!checkpoint` (manual) | **No** | Flow writes (≥2 exchanges); session note (≥4, reflection cooldown applies) |
| **`release`** (`!release` only) | Practitioner explicit | **Yes** | Runs checkpoint first, then clears history + release embed |

Idle marks the session **paused** (`active_sessions.closed`) so the monitor does not re-fire; the next message reopens it. Manual `!checkpoint` does **not** pause — practitioner continues.

River records successful checkpoints in **chronicle** (`💾 checkpoint (idle|manual|release): …`) — structural memory, not eddy dialogue.

Regular eddies: session notes today; **sediment** (cross-eddy resonance) deferred. Flow eddies: mechanical writes to flow `writes` paths.

**Implementation:** `sessions.py` (`checkpoint_session`, `CheckpointResult`); `commands.py` (`cmd_checkpoint`, `cmd_release`); chronicle via `_append_resonance_chronicle`.

**Spec:** TURTLE_SPEC §8.4

**Journeys:** [journeys.md](journeys.md)
