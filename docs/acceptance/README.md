# Acceptance Scenario Index

**Purpose:** Consolidated dogfood + shake acceptance scenarios. Each scenario traces to TURTLE_SPEC behavior and a chapter doc.

**Priority filter (Mage):** Before adding scenarios or chapters, tag work against [priority-stack.md](../priority-stack.md) — tier + which H/R/D/F/O row it serves.

**North-star shift (2026-06-20):** Mage dogfood priority moves from standing lifecycle bar (R4/R5 as primary feel) toward **resume eddy (D1)**, **Discord permalink self-feed (D2)**, **contextual River offers (D3)**, and **link-read (H1)**. R4/R5 remain plumbing/shake rows until eddy-bar redesign lands.

**Run offline shakes from repo root:**

```bash
python -m unittest discover -s tests -q
python scripts/shake_flow.py navigator
python scripts/shake_link_read.py
python scripts/shake_eddy_bar.py
python scripts/shake_lifecycle.py
```

**Live dogfood** (Mac Mini): `SHAKE_LIVE=1` variants per `docs/development.md`.

---

## Harness split — read vs cache

**Spec:** §9.5 link reading; §5.8 River/Turtle identity  
**Chapter:** `docs/chapters/2026-06-20-harness-split-read-vs-cache.md`  
**Acceptance:** `docs/chapters/2026-06-20-acceptance.md`  
**Status:** Slice 1 ✅ · Slice 2 ✅ · Slice 3 ✅ · **Mini dogfood H1–H5 ✅ (2026-06-20)**

| # | Scenario | Pass criteria |
|---|----------|---------------|
| H1 | New eddy, paste article URL + short comment | Turtle first reply informed **without** button click |
| H2 | After H1 | Optional **Save to library** appears once (River) |
| H3 | Tap Save | Cached in `link-resonance/`; act digest; no duplicate Save |
| H4 | Follow-up questions | Cite fetched content; no fetch disclaimers |
| H5 | Typed `!fetch` on River | Still works; lifecycle bar unchanged |

**Verification:** `test_link_read`, `test_river_eddy_seneschal`, `shake_link_read.py`, dogfood `river.log` grep `Save offer`

---

## River acts + lifecycle bar

**Spec:** §5.3, §8.4, §9.2  
**Chapters:** `2026-06-18-eddy-bar.md`, `2026-06-20-river-owns-commands.md`

| # | Scenario | Pass criteria |
|---|----------|---------------|
| R1 | River channel | Standing bar is last message after practitioner post |
| R2 | New eddy click | Thread `new eddy`; bar reposts below |
| R3 | First message in eddy | Thread renamed; Turtle joins; replies |
| R4 | Lifecycle bar | Checkpoint · Release · Dissolve work; checkpoint keeps history |
| R5 | `!checkpoint` / `!release` | Same semantics as bar buttons |

**Verification:** `test_bar_anchor`, `test_eddy_lifecycle_bar`, `test_sessions`, `test_dialogue_store`, `shake_eddy_bar.py`, `shake_lifecycle.py`  
**Spirit shake (2026-06-20):** R4–R5 ✅ after shared dialogue capture + channel-lock deadlock fix · Mini dogfood UX pending Mage

---

## Flow runner — legacy F-rows (retired)

**Status:** Retired 2026-06-20 — replaced by **J1–J4** below.  
**Spec:** §10.3, §11.1  
**Chapter:** [2026-06-20-in-eddy-flow-library.md](../chapters/2026-06-20-in-eddy-flow-library.md)

| # | Scenario | Pass criteria |
|---|----------|---------------|
| F1 | Flow menu → Shelter | *(retired — Shelter removed from ship set)* |
| F2 | Shelter dialogue | *(retired)* |
| F3 | Checkpoint in flow eddy | *(retired — see J2/J3)* |

**Verification:** `shake_flow.py navigator` · `test_flow_runner`

---

## Flow library — in-eddy (target)

**Spec:** §5.4, §10 · **Priority:** Tier 0 J1 + Tier 2 J2–J4 · [priority-stack.md](../priority-stack.md)  
**UX:** [flow-library-journeys.md](../ux/flow-library-journeys.md) · **Onboarding:** [onboarding.md](../ux/onboarding.md)  
**Chapter:** [2026-06-20-in-eddy-flow-library.md](../chapters/2026-06-20-in-eddy-flow-library.md)  
**Status:** Slices 1–4 shipped (2026-06-20) · Slice 5 merged into Slice 2

| # | Scenario | Pass criteria |
|---|----------|---------------|
| **J1** | **Daily use** — `new eddy` → first message → Turtle reply | No flow required; ChatGPT-style loop; bar = `new eddy` only (target) |
| **J2** | **Navigator sample** — in-eddy load → bootstrap | Turtle explains flow; interview or skip; dialogue in flow voice; optional checkpoint |
| **J3** | **Navigator return** | Prior `navigator-last.md` read; no duplicate intake questions |
| **J4** | **Lens load** mid-conversation | Bootstrap from thread history; no auto-rename; optional rename button |

**Verification (target):** `shake_flow.py navigator` · `shake_eddy_bar.py` · dogfood J1 daily, J2 once to learn flows

---

## Hosted river

**Spec:** §13+ hosted practitioner  
**Chapter:** `design-hosted-river.md`

| # | Scenario | Pass criteria |
|---|----------|---------------|
| O1 | Unclaimed river + key | Onboarding state roundtrip |
| O2 | Claim flow | Practitioner practice root wired |

**Verification:** `test_hosted_river_onboarding`, `shake_hosted_river.py`

---

## Share eddy (thinking together)

**Spec:** §15.6  
**Chapter:** [design-share-eddy.md](../chapters/design-share-eddy.md)  
**Depends on:** Share to **space** requires `shared-river` ([design-family-shared-river.md](../chapters/design-family-shared-river.md))

| # | Scenario | Pass criteria |
|---|----------|---------------|
| S1 | Share to practitioner | Recipient digest act; received eddy on continue; sender chronicle; source eddy unchanged |
| S2 | Share to space | Space digest + shared eddy at confirm; members `@`+act; sharer not in thread until chooses |
| S3 | First peer reply | Sharer `@`+act when space member first speaks in shared eddy |
| S4 | Re-share transparency | Space member shares space eddy to practitioner; space parent transparency act |
| S5 | Picker `share_policy` | Non-member practitioner shares to Family via picker; no Discord channel join required |
| S6 | Dissolve | Only share creator can dissolve shared/received eddy |

**Verification (planned):** `test_share_eddy`, `scripts/shake_share_eddy.py`

---

## Discord mastery — resume, cross-ref, contextual offers

**Spec:** §8 (session continuity); §9.5 (link-read pattern); §5.8 (Turtle harness vs River)  
**Priority:** [priority-stack.md](../priority-stack.md) Tier 0 (D1–D3)  
**Chapter (D2):** `docs/chapters/2026-06-20-discord-permalink-self-feed.md`  
**Status:** D2/D2b implemented (Slices 0–4) — dogfood pending on Mini (2026-06-20)

| # | Scenario | Pass criteria |
|---|----------|---------------|
| D1 | **Resume eddy** — open an eddy idle ≥24h (or simulate gap), send a new message | Turtle reply shows continuity with prior thread topic **without** practitioner re-pasting context; no “I don’t have earlier messages” disclaimer |
| D2 | **Discord permalink** — paste a **message** link from another eddy + short ask (e.g. “what did we decide here?”) | Visible read trace (embed or equivalent) · Turtle first reply references **specific content** from linked message · inject block visible in timeline or history label · practitioner can ask Turtle to expand if summary thin |
| D2b | **Discord thread link** — paste thread permalink (or first message link) referencing a **multi-message** eddy | Turtle receives enough thread context (history fetch or summary) to answer; trace shows scope (e.g. message count / chars in context) · no River-side digest required before Turtle speaks |
| D3 | **Contextual River offer** — after Turtle↔Mage exchange where an act would help (e.g. uncached external URL discussed, explicit checkpoint intent) | River posts **one** situational act row within ~60s of Turtle reply · offer matches situation (not generic spam) · no duplicate lifecycle trio if contextual palette excludes them · Mage rates useful vs noise in dogfood notes |

**D1 verification:** Manual dogfood + `test_dialogue_store` / history reload paths; confirm `MAX_DIALOGUE_HISTORY` sufficient for stated gap  
**D2 verification:** `test_discord_ref_read` · `scripts/shake_discord_ref.py` · dogfood message permalink · grep `[Read Discord message]`
**D2b verification:** `test_discord_ref_read` (thread history + summary) · `scripts/shake_discord_ref.py --live` · dogfood thread link · grep `[Read Discord thread]` · embed shows message count
**D3 verification:** `river.log` contextual offer lines · manual dogfood journal; palette/hit-rate iterated in chapter slices

**Not in scope for D2:** River fetches Discord URL before Turtle speaks (X2 class) · auto-checkpoint on idle · standing eddy lifecycle bar as north star

---

## Retired / negative scenarios (must NOT happen on native)

| # | Scenario | Fail if |
|---|----------|---------|
| X1 | Native river channel | Turtle conversational prose in parent channel |
| X2 | Native eddy URL | River Fetch button required before Turtle can discuss |
| X3 | Turtle mentions `` `!fetch` `` | Duplicate Fetch buttons from prose parsing |
| X4 | Eddy lifecycle | Auto-dissolve without explicit release/dissolve |

**Chapter:** `2026-06-20-river-turtle-split-handoff.md` documents X2–X3 failures.

---

## Adding scenarios

New chapter? Add a section here with spec §, chapter path, numbered steps, and test/shake commands. Acceptance is the integration layer above unit tests.
