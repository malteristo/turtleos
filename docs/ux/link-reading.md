# Eddy link reading

How practitioners share URLs in eddy dialogue and how the shell makes fetch legible.

**Spec:** TURTLE_SPEC §9.5 · Law of Visible Link Read (§17)  
**Implementation:** `link_read.py`, `content_fetch.py`, `discord_bot.handle_dialogue`  
**Shakedown:** `scripts/shake_link_read.py`

---

## Principles

### Two jobs, two modes

| Mode | Trigger | Purpose | Cache |
|------|---------|---------|-------|
| **Read for dialogue** | URL in eddy chat (auto or Read button) | Ground the **current turn** | No `link-resonance/` write |
| **Distill for library** | `!fetch <url>` | Save curated resonance for later | Yes — `link-resonance/` |

Practitioners should never wonder whether dropping a link **saved** something to their library. Dialogue read is ephemeral context; `!fetch` is explicit archival.

### Timeline owns the trace

Fetch progress and outcomes appear as **silent embeds** on the eddy timeline — Reading… → Read (or failure / opt-in). Turtle does **not** narrate fetch mechanics in conversational voice (“I’m fetching that now…”). The practitioner sees trace before and alongside the answer.

### URL-primary auto, incidental opt-in

**Auto-read** when the message is URL-primary:

- URL only
- ≤120 characters of non-URL commentary
- Explicit read/summarize cues (“read this”, “what’s the argument here?”)

**Incidental links** (long message + buried URL): **no auto-fetch on the first turn**. Shell posts **Read article / Skip** after Turtle’s first reply; Read triggers a follow-up turn with fetch.

Consent extends inside eddies — same spirit as [principles.md](principles.md) (consent before spawn).

### Honest partial read

Long pages spill to `box/intake/`; only an excerpt (default 8k chars) enters turn context. The status embed shows **N / M in context** *before* Turtle replies — not as an apology buried in the answer.

### River names threads

In split-bot mode, **River owns eddy titles** (`generate_topic`, flow materialize rename). Link-read must **not** rename practitioner- or flow-chosen names. Single-bot fallback may rename only blank eddies (`new eddy`, `blank eddy`) or bare host slugs.

### Same failure ladder everywhere

Every failure offers the same path: retry, `/paste` endpoint, screenshot, paste in chat, `!fetch` for distill-only. Copy stays consistent across status embed, dialogue inject, and `!fetch` help text.

### SSRF guardrails

Outbound fetches validate URLs before retrieval — block private/loopback/link-local targets, metadata endpoints, non-http(s) schemes, and unsafe redirect targets. Failures surface as `SSRF blocked: …` in embeds or `!fetch` replies.

---

## Patterns

### URL-primary message

| Step | Timeline |
|------|----------|
| Detect | External URL in message (not discord.com message links) |
| Status | Silent embed: **Reading…** → **Read {host} · N/M in context** (+ `box/intake/` when spilled) |
| Fetch | During `typing()` — layered extract via `content_fetch` / `link_read` |
| Reply | Turtle turn includes excerpt in context; embed-only trace |

### Long articles (>8k)

Full text saved to `box/intake/{timestamp}-{slug}.md`. Status embed shows ratio (e.g. **8,000 / 29,830 in context**) and spill path before Turtle speaks.

### Incidental link

| Step | Timeline |
|------|----------|
| First turn | Turtle replies to the message **without** fetch |
| After reply | **Link detected** embed — **[Read article]** / **[Skip]** |
| Read | Fetch + status embed + follow-up Turtle turn with extract |
| Skip | Embed confirms skip; no fetch unless practitioner asks again |

### Tips

- Wrap URLs in `<>` to hide Discord’s cosmetic link preview (preview is not what Turtle read).
- `!fetch` remains distill + cache — separate from dialogue read.

---

## Rejected (link reading)

See also [rejected.md](rejected.md).

| Pattern | Why |
|---------|-----|
| Silent fetch (no embed) | Feels like Turtle hung; practitioner can’t verify what was read |
| Fetch prose in Turtle voice | Collapses operational trace into chat; violates timeline-owns-trace |
| Auto-fetch on buried links | Violates consent; blocks first reply on slow pages |
| Link-read renames over River titles | Two system-line rename fights; River owns naming |
| Auto-write `link-resonance/` on dialogue fetch | Conflates read vs distill; surprises practitioners |
| Article title as forced thread name | Verbose; `generate_topic` / intake territory are better names |

---

## Journey

```
Practitioner drops URL (+ short ask) in eddy
  → Reading… embed (silent)
  → typing indicator during fetch
  → Read embed: host · N/M in context · spill path if long
  → Turtle reply grounded in excerpt
```

Incidental variant:

```
Long message with URL at end
  → Turtle reply (no fetch yet)
  → Link detected · [Read article] [Skip]
  → (Read) second turn with fetch + grounded reply
```

Full walkthrough index: [journeys.md](journeys.md#drop-url-in-eddy).

---

## Review prompts (link reading)

When touching fetch UX, ask:

1. Is fetch progress visible on the timeline before the reply?
2. Does Turtle avoid narrating fetch in conversational voice?
3. Are incidental links opt-in?
4. Does partial read show N/M (and path) in the embed?
5. Does link-read respect River-owned thread names?
6. Is read-for-dialogue still separate from `!fetch` distill?

Full checklist: [review-checklist.md](review-checklist.md).
