# Proposal: Eddy Link Reading (URL → context, with feedback)

**Date:** 2026-06-18  
**Spec reference:** TURTLE_SPEC §16 (Link Fetching / Content Reach), §6 (Inline Transparency), §8.2 (During Session)  
**Status:** Approved — Slices 1–5 shipped (2026-06-18)  
**Origin:** Mage dogfood + vortex comparison + Hermes/OSS harness survey

---

## Problem

Practitioners drop article URLs in eddy chat expecting modern-agent behavior: Turtle reads the page and responds with awareness of its contents. turtleOS **already fetches** in `handle_dialogue`, but the experience is broken:

1. **No visible progress** — fetch runs before `typing()`; multi-second pauses feel like Turtle hung.
2. **No outcome signal** — success/failure/LITL only appear inside model context, not on the timeline.
3. **Truncation is invisible** — `process_urls` caps at ~8k chars injected, ~6k in history; long articles silently clip.
4. **Two modes conflated** — auto-read-for-dialogue vs `!fetch` resonance-cache serve different jobs but share no UX language.
5. **Dead button path** — `LinkFetchView` never shows when auto-fetch runs (`_urls_already_processed = True`).

The vortex prototype got closer on **feedback** (seed embed “Linked content”, confirmation line) but lived on a deprecated intake path, not native v1 eddies.

**Goal:** Comparable to Hermes / Cursor / ChatGPT link reading — **with Discord-native affordances**, split-bot constraints, and turtleOS LITL honesty — without requiring cloud Tool Gateway or full browser automation in v1.

---

## Benchmark: how OSS harnesses do it

### Hermes Agent ([docs](https://hermes-agent.nousresearch.com/docs/user-guide/features/web-search))

| Layer | Tool | When | Practitioner sees |
|-------|------|------|-------------------|
| Fast read | `web_search` | Discovery | Tool progress in stream: `🔍 query` |
| Fast read | `web_extract` | Known URL, static/readable page | Progress → markdown extract (size-tiered) |
| Deep read | `browser_*` | JS forms, login, interaction | Browser session; slower, costlier |

**Size policy (`web_extract`):**

- &lt; 5k chars → full markdown to agent  
- 5k–500k → auxiliary LLM summary (~5k out)  
- 500k–2M → chunked summarize  
- &gt; 2M → refuse, suggest narrower URL  

**UX pattern:** Tool execution is **visible but not conversational** — SSE events `hermes.tool.progress`, `tool.started` / `tool.completed`; emoji + key arg inline; **does not pollute** final assistant text. Open WebUI shows brief indicators before the answer streams.

**Security:** SSRF guards on fetch paths; redirect re-validation (skills hub hardening — same class of concern for any URL fetcher).

**Discord note:** Hermes Tool Gateway is substrate-agnostic (“every interface benefits”); Turtle must **adapt** progress events to **embed edits**, not SSE.

### Cursor / ChatGPT (product reference)

- URL in message → implicit fetch or `@web` → status chip (“Reading…”) → answer grounded in page.  
- Failure → honest “couldn’t access” + alternatives.  
- User does not need to know tool names.

### turtleOS vortex (internal prototype)

- `process_urls()` **before** spawn/route in `handle_intake_message`.  
- Fetched text in seed embed (2k preview) + Turtle opening context (6k).  
- Practitioner sees linked content in embed — **good feedback**, wrong lifecycle for v1 bar → eddy path.

### turtleOS today

| Path | Behavior | UX |
|------|----------|-----|
| Auto in `handle_dialogue` | `process_urls` → `[Fetched content]` in history | Silent |
| `!fetch` | Distill → cache in `link-resonance/` → summary embed | Explicit, manual |
| `/paste` (intake_server) | Full text → `box/intake/` → vortex embed | Web form, not chat |
| Boom thread | Fetch + distill + **always feedback** | Good model for status messages |

**Existing stack to keep:** `content_fetch.py` layered fetch (direct → Jina → Wayback; Twitter/YouTube/Reddit CLI paths), LITL check, paste fallback URL builder.

---

## Design principles

1. **Read for dialogue ≠ save resonance** — Auto path injects **readable extract** for the current turn thread; `!fetch` remains opt-in **distill + cache** for library use (per `on_universal_link_fetching.md`).

2. **Acts, not words (River); operations, not chat (Turtle)** — Progress is a **status embed** (edited in place), not Turtle explaining “I am now fetching…”.

3. **Honest trace** — Practitioner sees: URL, method (`trafilatura` / `jina` / `youtube transcript`), char count, truncation/file spill, LITL flag, failure attempts chain.

4. **Latency visibility** — `typing()` during fetch **and** during LLM reply.

5. **Hybrid trigger** — Auto when the message is **URL-primary**; opt-in button when URL is incidental (Hermes: agent chooses tool; we use lightweight heuristics instead).

6. **Split-bot** — All fetch + inject happens in **Turtle process** (`discord_bot.py`). River never fetches page content.

7. **LITL** — Flag suspicious patterns; still pass content to model with warning block (existing behavior); surface warning on status embed.

8. **Degrade gracefully** — Every failure offers the same ladder: retry `--fresh`, `/paste` link, screenshot, paste in chat (short), `!fetch` for distill-only.

---

## Practitioner UX (v1 target)

### A. URL-primary message (auto-read)

**Heuristic (initial):** External URL present AND (message is only URL + whitespace OR non-URL text ≤ 120 chars OR message starts with “read”, “what do you think”, “summarize”, etc.). Tune in dogfood.

```
Practitioner: https://example.com/long-article
              what’s the argument here?

Turtle timeline:
  [status embed — grey/purple, silent]
  🔗 Reading example.com…

  [embed edits]
  🔗 Read example.com · 4,812 words · trafilatura · full text in context

  [typing]
  Turtle: [reply grounded in article]
```

**On failure:**

```
  🔗 Couldn’t read example.com
  Tried: direct: HTTP 403 → jina: timeout → wayback: not archived
  Paste full text: <paste URL>  ·  or  !fetch <url>
```

**On LITL hit:**

```
  🔗 Read example.com · 2,100 words · jina · ⚠️ instruction-like patterns flagged
```

**On truncation / file spill (&gt; 8k):**

```
  🔗 Read example.com · 18,400 words · trafilatura
  Full text: box/intake/20260618-example-com.md · 6,000 chars in prompt
```

### B. URL incidental (opt-in)

Long message with a link buried mid-paragraph → **no auto-fetch** (avoids surprise 20s delay).

```
  [small embed under practitioner message]
  🔗 Link detected: example.com
  [Read article]   [Skip]
```

- **Read article** → same pipeline as A (status embed → inject → Turtle reply on **next** turn OR same turn if we defer LLM until click — **recommend same-turn**: button defer → fetch → continue `handle_dialogue`).  
- **Skip** → dismiss embed; Turtle responds without fetch.

Retire or repurpose broken `LinkFetchView` (`fetch:{i}:{hash}`) to this slimmer **Read article** pattern with stable custom_ids including thread_id.

### C. Explicit `!fetch` (unchanged role)

Manual distill + cache + resonance embed. Not replaced. Status copy should cross-link: “Saved resonance — for discussion, drop the URL in chat or use Read article.”

### D. Commands teach buttons

Footer on opt-in embed: `` `!fetch https://…` `` for copy-paste (existing lore principle).

---

## Technical architecture

### New: structured fetch result

Extend `content_fetch.py` with a result type (dataclass or TypedDict):

```python
@dataclass
class FetchResult:
    url: str
    ok: bool
    content: str | None          # extracted markdown/text
    source: str | None             # trafilatura | jina | wayback | youtube | …
    attempts: list[str]            # failure chain
    char_count: int
    litl_hits: list[str]
    title: str | None              # best-effort from HTML/metadata
    artifact_path: str | None      # practice-relative path if spilled to file
    prompt_excerpt_chars: int      # how much went into prompt
```

Refactor `process_urls` → `fetch_urls_for_dialogue(urls) -> list[FetchResult]` while keeping string output for backward compatibility during migration.

### Pipeline (Turtle `handle_dialogue`)

```
1. Parse URLs from visible_content
2. Classify auto vs opt-in (heuristic)
3. If opt-in: post LinkOfferView; return early OR mark pending_fetch on message id
4. If auto (or Read clicked):
   a. Post status embed → status_message_id
   b. async with channel.typing():
        results = await fetch_urls_for_dialogue(urls)
   c. For each result:
        - LITL check (existing)
        - If len(content) > PROMPT_INLINE_MAX (8_000): write box/intake/{ts}-{slug}.md, inject excerpt + path
        - Else: inject full content
   d. Edit status embed with outcome summary
5. Append [Fetched content] to history (existing shape, richer header)
6. Continue LLM call (typing already on or second typing block)
```

**Constants (initial):**

| Constant | Value | Notes |
|----------|-------|-------|
| `PROMPT_INLINE_MAX` | 8_000 | Matches current `process_urls` slice |
| `HISTORY_INLINE_MAX` | 6_000 | Matches current history append |
| `AUTO_URL_COMMENTARY_MAX` | 120 | Chars of non-URL text for auto trigger |
| `MAX_URLS_PER_MESSAGE` | 3 | Existing |

### Hermes-inspired size policy (dialogue path)

Different from Hermes: we **prefer full text in file + generous excerpt** over silent LLM summarization for dialogue — practitioner is asking *about this article*, not for a card catalog entry.

| Size | Dialogue behavior |
|------|-------------------|
| ≤ 8k | Inline in prompt |
| 8k – 100k | Write `box/intake/`, inject first 6k + path + “full text on disk” |
| &gt; 100k | Same + note “very long — ask Turtle to search the file or focus on a section” |
| Fetch fail | No LLM pretend-read; status embed + paste ladder |

**v1.1 optional:** auxiliary Qwen pass for &gt;50k (Hermes-style) when Mage enables `link_read.summarize_long: true` in registry — not v1 default.

### Status embed module

New small module or functions in `content_fetch.py` / `link_read_ui.py`:

- `post_fetch_status(thread, url) -> Message`  
- `edit_fetch_status(message, FetchResult)`  
- Color: neutral (`0x5865F2`) in progress, green (`0x57F287`) success, amber fail, amber+warning LITL  

Embed edits are the Discord equivalent of Hermes `tool.started` / `tool.completed`.

### Interaction with flows

- **Navigator after Begin:** URL in first practitioner message → same pipeline; intake file + fetched article both in prompt (distinct sections).  
- **Skip path:** First message triggers rename + Turtle join via River; second message onward is Turtle — fetch on any Turtle-handled message.  
- **River:** No change.

### Caching

- **Do not** auto-write `link-resonance/` on dialogue fetch (that’s `!fetch`).  
- **Do** optional in-memory session cache keyed by `(thread_id, url_hash)` for “Read article” re-clicks within 1h to avoid refetch.  

### Security (v1 checklist)

- [ ] Block private IP / localhost / link-local URLs (SSRF) — **gap today**; Hermes-level hardening in same slice or fast follow.  
- [ ] Cap redirect hops in httpx  
- [ ] LITL (existing)  
- [ ] No auto-fetch of `file://`, `discord://`, attachment URLs  

---

## Out of scope (v1)

| Capability | Reference | turtleOS stance |
|------------|-----------|-----------------|
| Full browser automation | Hermes `browser_*` | Defer; Jina layer covers many JS sites |
| `web_search` | Hermes discovery | Separate feature; not link-reading |
| Cloud Firecrawl gateway | Hermes Tool Gateway | Optional backend later; keep self-hosted stack default |
| River fetching | — | Never |
| Auto-fetch every URL in every message | — | Incidental-link heuristic prevents pain |

---

## Implementation slices

### Slice 1 — Feedback + typing (MVP)

- `FetchResult` + status embed post/edit  
- Auto URL-primary heuristic  
- Move fetch inside `typing()` block (or nested typing)  
- Wire outcomes to embed  
- Fix/remove dead `LinkFetchView` post at end of `handle_dialogue`  
- Tests: unit tests for heuristic + result formatting; shake script drops URL in test eddy  

**Acceptance:** Drop `https://example.com` in fresh Navigator eddy → see Reading → Read → Turtle cites content within 30s.

### Slice 2 — Opt-in button

- `LinkOfferView` with Read / Skip  
- Incidental URL messages skip auto-fetch  
- Stable persistent custom_ids  

### Slice 3 — File spill

- &gt;8k → `box/intake/` artifact  
- Status embed shows path  
- Prompt gets excerpt + pointer  

### Slice 4 — Docs + spec ✅

- `docs/ux/link-reading.md` — link reading principles + journey
- `docs/ux/README.md` — UX index  
- TURTLE_SPEC §9.5 + Law of Visible Link Read + §7.6 embed trace  
- `docs/native-harness.md` acceptance lines aligned  
- `scripts/shake_link_read.py` + `test-runs/shake-link-read-latest.json`  
- `commands.py` — `!fetch` copy distinguishes distill vs dialogue read; removed dead `LinkFetchView`  

### Slice 5 — SSRF hardening ✅

- `url_validate.py` — shared validator (scheme, private/loopback/link-local IPs, metadata, numeric aliases, redirect hook)
- Wired into `link_read`, `content_fetch.fetch_url_content`, `!fetch`, httpx clients with redirects
- `tests/test_url_validate.py`

---

## Shake / test plan

**Offline:**

```bash
python3 -m unittest tests.test_link_read -q   # new: heuristic, FetchResult format, SSRF validator
```

**Live (Mini):**

1. Spawn blank eddy or Navigator after Begin  
2. Send URL-only message (known good static page)  
3. Assert status embed transitions Reading → Read with char count  
4. Assert Turtle reply references page-specific phrase  
5. Send 404 URL → failure embed + paste hint  
6. Send long message with URL at end → opt-in embed only (slice 2)  

Artifact: `test-runs/shake-link-read-latest.json`

---

## Open questions for Mage

1. **Auto heuristic strictness** — URL-only auto-read feels right; should “Here’s an article: URL” (short preamble) always auto-read? (Proposal: yes if ≤120 chars non-URL text.)

2. **Same-turn vs next-turn on Read button** — Same-turn (fetch then answer) matches Cursor; next-turn is simpler. **Recommend same-turn.**

3. **Summarize long pages?** — Hermes summarizes &gt;5k; we spill to file. OK for v1, or want optional summarize for dialogue?

4. **Visible in native eddy replies?** — One-line footer on Turtle reply: “Read: example.com (4.8k)” — or embed-only trace? **Recommend embed-only** (native voice integrity).

5. **Commit path** — Implement in `turtleos` main after slice 1 dogfood?

---

## Traceability

| Artifact | Action |
|----------|--------|
| TURTLE_SPEC §16 | Add visible fetch trace requirement for eddy dialogue |
| `docs/ux/link-reading.md` | Link reading principles, patterns, journey |
| `content_fetch.py` | `FetchResult`, SSRF (slice 5) |
| `discord_bot.py` | Pipeline reorder, status embeds |
| `commands.py` | Align `!fetch` footer copy with Read path |
| `on_universal_link_fetching.md` (magic lore) | Update §VI auto-detect to match v1 UX (when sanctioned) |

---

## Summary

**Transfer cost from vortex: low** — same `process_urls` engine, new **Hermes-inspired visibility layer** adapted for Discord embeds instead of SSE tool progress. **Comparable experience:** paste URL → see reading progress → grounded answer → honest failure ladder. **Differentiator:** practice-integrated file spill (`box/intake/`), LITL surfacing, split-bot discipline, no cloud gateway required.

Recommended start: **Slice 1** after Mage signs off on heuristics and embed-only trace.
