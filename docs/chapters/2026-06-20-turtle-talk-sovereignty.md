# Chapter — Turtle-Talk Platform Sovereignty

**Date:** 2026-06-20  
**Scope:** Documentation (chapter A) + code alignment (chapter B)

---

## Intent

Complete the v1 decoupling narrative at the **command inventory** layer: turtleOS is sovereign; Magic integrates it, not the reverse. Retire Magic workshop overlay from turtle-talk while keeping platform session continuity (checkpoint, flow writes) and deferring legacy thread patterns to Appendix A.

## Decisions

| Retire from turtleOS inventory | Defer (Appendix A) | Keep |
|--------------------------------|-------------------|------|
| Session & practice state (`!boom` … `!propose`, Magic `!edit`) | `!thread`, panel, absorb, eddy-check | River + eddy core + operator (`!diagnose`, `!admin`) |
| Outfacing `!signals`, `!drip` | | Flow checkpoint / release / dissolve |
| | | `!read` / `!ls` / `!search` on **practice root** |

Filesystem: practice root = `~/workshops/<practitioner>/`, not Magic `desk/`. Magic coupling documented in Magic repo (`library/resonance/turtle/`).

Future: novel turtleOS-native public extension (e.g. Twitter) — not port of Magic signal drip.

## Artifacts changed

### Chapter A (docs)
- `docs/turtle-talk.md` — rewritten inventory  
- `TURTLE_SPEC.md` §5.5 — cross-ref one-liner  
- Magic `desk/notes/on_turtle_talk.md` — practice note aligned  

### Chapter B (code, 2026-06-20)
- `commands.py` — retired handlers removed; `DIRECT_COMMANDS`, `_help_embed_fields`, panel, contextual actions aligned  
- `prompts.py` — platform seneschal; practice landscape uses sessions/flows not boom/compass  
- `discord_bot.py` — contextual command lists synced; proprioceptor, boom thread, offer_eddy gated to `magic` profile  

## Remaining

- Magic bundle doc pass (`library/resonance/turtle/`) — integration direction Magic → turtleOS  
- Deploy + shake on Mac Mini when ready  
