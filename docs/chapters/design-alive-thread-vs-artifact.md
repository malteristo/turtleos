# Design Note: Alive Thread vs Artifact

**Opened:** 2026-07-18  
**Status:** Design open — boundary locked vs crystallization; implement deferred  
**Seed eddy:** `collecting family favorite recipes for turtle` (`1527955819717591101`)  
**Depends on:** Continuity Engine ([continuity-engine-and-substrate.md](../design/continuity-engine-and-substrate.md)); pinned home eddies ([design-pinned-home-eddies.md](design-pinned-home-eddies.md)); crystallization ([design-turtle-artifact-crystallization.md](design-turtle-artifact-crystallization.md))  
**Dogfood first:** Operator river (cooking / living collections)

---

## Tension

Crystallization shipped an offer for **plan-shaped working docs** (Keep as working plan → file + home eddy + river pin). Dogfood then tried a *different* desire: a family recipe book — collect over time, query when deciding dinner, shopping list + cook-through later.

In that eddy Turtle stayed in framing dialogue; no plan-shaped body appeared, so the offer correctly did not fire. Broadening `looks_like_working_plan` → `looks_like_artifact` would still not have helped those turns — and would pull living collections into the **tool** habit (boil it down to a file) rather than the **relational** habit (Turtle remembers cooking talk across eddies and answers from that ground).

The design question:

> What should be conversation context that belongs to a common thread, and what role (if any) do artifacts play in that context?

---

## Two jobs (do not merge)

| Job | Primary surface | Example |
|-----|-----------------|--------|
| **Alive thread** | CE active theme (“knot”) + related eddies over time | Family favorites / cooking — grows through dinners you talk through |
| **Working document** | Notes file + optional home eddy + river pin | Workout plan you revise and perform |

**Living collections** (recipe book, packing lore, “how we do bedtime”) lean alive-thread-first.  
**Performable bodies** (today’s workout, this trip’s packing list as a checklist) lean artifact-first.

Hybrid is allowed: theme is primary; artifact is an optional *export* when the job is perform / print / revise-a-fixed-body (e.g. tonight’s shopping list from the theme).

---

## Proposed locks (for later sanction)

### L1 — Crystallization stays working-doc only

Do **not** rename or broaden the heuristic to “artifact.” Recipe-book conversations are out of scope for Keep-as-working-plan spam. Crystallization chapter remains the workout-plan product path.

### L2 — Alive thread is primary for living collections

“Recipe book” = theme in `alive.yaml` (practitioner-facing: a living thread Turtle can scope into), fed by cooking-related eddies and checkpoints — not a schema file filled in advance. CE already names this: active threads are **themes, not tasks**.

### L3 — Intent-to-home ≠ plan-shaped output

When someone asks for a durable *room* (“I want the book to exist”), that is a different signal from “Turtle just wrote a structured plan.” Candidate product (not day-one of crystallization): offer to **bind this eddy as home for the theme** (continuity room) — not necessarily write a Notes file.

### L4 — Artifact role (secondary)

Artifacts play a role when the practitioner needs:

- a body to revise in place weeks later, or  
- a perform/export surface (shopping list, printable card), or  
- explicit “save this list” after a concrete dump of recipes.

They are not the default ontology for “things we care about together.”

---

## Out of scope (this note)

- Implementing CE theme promotion from the recipes eddy  
- Broadening offer heuristics  
- New `!artifact` / recipe commands  
- Auto-classifier for “collection vs plan”

---

## Open questions

1. Should “home eddy” eventually mean **theme room** as often as **file room** — one product with two bindings, or two products?  
2. When does Turtle *offer* to open/scope an alive thread vs silently use CE inject?  
3. Family channel vs operator river — does a recipe theme live in family workshop, operator, or both with sovereignty rules?

---

## Recognition tests (when implemented)

1. Cooking talk across two eddies → Turtle can answer “what do we like?” without a recipe file existing.  
2. Workout-plan reply still gets Keep offer; open-ended “I want a recipe book someday” does **not**.  
3. Optional: after several concrete recipes named in chat, Turtle may offer export/home — not on the first framing turn.

---

## Status

**2026-07-18:** Boundary agreed — crystallization = working docs only; this note owns alive-thread vs artifact. Next: design depth / CE slice when chapter gravity returns (not offer-hook code).
