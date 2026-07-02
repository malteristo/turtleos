# Chapter — Continuity Engine Slice 1a: alive layer + `!focus` narrowing

**Date:** 2026-07-02
**Spec trace:** design `docs/design/continuity-engine-and-substrate.md` §5.2, §5.2a, §7, §11 (Slice 1)
**Commit:** `d4b4f42` (follows Slice 0 `3c9d614`)

## Intent

Ship the deterministic core of CE Slice 1 — the alive layer (active threads) as
headers in the holistic packet, plus per-eddy narrowing via `!focus` with scoped
self-feed — and live-verify the cross-process seam before dogfood. Conversational
narrowing (the intended front door) and checkpoint auto-proposals are deferred to
Slice 1b/2; `!focus` is the documented power-user shortcut (design §5.2a).

## Changes

| Area | What |
|------|------|
| `continuity_engine.py` | Alive layer (`state/alive.yaml`: read/write/add/remove/find/list active threads); per-eddy scope store (`state/scopes.yaml`, keyed by channel id); scoped self-feed (`render_scope_block` — keyword match over `sessions/*.md`, honest when thin); unified `render_substrate_packet` folding current + "In motion:" headers + intention + last-checkpoint into one block; `set_last_checkpoint` helper (rendered when present). Slice 0's `render_current_block` kept byte-stable via extracted `_when_line`/`_run_line`. |
| `commands.py` | `cmd_focus` — `!focus <topic>` narrows this eddy (creates the thread if new — manual pin folded in); `!focus` lists what's in motion + current focus; `!focus clear` widens. Registered in `DIRECT_COMMANDS`; added to help inventory. |
| `cmd_dispatch.py` | `focus` added to `_PRACTITIONER_COMMANDS` and act-digest fallback. |
| `discord_bot.py` | Seam at `_continue_dialogue_turn` swapped from `refresh_and_render` to `render_substrate_packet` with `get_scope(pd, channel_id)`. |
| `docs/turtle-talk.md` | `!focus` documented in eddy-core table + narrowing note. |
| `tests/test_continuity_engine.py` | 31 → 42 tests: alive CRUD, per-eddy scope isolation, header render + firewall, scoped self-feed match + honesty, unified packet, checkpoint carry-forward. |

## Design decisions

- **Per-eddy scope in `scopes.yaml`, not per-root `current.yaml`.** Split-bot is two
  OS processes (`com.turtle.river` handles `!focus`; `com.turtle.discord` reads the
  packet), so scope must persist to disk to cross the process boundary — and it must
  be keyed by channel id so narrowing one eddy never narrows the others.
- **Manual thread pin folded into `!focus`** (focus-creates-the-thread) rather than a
  second command — avoids colliding with the existing Discord `!pin` and keeps the
  narrowing surface to one jargon-free lever.
- **Vocabulary firewall extended** to the alive headers ("In motion:", never
  "knots"/"alive"); enforced by test on the full packet.

## Verified (live shakedown on the Mini)

- 42 CE tests green locally; Mini import smoke clean (`commands`/`cmd_dispatch`/
  `continuity_engine` load with real `discord`; `focus` in the running command list).
- **Cross-process write:** `!focus continuity engine` in the River process created the
  active thread in `alive.yaml` and wrote per-eddy `scopes.yaml` — verified in two roots.
- **Per-practitioner isolation:** an eddy resolving to Nesrine's root wrote *her*
  substrate, keyed by the exact eddy id — never the operator's (privacy, design §10).
- **Read half (real behavior):** after `!focus`, Turtle answered *"We are focused on
  the **Continuity Engine**"* — unprompted by the message, plain language, no jargon.
  The Turtle process composed a 10256-char scoped prompt with **0** `substrate packet
  failed` errors.
- **Confirmation reply** is plain-language and firewall-clean.
- Both practice roots restored to pre-shake state after verification.

## Deferred (Slice 1b / 2)

- **Conversational-offer narrowing** — Turtle offering to narrow when a first eddy
  message overlaps an active thread (confirm, never silent-set). Its own design fork
  (keyword-overlap vs LLM intent). This is the intended front door.
- **Checkpoint one-liner wiring** — `set_last_checkpoint` exists and the packet renders
  it, but wiring it into `cmd_checkpoint` is Slice 2 (checkpoint extraction).

## Status

**Shipped + live-verified.** Technical verification complete; practice evaluation
(dogfood) is next. TURTLE_SPEC amendment still staged until Slice 0–1 behavior settles.
