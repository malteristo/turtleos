# E1 experience — artifact navigation (practitioner view)

**Status:** Dogfood complete (2026-06-29 E1; 2026-06-30 E1.1 artifact browse + export refinement) — Mini at `7cd65dd`  

**Parent:** `docs/chapters/design-generative-ui-e1-artifact-presenter.md`  
**Law unchanged:** Chat = dialogue; browser = corpus (§11.5.5)

---

## One-line promise

**You stopped typing file commands to resume your practice.** Turtle still saves things the same way; browsing what you saved becomes tap-first, recency-first, and quiet about empty shelves.

---

## Mental model (what the practitioner should believe)

| Belief | How E1 supports it |
|--------|-------------------|
| “My notes live in *my* practice, not in chat scrollback.” | Opening an artifact goes to the **reader** (browser when configured), not a markdown dump in the thread. |
| “I can pick up where I left off.” | Default view is **Recent** — last touched sessions, notes, intake, etc., across shelves. |
| “Shelves still exist, but I don’t inventory them daily.” | Full shelf catalog is **one step away** (`!artifacts --all` or footer hint), not the first screen. |
| “I talk to Turtle; I tap to open files.” | Commands remain for search and power use; **Open** buttons replace `` `!read path` `` as the primary affordance. |

---

## Today vs E1 (same eddy, practitioner with a small corpus)

### Today — `!artifacts`

Practitioner types `!artifacts` (or Turtle nudges them to). They get a long markdown reply:

```
Practice artifacts — curated shelves (not the full filesystem)

• Sessions (`!artifacts sessions`) — 3 — checkpoint and session notes
• Notes (`!artifacts notes`) — 1 — flow outcomes
• Archives (`!artifacts archives`) — 0 — dissolved thread captures
• Chronicle (`!artifacts chronicle`) — 0 — practice timeline
• Saved links (`!artifacts links`) — 0 — …
• Intake (`!artifacts intake`) — 0 — …

View one: `!read <path>` · Export: `!export <path>` · Search: `!search <term>`
```

**Friction:** Empty shelves compete for attention. Every next step is **remember a command, copy syntax, type on mobile**.

### E1 — `!artifacts` (default)

Same trigger. Different surface — **one embed + buttons** (or a select menu if many recents):

```
┌─ Embed: Recent ─────────────────────────────────────┐
│ 2026-06-29-reflection.md          · Sessions        │
│ navigator-outcome.md              · Notes           │
│ compile-keynote-notes.md          · Intake          │
│                                                     │
│ Search with !search · All shelves: !artifacts --all │
└─────────────────────────────────────────────────────┘

[ Open: 2026-06-29-reflection ] [ Open: navigator-outcome ] [ Open: compile-keynote ]
```

**Tap Open** → same outcome as a successful `!read` today:

- **With practice web configured:** a compact embed appears; **tap the title** → Discord in-app browser → full artifact in the reader.
- **Without web:** fallback is today’s inline/preview behavior (unchanged).

No shelf with zero items. No `` `!read sessions/...` `` on every line.

---

## Journey 1 — Resume after checkpoint (highest-value path)

**Situation:** Practitioner finished a Navigator eddy, typed `!checkpoint` (or will use seneschal **Checkpoint** when offered). Turtle wrote `sessions/2026-06-29-navigator.md`.

### Today

```
Turtle: Checkpoint saved — 12 messages captured.
        Saved to Sessions — try `!artifacts sessions`.
```

Practitioner must **parse the hint**, run another command, scan a list, copy `!read …`.

### E1

```
Turtle: Checkpoint saved — 12 messages captured.

┌─ Embed (optional) ──────────────────────────────────┐
│ Saved to Sessions · 2026-06-29-navigator.md         │
└─────────────────────────────────────────────────────┘

[ Open ]
```

**One tap** → reader opens the thing that was just saved. Conversation stays in the eddy; reading happens in browser (when configured).

**Unchanged:** Seneschal may still offer **Checkpoint** before save — that’s the *decision* affordance. E1 adds the *after save* affordance.

---

## Journey 2 — “What have I been working on?” (default browse)

**Situation:** Practitioner returns after a day away, types `!artifacts` or asks Turtle “show my recent notes” and Turtle suggests `!artifacts`.

### E1 behavior

1. System loads up to **8 most recently modified** Tier-1 artifacts (any shelf), newest first.
2. **Embed lists them** with human names + shelf label (Sessions, Notes, Intake, …).
3. **Open affordance:**
   - **1–3 recents:** three labeled Open buttons.
   - **4–8 recents:** dropdown **Choose artifact to open** (Discord allows one select per row).
   - **More than 8 in corpus but showing 8:** footer nudges `!search` for deep lookup.

**What they should *not* see:** Archives (0), Chronicle (0), empty shelves — unless they ask for the full catalog.

### If corpus is empty (brand-new practitioner)

No recents → **fallback**, still not today’s wall of zeros:

```
┌─ Embed: Your practice library ──────────────────────┐
│ Nothing saved yet. Checkpoint an eddy or paste      │
│ something into intake — it will show up here.       │
└─────────────────────────────────────────────────────┘
```

Optional: if some shelves have items but mtime ordering failed edge case, show **only non-empty shelves** as short blurbs (no command per shelf). Shelf drill-in stays `!artifacts sessions` or a future Browse button — E1 may keep typed shelf name for drill-in.

---

## Journey 3 — Browse one shelf

**Situation:** Practitioner wants every session note, not just recent cross-shelf mix. They type `!artifacts sessions`.

### Today

Markdown list; each line ends with `` `!read sessions/foo.md` · `!export …` ``.

### E1

```
┌─ Embed: Sessions (3) ───────────────────────────────┐
│ 2026-06-29-navigator.md                             │
│ 2026-06-27-reflection.md                            │
│ 2026-06-20-intake.md                                │
└─────────────────────────────────────────────────────┘

[ Open: 2026-06-29-navigator ] [ Open: 2026-06-27-reflection ] [ Open: 2026-06-20-intake ]
```

Or, if **4+ items**, select menu instead of buttons.

**Export in E1:** Not on the primary row (room for Open only). Practitioner can still `!export path` or we add Export in E1.1 — **critique welcome**.

---

## Journey 4 — Full catalog (escape hatch)

**Situation:** Practitioner wants the map of all shelves, including empty ones, or Spirit/operator running shakedown.

**Trigger:** `!artifacts --all` (not the default).

**Experience:** **Same as today** — full markdown shelf menu with command hints. This path is explicitly **operator-oriented**; practitioners discover it via footer on Recent embed, not by default.

---

## Journey 5 — Search (unchanged in E1)

**Situation:** Practitioner `!search ferritin`.

E1 does **not** change search results in v1. They still see matching lines in chat; they open full artifacts via `!read` or a future E1.1 Open row on hits.

**Why call it out:** So critique doesn’t assume search got generative treatment yet.

---

## Journey 6 — Mobile vs desktop

Discord is the same components; **density** differs in feel:

| Surface | Mobile | Desktop |
|---------|--------|---------|
| **Open buttons** | Large tap targets; 1–3 obvious | Same; may feel sparse if only one recent |
| **Select menu** | Full-screen half-sheet picker | Dropdown — good for 4–8 items |
| **Embed → browser** | Tap title → in-app browser (primary mobile read path) | Same; larger screen for reader |
| **Footer hints** | `!artifacts --all` is typable but awkward — consider whether footer is enough | Fine |

**Design intent:** Mobile is the forcing function — if Open works on phone, desktop is gravy.

---

## What stays the same (explicit)

- **Turtle dialogue** — no change to how Turtle talks; E1 is River/command presentation.
- **`!read`, `!export`, `!search`** — still work when typed.
- **Allowlist / sovereignty** — same artifacts, same denials.
- **Browser reader** — same URL, same tap-title-to-open embed when web is configured.
- **Chat vs browser law** — full corpus never pasted into chat when web is on.

---

## What E1 deliberately does *not* do

- Replace Turtle with a file manager UI.
- Auto-open browser without a tap (no unprompted pop-ups).
- Generate custom layouts per user via LLM.
- Merge search + browse into one mega-screen.
- Show **Export** on every row (deferred).

---

## Wireframe — full eddy timeline (checkpoint + browse)

```
… earlier dialogue …

You: !checkpoint

Turtle: Checkpoint saved — 8 messages captured.
        ┌ Saved to Sessions · 2026-06-29.md ┐
        [ Open ]

You: (tap Open)
        ┌ Embed: 2026-06-29 · tap title to open in browser ┐

You: (read in browser, close, back to Discord)

You: !artifacts

Bot:    ┌ Recent ─────────────────────────────────────────┐
        │ 2026-06-29.md · Sessions  ← just touched          │
        │ 2026-06-27.md · Sessions                          │
        │ compile-notes.md · Intake                         │
        └ Search · All shelves: !artifacts --all ──────────┘
        [ Open: 2026-06-29 ] [ Open: 2026-06-27 ] [ Open: compile-notes ]
```

---

## Dogfood learnings (2026-06-30 — E1.1 artifact browse + export)

Principles that emerged from Mage dogfood on river bar → Recent → select → preview/export. Treat as **presentation law** for the artifact kit going forward.

### Composition

1. **One file, one surface.** Don't stack instructional embed, code fence, attachment, and button row for the same artifact. The practitioner should see one coherent preview, not three versions of the same note.

2. **Let Discord's attachment be the preview.** For `.md` exports and select follow-ups, the attachment bar (filename + expandable body) *is* the in-chat preview. A separate ` ```md ` block duplicates it and reads as clutter.

3. **Filename once.** The attachment bar already shows `2026-06-30-3.md`. Drop bold display-name lines above the preview.

4. **Download without a Download button.** Mobile save path = `⋯` on the attachment bar. A dedicated Download button is redundant when the file is already attached.

5. **Instructional copy is not part of every handoff.** Phone/Desktop hints and `-#` download lines helped once; on a repeated action they become noise. Prefer silent attachment or one quiet line max — attachment-only won.

### Navigation chrome

6. **Standing bar = process indicator during browse.** Clicking **artifacts** on the river bar should highlight that action and grey out the rest — not delete the bar message (which reads as "reference to deleted message"). Re-anchor at bottom only when the browse step completes.

7. **Select replaces the browse surface.** Picking from the Recent dropdown should transform *that message* into the preview — not leave the Recent embed visible under a "tap below to open" header with extra buttons.

8. **Open in browser stays optional.** When `PRACTICE_WEB_BASE` is set, a single **Open in browser** link below the attachment is enough for full-corpus reading. It is secondary to the in-chat preview, not a third content copy.

### What we tried and rejected (this session)

| Attempt | Why it failed dogfood |
|---------|-------------------------|
| Export ops embed + hidden `⋯` | Opaque; practitioner couldn't find Download |
| Full download envelope (Phone / Desktop fields + Open + Download) | Felt like a tutorial after every export |
| `-#` hint line + attachment | Better, still redundant once attachment bar is understood |
| Code block + title + attachment | Two previews of the same file |
| Recent embed + select result layered | Confusing — two stages visible at once |

**Reference implementation:** `artifact_presenter.py` — `present_artifact_preview_in_place()`, `RiverEddyBarView.with_active_command()`.

---

## UX questions for critique

These are the decisions worth your eye before implementation:

1. **Recent vs shelves as default** — Is cross-shelf recency the right “home,” or should default be “non-empty shelves only” without mtime ranking?
2. **Post-checkpoint Open** — One button always, or embed-only when multiple files written in one checkpoint?
3. **Select vs buttons threshold** — At 4+ recents, is a dropdown acceptable, or should we paginate with << >> buttons (more taps, more visible)?
4. **`--all` discoverability** — Footer text enough, or a second button **Browse all shelves** on the Recent embed?
5. **Export absent from primary row** — OK for E1, or must Export sit beside Open for parity with today?
6. **Empty corpus copy** — Does the “nothing saved yet” message match onboarding tone?
7. **Shelf drill-in** — Keep `!artifacts sessions` as typed drill-in, or add **[Browse Sessions]** buttons on fallback view?
8. **Naming** — Embed title **Recent** vs **Pick up where you left off** vs **Your library** — voice of turtleOS practitioner UX.

---

## After critique

| Outcome | Next step |
|---------|-----------|
| Experience resonates with edits | Update this doc + align technical spec → implement |
| Experience wrong | Revise scenarios before any code |
| Partial (e.g. defer checkpoint Open) | Mark scope in both docs → implement reduced E1 |

**Gate:** Mage critique of **this file**, not the Python spec.
