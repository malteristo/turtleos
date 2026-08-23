# Chapter: Flow trace + deploy alignment

**Date:** 2026-06-18  
**Status:** Shipped — `28feb48` on main; Mini deployed  
**UX doc:** [flows-and-intake.md](../ux/flows-and-intake.md), [eddy-entry.md](../ux/eddy-entry.md)  
**Proposals:** [shell-inject-flow-markers](../../autoresearch/proposals/2026-06-17-shell-inject-flow-markers.md) (shipped), link reading (prior slice, `9300cae`)

## Problem

Two practitioner-facing gaps after link reading shipped:

1. **Deploy drift** — Mac Mini behind laptop (`f277bb6` vs `9300cae`); piecemeal runtime during link-reading chapter.
2. **Flow operational lines in Turtle voice** — Shelter dogfood showed `-# flow:` / `-# read` (and later flow-example meta) in dialogue instead of on the timeline. Partial implementation: strip + prompt changes existed; shell never posted `flow_presence_line()`.

## Solution

### Shell-inject flow presence (`3165c68`)

- `post_flow_presence_if_needed()` in `eddy_spawn.py` — posts `-# Shelter · loaded …` once before first Turtle reply (native only).
- Wired in `discord_bot.py` and `flow_intake_opening.py`.
- Character + UX docs aligned: shell owns trace, model owns voice.

### Shelter dogfood hardening (`ef9130f`, `28feb48`)

- Removed copyable `*(No question. End here.)*` from flow examples; strip meta footers before send.
- Flow sections moved **last** in native prompt (override soul/conduct question bias).
- First-reply question guard for Shelter (strip `?` sentences) — tactical until identity craft session.

## Practitioner journey (Shelter)

```
river added turtle
-# Shelter · loaded shelter-last.md    ← shell (not Turtle prose)
Turtle: presence-only dialogue
```

## Key files

| File | Role |
|------|------|
| `eddy_spawn.py` | `post_flow_presence_if_needed`, `flow_presence_posted` flag |
| `flow_runner.py` | `flow_presence_line`, `strip_model_operational_lines`, `apply_flow_reply_guard` |
| `discord_bot.py` | Native send path: presence → strip → guard |
| `prompts.py` | Flow sections after Discord hint (recency) |
| `template/flows/shelter.md` | Shape-only examples |

## Deferred

- **Shelter identity craft** — register/tone with Qwen; guard is shell safety net only.
- **Mini stash** `pre-9300cae-deploy 20260618` — pre-pull local deltas; review or drop separately.

## Lessons

- "Timeline owns the trace" applies to flow loads same as URL fetch — embed/subtext from shell, not model performance.
- Flow example blocks need explicit "do not copy" framing or they become dialogue leaks.
- Turn contracts that fight character defaults need prompt recency **and** optional shell enforcement for v1 local models.
