# Handoff: Share Continue — digest disappears from river

**Date:** 2026-06-25 (session 2)  
**Status:** **BLOCKED** — S1 not acceptance-closed  
**Mini deploy:** `1b3cf8d` on `main`  
**Prior doc:** [2026-06-25-share-eddy-slice1-dogfood.md](2026-06-25-share-eddy-slice1-dogfood.md)

---

## Target UX (confirmed by Mage + Nesrine dogfood)

| Surface | Expected |
|---------|----------|
| **River (`#nesrine-dialogue`)** | Digest card stays visible after Continue: `@` line + embed + thread chip underneath (see neurodiversity lore share ~14:48) |
| **Received eddy (thread)** | Digest is the **first visible message** inside the thread, then attribution line, then conversation |
| **Turtle (invisible)** | Full shared history from `share/inbox/{share_id}.json` seeded into `dialogue/{thread_id}.json` |
| **Sharer river** | `@` + act when recipient first replies (working as of ~14:50 dogfood) |

**Not required for v1:** disabling Continue after open; ephemeral success toasts.

---

## What works (do not regress)

- `!share` sender path: synthesize → preview → confirm → chronicle
- Multiple pending shares: each digest keeps its own Continue button (`supersede_stale_share_acts` only replaces same `share_id`)
- Continue opens received eddy; Nesrine can converse; Turtle has seeded history
- Sharer first-reply notify (split-bot disk persistence: `share/received/{thread_id}.json`)
- Received-eddy conduct scaffolding (`received_eddy_context_lines`, `label_shared_history`)
- No ephemeral “Opened received eddy …” clutter (removed `9c31aba`)

---

## What is broken (reproducible 2026-06-25 afternoon)

**Symptom:** Nesrine taps **Continue** → digest **vanishes from river**; thread appears in sidebar; inside thread the digest/starter often **fails to load** (“could not load first message” on mobile DE client) or shows only the attribution line.

**Not fixed by:** `1b3cf8d` (stop editing digest after Continue).

**Working reference:** Older share “magic resonance neurodiversity lore thread” (~14:48) — digest + Continue + thread chip all visible in river. Later shares (storytime, contra chiang) degraded.

---

## Architecture (current code)

```
deliver_practitioner_share()     → River posts digest msg (text + embed + ShareContinueView)
ShareContinueView._on_continue   → defer(ephemeral); materialize_received_eddy()
materialize_received_eddy()      → msg.create_thread() on digest message
                                 → river_add_turtle_to_eddy()
                                 → seed dialogue_histories + sync_history
                                 → thread.send(attribution line)
                                 → save_received_thread_config()
discord_bot.handle_dialogue()    → maybe_notify_sharer_on_first_peer_reply() [Turtle process]
```

**Split bots:** River owns Continue + thread creation; Turtle owns dialogue + notify. Cross-process state on disk under `~/workshops/nesrine/share/`.

**Key file:** `share_eddy.py` — `materialize_received_eddy`, `ShareContinueView._on_continue`, `deliver_practitioner_share`

---

## Commits attempted this session (chronological)

| Commit | Intent | Outcome |
|--------|--------|---------|
| `e414c35` | Multi-Continue + cross-bot notify | **Good** — fixes real bugs |
| `9c31aba` | Remove ephemeral “Opened…” | **Good** |
| `c0434a8` | Received-eddy Turtle conduct | **Good** for tone; unrelated to digest UX |
| `fdf38c9` | Sibling `channel.create_thread` | **Bad UX** — digest stays but thread detached (“river started thread”); no digest in thread |
| `8d7a183` | Restore `message.create_thread` | Digest-attached UX back; spurious ephemeral |
| `e247f02` | Fix `return thread` indentation | Fixed spurious “no longer available”; **triggered post-Continue edit path** |
| `1b3cf8d` | Stop editing digest after Continue | **Did not fix** disappear — edit was red herring or not sole cause |

---

## Hypotheses (for fresh eyes)

### Likely wrong (tested or accidental)

- ~~Post-Continue `message.edit(view=…)` alone causes disappear~~ — removing edit (`1b3cf8d`) did not restore UX
- ~~`return thread` bug caused disappear~~ — it *prevented* edit from running, masking the issue

### Still open (investigate first)

1. **`message.create_thread()` + split River/Turtle** — River creates thread from River-owned message; Turtle sends inside thread. Does Discord mobile fail to render the starter when the creating bot ≠ the bot posting follow-ups? Compare with `eddy_spawn.py` patterns that work.

2. **Interaction message staleness** — `interaction.message` at Continue time may not reflect post-thread state; `getattr(msg, "thread", None)` may miss existing thread on re-click.

3. **Embed + components on thread starter** — Discord may treat embed+button starter differently on mobile when forked into thread. Neurodiversity “good” case may have been luck/timing before other state changed.

4. **`ensure_bar_at_bottom` / river housekeeping** — Could a river re-anchor or bar pass touch/delete messages near the digest? Grep river logs around Continue timestamp.

5. **Two-message design (recommended fallback)** — Do **not** fork digest into thread:
   - Leave digest message **untouched** in river (`channel.create_thread` on parent)
   - **Repost embed** as first message *inside* new thread (explicit copy from inbox bundle)
   - Link thread to share via `active_river_acts.json` `{share_id, message_id, thread_id}`
   - Matches design “digest first in river” without making digest the thread starter

---

## Repro protocol (next session)

1. Confirm Mini at `git log -1` ≥ `1b3cf8d`; restart `com.turtle.river` + `com.turtle.discord`
2. Kermit: fresh eddy with 4+ turns → `!share` → Nesrine
3. Nesrine: **do not open Discord until both shares posted** (multi-Continue test optional)
4. Nesrine: tap Continue on **one** share; capture:
   - River channel screenshot (digest visible?)
   - Thread interior screenshot (digest as first message?)
   - `~/workshops/nesrine/share/received/{thread_id}.json` exists
   - `~/workshops/nesrine/dialogue/{thread_id}.json` has labeled history
5. River log grep: `Share continue`, `HTTPException`, `materialize` around timestamp

---

## Acceptance impact

S1 row in [acceptance/README.md](../acceptance/README.md): **Partial** — sender + notify dogfooded; **recipient Continue UX not shippable** until digest-in-river + digest-in-thread stable.

Do **not** mark S1 closed until Continue UX passes Nesrine re-test.

---

## Suggested next implementation (when resuming)

**Option A — Two-message (safest):**

```python
# materialize_received_eddy — sketch
thread = await channel.create_thread(name=label, type=public_thread, ...)
embed = discord.Embed(title=f"📥 {sharer} shared…", description=f"**{label}**\n\n{bundle['digest']}", ...)
await thread.send(embed=embed)  # digest copy inside thread
await thread.send(attribution_line, silent=True)
# DO NOT touch river digest message
# Record thread_id in active_river_acts next to message_id
```

**Option B — Debug `message.create_thread` path** with River-only thread seeding + fetch fresh message after create before any side effects; compare with working neurodiversity message IDs in channel history.

---

## Related paths

| Path | Role |
|------|------|
| `share_eddy.py` | All Continue logic |
| `discord_bot.py` | `_build_native_runtime_env`, notify hook |
| `dialogue_store.py` | Shared history Turtle reads |
| `eddy_spawn.py` | Working `create_thread` patterns |
| `docs/chapters/design-share-eddy.md` | “Digest first” product law |

---

*Handoff written 2026-06-25. Next agent: start here, not from chat memory.*
