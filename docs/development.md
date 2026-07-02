# turtleOS Development Standard

turtleOS is in production. The public repository should describe the current product, not the private lineage that produced it.

## Production Standard

A change is ready to push when it is coherent from law to implementation:

1. **Spec:** `TURTLE_SPEC.md` names the behavior, boundary, or capability at the right level of abstraction.
2. **Implementation:** the shell implements the behavior, or the gap is explicitly marked in `ARCHITECTURE.md`.
3. **Operations:** active operator docs and prompts point to the current topology.
4. **Verification:** the change has been checked at the level its consequence requires.
5. **Public surface:** private lineage, local operator facts, and practitioner-specific state are not exposed as current product knowledge.

Production does not mean perfect. It means the repository does not knowingly publish contradictions between spec, docs, and runtime behavior.

## Development Chapters

Treat coherent turtleOS work as development chapters: bounded arcs that begin from a concrete friction or capability need, integrate the spec, implement the smallest useful slice, verify it, and harvest the lesson before moving on.

Chapter pattern:

1. **Name the tension** — What friction, gap, or future capability is being served? Tag tier + acceptance row in [docs/priority-stack.md](priority-stack.md).
2. **Check the spec** — If `TURTLE_SPEC.md` already governs the behavior, trace to it. If not, draft the smallest amendment and get sanction before treating it as canonical.
3. **Implement the slice** — Prefer the lowest-risk useful slice. Keep authority narrower than the eventual vision until it has earned trust.
4. **Document operation** — Update `ARCHITECTURE.md`, operator docs, prompts, skills, or procedures so the implementation can be used and rebuilt.
5. **Verify by consequence** — Run checks proportionate to the blast radius.
6. **Harvest** — Record what the chapter taught: what pattern should repeat, what remains intentionally deferred, and what future authority would require.

Example chapter: the read-only live update surface. The tension was safe updates for a live shell. The spec now defines the live shell update protocol in `TURTLE_SPEC.md` §22.8. The implemented slice stops at `update check/plan`, with tests and canary source coverage, while automated apply/restart remains deferred until the read-only surface proves itself in real updates.

## Drift Sweep Ritual

Run this before pushing any change that affects topology, runtime behavior, autonomy, model routing, practice files, channels, or operator workflow.

Check:

- `TURTLE_SPEC.md` — canonical product law
- `docs/ux/README.md` — applied practitioner UX (review when behavior feels wrong); topic files under `docs/ux/`
- `README.md` — public product frame and setup path
- `ARCHITECTURE.md` — implementation traceability
- `docs/architecture.md` — deployed/current-state operator map
- `docs/turtle-talk.md` — `!` command inventory (spec §5.5); update with any command change
- `AGENTS.md` — agent/operator guidance (`CLAUDE.md` is a pointer to it)
- `.env.template` and `mage_registry.example.yaml` — public configuration examples
- active prompts, skills, and procedures that instruct agents how to act
- Magic integration points when the behavior affects summoning, recall, release, calibration, or Turtle lore

Search for retired topology markers:

- `~/practice`
- `magic-bridge`
- `SCP`
- `#system`
- `DISCORD_CHANNEL_SYSTEM`
- retired Consul/Scout service framing

If a retired marker remains, it must be either removed, updated, or clearly contained in private lineage/archive material.

## Public Surface Policy

Keep public:

- current product law
- current setup and runtime architecture
- generic examples
- implementation traceability
- portable practice templates
- active skills/procedures that ordinary practitioners or operators need

Keep private:

- deprecated identity role cards
- private developmental lineage
- local operator facts and machine-specific paths
- real Discord IDs, channel IDs, tokens, and Tailscale IPs
- practitioner-specific practice state
- historical notes whose main value is internal understanding rather than public operation

When lineage contains a public lesson, distill the lesson into current docs instead of publishing the raw lineage artifact.

## Update Ritual

turtleOS updates are live-service operations governed by `TURTLE_SPEC.md` §22.8. The first supported update surface is read-only awareness:

```bash
python cli.py update check
python cli.py update plan
```

These commands inspect git state and print JSON. They do not pull, merge, restart services, write runtime task/audit state, modify practice files, or touch private configuration.

Use `check` to answer:

- which repository and upstream/base ref are being compared
- whether the working tree is dirty
- whether the checkout is ahead, behind, diverged, or up to date
- whether the local tracking ref appears stale compared with the remote head

Use `plan` when an update appears available. It lists available commits, changed files, impact buckets, the approval tier, and whether a restart is likely.

Manual apply remains an operator action:

1. Run `python cli.py update check` and `python cli.py update plan`.
2. Confirm the source of truth and approval tier.
3. Ensure the working tree is clean.
4. Record the current SHA as the rollback target.
5. Apply the update manually with the operator's chosen git workflow.
6. Run syntax checks for changed Python files.
7. For update-surface changes, run `python -m unittest tests.test_runtime_update`.
8. Run `python canary.py` before any restart decision and again after restart if restarted.
9. Run flow shakedown: `python scripts/shake_flow.py navigator` (offline) and `SHAKE_LIVE=1 python scripts/shake_flow.py navigator --live` on the Mini after restart when flow_runner or native eddy behavior changed.
10. Run link-read shakedown: `python scripts/shake_link_read.py` (offline) after link_read / content_fetch / dialogue fetch changes; `--live` on Mini when dogfooding.
11. Report the result in the relevant craft/admin surface.
12. Run `python scripts/shake_report.py` and close the functional gate before Mage UX dogfood ([functional-gate-protocol.md](automation/functional-gate-protocol.md)).
13. Mini steady-state ops: `python scripts/ops_runner.py` writes Spirit Ops Report to `desk/craft/automation-reports/latest.md` ([registry.md](automation/registry.md)).

Consequence tiers:

- Documentation-only updates can be operator-reviewed and usually require no restart.
- Runtime Python changes require Spirit/operator review and may require a bot restart after verification.
- Dependency changes require explicit operator approval and an install plan.
- Protected or governance files (`TURTLE_SPEC.md`, private config, launchd plists, identity files) require explicit Mage/operator approval before applying.

Do not add automated `git pull`, dependency install, service restart, or rollback behavior until read-only update awareness has proven reliable in real live updates.

## Traceability Matrix (living)

**Primary map:** [`docs/traceability-matrix.md`](traceability-matrix.md) — spec § → module → status → action. Update at every chapter close.

**Acceptance scenarios:** [`docs/acceptance/README.md`](acceptance/README.md) — dogfood + shake index.

**Consolidation chapter (2026-06-20):** [`docs/chapters/2026-06-20-consolidation-traceability.md`](chapters/2026-06-20-consolidation-traceability.md)

---

## Traceability Backlog

When implementation grows ahead of the spec, add the gap here **and** a row in `docs/traceability-matrix.md`. Current known areas needing tighter traceability:

- native runtime beyond the first vertical slice: long-running tasks, general tools, live dialogue routing, and Discord notification outputs
- `cli.py` command reference generation and operator docs
- audited update apply: preflight, explicit approval, verification, restart gating, and rollback after read-only `update check/plan` proves reliable
- self-development write authority: current shell harness is inspection-only; runtime prompt/procedure wording should stay aligned until a real low-risk write path exists
- skill/procedure lifecycle governance: when to add, update, deprecate, or test guidance cards
- founder/founding-room capabilities, if they remain in the public product
- `commands.py` command surface decomposition and generated command reference

Done in the first traceability pass:

- `runtime/` and `cli.py` first vertical slice mapped in `ARCHITECTURE.md`: event intake, durable tasks, audit JSONL, bounded practice capabilities, model probes, runtime readiness, registry-driven paths, and the Discord adapter handoff.
- `runtime/update.py` and `cli.py update check/plan` mapped in `ARCHITECTURE.md`: read-only live shell update awareness from `TURTLE_SPEC.md` §22.8, divergence checks, impact classification, and manual apply ritual guidance.
- `shell_harness.py` self-development inspection slice mapped in `ARCHITECTURE.md`: allowed read-only command families, path/git guardrails, audit log behavior, LLM tool and `/shell` exposure points, and the boundary that write/commit/restart authority is not implemented there.
- `capabilities.py`, `skills/`, and `procedures/` mapped in `ARCHITECTURE.md`: file-backed guidance cards, prompt summary injection, list/read tools, typed result classification, canary smoke check, and the boundary that cards guide behavior but do not grant permissions.

