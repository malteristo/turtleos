---
summary: First-pass self-development loop for understanding turtleOS code without making writes.
when: The Mage asks Turtle to improve itself, debug its own behavior, or inspect its implementation.
---

# Self-Development Inspection

This procedure is the first safe slice of Turtle self-development. It gives Turtle a way to understand its own code before Spirit or the Mage grants edit/deploy authority.

## Steps

1. Read the relevant skill card, usually `skill:source-inspection`.
2. Check repository state with `git status --short`.
3. Locate likely files with `ls` and targeted `rg`.
4. Inspect narrow diffs or symbols with read-only `git` and `rg`.
5. Verify syntax of any file under discussion with `python3 -m py_compile <file.py>` when relevant.
6. Summarize the diagnosis, smallest proposed change, and verification plan.

When doing this from Discord, keep tool use narrow: one shell action per turn. If more evidence is needed, continue in a follow-up turn rather than batching several shell calls at once.

## Boundaries

- Do not commit, stage, restart services, install packages, or edit files through the shell harness.
- Do not infer from memory when source inspection is cheap.
- If a change is needed, hand the patch plan to Spirit/Mage unless a future write-authority procedure has explicitly been installed.

## Done Means

The Mage can see what Turtle inspected, what Turtle believes, and what change would be made next.
