# turtleOS Development Standard

turtleOS is in production. The public repository should describe the current product, not the private lineage that produced it.

## Production Standard

A change is ready to push when it is coherent from law to implementation:

1. **Spec:** `TURTLE_SPEC.md` names the behavior, boundary, or capability at the right level of abstraction.
2. **Implementation:** the shell implements the behavior, or the gap is explicitly marked in `ARCHITECTURE.md`.
3. **Operations:** active operator docs and prompts point to the current topology.
4. **Verification:** the change has been checked at the level its consequence requires, with a positive control — an empty result is not evidence of absence.
5. **Claim coverage:** every claim the change adds — an invariant in a comment, a limit in a constant, a guarantee in a docstring, a gate described in a doc — is enforced by something that fails when it stops being true, or is written as a *decision with a reason* rather than a guarantee. See `docs/quality-measures.md` for why this is a standing requirement here rather than a nicety.
6. **Public surface:** private lineage, local operator facts, and practitioner-specific state are not exposed as current product knowledge.

Production does not mean perfect. It means the repository does not knowingly publish contradictions between spec, docs, and runtime behavior.

## Development Chapters

Treat coherent turtleOS work as development chapters: bounded arcs that begin from a concrete friction or capability need, integrate the spec, implement the smallest useful slice, verify it, and harvest the lesson before moving on.

Chapter pattern:

1. **Name the tension** — What friction, gap, or future capability is being served? Tag tier + acceptance row in [docs/traceability-matrix.md § Choosing the next chapter](traceability-matrix.md#choosing-the-next-chapter).
2. **Check the spec** — If `TURTLE_SPEC.md` already governs the behavior, trace to it. If not, draft the smallest amendment and get sanction before treating it as canonical.
3. **Implement the slice** — Prefer the lowest-risk useful slice. Keep authority narrower than the eventual vision until it has earned trust.
4. **Document operation** — Update `ARCHITECTURE.md`, operator docs, prompts, skills, or procedures so the implementation can be used and rebuilt.
5. **Verify by consequence** — Run checks proportionate to the blast radius. **Spirit quick gate:** `./scripts/spirit_verify.sh` (full unit suite). Chapter-close: relevant `shake_*.py` per [functional-gate-protocol.md](automation/functional-gate-protocol.md).
6. **Harvest** — Record what the chapter taught: what pattern should repeat, what remains intentionally deferred, and what future authority would require.

Example chapter: the read-only live update surface. The tension was safe updates for a live shell. The spec defines inspect/propose/heal authority in `TURTLE_SPEC.md` §20. The implemented slice stops at `update check/plan`, with tests and canary source coverage, while automated apply/restart remains outside operator default authority.

## Agent-Driven Development Workflow

*Adopted 2026-07-10. turtleOS is developed almost entirely by AI agents directed by a human who defines problems and reviews artifacts. This section codifies how that factory runs. It refines — does not replace — the chapter pattern above: a chapter is the narrative unit; this workflow is its production mechanics.*

### Principles

1. **Task sizing for the smart zone.** Agent quality degrades as context fills (~100K tokens regardless of window size). Size every task to complete well within a fresh context. Prefer clearing context and starting fresh over compacting; a session that must be compacted twice was scoped too large.
2. **Alignment before artifacts.** The valuable output of planning is a *shared design concept* between human and agent, reached by the agent interviewing the human (questions one at a time, recommended answer attached) — not a spec the human writes alone. Destination documents summarize alignment already reached; they do not substitute for it.
3. **Two task classes.** **HITL** (human-in-the-loop): alignment, design judgment, QA, taste, live-Mini operations. **AFK** (away-from-keyboard): implementation against a well-specified issue with working feedback loops. Planning is always HITL; implementation should almost always be AFK-able — if it isn't, the issue isn't specified well enough yet.
4. **Vertical slices (tracer bullets).** Break destinations into thin slices that cross all layers and produce something testable/visible, not horizontal layers. A slice's completion is observable by consequence, per the chapter pattern's "verify by consequence."
5. **Feedback loops are the ceiling.** Agent output quality is capped by the quality of the feedback loops it runs against — the unit gate, shakes, type/lint checks. A red or untrustworthy gate is a factory-stops defect (see issues 009/027/028). TDD (red → green → refactor) is the default implementation discipline: it instruments the code before writing it, which prevents test-cheating.
6. **Review in a fresh context.** Never have the implementing session review its own work — by review time it is deep in the dumb zone. Reviews run in fresh contexts (separate agents), with coding standards **pushed** to reviewers and **pullable** by implementers. The 2026-07-10 dual review (two independent models, same checkout) validated cross-model review diversity: each found critical issues the other missed.
7. **Deep modules, delegated interiors.** Design module interfaces deliberately (HITL); delegate implementations (AFK). Small interface, deep functionality — testable from the outside as a unit. This is how the human retains a working map of the codebase while agents write nearly all the code. Shallow-module sprawl is what unwatched agents produce by default.
8. **QA is where taste enters.** Human QA of the running system is not optional polish — it is the mechanism by which the operator's judgment shapes the product. QA findings become new backlog issues; the Kanban absorbs them continuously.
9. **Doc-rot policy.** Issue files and PRD-like artifacts are working memory, not documentation. Delete them when done (the chronicle records the fix). Durable knowledge goes to `TURTLE_SPEC.md`, `ARCHITECTURE.md`, or `docs/learnings.md`.
10. **Definition-of-good travels with the artifact.** Every artifact that reaches a HITL review gate (destination doc, design chapter, QA pass) carries review criteria written at alignment time — a meaningful share of bad agent output is an evaluation problem, not a model problem. But humans can rarely specify "good" upfront, because they don't yet know what is possible: so the agent drafts the criteria *from the grilling conversation*, phrased at value-altitude as recognition tests ("this succeeded if, a week in, you reach for X without thinking about it"), never as solution specs. The human reacts and corrects rather than authoring from scratch. Before surfacing any artifact for review, the agent checks it against the stated criteria and reports deviations as flags — human review becomes judging flagged trade-offs, not hunting for problems.

11. **Name the reader.** Every slice that *produces* an artifact ships a test that asserts something *consumes* it. Not that the write happened, not that its shape is right — that a reader receives it. A writer with no named reader is a write-only artifact, and it ships green.

    This is not hypothetical. Five were found in two days (2026-07-28/29), every one of them written by code that was complete, correct, and covered:

    | Artifact | Test coverage it had | Reader |
    |---|---|---|
    | `alive.yaml` themes | confirm flow tested end to end | never populated in a shared root |
    | eddy notes | writer + parser tested | nothing, at conversation time |
    | communal daily note | voice branch pinned by `test_witness_voice` | posted nowhere |
    | `render_scope_block` | matching + honest-when-thin tested | pointed at `sessions/`, retired 3 weeks earlier |
    | `proposed-themes` | written every checkpoint | nothing *(closed 2026-07-29 — room memory renders them, and 2026-08-05 — they promote into the alive layer)* |

    `test_witness_voice` proved the daily note was written in the right voice for the right audience. Nothing anywhere asked whether it reached a human — so it was correct, tested, and unread for weeks, and the felt absence was answered by building a *second* artifact (per-member notes) which then inverted whose day it was telling (INT-048).

    **The test to write:** given a produced artifact, assert the consuming path returns it — the channel it posts to, the prompt it enters, the surface it renders into. If no such assertion is writable, the reader does not exist yet, and *that* is the finding. Say so in the slice rather than shipping the writer alone.

    **Corollary for retirements.** When a genre stops being written, grep for its readers before closing the issue. `sessions/*.md` was retired on 2026-07-15 with no one asking what still read it; the answer was the only turn-time retrieval in the system, which then spent three weeks serving April.

    Companion in the Magic practice: `system/lore/practice/on_wire_before_mechanism.md` — when a fix needs a gate, look for the connection that was never made.

12. **Write the destination before the mechanism.** Any change to what a practitioner *experiences* ships four artifacts first — before the design doc, before the slices, before code:

    | | Artifact | What it is |
    |---|---|---|
    | 1 | **Press release** | The ideal, from the practitioner's side, announcing the thing as though it already works. No mechanism named anywhere in it. |
    | 2 | **Happy path** | One practitioner, one task, start to finish, written **as dialogue**. House style is `docs/design/continuity-engine-and-substrate.md` §3.5. |
    | 3 | **Success criteria** | Experience-shaped, not capability-shaped. |
    | 4 | **Abandon line** | The observable whose arrival means stop. A success criterion alone is a wish; the pair is a decision. |

    Bug fixes and refactors are exempt — their destination is *the same, but correct*. The rule is deliberately narrow: an over-covering rule gets ignored, which is worse than a narrow one that is obeyed.

    **Three tests every criterion must pass.** These are not style notes; each one is a defect the continuity engine already shipped.

    - **Mechanism-blind.** Could a completely different implementation be scored against this, unchanged? CE criterion 3 said *"after checkpoint **+ confirm**…"* and criterion 5 said *"**`!focus`** deepens one slice."* When the confirm gate was dropped (2026-07-29) and `!focus` went on notice, neither criterion failed — they stopped meaning anything, and the design lost two of its nine tests with no red light anywhere. **A criterion that names a mechanism dies silently when the mechanism changes; a criterion that names an experience fails loudly.**
    - **Can it fail in week three?** If it can only be demonstrated once, it is a demo, not a criterion. All nine CE criteria were shaped *can it do the thing* — answerable yes the first time the feature works and never asked again. Criterion 6 (*"Turtle states limits when substrate stale — no fabricated recall"*) passed at ship and has been violated in two live roots for weeks, because nothing re-ran it. Twenty of the twenty-eight defects in Defect Set 01 reported success while broken; a capability-shaped criterion is that instrument by construction.
    - **Named re-run.** Who or what re-checks it, and when. No cadence, no criterion.

    **Falsifier.** If two features ship and no press release ever killed or reshaped one *before* it was built, this principle is ceremony and gets deleted.

### The pipeline

```
idea/friction ──HITL──► grilling session (agent interviews human → design concept)
              ──HITL──► press release + happy path + criteria + abandon line (§12;
                        practitioner-visible change only — may end here, not built)
              ──HITL──► destination doc (problem, stories, module map, out-of-scope,
                        value criteria drafted by agent, human reacts)
              ──HITL──► vertical-slice issues with blocking relations (issues/, gitignored)
              ──AFK───► implementation loops (TDD, gate green, one issue per fresh context;
                        parallel agents on unblocked issues)
              ──fresh──► automated review (standards pushed, separate context)
              ──HITL──► QA on the running system against the value criteria
                        (artifacts arrive pre-checked, deviations flagged) → new issues → repeat
              ──gate──► chapter close per the pattern above (matrix, shakes, harvest)
```

### Backlog conventions

- `issues/` (gitignored — may contain unfixed security detail): `NNN-slug.md`, each with severity, tranche, **Mode: AFK/HITL**, **Blocked-by**, finding, fix sketch, acceptance criteria. Unblocked issues in a tranche are parallelizable.
- An issue is ready for AFK dispatch when a fresh agent could complete it from the file alone plus repo exploration — acceptance criteria testable, feedback loop named.
- Live-Mini actions inside any issue stay HITL per the live-runtime boundaries in `AGENTS.md`, regardless of the issue's mode tag.

## Drift Sweep Ritual

Run this before pushing any change that affects topology, runtime behavior, autonomy, model routing, practice files, channels, or operator workflow.

Check:

- `TURTLE_SPEC.md` — canonical product law
- `docs/ux/README.md` — applied practitioner UX (review when behavior feels wrong); topic files under `docs/ux/`
- `README.md` — public product frame and setup path
- `ARCHITECTURE.md` — the software: modules, subsystems, design decisions
- `docs/live-runtime.md` — one deployment: the operator Mac Mini's services, filesystem, and Forge sync
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

The allowlist lives in `scripts/public_surface.conf`. Ask it, do not remember it:

```bash
./scripts/public_surface.sh --check docs/live-runtime.md   # private
./scripts/public_surface.sh --list                         # what would ship
./scripts/public_surface.sh --self-test
./scripts/publish_public_turtleos.sh                       # dry-run (default)
```

`docs/live-runtime.md` and `docs/learnings.md` are denied by name in that file and by an absolute never-list in the script. A test fails if either would classify as public. `publish_public_turtleos.sh` prints the same path list; `--publish` is the visibility act and refuses `origin` (the Mini's private pull). It does not create remotes.

## Update Ritual

turtleOS updates are live-service operations governed by `TURTLE_SPEC.md` §20. The first supported update surface is read-only awareness:

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
13. Mini steady-state ops: `./venv/bin/python3 scripts/ops_runner.py` writes Spirit Ops Report to `{practice_root}/state/notes/automation-reports/`; Forge harvests via Magic `sync_practice_root.sh pull` ([registry.md](automation/registry.md)). On Mini, always use the venv interpreter — system `python3` lacks deps and fails unittest discovery.

Consequence tiers:

- Documentation-only updates can be operator-reviewed and usually require no restart.
- Runtime Python changes require Spirit/operator review and may require a bot restart after verification.
- **Split-bot:** restart **both** `com.turtle.discord` (Turtle) and `com.turtle.river` (River) when shared modules change — kickstarting Turtle alone leaves stale River code loaded. Prefer `./restart.sh` (bounces both when River is loaded). Module tags: [`deploy-touchpoints.md`](deploy-touchpoints.md). Canary/readiness require River alive when `RIVER_BOT_TOKEN` is set.
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
- `runtime/update.py` and `cli.py update check/plan` mapped in `ARCHITECTURE.md`: read-only live shell update awareness from `TURTLE_SPEC.md` §20.2, divergence checks, impact classification, and manual apply ritual guidance.
- `shell_harness.py` self-development inspection slice mapped in `ARCHITECTURE.md`: allowed read-only command families, path/git guardrails, audit log behavior, LLM tool and `/shell` exposure points, and the boundary that write/commit/restart authority is not implemented there.
- `capabilities.py`, `skills/`, and `procedures/` mapped in `ARCHITECTURE.md`: file-backed guidance cards, prompt summary injection, list/read tools, typed result classification, canary smoke check, and the boundary that cards guide behavior but do not grant permissions.

