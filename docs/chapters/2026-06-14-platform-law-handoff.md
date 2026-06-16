# Chapter Handoff — Platform Law & Ripple

**Closed:** 2026-06-14  
**Chapter arc:** turtleOS decoupling → vanilla product vision → TURTLE_SPEC rewrite → resonance pass → doc/template ripple  
**Next chapter:** `. turtleOS` scoped to **identity crafting** (native attunement)

---

## What This Chapter Set Out To Do

Move turtleOS from magic-coupled "Spirit-in-persistent-mode" default toward a **platform + attunement** product: local open-weight AI accessible through Discord (river + eddies), with Magic as optional layer.

---

## What Was Achieved

### 1. Strategic resonance (conversation)

Agreed vanilla product shape:

| Component | Role |
|-----------|------|
| **River** | Main channel — acts only, no prose; Moana-sea / casita metaphor |
| **Turtle** | Eddies only — dialogue + threshold-gated think-aloud |
| **Two local models** | Small River + capable Turtle (~30B class); cloud opt-in |
| **Turtle Practice** | Shipped flow library (retired "front door" term) |
| **Minimal practice root** | `character/`, `flows/`, `chronicle/`, `state/` — no required compass/boom/bright |
| **Chronicle** | Dual layer; thread jump URLs on eddy materialize |
| **Sediment / PRACTICE.md** | Deferred / paused |

Key UX decisions: always-offer-eddy button; NL→acts + turtle-talk `!` power path; chat-app eddy persistence; spec-then-identity authoring order; single canonical spec (no Magic mirror body).

### 2. TURTLE_SPEC rewrite (`turtleos/TURTLE_SPEC.md`)

- Title: **Law of the Platform** (not Persistent Spirit)
- ~689 lines — River/Turtle split, act catalog, practice state, install law, Appendix A for magic-attuned
- Mage resonance pass integrated (14 inline notes → law)
- Magic bundle: stub pointer only (`library/resonance/turtle/TURTLE_SPEC.md`)

### 3. Ripple (§19 steps 2–4)

| Artifact | Status |
|----------|--------|
| `README.md` | Local-first product narrative |
| `ARCHITECTURE.md` | Target architecture + migration status table |
| `PRACTICE.md` | Paused banner |
| `docs/install/SKILL.md` | Agent-assisted install |
| `template/` | `character/`, `flows/`, `chronicle/`, `state/` skeleton |
| `.env.template` | Ollama-first defaults |
| `mage_registry.example.yaml` | `attunement` comment |
| `docs/architecture.md` | Pointer to canonical docs |

**Not done:** Shell code migration (River acts, eddy-only Turtle) — explicitly next implementation chapter after identity.

---

## Operator Context (Kermit's Instance)

- Mac Mini runs **magic-attuned** profile today — not vanilla default
- Legacy shell still active (proprioception, river dialogue, cloud dialogue options)
- Phase 2 contextual buttons shipped prior sub-chapter; commit state may still be open on Mini
- Live instance update is **last** per §19 — after vanilla identity + shell slices

---

## Next Chapter — Identity Crafting

**Status:** Complete (2026-06-14)

**Deliverables (in `template/character/`):**

| File | Purpose |
|------|---------|
| `soul.md` | Native Turtle voice — eddy partner, not Spirit |
| `conduct.md` | Think-aloud, operational lines, flow/state rules |
| `river_prompt.md` | Act-only River JSON contract |

**Next:** Mage curation (optional annotations) → shell wiring in `prompts.py` → migration slices

---

## Next Chapter — Shell Migration (after curation)

**Invocation:** implementation work on `turtleos` repo

**First slice:** River act harness, always-offer-eddy, eddy-only Turtle routing

See ARCHITECTURE.md migration table.

---

## Open Threads (Carried Forward)

| Thread | Owner | When |
|--------|-------|------|
| Native character authoring | Next `. turtleOS` chapter | Now |
| Shell migration (River acts, eddy-only) | Implementation slice | After identity |
| Turtle Practice flows — turtleOS-ready | Flow prep | Parallel or after identity |
| Practice state MV (`state/` beyond notes/) | Design chapter | v1.1 |
| Sediment / cross-eddy memory | Design chapter | Deferred |
| Magic-attuned Mini migration | Operator | Last |
| Prior: Phase 2 commit, sediment, 032 computer use | Operator backlog | As Mage prioritizes |

---

## Lessons

- **Spec before identity** prevents Caretaker/Spirit bleed into vanilla product
- **Always-offer-eddy** is a safety net — buttons are constant affordances, not classification outcomes
- **Single canonical spec** beats mirror maintenance
- **Migration honesty** in ARCHITECTURE.md keeps operator instances valid while law moves forward
- **River acts / Turtle dialogue** split is the distinctive product bet — enforce in law before code

---

## Files Touched This Chapter (turtleos repo)

- `TURTLE_SPEC.md` — rewritten
- `README.md`, `ARCHITECTURE.md`, `PRACTICE.md`
- `docs/install/SKILL.md`, `docs/architecture.md` (banner)
- `template/README.md`, `template/character/README.md`, `template/flows/_example.md`, `template/state/`, `template/chronicle/`
- `.env.template`, `mage_registry.example.yaml`

Magic repo: `library/resonance/turtle/TURTLE_SPEC.md` (stub), `library/resonance/turtle/README.md` (canonical pointer).

---

*Design arc complete. Next breath is voice.*
