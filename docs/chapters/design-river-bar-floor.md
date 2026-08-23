# Design Chapter: River Bar as Reconciled Floor

**Opened:** 2026-07-15  
**Status:** Destination sanctioned — implement reconcile → hold → chrome  
**Spec trace:** TURTLE_SPEC §5.3, §5.4, §17  
**UX:** [docs/ux/river.md](../ux/river.md)  
**Grill:** Forge craft session 2026-07-15 (launch pad · hybrid placement · more select)

---

## Tension

The river standing bar is meant to be a **floor fixture** — always reachable, never the story. Eager `ensure_bar_at_bottom` tracks one message id and re-anchors on many event paths. The invariant is local (“is *my tracked* bar last?”), not global (“exactly one bar, and it is last”). Living friction:

1. **Duplicate bars** after busy stretches (cools, ops, Spirit posts) — orphan messages the tracker never sweeps.
2. **Bar between related acts** — multi-step flows (artifacts browse, clustered lifecycle embeds) get chrome inserted mid-sequence.
3. **Console face** — `new eddy` · `artifacts` · `help` as peers fights the journey target (`new eddy` only) and hosted-practitioner “start a conversation” read.

---

## Design intent

| Principle | Meaning |
|-----------|---------|
| **Launch pad** | Bar purpose is “start a conversation,” not “operate the river.” |
| **Reconciled floor** | Placement law is global reconcile (scan → purge orphans → one fresh bar last), not eager per-event re-anchor. |
| **Hybrid rhythm** | Quiet debounce after activity (~1–2s coalesce) plus slow safety sweep / on-ready. |
| **Hold during multi-step** | Known multi-step paths pause reconcile until the sequence ends; then one settle. No active-face polish in v1. |
| **Secondary under more** | Face = `new eddy` + `more` select (`artifacts` · `help`). Help is ephemeral; artifacts keep public Recent for now. |

---

## Behavior

### Reconcile

1. If `bar_hold` for the channel (and not expired) → no-op.
2. Scan recent history for river-bar markers (`river:bar:` custom ids; legacy act buttons on ZWSP bar messages).
3. Delete all matches.
4. Post one fresh bar last; update `eddy_bar.json`.

**Triggers:**

- **Debounced** — timeline activity schedules reconcile; coalesces during bursts.
- **Immediate** — bot ready, safety sweep, hold release.
- **Hold** — artifacts browse (and similar) sets hold at start; releases when browse completes (or hold expires).

### Chrome

```text
[ 🌀 new eddy ]  [ more ▾ ]
```

- **new eddy** — unchanged materialize path.
- **more** — Discord select on the bar message: `artifacts` · `help`.
- **help** — ephemeral Commands card (no timeline litter).
- **artifacts** — public Recent flow as today; hold reconcile for the browse sequence.

### Out of scope

- Pinned / alive artifact presentation — design locked: [design-pinned-home-eddies.md](design-pinned-home-eddies.md) (not list-browse; river pin + home eddy).
- Shared-river artifact privacy model.
- Eddy lifecycle / in-eddy flow-library bars.
- Active-face “artifacts highlighted” polish.
- Act Three period notes.

---

## Stories

1. After a wave of cools and ops embeds, the river shows **one** bar at the bottom — never two.
2. During artifacts Recent → pick → preview, no bar appears between steps; bar settles once at the end.
3. First glance at the river reads as start-a-conversation (`new eddy` primary).
4. Help from **more** leaves no Commands embed in the timeline.
5. Typed `!artifacts` / bar **more → artifacts** both honor hold.

---

## Value criteria (recognition tests)

A week in, this succeeded if:

1. You almost never notice the bar mid-conversation — only when you want a new eddy.
2. You never see two bars after a busy stretch.
3. Multi-step acts stay contiguous — bar settles after, not between.
4. First glance reads as “start a conversation,” not “operate a console.”
5. Help does not leave inventory litter (ephemeral from **more**).

---

## Module map

| Module | Role |
|--------|------|
| `river_handler.py` | `RiverEddyBarView`, reconcile floor, post bar, orphan scan |
| `bar_anchor.py` | Debounce schedule, hold/release, river vs eddy routing |
| `commands.py` / `cmd_practice_io.py` | Help ephemeral path; artifacts hold at start |
| `artifact_presenter.py` | Release hold + schedule reconcile when browse completes |
| `river_bot.py` | On-ready immediate reconcile; periodic safety sweep |
| Tests | `tests/test_bar_anchor.py`, `tests/test_river_handler.py` |

---

## Vertical slices

| Issue | Slice |
|-------|-------|
| 042 | Reconcile + debounce + orphan sweep (replace ensure law) |
| 043 | Bar hold for multi-step |
| 044 | Chrome: more select + ephemeral help |

---

## Forward signal

Artifact browsing may move from “sift a Recent list” to **pinned home eddies** ([design-pinned-home-eddies.md](design-pinned-home-eddies.md)). Do not invest in list-browse UX beyond keeping the public Recent path working under hold/reconcile.

---

## Spec amendment

§5.3: standing bar is a **launch pad** (`new eddy` + overflow); harness **reconciles** the floor (debounce + sweep), not only “ensure last after each message.”
