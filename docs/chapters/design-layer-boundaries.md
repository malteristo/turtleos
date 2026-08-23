# Layer boundaries — the ratchet before the restructuring

**Status:** instrument, ratchet, and the first layer shipped 2026-08-15. `core/` holds ten modules and is enforced.
**Rule:** `core/` → `services/` → `transport/`. Dependencies point one way. **`core/` means transport-free, not I/O-free** — see below.
**Enforced by:** `scripts/import_graph.py` + `tests/test_import_graph.py` (the ratchet), `tests/test_core_layer.py` (the boundary).

---

## What was actually wrong

An independent review on 2026-08-14 ranked this as the highest-leverage
restructuring available by six-month cost, and gave the argument in a form
specific to how this codebase is built:

> An agent cannot see the global structure — it sees the file in front of it, so a
> flat namespace with 471 edges gives every agent change an unbounded blast
> radius. An enforced layer boundary converts architectural discipline from
> something a human must notice into something the codebase refuses to violate.

It also named `683 imports deferred inside function bodies` as "not style but
load-bearing scaffolding holding a cycle-ridden graph together, and it makes the
true dependency graph invisible to static analysis."

That was a claim about structure with no instrument behind it. Measured
2026-08-15, it is sharper than the review said:

| | |
|---|---|
| module-level import edges | 227 |
| cycles at import time | **0** |
| imports written inside function bodies | 308 (across 66 of 95 modules) |
| cycles counting those | 2 |
| **largest such cycle** | **50 modules** |
| `mage` importers | 61 of 95 |

**The module-level graph is acyclic. Add the deferred imports back and half the
codebase collapses into one strongly connected component.** The zero at import
time is not health; it is the cycles having been moved somewhere that does not
raise at boot. `dialogue_turn` alone defers 13 imports, `river_eddy_seneschal`
16.

That 50 is the layering problem stated as one number. `core/` → `services/` →
`transport/` is a proposal to break that component. Until it shrinks, no amount
of moving files has changed anything — and moving a file between directories
does not move it. Only removing a dependency does.

## Why the check ships before any module moves

The worked example is in this repository. `runtime/__init__.py` claimed *"This
package is intentionally independent of Discord"* for **100 days** with nothing
checking it, and the claim turned out to be true and worthless — the seam had
zero production importers. It became real the week a test made violating it
impossible, and then `runtime lines unused by production` ratcheted 466 → 241
because a number nobody could fudge was attached to the work.

So: baseline and guard first, moves second, each move visible in the number or
not a move. The alternative — reorganise now, measure later — is how a flat
namespace becomes a nested namespace with the same 475 edges, which the review
warned about directly when it argued *against* splitting the god-modules first.

**The ceilings are recorded facts, not targets.** `LARGEST_RUNTIME_CYCLE = 50`
and `HUB_FAN_IN = 61` may be lowered by a change that removes a dependency, and
lowering them is the point. A change needing them raised is a change that made
the tangle worse, and it has to say so in the diff. A companion test fails if a
ceiling drifts *above* the real number, because a slack ceiling is not a ratchet
— that is how a guard goes on passing through the next fifty edges somebody adds
back.

## The first cut, and what it cost the number

**Ten modules moved into `core/` on 2026-08-15. Every number in the table above
stayed exactly the same.** Cycle 53, `mage` fan-in 63, 263 module-level edges.

That is the design working, not the design failing. The chapter said *moving a
file between directories does not move it; only removing a dependency does*, and
the first move is the proof — a restructuring that reorganised ten files and
removed zero dependencies bought exactly zero. Any measure that had improved
would have been measuring the directory tree.

**What the move did buy** is the one thing a directory can buy: those ten
modules can never be pulled back into the tangle, because `tests/test_core_layer.py`
fails the build if anything in `core/` imports upward. The floor is now a floor.

### `core/` means transport-free, not I/O-free

The review's shorthand was "no I/O, no transport". Only the second half is
measurable, and it is the half the decision rests on — *don't close the door to
switching transports*. `atomic_io` writes files and belongs in `core/`, because a
shared write primitive is exactly what a bottom layer is for. Claiming "no I/O"
while shipping `atomic_io` inside it would be a claim the tree contradicts on
sight, which is the failure this whole chapter is downstream of.

### Three modules the static measure could not judge

Fifteen modules measured transitively transport-free; ten moved. The three
exclusions are the argument for looking before moving:

- **`cli.py`** — an operator entry point (`cli.py update check`), documented and
  invoked as a script. Entry points are the top of a layer stack, not the bottom.
- **`canary.py`** — loads `discord_bot.py`, `tos_tools.py` and `mage.py` **by
  file path** at runtime. Statically it imports no transport; in practice it
  depends on all of it, and `Path(__file__).parent` would have silently
  re-rooted to `core/`.
- **`twitter_ops.py`** — reads `.env` as `Path(__file__).parent / ".env"` at
  import time. Moving it relocates that lookup, and credentials that silently
  fail to load are this codebase's signature defect.

`outfacing.py` also stayed: twelve lines of tombstone for a retired feature. A
tombstone is a record, not a layer member.

**And one module left entirely.** `tools.py` — 152 lines, superseded by
`tos_tools.py`, **zero importers static or dynamic**, last touched by the commit
that retired the Magic-era surfaces in July. ARCHITECTURE.md described it as
"238 lines, retained for operational use", wrong in the count and wrong about
the use. Deleted.

### What a module move actually touches

Three kinds of reference name a module, and only the first is obvious:

1. **import statements** — 36 files, rewritten from the AST.
2. **`mock.patch` string targets** — `patch("atomic_io.os.replace")`. Invisible
   to any import-aware tool.
3. **path literals** — `canary.py`'s compile-check list, and a test reading
   `offload.py` off disk to assert on its source.

A first pass rewrote quoted strings repo-wide and corrupted three unrelated
things: `"models"` (an Ollama API response key), `"capabilities.py"` (a filename
in a list), `"record_gaps"` (a bundle key). **The name of a module and the word
that spells it are not the same thing** — reverted, and redone from the AST with
the two string cases handled explicitly.

## What is in `core/`, and what is next

```
atomic_io   capabilities   models        offload      prepared_eddies
prepared_surface  record_gaps  self_heal  url_validate  workspace_refresh
```

Dependency-closed: nine are leaves, and `workspace_refresh` imports
`prepared_eddies`. Forty-six modules import `discord` directly and are
`transport/` or want to become `services/`; the remainder is the work.

**What is deliberately not decided:** the assignment of the other 75 root
modules. Doing that by hand would be the same mistake in a new place — a taxonomy
written ahead of the measurements that justify it.

## Two numbers, two different jobs — a correction

An earlier draft of this chapter proposed splitting `mage` or `state` as the next
move "whose success or failure the ratchet can report", implying it would shrink
the 53. **It would not. `mage` and `state` are not in the cycle.** They are
heavily-imported leaves: everything imports them, they import almost nothing.

The two ratchets measure different diseases and have different cures:

| ratchet | what it measures | what shrinks it |
|---|---|---|
| `largest_runtime_cycle` = 53 | mutual dependency inside the Discord surface | cutting edges *between* `commands`, `discord_bot`, `dialogue_turn`, the `eddy_*` and `cmd_*` modules |
| `hub_fan_in` = 63 | blast radius of one module's change | splitting `mage`, so importers depend on the part they use |

**The cycle has no keystone.** Measured by lifting each member out in turn: the
best single removal is `discord_bot`, and the component still stands at **43**.
`commands` and `helpers` leave 46. There are 220 internal edges among the 53
modules, **132 of them deferred-only** — the scaffolding, spread across
`commands` (10), `eddy_lifecycle_bar` (8), `eddy_spawn` (7), `share_delivery`
(7). That is a long campaign, not a slice, and it is honest to say so before
starting it.

**The fan-in is a slice, and it is now unblocked.** See below.

## The one-line coupling under the most-imported function

`mage.get_pd()` resolves the practice directory and is imported by **34
modules** — the single most-depended-on function in the codebase. On 2026-08-15
it was transport-coupled, four levels down and one line wide:

```
get_pd → _resolve_primary_practice_dir → _infer_primary_workshop_dir
       → _resolve_dialogue_channel_id → state (owns the Discord client)
```

`_infer_primary_workshop_dir` runs **only when `mage_registry.yaml` is missing**,
and it wanted the dialogue channel id as a **tiebreaker** for scoring candidate
workshop directories. So practice-directory resolution — called on every turn,
imported everywhere — reached through the module that owns the client, to read a
number, in a fallback.

`CHANNELS` is a dict of environment-derived ids. It moved to `core/config.py`;
`state.py` re-exports it so every existing caller is untouched. No behavioural
change, and **`mage` went from 42 transport-free functions of 75 to 57**, with
`get_pd` and `get_runtime_dir` — 34 and 24 importers — now among them.

The suite caught the one real consequence and it is worth keeping: a test
patching `state.CHANNELS` stopped affecting `mage`. **The patch target was the
assertion about the layer**, and it now names `mage.CHANNELS`.

### The next slice, with its payoff and its hazard measured

`core/mage_registry.py` takes the 57 transport-free functions; `mage.py` keeps
the 18 that need `discord` or a live channel. **32 of the 92 importers use only
names from the pure set**, so their edge moves off the hub: `hub_fan_in` **63 →
roughly 31**. That is the first change in this campaign that moves a ratchet.

**The hazard, named before the work starts.** `reload_mage_registry()` *rebinds*
the module-global `_MAGE_REGISTRY`, and `maybe_reload_mage_registry()` is
load-bearing for the split-bot deploy — River claims, Turtle observes the file
without restarting. A naive split where `mage.py` does
`from core.mage_registry import _MAGE_REGISTRY` binds the **old dict forever**:
every reload would appear to succeed and change nothing, silently, in the code
that decides which practitioner a channel belongs to. The 18 remaining functions
must reach the registry through an accessor, not a name. This is the exact defect
class this repo keeps paying for, visible in advance for once — so it gets built
that way rather than found that way.

## How to read the instrument

```
python3 scripts/import_graph.py          # human-readable, with the cycle listed
python3 scripts/import_graph.py --json   # machine-readable
```

`import_time_cycles` is an invariant — non-zero means the bot will not start.
`largest_runtime_cycle` and `hub_fan_in` are the two ratchets. Everything else is
context.

## Related

- `tests/test_transport_boundary.py` — the same mechanism at a smaller scale, and the proof it works here.
- `docs/quality-measures.md` § Structural series — where the numbers this work moves are recorded.
- `tests/test_dialogue_turn_trunk.py` — the trunk's tests, which this restructuring will lean on; standing up one call to `continue_dialogue_turn` takes 26 patched boundaries and exceeds CPython's static nesting limit. That is the 475-edge tangle expressed as a cost paid per test.
