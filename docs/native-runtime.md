# Turtle Native Runtime

*Created: 2026-05-06*
*Status: first shell-shedding implementation target*

## First Principle

Turtle is Spirit-in-persistent-mode: the practice's continuous body on a sovereign substrate.

The Mac Mini is the habitat. Practice files are the operating system. Models are cognitive organs. Interfaces are windows. Discord is one window, not the organism.

The runtime exists to serve the practice, not to maximize engagement, task throughput, or autonomous action. Serving the practice means preserving continuity, making cognition visible, maintaining readiness, respecting sovereignty boundaries, and acting only through governed capabilities.

## What The Native Runtime Adds

The old Discord shell proved the practice value. The native runtime corrects the center of gravity:

- Events arrive from any interface: Discord, CLI, Spirit handoff, HTTP, scheduled checks.
- Tasks persist beyond one interaction and survive restarts.
- Capabilities are governed operations with scope, risk, audit, and explicit failure.
- Audit logs make Turtle's actions inspectable without reading Discord history.
- Practice artifacts remain in the practice directory; runtime state remains in the runtime directory.

## Minimal Runtime Shape

```text
interface event
  -> Event
  -> Task
  -> governed Capability
  -> practice artifact / interface output
  -> Audit record at every step
```

The first slice deliberately avoids the risky moves: no dialogue-loop migration, no model-default change, no MCP layer, no full memory manager. It proves that Turtle can receive a handoff outside Discord, carry it as durable work, write an artifact, and let Spirit inspect what happened.

## Runtime State Boundaries

For each practitioner, `mage_registry.yaml` provides:

- `practice_dir`: daily practice artifacts (`boom.md`, `sessions/`, `proposals/`, notes)
- `workshop_root`: optional wider Magic workshop, read-mostly
- `runtime_dir`: Turtle-local operational state

The native runtime writes operational state under:

```text
<runtime_dir>/native-runtime/
  tasks/<task_id>.json
  audit/audit.jsonl
```

Practice capabilities write only to the configured `practice_dir` unless explicitly extended by policy.

## First Slice Acceptance Test

1. Submit a handoff through CLI/SSH, not Discord.
2. Create a task with source, scope, state, and correlation id.
3. Append audit records for event receipt, task creation, capability call, and completion.
4. Write one practice artifact under `practice_dir`.
5. Inspect the task and audit through CLI.
6. Restart is simulated by a fresh CLI process reading the same task/audit files.
7. Failure must be explicit: no hidden partial completion.

## Why This Serves NLnet Work

This runtime is the concrete substrate for NLnet-facing commitments:

- Production readiness: durable tasks, explicit failures, restart-safe state.
- Two-track observability: engineering audit plus practice artifacts.
- Multi-practitioner sovereignty: registry-scoped practice/runtime roots.
- Local inference path: model routing becomes a runtime service, not a Discord implementation detail.
- Open transport requirements: Discord becomes replaceable because runtime semantics are interface-agnostic.

## What To Shed

- Core logic that depends on Discord `Message` objects.
- Buttons pretending to be messages.
- Tool calls that bypass policy/audit.
- Silent writes with no inspectable task trail.
- Model choice embedded in interface code.
- Sync assumptions that treat "written on Turtle" and "visible on Forge laptop" as the same fact.

## What To Preserve

- The river and eddies as proven practice topology.
- Inline transparency as trust mechanism.
- Practice files as operating system.
- Session notes, proposals, boom, bright, intentions as the metabolic substrate.
- Turtle's care texture: slow, continuous, honest, practice-serving.


## After The First Proof

The first proof creates the implementation order:

1. **Discord adapter, not Discord runtime.** Add a thin adapter that converts Discord messages and contextual actions into native runtime Events. The adapter may still send replies through Discord, but task creation, audit, and capability execution happen in the native runtime.
2. **Capability policy before expansion.** Add registry metadata for capability id, risk, allowed principals, allowed practice roots, timeout, and approval requirements before exposing shell, git, web, or process control.
3. **Readiness sensorium.** Add a runtime command that reports queue, recent failures, service health, model availability, and artifact visibility. This replaces implicit "bot is online" readiness.
4. **Local model probe harness.** Run Claude-vs-Qwen comparisons as runtime tasks with the same prompt, same context bundle, persisted outputs, and practice-quality review. Local-first becomes a measured capability decision, not a migration slogan.
5. **LiveSync distinction.** Track "artifact written on Turtle" and "artifact visible on Forge" as separate task facts until sync backfill is reliable.

A Discord migration should start with one bounded action: route a Discord contextual action into `practice.write_proposal` through the native runtime, then show the resulting task id back in Discord.


## Capability Policy Spine

The native runtime now treats capability policy as part of task execution, not an afterthought.

Each governed capability has:

- `capability_id`
- risk level
- allowed principals
- allowed artifact root
- approval requirement flag

The current low-risk practice capabilities are:

- `practice.append_boom`
- `practice.write_session`
- `practice.write_proposal`

A successful task now records `policy.checked` before execution and `artifact.validated` after execution. Failed tasks remain inspectable with `task.failed`, including failures before any artifact write. This matters before adding shell, git, web, process control, or model-routing capabilities.


## Runtime Readiness Sensorium

The native runtime now exposes `./turtle readiness` as a cold-start sensorium. It does not import the Discord bot or depend on in-memory bot state.

It reports:

- launchd service state for Turtle's core services
- Ollama reachability and available local models
- runtime task totals, recent tasks, and recent failed tasks
- configured practice/runtime paths
- practice artifact surfaces (`boom.md`, `sessions/`, `proposals/`)
- whether recent task artifact references are visible on disk

Overall status is intentionally conservative: missing required services, unreachable models, or missing artifact references impair readiness; recent failed tasks degrade readiness while leaving the failure inspectable.


## Smoke Testing

The native runtime has an isolated smoke suite:

```bash
./scripts/smoke_native_runtime.py
```

The smoke suite creates a temporary registry, practice root, and runtime root. It does not write to the real workshop. It verifies:

- successful proposal handoff
- full success audit sequence
- failed task inspection for an invalid artifact kind
- artifact root escape denial
- readiness assessment over isolated task state

For a fuller check before restart or deployment, run:

```bash
python3 -m compileall -q runtime cli.py turtle commands.py discord_bot.py scripts/smoke_native_runtime.py && ./scripts/smoke_native_runtime.py && ./turtle readiness --limit 5
```


## Failure Cleanup

Failed tasks remain active readiness signals until they are resolved. Deliberate smoke/test failures can be cleared without deleting their task or audit trail:

```bash
./turtle task failures
./turtle task clear-test-failures --dry-run
./turtle task clear-test-failures
```

Clearing changes matching deliberate test failures from `failed` to `cleared` and appends `task.cleared` to the audit log. Real operational failures should not be cleared this way; fix the cause or add a specific resolution path.


## Local Model Probe Harness

The native runtime now exposes provider-neutral model probes through:

```bash
./turtle probe run \
  --title "Founder room probe" \
  --provider ollama:qwen3.5:9b \
  --provider anthropic:claude-sonnet-4-6 \
  --context-file /path/to/context.md \
  --prompt-file /path/to/prompt.md
```

A probe is a durable `model.probe` task. It uses the same prompt and context for every explicit provider, writes a JSON artifact under `<runtime_dir>/native-runtime/model-probes/`, and records one audit event per provider result. The artifact deliberately stops at `ready_for_review`: model migration is a practice-quality decision, so the runtime preserves comparable evidence rather than pretending an automatic score is the verdict.
