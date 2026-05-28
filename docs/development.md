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

## Drift Sweep Ritual

Run this before pushing any change that affects topology, runtime behavior, autonomy, model routing, practice files, channels, or operator workflow.

Check:

- `TURTLE_SPEC.md` — canonical product law
- `README.md` — public product frame and setup path
- `ARCHITECTURE.md` — implementation traceability
- `docs/architecture.md` — deployed/current-state operator map
- `CLAUDE.md` — agent/operator guidance
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

## Traceability Backlog

When implementation grows ahead of the spec, add the gap here or in `ARCHITECTURE.md`. Current known areas needing tighter traceability:

- native runtime beyond the first vertical slice: long-running tasks, general tools, live dialogue routing, and Discord notification outputs
- `cli.py` command reference generation and operator docs
- self-development write authority: current shell harness is inspection-only; runtime prompt/procedure wording should stay aligned until a real low-risk write path exists
- skill/procedure lifecycle governance: when to add, update, deprecate, or test guidance cards
- founder/founding-room capabilities, if they remain in the public product
- `commands.py` command surface decomposition and generated command reference

Done in the first traceability pass:

- `runtime/` and `cli.py` first vertical slice mapped in `ARCHITECTURE.md`: event intake, durable tasks, audit JSONL, bounded practice capabilities, model probes, runtime readiness, registry-driven paths, and the Discord adapter handoff.
- `shell_harness.py` self-development inspection slice mapped in `ARCHITECTURE.md`: allowed read-only command families, path/git guardrails, audit log behavior, LLM tool and `/shell` exposure points, and the boundary that write/commit/restart authority is not implemented there.
- `capabilities.py`, `skills/`, and `procedures/` mapped in `ARCHITECTURE.md`: file-backed guidance cards, prompt summary injection, list/read tools, typed result classification, canary smoke check, and the boundary that cards guide behavior but do not grant permissions.

