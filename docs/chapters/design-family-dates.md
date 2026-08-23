# Design: Family Dates & Proactive Reminders

**Date:** 2026-08-04
**Status:** Destination doc — ready for a bounded TDD slice
**Spec reference:** TURTLE_SPEC §11 (state artifacts), §6.2 (river acts), §15 (shared spaces)
**Origin:** Member-expressed need in a family shared space: keeping track of important dates for the family. First slice of the family care and operations refocus (interpersonal AI; members, not users).

---

## The need

A non-technical, phone-first member wants the family's important dates held reliably — told once, conversationally, and surfaced at the right time without anyone maintaining a system. The operator wants family admin items (fees, appointments, birthdays) to stop living rent-free in heads. The existing working-plan mechanism (`home_plans.py`) proved the pattern: a small per-root registry plus a river-visible artifact.

## Design laws

1. **Say it in chat.** Every member-facing operation — add, change, ask, silence — happens conversationally (or via lightweight typed command for practitioners who prefer it). If it needs a config file, it is not a member feature.
2. **Zero-input maintenance.** After capture, the member does nothing. No app, no sync, no review chore.
3. **Member-chosen lead times.** "Remind me two weeks before so I can get a gift, and the day before" is stored as part of the date, in the member's words at capture time. Sensible default (7 days + day-of) when unstated.
4. **Owning root = owning audience.** Dates captured in the family space live in the family root and surface in the family river; dates captured in a private river stay private. Same routing law as all state.
5. **Care before operations.** A reminder is support, not a task assignment. Surfacing language offers ("the birthday is in two weeks — the gift lead time you asked for"), never demands.

## Mechanism (bounded slice)

- **Registry:** `state/dates.yaml` per practice root, mirroring the `home_plans.yaml` pattern (versioned, locked writes). Entry: `id`, `title`, `date` (ISO), `recurrence` (`none` | `yearly`), `lead_days` (list), `captured_by`, `captured_at`, `notes`.
- **Capture:**
  - Conversational: when dialogue contains a date-worthy commitment, Turtle offers a Keep-style confirm (same offer pattern as continuity confirm / river act offers — reuse, don't invent). On confirm, entry written verbatim-titled.
  - Typed: `!date <when> <what>` for direct capture; `!dates` lists upcoming.
- **Surfacing:**
  - Hook the existing hourly scheduled loop (the `run_scheduled_daily_note` heartbeat): once per day per root, check registry against lead times; due reminders post as river acts in the owning channel.
  - Upcoming dates (next N days) render into the daily note context and the home attunement packet, so ambient awareness costs nothing.
- **Dedup/state:** per-root done-map keyed by `(entry_id, lead_day, date)` — same idempotency pattern as scheduled daily notes.

## Not in this slice

- Calendar-system sync (CalDAV/Google) — integration tax; revisit only if the registry demonstrably fails.
- Recurrence beyond `yearly` — no rule engine.
- Per-member notification preferences beyond per-entry lead times.
- Any web/dashboard surface — river acts and chat queries are the interface.

## Verification expectations

TDD: registry round-trip, lead-time due computation (incl. yearly rollover and `de` locale date parsing at capture), idempotent scheduled surfacing, routing (family-root date never surfaces in a private river and vice versa). Suite green via `./scripts/spirit_verify.sh` before review.

## Capture vocabulary (amended 2026-08-06)

The first slice shipped Design law 1 only halfway. Both capture paths accepted a
date **only when written as digits** — ISO `2026-12-24` or German `24.12.` — while
`_MONTHS_DE`, `_MONTHS_EN`, `_WEEKDAYS_DE` and `_WEEKDAYS_EN` sat in the module
serving `human_date()` alone. Turtle could echo "Samstag" back to a member and
could not read it. Two days after the announcement reached five rivers,
`state/dates.yaml` existed in zero roots, and the metric could not distinguish
*no date arose* from *a date arose in the form people use*.

**Now accepted, both paths:** month names day-first or month-first, with or
without a year (`24. Dezember`, `December 24, 2029`, `Dez 24`); weekday names
with optional qualifier (`Samstag`, `nächsten Samstag`, `next Saturday`), read
as the next strictly-future occurrence; and relative words (`heute`, `morgen`,
`übermorgen`, `nächste Woche`, `in 3 Tagen`, and their English forms). Two-letter
weekday abbreviations are typed-command only — `so`, `do` and `mi` are ordinary
German words and would fire the offer constantly. `!date` now takes a
multi-token when (`!date 24. Dezember Kita Fest`), and an explicit year in any
accepted form buys the birthday "turns N".

**Conversational capture is two-tier**, because a river is not a calendar:

| Tier | Forms | Fires |
|------|-------|-------|
| 1 | numeric, month-name | on its own — writing `24. Dezember` is already deliberate |
| 2 | weekday, relative word | only alongside a commitment cue (birthday, appointment, Fest, "bitte erinnern", …) |

Without the tier-2 gate, *"Ich gehe morgen noch schnell einkaufen"* produces a
Keep offer. The restraint stage of `scripts/shake_dates.py` is the control that
pins this, and it fails as expected when the gate is disabled.

**Still scaffolding.** The cue list is a hand-built rule of exactly the kind the
bitter-lesson stance says to replace with model judgment once the river shows
misses. The upgrade path is unchanged: classify the turn instead of matching it.

## Open questions

1. ~~Recurrence for birthdays with ages ("turns 5")~~ — shipped; birth year optional, and never invented when the member wrote no year.
2. Locale of reminder copy — registry locale exists (`de`); reminder acts should honor it.
3. Whether `!dates` belongs in the practitioner command allowlist immediately (recommend yes — read-only).
4. When to replace the tier-2 cue list with model classification — needs a real miss to justify the per-turn cost.
