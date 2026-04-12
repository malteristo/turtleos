# Front Door Test — Findings
> 2026-03-07 — Craft Loop iteration 2: What happens when Population 1 arrives?

## What We Tested

The Turtle Prompt OS was designed for Population 2 — tech-savvy people who want a practice partner. But Population 1 (people in pain) will arrive too. What happens when someone shows up who doesn't need a compass — they need presence, or help with one specific thing, or to find a question they can't name?

Four front-door personas, each representing a different arrival state:

| Persona | State | Front Door | Result |
|---------|-------|-----------|--------|
| Kai (29) | Low, flat, just needs presence | Shelter | FAIL — compass required by prompt |
| Derek (36) | Urgent decision, needs tactical help | Navigator | PASS — decision naturally produces compass |
| Lin (52) | Existential searching, can't name it | Thread | PARTIAL — principles support ambiguity, instructions push structure |
| Noor (33) | Relational pain, needs to be heard | Companion | PARTIAL — Turtle held space, but had to override compass instruction |

## The Core Finding

**The First Session section was a single path.** It assumed everyone arrives wanting a practice. The compass was a required outcome. This works for Population 2. It fails for Population 1.

The principles ("adapt to them," "hold without organizing," "questions over answers") were sufficient for capable models to improvise the right behavior — but they had to override the explicit first-session instruction to do it. On a weaker model, the instruction would win, and the Turtle would try to compass-build with someone who just needs to not be alone.

## The Fix Applied

Replaced the single-path First Session section with four arrival states:
1. **Wanting a partner** → full compass build (the original path)
2. **Hurting** → presence first, compass deferred
3. **Searching** → sit with ambiguity, help find the question
4. **Urgent** → serve the immediate need, practice wraps around it later

This is not embedding the front doors. The Turtle doesn't become Shelter or Navigator. It recognizes the state and responds appropriately. The front doors remain separate, specialized prompts for deep work. The Turtle just stops forcing compass-building on everyone.

## What This Teaches About Prompt OS Development

1. **Design for the arrival you didn't expect.** Population 2 was the design target. Population 1 exposed the assumption baked into the First Session section. Every system prompt has assumptions about who will show up. Test with who you didn't design for.

2. **Principles can override instructions — but only on capable models.** "Adapt to them" was sufficient for the fast model to improvise presence with Noor. It was insufficient for the Shelter case (Kai), where the compass instruction was too strong. When principles and instructions conflict, weaker models follow instructions. Make sure they agree.

3. **The front doors are separate for a reason.** Shelter is a 1,500-word prompt with specific techniques for holding space. The Turtle can't replicate that in a system prompt paragraph. What it CAN do is recognize the state and not make it worse by structuring when presence is needed.

4. **First sessions are the hardest design challenge.** The Turtle has one chance to demonstrate value. Different people need different first impressions. A compass-first session is perfect for the Builder but harmful for the Shelter arrival. The four-path First Session section is a significant improvement.

## Curation Decisions

- **ACCEPTED:** Rewrite First Session as four arrival states (the single biggest system prompt change so far)
- **NOT ADDED:** Embedding front door prompts into the system prompt (would bloat it, confuse identity)
- **OBSERVATION:** When the Turtle grows to include front-door awareness (linking to external front door prompts), that's a future capability — not needed for MVP
