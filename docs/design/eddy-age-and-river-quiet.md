# Eddies Age — River Quiet

**Status:** Design note (Spirit thin-craft, 2026-07-20)  
**Trigger:** Operator boom + same-evening Discord digest (river ≈ Closed-eddy firehose)  
**Spec touch (candidate):** TURTLE_SPEC §8 lifecycle copy / river acts  
**Backlog:** residual of `2026-07-08-eddy-dissolve-semantics` — previously “optional polish”; boom elevates to product semantics

---

## Finding

Implementation already distinguishes **cool** (auto-archive, memory retained) from **dissolve** (deliberate close). Residual UX still leads with:

```text
Closed eddy | <name> — auto-archived (cooled — use !dissolve to close deliberately)
```

(`sessions.post_eddy_lifecycle_feedback`, `action="Closed eddy"`)

Operator signal: *I don’t need to be informed about every cooled eddy. Eddies should probably not close at all. Meaningful content lives in eddy notes / day / week artifacts. Eddies should just grow old — ground truth for CE.*

Also asked: rules for eddies appearing/disappearing in the Discord sidebar.

---

## Recommended product stance (default for Mage `.`)

1. **Lifecycle truth stays:** cool ≠ dissolve. No reopening dissolve-on-archive.
2. **Metaphor shift:** speak **age / cool**, not **close**, for auto-archive.
3. **River quiet:** do **not** post a river act for routine cools (idle auto-archive, empty/shake cools). Keep river acts for: opened eddy, deliberate dissolve, capture-aborted, maybe first cool of a *named significant* eddy (optional later).
4. **CE attunes to notes**, not lifecycle events — already true in architecture; copy should not imply otherwise.
5. **Sidebar:** Discord owns visibility. Threads leave the active sidebar when Discord auto-archives them (idle). Turtle’s cool marks registry state so Continuity/`!threads`/Continue can unarchive on re-entry. Appear/disappear is mostly Discord archive + sticky-home exceptions — not a second turtleOS sidebar product. Document in UX one-liner; don’t invent a shelf.

---

## Smallest shippable slice (when sanction + deploy ok)

| Change | Where | Risk |
|--------|-------|------|
| Rename act `Closed eddy` → `Cooled eddy` for `mode=="cooled"` / `light_archive` | `sessions.py` + tests | Low |
| Suppress river post for `mode=="cooled"` (and optionally `light_archive`) | `post_eddy_lifecycle_feedback` early return | Low–med (operators lose cool audit on river; `!threads` still lists cooled) |
| Leave dissolve + opened acts unchanged | — | — |

Defer: full “never archive” (fights Discord + sticky-home design). Age = cool quietly + notes persist.

---

## Sidebar one-liner (for help / onboarding)

> Active eddies show in Discord’s thread list. When idle, Discord archives them and they drop from the active sidebar — Turtle has **cooled** them (history kept). Use Continue / jump link / `!threads` to return; use dissolve only when you mean to end the eddy.

---

## Out of scope tonight

- Live deploy / launchctl
- Changing idle archive timers
- Anonymized UX digest (separate sketch)
