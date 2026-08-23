"""`core/` — the layer that does not know a chat platform exists.

**The rule, and it is checked:** nothing in this package may import a module
outside it. No root module, no transport library, no `runtime/` adapter. Only
the standard library, third-party packages, and each other. `tests/test_core_layer.py`
fails the build otherwise.

**What "core" means here, precisely.** The outside review's shorthand was
"no I/O, no transport". Only the second half is measurable, and it is the half
the decision rests on — *don't close the door to switching transports*. So core
means **transport-free**, not I/O-free: `atomic_io` writes files and belongs
here, because a shared write primitive is exactly what a bottom layer is for.
Saying "no I/O" and then shipping `atomic_io` in it would be a claim the tree
contradicts on sight.

**Why these ten and not the fifteen that measured transport-free.** Three were
excluded for reasons a static import graph cannot see, and finding them is the
argument for looking before moving:

- `cli.py` — an operator entry point (`cli.py update check`), documented in
  ARCHITECTURE.md and invoked as a script. Entry points sit at the top of a
  layer stack, not the bottom.
- `canary.py` — loads `discord_bot.py`, `tos_tools.py` and `mage.py` **by file
  path** at runtime. Statically it imports no transport; in practice it depends
  on all of it, and `Path(__file__).parent` would have silently resolved to
  `core/` after a move.
- `twitter_ops.py` — reads `.env` as `Path(__file__).parent / ".env"` at import
  time. Moving it relocates that lookup, and a credential file that silently
  fails to load is this codebase's favourite kind of defect.

`outfacing.py` stays at the root as well: it is a twelve-line tombstone for a
retired feature, and a tombstone is a record, not a layer member.

The set is dependency-closed — only `workspace_refresh` imports a sibling
(`prepared_eddies`), and everything else is a leaf.
"""
