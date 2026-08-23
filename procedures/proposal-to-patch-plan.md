---
summary: Convert an inspected Turtle proposal or bug into a bounded patch plan while preserving read-only authority.
when: A proposal, shakedown, canary result, or Discord observation suggests a Turtle source change.
---

# Proposal To Patch Plan

This procedure lets Turtle participate in its own development without crossing into write authority. Turtle inspects, reasons, and produces a plan. Spirit or the Mage applies the patch separately.

## Steps

1. Read `skill:source-inspection` and `skill:patch-planning`.
2. State the proposal, bug, or observed gap in one sentence.
3. Check repository state with `git status --short`.
4. Inspect one relevant file or symbol per Discord turn.
5. Stop when the smallest plausible change is clear, or when the next needed evidence is known.
6. Produce a patch plan using the shape from `skill:patch-planning`.

## Boundaries

- Do not edit, stage, commit, restart services, or deploy (`TURTLE_SPEC.md` §20).
- Do not ask for widened shell authority as part of the plan.
- Do not combine patch planning with shakedown. Planning ends with a proposed verification path.
- If the tree is dirty, name the dirty files and avoid plans that depend on overwriting unrelated work.

## Done Means

The output is a handoff artifact: enough for Spirit or the Mage to apply a small patch, verify it, and rollback if needed.
