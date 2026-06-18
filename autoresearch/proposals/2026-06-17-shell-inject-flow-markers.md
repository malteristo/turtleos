# Proposal: Shell-Inject Flow Markers (Native Eddies)

**Date:** 2026-06-17  
**Spec reference:** TURTLE_SPEC §7 (Turtle in eddies), §10–11 (Practice flows), §14 (Native prompt)  
**Status:** Draft  
**Origin:** Mage dogfood — Shelter flow on Discord (shake + live sessions)

---

## Finding

When a practice flow loads in a native eddy, Turtle emits operational lines **as dialogue prose**:

```
-# flow: Shelter
-# read state/notes/shelter-last.md
```

These lines are **prompted** (`flow_runner.build_flow_prompt_sections` → “emit on first reply”; `prompts.NATIVE_EDDY_DISCORD_HINT` repeats the instruction). The shell sends the model output verbatim — it does not inject or strip them.

Observed in dogfood and shake:

| Session | Placement | UX |
|---------|-----------|-----|
| Spirit shake | After reply body | Discord `-#` subtext — reads like a weird footer |
| Mage dogfood | Mid-message, sometimes in a block | Reads like Turtle speaking in code |

The files **are** read before reply (prompt assembly loads flow state). The emitted lines are **performance**, not a faithful tool trace — and they break Shelter’s register (presence, not ops).

---

## Gap

**Spec intent:** Operational lines denote what the shell did (load flow, read state).  
**Current behavior:** The model improvises placement and formatting; Qwen sometimes wraps lines in code-ish blocks or appends them after closing prose.

This fails two requirements:

1. **Honest trace** — practitioner cannot trust `-# read …` as shell truth  
2. **Voice integrity** — especially in Shelter, any code-like footer pulls the person out of the room

---

## Proposal

### 1. Shell injects flow presence (first reply in flow eddy)

On first Turtle reply when `context_type` / `flow_id` is set:

- Post a **silent presence line** (same family as “Turtle joined”), e.g. embed or `-#` subtext attached by the shell:
  - `Shelter · loaded shelter-last.md` (human-readable, not path dump)
- Optionally disable the button after first reply (mirror existing eddy button patterns)

The model is **not** asked to emit `-# flow:` or `-# read`.

### 2. Strip model-emitted operational lines before send

In `discord_bot.py` native eddy path, before `split_message(reply)`:

- Remove lines matching `^-#\s*(flow:|read\s)` from model output
- Log stripped lines to internal console only (016 principle — operational noise not surfaced)

### 3. Prompt changes

- Remove “emit `-# read` / `-# flow:`” from `NATIVE_EDDY_DISCORD_HINT` for native profile
- Remove “Flow operational lines (emit on first reply)” section from model-facing prompt in `build_flow_prompt_sections` — keep state bundle, drop emit hint
- Update `template/character/conduct.md` operational-lines paragraph to say shell handles trace

### 4. Shake harness

- `shake_flow.py`: assert shell presence embed / config flag instead of `-# flow: Shelter` in model prose
- Offline: keep `build_flow_prompt_sections` tests; drop assertion that joined prompt contains emit hint

---

## Risk

| Risk | Mitigation |
|------|------------|
| Magic-attuned (non-native) threads rely on model-emitted lines | Scope strip/inject to `uses_native_turtle_prompt()` only |
| Practitioners lose visibility into what was loaded | Shell presence line uses plain language; optional `!flow` debug for founders |
| Flow spawn without `flow_id` in config | Inject only when `load_flow_spec` resolves |

---

## Test plan

1. Offline: flow prompt sections no longer contain “emit on first reply”
2. Live shake Shelter: first reply has **no** `-# flow:` in Turtle prose; shell posts presence once
3. Mage dogfood: screenshots show clean dialogue body only

---

## Traces to

- Dogfood session 2 (`heavy day need shelter`) — flow loaded, markers in wrong register  
- Shake thread `shake-shelter-20260617-182546` — footer-style markers  
- `flow_runner.py` `operational_lines()`, `prompts.py` `NATIVE_EDDY_DISCORD_HINT`
