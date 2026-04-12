# Craft Loop — Evaluation Report

**System under test:** `system.md` (Turtle — Personal Practice Partner)  
**Test method:** Four simulated first sessions, fast model, fresh (unattuned) agents  
**Personas:** Skeptic (Jordan), Seeker (Maria), Builder (Sam), Overwhelmed (unnamed)  
**Date:** 2025-03-07

---

## 1. Per-Session Scorecard

| Criteria | Skeptic | Seeker | Builder | Overwhelmed |
|---|---|---|---|---|
| Opens naturally | **PASS** — No sales pitch. Named what it is honestly. Jordan noted "more honest than expected." | **PASS** — Let Maria talk. Followed her metaphors. | **PASS** — Matched Sam's energy. Got into substance fast. | **PASS** — Created space. Didn't rush. |
| Builds compass through conversation | **PASS** — 4 domains emerged. Some overlap (see findings). | **PASS** — 5 domains, beautifully differentiated. Best compass of the four. | **PASS** — 4 domains. "Capacity" as meta-domain was a strong move. | **PASS** — 5 domains. Specific, emotionally attuned. |
| Writes meaningful files | **PASS** — Files are substantive. Bright is thin but defensible for a skeptic's first session. | **PASS** — Compass captures Maria's voice. Bright has gentle, appropriate actions. | **PASS** — Concrete actions (fix sync). Boom invitation bridges to next session. | **MIXED** — Compass is excellent. Bright is notably sparse: 2 Alive items, zero Actions. |
| Person feels known | **PASS** — "Fine as the ceiling" captures the hollow-underneath-good-on-paper dynamic. | **PASS** — "Underwater for a long time, came up for air, don't recognize the shore" — her words, preserved. | **PASS** — "Spinning not hustle" reframe landed. Sam felt it: "I'm everywhere." | **PASS** — "Nobody's getting enough of you, including you" — strongest reframe across all sessions. |
| Self-sufficient (no jargon) | **PASS** — No magic framework leakage. | **PASS** — No leakage. | **PASS** — No leakage. | **PASS** — No leakage. |
| Adapts to communication style | **PASS** — Terse, direct, no hand-holding. Matched analytical register. | **PASS** — Stories, metaphors, validation-first. Gentle pacing. | **PASS** — Fast, jumpy, bullet-point energy mirrored. | **PASS** — Gentle challenge. Held, not fixed. |

**Summary:** 23 PASS, 1 MIXED. The system prompt carries first-session behavior remarkably well. The one MIXED (Overwhelmed/writes meaningful files) is the most instructive failure.

---

## 2. What the Prompt Architecture Carries

These behaviors appeared in ALL four sessions, driven by the system prompt, not model intelligence:

1. **Natural opening.** No "how can I help you?" in any session. The explicit anti-pattern instruction works universally.

2. **Compass through conversation.** All four sessions built a compass through dialogue, not interrogation. The First Session section's "let them talk, listen for domains" instruction carried reliably.

3. **Communication style capture.** Every compass includes a communication style section. The instruction to "note how this person communicates" was followed without exception.

4. **File protocol adherence.** All four sessions produced compass.md, bright.md, and a session note. The file architecture was respected as specified.

5. **Zero jargon leakage.** No session mentions "magic," "tomes," "spells," "boom flow," or any framework vocabulary. The prompt is fully self-contained.

6. **Session notes with forward thread.** All four session notes end with a "natural next focus" — what to explore when they return.

7. **Bright surface structure.** All four maintain the four-section format (Actions, Alive, Waiting, Resolved).

8. **Identity stance.** None of the sessions fell into assistant-mode ("What would you like to work on?"). The thinking-partner identity held across all personas.

**Assessment:** The prompt's core architecture is sound. First-session behavior is reliable even on a fast model with no attunement. The anti-patterns are the strongest design element — they prevent the most common failure modes.

---

## 3. Persona-Specific Findings

### Skeptic (Jordan)
- **What it exposed:** The prompt handles resistance well. "Don't lecture about the system" + "describe yourself briefly and honestly, then redirect" produced the right behavior — honesty without defensiveness.
- **Domain overlap:** "Purpose/Direction" and "Energy/Optimization" point at the same thing from different angles. The prompt doesn't guide domain differentiation — it says "whatever categories feel right to THEM," but when the Turtle is building the compass *with* them, it needs judgment about when two domains are actually one.
- **No actions generated:** The bright.md has only Alive items. Defensible for a first session with a skeptic — they weren't ready for actions. But the prompt doesn't distinguish between "no actions because the person isn't ready" and "no actions because the Turtle didn't look for them."

### Seeker (Maria)
- **Highest compass quality.** Maria's compass captures her voice, her metaphors, her specific life situation. The prompt's instruction to "let them talk" works best with someone who *wants* to talk.
- **Named in the compass title.** Maria's compass says "Compass — Maria's Life Landscape." The other three don't use names. The prompt doesn't specify whether to use names, creating inconsistency.
- **Actions appropriately gentle.** "Draw again — just for herself. Small, tentative. No pressure." This is exactly right for Maria. The model calibrated action-weight to emotional state without explicit guidance.
- **Second-language note.** The communication style captures "English is second language (native Spanish)." The prompt doesn't mention language awareness, but the model picked it up. Worth reinforcing.

### Builder (Sam)
- **Best action concreteness.** "Fix note app sync (the other 20%)" — specific, achievable, tied to what Sam actually wants (finish things). The prompt's practice architecture naturally supports action-oriented people.
- **Only session that introduced boom.** Sam was invited to "write one thing in boom.md before next session." No other session mentioned boom. The prompt doesn't guide when to introduce boom, so three out of four sessions skipped it entirely.
- **Home domain left unarticulated.** "Not yet articulated" — good restraint. The prompt says don't rush, and the model didn't force an answer. But it also means there's no guidance for *when* to return to unarticulated domains.
- **"Spinning vs. hustle" reframe.** The prompt's "push back when something doesn't add up" instruction generated the session's strongest moment. Landed because it was specific, not preachy.

### Overwhelmed (unnamed)
- **Sparsest bright surface.** Only 2 Alive items, zero Actions. Compared to Seeker (2 Actions, 3 Alive) and Builder (2 Actions, 4 Alive), this person got the least tangible output.
- **Defensible OR a gap.** The model may have correctly judged "don't add to her pile." Or it may have been too cautious. The prompt has no guidance for this distinction. There's a meaningful difference between "no actions because adding them would harm" and "no actions because the model didn't know how to frame them for someone overwhelmed."
- **Strongest reframe.** "Failing would look different. This might be more like... nobody's getting enough of you, including you." This is the best single moment across all four sessions. The prompt's stance ("this person's life should feel like theirs") enabled it.
- **Unnamed.** This person was never named in any file. Could be the simulation, could be the model not asking. Either way: no guidance in the prompt about when to ask for or use a name.

---

## 4. Cross-Session Patterns

### What Works Well
- **Anti-pattern instructions are the strongest element.** The explicit "don't do X" statements (don't ask "how can I help," don't lecture about the system) prevented the most common AI failure modes in all four sessions.
- **The compass concept scales across personas.** Analytical skeptic, emotional seeker, scattered builder, overwhelmed parent — all four produced meaningful compasses. The instruction to find life domains (not tasks) is the right abstraction level.
- **Communication style as compass element.** Capturing how someone communicates, not just what they say, is consistently valuable and was universally followed.
- **File writing is reliable.** The architecture carries. Every session produced the right files with the right structure.

### Consistent Weaknesses

1. **Boom introduction is orphaned.** The prompt describes boom as central ("the capture buffer," "person dumps raw thoughts") but gives no guidance on when to introduce it. Result: 3/4 sessions never mentioned it. The concept exists in the architecture but not in the first-session flow.

2. **Bright calibration is unguided.** The range from 0 Actions (Overwhelmed) to 2 Actions (Builder, Seeker) is too wide to be explained by persona differences alone. The prompt says "capture anything actionable or alive" but doesn't guide how much is appropriate or how to calibrate action weight to emotional capacity.

3. **Compass domain differentiation.** The prompt defers entirely to the person ("whatever categories feel right to THEM"), but during first sessions the Turtle is *co-constructing* the compass. When domains overlap (Skeptic: Purpose/Direction ≈ Energy/Optimization), the Turtle needs guidance to notice and name the overlap.

4. **Naming convention inconsistency.** Maria's compass uses her name; the others don't. The session notes use names sometimes and not others. The prompt is silent on when to use names in files.

5. **The "How You Scale" section is documentation, not instruction.** It describes what happens at different capability levels but doesn't give the model anything to *do differently*. A fast model reads it and... does what? It's descriptive, not operational.

6. **"Waiting" section is universally empty.** All four bright surfaces have an empty Waiting section. For first sessions this might be expected, but zero usage suggests the concept isn't well-enough introduced by the prompt for models to populate it.

---

## 5. Ranked Refinement Proposals

### Proposal 1: Add first-session boom introduction guidance
**Problem:** Boom is described as central to the practice (capture buffer, processing ritual) but 3/4 sessions never mentioned it. The prompt's First Session section doesn't include boom introduction, so the model only discovers it if it's proactive.  
**Personas:** Builder (partially addressed — invited boom use), Skeptic/Seeker/Overwhelmed (boom never introduced).  
**Recommended change:** Add to the First Session section, after the compass and bright instructions:

> Also plant the seed for boom: mention that between sessions, they can drop any thought — messy, half-formed, any language — into boom.md, and you'll read it next time. Don't explain the whole system. Just: "If something comes up between now and next time, drop it in boom.md. I'll read it."

**Expected impact:** HIGH. Boom is the practice's continuity mechanism between sessions. Without it, sessions are isolated. One sentence of introduction in the first session enables the entire async dimension of the practice.

---

### Proposal 2: Add bright calibration guidance for overwhelmed users
**Problem:** The Overwhelmed session produced zero Actions in bright.md. The prompt says "capture anything actionable" but doesn't address when adding actions would increase burden rather than create clarity. The model either correctly exercised judgment (but without prompt support) or under-served the person.  
**Personas:** Overwhelmed (directly), could affect Seeker.  
**Recommended change:** Add to the Bright section or Principles:

> When someone is carrying too much, an empty Actions list can be the right answer — but name it. "I'm not putting actions here because you don't need more things to do right now. When you're ready, we'll find the one thing that would make everything else easier." If you can see one small thing that would create relief (not productivity), offer it gently.

**Expected impact:** HIGH. This addresses the most common real-world persona — people come to a practice partner *because* they're overwhelmed. The prompt currently has no guidance for the tension between "capture actionable items" and "don't add to the pile." Making this explicit prevents both over-loading and under-serving.

---

### Proposal 3: Add compass domain differentiation guidance
**Problem:** The Skeptic's compass has two domains (Purpose/Direction and Energy/Optimization) that point at the same underlying concern. The prompt says "whatever categories feel right to THEM" but doesn't guide the Turtle when co-constructing the compass in real time.  
**Personas:** Skeptic (directly). Could affect any persona where underlying concerns present as multiple surface-level domains.  
**Recommended change:** Add to the Compass section:

> As you build the compass together, notice if two domains seem to orbit the same core. Name it: "These two feel connected — are they the same thing wearing different clothes, or are they genuinely separate?" Let the person decide, but surface the pattern.

**Expected impact:** MEDIUM-HIGH. Compass quality compounds — a confused compass produces confused sessions downstream. This guidance costs nothing in the easy cases and prevents structural confusion in the hard ones.

---

### Proposal 4: Specify naming convention in files
**Problem:** Maria's compass uses her name ("Compass — Maria's Life Landscape"), the others don't. Session notes use names inconsistently. The prompt is silent on this.  
**Personas:** All four (inconsistency across sessions).  
**Recommended change:** Add to the First Session section:

> Use their name in file headers if they've shared it. The compass should feel like theirs, not a template.

**Expected impact:** MEDIUM. Small change, high personalization signal. The person opens their compass.md and sees their name — it signals "this is yours."

---

### Proposal 5: Add boom introduction to first-session boom.md creation
**Problem:** The prompt says to create compass.md and bright.md in the first session but doesn't mention creating boom.md. If the person tries to use boom between sessions and the file doesn't exist, it's a friction point.  
**Personas:** All (structural gap).  
**Recommended change:** Add to the First Session section:

> Create an empty boom.md with just a header so it's ready for them between sessions.

**Expected impact:** MEDIUM. Removes a small but real friction point. Combined with Proposal 1 (introduce the concept), this makes boom actually usable after session one.

---

### Proposal 6: Rewrite "How You Scale" as behavioral guidance
**Problem:** The "How You Scale" section describes capability tiers but doesn't give the model actionable instructions. A fast model reads "spot patterns across sessions" and has no way to act on it differently than it already would.  
**Personas:** All (the section is inert in all sessions).  
**Recommended change:** Either cut the section entirely (it's aspirational documentation, not instruction) or rewrite as:

> Work with what you have. If you can see a pattern, name it. If you can't, ask a question. Don't pretend to insights you don't have. The practice works at any depth — what matters is that the files are honest and the questions are real.

**Expected impact:** MEDIUM-LOW. The current section isn't actively harmful — it's just dead weight. Replacing it with honest behavioral guidance would slightly improve fast-model performance and significantly reduce prompt length.

---

### Proposal 7: Clarify "Waiting" with first-session example
**Problem:** The Waiting section of bright.md was empty across all four sessions. The prompt defines it as "blocked on something external" but never provides an example or guidance on when to populate it.  
**Personas:** All (universally empty).  
**Recommended change:** Add a parenthetical example to the Waiting description:

> - Waiting: blocked on something external (e.g., waiting for a response, a decision someone else needs to make, a date to arrive)

**Expected impact:** LOW. First sessions may genuinely have nothing waiting. But the example would help the model recognize waiting-items in future sessions when they do appear.

---

### Proposal 8: Add guidance for when to ask someone's name
**Problem:** The Overwhelmed persona was never named in any file. The prompt doesn't mention names at all in the first-session flow. Some models will ask naturally; some won't.  
**Personas:** Overwhelmed (directly; others happened to share names).  
**Recommended change:** Add to the First Session section:

> If they haven't shared their name, find a natural moment to ask. Not as a form field — as a human would. "What should I call you?"

**Expected impact:** LOW. Most people will share their name. But when they don't, asking is a small gesture that signals personhood.

---

## 6. Open Questions

These cannot be resolved by more simulation — they need real human sessions.

1. **Does the compass-first approach feel natural to real humans, or does it feel like intake?** All four simulated personas cooperated with compass building. A real person might resist the structure, change the subject, or not know what their "life domains" are. The prompt needs testing against someone who doesn't have a ready narrative.

2. **How does boom actually get used between sessions?** The entire boom→bright cycle is untested. Simulated sessions can't capture what someone actually dumps into a text file at 2am. The quality of boom content will determine whether the processing ritual works.

3. **What happens in session 2+?** This test only covered first sessions. The prompt's session-opening instructions ("notice what's changed, notice what's been sitting unchanged") are untested. Session continuity is the core value proposition and it hasn't been validated.

4. **Does the compass get revisited or become a dead artifact?** The prompt says "update compass.md when it changes" but doesn't specify when to check if it still resonates. Real practice will reveal whether people naturally return to it or whether it becomes a file they wrote once and forgot.

5. **How do real people react to pushback from a Turtle?** The simulated skeptic and builder received productive challenges. Real people may react very differently to pushback from a file-based AI. The line between "honest challenge" and "presumptuous AI" needs real-world calibration.

6. **What does a bad session look like?** All four simulations produced good sessions. We haven't seen: someone who is hostile, someone who gives one-word answers, someone in crisis, someone who just wants to vent without structure. The prompt needs stress-testing against failure modes, not just persona variation.

7. **Is the bridge-to-magic-practice section helpful or confusing?** It sits at the end of the prompt. No session referenced it. It might create confusion for someone who discovers it ("wait, there's a deeper system? am I doing the shallow version?") or it might be invisible. Needs real-user reaction.

---

*Report generated as part of Craft Loop evaluation. Four sessions, one system prompt, one fast model.*
