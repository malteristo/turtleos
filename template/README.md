# Practice Root Template

Starter layout for a vanilla turtleOS instance. Copy the **required** directories to your practice root (e.g. `~/workshops/you/`).

## Required (TURTLE_SPEC §11.1)

```
practice_root/
├── character/          # Turtle attunement — soul.md, conduct.md (§14)
├── flows/              # Turtle Practice prompt programs
├── chronicle/          # Deep event log (runtime writes deep.jsonl)
└── state/
    ├── notes/          # Flow outcomes, exit summaries
    └── registry.yaml   # Optional file inventory (see state/registry.yaml)
```

## Optional (legacy portable / flow-loaded)

These files are **not** required at install. Flows may declare `reads:` / `writes:` to load them when a program needs them:

| Path | Purpose |
|------|---------|
| `compass.md`, `boom.md`, `bright.md` | Legacy portable practice surface |
| `intentions/`, `sessions/` | Extended practice files |
| `system.md` | Portable prompt (pre-shell era) |

Keep them in `template/` for reference and for flows that expect them; do not copy unless you need them.

## Flows

Each flow is a markdown file with optional YAML front matter:

```yaml
---
title: Example
reads: [state/notes/example.md]
writes: [state/notes/example.md]
think_aloud: auto
---
```

Plain prompts without front matter run in-eddy only — no persistent state.

See `flows/_example.md` for a skeleton.

## Character

Native vanilla attunement — **`soul.md`**, **`conduct.md`**, **`river_prompt.md`** (authored 2026-06-14 per TURTLE_SPEC §14). See `character/README.md`.
