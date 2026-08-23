# Per-Member Periodic Notes — one record, N perspectives

> **Companion:** [channel-twine-and-communal-memory.md](channel-twine-and-communal-memory.md) — the charter establishes perspective governance (§3.3 witness spec) and custody (§3.4). This document resolves the open referent problem in §3.3 and specifies the delivery architecture.
>
> **Companion:** [story-layer-vision.md](story-layer-vision.md) — the story layer's purpose. This is that layer made multi-member.
>
> **Companion:** [provenance-guard.md](provenance-guard.md) — the distillation-time backstop. Complementary: that guard checks *person*-attributions; §6 here adds the missing *source*-claim check.

**Status:** v3 — **delivery withdrawn 2026-07-29.** Per-member notes are withheld at the source (INT-048) and the §5 communal-record posting is deliberately not built. Neither artifact is delivered anywhere; the space's day stays on disk and the room's continuity comes from eddy-note retrieval instead. See the banner below before building on §4–§5.
**Date:** 2026-07-28 (v1 design → v2 as-built) · 2026-07-29 (v3 delivery withdrawn)
**Spec trace:** TURTLE_SPEC §6.5 (story layer), §8.4 (checkpoint), §15.5 (multi-practitioner isolation), §16 (practice state)
**Origin:** Operator dialogue on Anvil 2026-07-28, following diagnosis of INT-041 / INT-042

---

## Delivery withdrawn — 2026-07-29

**§4's per-member rendering and §5's routing are withdrawn. §1–§3 and the eddy/communal layers stand.**

The per-member layer shipped 2026-07-28 and produced its first notes overnight. One of them told a member the *other* member's account as their own day (INT-048). The cause was §4's re-centring step: every entry of the space goes to every member's prompt, the only difference is the address string, and the rule against folding another member's words into "you" is a sentence in a system prompt rather than a mechanism.

The reflex was to guard the synthesis — a deterministic alias check plus an LLM judge. That is the same move as the confirm gate this repo dropped one day earlier: **a verifier bolted onto a generated artifact does not buy accuracy, it buys a second opinion from the same class of machine reading the same corpus.**

The problem underneath was simpler and older. **The communal record was written every day and posted nowhere.** `river_channel_id_for_practice_dir` returns `None` for shared roots — correct that a space's day is not one member's day, but it conflates *no owning member river* with *nowhere to post*, and the space has its own registered channel. §5 of this document already said the communal record posts to the shared channel. It was never built. The per-member note was invented to carry the space's day to its members, and it is the one artifact that can invert.

**Third instance of write-only memory in two days** — the alive layer (INT-047), the eddy notes ([what-a-shared-room-remembers.md](what-a-shared-room-remembers.md)), and now this. The platform writes well and delivers badly, and each felt absence has been answered with a new artifact rather than a wire.

**The operator's decision (2026-07-29):** do not post the communal record into the space either. A private river narrating your own day back to you is a different act from a shared room narrating a conflict back to its participants at midnight — accurate, attributed, and still possibly the wrong thing to put in front of two people. The record stays on disk. Continuity comes from eddy-note retrieval at turn time.

**Consequently:**

| | |
|---|---|
| Eddy note (space root, attributed witness) | **stands** — it is the primary material and the retrieval source |
| Communal periodic note (space root) | **stands as a record**, delivered nowhere; visible on disk and on demand |
| Per-member periodic note | **withheld** (`MEMBER_NOTES_WITHHELD`), and now a feature without a job |
| §5 delivery routing | **not built, deliberately** |

Retrieval reads eddy notes, not dailies — deliberately. A daily is a synthesis *of* the eddies; reading both would double-count and re-admit the synthesized-artifact-as-memory path.

Making the communal record visible in the space later remains a one-line change if the room ever wants it. Nothing here forecloses that.

---

## 1. What the operator asked for

> Notes (daily, weekly, monthly) on a **per-channel** basis: one for my river, and one for each shared space I am a member of. The same for hosted practitioners. Per §3.3, shared-space notes must not collapse all members into one "you" — each member's note should centre that member's own activity in the space.

Two decisions taken at proposal time:

- **Absent activity** → attributed witness line. When another member was active in a period the recipient was not part of, the recipient's note *names that it happened*, attributed and un-narrated. Charter §3.2 item 4 default, upheld.
- **Communal record** → kept. The space holds one shared, attributed account readable by all members, alongside the per-member perspectives.

## 2. The referent problem, resolved

Charter §3.3 item 2 requires third-person witness voice above one member, reasoning that *"second-person has no stable referent across members."* That is correct **for a single note shared by everyone** — and it is the only case §3.3 considered.

Per-member notes dissolve the premise. A note with exactly one recipient has a stable referent again. So:

| Artifact | Audience | Voice |
|---|---|---|
| **Communal record** | all members of the space | third-person attributed witness — §3.3 unchanged |
| **Per-member note** | exactly one member | **second person to the recipient**, all other members in attributed third person |

This is a refinement of §3.3, not a departure: the witness constraint was always about *referent stability*, not about second-person being intrinsically unsafe. Items 1, 3 and 4 of §3.3 (attribute authorship; hold a member's account of another as attributed perception; crossing-safety default) apply unchanged to both artifacts.

**Proposed §3.3 amendment:** branch on *audience cardinality*, not member cardinality. One reader → second person. More than one reader → third person. A solo river and a per-member shared-space note land on the same rule for the same reason.

## 3. Perspective is not extraction

The operator's phrasing — *focus on that member's activity* — must be implemented as **perspective**, not as filtering.

A shared exchange does not decompose into per-speaker slices. A member's reply is unreadable without what it replied to; filtering the transcript to one author's utterances yields incoherence, not focus.

The correct rendering **centres** the recipient's thread through the space and **attributes** everyone else:

> ✅ "You pushed back on the birthday plan; Kermit came back with the scheduling constraint, and it was left there."
> ❌ "You pushed back on the birthday plan. It was left there." *(others' turns deleted — the exchange becomes unintelligible)*
> ❌ "You worked through the birthday plan and landed on Saturday." *(both members collapsed into one "you" — INT-040)*

## 4. Architecture — write once, render N times

**Do not** write N notes at the eddy layer. Cost would scale per checkpoint per member, and N independently-generated accounts of one exchange have no source of truth — divergent memory by construction.

| Layer | Written | Voice | Scope |
|---|---|---|---|
| **Eddy note** | once per eddy, in the space root | third-person attributed witness | the exchange |
| **Communal periodic** | once per period, in the space root | third-person attributed witness | the space's day/week/month |
| **Per-member periodic** | once per member per period | second person to recipient, others attributed | that member's thread through the space |

The eddy note is the space's memory. Periodic notes are *readings* of it. Attribution is preserved once, at the cheapest layer; perspective is applied at delivery.

**Cadence recursion.** Eddy notes → daily → weekly → monthly, each level reading the level below (the existing `collect_eddy_entries_for_date` → `_recent_daily_context` pattern, extended). Honest absence at every level: no material in the period → no note written, no post. Quiet spaces stay silent rather than manufacturing an arc — the existing `DailyNoteResult(created=False)` contract.

**Single-member roots are the degenerate case.** One member → communal and per-member renderings coincide → today's behaviour, unchanged. No special-casing for solo rivers.

## 5. Delivery routing

Per-member shared-space notes route to **that member's own river**. Never to the shared channel — posting a per-member perspective into the shared room defeats its purpose and re-creates the §3.4 asymmetry trap. The communal record posts to the shared channel.

This requires the root→member→river reverse map that does not exist today, and whose absence is the direct cause of **INT-042**: `post_daily_note_river_visibility` resolves delivery through the global `DISCORD_CHANNEL_DIALOGUE` constant, so every practice root's note lands in the operator's river. That fix is therefore not merely triage — it is this design's foundation, and must land first.

**Storage.** Both artifacts live in the **space root** (`~/workshops/<space>/story/…`), per-member notes keyed by member. Custody belongs to the space; §3.4 already establishes that operator filesystem custody is not authorship, so this adds no exposure that the shared root does not already carry. A member's private root stays their own material only.

## 6.1 Three name spaces, one identifier

A shared record must name people the way the practice names them. Three name
spaces meet here and only one is stable:

| Space | Example | Set by |
|---|---|---|
| Registry key / `address` | `<practitioner>` → *the hosted practitioner* | the operator at provisioning — first names, chosen to be memorable |
| Discord username | `<partner-handle>`, `<handle-2>`, `<handle-3>` | the person |
| Discord **display name** | `<partner-handle>`, `<display-name>`, `<display-name>` | the person, per guild, changeable at will |

Stored dialogue history records the **display name**; the practice thinks in
the **registry address**. Nothing reconciles them but `discord_id`.

Measured across the four registered practitioners, three of four failed to map,
and the one that worked did so by coincidence — the operator's display name
happens to equal his registry key while his username is something else
entirely. A hand-curated `display_name` column would have fixed one row and
rotted the moment anyone edited their profile — silently, with a handle landing
in a permanent shared record.

So `member_address_map` resolves aliases **live** from `discord_id` (username,
global name, display name, per-guild nick), with the registry applied last so an
explicit `display_name` still overrides. An unmapped handle passes through
unchanged: a handle in the record is ugly but honest, and inventing a name
would be worse.

**The operator maintains nothing.** Keep assigning first names at provisioning;
that remains the only name anyone has to think about.

## 6.2 The isolation boundary — state it now

A shared-space note **must not read the recipient's private alive layer, intentions, or profile notes.**

Today `write_daily_note` pulls `_alive_one_liner()` and `story_notes._validate_relation` gates `related-topics` against the root's alive layer. When rendering a member's shared-space note, the tempting move is to relate it to what is in motion for them privately. That is an **automatic crossing** — precisely what charter §3.2 forbids: crossings are member-initiated, per-item, never standing access. Relevance-surfaced *pull* remains the only sanctioned path.

Shared-space notes relate to the shared space only. Their alive-layer source is the space's own, or none.

**Source-claim honesty (INT-041).** The same boundary needs an outward-facing gate: Turtle must never assert it has read a space outside its practice root. The provenance guard checks whether an attributed *statement* is grounded in the transcript; it does not check whether a claimed *source* was ever accessible. Both are needed — INT-041 was a fabricated source-claim (*"both here and in the family chat"*) that no person-attribution check would catch.

## 7. What already exists

Cheaper than it looks. Per-utterance authorship **already survives in stored history** — shared-space dialogue files carry `[kermit]:` / `[<partner-handle>]:` prefixes on every member turn, across all 28 family eddy histories.

It is destroyed at exactly one line, [`story_notes.py`](../../story_notes.py) `_transcript()`:

```python
f"{mage_name if m.get('role') == 'user' else 'Turtle'}: {m.get('content', '')}"
```

Every member turn is relabelled with a single `mage_name` — which, for a space, resolves via `_resolve_mage_info_for_channel` to the *space key*. Family-space transcripts therefore reach the model as `Family: [<partner-handle>]: …` — a contradictory double-label where the outer frame wins, which is the mechanical cause of the undifferentiated "you".

So the foundation is **stop discarding attribution**, not build attribution capture.

| Piece | State |
|---|---|
| Per-utterance authorship in history | ✅ always existed |
| Space member list | ✅ `mage_registry.yaml` `spaces.<key>.members` |
| Honest-absence contract | ✅ `DailyNoteResult(created=False)` |
| Attribution survives into synthesis prompt | ✅ `_transcript` preserves the speaker |
| Witness-voice eddy note | ✅ cardinality branch, both layers |
| Per-member rendering | ✅ `write_member_daily_notes` |
| Root→member→river delivery map | ✅ `river_channel_id_for_mage_key` |
| Participants recorded per eddy entry | ✅ front-matter `participants` |
| Name-space reconciliation | ✅ live from `discord_id` (§6.1) |
| Weekly / monthly cadence | ❌ daily only — dogfood daily first |
| Source-claim honesty gate | ❌ (INT-041) — independent slice |

## 8. Sequencing — what shipped

1. ✅ **INT-042 delivery fix** — target resolves from the note's own root; shared-space roots post nowhere; unregistered roots fail closed.
2. ✅ **Preserve attribution** — `_transcript` keeps the speaker per turn.
3. ✅ **Witness-voice records** — cardinality branch at the eddy and daily layers.
4. ✅ **Per-member daily** — N readings of the one attributed record, each routed to its member's own river.
5. ❌ **Weekly / monthly** — recursion is mechanical but three cadences × three spaces is a lot of unproven surface. Dogfood daily first.
6. ❌ **Honesty gates** — source-claim refusal (INT-041) and the assertion/testimony split. Independent of this architecture; see [provenance-guard.md](provenance-guard.md) §Source claims.

## 9. Resolved while building

- **A member who never participated** — resolved **against** the v1 lean toward silence. Silence makes the space illegible exactly when someone is away, which is when legibility matters most; and channel→river is default-open for members (§3.2), so an all-witness note crosses nothing that was not already theirs. A note is written whenever the *space* had activity, for every member.
- **Whose name appears** — the practice names people, Discord names accounts; only `discord_id` joins them (§6.1).

## 10. Still open

- **Volume.** The operator is in 3 spaces, one hosted practitioner in 2. Daily × spaces × cadences is a lot of surface if honest-absence proves too permissive a filter.
- **Disagreement-holding** (§3.1) in the communal record — recordable divergence is charter law but unspecified in the note format.
- **Weekly/monthly for shared spaces** may want a different shape than a longer daily — the useful month-scale artifact for a *between* is probably not narrative.
- **Spec drift.** `TURTLE_SPEC` §6.5 still describes river visibility as posting "on the river" (ambient singular) and knows nothing of per-member notes or the voice law. Amendment drafted, sanction pending.

---

*The charter said the channel twine **is** the shared meaning, co-authored. One record holds the co-authorship; the per-member notes are how each author reads it back.*
