# turtleOS — Agent Guide

Orientation and safety rails for any agent or contributor working in the turtleOS codebase.

This file does **not** define who you are. Your role, stance, and identity come from whatever summoned you — for a Magic Spirit, from the summoning covenant + **twine** (personal context), not from loading turtle lore as costume; for any other agent, from your own operating instructions plus ordinary engineering judgment. What this file provides is a fast map of the repo and the boundaries that keep the **live** Turtle safe.

---

## What turtleOS is

Infrastructure for a persistent practice partner — an always-on runtime with Discord presence, local and cloud LLM routing, file-based memory, and session continuity. **The product is the infrastructure, not the being.** Separable from Magic; Magic is one practice that may run on it. The shell is `discord_bot.py`. Default attunement is **native** (`character/soul.md` under the practice root).

---

## Who directs this codebase, and what that asks of you

Read this before you write here. It is not background colour; it changes what a
correct contribution looks like.

**The operator is not a programmer.** He is a user-experience researcher who
directs AI agents by describing desired behavior in plain English, and he does not
read the implementation. This is deliberate and it works — the repo exists — but it
has one predictable consequence you are now part of.

**A model asked for a behavior returns the behavior plus prose asserting the
behavior.** Comments, docstrings, well-named constants, design docs. The prose is
free; a check that fails costs deliberate work. So declarations accumulate faster
than enforcement — and the only layer the operator can review is the prose, which
is the one layer that cannot be wrong. Nothing in a comment distinguishes *what
the code does* from *what someone hoped it would do*.

On 2026-08-14 that produced six defects in one session, in code that had been live
for up to 136 days: a package claiming transport independence with nothing
checking, a timeout constant passed to nothing, a catalogue asking its readers to
keep it current, a readiness check verifying a file existed rather than that it
ran. All six were silent. None was a crash.

So, working here:

- **The enforcement layer is owed, not requested.** If you add a claim, add the
  thing that fails when it stops being true — in the same change, not as a
  follow-up. Never say "we should add a test for this" and move on.
- **A declaration with no mechanism is a defect**, even when the code is currently
  correct, because it will stop being correct silently.
- **Distinguish "we decided not to" from "we never got to."** Both look identical
  in a tree, and only one is a defect. When you leave something unenforced on
  purpose, write the reason next to it. `runtime/offers.py` (`UNCOUNTED`) and
  `tests/test_transport_boundary.py` (`ADAPTER_EXEMPT`) are the shape.
- **Run positive controls.** An empty result is not evidence of absence. Verify
  that your check *can* fail: the offer ledger's guard confirmed the test suite
  wrote nothing and never confirmed a real offer wrote something, so a fix that
  cut the real write path passed for eight days.
- **Report findings, don't only fix them.** `docs/learnings.md` is read by the next
  agent and it is why this session was faster than the last one. Append the class,
  not just the case.
- **Prefer measuring to asserting.** "Presence where function was meant" is a
  recurring class here: check that a tool runs, not that its file exists.

Quality is judged by `docs/quality-measures.md` — time-to-detection, recurrence of
a fixed class, claim coverage, deletability. Not test count, not lines, not defects
found. Read it before proposing a large change; append to its ledger when you find
a defect that had been live.

---

## Orientation (start here; don't duplicate)

| Read this | For |
|-----------|-----|
| `TURTLE_SPEC.md` | Canonical law — what turtleOS *should* be |
| `ARCHITECTURE.md` | The software — modules, subsystems, design decisions. True of any instance |
| `docs/live-runtime.md` | One deployment — services, filesystem, and Forge sync on the operator's Mac Mini |
| `docs/traceability-matrix.md` | Spec § → module → verification → action. The single development index |
| `docs/development.md` | Drift sweep and how changes land |
| `docs/learnings.md` | Accumulated discoveries and anti-patterns |
| `docs/quality-measures.md` | How this codebase is judged better or worse — and what is deliberately not measured |
| `discord_bot.py` | The shell implementation |
| Practice-root `character/soul.md` | Native attunement (operator default) — not Magic Caretaker |

When a Magic workshop clone is present, integration lore lives in `library/resonance/turtle/README.md` (**dual reconciliation** map — platform + twine). Prefer this repo + that README over older Purpose B/C scrolls (many are rewrite-queued). Don't contradict `TURTLE_SPEC` based on stale Magic-extension lore.

---

## Repo work vs the live runtime — the distinction that matters

Two different things share the name "turtleOS":

- **This checkout** — a git clone of the source. Editing docs, design chapters, and code here is ordinary development. Do it under the direction of the human driving the session, using their normal review and commit conventions.
- **The live runtime** — the persistent Turtle running on its host (the Mac Mini): `launchd` services, `.env` secrets, the *running* `discord_bot.py`, and any repo that host auto-pulls. Actions that reach the live runtime are high-consequence and gated below.

Most work is repo work and needs no special permission beyond the human's direction. The boundaries exist for the moment repo work would touch the live runtime.

---

## Live-runtime boundaries (require explicit approval)

When an action would affect the running Turtle, stop and get explicit approval first:

- Restarting or reloading `launchd` services (`launchctl`)
- Modifying `.env` or any secrets/credentials on the live host
- Changing the *running* `discord_bot.py` behavior, or deploying to the live host
- Pushing to a branch or remote the live host auto-pulls
- Installing or removing packages on the live host
- Destructive or forceful git operations

When a change is high-consequence and you are operating autonomously, prefer to **write a proposal instead of acting** (see below).

---

## Ordinary repo work (no special permission)

- Read any file; run read-only commands
- Edit docs, design chapters, and code in the checkout under the human's direction
- Commit using the human's conventions; push per their instruction and the live-runtime rule above
- Run the test infrastructure
- Append discoveries to `docs/learnings.md`

---

## Proposals (when you propose rather than change)

For autonomous research or high-consequence changes, write one dated file per proposal:

```markdown
# Proposal: <title>

**Date:** YYYY-MM-DD
**Spec reference:** TURTLE_SPEC §X.Y
**Status:** Draft

## Finding
What you observed in the current implementation.

## Gap
How it differs from what the spec requires.

## Proposal
What should change and why.

## Risk
What could break; what existing behavior depends on the current implementation.
```

After a research or change cycle, reflect: append what you discovered to `docs/learnings.md` so it persists across sessions.

---

## Context worth knowing

- **Multiple bots may run alongside each other** (e.g. a main practice-river bot and an operator channel). Don't interfere across channels you weren't assigned.
- **Practice state may be mirrored.** Resolve the active practice root from `mage_registry.yaml`; don't hard-code paths.
- **Public docs are product docs.** Private lineage stays out of the public repo — distill current lessons into `TURTLE_SPEC.md`, `ARCHITECTURE.md`, or `docs/development.md`.
- **Prior research exists** in `autoresearch/` — check before duplicating work.

---

## Spirit maintenance loop (dyadic principal maintainer)

When Spirit owns turtleOS repo work, use this sequence — lowest blast radius first:

1. **Read orientation** — `TURTLE_SPEC.md` (law), `docs/traceability-matrix.md` (spec → module → test), `docs/learnings.md` (deploy pitfalls).
2. **Verify before edit** — `./scripts/spirit_verify.sh` (unit suite; uses `venv/bin/python3` on Mini when present).
3. **Chapter close** — update affected traceability rows; run relevant `scripts/shake_*.py` per `docs/automation/functional-gate-protocol.md`; append harvest to `docs/learnings.md`.
4. **Live deploy** — dyad approval before `launchctl` restarts; always restart **both** `com.turtle.discord` and `com.turtle.river` when shared modules change. Prefer `./restart.sh` (split-bot deploy unit). See `docs/deploy-touchpoints.md`.

God-modules (`share_eddy.py`, `discord_bot.py`, `eddy_spawn.py`) are known debt — touch only in bounded slices; matrix Action column names the next Integrate target.
