# Chapter handoff — River/Turtle split (pause for rethink)

**Date:** 2026-06-20  
**Status:** Paused — dogfood failed acceptance; architectural review needed  
**Mini HEAD:** `9d91fa1` (Turtle restarted)

---

## What we shipped this chapter

- **River owns acts:** `!` commands, lifecycle bar, seneschal act rows, act digests, bar re-anchor (`bar_anchor.py`)
- **Turtle owns prose:** dialogue in eddies; native URL auto-fetch disabled; seneschal extraction enabled
- **Reliability patches:** dialogue queue (no lock during LLM), `on_message_edit`, fetch act digest with excerpt, seneschal dedupe filter
- **Prompt tuning:** Turtle should suggest `!fetch`; River executes; use `[Act: !fetch]` excerpt

---

## Dogfood result: not acceptable

| Symptom | Evidence |
|---------|----------|
| Turtle disclaimers | Still says it cannot fetch / content not in eddy despite River act |
| Duplicate Fetch buttons | Two identical "Fetch link" buttons on one seneschal row |
| Identity confusion | Structural messages often appear as **turtle APP** in Discord UI |
| Seneschal log | `Seneschal row posted as ?` — River client identity not confirmed at post time |
| Hangs / silence | Channel lock + gemma latency; edits; restarts mid-turn; practitioner waits |
| Wrong memory labels | Thread context log: `2 mage / 3 spirit` — attribution conflates Turtle assistant with Spirit |

Partial wins: fetch embed + act log on button click; lifecycle bar present; typed `!` on River works.

---

## Signal: stripping acts from Turtle is fighting the harness

Current architecture **splits identity in Discord** (two bots) but **unifies in one Python codebase**:

- Turtle turn handler still **parses** Turtle prose → **posts** River buttons → **calls** `ensure_channel_bars`
- Act digests injected as synthetic user lines — fragile context bridge
- Prompt + regex + seneschal filter + digest format = four layers to keep aligned
- Every Turtle mention of `` `!fetch` `` can re-spawn buttons (duplicate extraction paths)

**Hypothesis for next chapter:** The split-bot *product* direction may be right (River = structure, Turtle = conversation) but the *implementation* of seneschal-as-Turtle-sidecar is wrong. Alternatives to evaluate:

1. **River-only suggestions** — Turtle never mentions command syntax; River model reads thread and posts act rows (no regex on Turtle output)
2. **Single bot, dual voice** — one Discord app; embed author/webhook distinction for “acts” vs “dialogue” (simpler interaction routing)
3. **Explicit act queue** — Turtle emits structured intent JSON (internal); River renders buttons; no prose parsing
4. **Drop seneschal v1** — lifecycle bar + typed `!` only until River-side seneschal exists
5. **Fetch as dialogue inject** — `!fetch` always injects `[Fetched content]` into history at act time (verify end-to-end before any button UX)

---

## Known bugs (carry forward)

- Duplicate seneschal buttons: likely `_extract_contextual_actions` double-match (backticks + recommendation tail)
- `Seneschal row posted as ?`: verify `river_client.user` at post time; confirm Discord shows **river** not **turtle**
- Thread history loader may label Turtle replies as spirit (`helpers.load_thread_history`)
- gemma4:31b turn latency blocks perceived responsiveness even when queue works

---

## Next chapter entry

1. Read this handoff + `docs/ux/eddy-lifecycle-bar.md` + `docs/turtle-talk.md`
2. **Decide architecture** (options above) before more prompt/filter patches
3. If keeping split-bot: prototype River-side seneschal; remove Turtle→River orchestration from `discord_bot.py`
4. Acceptance test script: one eddy, fetch via button, follow-up question — must cite article without re-fetch button

---

## Commits (main)

`9ee9648` sovereignty + bar anchor  
`d3d4516` native seneschal  
`679d9cb` no auto-fetch native  
`0186232` dialogue queue + edits  
`13442ab` import fix  
`1c80657` prompt voice  
`9d91fa1` fetch digest + seneschal filter  
