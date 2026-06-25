# Handoff: Share Continue — silent success on digest

**Date:** 2026-06-25 (session 2, reframed 2026-06-25 evening)  
**Status:** **VERIFY** — fix shipped; Nesrine re-dogfood pending  
**Mini deploy:** `1b3cf8d` on `main` (plus contract test on next push)  
**Prior doc:** [2026-06-25-share-eddy-slice1-dogfood.md](2026-06-25-share-eddy-slice1-dogfood.md)

---

## Target UX (Mage-confirmed resonance)

When Nesrine taps **Continue** on a share digest in her river:

| Surface | Expected |
|---------|----------|
| **River digest message** | **Unchanged** — `@` line + embed + Continue button; after Continue, Discord adds the **thread chip** on this same message (see neurodiversity share ~14:48) |
| **Second river message** | **None on success** — no "Opened received eddy…", no "This share is no longer available", no other ephemeral confirmation |
| **Received eddy (thread)** | Thread opens on the digest; attribution line inside; Turtle has seeded history |
| **Sharer river** | `@` act when recipient first replies (working) |

The thread chip on message 1 **is** the confirmation UX. River should not narrate success afterward.

**Not required for v1:** disabling Continue after open; ephemeral success toasts.

---

## What was actually broken (session 2 diagnosis)

Two issues were conflated during debugging:

1. **Redundant ephemeral (the Mage's ask)** — After Continue, River posted a private second message ("Opened…" or spurious "no longer available"). **Fixed** by `9c31aba`, `e247f02`, `1b3cf8d`.

2. **Digest vanishes (handoff over-focus)** — Some dogfood runs showed digest loss or empty thread interior on mobile. The **good reference** (neurodiversity ~14:48) shows `message.create_thread` working with digest + thread chip intact. Experiments with sibling threads and post-Continue `message.edit` were **reverted**; they fought the target UX.

**Do not reopen Option A (two-message repost)** unless verify fails on thread *interior*, not on the redundant ephemeral.

---

## Continue contract (code)

```
ShareContinueView._on_continue → continue_received_share()
  → defer(ephemeral=True)          # Discord 3s ack only
  → materialize_received_eddy()    # msg.create_thread on digest; never edit digest
  → delete_original_response()     # remove thinking bubble; NO followup on success
```

Errors (wrong recipient, materialize exception) may still send a private ephemeral — that is correct.

**Key file:** `share_eddy.py` — `ShareContinueView._on_continue`, `materialize_received_eddy`

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

---

## Verify protocol (closes S1 UX if pass)

1. Mini at `git log -1` ≥ handoff commit; restart `com.turtle.river` + `com.turtle.discord` if needed
2. Kermit: fresh eddy → `!share` → Nesrine
3. Nesrine: tap **Continue** once on one share
4. **Pass criteria:**
   - Digest message unchanged in river + thread chip visible
   - **No second ephemeral/message from River on success**
   - Thread opens; Nesrine can talk; Turtle has context
5. Optional: thread interior screenshot (mobile DE); disk checks under `~/workshops/nesrine/share/`

**Fail criteria:** Any success-path second message; digest stripped from river; thread interior empty with no workaround.

---

## Acceptance impact

S1 in [acceptance/README.md](../acceptance/README.md): **Partial** until verify pass.

Do **not** mark S1 closed until Nesrine re-test confirms silent Continue.

---

## If verify fails

Investigate in order:

1. Which code path sent a second message? (error branch vs old deploy)
2. Thread interior only — consider reposting digest inside thread (narrow fix), not sibling-thread architecture
3. Compare with working message IDs in channel history; River logs around Continue timestamp

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
