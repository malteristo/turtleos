# Chapter — Discord permalink self-feed (Turtle harness)

**Date:** 2026-06-20  
**Status:** Slice 1 shipped (2026-06-24) · Slices 2–4 pending  
**Deciders:** Kermit + Spirit (Forge)  
**Priority:** Tier 0 · acceptance **D2**, **D2b** · [priority-stack.md](../priority-stack.md)  
**Builds on:** `2026-06-20-harness-split-read-vs-cache.md` (web link-read), existing `_fetch_discord_message_context` in `discord_bot.py`

---

## Problem

Practitioners cross-pollinate eddies by pasting **Discord thread or message permalinks** — the same move as dropping an article URL, but turtleOS treats them differently today:

| Path | Today | Practitioner experience |
|------|--------|-------------------------|
| **External URL** | Turtle **link-read**: visible embed trace, heuristics, inject → informed reply | Modern-agent feel (H1) |
| **Discord permalink** | Raw API dereference → `[Dereferenced Discord context]` block, **no** link-read UX | Opaque; single-message fetch; no thread summary; inconsistent with web |

**North-star decision:** Turtle **self-feeds** Discord links (parity with web). **River does not** pre-digest Discord URLs — same split as read-for-dialogue vs `!fetch` for the web.

**Compose with Discord:** Human uses search + permalinks; Turtle gets scaffolding because it cannot run Discord search.

---

## Target behavior

```
Practitioner pastes Discord permalink (+ short ask) in eddy A
  → Turtle harness: detect discord.com/channels/… URL(s)
  → Visible trace on timeline (Reading… → Read — mirror web link-read tone)
  → Fetch: message and/or thread history via bot API
  → Optional: qwen (river/fast model) summarizes long threads before inject
  → Inject transparent block into dialogue history (label visible to practitioner)
  → Turtle: informed reply; practitioner can say “read the whole thread” if thin
```

**Not:**

```
Practitioner pastes Discord URL → River summarizes → Turtle speaks          ✗
Silent dereference with no timeline trace                                   ✗
Must click a button before Turtle can discuss                               ✗
```

---

## Scope

### In scope (v1)

1. **Message permalinks** — `…/channels/{guild}/{channel}/{message_id}` (existing regex + fetch path).
2. **Thread context** — when link targets a thread, fetch enough history for cross-eddy reference (bounded: last N messages or char cap — same discipline as web spill).
3. **Visible trace** — status embed or equivalent (reuse `link_read` embed colors/pattern; new label e.g. “Read Discord thread · 12 messages · 4.2k in context”).
4. **Transparent inject** — practitioner sees what Turtle received (summary + pointer to full thread on Discord).
5. **Turtle harness only** — no River pre-fetch; Save-to-library remains separate (web `!fetch` / H2–H3).
6. **Acceptance D2 / D2b** — dogfood pass criteria in [acceptance/README.md](../acceptance/README.md).

### Out of scope (v1)

- River-side Discord digest (rejected for consistency).
- Replacing Discord search UI for humans.
- Writing `link-resonance/` on dialogue read (same as web).
- Standing eddy lifecycle bar (contextual River offers = separate chapter D3).

### Open (Mage decision during slice)

- **Summary model:** qwen river model for long-thread compress vs inject raw history up to cap.
- **Thread-only URLs** without message id — extend URL parser if needed.
- **Cross-guild** links — fail gracefully with clear embed.

---

## Existing code (starting point)

| Artifact | Role |
|----------|------|
| `discord_bot.py` → `_DISCORD_MESSAGE_LINK_RE`, `_extract_discord_message_refs`, `_fetch_discord_message_context` | Message-level dereference already in `handle_dialogue` |
| `link_read.py` | External URL pipeline — **pattern to mirror** (FetchResult, embeds, inject limits) |
| `craft_intake.py` | Also uses dereference — keep behavior aligned |
| `docs/ux/link-reading.md` | UX principles — extend with Discord permalink section |

**Gap:** dereference is silent-ish, single-message biased, no thread-history policy, no link-read embed parity.

---

## Architecture

### Same harness split as web

| Job | Owner |
|-----|--------|
| Read Discord permalink so **next Turtle reply** is informed | **Turtle** (`discord_bot` / new `discord_ref_read.py`) |
| Save distilled URL to library | **River** (`!fetch`) — web only today |

### Module sketch

```
discord_ref_read.py   # detect, fetch thread/message, optional summarize, FetchResult-like struct
link_read.py          # shared embed helpers or import discord_ref_read outcomes into dialogue plan
discord_bot.py        # plan_dialogue: external URLs + discord refs in one self-feed pass
```

**Inject label (proposed):** `[Discord context]` or `[Read Discord thread]` — distinct from `[Fetched content]` (web) so practitioners and tests can tell them apart.

### Long thread policy (initial)

| Size | Behavior |
|------|----------|
| ≤ inline cap (~8k) | Inject raw formatted thread excerpt |
| > inline cap | qwen summary + “N messages · full thread on Discord” + optional spill file under practice root if web spill pattern applies |

Mirror web: honest N/M in context on embed.

---

## Implementation slices

### Slice 1 — Parity trace + message permalink (MVP) — **Done**

- Wrap existing dereference in **visible embed** (Reading → Read / fail ladder).
- Ensure D2 message-link dogfood passes with **specific citation** in Turtle reply.
- Unit tests: parse, inject shape, embed text.

**Acceptance:** D2 on Mini (dogfood pending).

### Slice 2 — Thread history fetch

- Given thread id, fetch last N messages (bot permissions, rate limits).
- Apply char cap + inject policy.
- **Acceptance:** D2b.

### Slice 3 — Optional qwen summary for long threads

- When history > cap, summarize with `RIVER_MODEL` / qwen before inject.
- Practitioner-visible summary in embed; expand-on-request via follow-up message.

### Slice 4 — Docs + shake

- `docs/ux/link-reading.md` — Discord permalink subsection.
- `TURTLE_SPEC.md` §9.5 amendment (sanction) — Discord read-for-dialogue alongside external URLs.
- `scripts/shake_discord_ref.py` or extend `shake_link_read.py`.

---

## Verification

**Offline:**

```bash
python3 -m unittest tests.test_discord_ref_read -q   # to add
python3 -m unittest tests.test_link_read -q
```

**Live (Mini):**

1. Copy message permalink from eddy B → paste in eddy A with “remind me what we said about X” → D2.
2. Copy thread link from 10+ message eddy → paste in eddy A → D2b.
3. Confirm no River digest before Turtle reply; optional Save to library still web-only.

Artifact: `test-runs/shake-discord-ref-latest.json`

---

## Risks

| Risk | Mitigation |
|------|------------|
| Bot lacks permission to read linked channel/thread | Fail embed + paste hint |
| Rate limits on history fetch | Cap N messages; backoff |
| Summary drops nuance | Transparent inject; practitioner can demand full thread |
| Duplicates web + discord fetch on same message | Single plan pass; dedupe URLs |

---

## Traceability

| Artifact | Action |
|----------|--------|
| [acceptance/README.md](../acceptance/README.md) | D2, D2b rows |
| [priority-stack.md](../priority-stack.md) | Tier 0 Discord permalink row |
| `discord_bot.py` | Replace silent dereference with traced self-feed |
| `link_read.py` / new module | Shared embed + inject discipline |
| `prompts.py` | Turtle assumes Discord context available when trace succeeded |
| `TURTLE_SPEC.md` §9.5 | Amend after slice 1 dogfood (Mage sanction) |

---

## Summary

**Discord permalinks are link-read for the graph you already live in.** Reuse Turtle self-feed, visible trace, and honest inject — not River digest. Existing dereference code is a wedge, not the finished product. Ship Slice 1 for D2, then thread history for D2b.

**Next chapter (related, not this file):** contextual River bar (D3) — separate doc when scoped.
