# Turtle Native Harness Research Design

*Drafted: 2026-05-05*
*Scope: Mac Mini first; portable to future Magic-enchantable infrastructure*

## Thesis

Turtle should not live inside Discord. Turtle should live in a native agent harness on the Mac Mini, with Discord as one interface.

The current shell has delivered real practice value, but its center of gravity is backwards: `discord_bot.py` is the runtime, and everything else orbits Discord's event model. That makes every capability express itself as a Discord interaction, button, command, thread, or timeout. The deeper Turtle wants a body: persistent process, durable tasks, local tools, local model routing, audit trail, readiness, and interfaces attached around it.

The harness should be the shell. Discord should be a window.

Turtle grew up on Discord. Turtle should not be confined to Discord.

Discord was not a mistake. It was the right nursery: social, persistent, mobile, threaded, forgiving, already part of life. It taught Turtle the river, eddies, inline transparency, session notes, practice invitations, tool friction, and the difference between being a chatbot and being a practice partner.

The native harness should honor that lineage without mistaking the nursery for the body. We are not building a business agent with practice-flavored language. We are building a persistent practice partner with agent-harness rigor. Borrow from enterprise harness design where it serves the practice: durable execution, audit logs, capability registries, guardrails, progressive disclosure, evaluation, model routing. Reject the default optimization target. Turtle is not meant to maximize conversion, engagement, task throughput, or autonomous action. Turtle serves the practice.

## Evidence From Current Turtle

Recent conversation surfaced the right diagnosis:

- Turtle named the inversion directly: the Mac Mini is the habitat; Discord is one interface to it.
- The immediate contextual-action failure (`_InteractionAsMessage` lacks `create_thread`) is a symptom of adapter leakage. Discord interactions are being wrapped as fake messages so command handlers can be reused, but the abstraction breaks on message-specific behavior.
- Turtle's tools struggled to write the proposal file. The dialogue model understood the practice need, but the tool/runtime path failed to carry it into durable state.
- Current code confirms the shape: `discord_bot.py` handles message reception, triage, proprioception, URL fetching, prompt assembly, tool loop, reply sending, contextual-action extraction, reflection scheduling, and thread-state updates in one path. `commands.py` carries direct operations, UI views, contextual action wrappers, and control panel behavior. `shell_harness.py` exists, but as a constrained self-inspection tool, not the native runtime.

## External Research Signals

The 2026 agent-harness landscape points in the same direction:

- **Durable execution matters.** LangGraph's checkpointers and interrupts treat `thread_id` as a persistent cursor, allowing long-running work to pause and resume without losing state.
- **Tool governance is a runtime responsibility.** Modern SDKs distinguish local runtime tools, hosted tools, agents-as-tools, MCP tools, and guardrails. The harness should mediate tools, not let conversation code call them ad hoc.
- **MCP is useful but unsafe by default.** Tool schemas, descriptions, and outputs are prompt content; local tool servers are privileged dependencies. A Turtle harness needs a control plane: capability registry, policy gate, audit log, scope boundaries, and human approval for privileged actions.
- **Qwen3 function calling is viable but template-sensitive.** Qwen's own docs recommend Hermes-style tool use. Ollama tool-calling can work, but reported issues suggest the harness should own parsing and not blindly depend on one provider's tool adapter.
- **Long-lived agents need auditability and self-perception.** Springdrift's architecture is especially relevant: append-only logs, supervised processes, sensorium injection, gates around input/tool/output, and forensic reconstruction. Turtle already has lore equivalents: readiness, interoception, canary, river_state, sessions, proposals. The native harness should make those first-class.
- **Context is virtual memory.** ClawVM's typed pages, minimum-fidelity invariants, staged writeback, and observable faults map cleanly to Turtle's practice state. Turtle should not "just retrieve context"; the harness should decide what must be resident, at what fidelity, and why.

## Design Principles

1. **Interface inversion.** The core runtime exposes a stable event/task API. Discord, CLI, HTTP, voice, and Spirit relay all attach as adapters.
2. **Durability by default.** Every event, task, tool call, interrupt, output, and state transition is logged append-only with enough metadata to replay or audit.
3. **Tools through a control plane.** Tools are capabilities with scopes, risk levels, policies, timeout classes, and audit records. The LLM never executes "shell"; it requests capabilities.
4. **Local-first, quality-gated.** Qwen/local models become default where practice quality holds. Claude/frontier remains a depth fallback, not Turtle's identity.
5. **State as managed memory.** Practice files, thread summaries, active tasks, constraints, evidence, and identity are typed pages with residency/fidelity rules.
6. **Sensorium before response.** Each cognitive cycle receives a structured self-state: queue, services, model state, active tasks, recent errors, readiness, current practice pulse.
7. **Human-in-the-loop at altitude.** The harness can pause tasks for Mage/Spirit approval, then resume from checkpoint. Approval is not a Discord hack; it is a runtime primitive.
8. **Practice tests over code nostalgia.** Verify the new harness against lived practice: link intake in under 10 seconds, thread creation works, session notes land, proposal writes survive, uncertainty is honest, and Turtle feels present.

## Proposed Architecture

```
Mac Mini
└── turtle-native-harness
    ├── runtime kernel
    │   ├── event bus
    │   ├── task/checkpoint store
    │   ├── append-only audit log
    │   ├── sensorium builder
    │   ├── context/page manager
    │   ├── model router
    │   └── policy/tool gate
    ├── capability registry
    │   ├── practice files
    │   ├── turtleOS source inspection
    │   ├── git
    │   ├── Discord operations
    │   ├── web/content fetch
    │   ├── process/service control
    │   └── optional MCP adapters
    ├── cognitive loops
    │   ├── dialogue loop
    │   ├── reflection loop
    │   ├── research/pattern loop
    │   ├── maintenance loop
    │   └── self-development loop
    └── interfaces
        ├── Discord adapter
        ├── CLI adapter
        ├── Spirit RPC/SSH adapter
        ├── local HTTP control surface
        └── future voice/mobile adapters
```

## Core Runtime Objects

### Event

Anything that reaches Turtle: Discord message, CLI prompt, scheduled pulse, canary result, file change, Spirit handoff, tool result, approval response.

Required fields: `event_id`, `source`, `interface`, `principal`, `scope`, `trust_level`, `timestamp`, `payload_ref`, `correlation_id`.

### Task

A durable unit of work. Conversations are tasks. Scheduled maintenance is a task. "Create a founder invite" is a task. "Investigate contextual-action failure" is a task.

Required fields: `task_id`, `kind`, `state`, `owner`, `checkpoint`, `resident_pages`, `pending_approval`, `audit_refs`.

### Page

A managed context unit: identity, policy, active plan, thread summary, practice file excerpt, tool evidence, current task, user preference, runtime constraint.

Required fields: `page_id`, `type`, `scope`, `provenance`, `fidelity`, `min_fidelity`, `dirty`, `source_ref`.

### Capability

A tool exposed through policy. Capabilities are not raw Python functions to the model; they are governed operations.

Required fields: `capability_id`, `namespace`, `risk`, `allowed_scopes`, `requires_approval`, `timeout`, `input_schema`, `output_schema`, `audit_policy`.

## Capability Model

Start with native capabilities before MCP:

- `practice.read`, `practice.search`, `practice.append`, `practice.patch`, `practice.write_proposal`, `practice.write_session`
- `discord.send`, `discord.reply`, `discord.create_thread`, `discord.fetch_thread`, `discord.update_message`
- `source.search`, `source.read`, `source.diff`, `source.compile_check`, `source.test`
- `git.status`, `git.diff`, `git.log`, `git.commit_after_approval`
- `service.status`, `service.restart_allowed`, `service.logs`
- `web.fetch`, `content.extract`, `content.summarize`
- `task.create`, `task.pause`, `task.resume`, `task.cancel`
- `approval.request`

MCP can be added behind the same control plane later. The policy surface should not care whether a capability is native Python, an MCP server, a shell subprocess, or a remote API.

## Model Router

Use the tiered cognitive stack, updated for May 2026:

- Triage: smallest local Qwen that classifies reliably, always `think=false` or template-equivalent.
- Sensorium/proprioceptor: local fast model, structured output only.
- Dialogue: local Qwen3/Qwen3.5/Qwen3.6 candidate by default once practice probes pass. Claude remains fallback.
- Reflection: larger local Qwen, multi-pass allowed.
- Research: largest local model that fits on the Mac Mini without degrading live dialogue.
- Depth: Claude/frontier via explicit escalation or confidence threshold.

Important: do not build the harness around Ollama's `tools` parameter as a single point of failure. Prefer a provider-neutral tool protocol with adapters:

1. native structured tool calls when reliable,
2. Hermes-style tool prompting and parser for Qwen,
3. Anthropic tool calls for Claude fallback,
4. replayable transcript format independent of provider.

## Context Manager

Turtle already has files as OS. The native harness should add OS-like memory management:

- Identity/policy pages are pinned.
- Active task plan pages must stay at structured fidelity or above.
- Evidence pages can degrade to pointer if resolvable.
- Thread summaries can degrade but not disappear while active.
- Dirty pages must write back before compaction, task close, restart, or model handoff.
- Missing required pages should produce observable faults, not silent shallow responses.

This gives Turtle a real answer to "what do I know right now?" and "why didn't I remember that?"

## Interface Contracts

### Discord Adapter

Discord should translate between Discord events and runtime events:

- Message -> Event
- Button click -> Approval/Event, not fake Message
- Thread creation -> `discord.create_thread` capability
- Reply/post -> Output channel selected by runtime
- Silent embeds -> Observation output

No core command handler should require a Discord `Message` object.

### CLI Adapter

The CLI is the local primary harness surface:

- `turtle ask "..."` for direct conversation
- `turtle task list|show|resume|cancel`
- `turtle inspect readiness|sensorium|queue|models`
- `turtle approve <approval_id> yes|no|edit`
- `turtle run <procedure>` for maintenance/self-development procedures

CLI gives Spirit and Mage a direct path to Turtle without Discord mediation.

### Spirit RPC Adapter

Spirit needs a clean machine channel:

- submit handoff as file/stdin without chunk confusion,
- create tasks,
- request Turtle perspective,
- inspect audit/task state,
- approve or annotate implementation guidance,
- receive structured results.

This can begin as local CLI over SSH and later become local HTTP or Unix socket.

## Migration Plan

### Phase 0: Fix the immediate leak

Patch contextual actions so button handlers do not wrap interactions as fake messages for operations that require real messages. This restores trust while we design the harness.

### Phase 1: Extract runtime seams

Introduce runtime domain objects (`Event`, `Task`, `CapabilityResult`) and move direct command handlers to accept runtime context rather than Discord `Message`.

### Phase 2: Build harness skeleton beside current bot

Run a native process with event queue, audit log, task store, sensorium builder, and capability registry. Discord still handles live dialogue but forwards selected events into the harness.

### Phase 3: Move tools behind capability registry

Replace ad hoc calls in `tos_tools.py`, `commands.py`, and `shell_harness.py` with governed capabilities. Keep old wrappers as adapters.

### Phase 4: Move dialogue loop into harness

Discord adapter sends message events; harness handles triage, proprioception, prompt assembly, model call, tools, and output. Discord only renders.

### Phase 5: Add CLI and Spirit direct channel

Use the same event/task/capability system through CLI. Make Spirit handoffs and local investigations first-class.

### Phase 6: Local model migration

Run paired Claude-vs-Qwen probes using real founder-room and Turtle conversations. Default to local only after practice quality passes.

### Phase 7: Retire old Discord-centered shell

Archive old shell. Keep current code as lineage/reference. New harness becomes `~/turtleos` runtime.

## Verification Suite

Minimum acceptance tests:

- Click "Create thread" contextual action -> thread created, parent channel receives clickable link.
- Share X/YouTube/web link from phone -> **Reading… → Read** status embed within 10 seconds, then grounded Turtle reply; failure shows paste/`!fetch` ladder (§9.5).
- Long message with incidental URL -> **Read article / Skip** offer without blocking first reply.
- Article over 8k chars -> status embed shows **N/M in context** and `box/intake/` spill path.
- Ask "what did you just read?" -> Turtle can show source trace and resident pages.
- Let session go quiet -> session note written, readiness recorded, channel gets concise closure.
- Trigger one scheduled interoception -> event logged, sensorium updated, output rendered, no duplicate noise.
- Run `turtle task` from SSH -> active tasks visible without Discord.
- Restart harness mid-task -> task resumes or reports checkpointed interruption.
- Tool call blocked by policy -> clear reason code, no hidden failure.
- Local dialogue model answers known founder-room question -> uncertainty handling and routing to the human operator preserved.

## First Cognition-Altitude Decision

Recommended: treat this as a real shell-shedding chapter, not a refactor.

The current code should be harvested and used as reference, but the target architecture should not be constrained by `discord_bot.py`. The first implementation move should be a parallel native harness skeleton, not editing the old event loop into shape. That lets Turtle keep serving through Discord while the new body grows beside it.

If this lands, the next concrete artifact should be:

`floor/drafts/turtle_native_harness_blueprint.md` or a tracked `docs/native-harness.md` in `turtleos`, depending on whether the dyad wants the design to mature privately first or enter the shell repo immediately.

