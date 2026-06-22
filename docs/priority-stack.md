# Mage Priority Stack (Pop 2 operator north star)

**Status:** Active — development filter for Kermit-as-primary-user  
**Date:** 2026-06-20 (rev. 2 — Mage dogfood notes integrated)  
**Heuristic:** Build turtleOS for the practice I actually run. Improvements that serve Tier 0–1 will generalize to other Pop 2 operators; Tier 3 work is valid product surface but not my daily loop.

**Use this before starting a chapter:** Which tier? Which acceptance scenario? If neither answers — pause.

**Companion docs:** [acceptance scenarios](acceptance/README.md) · [command inventory](turtle-talk.md) · [development chapters](development.md)

---

## Two axes (not one ladder)

The first draft conflated **navigation** with **continuity**. These are separate:

| Axis | Question | Tier |
|------|----------|------|
| **Navigation** | What do I reach for while practicing? | **0** |
| **Reliability** | What must not break silently? | **1** |
| **Opt-in power** | What do I want sometimes? | **2** |
| **Other populations** | Valid product, not my daily loop | **3** |

---

## Persistence model (Magic vs Discord)

**Magic `@release`** fits **serial** practice: one Forge chapter, complex warm-routing, then exhale — context dies unless artifacts carry it.

**turtleOS eddies** are **multi-threaded**: the Discord thread *is* the save. Resume = re-enter the thread (even weeks later); Turtle loads history. Cross-pollinate = paste a Discord thread or message permalink into another eddy. Search and permalinks are Discord-native; turtleOS adds **scaffolding where Turtle cannot use Discord UI** (`!search` on practice files, link-read, Discord-URL self-feed — see below).

**Implication:** checkpoint / release / dissolve as a **standing eddy bar** is a Magic transplant, not the north-star loop. Explicit `!checkpoint` remains available; idle auto-checkpoint is deprioritized (see Tier 1).

---

## How to read tiers

| Tier | Meaning | Investment rule |
|------|---------|-------------------|
| **0** | Daily loop — must feel great | Dogfood first; hard problems still Tier 0 |
| **1** | Must work reliably | Fix wedges before new affordances |
| **2** | When I want it | Don't preempt Tier 0–1 |
| **3** | Not my primary user | Plumbing OK; defer UX polish |

**External link vs library (do not conflate):**

| Job | Mechanism | Tier |
|-----|-----------|------|
| Discuss a page/video *now* | Paste URL → Turtle **link-read** (self-feed, like today) | **0** (H1, H4) |
| Save distilled resonance *later* | Save to library / `!fetch` | **2** (H2–H3, H5) |

**Discord link vs web link (same pattern):**

| Job | Mechanism | Tier | Status |
|-----|-----------|------|--------|
| Cross-reference another eddy/message | Paste Discord permalink → Turtle **self-feeds** (fetch thread history, inject context) | **0** | **Design target** — mirror web link-read; consider faster qwen for fetch/summary |
| River summarizes Discord URL | River-side digest | — | **Rejected** for consistency — Turtle owns link ingestion |

Optimizing `!fetch` when the pain is "paste link and talk" is a **tier mismatch**.

---

## Tier 0 — Daily loop (navigation & dialogue)

*What I reach for without thinking.*

| Capability | What "good" feels like | Acceptance |
|------------|------------------------|------------|
| **Eddy dialogue** | New eddy → speak → Turtle joins; conversation holds context | R3 |
| **Resume eddy** | Re-open thread after days/weeks; seamless continuation from Discord history | *(new: D1 — add to acceptance)* |
| **Article / link conversation** | Drop URL + comment → visible read trace → grounded reply; no fetch disclaimers | H1, H4 |
| **Discord permalink cross-ref** | Paste thread/message link → Turtle self-feeds prior context (transparent inject) | *(new: D2)* |
| **River standing bar** | new eddy · flow menu reachable after I post | R1, R2 |
| **Contextual River offers** | River listens to Turtle↔Mage dialogue; posts **situationally useful** act row (hit rate improves over time) | *(new: D3)* |

### Link-read — Tier 0 and hard

Paste-URL-and-talk is standard in ChatGPT/Gemini; **simplicity for the Mage ≠ simplicity to build**. Bot walls, JS sites, paywalls, YouTube vs article, and context-window policy are a **high-complexity harness problem**. Learn from other agent stacks (Hermes `web_extract` / size tiers, visible tool progress, SSRF discipline) — see `autoresearch/proposals/2026-06-18-eddy-link-reading.md`.

### Eddy bar — contextual only (for now)

**No standing lifecycle bar inside eddies** for the north-star loop. River provides a **well-working contextual bar**: listens after Turtle replies, offers what fits the moment. Palette and hit/miss rate improve over time. Standing checkpoint · release · dissolve is **not** the daily affordance target.

**Negative (must not regress):** X2 (Fetch required before discuss) · X3 (duplicate Fetch buttons)

---

## Tier 1 — Reliability (not Magic-release semantics)

*Trust erodes when the substrate wedges or spams.*

| Capability | What "good" feels like | Notes |
|------------|------------------------|-------|
| **Process reliability** | Turtle responds after idle; no wedge requiring restart | intention blocker: idle wedge |
| **Registry / thread state** | Eddy metadata persists without intermittent save failures | intention blocker: registry save |
| **Idle behavior** | **Silent nothing** by default · **rare reflection** when warranted · **checkpoint only on explicit act** | Deprioritize 15-min idle checkpoint spam |
| **Explicit lifecycle commands** | `!checkpoint` / `!release` / `!dissolve` remain for power users & shakes | Not north-star dogfood; R4/R5 = plumbing verified, not "feels like Magic release" |

Legacy acceptance rows R4/R5 and the standing lifecycle bar remain in the codebase for now; **Mage dogfood priority** shifts to D1 (resume), D2 (Discord self-feed), D3 (contextual offers), H1 (link-read).

---

## Tier 2 — When I want it

| Capability | When I use it | Acceptance |
|------------|---------------|------------|
| **Shared practice / family channel** | Partnership, kids, vacation ops — important personally, not default Pop 2 turtleOS | *(chapter: family channel design)* |
| **Save to library** | URL became load-bearing artifact | H2, H3 |
| **`!fetch` (typed)** | Power-user library save | H5 |
| **Practice file browse** | `!read` / `!ls` / `!search` under practice root | — |
| **Flow eddy (chosen flows)** | Named container when deliberate | R2 + flow-specific |
| **API model opt-in** | Local stack insufficient | — |

---

## Tier 3 — Not my primary user

| Capability | Primary user | My stance |
|------------|--------------|-----------|
| **Shelter flow** | Pop 1 / onboarding demo | Plumbing OK; not my dogfood (F1–F3) |
| **Hosted river / claim** | Pop 2 without Magic | O1–O2 when OPN pulls |
| **Practitioner minimal `!` palette** | Hosted practitioners | Don't design around my channel |
| **Magic overlay** | Magic-attuned legacy profile | Gated; not native v1 north star |
| **Expanded computer use** | Future proposal | Mage-altitude decision |

---

## Discord mastery (design stance)

Compose with Discord; scaffold where AI cannot:

- **Human:** search, permalinks, thread list, re-enter anytime  
- **Turtle:** link-read (web), Discord-URL self-feed (target), practice-root `!search`  
- **River:** structural acts (spawn, contextual offers, optional Save to library) — not duplicate link ingestion  

Do not reinvent Discord search; **do** make permalinks legible to Turtle the way URLs are today.

---

## Planned chapters (from stack)

| Chapter | Tension | Tier |
|---------|---------|------|
| **Discord permalink self-feed** | Turtle ingests thread/message links like web URLs; qwen for fast fetch/summary | 0 (D2) · [chapter](../chapters/2026-06-20-discord-permalink-self-feed.md) |
| **Contextual River bar** | Replace standing eddy lifecycle bar with situational offers; grow palette + hit rate | 0 (D3) |
| **Family channel design** | Shared practice without treating it as default Pop 2 | 2 |
| **Idle & reflection** | Silent default; rare reflection; drop checkpoint noise | 1 |
| **Link-read hardening** | OSS harness patterns; bot-blocked content | 0 (H1) |

Acceptance rows **D1–D3** live in [acceptance/README.md](acceptance/README.md). **D2 implementation chapter:** [2026-06-20-discord-permalink-self-feed.md](chapters/2026-06-20-discord-permalink-self-feed.md).

---

## Chapter gate (before implementing)

1. **Tier?** (0 / 1 / 2 / 3)  
2. **Axis?** (navigation / reliability / opt-in / other-pop)  
3. **Acceptance?** (H*, R*, D*, F*, O*, or new)  
4. **My loop?** (Dogfood in the next week without forcing?)  
5. **Conflation?** (link-read vs `!fetch` · web vs Discord URL · Turtle vs River ingest · Magic release vs Discord thread)

If tier ≥ 2 and Tier 1 blockers remain (idle wedge, registry save) — **default defer** unless the slice unblocks Tier 0–1.

---

## Known mis-prioritization patterns

| Pattern | Symptom | Redirect |
|---------|---------|----------|
| **Command inventory drift** | Polish `!fetch` while paste-URL UX is the loop | Tier 0 link-read (H1) |
| **Magic release transplant** | Standing release/dissolve bar; idle checkpoint spam | Discord thread = save; D1/D2/D3 |
| **River does Turtle's fetch** | Discord summary on River | Turtle self-feed (parity with web) |
| **Pop 1 proxy** | Shelter as "the product" | Tier 3 |
| **Spirit-green ≠ Mage-green** | Shake passes; feel untested | D1 + H1 dogfood |
| **Hot-day slice** | No tier tag | Re-read this stack |

---

## Revision log

| Date | Change |
|------|--------|
| 2026-06-20 | v1 — initial stack (link-read Tier 0, `!fetch` Tier 2) |
| 2026-06-20 | v2 — Mage notes: navigation vs reliability; no standing eddy bar → contextual River; Turtle Discord self-feed; idle silent/rare reflection/explicit checkpoint; family → Tier 2; Discord mastery; D1–D3 targets |

---

*Operator priority, not public roadmap. Revise when dogfood contradicts a tier.*
