# Chapter: Turtle → River structured act offers

**Date:** 2026-07-18  
**Status:** Slice 1 shipped (Forge) — Mini deploy + dogfood pending  
**Deciders:** Kermit + Spirit  
**Builds on:** §5.8 split-bot; harness-split (read vs cache); River-only seneschal (2026-06-20); reject prose→button parsing

---

## Tension

Turtle knows the turtle-talk catalog better than most practitioners. River owns acts and contextual buttons. Today River heuristics cover a few cases (Save, Checkpoint intent, Keep-as-plan). The long tail only appears if the user already knows `!`.

Prose parsing (Turtle mentions `` `!checkpoint` `` → River posts button) **failed dogfood** — duplicates, identity blur, prompt/regex thrash.

## Architecture lock

| Role | Owns |
|------|------|
| **Turtle** | May **propose** one allowlisted act offer per turn via structured IPC (tool → signal file). Never posts act buttons in split-bot. May still mention commands in prose to the practitioner. |
| **River** | **Renders** the offer as a button row; **executes** on accept; writes `[Act: !…]` digests. Validates allowlist — never trusts arbitrary command strings from Turtle. |

**Priority after Turtle reply (one row max):**

1. Keep-as-working-plan (home plan heuristic)  
2. Turtle structured intent (this chapter)  
3. River heuristics (Save / Checkpoint)

## Slice 1

- Signal: `runtime/signals/act-offers/{channel_id}.json`
- Tool: `offer_river_act` — `action` ∈ `{checkpoint, save}`; `save` requires `url`
- River maps kinds → fixed button labels / `!` strings
- Tests: signal + seneschal consume + tool validation
- Prompt: one short guidance line — use the tool; do not expect backticks to spawn buttons

## Out of scope (later)

- Broader allowlist (`share`, `focus`, `release`, `flows`, …)
- Single-bot fallback posting from Turtle
- TURTLE_SPEC §5.8 one-liner (propose at chapter close / sanction)
- Model reliability tuning if under/over-offers

## Acceptance

1. Eddy: Turtle calls `offer_river_act(checkpoint)` when wrap-up fits → River posts **Checkpoint** once → tap → `[Act: !checkpoint]` in history  
2. Eddy: Turtle calls `offer_river_act(save, url=…)` for an uncached link → **Save to library** once  
3. Turtle prose mentioning `` `!checkpoint` `` alone does **not** spawn a button  
4. At most one contextual row per turn (home plan still wins over intent)

## Deploy

Restart **both** bots (`./restart.sh`). Shake: unit suite; live dogfood of the two offers above.
