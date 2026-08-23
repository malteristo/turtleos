# Chapter — Consolidation: traceability & technical debt map

**Date:** 2026-06-20  
**Status:** Complete  
**Deciders:** Kermit + Spirit (Forge)  
**Precedes:** Harness ch. (Slice 2 debug) · Decomposition ch.

---

## Tension

v1 spec refurbish gave clear product law, but implementation accumulated legacy magic-attuned paths, experimental features, and monoliths (`commands.py` ~2030 lines, `discord_bot.py` ~1890). Documentation traceability lagged; no Sunday pass in ages. Mage asked: can we rewrite top-down? what to retire? what to integrate?

---

## What we did

1. **Traceability matrix v0** — `docs/traceability-matrix.md` (35 rows: spec § → module → status → action)
2. **Acceptance index** — `docs/acceptance/README.md` (harness, river/bar, flow, hosted, negative cases)
3. **Retire / Strangle / Integrate / Keep classification** — in matrix summary
4. **Drift sweep** — findings below
5. **Test baseline** — 147 unit tests OK (`python -m unittest discover -s tests`)

---

## Drift sweep findings

| Check | Result |
|-------|--------|
| `TURTLE_SPEC.md` | Current (2026-06-18); harness § cross-refs pending Slice 3 |
| `ARCHITECTURE.md` | Honest migration table; line counts slightly stale |
| `docs/architecture.md` | **STALE** — dated 2026-03-21; contradicts git-canonical workshop; header updated to redirect |
| `docs/turtle-talk.md` | Mostly current; sovereignty chapter done |
| `docs/development.md` | Current; traceability backlog updated to point at matrix |
| `README.md` / `PRACTICE.md` | Not re-audited this session — next Sunday |
| Retired markers grep | `proprio`, `triage`, `vortex` still in live code paths (expected: strangle) |
| `~/practice`, `magic-bridge`, SCP | Not found in public turtleos tree ✅ |
| Magic bundle `library/resonance/turtle/README.md` | Freshness labels present; some desk paths stale — **Integrate** on Magic side |
| Tests spec-indexed | **Gap** — only `test_runtime_update` cites TURTLE_SPEC; index is follow-up |

---

## Key decisions

1. **No big-bang rewrite.** Strangler migration behind attunement profiles; chapters close gaps row-by-row.
2. **Harness split is the template** — architecture lock → slices → acceptance → spec cross-ref last.
3. **Next implementation chapter:** Harness Slice 2 (Save offer) **or** explicit dogfood trace session — matrix row §9.5 already marks Partial.
4. **Decomposition chapter queued** after harness green: `commands.py` first gravity well.

---

## Lessons

1. **Boundary debt hurts more than feature debt** — split Discord identity without split harness responsibility caused dogfood failure (briefing Lessons 1–3).
2. **Traceability matrix makes “is docs sufficient?” answerable** — verdict: spec yes, module boundaries + acceptance index were the gap (now started).
3. **147 passing unit tests ≠ UX acceptance** — matrix separates `unit` vs `dogfood` verification tiers.
4. **Sunday metabolism overdue** — both Magic workshop and turtleos `docs/architecture.md` suffered.

---

## Artifacts

| File | Role |
|------|------|
| `docs/traceability-matrix.md` | Living law → code map |
| `docs/acceptance/README.md` | Scenario catalog |
| `docs/development.md` | Points to matrix; backlog trimmed |

---

## Next chapter options (Mage `.` to pick)

| Option | Focus | CR |
|--------|-------|-----|
| **A — Harness** | Save offer dogfood trace + Slice 3 spec cross-refs | Medium — needs clean `river.log` run |
| **B — Decomposition** | `commands.py` dispatch extraction plan (no behavior change) | High after harness |
| **C — Sunday** | Magic `@sunday` + turtleos doc refresh + bundle resonance pass | High — metabolism |

---

*Consolidation complete. Matrix is the navigation surface for all subsequent turtleOS chapters.*
