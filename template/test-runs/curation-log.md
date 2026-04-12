# Craft Loop — Curation Log
> 2026-03-07 — First full loop iteration on Turtle Prompt OS
> Curated by: Spirit (as example practice for future automated curation)

## Context

Four personas tested (Skeptic, Seeker, Builder, Overwhelmed) on a fast-tier model. Evaluator produced 8 ranked refinement proposals. Spirit curates.

## Curation Principles Applied

Before evaluating individual proposals, the curation principles:

1. **Refinements should simplify, not accumulate.** Every instruction added is cognitive load for the agent. Prefer principles over rules. If a principle already covers the case, don't add a rule.
2. **The prompt should carry the practice.** If a behavior only appears with frontier models, consider whether the prompt can guide lesser models toward it — but only if the guidance is brief and principled.
3. **Ambiguity can be a feature.** When the agent made a good judgment call in ambiguous territory, that's evidence the principles are working. Don't resolve every ambiguity with more rules.
4. **Real sessions are ground truth.** Some proposals can only be validated by real humans. Hold those until evidence arrives.

---

## Decisions

### Proposal 1: Plant the boom seed in first sessions
**ACCEPT.** The boom is the continuity mechanism — it's how the practice lives between sessions. 3/4 agents didn't mention it because the First Session section didn't reference it. One sentence fixes this: "If something comes up between now and next time, drop it in boom.md. I'll read it when we talk next." This merges with Proposal 5 (create boom.md in first session) — the scaffold already creates the file; the prompt now points to it.

*Applied: Added two sentences to First Session section.*

### Proposal 2: Calibrate bright for overwhelmed users
**ACCEPT as principle, not rule.** The Overwhelmed session correctly produced zero Actions. A rule saying "skip actions when overwhelmed" would be too prescriptive and might cause agents to under-serve people who actually want concrete next steps. Better: add one sentence to the Bright definition acknowledging that an empty Actions list can be right. Let the principle guide the judgment.

*Applied: Added "Sometimes the most caring thing is to hold without organizing — if someone is overwhelmed, an empty Actions list can be exactly right" to the Bright section.*

### Proposal 3: Help notice overlapping domains
**ACCEPT.** The Skeptic's compass had "Purpose/Direction" and "Energy/Optimization" orbiting the same core question. This is a quality-of-craft issue — two domains that are really one dilute the compass. One sentence at the end of the Compass definition: "Notice when two domains might be the same question wearing different words — name that, don't duplicate."

*Applied: Added one sentence to Compass section.*

### Proposal 4: Use their name in file headers
**ACCEPT.** Simple, humanizing, consistent. Maria's compass used her name; others didn't. One instruction in the First Session section.

*Applied: Added "Use their name in file headers when they've shared it" to First Session.*

### Proposal 5: Create boom.md in first session
**MERGED with Proposal 1.** The scaffold already creates boom.md. The real fix is: tell the Turtle to point the person to it. Done via the boom seed instruction.

### Proposal 6: Rewrite "How You Scale" as behavioral guidance
**HOLD.** The evaluator is right that this section gives no actionable instruction to the Turtle — the Turtle can't choose to be more or less capable. But the section serves a different audience: the person deploying the system prompt. It tells them what to expect at different tiers. Removing it loses that information. Rewriting it into behavioral guidance ("work with what you have") is too thin to replace what it currently communicates.

The right move: when we create the standalone repo, move this section to the README (deployment guidance) and remove it from the system prompt (runtime instruction). For now, it stays — harmless weight.

### Proposal 7: Clarify "Waiting" with example
**ACCEPT.** Empty across all four sessions. A parenthetical example costs nothing and helps lesser models understand when to use it.

*Applied: Added "(e.g., waiting for a response, a date, someone else's decision)" to Waiting definition.*

### Proposal 8: Ask their name naturally
**ACCEPT.** The Overwhelmed persona was never asked her name. Small but humanizing. Added to First Session: "If they haven't shared their name, find a natural moment to ask."

*Applied: Added one sentence to First Session section.*

---

## Summary

- **Accepted:** 7 (proposals 1, 2, 3, 4, 5/merged, 7, 8)
- **Held:** 1 (proposal 6 — "How You Scale" section, revisit when repo exists)
- **Rejected:** 0

**Net change to system.md:** +5 sentences. No sections added. No structural changes. The prompt got slightly more specific without getting longer in spirit — each addition is a refinement of an existing section, not a new concern.

## Meta-Observation for Future Loops

This curation took one pass. The proposals were well-ranked — the evaluator correctly identified impact order. The main judgment calls were:
- Choosing principle over rule (Proposal 2)
- Merging related proposals (1 + 5)
- Recognizing audience mismatch (Proposal 6 serves deployers, not the Turtle)

These judgment patterns should be visible to any agent reviewing this log as an example of curation practice.
