# turtleOS UX Principles

**Status:** Living document — describes UX we **apply in the shell today**, not aspirational spec alone.  
**Canonical law:** [TURTLE_SPEC.md](../../TURTLE_SPEC.md) (platform rewrite, 2026-06).  
**Use this when:** reviewing behavior, designing a slice, dogfooding friction, or deciding whether a change belongs in River acts vs Turtle dialogue.

When implementation and these docs disagree, **implementation wins until someone updates them on purpose.** When these docs and TURTLE_SPEC disagree, **propose a spec amendment** — do not silently drift.

---

## How to read this collection

| Layer | Where | What it holds |
|-------|--------|----------------|
| **Principles** | [principles.md](principles.md) | Stable intent — why the UX feels the way it does |
| **Patterns** | Topic files below | Concrete behaviors the shell implements now |
| **Journeys** | [journeys.md](journeys.md) | End-to-end walkthroughs |
| **Rejected** | [rejected.md](rejected.md) | UX we tried or considered and explicitly do not want |
| **Review** | [review-checklist.md](review-checklist.md) | Questions before merging UX-touching changes |

**Traceability:** Each pattern lists primary code paths. Spec amendments trace to `TURTLE_SPEC.md`. Spirit/Mage edits to UX should start here, then code, then spec when law-level.

---

## Topic index

| Topic | Doc |
|-------|-----|
| Cross-cutting intent (River/Turtle, consent, visibility) | [principles.md](principles.md) |
| River bar, acts, chronicle | [river.md](river.md) |
| Blank eddy, deferred presence, system lines | [eddy-entry.md](eddy-entry.md) |
| Eddy lifecycle bar (checkpoint / release / dissolve) | [eddy-lifecycle-bar.md](eddy-lifecycle-bar.md) |
| Turtle voice inside eddies | [turtle-dialogue.md](turtle-dialogue.md) |
| Flow menu, Shelter vs Navigator intake | [flows-and-intake.md](flows-and-intake.md) |
| URL → context (read vs distill) | [link-reading.md](link-reading.md) |
| Checkpoint, release, idle capture | [sessions.md](sessions.md) |
| Practitioner walkthroughs | [journeys.md](journeys.md) |
| Do-not-reintroduce inventory | [rejected.md](rejected.md) |
| Pre-merge checklist | [review-checklist.md](review-checklist.md) |

---

## Spec alignment

**Status (2026-06-18):** `TURTLE_SPEC.md` amended to match shipped native UX. This collection is the **practitioner-facing resonance surface** — patterns, journeys, rejected UX, and review checklist. Spec holds platform law; these docs hold how it should *feel*.

| Topic | Spec | UX doc |
|-------|------|--------|
| Eddy affordance | §5.3–5.4, §17 — standing bar | [river.md](river.md), [journeys.md](journeys.md) |
| Flow entry | §5.4, §7.2 — orientation; intake | [flows-and-intake.md](flows-and-intake.md) |
| Link reading | §9.5, Law of Visible Link Read | [link-reading.md](link-reading.md) |
| Checkpoint / release | §8.4, §17 | [sessions.md](sessions.md), [eddy-lifecycle-bar.md](eddy-lifecycle-bar.md) |
| Native system lines | §7.7 | [eddy-entry.md](eddy-entry.md) |
| Rejected UX | §7.7 (partial) | [rejected.md](rejected.md) |

When dogfooding surfaces new friction, update **the relevant UX doc first**, then propose spec amendments for law-level changes.

---

## Key files

| Concern | Files |
|---------|--------|
| River acts + bar | `river_handler.py`, `river_bot.py` |
| Eddy spawn + presence | `eddy_spawn.py` |
| Flow loading + intake | `flow_runner.py`, `flow_intake_handler.py`, `flow_intake_opening.py` |
| Link reading | `link_read.py`, `url_validate.py`, `content_fetch.py`, `discord_bot.handle_dialogue` |
| River model prompt | `template/character/river_prompt.md` |
| Turtle character | `template/character/soul.md`, `conduct.md` |
| Session capture | `sessions.py`, `commands.py` |
| Eddy lifecycle bar | `eddy_lifecycle_bar.py`, `river_bot.py`, `discord_bot.py` |
| Platform law | `TURTLE_SPEC.md` §5, §7, §9.5, §17 |
| Shakedown | `scripts/shake_river.py`, `scripts/shake_flow.py`, `scripts/shake_link_read.py`, `scripts/shake_hosted_river.py` |
| Chapters (history) | `docs/chapters/2026-06-16-*.md`, `docs/chapters/2026-06-18-*.md` |

---

## Evolution log

| Date | Change |
|------|--------|
| 2026-06-16 | Native river acts; two-bot split; Eddy Door (pinned) + blank eddy + deferred presence |
| 2026-06-17 | Shell-inject flow presence; model no longer emits operational `-#` lines |
| 2026-06-18 | **Eddy bar** replaces pinned door — bottom anchor, Discord thread embed, flow menu on bar |
| 2026-06-18 | Split-bot handoff fix — River `add_user` on materialize; no Turtle `add_user` on river eddies |
| 2026-06-18 | Dogfood: flow menu installed flows only; flow eddy orientation; pinned-in-eddy rejected |
| 2026-06-18 | **Checkpoint vs release** — `checkpoint_session` on idle/`!checkpoint`; `!release` user-only |
| 2026-06-18 | **TURTLE_SPEC amended** — bar, system lines, checkpoint law |
| 2026-06-18 | **River intake v1** — Prepare/Skip/Begin, split-bot handoff + Turtle auto-opening |
| 2026-06-18 | **Eddy link reading** — URL-primary auto-fetch, status embed, spill, Read/Skip |
| 2026-06-18 | **Intake rename on Begin** — thread retitled from intention/territory before Turtle joins |
| 2026-06-18 | **SSRF hardening** — `url_validate.py` shared across link read, content_fetch, `!fetch` |
| 2026-06-18 | **UX doc split** — `docs/ux/` topic files; link-reading principles; stub `ux-principles.md` |
| 2026-06-19 | **Eddy lifecycle bar** specified — River-owned in-thread bar; appear on first activity; dissolve confirm Option A ([eddy-lifecycle-bar.md](eddy-lifecycle-bar.md)) |
| 2026-06-19 | **Eddy lifecycle bar shipped** — `eddy_lifecycle_bar.py`; checkpoint/release/dissolve buttons in live eddies |
| 2026-06-18 | **Flow trace + deploy** — shell-inject flow presence; Shelter meta/question guards; Mini at `28feb48` |

---

*This collection is the resonance surface for turtleOS UX — review it when the product should feel different, not only when code changes.*
