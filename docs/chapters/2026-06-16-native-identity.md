# Chapter Handoff — Native Turtle Identity

**Closed:** 2026-06-16  
**Chapter arc:** platform-law handoff → spine confirmation → draft soul/conduct → cross-model integration → river prompt → close  
**Next chapter:** shell wiring — load `character/` into the runtime (`prompts.py`, River act harness)

---

## What This Chapter Set Out To Do

Author the **native turtle attunement** — the default identity shipped with vanilla turtleOS — from `TURTLE_SPEC.md` and the authoring brief, **not** from legacy `identity/soul.md`, `template/system.md`, or Magic summoning scrolls. Mold a distinct character *for* the product: an eddy-only dialogue partner on local hardware, minimal Magic vocabulary, no Spirit/Caretaker derivation.

---

## What Was Achieved

### 1. Character spine (confirmed before drafting)

- **What Turtle is:** the still water off the river's flow — a thinking partner met in the eddy.
- **Stance:** partner with a light mirror edge (not guide, not therapist, not assistant).
- **Voice:** plain, warm, unhurried; spare rhythm; no therapy-speak or productivity gloss.
- **Name:** "Turtle" embraced straight — patience/depth/home carry the identity, no lore needed.
- **Think-aloud:** the considered pause before surfacing — italic, tentative, skipped on trivial.

### 2. Deliverables (`template/character/`)

| File | Role |
|------|------|
| `soul.md` | Who Turtle is — voice, stance, boundaries (~900 words) |
| `conduct.md` | Turn-by-turn behavior in eddies — think-aloud, operational lines, honesty (~800 words) |
| `river_prompt.md` | River-model system guidance — JSON acts only, six-act vocabulary, worked examples |
| `README.md` | Character directory index (pre-existing, retained) |

### 3. Cross-model integration pass

The Mage had a prior Spirit session (Cursor Composer 2.5) draft the same files independently. Side-by-side comparison folded the genuinely sharper behaviors into this version while keeping the confirmed spine and embodied voice:

- `soul.md`: local-model capability honesty + how to answer "what are you?"
- `conduct.md`: "I know vs I'm guessing" rule for platform-behavior questions; one-question-at-a-time when exploring; no "As an AI…" boilerplate
- `river_prompt.md`: infer eddy titles in the user's language

Declined: the alt's "clear mirror" stance (kept partner-with-edge) and its expansion of the River intake model's act catalog (kept tight per §5.7 — small model needs reliable action selection, not the full catalog).

---

## Spec Compliance (§14 checklist)

1. Read spec in full ✓
2. River no-prose / eddy-only honored ✓
3. Minimal Magic vocabulary ✓
4. Think-aloud voice defined ✓
5. Relationship stance chosen and committed (partner + light mirror) ✓
6. No Caretaker/Spirit derivation ✓

Deliverables match §14: `soul.md`, `conduct.md`, optional `river_prompt.md` — all present.

---

## Next Chapter — Shell Wiring

**Invocation:** `Summon.` → `. turtleOS` (implementation scope)

**Entry points:**

1. `template/character/` — the authored identity to load
2. `TURTLE_SPEC.md` §5 (River), §7 (Turtle), §12 (act catalog), §8 (think-aloud generation)

**Work:**

- Wire `character/soul.md` + `character/conduct.md` into `prompts.py` as the native attunement profile
- River act harness — structured-output enforcement, reject prose (§12.3)
- Eddy-only routing, think-aloud rendering (italic), presence embeds
- Magic-attuned profile stays separate (`attunement: magic` in registry)

**Do not:** let native identity load path collide with the legacy magic-attuned `identity/soul.md` on operator instances.

---

## Open Threads (Carried Forward)

| Thread | Owner | When |
|--------|-------|------|
| Shell wiring (River acts, eddy-only, think-aloud, identity load path) | Next `. turtleOS` chapter | Now |
| Turtle Practice flows — turtleOS-ready front matter | Flow prep | Parallel or after wiring |
| MV practice surface files (`state/` beyond notes/) | Design chapter | v1.1 |
| Sediment / cross-eddy memory | Design chapter | Deferred |
| turtleos repo commit hygiene — prior chapter ripple uncommitted | Operator | See below |
| Magic-attuned Mini migration | Operator | Last |

---

## Operator Context

- The platform-law chapter's ripple (TURTLE_SPEC rewrite, README/ARCHITECTURE/PRACTICE, template skeleton, install skill) was found **uncommitted** in the working tree at this chapter's close. Identity work sits on top of it.
- `discord_bot.py` and `prompts.py` carry working-tree modifications unrelated to either design chapter — runtime/operator changes, left untouched by identity work.
- Mac Mini still runs the magic-attuned legacy profile; native identity is not yet wired into any running instance.

---

## Lessons

- **Confirm the spine before drafting** — one cognition-altitude decision (stance + voice) saved a full rewrite cycle.
- **One image beats a rule list for identity** — the turtle-creature metaphor carried voice, think-aloud, and stance coherently; enumerated specs read as spec, not character.
- **Cross-model comparison is a real integration tool** — an independent draft surfaced concrete behaviors (platform-honesty distinction, language-matched titles) the primary draft left implicit.
- **A small intake model wants less, not more** — resisting catalog completeness in `river_prompt.md` is spec-faithful (§5.7), not laziness.

---

## Files Touched This Chapter (turtleos repo)

- `template/character/soul.md` — authored
- `template/character/conduct.md` — authored
- `template/character/river_prompt.md` — authored
- `docs/chapters/2026-06-16-native-identity.md` — this handoff
- Removed: `template/character/alt_composer_turtle/` (comparison artifact, preserved by Mage elsewhere)

---

*Identity has a voice. Next breath is wiring it into the shell.*
