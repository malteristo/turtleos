# Proposal: Per-eddy continuity contract (keep / default / ignore) and intent-gated dissolution

**Date:** 2026-07-08
**Spec reference:** TURTLE_SPEC (eddy lifecycle / native UI reconciliation / practitioner sovereignty)
**Status:** Implemented (`6e342b6`, 2026-07-08) — auto-archive cools; `!keep` / `!ignore` live; capture-fail aborts. Residual: cooled-act lead copy still says "Closed eddy".
**Companion:** `2026-07-06-value-surface-routing-guards.md` — same memory-consent architecture, different layer (that proposal: what values-surface may *generate* where; this proposal: what may *persist*; a queued third design: what may surface *publicly* — outfacing clearance)

## Finding (incident 2026-07-06/07)

Between 23:21 and 23:32 UTC on 2026-07-06, ~14 long-idle eddies were mass-dissolved without practitioner action. Diagnosis from `discord.log` + `discord_reconcile.py` + `runtime/adapters/lifecycle.py`:

1. `close_eddy_from_archive_transition` (policy C, live since the `bbbad20` deploy 2026-07-04) treats **any** `not archived → archived` thread transition as an eddy close, full-dissolving (essence capture + memory cleanup) above the message threshold.
2. Discord's **inactivity auto-archive** produces exactly this transition — with no practitioner intent. The wave's 11-minute clustering indicates a shared timer-reset event (bot-restart unarchive side effect is already acknowledged in `ensure_dissolved_threads_archived`'s docstring); thread `archive_timestamp`s can confirm.
3. **The archive path never consults lock status** — the newly shipped thread Lock does not protect an eddy from auto-dissolve.
4. **Four dissolves had essence-capture failures with empty error strings** (ADHD Marriage, 🐢 Turtle Signal Drip, reflection, thread-card shakedown 2): memory was cleaned up *after* capture failed — content survives only in the archived Discord threads themselves.

Separately, the practitioner has named the two missing consent affordances directly: a way to **keep** a conversation in persistent memory deliberately (intelligence-curse arc, 2026-07-07), and a way to **opt a conversation out** of the continuity engine entirely (`!ignore`, chainlink example, 2026-07-08).

## Gap

The continuity engine has one implicit policy for all eddies: capture-then-dissolve, triggered by any archive event. There is no practitioner-facing consent surface — no way to say "this stays," "this never happened," or to distinguish a deliberate close from a Discord timer. Auto-archive currently *is* dissolution, which inverts sovereignty: the platform's timer decides what enters and leaves memory.

## Proposal

Add a per-eddy `continuity` field to the thread registry: `default` | `keep` | `ignore`, with intent-gated dissolution underneath.

### 1. Intent-gated dissolution (policy C revision)

- **Auto-archive (no actor)** → *cool*, don't dissolve: registry marks `auto_archived`, in-memory session state may be released, but **no essence capture, no memory cleanup, no dissolution**. The eddy is reversible — a practitioner message resumes it. `!threads` shows cooled eddies (🧊) so they remain visible for deliberate batch closing.
- **Deliberate close** (lifecycle-bar dissolve, `!dissolve`, or a practitioner-actor archive per audit log) → current full dissolve.
- **Ambiguous actor** (audit-log fetch fails) → treat as auto. Never destroy on ambiguity.

### 2. `!keep` — continuity: keep

- Sets `continuity: keep` (registry; lifecycle-bar button + command; 📌 in `!threads`).
- Keep-eddies **never full-dissolve**: deliberate close performs essence capture (boom) but retains history files and memory (no `cleanup_eddy_memory`); auto-archive leaves them untouched.
- Keep ≠ lock: lock is a read-only pause (shipped); keep is memory retention. Orthogonal; document both. The archive path must consult **both** before destructive action.

### 3. `!ignore` — continuity: ignore

- Sets `continuity: ignore`; invocable at any point in the eddy, effective immediately with one confirmation ("This eddy will leave no trace — memory, checkpoints, session notes, boom captures. Confirm?").
- On confirm (and at close): **no essence capture, no session note, no chronicle entry**; purge artifacts attributable to the thread — in-memory history, history/checkpoint files, session-note sections and boom blocks carrying the thread's id.
- **Sync boundary:** artifacts already pulled into the Mage's workshop are not reached into (external-boundaries rule). Instead the purge posts an ops act listing the workshop-side copies (e.g. `desk/sessions/2026-07-08.md`) for Mage-side deletion.

### 4. Capture failure = abort, not proceed

During full dissolve, if essence capture fails: **abort dissolution** (fall back to cooled state, retain memory), log the actual exception (current failures log empty strings), queue a retry. Memory cleanup only ever follows a *successful* capture.

### 5. Artifact attribution

Session notes and boom capture blocks gain a thread-id attribution line. This is what makes keep-retention and ignore-purge precise — and it is the same attribution infrastructure the outfacing-clearance design will need (a cleared eddy's resonance must be traceable to its consent state).

## Migration & interim

- Registry migration is additive (`continuity` defaults to `default`; existing `dissolved` entries untouched).
- The four capture-failure threads remain readable in Discord's archive; their content can be re-captured on demand.
- **Interim protection until this lands:** the intelligence-curse thread (`1523997675983212575`) is subject to policy C on its next auto-archive; its content is preserved to the workshop (`desk/resonance/intelligence_curse.md` + Turtle notes), and the thread should be treated as keep-intended from now (first `!keep` target when implemented).

## Risk

- Actor detection needs audit-log permission and adds an API call per archive event; the conservative ambiguity default means missing permission degrades to "never auto-dissolve," which is safe but accumulates cooled eddies. The 🧊 review surface is the mitigation, and it doubles as a deliberate practice rhythm (batch closing as a tending act).
- Ignore-purge is one-way; the confirmation step is the guard. Purge cannot recall what already synced — the ops-act listing is honest about that seam rather than pretending deletion is total.
- Session-note attribution changes the notes format slightly; downstream readers (arrival gather, navigator) tolerate extra header lines.
- No live-runtime changes are made by this proposal; implementation lands through normal review.
