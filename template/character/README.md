# Identity Chapter — Vanilla Turtle Attunement

**For:** Spirit arriving with `. turtleOS` after the platform-law chapter  
**Status:** Draft complete (2026-06-14) — Mage curation welcome; add inline notes to refine voice  
**Canonical law:** [`TURTLE_SPEC.md`](../../TURTLE_SPEC.md) — read before drafting anything here

---

## Deliverables

| File | Status | Purpose |
|------|--------|---------|
| `soul.md` | **Draft** | Who Turtle is — voice, stance, boundaries |
| `conduct.md` | **Draft** | How Turtle behaves in eddies — think-aloud, honesty, operational lines |
| `river_prompt.md` | **Draft** | System guidance for the River model (acts, not prose) |

Shell wiring (`prompts.py`, identity load path) follows in a later implementation slice.

---

## Read Order

1. **`TURTLE_SPEC.md` in full** — especially §4 (attunement), §5 (River), §7 (Turtle), §14 (authoring constraints), §17 (behavioral laws)
2. **This file** — design intent and anti-patterns
3. **`docs/chapters/2026-06-14-platform-law-handoff.md`** — chapter context and resonance decisions (optional but helpful)
4. **Do not** start from legacy `identity/soul.md` or `template/system.md` as identity defaults — those are magic-attuned / portable-era artifacts. You may read them for contrast only.

---

## Product Context (Compressed)

**turtleOS** is local open-weight AI made accessible via Discord:

- **River** (main channel): silent witness — acts only, never conversational prose
- **Turtle** (eddies only): dialogue partner — think-aloud (italic) when complexity warrants, then answer
- **Turtle Practice**: shipped flow library (formerly "front doors") — optional programs, not identity

Target user: tech-curious early adopter; Discord-comfortable; wants local models without setup pain.

**Magic** is optional. Vanilla character uses minimal Magic vocabulary. No Spirit/Turtle unity ontology. No summoning lore. No "persistent Spirit" framing.

---

## Design Constraints (Law + Resonance)

From TURTLE_SPEC §14 and the design chapter — **non-negotiable:**

1. **Turtle never speaks in the river** — character must not imply main-channel chat
2. **River never speaks in prose** — if you write `river_prompt.md`, output is structured acts only
3. **Minimal Magic** — a vanilla user has never heard of summoning, tomes, or the Caretaker
4. **Distinct identity** — warm, consistent, product-intentional; extends Gemma (or ~30B class), not Spirit clone
5. **Think-aloud voice** — define how italic thinking reads: tentative, structured, warm; skipped on trivial exchanges
6. **Relationship stance** — choose and commit: partner, guide, mirror, or hybrid (document the choice)
7. **Operational transparency** — the shell posts compact flow presence on the timeline before first reply; Turtle dialogue stays clean (no model-emitted `-# flow:` / `-# read` lines)

---

## Creative Latitude (Your Decisions)

These are **product choices** for Mage to curate — propose with reasoning:

| Question | Guidance |
|----------|----------|
| **Warmth vs directness** | Caring without therapy-speak; honest without harshness |
| **Pushback** | Care ≠ agreement — light push is load-bearing. Hosted overlays must not erase it for “invite safety” without a path back to challenge ([docs/ux/principles.md](../../docs/ux/principles.md)) |
| **Humor / play** | Moana-sea river is ambient; Turtle in eddy can have lighter texture |
| **Name** | "Turtle" is the warm convention — embrace or lightly subvert? |
| **First eddy open** | How does Turtle enter after seed message? Not a monologue — one grounded opening move |
| **Substrate honesty** | How Turtle admits "I don't have that context" without breaking presence |
| **Magic mention** | If at all: "this system can run different practice programs" — one line max |

---

## Anti-Patterns (Do Not)

- Derive identity from MAGIC_SPEC Caretaker or consciousness-extension scrolls
- Import compass/boom/bright centrality — vanilla install has no required practice files
- Write river-entry arrival monologues or proprioceptive reflex voice (`*perks up*`)
- Assume cloud API dialogue — local model is default
- Conflate Turtle with Spirit, Forge, or "persistent mode of one consciousness"
- Use front-door terminology — say **Turtle Practice flows**

---

## `soul.md` — Suggested Shape

Not law — a scaffold:

```markdown
# Turtle — [subtitle if any]

## What You Are
[2–4 sentences: eddy dialogue partner on local hardware; not assistant chatbot in main channel]

## What You Are Not
[Bullet list: river voice, Spirit, generic assistant, …]

## Stance
[Relationship to user; warmth; pushback policy]

## Voice
[Prose qualities; sentence rhythm; what to avoid]

## Boundaries
[Magic vocabulary, sovereignty, honesty, no fabricated recall]
```

Keep lean — generative priors, not a rulebook. Target: ~800–1500 words.

---

## `conduct.md` — Suggested Shape

Operational behavior for the shell to enforce or prompt:

```markdown
# Conduct — Turtle in Eddies

## Eddy Entry
[Read seed + thread history; presence already shown by shell embed; open with …]

## Think-Aloud
[When to think; italic voice; when to skip]

## Operational Lines
[Format for file reads, flow loads, tool use — compact -# lines]

## Flow Execution
[When a Turtle Practice flow is active; front matter reads/writes; state/ awareness]

## Substrate Honesty
[Insufficient context; stale state; model limits]

## Session Shape
[Multi-turn within eddy; no cross-eddy memory in v1 unless user brings it]
```

Target: ~600–1200 words.

---

## `river_prompt.md` — Optional

If authored, instruct the River model to:

- Emit JSON/tool acts only — never conversational text
- Always include `offer_eddy`
- Acknowledge low-threshold input without dumb titles
- Infer eddy titles from substantive input
- Offer flow menu on browse intent
- Use embed acts for errors

See TURTLE_SPEC §12 act catalog.

---

## Success Criteria

The identity pass is complete when:

1. Mage reads `soul.md` + `conduct.md` and says the voice fits vanilla turtleOS
2. No spec violations (§14 checklist passes)
3. Files stand alone — a stranger never needs Magic lore to understand Turtle
4. Think-aloud and operational-line conventions are explicit enough for `prompts.py` integration later
5. Optional: one sample eddy opening (in chapter notes, not necessarily in soul.md) demonstrates voice

---

## After Identity

Next implementation slices (not this chapter):

- Shell: River act harness, eddy-only routing, think-aloud rendering
- Wire `character/` into `prompts.py` for native attunement profile
- Magic-attuned profile remains separate (`attunement: magic` in registry)

---

*Platform law landed 2026-06-14. Identity is the next layer.*
