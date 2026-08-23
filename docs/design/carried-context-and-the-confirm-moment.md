# Carried Context and the Confirm Moment

> **Companion:** [continuity-engine-and-substrate.md](continuity-engine-and-substrate.md) — CE design v4. This resolves where Slice 2's confirm gate belongs and what carries without one.
>
> **Companion:** [per-member-periodic-notes.md](per-member-periodic-notes.md) — the voice law for prose records. This applies the same law one layer down, to structured state.
>
> **Companion:** [channel-twine-and-communal-memory.md](channel-twine-and-communal-memory.md) — §3.2 crossings, §3.3 witness spec.

**Status:** **§1–§3 current. §4–§5 SUPERSEDED** by [`what-a-shared-room-remembers.md`](what-a-shared-room-remembers.md) (2026-07-29) — the confirm gate is dropped in favour of retrieval from notes already written. Slices 1–3 shipped (`5ed8f7a`) and stand; slice 4 as designed here is **not to be built**. §7 carries the revised sequencing pointer.
**Date:** 2026-07-28 (design) → 2026-07-29 (as-built through slice 3, then §4–§5 superseded)
**Spec trace:** TURTLE_SPEC §6.5 (story surfaces), §7.1 (CE composition), §8.4 (checkpoint), §15.5 (multi-practitioner isolation)
**Origin:** Operator dialogue on Anvil, 2026-07-28 evening — following the per-member-notes ship, prompted by a shared-space member's frustration that every new eddy starts cold.

---

## 1. Finding

Two mechanisms carry context between eddies in a practice root. Only one has a consent gate, and it is attached to the wrong door.

| | `last_checkpoint_one_liner` | Alive threads |
|---|---|---|
| **Written by** | `set_last_checkpoint`, on **every** idle checkpoint | `add_active_thread`, only via confirm |
| **Gate** | none | `continuity_confirm.offer_theme_confirm` |
| **Reachable from** | idle *and* manual checkpoint | **manual `!checkpoint` / `!release` only** |
| **Scope written** | the practice root | the practice root |
| **Injected** | `dialogue_turn.py:397-406`, unconditional, every turn | same packet, via `render_alive_headers` |

`_offer_theme_confirm_if_any` lives in [`cmd_sessions.py`](../../cmd_sessions.py); the idle path in [`sessions.py`](../../sessions.py) never calls it. So:

**The path that requires a deliberate human act asks permission. The path that runs itself every fifteen minutes asks nothing.**

### Measured on the live node (2026-07-28)

| Root | `alive.yaml` | Eddy notes since 07-19 | Banked `proposed-themes` sets |
|---|---|---|---|
| `kermit` | 4 threads, last written **07-17** | 18 entries | — |
| `<practitioner>` | 3 threads, last written **07-16** | 19 entries | — |
| `family` | **absent — never created** | **44 entries / 22 eddies** | **45** |

The family space has never had a manual checkpoint, so nothing has ever entered its alive layer. Its `state/` directory contains exactly one file. Meanwhile its `current.yaml` carries an unconfirmed, model-authored one-liner — at time of writing, an account of a marital conflict naming both members — recited into every turn in the space, read by both.

So the space is not "starting from zero." It remembers nothing either member agreed to, and one thing neither did.

**This is the third instance of the same law in one day.** INT-042 was ambient *delivery*; INT-046 is ambient *authorship selection*; this is ambient *carry*. Each resolves toward whoever already holds the most access.

## 2. Why the obvious fix is wrong

Wiring the idle path into the existing confirm gate fails, for a reason the operator identified before it was built:

- The idle checkpoint fires **15 minutes after the last message**. The room is empty by definition.
- `CONFIRM_TIMEOUT_SECONDS = 180` — the view is inert three minutes later, and is not persistent across restarts.
- The dead prompt stays visible in the eddy indefinitely, with copy written for someone who just typed `!release`: *"Before you go — these feel live right now…"*

The result would not be stale context leaking forward. It would be **near-total capture failure plus a corpse in every cooled eddy**. Worse than the current silence.

The operator also named the adjacent risk — someone stepping into an old eddy days later and tapping *Keep these*, promoting a stale moment into live state. The 3-minute timeout happens to prevent this today, but by accident rather than design. Any confirm surface that *lives at the eddy* carries that risk structurally.

## 3. The split

The two mechanisms have different half-lives and want different treatment. Collapsing them was the design error.

| | `last_checkpoint_one_liner` | Alive threads |
|---|---|---|
| **Asserts** | *where we left off* — a pointer to the last moment | *what is ongoing* — a claim about the present |
| **Lifetime** | hours | weeks |
| **Needs** | **expiry + scope** | **a consent gate** |
| **Gate?** | no — it asserts nothing about the present | yes |

The one-liner does not need confirmation, because it does not claim anything is ongoing. It needs to **age out** — a "where we left off" from six days ago is simply false — and in a multi-member root it must stop reciting one member's last moment to another as though it were the room's.

Alive threads do need the gate. What was wrong was not the gate but its **moment**.

## 4. Confirm at re-entry, not at capture

> **SUPERSEDED 2026-07-29** → [`what-a-shared-room-remembers.md`](what-a-shared-room-remembers.md) §4.
>
> The reasoning below is kept because it is *correct about the confirm gate* — asking at capture cannot work, and asking at re-entry is where you land if you keep the gate. What it never questioned is whether the gate should exist. It came from CE Slice 2, which was designed for a solo practitioner, and consent turned out to buy far less accuracy than it cost in decisions. Do not build this.

**Stay silent at the idle checkpoint.** Nothing is lost: proposals are already banked in each eddy note's `proposed-themes` front-matter, dated, one set per checkpoint (45 of them sit unread in the family root today).

**Ask when a member returns**, with the surface composed fresh from recent material:

> *Since you were last here, a few things kept coming up:*
> *• invisible caregiving burden*
> *• intent versus impact in conflict*
> *Want me to keep any of these in mind?*

This answers both objections structurally rather than with a timer:

- **Nothing left on the table.** One batched ask replaces N unanswered ones. Unconfirmed proposals stay banked rather than expiring — they remain eligible next time they recur.
- **No stale carry.** There is no old button to press: the surface is generated at the moment of asking, bounded by recency (last day or two). Stepping into a three-week-old eddy cannot resurrect a three-week-old theme.

**Host:** [`fresh_eyes.py`](../../fresh_eyes.py) already assembles *"Where you left off"* + *"Recent conversation notes"* from exactly this material. The ask belongs there, not in the eddy.

## 5. Attributed space threads

> **SUPERSEDED 2026-07-29** → [`what-a-shared-room-remembers.md`](what-a-shared-room-remembers.md) §4–§5.
>
> Built and shipped in `5ed8f7a`, and **demoted rather than reverted**: `confirmed_by` remains correct for anything confirmed through a manual `!checkpoint`, and is harmless. It is no longer the foundation of shared memory. Retrieval inherits attribution from the notes themselves, where the voice was already resolved at write time — so the cardinality branch this section introduces is not needed. New work should not build on it.

**Operator decision, 2026-07-28:** a confirmed thread in a shared space belongs to **the space, attributed to the member who confirmed it** — not to a private per-member alive layer.

Rationale: the space is meant to develop shared memory; per-member layers would prevent exactly that. Attribution is what makes shared memory safe, and it is the same answer the prose layer already reached — the witness law applied one layer down, to structured state.

**Schema** (as built, `5ed8f7a`). `active_threads` entries were `{id, label, since, tone}`. Now also:

```yaml
- id: invisible-caregiving-burden
  label: invisible caregiving burden
  since: '2026-07-28'
  tone: active
  confirmed_by: <practitioner>      # registry address, resolved per §6.1 name spaces
```

**Rendering.** `render_alive_headers` gains attribution when the root has more than one member — the same cardinality branch the note layers already use:

```text
In motion: (1) invisible caregiving burden — the hosted practitioner, active; (2) …
```

**Solo roots are the degenerate case.** One member → `confirmed_by` is the sole member → omitted from rendering. Today's behaviour, unchanged. No special-casing.

**Vocabulary firewall holds:** "in motion", never "active threads" or "alive layer"; the attribution reads as a name, not as a field.

## 6. The gap this closes in the drafted amendment

[`spec-amendment-story-layer-draft.md`](spec-amendment-story-layer-draft.md) proposes a voice law branching on audience cardinality. As drafted it governs **prose records only**. Two gaps:

1. **Structured state has no author.** `alive.yaml` threads carry no `confirmed_by`, so a theme one member confirmed is recited into the other's eddies with no marker of whose it was — the INT-040 collapse, one layer below the prose, in the state that shapes *every* turn rather than one note.
2. **The "Whose is this?" law reaches delivery but not selection or carry.** It says *which root, which river, which author*. It does not say *which root gets written for* (INT-046) or *what carries into a shared room unconfirmed* (INT-047).

**Proposed additional clauses** — for the operator to fold in before sanction, not applied here:

> - The voice law governs **structured carried state as well as prose**. Any element of practice state that is recited into dialogue in a multi-member root MUST carry its author and MUST render that attribution.
> - ~~**Nothing carries into a shared room unconfirmed.**~~ **Withdrawn 2026-07-29** — drafted from the superseded confirm design and would write a discarded mechanism into law. The durable part is narrower and survives: *a recency pointer MUST expire and MUST NOT be attributed to the room.* What replaces the rest: context carried into a shared room MUST be attributed to its author and MUST NOT persist as standing state — see [`what-a-shared-room-remembers.md`](what-a-shared-room-remembers.md) §4.
> - Selection of *which* practice root a scheduled artifact is written for MUST resolve explicitly and fail closed — not from ambient context.

## 7. Sequencing

| | Slice | State |
|---|---|---|
| 1 | **Stopgap** — clear the carried line; suppress carry in multi-member roots | ✅ `85c0370` — cleared in `family` *and* `<practitioner-2>_sandbox` |
| 2 | One-liner ages honestly (stamp at write, qualify at render, drop at 30d) | ✅ `5ed8f7a` |
| 3 | `confirmed_by` schema + attributed rendering + cardinality branch | ✅ `5ed8f7a` — packet and Fresh Eyes |
| 4 | ~~Re-entry ask~~ | **dropped 2026-07-29** — see [`what-a-shared-room-remembers.md`](what-a-shared-room-remembers.md) §7 for the revised sequence (INT-041 first, then retrieval) |
| 5 | INT-046 root-blind scheduler → per-member daily dogfood | ❌ open — now after retrieval |
| 6 | Widened §6.5 amendment covering all three faces of the ownership law | ❌ open — **must not be sanctioned describing the confirm design** |

**Slice 2 was refined in the building.** The note above said the one-liner should *age out*. That is wrong at the edge that matters: after a five-day gap, "where you left off" is exactly what a returning practitioner wants, and deleting it makes Turtle coldest precisely when return is hardest. What was false was never that the line existed — it was presenting a six-day-old moment as though the practitioner had just been there. So the line is stamped at write and **qualified at render** ("Last checkpoint (3 days ago): …"), and dropped only at thirty days, once it has stopped pointing at anything. Lines written before the stamp existed render unqualified: silence beats a fabricated age.

**A shared room now carries nothing until slice 4.** That is honest and it is cold. Slices 1–3 removed what nobody agreed to and built the rails for attribution; only the re-entry ask puts anything back. The material is banked and waiting — 45 `proposed-themes` sets in the family root as of 2026-07-29.

## 8. What this does not do

- **Not retroactive.** The 44 existing family eddy entries (42 written before the witness fix deployed 19:14 on 2026-07-28) are untouched by this design. Whether they are left as history, annotated, or regenerated is a separate operator decision with a second person's stake in it.
- **Not mood or state inference.** CE non-goals stand. Themes are content a member confirmed, in their own words, and now carry their name.
- **Not automatic crossing.** A confirmed shared-space thread is the *space's*. It does not read, and must not read, either member's private alive layer, intentions, or profile notes (§3.2, and per-member-notes §6.2).

---

*The gate was never wrong. It was on the door nobody uses, while the door everyone uses had none.*
