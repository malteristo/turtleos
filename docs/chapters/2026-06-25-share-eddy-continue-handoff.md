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
| **River digest message** | **Unchanged** — `@` line + embed + Continue button stay in the river after Continue (no vanish on mobile) |
| **Second river message** | **None on success** — no "Opened received eddy…", no "This share is no longer available", no other ephemeral confirmation |
| **Received eddy (thread)** | Sibling thread in sidebar; digest embed reposted inside; attribution line; Turtle has seeded history |
| **Sharer river** | `@` act when recipient first replies (working) |

**Trade-off:** Sibling-thread creation (`channel.create_thread`) keeps the river digest visible. We do **not** get Discord's thread chip on the digest message (that path used `message.create_thread`, which made the digest disappear on mobile).

**Not required for v1:** disabling Continue after open; ephemeral success toasts; thread chip on digest.

---

## What was actually broken (session 2 diagnosis)

Two issues were conflated during debugging:

1. **Redundant ephemeral (the Mage's ask)** — After Continue, River posted a private second message ("Opened…" or spurious "no longer available"). **Fixed** by `9c31aba`, `e247f02`, `1b3cf8d`.

2. **Digest vanishes on mobile (chicken joke ~22:20)** — `message.create_thread` opened the eddy server-side but the digest left the river without a thread chip. **Fixed** by switching to sibling `channel.create_thread` + repost digest inside thread.

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
| *(next)* | Sibling thread + digest repost inside | **Verify** — fixes mobile vanish |

---

## Verify protocol (closes S1 UX if pass)

1. Mini at `git log -1` ≥ handoff commit; restart `com.turtle.river` + `com.turtle.discord` if needed
2. Kermit: fresh eddy → `!share` → Nesrine
3. Nesrine: tap **Continue** once on one share
4. **Pass criteria:**
   - Digest message **still visible** in river (unchanged text + embed + Continue button)
   - **No second ephemeral/message** from River on success
   - New eddy appears in sidebar; **digest embed reposted** as first message inside thread
   - Nesrine can talk; Turtle has context
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
