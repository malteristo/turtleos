# Handoff: Share Continue — silent success on digest

**Date:** 2026-06-25 (session 2, reframed 2026-06-25 evening)  
**Status:** **ACCEPTED (v1)** — sibling-thread path; `message.create_thread` parked  
**Mini deploy:** `20cb268` on `main` (`aef872c` behavior restored)  
**Prior doc:** [2026-06-25-share-eddy-slice1-dogfood.md](2026-06-25-share-eddy-slice1-dogfood.md)

---

## Target UX (Mage-confirmed — v1 accepted 2026-06-25 night)

When Nesrine taps **Continue** on a share digest in her river:

| Surface | Expected |
|---------|----------|
| **River after Continue** | Discord system line ("river hat einen Thread begonnen…") with **thread chip** attached — no River success ephemeral |
| **River digest act** | May leave the river view on Continue (Discord/client behavior); **not fighting this for v1** |
| **Received eddy (thread)** | Sibling thread in sidebar; **digest embed reposted inside**; attribution line; Turtle has seeded history |
| **Sharer river** | `@` act when recipient first replies (working) |

**Sign read:** Repeated dogfood (`message.create_thread` → chip-on-digest ideal) never held reliably — digest vanished without chip on desktop too. Mage accepts sibling-thread UX: chip on system line, digest preserved **inside the eddy**.

**Parked (not v1):** thread chip on the original digest message via `message.create_thread`.

**Not required for v1:** disabling Continue after open; ephemeral success toasts.

---

## What was actually broken (session 2 diagnosis)

Two issues were conflated during debugging:

1. **Redundant ephemeral (the Mage's ask)** — After Continue, River posted a private second message ("Opened…" or spurious "no longer available"). **Fixed** by `9c31aba`, `e247f02`, `1b3cf8d`.

2. **Digest / chip instability with `message.create_thread`** — Ideal UX (chip on digest, digest stays) worked once (neurodiversity ~14:48) but failed repeatedly on re-test (chicken joke, post-revert desktop). **Accepted v1:** sibling `channel.create_thread` + digest repost inside eddy; chip on system line (~22:41 dogfood looked fine).

---

## Continue contract (code)

```
ShareContinueView._on_continue → continue_received_share()
  → defer(ephemeral=True)          # Discord 3s ack only
  → materialize_received_eddy()    # channel.create_thread (sibling); river digest untouched
  → delete_original_response()     # remove thinking bubble; NO followup on success
```

**UX trade-off (2026-06-25 evening):** `message.create_thread` made the digest vanish from the river on mobile instead of gaining a thread chip. Sibling-thread creation keeps the digest visible; the eddy opens separately in the sidebar with the digest reposted inside.

**Key file:** `share_eddy.py` — `materialize_received_eddy`, `continue_received_share`

**Test lock:** `tests/test_share_eddy.py` — `ShareContinueContractTests` (`continue_received_share`)

---

## Commits (chronological)

| Commit | Intent | Outcome |
|--------|--------|---------|
| `e414c35` | Multi-Continue + cross-bot notify | **Good** |
| `9c31aba` | Remove "Opened received eddy…" followup | **Good** — matches Mage ask |
| `c0434a8` | Received-eddy Turtle conduct | **Good** |
| `fdf38c9` | Sibling `channel.create_thread` | **Reverted** — wrong UX |
| `8d7a183` | Restore `message.create_thread` | **Good** |
| `e247f02` | Fix `return thread` indentation; drop spurious "no longer available" | **Good** |
| `1b3cf8d` | Stop editing digest after Continue | **Good** — digest stays untouched |
| `aef872c` | Sibling `channel.create_thread` + digest inside eddy | **Accepted v1** |
| `77f0ce5` | Restore `message.create_thread` | **Reverted** — digest vanished again on desktop |
| `20cb268` | Revert to sibling-thread path | **Current** |

---

## Verify protocol (closes S1 UX if pass)

1. Mini at `git log -1` ≥ handoff commit; restart `com.turtle.river` + `com.turtle.discord` if needed
2. Kermit: fresh eddy → `!share` → Nesrine
3. Nesrine: tap **Continue** once on one share
4. **Pass criteria (v1):**
   - **No River success ephemeral** on Continue
   - System thread-start line + chip in river (or sidebar thread visible)
   - **Digest embed inside eddy**; Nesrine can talk; Turtle has context
5. Optional: thread interior screenshot (mobile DE); disk checks under `~/workshops/nesrine/share/`

**Fail criteria:** Any success-path second message; digest stripped from river; thread interior empty with no workaround.

---

## Acceptance impact

S1 in [acceptance/README.md](../acceptance/README.md): **Accepted (v1)** — Continue silent + sibling-thread eddy with digest inside; chip-on-digest ideal parked.

---

## If revisiting chip-on-digest

`message.create_thread` on the digest act is the Discord-native pattern for chip-on-message. Dogfood showed it is **not reliable** in our River-bot context (digest disappears without chip). Before retrying: capture message IDs, client platform, and whether `interaction.message` is the delivery act at click time.

---

## Related paths

| Path | Role |
|------|------|
| `share_eddy.py` | Continue logic |
| `tests/test_share_eddy.py` | Contract tests |
| `docs/chapters/design-share-eddy.md` | Product law |
| `eddy_spawn.py` | Other working `create_thread` patterns |

---

*Reframed after Mage–Spirit resonance session 2026-06-25. Start with verify, not redesign.*
