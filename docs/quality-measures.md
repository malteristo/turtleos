# Quality Measures

**How to tell whether this codebase is getting better or worse.**

Established 2026-08-14, after a session that found six defects sharing one shape:
something declared in English that nothing enforced. This document exists because
"is it improving?" was not answerable, and an unanswerable question gets answered
by mood.

**Adopted by the operator 2026-08-15**, in his words: *"it's the best measure we have
for now. We may find better ones in the future, but this one will do."* That matters
in two directions and both are load-bearing. It is no longer a proposal, so the claim
in `AGENTS.md` that quality is judged here is now true rather than aspirational — the
usual defect in this repo, caught before it aged. And it was adopted **provisionally on
purpose**: a better measure is welcome and needs no permission to be proposed. What the
provisionality does not license is quiet drift. Replacing a measure is a decision, with
a date and a reason recorded here. A measure that simply stops being computed is the
exact failure these four exist to catch.

Structural numbers here are **generated**, not typed — `scripts/quality_baseline.py`
computes them. That is deliberate. A document holding hand-copied metrics is the
exact shape that let `docs/acceptance/README.md` drift 41 commits behind: it asked
its reader to remember, and remembering is not a mechanism.

```bash
python3 scripts/quality_baseline.py          # report
python3 scripts/quality_baseline.py --row    # a row to append below
```

---

## What is deliberately not measured

**Test count.** Rises with activity and with padding. 1,158 tests that assert the
shape of the code protect nothing.

**Lines of code.** Says how much was written, not whether it can be changed.

**Defects found per session.** Rises when you look harder. A session that finds
six defects is a *better* session than one that finds none, which makes the raw
count an incentive to look away.

All three go up when things go well and up when things go badly. They are
activity, not quality.

---

## The four measures

### 1. Time-to-detection

**For each defect found, how long was it live?**

This is the primary measure for this codebase specifically, because its
characteristic failure is not a crash — it is silence. Something stops working,
nothing says so, and the behavior that replaces it is indistinguishable from
normal. Every defect in the founding session was of that kind.

**How to observe it:** when a defect is found, `git log -S"<the defective code>"`
to date its introduction, and record the interval. Append to the ledger below.

**Falling** means the system has started telling you things.
**Rising** means features are being added faster than instruments.

### 2. Recurrence after a fix

**After a defect is fixed, does its class come back?**

The sharpest available signal, because it measures whether fixes are cases or
classes. On 2026-08-14 the same shape — *an id that might be a thread, looked up
in a registry that holds only parents* — appeared three times in one day, in code
sharing no vocabulary and no symbol. The first fix was correct and did not
generalize.

**How to observe it:** every ledger entry names a class. A second entry naming an
existing class is a recurrence. Target: no third instance of any class, ever.

### 3. Claim coverage on new work

**Of the claims a change adds, how many are backed by something that fails?**

A claim is any assertion about behavior that a reader would rely on: a comment
stating an invariant, a constant naming a limit, a docstring describing a
guarantee, a README describing a gate. This is the measure that directly opposes
this project's structural bias, because prose describing code is produced for
free while enforcement is produced only on request.

**How to observe it:** per change, not as a global audit. For each claim added,
either a check exists that fails when the claim is false, or the claim is written
as a *decision with a reason* rather than a guarantee (see `runtime/offers.py`
`UNCOUNTED` for the shape). "We meant to" and "we decided not to" must not look
identical in the tree.

### 4. Deletability

**Can a feature be removed, with the suite localizing the damage?**

Everybody measures whether a system is easy to add to. Adding is what organic
growth is already good at. Removal is where hidden coupling surfaces, and it is
the difference between maintainable and merely working.

**How to observe it:** occasionally delete a real feature on a branch, run the
suite, and count how many failures are *about that feature* versus incidental. A
clean localization means the seams are real.

---

## Structural series

Append a row per measurement, do not edit old rows. A baseline is a historical
fact; re-measuring is an act, not a state.

Three numbers here are *goals* rather than context.

**runtime lines unused** is the sharpest and the newest. An independent review on
2026-08-14 found that `runtime/messages.py` — the documented seam between a chat
platform and the runtime, with the best test in the repository guarding it — had
**zero production importers**. Five `runtime/` modules and 466 lines were tested,
enforced, and never executed. The boundary guard was real and passing; nothing
crossed the boundary it guarded, and its own excellence is what made the gap
durable, because a green test reads as a working architecture. This number can
only fall by a production path actually constructing a value object. Moving a file
does not move it.

**transport boundary exemptions** and **modules importing transport** are the same
story at two scales. Both should fall, and only because a module stopped needing a
transport.

**Two numbers live outside this table on purpose.** The layering ratchet —
largest runtime import cycle (**53 of 115 modules**) and hub fan-in (`mage`,
**63 importers**) — is measured by `scripts/import_graph.py` and pinned by
`tests/test_import_graph.py`, because it is a ceiling that fails a build rather
than a series that gets appended.

**Read the last row against those two.** `root modules` fell 95 → 84 and
`packages` rose 3 → 4 when `core/` was created and `tools.py` deleted — and the
cycle and the fan-in **did not move at all**, because ten modules changed
directory and no dependency was removed. That is the intended reading: this table
records shape, the ratchet records coupling, and only the second one can be
improved by moving a file if you are not careful. It cannot, because it counts
packages. The reading that matters: the
module-level graph is *acyclic*, and adding back the 308 imports written inside
function bodies collapses half the codebase into one component. Rationale and
the first cut: `docs/chapters/design-layer-boundaries.md`.

| date | root modules | packages | modules ≥1000 lines | prod LOC | test LOC | test:prod | tests | importing transport | boundary exemptions | runtime lines unused |
|------|--------------|----------|---------------------|----------|----------|-----------|-------|---------------------|---------------------|----------------------|
| 2026-08-14 | 93 | 3 | 7 | 46241 | 19789 | 0.43 | 1171 | 45 | 2 | 466 |
| 2026-08-14 | 94 | 3 | 7 | 46678 | 20972 | 0.45 | 1248 | 46 | 2 | 241 |
| 2026-08-14 | 95 | 3 | 7 | 46837 | 21651 | 0.46 | 1261 | 46 | 2 | 241 |
| 2026-08-15 | 95 | 3 | 7 | 47034 | 22658 | 0.48 | 1325 | 46 | 2 | 241 |
| 2026-08-15 | 95 | 3 | 7 | 47256 | 22829 | 0.48 | 1334 | 46 | 2 | 241 |
| 2026-08-15 | 84 | 4 | 7 | 47227 | 23004 | 0.49 | 1340 | 46 | 2 | 241 |

The 2026-08-15 row is the first tests-collected number this table can defend.
Until that morning `_test_count` read the digit out of pytest's summary line and
ignored the rest of it, so `1297 tests collected, 3 errors` reported **1297** —
the count of what imported, with the files that did not silently dropped and no
signal that any had. Its docstring already promised *"None when collection fails
— never a guess"*; a partial failure was simply never treated as a failure. The
count now refuses rather than guesses: any collection error at all and the cell
reads `—`. **A measure blind to a whole test file disappearing is this
document's own failure mode, one level up.**

Run it with an interpreter that has the runtime dependencies installed — the
repo venv, not a bare system python. A bare interpreter now honestly reports `—`
where it used to report a confident undercount.

*Founding note: an earlier hand count in the same session gave 0.51 and 40, by
measuring only the repo root and grepping for imports. The script counts
subpackages and parses imports as syntax, which is why these numbers are lower
and higher respectively. The script's numbers are canonical because they are
reproducible.*

---

Two rows carry the same date, and the date cell stays a bare date because
`test_quality_measures` requires the series to remain machine-readable. The
**second** row is the later measurement, taken after the enforcement slice (pre-push
gate and CI, lazy client construction, the link offer routed through the transport
seam). **runtime lines unused fell 466 → 241** because `messages.py` and
`adapters/discord.py` became load-bearing; `importing transport` rose by one because
`discord_render.py` is new and is *supposed* to import Discord — it is the renderer.
That is the reading discipline this table needs: the number moving is a question, not
a verdict.

## Time-to-detection ledger

Append-only. One row per defect, dated by the commit that introduced it.

| found | defect | introduced | live for | class |
|-------|--------|------------|----------|-------|
| 2026-08-14 | Offer ledger recorded nothing; report said "no data yet" | 2026-08-06 | 8 days | thread id looked up in a parent-only registry |
| 2026-08-14 | Attunement resolved to the global default inside any thread | 2026-08-06 | 8 days | thread id looked up in a parent-only registry |
| 2026-08-14 | Offer suppression recorded nothing | 2026-08-06 | 8 days | thread id looked up in a parent-only registry |
| 2026-08-14 | `runtime/` claimed transport independence, unenforced | 2026-05-06 | 100 days | declaration with no mechanism |
| 2026-08-14 | Acceptance catalogue gated two shakes covering nothing | 2026-06 (approx) | 41 commits | declaration with no mechanism |
| 2026-08-14 | `EXA_TIMEOUT_SECONDS` declared, passed to nothing | 2026-08-13 | 1 day | declaration with no mechanism |
| 2026-08-14 | Every tool call froze every channel until it returned | 2026-03-31 | 136 days | blocking work on the event loop |
| 2026-08-14 | `!diagnose` ran the whole canary board on the event loop | 2026-04-27 | 109 days | blocking work on the event loop |
| 2026-08-14 | `!search` walked the practice tree on the event loop | 2026-06-20 | 55 days | blocking work on the event loop |
| 2026-08-14 | Four CLI fetchers dead; readiness reported them installed | 2026-04-06 | 130 days | presence checked where function was meant |
| 2026-08-14 | Tool execution blocks the event loop | 2026-03-31 | 136 days | consequence invisible until a slow tool arrived |
| 2026-08-14 | `runtime/` seam documented as shipped; nothing constructs it | 2026-05-06 | 100 days | declaration with no mechanism |
| 2026-08-14 | Pre-push gate exited 0 on empty stdin — every push allowed | 2026-08-14 | 4 minutes | skip path reachable by accident (fail-open) |
| 2026-08-14 | Regex found 4 of 9 module-level client bindings | 2026-08-14 | minutes | regex-shaped search for an AST-shaped question |
| 2026-08-14 | Before/after probe reported a clean tree while importing nothing | 2026-08-14 | minutes | failure counted as absence (fail-open) |
| 2026-08-14 | Decline-button guard blinded by labels moving into `Action` | 2026-08-14 | 0 (same commit) | value left a literal; static guard kept passing |
| 2026-08-14 | Chapter test required "no production importers" after it became false | 2026-08-14 | 0 (same commit) | guard pinning a claim that had gone stale |
| 2026-08-14 | Every `discord.ui.View` subclass is a mock in half the suite; no view body ever ran | 2026-04 (approx) | ~130 days | stub silently replaced a base class |
| 2026-08-14 | Turtle and River each built the other bot's client; one always a zombie | 2026-06-19 | 56 days | rule written as a docstring, no mechanism |
| 2026-08-15 | Artifact-read test 403s on Mini (token in `.env`); green on Forge | 2026-06-30 | 46 days | test inherits production env |
| 2026-08-15 | `tests collected` reported the number that imported, dropping the rest | 2026-08-14 | 1 day | presence checked where function was meant |
| 2026-08-18 | §3.2 packet persistence named; `current.yaml` debounce was the only write | 2026-08-11 | 7 days | declaration with no mechanism |
| 2026-08-18 | Artifacts the save tool wrote to `state/notes/` never reached the reviewer; the Forge pull took `navigator-*.md` only | 2026-06-29 | 50 days | reader allowlist narrower than the writer |
| 2026-08-18 | A second spec→module index lived inside `ARCHITECTURE.md` — 26 rows, a spec version behind, one row still calling shipped work pending — through the consolidation whose stated job was to leave exactly one | 2026-06-20 | 59 days | duplicate enumerated by name, not by shape |
| 2026-08-30 | Leave only logged; join told the operator to `!admin invite` | 2026-07-28 | 33 days | destination written as current topology |

Two classes account for seven of nine. That is the finding this document was
created to keep in view.

**The last row adds a new class, and the reason it survived 50 days is the part
worth keeping.** The reader (`sync_practice_root.sh`) and its guard
(`check_turtle_state.py`) were written in the same commit, so the guard globbed
the same one filename prefix the reader did. A check written beside the thing it
checks inherits its assumptions — it can only ever confirm that the code does
what its author believed. The generalisation now runs against the Mini rather
than a remembered mapping table: any top-level directory being written on the
host with no reader on Forge is reported by name, and a path deliberately not
carried has to say why.

**The index row is a class of its own, and it was found by a question, not a
sweep.** The operator asked why two files were both called architecture. The
answer was a leaked boundary — and behind it, a duplicate index that the
2026-08-02 consolidation had not counted, because that consolidation enumerated
the documents it knew were indexes rather than everything shaped like one. A
table inside a file named for something else is invisible to a list of names.
The guard now runs on shape: `tests/test_doc_topology.py` fails on any tracked
markdown file outside the matrix carrying five or more rows that open on a spec
section, and it fires on the pre-deletion file at 26 rows (verified). The same
test resolves every relative link in the tree, since a rename is what breaks
those, and pins the sync mapping to the one file that is allowed to state it.

**Recurrence, recorded against measure 2.** The last row is the fourth member of
*presence checked where function was meant* — after the readiness report calling
four dead CLI fetchers installed, and the offer guard that verified the test
suite wrote nothing while never verifying a real offer wrote something. This one
is in the measurement layer itself: the instrument that counts the tests could
not tell a test file that failed to load from a test file that does not exist.
The class has now appeared where it is hardest to see, which is what a third and
fourth instance are for.

The last row was found by an **outside reviewer with no knowledge of the practice,
on the same day the seam was written** — and it names the failure the reviewer
called the most durable one here: *a guard whose quality makes the gap it does not
close invisible*. Worth recording that it took an outsider, and that the number it
produced (466 lines) is now generated on every run rather than remembered.

---

## The bias this codebase is correcting for

Worth stating plainly, because it explains why the measures are these and not the
usual ones.

This codebase is written by AI agents directed by a non-programmer who specifies
desired behavior in plain English and does not read the implementation. That
arrangement has a specific and predictable failure mode:

**A model asked for a behavior returns the behavior plus prose asserting the
behavior.** The prose costs nothing. Enforcement costs a test that must fail
first. So declarations accumulate faster than checks — and the operator's review
surface is the prose, which is the one layer that cannot be wrong. Nothing in a
comment distinguishes *what the code does* from *what someone wanted it to do*.

The correction is not for the operator to learn to read code — that would make
him a slow reviewer of the layer least likely to be wrong. The correction is:

- **Every behavior description carries its observable absence.** Not "the link
  offers a transcript" but "if this broke, the button would say the wrong thing
  and nothing would tell me." A falsifiable description forces a check.
- **Any agent writing here treats the enforcement layer as owed, not requested.**
  A guard is part of the change, not a follow-up.
- **A declaration with no mechanism is a defect**, even when the code happens to
  be correct — because it will stop being correct silently.

See `docs/learnings.md` for the individual cases, and `AGENTS.md` § *Who directs
this codebase* for what it asks of an agent working here.
