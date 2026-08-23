# Building this codebase for the agents who maintain it

**Status:** planning surface, opened 2026-08-15. Nothing here is committed to.
**Premise, from the Mage:** *"you guys are the only ones who will be touching the code anyways."*
**Every number below was measured this session, not estimated.**

---

## What actually makes a codebase hard for an agent

An agent does not read a repository. It reads the file in front of it, plus
whatever it thought to grep for. That single fact reorders the usual priorities:

- **Global structure is invisible.** A human maintainer builds a mental model
  over months. An agent rebuilds one every session from whatever the prompt and
  the first three greps happen to contain. 115 modules with 534 edges means every
  change has an unbounded blast radius that nothing in the file reveals.
- **Prose is trusted at face value.** A comment claiming an invariant reads
  exactly like an invariant that is enforced. This repo has now found that class
  eight times, and the outside reviewer found the sharpest one: *"the guard is
  real, the boundary it guards is not load-bearing, and the guard's own
  excellence is what makes the illusion durable."*
- **Verification is the only ground truth.** An agent cannot feel that something
  is off. It can only run something. Anything that cannot fail is decoration.
- **Scaffolding is contagious.** An agent copies the shape it finds. 331 imports
  inside function bodies exist because the first few were necessary and every
  later one looked normal.

So the ranking below is not "clean code". It is: *what does an agent need in
order to change this system without breaking it unknowingly?*

---

## The board

### A · Delete the test-harness tax

**77 of 121 test files stub `sys.modules["discord"]` before importing anything.**
That stub replaces every `discord.ui.View` base class with a `MagicMock`, which
is why the outside read found that **no view body has ever executed in a test**
(~130 days). It also forces the trunk tests written today to un-stub the package
by hand and reload the module under test, because whether they see the real
`discord.Thread` was otherwise decided by *filename alphabetical order*.

The stub existed because importing anything built a Discord client. **That has
been false since 2026-08-14.** `requirements.txt` is pinned and CI installs it.

- **Do:** delete the stubs, add `discord.py` as a test dependency, let tests
  import the real package.
- **Cost:** mechanical across 77 files; expect a tail of tests that only passed
  because a mock accepted anything.
- **Unblocks:** view bodies become testable at all; `isinstance` branches stop
  being order-dependent; every future test author stops copying the stub.
- **This is a deletion, not an addition** — the best kind available here.

### B · Generate the inventories that keep drifting

`ARCHITECTURE.md` described `tools.py` as *"238 lines, shell/tool helpers
retained for operational use."* It was 152 lines with **zero importers**, dead
since July. `docs/acceptance/README.md` is 20 commits behind; the traceability
matrix was 19 behind when last measured and is 5 now.

Every one of these is a hand-copied fact about the tree, and this project has
already proven the fix works: `quality_baseline.py` generates the structural
numbers and `test_quality_measures.py` binds them, after a hand-maintained table
drifted 41 commits.

- **Do:** generate the module inventory (path, lines, importers, layer) from the
  AST; keep prose *about* modules, delete numbers *of* modules.
- **Cost:** one script, one binding test.
- **Unblocks:** the doc an agent reads first stops lying about the tree it is
  about to change. **Currency is a state; drift is a rate** — rewriting these by
  hand buys one more interval of quiet drift.

### C · Break the 53-module cycle — a campaign, not a slice

Measured today: 220 internal edges among the 53, **132 deferred-only**. No
keystone — lifting out `discord_bot` still leaves **43**; `commands` and
`helpers` leave 46. The heaviest deferrers are `commands` (10),
`eddy_lifecycle_bar` (8), `eddy_spawn` (7), `share_delivery` (7).

- **Do:** treat it as a ratchet, not a project. Each session that touches one of
  those modules removes one deferred edge and lowers the ceiling by one.
- **Cost:** ongoing, near-zero per session.
- **Unblocks:** eventually, layer assignment for the other 75 modules.
- **Explicitly not:** a big-bang restructuring. Nothing measured today supports
  one, and the reviewer argued against exactly that.

### D · Split the two hubs

`mage` 63 importers, `state` 41. `mage` is already scoped: 57 of its 75
functions are transport-free, **32 of 92 importers use only those**, so the split
takes `hub_fan_in` **63 → ~31**. `state.py` is a grab-bag — 37 config constants,
four mutable runtime dicts, the lazy client, and a zombie-access detector in one
file.

- **Cost:** one session each, mechanical after the analysis.
- **Unblocks:** an agent editing registry logic stops loading the transport.
- **Hazard, already found:** `reload_mage_registry()` **rebinds** the module
  global. A naive re-export binds the old dict forever and every reload silently
  changes nothing — in the code that decides which practitioner a channel
  belongs to. Reach the registry through an accessor.

### E · Replace the module-global rebind pattern wherever it appears

D's hazard is probably not unique. A `global X; X = load()` pattern is invisible
to every importer that did `from m import X`, and an agent reading either side
sees nothing wrong.

- **Do:** grep for `global` at module scope, convert each to an accessor.
- **Cost:** an hour, mostly reading.
- **Unblocks:** removes a class an agent cannot see locally — which is the whole
  category this document is about.

### F · Retire the change-detector tests

The outside read estimated **13%** of the suite are change-detectors —
`test_practice_dispatch.py` patches six collaborators to assert one was awaited.
It fails on any behaviour-preserving refactor and passes if the logic inside all
six is wrong. For an agent, that is worse than no test: it *punishes* the
refactoring this document is asking for and *rewards* leaving things alone.

- **Do:** as each is hit during other work, rewrite it against observable
  behaviour or delete it. Not a sweep.
- **Cost:** incidental.
- **Unblocks:** the suite stops arguing against structural change.

### G · Route the remaining writes through `atomic_io`

50 raw write sites against 18 atomic ones, with **two processes sharing the
files** and only an `asyncio.Lock` between them — which gives no cross-process
protection at all. The primitive is excellent and mostly unused.

- **Cost:** mechanical, plus an AST guard so the ratio cannot drift back.
- **Unblocks:** the one failure mode here that corrupts practitioner-visible
  state rather than crashing.

---

## What is deliberately not on the board

- **Splitting the seven 1000-line modules.** The reviewer's argument holds and I
  agree: splitting inside a flat namespace with no dependency rule yields more
  modules and more edges. Do it *after* the layer rule exists to receive the
  pieces.
- **A linter or type checker.** Cheap and probably worth it, but it is not a
  robustness change and it will generate a large diff that hides real ones.
  Separate session, separate commit.
- **Rewriting the untested orchestration in bulk.** 36 functions ≥60 lines are
  named in no test (3,484 lines). The trunk was the important two; the rest
  should be tested when touched, not swept.

---

## Recommendation

**A first.** It is a deletion, it makes every later test better, and it is the
only item that removes a tax every future session currently pays. **B second** —
it is one script and it stops the docs from lying to the next agent. Then **D**
for the first ratchet movement, with **C**, **E**, **F**, **G** as ongoing habits
rather than projects.

The through-line: *this codebase is already good at knowing whether it works.*
Its test-to-production ratio is 0.49 at 130 days old, with AST-level invariant
guards and a nightly gate. What it is not yet good at is **letting a reader see
the system from any one file**. Every item above buys that, and only that.
