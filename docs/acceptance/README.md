# Acceptance Scenario Catalogue

**Purpose:** The definitions behind the H/R/D/J/S/O/X ids — what each scenario is, how it is verified, and which spec behaviour it covers. Reference data. Each traces to a TURTLE_SPEC behaviour and a chapter doc.

**This is not an index of the work.** That is [traceability-matrix.md](../traceability-matrix.md), which since 2026-08-02 carries the tiers, the chapter gate and the mis-prioritization patterns that used to live in the retired priority stack. Tag work there; define the scenario here.

**Functional gate (2026-06-26):** Each scenario has two gates — **Spirit** (shake/unittest plumbing) and **Mage** (async UX dogfood). Spirit closes the functional gate before Mage tests feel. See [functional-gate-protocol.md](../automation/functional-gate-protocol.md) and `python scripts/shake_report.py`.

| Gate | Owner | Pass means |
|------|-------|------------|
| **Spirit** | Spirit on Mini/Forge | Scenario covered by `shake_*` verdict JSON |
| **Mage** | Mage async | Practice feel — screenshot + felt-sense in Forge |

**Which Mage gates are current** lives in `shake_report.MAGE_UX_SCENARIOS`, not here — a dogfood priority written into prose stays whatever it was the day it was written (this line replaced a north star from 2026-06-20).

**To run the shakes:** `./scripts/spirit_verify.sh` for units, then `python scripts/shake_report.py` for the verdict board. The offline suite is `shake_report.DEFAULT_OFFLINE_SUITE` — one list, executed by the nightly, guarded by a test. This file used to hand-copy four of the eleven script names, which is how a reader could run the catalogue's own instructions and cover a third of the gate.

**Live dogfood** (Mac Mini): `SHAKE_LIVE=1` variants per `docs/development.md`.

---

## Harness split — read vs cache

**Spec:** §9.5 link reading; §5.8 River/Turtle identity  
**Chapter:** `docs/chapters/2026-06-20-harness-split-read-vs-cache.md`  
**Acceptance:** `docs/chapters/2026-06-20-acceptance.md`  
**Status:** Slice 1 ✅ · Slice 2 ✅ · Slice 3 ✅ · **Mini dogfood H1–H5 ✅ (2026-06-20)**

| # | Scenario | Spirit gate | Mage gate |
|---|----------|-------------|-----------|
| H1 | New eddy, paste article URL + short comment | `shake_link_read` | First reply *feels* informed |
| H2 | After H1 | `shake_link_read` (offer) | Save UX (Tier 2) |
| H3 | Tap Save | manual / dogfood | Library act digest |
| H4 | Follow-up questions | `shake_link_read` | No fetch disclaimers in feel |
| H5 | Typed `!fetch` on River | `shake_link_read` | River lifecycle unchanged |

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

**Spec:** §5.4, §10 · **Priority:** Tier 0 J1 + Tier 2 J2–J4 · [traceability-matrix.md § Choosing the next chapter](../traceability-matrix.md#choosing-the-next-chapter)  
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
**Chapter:** [design-share-eddy.md](../chapters/design-share-eddy.md) · **Decomposition:** [2026-07-10-decomposition-share-eddy.md](../chapters/2026-07-10-decomposition-share-eddy.md) · **Dogfood:** [2026-06-25-share-eddy-slice1-dogfood.md](../chapters/2026-06-25-share-eddy-slice1-dogfood.md) · **Continue v1:** [2026-06-25-share-eddy-continue-handoff.md](../chapters/2026-06-25-share-eddy-continue-handoff.md)  
**Depends on:** Share to **space** requires `shared-river` ([design-family-shared-river.md](../chapters/design-family-shared-river.md))  
**Status:** Slice 1 **S1 accepted (v1)** — sibling-thread Continue, digest inside eddy · sender + Continue UX dogfooded 2026-06-25 · Mini `ab75b11` · chip-on-digest **parked** · S2–S6 after shared-river

| # | Scenario | Pass criteria |
|---|----------|---------------|
| S1 | Share to practitioner (v1) | Sharer: digest act to recipient; source eddy unchanged; `@` act on first peer reply. Recipient: **Continue** with **no River success ephemeral**; sibling thread (Discord system line + chip); **digest reposted inside received eddy** with Turtle context. *(Parked: thread chip on digest via `message.create_thread`.)* |
| S2 | Share to space | Space digest + shared eddy at confirm; members `@`+act; sharer not in thread until chooses |
| S3 | First peer reply | Sharer `@`+act when space member first speaks in shared eddy |
| S4 | Re-share transparency | Space member shares space eddy to practitioner; space parent transparency act |
| S5 | Picker `share_policy` | Non-member practitioner shares to Family via picker; no Discord channel join required |
| S6 | Dissolve | Only share creator can dissolve shared/received eddy |

**Verification:** `tests/test_share_*.py`, `scripts/shake_share_eddy.py` (offline) · live Mini dogfood S1 for deploy gates · space scenarios S2–S6 after shared-river

---

## Discord mastery — resume, cross-ref, contextual offers

**Spec:** §8 (session continuity); §9.5 (link-read pattern); §5.8 (Turtle harness vs River)  
**Priority:** [traceability-matrix.md § Choosing the next chapter](../traceability-matrix.md#choosing-the-next-chapter) Tier 0 (D1–D3)  
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

## Family dates (capture → reminder)

**Spec:** §11 (state artifacts), §6.2 (river acts), §15 (shared spaces)
**Chapter:** [design-family-dates.md](../chapters/design-family-dates.md)
**Status:** Shipped 2026-08-04; capture vocabulary widened 2026-08-06.

| # | Scenario | Pass criteria |
|---|----------|---------------|
| T1 | Say it, don't type it | A member names a date in ordinary speech — month name, weekday, or "morgen" with a commitment cue — and Turtle offers a Keep whose echo spells the weekday and month in words |
| T2 | The river stays quiet | Ordinary speech containing "morgen" or a weekday and *no* commitment produces no offer |
| T3 | It arrives | The reminder posts at each lead day, once, in the owning root's river and nowhere else |

**Verification:** `tests/test_dates.py`, `scripts/shake_dates.py` (journey: notice · restraint · confirm · keep · surface · read back · typed) · live: the first voluntary keep, still zero as of 2026-08-06

T1/T2 are the pair. T2 without T1 is a system that never helps; T1 without T2 is a system that interrupts — and the second is how an opt-in feature becomes worse than no feature.

---

## Practice artifacts (curated access)

**Spec:** §11.5 (access tiers, curated shelf)

| # | Scenario | Pass criteria |
|---|----------|---------------|
| A1 | Ask for the shelf | `!artifacts` lists only allowlisted Tier-1 surfaces — never a raw practice-root listing |
| A2 | Open one | Selection opens the artifact for reading; no full-body markdown dump into the eddy timeline (§11.5.5) |

**Verification:** `scripts/shake_artifacts.py` (registration · allowlist · practice_io · shelf menu · discoverability) · live `--live` sends `!artifacts` in river and eddy

---

## Pinned home eddies (working-plan pins)

**Spec:** §5.3 (river acts), §8 (sticky cool), §11.5 (home binding)

| # | Scenario | Pass criteria |
|---|----------|---------------|
| P1 | One home per root | Registry binds home eddy to practice root 1:1; a second binding is refused, not silently overwritten |
| P2 | Offered once, then quiet | The plan offer fires on its heuristic and the sticky skip flag holds — a declined pin is not re-offered next message |

**Verification:** `scripts/shake_home_plans.py` (registry · registration · honesty copy · plan-offer heuristic) · live deferred to operator dogfood after a both-bot restart

---

## Adding scenarios

New chapter? Add a section here with spec §, chapter path, numbered steps, and test/shake commands. Acceptance is the integration layer above unit tests.

**The id set is checked, not trusted.** `tests/test_acceptance_catalogue.py` joins this catalogue to `scripts/shake_report.py`: an id a shake claims must be defined here, and an id defined here must either be claimed by a shake or written into that test's `UNVERIFIED` inventory with a reason. Adding a section without a shake fails the suite until one of those two things is true. This exists because A1–A2 and P1–P2 above shipped with working shakes on 2026-08-06 and reached the nightly gate mapped to **no scenario at all** — the catalogue said nothing was there for 41 commits, and nothing said otherwise.

**Status does not live here.** Ship state, tiers and next-chapter priority are [traceability-matrix.md](../traceability-matrix.md); live verdicts are `python scripts/shake_report.py`. Duplicating them into this file is what made every dated `Status:` line below stale.
