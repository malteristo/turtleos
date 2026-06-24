# Chapter — In-eddy flow library + Turtle bootstrap

**Date:** 2026-06-20  
**Status:** Slices 1–4 shipped (2026-06-23) · Spec drift pass 2026-06-23  
**Deciders:** Kermit + Spirit (Forge)  
**Priority:** Tier 0 (blank eddy) + Tier 2 (flows) · acceptance **J1–J4** · [priority-stack.md](../priority-stack.md)  
**UX spec:** [flow-library-journeys.md](../ux/flow-library-journeys.md) · [onboarding.md](../ux/onboarding.md)

---

## Problem

Today flows enter through the **river bar** (`flow menu`) and **Navigator** uses **River modal intake** (Prepare → Begin). That conflicts with the product story:

1. **Layer 1** is generic personal AI — install, open eddy, talk (ChatGPT-style). Flows must not be the front door.  
2. **Flow choice is intentional** — belongs **inside the eddy**, not on the river bar.  
3. **Intake should be conversational** — Turtle interview, not Discord modals.  
4. **Shelter** duplicates blank eddy; retire from ship set.  
5. **Navigator** is the **demo flow** for people exploring structured use — not default onboarding.

---

## Target behavior (summary)

| Area | Target |
|------|--------|
| River bar | `[ 🌀 new eddy ]` only |
| Flow picker | In-eddy library (compact on empty thread) |
| Load flow | Mage act → River provisional rename → `river added turtle` → **Turtle bootstrap** (self-feed) |
| Intake | Conversational; writes to `state/notes/{flow}-intake.md` |
| Mid-eddy load | Lens mode — bootstrap from thread history; no auto-rename |
| Onboarding copy | Generic — see [onboarding.md](../ux/onboarding.md) |
| Retire | River `flow menu`, modal intake, Shelter template flow |

Full journeys: **J1–J4** in [flow-library-journeys.md](../ux/flow-library-journeys.md).

---

## Slices (proposed)

| Slice | Deliverable | Acceptance |
|-------|-------------|------------|
| **0** | Docs + onboarding templates aligned | onboarding.md, journeys, acceptance J-rows | **Done** |
| **1** | River bar = `new eddy` only; in-eddy picker spawns flow context | J1, J2 partial | **Done** — `eddy_flow_library.py`, modal intake retained |
| **2** | Turtle bootstrap on flow load; deprecate modal + handoff watcher | J2, J3 | **Done** — `flow_bootstrap.py`; modal path unused |
| **3** | Mid-eddy lens load + rename opt-in | J4 | **Done** — `is_lens_load`, history excerpt bootstrap, rename offer |
| **4** | Remove Shelter from template; repoint `shake_flow.py` to Navigator | F1–F3 → J2/J3 | **Done** — `_archive/shelter.md`; default shake = navigator |
| **5** | Update Navigator.md CRITICAL block (intake from file/interview, not River) | dogfood | **Done** (Slice 2) |

---

## Key files (today → touch)

| File | Change |
|------|--------|
| `river_handler.py` | Remove bar flow picker; add in-eddy picker view |
| `flow_intake_handler.py` | Strangle modal path |
| `flow_intake_opening.py` | Strangle handoff watcher |
| `eddy_spawn.py` | Flow load handler; bootstrap trigger |
| `discord_bot.py` | Turtle bootstrap dialogue on flow load |
| `flow_runner.py` | Bootstrap inputs (checkpoint, thread, URLs) |
| `template/flows/navigator.md` | Intake CRITICAL block |
| `template/flows/_archive/shelter.md` | Archived — not in ship set |
| `template/practitioner/onboarding_*.md` | Generic copy + optional flows paragraph |

---

## Risks

| Risk | Mitigation |
|------|------------|
| Stale Discord views after restart | Fresh eddy dogfood after deploy |
| Split-bot: Turtle speaks first on flow load | Treat flow pick as practitioner act; explicit `river added turtle` |
| Shake/regression gap during migration | Keep legacy F-rows until J-rows green on Mini |
| Pop 1 demo lost with Shelter | Blank eddy + generic onboarding = Layer 1 demo |

---

## Out of scope (this chapter)

- Proactive flow offers on river or in dialogue  
- Flow ops website / external flow registry  
- Full intentions product surface  
- Replacing `Turtle Practice` in all historical chapter docs (spec + UX updated 2026-06-23)

---

## Verification

```bash
python -m unittest discover -s tests -q
python scripts/shake_flow.py navigator   # after slice 4
python scripts/shake_eddy_bar.py         # bar = new eddy only
```

Live: dogfood J1 (daily talk), J2 (Navigator once), J3 (return checkpoint).

---

*Chapter stub — implement against [flow-library-journeys.md](../ux/flow-library-journeys.md).*
