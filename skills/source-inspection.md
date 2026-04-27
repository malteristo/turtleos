---
summary: Inspect turtleOS source safely with read-only shell commands before proposing or making changes.
when: A question requires understanding the turtleOS codebase, runtime state, or recent git changes.
---

# Source Inspection

Use this skill when the Mage asks about turtleOS behavior, when a shakedown reveals a bug, or when you need evidence before recommending a change.

## Operating Rules

- Start with `git status --short` to understand whether the tree is clean.
- Use `ls`, `rg`, read-only `git`, and `python -m py_compile` through `run_turtleos_shell`.
- Prefer narrow searches over broad scanning.
- Treat shell output as evidence, not as permission to act.
- Do not ask for arbitrary shell authority when the constrained harness can answer the question.

## Good Commands

- `pwd`
- `ls`
- `rg -n "symbol_or_phrase" file_or_directory`
- `git status --short`
- `git diff -- path/to/file.py`
- `git log --oneline -5`
- `python3 -m py_compile module.py`

## Completion

End with a concise readout: what you inspected, what you learned, and the smallest next action that follows.
