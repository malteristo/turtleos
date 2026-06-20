# Acceptance Scenario Index

**Purpose:** Consolidated dogfood + shake acceptance scenarios. Each scenario traces to TURTLE_SPEC behavior and a chapter doc.

**Run offline shakes from repo root:**

```bash
python -m unittest discover -s tests -q
python scripts/shake_flow.py shelter
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

## Flow runner (Shelter)

**Spec:** §10.3, §11.1  
**Chapter:** platform-law handoff + flow trace

| # | Scenario | Pass criteria |
|---|----------|---------------|
| F1 | Flow menu → Shelter | Orientation embed; practitioner speaks first |
| F2 | Shelter dialogue | Flow guard on first reply; state writes |
| F3 | Checkpoint in flow eddy | Session note / state captured |

**Verification:** `test_flow_runner`, `shake_flow.py shelter`

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
