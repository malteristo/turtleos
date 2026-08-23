---
summary: Turn source inspection into a precise, reviewable patch plan without editing files.
when: Turtle has identified a source issue or improvement and needs to hand off implementation safely.
---

# Patch Planning

Use this skill after source inspection finds a likely code change. The goal is not to edit. The goal is to make the next edit obvious, bounded, and verifiable.

## Plan Shape

Produce a patch plan with:

- **Problem:** the observed behavior or gap.
- **Evidence:** files, symbols, commands, or tool results inspected.
- **Change:** the smallest implementation that would address the problem.
- **Files:** exact files expected to change.
- **Verification:** compile checks, canary checks, shakedown steps, or live Discord checks.
- **Rollback:** how to back out if the change misbehaves.
- **Risk:** what could break or what remains unknown.

## Operating Rules

- Keep the plan smaller than the current evidence supports.
- Separate facts from guesses.
- If more inspection is needed, ask for one next source-inspection action rather than filling gaps with confidence.
- Do not claim the patch is done until Spirit or Mage applies it and verifies it.

## Completion

The Mage or Spirit should be able to implement the change from the plan without re-deriving the architecture.
