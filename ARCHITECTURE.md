# turtleOS Bot Architecture

> **Scope:** the software — modules, subsystems, dispatch, and the design decisions behind them. True of any instance. Rebuilt 2026-03-29 from a monolith; evolving toward platform law (River/Turtle split).  
> **One deployment:** [`docs/live-runtime.md`](docs/live-runtime.md) — services, filesystem, and Forge sync of the operator's Mac Mini. Instance facts belong there, not here.  
> **Law:** [TURTLE_SPEC.md](TURTLE_SPEC.md) — what turtleOS must do. **Spec → module → verification:** [`docs/traceability-matrix.md`](docs/traceability-matrix.md), the single development index; this file does not keep a second one.

Module and line counts are deliberately not stated here. A count in prose drifts the moment code lands and nothing can notice; the previous header claimed ~34 modules while the tree held 89. Count when you need one — `git ls-files '*.py' | xargs wc -l`.

---

## Target Architecture (TURTLE_SPEC 2026-06)

Vanilla turtleOS — what the shell **should** implement:

```
River channel message
    │
    ├─ set_practice_context (mage.py)
    ├─ try_direct_command (commands.py)     ← turtle-talk ! power path
    └─ river_handler (target)
        ├─ river_model (small local)        ← classify → structured acts
        ├─ act_renderer                     ← buttons, embeds, reactions only — NO prose
        ├─ always offer_eddy + optional ack / flow_menu / revise
        └─ chronicle (surface + deep.jsonl) ← thread jump URLs on materialize

Eddy (thread) message
    │
    └─ turtle_handler (target)
        ├─ presence embed (joined / stepped out)
        ├─ turtle_model (capable local)     ← think-aloud + answer (single call v1)
        ├─ flow_runner                      ← front matter reads/writes state/
        └─ operational lines (-# read …)   ← visible tool/context transparency
```

| Component | Model | Channel |
|-----------|-------|---------|
| **River** | 4B–9B local | Main channel — acts only |
| **Turtle** | ~30B local | Eddies only — dialogue |

**Practice root (vanilla):** `character/`, `flows/`, `chronicle/`, `state/` — no required compass/boom/bright at install.

**Retired from vanilla target:** proprioceptor, reflex, river-entry monologue, vortex/prism, Turtle speech in river.

---

## Migration Status (2026-07-04)

**Platform law** (TURTLE_SPEC 2026-06 rewrite) defines native turtle as the default product. A typical instance is `attunement: native` with a practice root under `~/workshops/<member>/`. One operator deployment’s paths are not product law.

The shell is **native-only** (Phase D, 2026-07-08). Legacy magic-attuned Appendix A code paths removed. Strangle archive: Magic repo `floor/research/native-migration-strangle-checklist.md`.

| Target (spec) | Operator Mini (native) | Codebase (dual-stack) |
|---------------|------------------------|------------------------|
| River acts only | **Live** — `river_handler.py` + `river_bot.py` | Gated `attunement: native` |
| Always offer eddy | **Live** — standing eddy bar | Aligned |
| Eddy-only Turtle | **Live** — native `character/` in eddies | Legacy magic prompts remain for Appendix A |
| Two local models (River 4–9B / Turtle ~30B) | Partial — triage still in tree | **Gap** on model routing cleanup |
| `state/` + CE practice infrastructure | **Live** — CE Slice 0+1a, `!focus` | **Aligned** (2026-07-10 purge) |
| Chronicle jump URLs | Partial | **Integrate** |
| Magic-attuned mode | **Removed** (Phase D) | Appendix A retired from codebase |

**Default attunement in code:** `mage.py` defaults to `native` when registry omits `attunement` (2026-07-04).

---

## Reading the live dispatch path

There is deliberately no diagram of the current message path here. The one that stood in this section until 2026-08-18 was labelled *pre-migration*, still placed `handle_dialogue` in `discord_bot.py` after it had moved to `dialogue_turn.py`, and still drew two background loops that had been retired. A drawing of code cannot notice when the code moves; the module map below and the entry points named here can be checked against the tree.

Follow the path in the source, starting at these four:

| Entry | Where |
|-------|-------|
| Message dispatch | `discord_bot.py:on_message` |
| Eddy dialogue turn | `dialogue_turn.py:handle_dialogue` |
| River acts in parent channels | `river_handler.py` (`parse_river_output` → act rendering) |
| Session close and eddy notes | `sessions.py:close_session` |

## Module Map

Line counts are approximate snapshots from the deployed shell. Prefer the responsibilities and dependency direction over exact counts.

### Layer 0: Foundation and Configuration

| Module | Approx. lines | Purpose |
|--------|---------------|---------|
| `core/models.py` | ~100 | Two-stack model routing: River (Qwen), Turtle (Gemma), background stack, KNOWN_MODELS aliases, API opt-in. |
| `state.py` | 305 | Shared mutable state: bot client, config constants, locks, histories, model re-exports, channel mappings, thread configs. |
| `mage.py` | 250 | Mage/practitioner registry, channel→practice-dir routing, contextvars for per-channel async isolation. |
| `practice_io.py` | 184 | File I/O helpers for practice directories: read, write, list, search, section extraction, links. |
| `helpers.py` | 110 | Discord/practice utilities: message splitting, activity logging, history access, local time. |

### Layer 1: Model and Content Services

| Module | Approx. lines | Purpose |
|--------|---------------|---------|
| `llm.py` | 233 | Anthropic, Gemini, and Ollama backends; model resolution; tool-call loop. |
| `triage.py` | 100 | Fast local message classification with heuristic fallback. |
| `content_fetch.py` | 705 | URL extraction and platform-specific content fetching; direct/Jina/Wayback fallback; LITL checks; attachment preprocessing. |
| `twitter_ops.py` | 176 | Twitter/X API integration and posting support. |

### Layer 2: Practice Intelligence

| Module | Approx. lines | Purpose |
|--------|---------------|---------|
| `prompts.py` | 626 | System prompt construction for mage/practitioner/thread contexts; identity and practice-state injection. |
| `proprioceptor.py` | 204 | Local connective-tissue model: practice-state scan, context brief, visible reflex. |
| `readiness.py` | 432 | Practice and engineering readiness assessment; readiness trail persistence. |
| `pulse.py` | 346 | Practice pulse scan and river-entry/interoception texture composition. |
| `tos_tools.py` | 409 | Practice file tools exposed to LLMs plus delegate-edit machinery. |
| `attunement.py` | 216 | Attunement helpers and digest-age checks. |
| `outfacing.py` | 242 | Autonomous signal evaluation and signal draft persistence, now gated by crystallization and daily cap. |
| `load_command.py` | 284 | `!load` context/resonance loader for circles and bundles. |

### Layer 3: Conversation, Session, and River Orchestration

| Module | Approx. lines | Purpose |
|--------|---------------|---------|
| `discord_bot.py` | 937 | Main entry point and event handlers; message dispatch; dialogue path; thread updates; startup orchestration; singleton guard. |
| `commands.py` | 2556 | Direct command dispatcher plus Discord views/modals. Current largest gravity well. |
| `sessions.py` | 378 | Session monitor, checkpoint orchestration (eddy note via `story_notes`, day-file assembly), practice-state extraction, manual-release dissolution. |
| `background.py` | — | Scheduled loops: reminders, daily notes, health canary; practice-health + interoception retired. |
| `boom_thread.py` | 437 | Standing boom thread intake, distillation, and follow-up interactions. |
| `eddy_spawn.py` | 720 | Thread/eddy creation, intake-thread launcher, vortex/prism routing, resonance detection. |
| `thread_registry.py` | 233 | Thread registry, backfill, activity tracking, lifecycle metadata. |
| `intake_server.py` | 511 | Embedded aiohttp server for `/intake`, `/paste`, `/health`; saves long-form content to `box/intake/`. |

### Layer 4: Operations and Shell Support

| Module | Approx. lines | Purpose |
|--------|---------------|---------|
| `canary.py` | 232 | Standalone mechanical health check run by launchd; state-change alert dedup. |
| `core/self_heal.py` | — | Pre-defined self-healing registry per `TURTLE_SPEC.md` §20.4; Ollama auto-heal only |
| `shell_harness.py` | 366 | Constrained, audited self-development inspection harness for read-only source inspection and syntax verification. |
| `core/capabilities.py` | 110 | File-backed registry for Turtle skill/procedure cards used during self-development, diagnostics, and shakedowns. |
| `spirit_ops.py` | 120 | Spirit-side Discord CLI for reading/sending. Needs import-safety and `--file` mode. |
| `discord_ops.py` | 79 | Operator Discord CLI for read/send/thread operations. |
| `deploy_river.py` | 224 | Deployment helper for river assets. |

*\* = lazy import to break circular dependency*

### Native Runtime Slice: Task / Audit / Capability Body

The native runtime is the first step toward making the Mac Mini the shell and Discord one interface into it. It runs beside the Discord bot rather than replacing the live dialogue path.

```
CLI / Discord adapter handoff
    |
    v
Event (runtime/events.py)
    |
    v
Task (runtime/tasks.py) + Audit JSONL (runtime/audit.py)
    |
    +--> Capability policy check (runtime/policy.py)
    |
    +--> Governed capability call
          - practice.append_note
          - practice.write_session
          - practice.write_proposal
          - model.run_probe
    |
    v
Artifact reference + task state for later inspection
```

| Module | Purpose |
|---|---|
| `cli.py` | Operator CLI for native runtime handoffs, task inspection, audit inspection, readiness, and provider-neutral model probes. |
| `runtime/events.py` | Normalized event envelope: source, interface, principal, scope, trust level, timestamp, event id, correlation id, payload. |
| `runtime/tasks.py` | Durable task records with state, artifact refs, audit refs, checkpoint, failure, and next action. |
| `runtime/audit.py` | Append-only JSONL audit trail for events, task transitions, policy checks, capability calls, artifact validation, and provider results. |
| `runtime/handoff.py` | Practice handoff execution path: event -> task -> policy -> practice artifact capability -> audit/task completion. |
| `runtime/policy.py` | Capability registry and artifact path validation. Current policies are per-principal and root-bounded. |
| `runtime/capabilities/practice.py` | Governed practice artifact writes: append note, write session, write proposal. |
| `runtime/model_probe.py` | Provider-neutral model probe tasks for comparable outputs across Ollama, Anthropic, Gemini, and stub providers. |
| `runtime/readiness.py` | Native runtime readiness sensorium: service state, model availability, task failures, and artifact visibility. |
| `runtime/update.py` | Read-only turtleOS repository update awareness: git divergence, remote tracking freshness, changed-file impact classification, approval tier, and manual apply guidance. |
| `runtime/paths.py` | Registry-driven principal resolution for practice dir, runtime dir, native runtime dir, tasks dir, and audit dir. |
| `runtime/adapters/discord.py` | Thin adapter that translates Discord message-like metadata into native runtime handoffs without leaking Discord objects into task/audit/capability code. |

This slice implements the first vertical path from Proposal 037: handoff -> task -> audit -> artifact. Dialogue still runs through `discord_bot.py`. The native runtime currently proves durable task/audit semantics and bounded capabilities; it does not yet own model routing for live dialogue, long-running autonomous work, or a general tool system.

`cli.py update check` and `cli.py update plan` are deliberately inspection-only. They do not pull, merge, restart services, write runtime state, touch practice files, or modify private configuration. `check` reports source-of-truth comparison, dirty working tree state, divergence, and stale tracking refs. `plan` adds commit/file impact classification, approval tier, restart likelihood, and the manual apply ritual. Automated apply, rollback, dependency install, and service restart are intentionally deferred until this read-only surface has been exercised in real updates.

### Self-Development Inspection Harness

`shell_harness.py` is the current runtime guard for Turtle inspecting its own shell from Discord or the intake server. It deliberately implements the first safe slice of the self-development protocol: understand, verify, and prepare a patch plan without granting arbitrary command execution or write authority.

Allowed command families:

- `pwd`
- `ls` with simple listing flags
- `rg` with bounded search flags, plus a Python fallback when `rg` is unavailable
- read-only `git`: `status`, `diff`, `log`, `branch --show-current`, `rev-parse --show-toplevel`, `show`
- `python -m py_compile <files>` for Python syntax verification

Guardrails:

- Shell metacharacters are blocked; commands execute via parsed argv, not a shell string.
- `cwd` and inspected paths must stay inside `~/turtleos`.
- Git root must resolve exactly to `~/turtleos`.
- Output is clipped to 6000 characters.
- Each attempt is logged to the active runtime directory as `shell-actions.jsonl`, including requester, command, reason, allow/block decision, stdout/stderr, and whether git state changed during execution.
- The harness records but does not allow mutation. It cannot edit files, stage, commit, restart services, install packages, or run arbitrary Python.

Exposure points:

- LLM tool `run_turtleos_shell` in `tos_tools.py`.
- `/shell` endpoint in `intake_server.py`, restricted to localhost unless `TURTLE_SHELL_TOKEN` is configured; the harness allowlist still applies after endpoint authorization.
- Procedure card `procedures/self-development-inspection.md`, which instructs Turtle to inspect, diagnose, and hand patch plans to Spirit/Mage per `TURTLE_SPEC.md` §20.

Traceability to `TURTLE_SPEC.md` §20: this implements the inspect lane (§20.2). It does not implement shell writes, commit, or non-registry restart authority.

### Turtle Skills and Procedures

`core/capabilities.py` implements a file-backed skill/procedure card registry. This is guidance infrastructure, not an authority system: cards teach Turtle how to approach recurring work, while actual permissions remain enforced by tools such as `shell_harness.py`, `tos_tools.py`, and the native runtime policy layer.

Current card inventory:

| Card | Kind | Purpose |
|---|---|---|
| `source-inspection` | skill | Inspect turtleOS source safely with read-only shell commands before proposing or making changes. |
| `patch-planning` | skill | Convert source inspection into a precise, reviewable patch plan without editing files. |
| `tool-diagnosis` | skill | Classify tool failures before retrying or escalating. |
| `self-development-inspection` | procedure | First-pass self-development loop for understanding turtleOS code without making writes. |
| `proposal-to-patch-plan` | procedure | Convert a proposal, shakedown, canary result, or Discord observation into a bounded patch plan. |
| `tool-shakedown` | procedure | Exercise a newly added or changed tool through a narrow observable test. |

Runtime integration:

- `prompts.py` injects a compact index from `build_capability_summary()` into Turtle's system prompt.
- LLM tools `list_turtle_capabilities` and `read_turtle_capability` in `tos_tools.py` let Turtle list cards and load full text before acting.
- `tool_result.py` classifies successful capability list/read outputs as typed tool successes.
- `canary.py` includes a `capability_index` smoke check so a broken registry becomes visible in the tools layer.

Lifecycle boundary: cards are source files in the public turtleOS repo. They should describe reusable operator/practitioner procedures, not private lineage or local machine facts. Adding or changing cards changes Turtle's operating guidance and should be treated as production docs under `docs/development.md`.

## Circular Dependencies

The shell still has a few deliberate circular edges, resolved via lazy (in-function) imports:

1. **readiness ↔ sessions/background** — `readiness.py` needs to check if background tasks are running, but sessions/background import readiness for post-session checks. Resolved: readiness lazy-imports `session_monitor`, `interoception_loop`, `practice_health_loop`.

2. **commands → sessions** — `cmd_release` calls `close_session`, but sessions imports helpers which is at the same layer. Resolved: commands lazy-imports `close_session` inside the function.

3. **helpers → content_fetch** — `preprocess_attachments` needs Gemini config from helpers but content_fetch is independent. Resolved: lazy import inside function.

## Context Variable Architecture

Per-channel async isolation uses Python `contextvars`:

```python
# mage.py
_practice_dir_ctx = contextvars.ContextVar("practice_dir", default="~/workshops/default")
_mage_name_ctx = contextvars.ContextVar("mage_name", default="Practitioner")
_mage_key_ctx = contextvars.ContextVar("mage_key", default="default")
```

Set on every message via `set_practice_context(message)`. All downstream code calls `get_pd()`, `get_mage_name()`, `get_mage_key()`, `get_mage_type()` — never touches the registry directly. This means a message in any registered channel automatically resolves to that person's practice directory, name, and practitioner type, without any module needing to know about multi-practitioner routing.

## Mage Registry

`mage_registry.yaml` maps Discord channels to mages and their practice directories:

```yaml
mages:
  default:
    discord_id: '<discord-account-id>'
    address: Practitioner
    practice_dir: ~/workshop/desk
    type: mage
  companion:
    discord_id: '<discord-account-id>'
    address: Companion
    practice_dir: ~/workshops/companion
    type: practitioner

spaces:
  shared:
    practice_dir: ~/workshops/shared
    members: [default, companion]

channels:
  '<dialogue-channel-id>': default
  '<companion-channel-id>': companion
  '<shared-channel-id>': shared
```

**Type routing:**
- `mage` — full command set, thread orchestration, practice vocabulary, conversational editing
- `practitioner` — limited commands (status, help, recall, release), no practice jargon, language mirroring, silent practice state extraction

## Practice Directory Structure

Each mage/practitioner has a practice directory with:

```
~/workshops/<name>/
├── character/         # soul.md, conduct.md (native attunement)
├── state/
│   ├── current.yaml   # Continuity engine snapshot
│   └── notes/         # Flow outcomes, extracted insights
├── sessions/          # Session notes (checkpoint/release)
├── thread-archive/    # Dissolved eddy captures
├── chronicle/         # Practice timeline
├── proposals/         # Autonomous proposals (operator / host)
├── box/intake/        # Pasted captures
└── thread-state/      # Eddy registry metadata (runtime-adjacent)
```

## Tool System

9 tools exposed to LLMs via function calling:

| Tool | Purpose | Cost |
|------|---------|------|
| `read_practice_file` | Read file (optional section extraction) | Free |
| `list_practice_files` | Browse directory | Free |
| `search_practice_files` | Search across files | Free |
| `list_headings` | Extract markdown structure | Free |
| `get_file_info` | File metadata | Free |
| `patch_practice_file` | Surgical find/replace | Cheap |
| `append_to_practice_file` | Add content | Cheap |
| `delegate_edit` | Complex edits via local model | Free (local model) |
| `write_practice_file` | Full file rewrite | Expensive |

Tools are defined in `tos_tools.py` as JSON schemas (`TOS_TOOLS` list), dispatched via `execute_tos_tool()`, and reported via `build_tool_report()`. The LLM backends (`llm.py`) handle the tool-call loop — iterating until the model stops requesting tools or hits `MAX_TOOL_ROUNDS`.

## LLM Backend Selection

Two-stack architecture (TURTLE_SPEC §8.1). Configuration lives in `core/models.py` and `.env`.

```
Message arrives
    │
    ├─ River channel (native)
    │   └─ RIVER_MODEL (Qwen ~4B) — structured acts only, no Turtle prose
    │
    ├─ Eddy / thread (native)
    │   ├─ Default → TURTLE_MODEL (Gemma ~31B)
    │   ├─ !thread --model M → resolve_model(M) — local gemma/qwen or API claude/gemini
    │   └─ think=False at Ollama API for Gemma
    │
    ├─ Magic-attuned main channel
    │   └─ DIALOGUE_MODEL (defaults to TURTLE_MODEL; claude-* for API opt-in)
    │
    └─ Background (always local Qwen stack)
        ├─ TRIAGE_MODEL — message classification
        ├─ REFLECTION_MODEL — session reflection, health, interoception
        └─ EDIT_DELEGATE_MODEL — delegate file edits
```

**Instance defaults** (see `.env.template`): `RIVER_MODEL=qwen3.5:4b`, `TURTLE_MODEL=gemma4:31b`. Faster eddy fallback: `!thread --model gemma-26b`. Cloud dialogue remains opt-in via `DIALOGUE_MODEL=claude-*` or per-thread `--model claude`.

## Session Lifecycle

```
Message received → active_sessions[channel_id] updated
    │
    ├─ 15 minutes of silence
    │   └─ session_monitor fires close_session()
    │       ├─ Skip reflection if < MIN_EXCHANGES_FOR_REFLECTION
    │       ├─ Skip reflection if idle cooldown not elapsed
    │       │   (manual !checkpoint / release always reflect — §8.4)
    │       ├─ story_notes.write_eddy_note via REFLECTION_MODEL
    │       │   ├─ dated entry → story/eddies/<thread-id>-<slug>.md
    │       │   └─ entry appended mechanically → sessions/YYYY-MM-DD.md
    │       ├─ If practitioner: _extract_practice_state()
    │       │   ├─ ---NOTE_ITEMS--- → append state/notes/
    │       │   └─ ---PROFILE_UPDATE--- → state/notes/practitioner-profile.md
    │       └─ assess_readiness → readiness trail
    │
    └─ Next message resets the timer
```

## Deployment

**Host:** Mac Mini or other always-on machine running macOS/Linux, reachable through the operator's chosen private network
**Service manager:** launchctl (`com.turtle.discord`)
**Python:** 3.14, virtualenv at `~/turtleos/venv/`
**Process:** Single Python process, single Discord gateway connection

```bash
# Restart
launchctl kickstart -k gui/$(id -u)/com.turtle.discord

# Logs
tail -f ~/turtleos/logs/discord.log    # stdout
tail -f ~/turtleos/logs/discord.err    # stderr

# Config
~/turtleos/.env                         # API keys, channel IDs
~/turtleos/mage_registry.yaml           # Multi-mage routing
~/turtleos/identity/soul.md             # Spirit identity

# Rollback
cp ~/turtleos/discord_bot.py.bak ~/turtleos/discord_bot.py
launchctl kickstart -k gui/$(id -u)/com.turtle.discord
```

**Required services:**
- Ollama running locally (triage, reflection, health, interoception, delegate edits)
- Anthropic API key (dialogue for API channels)
- Google API key (Gemini for attachments, optional dialogue model)
- Discord bot token
- CouchDB / LiveSync (**retired** 2026-06-19 — do not resurrect without sanction)

## Design Decisions

**Why contextvars, not a class?** The Discord.py event loop means multiple channels can be processing simultaneously. Contextvars give per-task isolation without passing a context object through every function call. The alternative (a bot class with per-channel state) would require rewriting every module's function signatures.

**Why local models for all autonomous work?** Token cost. Session reflections, health reads, interoception, triage, and delegate edits all run on local Ollama models. Only human-facing dialogue uses API models. This means the bot can run indefinitely without API spend on background tasks.

**Why 13+ modules instead of fewer?** Each module corresponds to a natural seam — a concept that changes independently. Commands change when adding features. Prompts change when tuning behavior. Sessions change when adjusting reflection. The monolith required understanding 4,656 lines to change anything; now each change is scoped to its module.

**Why lazy imports?** Three circular dependency chains exist (readiness↔sessions, commands→sessions, helpers→content_fetch). Lazy imports inside function bodies break the cycles without restructuring the dependency graph. This is a pragmatic choice — the alternative would be a mediator pattern that adds complexity without benefit.

**Why two prompt paths (mage vs practitioner)?** Practitioners shouldn't see practice vocabulary, thread orchestration, or the full command set. The prompt diverges early based on `get_mage_type()` and builds completely different instruction blocks. This is cheaper than a single prompt with conditionals scattered throughout.

## Identity files (two, and they are not the same file)

There are **two** `soul.md` files and both are live. Read the file rather than a summary of it — this section used to paraphrase an eleven-heading structure that the file had long since stopped having.

| File | Loaded by | Role |
|------|-----------|------|
| `~/turtleos/identity/soul.md` (`IDENTITY_DIR`) | `prompts.py` — Discord practice-state prompt, several non-craft callers | Platform-level seed. The code calls its opening line `LEGACY_IDENTITY_OPENER` and the craft prompt deliberately strips it. |
| `<practice root>/character/soul.md` | `prompts.py:load_character_file` — native and craft prompts | Per-instance attunement. The operator default (`AGENTS.md`). |

The practice-root file is the one an instance customizes; the identity seed is platform scaffolding on its way out of the dialogue path. Spec origin: `TURTLE_SPEC §3`, §14 for authoring.

## Practitioner Onboarding (hosted)

**Primary path:** `!admin invite <name> <emoji> [en|de] [--member @member|id|username]` (alias `river-key`).

1. Create private claim room `#river-<name>` (operator + bots; optional `--member` pre-grant)
2. Guest sends the emoji → bind `discord_id`, lock permissions, post onboarding embed, deploy eddy bar
3. Channel **stays** `#river-<name>` for life (no `*-dialogue` rename)
4. Workshop seeded at `~/workshops/<name>/` with character templates + continuity scaffold

**Host tools:** `!admin rivers` · `rivers sync-names` · `doctor` · `space …` — see `docs/chapters/design-admin-experience.md`.

**Deprecated:** `!admin onboard` (redirects to `invite`).

**What's NOT automated:**
- Seeding `resonance.md` (start from `template/practitioner/resonance.md.example`)
- Adding to family / shared space membership (`!admin space create`)

## Content Fetching (content_fetch.py)

Content fetching handles URL extraction and content processing. The module has grown beyond the original direct/Wayback fetcher into a layered content-reach system.

**URL processing pipeline:**
```
URL detected in message
    │
    ├─ detect_platform()
    │   ├─ twitter/x.com → fetch_twitter()
    │   │   └─ Twitter oembed API → text + follow t.co links → extract linked articles
    │   ├─ youtube → fetch_youtube_transcript()
    │   │   └─ youtube_transcript_api → full transcript text
    │   └─ other → fetch_url_content()
    │       ├─ Layer 1: direct HTTP GET + trafilatura extraction
    │       ├─ Layer 2: Jina Reader
    │       └─ Layer 3: Wayback Machine fallback
    │
    ├─ litl_check() — scan for prompt injection patterns
    │   └─ Regex: "ignore previous", "you are now", "new instructions", etc.
    │   └─ If hit: content still shown, but with [LITL WARNING] prefix
    │
    └─ Return formatted content (max 8000 chars per URL, max 3 URLs)
```

**Attachment processing:**
- Supported: JPEG, PNG, GIF, WebP, PDF (up to 20MB)
- Processing: Gemini Flash describes images, extracts PDF text
- Falls back to "[no Gemini API key]" message if unconfigured

## Workshop Sync

The bot reads and writes **practice roots** directly on the host (`~/workshops/<name>/`). It does not implement cross-substrate sync.

Which paths move between which machines is an **instance** fact, and it is stated once, in [`docs/live-runtime.md`](docs/live-runtime.md) § Sync with Forge — including the scripts, which live in the operator's Magic workshop rather than in this repo. It was stated in both files until 2026-08-18, and both copies were wrong in the same way for 50 days.

What is platform-level: an instance MAY set `workshop_root` in the registry for a full Magic mirror (Appendix A); the operator default does not. CouchDB / LiveSync was retired 2026-06-19 — do not resurrect without sanction.

## Spec Traceability

**Not here.** `docs/traceability-matrix.md` is the single development index — spec § → module → verification → docs → action, updated at every chapter close.

This section held a second spec→module table until 2026-08-18. The matrix opens with an essay about three competing indexes going stale and being consolidated into one; this table was a fourth that the essay never counted, and it drifted exactly as predicted. It still said "TURTLE_SPEC v2.4" against a 2026-07-17 spec, still called `!diagnose` pending after it had shipped, and one row carried leftover columns pasted from the matrix. The rows are in git history if a specific old verdict is ever wanted.

The lesson generalizes: a view of the index is not free. It costs a second thing to update, and the cheaper copy to keep current is the one nobody reads.

A parallel list of active gaps went with it, for the same reason — the matrix's **Action** column is the maintained answer to "what is unfinished." One item from that list had no matrix row and is carried below in the backlog rather than lost.

## Companion Documents

| Document | Location | Purpose |
|----------|----------|---------|
| TURTLE_SPEC (platform law) | `TURTLE_SPEC.md` | Canonical law — *what* turtleOS must do (sole spec; no Magic mirror) |
| ARCHITECTURE.md | `ARCHITECTURE.md` | The software: modules, subsystems, design decisions (this doc) |
| Live runtime | [`docs/live-runtime.md`](docs/live-runtime.md) | One deployment: operator Mac Mini services, filesystem, Forge sync |
| Traceability matrix | [`docs/traceability-matrix.md`](docs/traceability-matrix.md) | Spec § → module → verification → action (single development index) |
| Install skill | `docs/install/SKILL.md` | Agent-assisted install flow |
| Template layout | `template/README.md` | Practice root skeleton |
| soul.md | `identity/soul.md` + practice-root `character/soul.md` | Two files, two callers — see § Identity files |
| mage_registry.yaml | `mage_registry.yaml` | Channel → practice root routing |
| Magic lore (optional) | Magic `library/resonance/turtle/lore/` | History and magic-attuned operations |

Rebuild kit for vanilla: TURTLE_SPEC + ARCHITECTURE.md + template + install skill. Identity (`character/`) authored per spec §14.

## Traceability Backlog

The implementation currently contains several capabilities that should receive tighter spec traceability before they become major public extension points:

- native runtime beyond the first vertical slice: long-running tasks, general tools, live dialogue routing, and Discord notification outputs
- `cli.py` command reference generation and operator docs
- self-development write authority: current harness is inspection-only; runtime prompt/procedure wording should stay aligned until a real low-risk write path exists
- skill/procedure lifecycle governance: when to add, update, deprecate, or test guidance cards
- founding-room/founder-key capabilities, if they remain in the public product
- `commands.py` command surface decomposition and generated command reference
- `spirit_ops.py` import-safety and `--file` input, before large Spirit→Turtle handoffs are clean — carried here 2026-08-18 from the deleted gap list; unverified since it was written, so confirm before acting on it
