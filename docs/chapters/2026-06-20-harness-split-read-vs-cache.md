# Chapter proposal — Harness split: read (Turtle) vs cache (River)

**Date:** 2026-06-20  
**Status:** Architecture locked — implementation next  
**Deciders:** Kermit + Spirit (Forge)  
**Builds on:** `2026-06-20-river-turtle-split-handoff.md`, `09bcbc0` (River pre-fetch seneschal — to be superseded)

---

## Problem

Split-bot identity (River + Turtle) still blurs **conversation** and **platform** when URL handling routes through River `!fetch` before Turtle can speak informed prose. Practitioners experience one bot misbehaving: disclaimers, duplicate buttons, fetch-as-prerequisite for dialogue.

**Root cause:** two different jobs named “fetch”:

| Job | Who should own it | Durability |
|-----|-------------------|------------|
| Read URL so the *next reply* is informed | **Turtle harness** | Ephemeral (turn / session context) |
| Distill + save to practice library | **River harness** | Durable (`link-resonance/`) |

Native eddies currently disable Turtle link-read (`plan_dialogue_urls` → `native_eddy=True` → no auto-fetch) and substitute River pre-fetch buttons — the wrong seam.

---

## Architecture lock

### River harness → turtleOS operations

Structured platform acts: instant, state-changing or state-surfacing, not conversational prose.

**Includes:** lifecycle (checkpoint / release / dissolve), flow materialization, bars, typed `!`, practice-root browse (`!read` / `!ls` / `!search`), diagnose/admin, **`!fetch` as “save to library”** (opt-in persistence).

**River seneschal (v2):** scan thread *after* Turtle replies; offer **Save to library** (`!fetch`) when a URL was discussed and is not yet cached — not before dialogue.

### Turtle harness → conversation-enabling operations

Silent or low-friction ops that **inform the next Turtle turn** without being turtleOS acts on the timeline.

**Includes:**

- **Silent link-read** when practitioner message contains external URL(s) (same heuristics as legacy auto-fetch: URL-primary, short commentary, read cues)
- Attachment preprocessing
- Flow front-matter `reads:` / flow state injection
- Ephemeral context injects (forwarded messages, link-read followup `[Fetched content]`, large spill → `box/intake/` for the turn)
- Optional `-# Sources:` trace (transparency, not an act)

**Excludes:** posting act rows, parsing Turtle prose for buttons, `!fetch` cache/distill, thread archive, lifecycle mutations.

### Shared codebase

One repo (`~/turtleos/`), two Discord clients when `RIVER_BOT_TOKEN` is set. Shared modules (`commands.py`, `link_read.py`, `bar_anchor.py`, …) are libraries; **harness** = which entrypoint runs which ops on which message class.

---

## Target flow (native eddy)

```
Practitioner posts URL
    → Turtle harness: silent link-read → inject excerpt into dialogue history
    → Turtle: informed reply (no “I can’t fetch”)
    → River harness (optional): if URL uncached in link-resonance/, post “Save to library” button
    → Practitioner taps Save (or types !fetch) → River caches + embed; act digest for continuity
```

**Not:**

```
Practitioner posts URL → River Fetch button → must click before Turtle can discuss  ✗
Turtle prose mentions !fetch → River parses backticks → duplicate buttons       ✗
```

---

## Implementation slices

### Slice 1 — Restore Turtle read (conversation) ✅ *2026-06-20*

- **`link_read.plan_dialogue_urls`:** native eddies use same auto-fetch heuristics as legacy.
- **Removed** `river_eddy_seneschal.maybe_offer_eddy_fetch` on practitioner URL post.
- **Prompts:** Turtle assumes content available when link-read ran; no River prerequisite for discussion.
- **Acceptance:** URL in eddy → Turtle first reply cites/substantively engages content → no Fetch button required.

### Slice 2 — River save-offer (platform) ✅ *2026-06-20*

- **New:** post-Turtle scan for external URLs in practitioner input; if not in `link-resonance/`, one **Save to library** act row (River-owned). **Must run in `river_bot.py`** — Turtle process cannot post via disconnected `river_client`.
- **`!fetch` semantics** documented in `turtle-talk.md`: persistence act, not dialogue prerequisite.
- **Acceptance:** after informed reply, optional Save button; tap → cached; second Save suppressed; typed `!fetch` still works.

### Slice 3 — Spec + inventory alignment

- **`docs/turtle-talk.md`:** eddy core `!fetch` = cache/distill; link-read = Turtle path (not a `!` command).
- **`TURTLE_SPEC` §5.8 / §8.4 cross-ref** when spec edit window opens.
- **`prompts.py`:** remove stale “River attaches Fetch when you post URL” native hints.

---

## Acceptance (full chapter)

1. New eddy, paste article URL with short comment  
2. Turtle responds informed **without** any button click  
3. River may offer **Save to library** once (not on every message)  
4. Follow-up questions cite content; no duplicate Save; no disclaimers  
5. Lifecycle bar unchanged; typed `!fetch` on River still caches  

---

## Non-goals (this chapter)

- River model classifying all seneschal acts from thread (future)  
- Single-bot dual-voice rollback  
- Auto-fetch on every URL regardless of commentary length (keep incidental Read/Skip or legacy heuristics)  
- Magic-overlay boom/compass `!` restoration  

---

## Code touch map

| Area | Change |
|------|--------|
| `link_read.py` | `plan_dialogue_urls` native branch |
| `discord_bot.py` | `handle_dialogue` URL path (unchanged structure, native auto_fetch true) |
| `river_eddy_seneschal.py` | Remove pre-fetch; add post-Turtle save-offer (Slice 2) |
| `river_bot.py` | Drop practitioner-URL hook or repurpose for post-turn hook via shared state |
| `commands.py` | `fetch_act_digest` / `!fetch` docs only unless save-offer needs cache probe helper |
| `prompts.py` | Native eddy link + act copy |

---

## Relation to prior commits

- **`9d91fa1`** fetch act digest + seneschal filter — keep digest on explicit `!fetch`; good for post-save continuity.  
- **`09bcbc0`** River pre-fetch on URL — **revert behavior** in Slice 1; keep module for Slice 2 save-offer pattern (`post_act_suggestion_row`).

---

*Operations vs conversation: Turtle reads to talk; River saves to keep.*
