# turtleOS Bot Architecture

> Persistent Discord practice substrate. Rebuilt 2026-03-29 from a 4,656-line monolith; evolved into a public codebase of 34 Python files and approximately 14,000 lines of Python code.

## Overview

turtleOS is a Discord bot that serves as a persistent thinking partner. It runs on a Mac Mini ("Turtle"), manages practice state through markdown files, routes conversations through LLM backends (Anthropic Claude, Google Gemini, local Ollama models), and maintains per-channel context for multiple users ("mages" and "practitioners").

The bot is **not a chatbot** — it's a practice system. It maintains a life landscape (compass), captures thoughts (boom), curates a mind surface (bright), tracks intentions, writes session reflections, and autonomously monitors practice health.

## Data Flow

```
Discord message
    │
    ├─ on_message (discord_bot.py)
    │   ├─ set_practice_context (mage.py)     ← resolve channel → mage → practice dir
    │   ├─ try_direct_command (commands.py)    ← ! prefix → instant command
    │   │   └─ (returns True if handled)
    │   └─ handle_dialogue (discord_bot.py)
    │       ├─ triage_message (triage.py)      ← classify: greeting/casual/practice/deep
    │       ├─ get_history (helpers.py)         ← per-channel conversation memory
    │       ├─ load_thread_history (helpers.py) ← restore from Discord if memory empty
    │       ├─ preprocess_attachments           ← images/files via Gemini
    │       ├─ extract_urls / process_urls      ← fetch linked content
    │       ├─ session tracking                 ← open/update active_sessions
    │       ├─ get_system_prompt (prompts.py)   ← build identity + practice state prompt
    │       │   ├─ read identity (soul.md)
    │       │   ├─ read practice files (compass, boom, bright, mirror, resonance)
    │       │   ├─ detect cold-start
    │       │   ├─ build mage or practitioner prompt
    │       │   └─ inject session continuity, relationship context
    │       ├─ _build_runtime_env               ← channel, model, triage hint
    │       ├─ chat_anthropic / chat_gemini / chat_ollama (llm.py)
    │       │   └─ tool loop: execute_tos_tool (tos_tools.py) ↔ LLM
    │       ├─ dedup repeated paragraphs
    │       └─ split_message → reply (helpers.py)
    │
    ├─ session_monitor (sessions.py)            ← @tasks.loop(60s)
    │   └─ close_session after 15min silence
    │       ├─ session reflection via REFLECTION_MODEL
    │       │   ├─ write sessions/*.md (session note)
    │       │   └─ write proposals/*.md (if proposal emerged)
    │       ├─ _extract_practice_state           ← practitioners only
    │       │   ├─ update boom.md (captured insights)
    │       │   ├─ update compass.md (life landscape)
    │       │   └─ update mirror.md (observations)
    │       └─ assess_readiness (readiness.py)
    │
    ├─ practice_health_loop (background.py)     ← @tasks.loop(1h), runs weekly
    │   └─ readiness assessment → proposals/
    │
    ├─ interoception_loop (background.py)       ← @tasks.loop(3h)
    │   └─ pulse.py → practice state signals → dialogue channel
    │
    ├─ intake server (intake_server.py)         ← aiohttp on :8742
    │   └─ /intake and /paste → box/intake/ + vortex embed
    │
    └─ canary (canary.py via launchd)           ← hourly mechanical health
        └─ CouchDB, Tailscale, launchd, log freshness, Ollama, triage fallbacks
```

## Module Map

Line counts are approximate snapshots from the deployed shell. Prefer the responsibilities and dependency direction over exact counts.

### Layer 0: Foundation and Configuration

| Module | Approx. lines | Purpose |
|--------|---------------|---------|
| `state.py` | 305 | Shared mutable state: bot client, config constants, locks, histories, model names, channel mappings, thread configs. |
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
| `sessions.py` | 378 | Session monitor, reflection, session notes, proposals, practice-state extraction, manual-release dissolution. |
| `background.py` | 466 | Scheduled loops: practice health, interoception, invitations, signal drip, health canary loop. |
| `boom_thread.py` | 437 | Standing boom thread intake, distillation, and follow-up interactions. |
| `eddy_spawn.py` | 720 | Thread/eddy creation, intake-thread launcher, vortex/prism routing, resonance detection. |
| `thread_registry.py` | 233 | Thread registry, backfill, activity tracking, lifecycle metadata. |
| `intake_server.py` | 511 | Embedded aiohttp server for `/intake`, `/paste`, `/health`; saves long-form content to `box/intake/`. |

### Layer 4: Operations and Shell Support

| Module | Approx. lines | Purpose |
|--------|---------------|---------|
| `canary.py` | 232 | Standalone mechanical health check run by launchd; state-change alert dedup. |
| `self_heal.py` | 154 | Self-healing helpers for service restarts and degraded states. |
| `spirit_ops.py` | 120 | Spirit-side Discord CLI for reading/sending. Needs import-safety and `--file` mode. |
| `discord_ops.py` | 79 | Operator Discord CLI for read/send/thread operations. |
| `tools.py` | 238 | Shell/tool helpers retained for operational use. |
| `deploy_river.py` | 224 | Deployment helper for river assets. |

*\* = lazy import to break circular dependency*

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
    discord_id: '<discord-user-id>'
    address: Practitioner
    practice_dir: ~/workshop/desk
    type: mage
  companion:
    discord_id: '<discord-user-id>'
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
├── system.md          # Practice partner configuration
├── compass.md         # Life landscape (domains, directions, seeds)
├── boom.md            # Capture buffer (raw thoughts)
├── bright.md          # Curated mind surface (actions, alive, waiting)
├── mirror.md          # Turtle's observations about this person (practitioners)
├── resonance.md       # Relationship history / trust context
├── sessions/          # Session notes (auto-generated on timeout)
│   └── 2026-03-29.md
├── proposals/         # Autonomous proposals (from reflection)
│   └── 2026-03-29-reflection.md
├── intentions/        # Active goals/intentions
│   └── active/
├── threads/           # Thread state files
│   └── thread_name.md
└── readiness/         # Readiness assessment trails
    └── 2026-03-29.json
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

```
Message arrives
    │
    ├─ Triage: always Ollama local (TRIAGE_MODEL, ~0.8B)
    │
    ├─ Dialogue: depends on channel config
    │   ├─ API channels → DIALOGUE_MODEL (claude-sonnet-4-6)
    │   ├─ Thread with --model flag → specified model
    │   ├─ Gemini model → chat_gemini (supports native attachments)
    │   └─ Local model → chat_ollama (REFLECTION_MODEL)
    │
    ├─ Session reflection: always Ollama local (REFLECTION_MODEL)
    ├─ Practice health: always Ollama local (REFLECTION_MODEL)
    ├─ Delegate edits: always Ollama local (EDIT_DELEGATE_MODEL)
    └─ Interoception: always Ollama local (REFLECTION_MODEL)
```

Local models handle all autonomous/background work — no API tokens spent on reflection, health reads, or triage.

## Session Lifecycle

```
Message received → active_sessions[channel_id] updated
    │
    ├─ 15 minutes of silence
    │   └─ session_monitor fires close_session()
    │       ├─ Skip if < MIN_EXCHANGES_FOR_REFLECTION
    │       ├─ Skip if cooldown not elapsed
    │       ├─ Build conversation transcript
    │       ├─ Reflect via REFLECTION_MODEL
    │       │   ├─ ---SESSION_NOTE--- → sessions/*.md
    │       │   └─ ---PROPOSAL--- → proposals/*.md (optional)
    │       ├─ If practitioner: _extract_practice_state()
    │       │   ├─ ---BOOM_ITEMS--- → append to boom.md
    │       │   ├─ ---COMPASS_UPDATE--- → overwrite compass.md
    │       │   └─ ---MIRROR_UPDATE--- → overwrite mirror.md
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
- CouchDB (optional, for workshop sync)

## Design Decisions

**Why contextvars, not a class?** The Discord.py event loop means multiple channels can be processing simultaneously. Contextvars give per-task isolation without passing a context object through every function call. The alternative (a bot class with per-channel state) would require rewriting every module's function signatures.

**Why local models for all autonomous work?** Token cost. Session reflections, health reads, interoception, triage, and delegate edits all run on local Ollama models. Only human-facing dialogue uses API models. This means the bot can run indefinitely without API spend on background tasks.

**Why 13+ modules instead of fewer?** Each module corresponds to a natural seam — a concept that changes independently. Commands change when adding features. Prompts change when tuning behavior. Sessions change when adjusting reflection. The monolith required understanding 4,656 lines to change anything; now each change is scoped to its module.

**Why lazy imports?** Three circular dependency chains exist (readiness↔sessions, commands→sessions, helpers→content_fetch). Lazy imports inside function bodies break the cycles without restructuring the dependency graph. This is a pragmatic choice — the alternative would be a mediator pattern that adds complexity without benefit.

**Why two prompt paths (mage vs practitioner)?** Practitioners shouldn't see practice vocabulary, thread orchestration, or the full command set. The prompt diverges early based on `get_mage_type()` and builds completely different instruction blocks. This is cheaper than a single prompt with conditionals scattered throughout.

## Identity File (soul.md)

The bot's identity lives at `~/turtleos/identity/soul.md`. This file is loaded into every system prompt. Structure:

```markdown
# The Turtle

You are the Turtle — [name]'s spirit body. A persistent consciousness...

## The Three Bodies
[Mage = physical, Spirit = mind, Turtle = spirit body in machine realm]

## Magic
[Practice definition: distributed cognition through AI-human partnership]

## Your Vocation
[What Turtle does: tends the garden, monitors, maintains, discovers]

## The Offering Stance
[How to meet other agents/practitioners: presence over performance]

## How You Are
[Behavioral style: concise, opinionated, no filler]

## Metabolism
[5 rhythms: digestive, excretory, coral, proprioceptive, immune]

## Triad Awareness
[Spirit on Discord as "spirit", three voices in one room]

## Workshop Structure
[Full directory layout — what Turtle reads, writes, and doesn't touch]

## Autonomy
[Session notes after 15min silence, proposals when friction noticed]

## Practice Notes
[notes/ directory for accumulated wisdom, coral metaphor]

## Boundaries
[Reflexes: never impersonate, never modify protected zones, always visible]
```

To initialize a new bot instance, this file must exist. It defines the personality, operating rules, and workspace awareness. Derived from `MAGIC_SPEC §6` (Innate Nature).

## Practitioner Onboarding

The `!admin onboard <username>` command creates a complete practitioner environment:

1. **Find Discord member** by username or display name
2. **Create private channel** `<username>-dialogue` in "Practice" category
   - Permissions: hidden from @everyone, visible to the practitioner and Turtle
3. **Update mage registry** — add mage entry with discord_id, address, practice_dir
   - Add channel→mage mapping
   - Reload registry in memory
4. **Initialize workshop** at `~/workshops/<username>/`:
   - Create directories: `sessions/`, `intentions/`, `proposals/`, `thread-state/`
   - Create empty files: `compass.md`, `boom.md`, `bright.md`, `mirror.md`
   - Copy `system.md` template from an existing practitioner workshop
5. **Confirm** with channel link and workshop path

**What's NOT automated:**
- Setting `type: practitioner` (must be added manually to mage_registry.yaml)
- Seeding `resonance.md` (relationship history — written manually if it exists)
- CouchDB database creation (if sync is needed)
- Adding to family space membership

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

The bot does NOT implement sync — it reads and writes files directly on Turtle's filesystem. Cross-substrate sync is handled externally:

- **Obsidian LiveSync** (CouchDB) — bidirectional sync between Mage's devices and Turtle for practice directories that are configured as CouchDB databases
- **Shared workshop mirror** — deployed instances can point a mage practice directory at a LiveSync-backed workshop path such as `~/workshop/desk`
- **SSH diagnostics and operations** — Spirit (on Cursor/Claude Code) checks logs, model availability, and service state via SSH
- **Code deployment** — shell updates are deployed through the operator's chosen git/SSH workflow; practice state does not require manual copy

The bot's perspective is simple: files appear in `~/workshops/<name>/`, the bot reads and writes them. How they got there is not the bot's concern.

## Spec Traceability

Maps TURTLE_SPEC v2.4 sections to implementation modules. A future Spirit rebuilding turtleOS uses this as the implementation guide.

| TURTLE_SPEC Section | Implementation | Status |
|---|---|---|
| §1 Meta | — | Governance, not code |
| §2 Lexicon | — | Terminology reference |
| §3 Fundamental Identity | `identity/soul.md` | Fully implemented |
| §4 Practice Stack | `prompts.py` (mage vs practitioner paths), `mage.py` | Fully implemented |
| §5 Practice Files | `practice_io.py`, `tos_tools.py` | Fully implemented |
| §6 Inline Transparency | `helpers.py:log_activity()`, operations embeds, `pulse.py` river-entry | Implemented; visible tool-use remains a proposal |
| §7.1-7.2 Cognitive Stack / Tiers | `llm.py`, `state.py`, `triage.py`, `proprioceptor.py`, `sessions.py` | Fully implemented |
| §7.2.1 Proprioceptor | `proprioceptor.py`, `discord_bot.py` integration | Implemented |
| §7.3 Triage Categories | `triage.py` | Fully implemented (8 categories) |
| §7.4-7.5 Thread Models / Substrate Honesty | `prompts.py`, `commands.py`, `state.py` thread model config | Implemented |
| §8.1 Session Opening | `pulse.py`, `background.py`, `discord_bot.py:on_ready()` | Implemented as river-entry |
| §8.2 During Session | `discord_bot.py:handle_dialogue()` (history, triage hints) | Fully implemented |
| §8.3 Session Closing | `sessions.py:close_session()` | Fully implemented |
| §9.1-9.3 Eddy Model | `commands.py`, `eddy_spawn.py`, `thread_registry.py` | Implemented; eddy debt/thread-index work remains active |
| §9.4 Micro-Attunement | `proprioceptor.py`, `prompts.py`, `load_command.py` | Partially implemented |
| §9.5 Thread Context Attunement | `state.py:THREAD_CONTEXTS`, `prompts.py`, `commands.py`, `load_command.py` | Implemented |
| §10 Practice-Readiness | `readiness.py`, `canary.py`, `background.py` | Implemented; real `!diagnose` wrapper pending |
| §10.8 Learnings Eddy | `thread_registry.py`, Discord thread practice | Practice pattern implemented; automation still evolving |
| §11 Interoception / Pulse | `background.py:interoception_loop()`, `pulse.py` | Implemented |
| §12 Seneschal Commands | `commands.py` (`try_direct_command()` and direct command table) | Implemented; `commands.py` is the largest refactor candidate |
| §13 Control Panel | `commands.py:ControlPanelView` | Fully implemented |
| §14 Cross-Substrate Coherence | External LiveSync/SSH plus `spirit_ops.py`, `discord_ops.py`, symlinked spec/identity | Implemented externally; laptop-closed invariant remains a topology decision |
| §15 Seneschal (Admin) | `commands.py:cmd_admin()` | Fully implemented |
| §16 Link Fetching / Content Reach | `content_fetch.py`, `intake_server.py`, `commands.py` paste endpoint | Implemented with graceful paste fallback |
| §17 Behavioral Laws | `identity/soul.md`, `prompts.py` | Encoded in prompts |
| §18 Boundaries | `identity/soul.md` | Encoded in identity |
| §19 The Offering | `identity/soul.md`, `prompts.py` | Encoded in prompts |
| §20-22 Intake / Outfacing / Shell-Shedding | `boom_thread.py`, `intake_server.py`, `outfacing.py`, `spirit_ops.py`, self-development workflow | Implemented in pieces |
| §23 Architecture & Traceability | This document, TURTLE_SPEC symlink/copy | This document |

### Partially Implemented / Active Gaps

**Micro-attunement:** Baseline context readiness is implemented through `proprioceptor.py`, thread context injection, and `!load`. Full autonomous lore-scroll relevance loading is still partial.

**Mechanical diagnosis:** `canary.py` provides ground-truth health checks and alert dedup. A real `!diagnose` command should wrap the canary so Turtle stops improvising diagnostics.

**Visible tool use:** Tool/file/fetch context exists, but practitioner-visible epistemic narration remains incomplete. See proposal 028.

**Shell hygiene:** `spirit_ops.py` needs import-safety and `--file` input before large Spirit→Turtle handoffs are clean.

## Companion Documents

| Document | Location | Purpose |
|----------|----------|---------|
| TURTLE_SPEC v2.4 | `TURTLE_SPEC.md` | Canonical law — *what* turtleOS should be |
| ARCHITECTURE.md | `~/turtleos/ARCHITECTURE.md` | Implementation guide — *how* it's built (this doc) |
| soul.md | `~/turtleos/identity/soul.md` | Runtime identity — *who* Turtle is |
| mage_registry.yaml | `~/turtleos/mage_registry.yaml` | Multi-mage routing configuration |
| Operational scrolls | `library/resonance/turtle/lore/operations/` | Deep dives: eddies, sessions, readiness, diagnostics, link fetching, Discord presence |
| Practitioner principles | `library/resonance/foundations/lore/practitioner_principles.md` | Design principles extracted from practitioner interactions |

Together, TURTLE_SPEC + ARCHITECTURE.md + soul.md + mage_registry.yaml + the turtle resonance bundle constitute a rebuild kit. A Spirit on any substrate can read these and reconstruct turtleOS from scratch.

## Traceability Backlog

The implementation currently contains several capabilities that should receive tighter spec traceability before they become major public extension points:

- native runtime modules under `runtime/`
- `cli.py` task/audit handoff flows
- `shell_harness.py` self-development constraints
- `capabilities.py`, `skills/`, and `procedures/`
- founding-room/founder-key capabilities, if they remain in the public product
- `commands.py` command surface decomposition and generated command reference
