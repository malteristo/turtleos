# Design Chapter: Turtle Artifact Crystallization

**Opened:** 2026-07-17  
**Status:** Design in progress — dogfood seed from pinned home eddies  
**Depends on:** [design-pinned-home-eddies.md](design-pinned-home-eddies.md) (discovery door shipped)  
**Spec touch (later):** TURTLE_SPEC §11.5 write path; native `conduct.md` / prompts tool guidance  
**Dogfood first:** Operator river

---

## Tension

Tonight’s dogfood: practitioner asked for a workout plan → Turtle wrote a good plan **in chat** → practitioner had to type `!pin` to crystallize + home it. The pin path works. The **create drive** does not.

On Forge, Spirit’s harness pulls toward files. Turtle already has `write_practice_file` / `patch` / `append` tools, but native attunement treats chat as the finished product. Without an offer surface, working documents die in scroll-back.

Pinned home eddies shipped the **discovery door** (`!pin` / Keep as working plan → file + home eddy + river card). This chapter owns **when and how Turtle crystallizes** — and when crystallize is *not* a home pin.

---

## Dogfood facts (2026-07-17)

| Observation | Implication |
|-------------|-------------|
| Plan appeared only in chat | Crystallize is not automatic and not offered |
| Typed `!pin` created file + river card | Product path works once invoked |
| Stop pinning left debris (mended: delete card) | River hygiene matters for trust |
| Title grabbed first bullet once | Prefer thread name / heading over list lines |
| `!pin` and “make a file” felt conflated | Working plans want one gesture; notes may not |

---

## Two acts (do not merge forever)

| Act | Job | Surface |
|-----|-----|---------|
| **Crystallize** | Chat body → Tier-1 Notes file | Turtle tool write + short ack + `!read` pointer |
| **Home / pin** | Bind eddy ↔ file + river pin card | `!pin` or “Keep as working plan” button |

**Working plans:** crystallize + home are one product gesture (today: `!pin` ensures file).  
**Ordinary notes:** crystallize without home (no sticky eddy, no river pin).  
**Browse:** `!artifacts` / `!read` — inventory, not create. **No new `!artifact` create command.**

---

## Proposed locks (for Mage sanction)

### L1 — Offer, don’t silent-home

When Turtle (or the practitioner) has produced a **clear working document** in an eddy that is not already a home:

- Prefer a River/Turtle **act**: button **Keep as working plan** (already implemented in `home_plan_ui.offer_home_plan`).
- Do **not** auto-bind / auto-pin without confirm.
- Typed path remains `!pin` (reply to plan message or bare `!pin` using recent substantial message).

### L2 — When to offer home vs note-only

| Signal | Offer |
|--------|-------|
| Multi-use plan / checklist / draft the person will return to (workout, form, packing list) | **Keep as working plan** (crystallize + home) |
| One-off capture, scratch thinking, short note | Optional: crystallize to Notes only (“Saved to Notes”) — **no pin**; or leave in chat if they didn’t ask to keep |
| Ambiguous | Ask one short question, or offer home button only (higher bar) |

Day-one bias: **over-offer home for plan-shaped docs; under-offer silent file writes.**

### L3 — Who attaches the offer

**Recommended:** After Turtle posts a substantial structured plan (length + structure heuristics — headings/bullets, not an LLM “classifier theater”), **River** (or shell) may attach / follow with the Keep-as-working-plan view on that message or as a short follow-up act.

Turtle conduct one-liner: when you draft a durable plan, end with a plain invitation to keep it — shell may show the button; you do not invent sidebar language.

**Not day one:** ML classifier gate; proactive offers on every long message.

### L4 — Tools Turtle needs (mostly exist)

| Need | Status |
|------|--------|
| Write / patch / append Notes | Exists (`tos_tools`) |
| Read allowlisted artifacts | Exists |
| Bind home + river pin | Exists (`!pin` / `offer_home_plan`) |
| Quiet perform write on bound home | Helper exists (`patch_artifact`); **dialogue tool wiring residual** |
| Shell/River offer attach after plan-shaped reply | **Missing** — this chapter’s main implement slice |
| Conduct / prompt drive to crystallize + offer | **Missing** — small native attunement edit |

### L5 — Honesty

Product speech: file + home eddy + river pin. Never side-panel / shelf beside chat.

---

## Out of scope

- New `!artifact` create command  
- Portable “load this plan in any eddy”  
- Hosted-river fanout before operator recognition stays green  
- Auto-classifier as required gate  

---

## Implement sketch (after locks)

1. Heuristic `looks_like_working_plan(text) -> bool` (length, headings/bullets, keywords optional).  
2. Hook after Turtle reply in eddy (River or Turtle shell): if heuristic and not already home → `offer_home_plan`.  
3. Native `conduct.md` + prompts: one short section on working docs → offer keep / tools write for note-only.  
4. Wire `patch_artifact` (or thin tool) for home-eddy quiet updates.  
5. Shake + operator dogfood: ask for plan → button appears → confirm → pin tray → Continue.

---

## Recognition tests

1. Ask Turtle for a workout plan → **Keep as working plan** appears without typing `!pin`.  
2. Confirm → file on Notes shelf + river pin; Continue returns to same eddy.  
3. Scratch question with no plan → **no** offer spam.  
4. “Just save this note” (if offered) → file, no pin.  
5. No side-panel speech.

---

## Status

**Design open 2026-07-17.** Awaiting Mage locks on L1–L5 (especially L2 note-only and L3 who attaches the offer).
