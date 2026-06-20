# Chapter — Acceptance dogfood (native harness + lifecycle)

**Date:** 2026-06-20  
**Status:** Complete — practitioner dogfood on Mini; harness green; lifecycle split-bot gaps filed  
**Deciders:** Kermit + Spirit (Forge)  
**Thread:** `#physics lab mini universe experiment time test` (`1517909441817739345`)  
**Builds on:** `2026-06-20-harness-split-read-vs-cache.md`, `docs/acceptance/README.md`

---

## Purpose

Close the **Acceptance chapter** promised in the Consolidation traceability arc: run the indexed scenarios (H*, R*, partial F*) on the operator Mini at commit `2fbde49` (Strangler stack), record pass/fail with evidence, and name the next implementation chapter from gaps — not from unit tests alone.

---

## Environment

| Item | Value |
|------|--------|
| **Instance** | Mac Mini (`turtle@100.110.46.104`) |
| **Commit** | `2fbde49` (post-Strangler: harness, decomposition, seneschal retire) |
| **Attunement** | `native` |
| **Bots** | `com.turtle.discord` + `com.turtle.river` (split-bot) |
| **Practitioner** | Kermit (`firlefance`) + Spirit probes for retry |
| **Models** | Turtle `gemma4:31b`; fetch distill `qwen3.5:27b` (`REFLECTION_MODEL`) |

**Incident during session:** Turtle process wedged after idle session note (~17:27); no `Turtle inbound` for subsequent messages until `launchctl kickstart -k gui/501/com.turtle.discord` (pid 7126). Mars URL at 17:22 was lost to wedge, not harness logic.

---

## Results summary

| Block | Pass | Partial | Fail | Skip |
|-------|------|---------|------|------|
| **Harness H1–H5** | H1, H2, H3, H4, H5 | — | — | — |
| **River R1–R5** | R1, R2, R3 | — | R4, R5 | — |
| **Flow F1–F3** | — | — | — | Not run (Shelter separate) |
| **Negative X*** | — | — | — | Not exercised this thread |

**Verdict:** **Harness split (read vs cache) is accepted** for native eddies on split-bot Mini. **Lifecycle bar on River in split-bot mode is not accepted** — checkpoint/release operate on the wrong history surface and release copy over-claims.

---

## Harness scenarios (H*)

### H1 — URL + question → informed reply without Fetch click ✅

**Input:** ScienceAlert mini-universe URL + “what’s the news here?”  
**Evidence:** Link-read embed **4,624 chars**; Turtle entropy/BEC reply without disclaimer.  
**Log:** `Turtle inbound` → `Native Turtle reply sent` (857 chars).

### H2 — Save offer after informed reply ✅

**Evidence:** River `-# Save to library` row after Turtle reply.  
**Log:** `Save offer scheduled` → skip on cached mini-universe URL (correct for H2/H3 on *second* URL test); fresh Mars run: `Save offer posted`.

### H3 — Tap Save → cache + act digest ✅

**Input:** Mars meteorite URL (after Turtle restart + spirit retry).  
**Evidence:**
- Distill embed with bullet summary; footer *Distilled via article • cached in link-resonance/*
- `17:46 Act !fetch via button`
- File `link-resonance/33ff662e52dc843d.md` (hash of Mars URL)

**Note:** ~4 min defer/typing during HTTP fetch + Ollama distill — no progress copy (UX gap, not functional fail).

### H4 — Follow-up cites content ✅

**Evidence:** Mars reply discussed garnet/andradite/NWA 8171 from read content; no “I can’t fetch” disclaimer.

### H5 — Typed `!fetch` on River ✅

**Evidence:** Earlier session `River act [!fetch] in #river` — lifecycle bar unchanged in eddy.

---

## River + lifecycle scenarios (R*)

### R1 — River bar last after practitioner post ✅

**Evidence:** Dogfood post in `#river`; bar reposted (earlier in session).

### R2 — New eddy ✅

**Evidence:** `River eddy materialized: new eddy`; standing bar below.

### R3 — First message rename + Turtle join ✅

**Evidence:** `Eddy renamed` → `physics lab mini universe experiment time test`; `River added Turtle`; H1 processed.

### R4 — Lifecycle Checkpoint ❌ (split-bot)

| Attempt | Message | Root cause |
|---------|---------|------------|
| After H1 (~17:21, Turtle bar) | *Checkpoint ran — nothing new met the save threshold* | Turtle history: 1 exchange; reflection needs 4; no flow write |
| After H3 (~17:52, River bar) | *Not enough conversation to checkpoint yet* | River `dialogue_histories`: act digests only (~1 entry); gate `< MIN_EXCHANGES_FOR_CHECKPOINT` |

**Practitioner experience:** Rich thread dialogue; both messages deny capture. **Fail** vs acceptance criterion “checkpoint keeps history and saves resonance.”

### R5 — Release ❌ (split-bot + copy bug)

**Input:** Release button after failed checkpoint.  
**Evidence:** *Closing session…* → green **Session Released** — *Session note written. Conversation history cleared.*

**Reality:**
- **No** new file under `desk/sessions/` at 17:52 (latest remains `2026-06-20-2.md` from 17:27 idle on mini-universe only).
- `cmd_release` embed text is **hardcoded** — does not inspect `CheckpointResult` (`cmd_sessions.py` L68–69).
- River cleared **River** `dialogue_histories`; Turtle in-memory history may persist until next turn.

**Fail** vs “same semantics as `!checkpoint` / `!release` with honest outcomes.”

---

## UX gaps (non-blocking for harness accept; blocking for lifecycle accept)

1. **Split-bot lifecycle history** — River runs `cmd_checkpoint` / `cmd_release` against River `dialogue_histories`; Turtle owns prose + link-read history. Two processes, no shared capture surface.
2. **Duplicate lifecycle bars** — Turtle `ensure_channel_bars` uses unlogged `river_client` in Turtle process → posts/reposts bar as **Turtle**; River also posts bar → two Checkpoint/Release/Dissolve rows.
3. **Fetch progress** — `interaction.response.defer()` + `channel.typing()` only; long distill feels hung.
4. **Checkpoint copy** — *nothing new met the save threshold* / *not enough conversation* do not explain split-bot or reflection thresholds.
5. **Turtle wedge** — Event loop stopped logging/processing after idle checkpoint (~15 min); requires restart. Separate reliability chapter; blocked Mars message at 17:22.

---

## Negative scenarios (not run; no regressions observed)

- **X1** — No Turtle prose in parent river channel this session.
- **X2** — No Fetch-before-discuss on native eddy.
- **X3** — No duplicate Fetch from Turtle prose.
- **X4** — No auto-dissolve.

---

## Verification crosswalk

| Layer | Result |
|-------|--------|
| `python -m unittest discover -s tests` | Green pre-deploy (8/8 canary) |
| `shake_link_read.py` | Green at deploy |
| Mini `river.log` / `discord.log` | H2/H3 grep: `Save offer posted`, `Seneschal row posted` |
| Practitioner Discord | Screenshots 2026-06-20 17:42–17:53 |

---

## Next chapter — Split-bot lifecycle capture

**Title (proposed):** `2026-06-21-split-bot-lifecycle-capture.md`  
**Spec:** §8.4 checkpoint/release; §5.8 identity  
**Goal:** Lifecycle buttons on River call capture against **authoritative dialogue history**, not River act digests alone.

### Proposed fixes (ordered)

1. **Shared history for capture** — On lifecycle act in split-bot mode, load history from Turtle process (file snapshot written each turn, or reload from Discord thread via Turtle client, or IPC). Minimum: merge Turtle `dialogue_histories` path under `runtime/dialogue/` both processes read.
2. **Honest release embed** — `cmd_release` reports what `checkpoint_session` actually wrote (`session_note`, `flow_writes`, or “nothing captured”).
3. **Bar identity** — Turtle process must not post lifecycle bar when `river_bot_enabled()`; only River `get_lifecycle_bar_client` with logged-in client (`bar_anchor.py` / `channel_for_client` guard).
4. **Fetch progress** — Ephemeral “Distilling…” after defer, or act digest before long Ollama call.
5. **Reliability** — Investigate post-idle wedge (ensure_channel_bars / session_monitor deadlock); out of lifecycle scope but filed from this dogfood.

### Acceptance re-run (after fix)

- R4: checkpoint after ≥2 practitioner turns writes session note or honest “below reflection threshold” with reason.
- R5: release after Mars+H1 thread writes session note including both topics, or embed says no note captured.
- Single lifecycle bar, River-authored.

---

## Harvest

- **Accepted:** Harness split read (Turtle) vs cache (River) on native split-bot Mini — core Acceptance goal met.
- **Rejected for v1 sign-off:** Lifecycle bar semantics in split-bot until history capture is fixed.
- **Operator workaround:** Typed `!checkpoint` / `!release` on Turtle (single-bot fallback) or restart Turtle if eddy goes deaf after long idle.
- **Doc sovereignty chapter** remains queued post-Acceptance (matrix row: `docs/architecture.md`, Magic `library/resonance/turtle/` bundle).

---

*Dogfood: Kermit + Spirit, 2026-06-20. Mini thread `1517909441817739345`.*
