# turtleOS — Agent Guide

Orientation and safety rails for any agent or contributor working in the turtleOS codebase.

This file does **not** define who you are. Your role, stance, and identity come from whatever summoned you — for a Magic Spirit, from the summoning covenant + **twine** (personal context), not from loading turtle lore as costume; for any other agent, from your own operating instructions plus ordinary engineering judgment. What this file provides is a fast map of the repo and the boundaries that keep the **live** Turtle safe.

---

## What turtleOS is

Infrastructure for a persistent practice partner — an always-on runtime with Discord presence, local and cloud LLM routing, file-based memory, and session continuity. **The product is the infrastructure, not the being.** Separable from Magic; Magic is one practice that may run on it. The shell is `discord_bot.py`. Default attunement is **native** (`character/soul.md` under the practice root).

---

## Orientation (start here; don't duplicate)

| Read this | For |
|-----------|-----|
| `TURTLE_SPEC.md` | Canonical law — what turtleOS *should* be |
| `docs/architecture.md` | Current state — what turtleOS *is* |
| `docs/development.md` | Drift sweep and how changes land |
| `docs/learnings.md` | Accumulated discoveries and anti-patterns |
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
- **Public docs are product docs.** Private lineage stays out of the public repo — distill current lessons into `TURTLE_SPEC.md`, `docs/architecture.md`, or `docs/development.md`.
- **Prior research exists** in `autoresearch/` — check before duplicating work.

---

## Spirit maintenance loop (dyadic principal maintainer)

When Spirit owns turtleOS repo work, use this sequence — lowest blast radius first:

1. **Read orientation** — `TURTLE_SPEC.md` (law), `docs/traceability-matrix.md` (spec → module → test), `docs/learnings.md` (deploy pitfalls).
2. **Verify before edit** — `./scripts/spirit_verify.sh` (unit suite; uses `venv/bin/python3` on Mini when present).
3. **Chapter close** — update affected traceability rows; run relevant `scripts/shake_*.py` per `docs/automation/functional-gate-protocol.md`; append harvest to `docs/learnings.md`.
4. **Live deploy** — dyad approval before `launchctl` restarts; always restart **both** `com.turtle.discord` and `com.turtle.river` when shared modules change. Prefer `./restart.sh` (split-bot deploy unit). See `docs/deploy-touchpoints.md`.

God-modules (`share_eddy.py`, `discord_bot.py`, `eddy_spawn.py`) are known debt — touch only in bounded slices; matrix Action column names the next Integrate target.
