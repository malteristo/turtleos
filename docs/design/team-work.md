# Team work — shared horizon, sovereign fronts

**Status:** Implemented 2026-09-07 · first live instance: Quest

## Experience contract

A team exists because its members share a direction, not because one member may
assign the others. turtleOS gives this middle ground a durable shape:

- The **shared horizon** is broad, revisable, and confirmed by every active
  member.
- A **member front** is that person's current sub-goal or exploration and its
  relation to the horizon: advance, explore, support, challenge, or paused.
- The member owns their front, next move, dependencies, commitments, and
  capacity. Turtle may suggest; only the member confirms.
- The coordinator keeps the board and process coherent. Coordination grants no
  authority over another member's intent or testimony.

Alignment is therefore observable without becoming obligation. A member can
explore, challenge the current framing, or pause and still remain honestly
represented in the team.

## Activity forms

The team primitive supports:

1. Discovering and refining a shared goal.
2. Independent work in member-owned eddies.
3. Contributions, progress, commitments, dependencies, and handoffs.
4. Open tasks and owner-confirmed assignments.
5. Proposals, affected-member confirmation, and agreed decisions.
6. Artifact creation, review, integration, and provenance.
7. Candidate intersections between member activities.
8. Shared convergence when a decision or moment genuinely needs everyone.
9. Reflection, learning, pause, re-alignment, and retirement.

These are platform capabilities. A campaign, software project, research effort,
or household undertaking composes them without becoming a new channel type.

## State and authority

`team/events.jsonl` and governed proposal files are the record. `team/current.*`
is a rebuildable board. Every mutation names actor, role, source eddy, timestamp,
and scope.

- A shared horizon is confirmed by every active member.
- A member front is confirmed by that member.
- A commitment is confirmed by every named owner.
- An assigned task is confirmed by its named owner.
- A scoped decision is confirmed by every affected member.
- A contribution or artifact is attributed to its member and implies no agreement.
- An intersection remains a candidate until the activity makes it relevant.

## Member lanes

A member lane is visible to the team and writable for state by one owner.
Discord cannot make a public thread read-only for selected members, so turtleOS
enforces ownership before dialogue and persistence. A non-owner may peek but a
message in the wrong lane receives a plain notice and advances nothing.

Lanes publish bounded attributed developments to the shared root. Each sibling
lane receives only unseen summaries through a delivery cursor. Full transcripts
are not copied and no member's private practice root is read.

## Galactic Adventure

Galactic Adventure is the first event-backed team activity. The former shared
table is an immutable prologue. Gargibald and Ossimandus continue in separate
member lanes against one campaign event stream.

Every completed player/Turtle exchange is persisted before semantic reduction.
The current world, scene, checkpoint, and per-member character state are
readable derived views. A failed reducer leaves the raw event pending. Each
player advances immediately; unseen sibling effects enter the story only when
meaningful and paths reconcile at natural scene boundaries.

## Deliberate omissions

- No round-robin wait.
- No coordinator assignment authority.
- No silent private-to-shared memory merge.
- No sibling transcript injection.
- No Quest-specific memory engine.
- No claim that the first campaign defines the final multiplayer mechanics.
