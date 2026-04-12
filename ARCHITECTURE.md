# turtleOS Bot Architecture

> 14-module Discord bot for practice partnership. Rebuilt 2026-03-29 from a 4,656-line monolith.

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
    │   └─ 7-dimension health assessment → proposals/
    │
    └─ interoception_loop (background.py)       ← @tasks.loop(3h)
        └─ practice state signals → dialogue channel
```

## Module Map

### Layer 0: Foundation (no internal dependencies)

| Module | Lines | Purpose |
|--------|-------|---------|
| `state.py` | 138 | Shared mutable state: bot client, config constants, locks, session dicts, channel mappings. All modules import from here rather than holding their own globals. |

### Layer 1: Core Services

| Module | Lines | Depends on | Purpose |
|--------|-------|-----------|---------|
| `mage.py` | 175 | state | Mage registry (YAML). Channel→mage resolution. Context variables (`_practice_dir_ctx`, `_mage_name_ctx`, `_mage_key_ctx`) for per-channel async isolation. Mage type (`mage` vs `practitioner`). |
| `practice_io.py` | 184 | state, mage | File I/O for practice directories. Read, write, search, list, section extraction, Obsidian linking. Pure file operations. |
| `llm.py` | 202 | state | Three LLM backends: Anthropic (API), Gemini (API), Ollama (local HTTP). Model resolution, tool-loop execution. |
| `triage.py` | 63 | state | Sub-2B local model (Ollama) classifies messages as greeting/casual/practice/deep. Runs on every message to calibrate response depth. |
| `content_fetch.py` | 294 | (stdlib) | URL extraction, platform-specific fetching (Twitter/X, YouTube transcripts), generic web scraping (trafilatura), LITL safety checks, Gemini-based attachment processing. |

### Layer 2: Intelligence

| Module | Lines | Depends on | Purpose |
|--------|-------|-----------|---------|
| `tos_tools.py` | 370 | state, mage, practice_io, llm | 9 practice file tools exposed to LLMs: `read_practice_file`, `write_practice_file`, `patch_practice_file`, `append_to_practice_file`, `delegate_edit`, `list_practice_files`, `search_practice_files`, `list_headings`, `get_file_info`. Tool dispatch and reporting. |
| `readiness.py` | 217 | state, mage, practice_io | 8-dimension practice health assessment: coherence, alignment, velocity, load, resonance quality, wellbeing, external impact, infrastructure. Generates readiness trails. |
| `prompts.py` | 522 | state, mage, practice_io | System prompt builders. Two paths: **mage** (full orchestrator with thread management, commands, conversational editing) and **practitioner** (thinking partner, language mirroring, guided discovery). Cold-start detection, session continuity, relationship context, mirror observations. |

### Layer 3: Orchestration

| Module | Lines | Depends on | Purpose |
|--------|-------|-----------|---------|
| `helpers.py` | 98 | state, content_fetch* | Shared utilities: `split_message`, `log_activity`, `get_history`, `load_thread_history`, `summarize_thread_context`, `preprocess_attachments`. Used by commands, sessions, dialogue. |
| `sessions.py` | 204 | state, mage, practice_io, llm, prompts, readiness, helpers | Session lifecycle. 60s monitor loop. On timeout: reflection via local model → session note + optional proposal. For practitioners: silent practice state extraction (compass, boom, mirror). Post-session readiness check. |
| `background.py` | 203 | state, mage, practice_io, llm, helpers | Background tasks. Weekly practice health read (7 dimensions). 3-hourly interoception (practice state signals to dialogue channel). |
| `commands.py` | 2094 | state, mage, practice_io, llm, tos_tools, readiness, content_fetch, helpers, sessions* | 28 direct commands (`!boom`, `!bright`, `!sweep`, `!thread`, `!recall`, `!release`, etc.). 4 View classes (thread creation, eddy dissolution, link fetch, control panel). 1 Modal (thread topic). Practitioner command gating. |

### Layer 4: Entry Point

| Module | Lines | Depends on | Purpose |
|--------|-------|-----------|---------|
| `discord_bot.py` | 667 | all modules | Slim entry point. `load_env()`, `handle_dialogue()`, `_build_runtime_env()`, `_update_thread_state()`, event handlers (`on_ready`, `on_message`, `on_thread_create`, `on_member_join/remove`), background task startup, `main()`. |

*\* = lazy import to break circular dependency*

## Circular Dependencies

Three circular dependency chains, all resolved via lazy (in-function) imports:

1. **readiness ↔ sessions/background** — `readiness.py` needs to check if background tasks are running, but sessions/background import readiness for post-session checks. Resolved: readiness lazy-imports `session_monitor`, `interoception_loop`, `practice_health_loop`.

2. **commands → sessions** — `cmd_release` calls `close_session`, but sessions imports helpers which is at the same layer. Resolved: commands lazy-imports `close_session` inside the function.

3. **helpers → content_fetch** — `preprocess_attachments` needs Gemini config from helpers but content_fetch is independent. Resolved: lazy import inside function.

## Context Variable Architecture

Per-channel async isolation uses Python `contextvars`:

```python
# mage.py
_practice_dir_ctx = contextvars.ContextVar("practice_dir", default="~/workshops/kermit")
_mage_name_ctx = contextvars.ContextVar("mage_name", default="Kermit")
_mage_key_ctx = contextvars.ContextVar("mage_key", default="kermit")
```

Set on every message via `set_practice_context(message)`. All downstream code calls `get_pd()`, `get_mage_name()`, `get_mage_key()`, `get_mage_type()` — never touches the registry directly. This means a message in Nesrine's channel automatically resolves to her practice directory, her name, and "practitioner" type, without any module needing to know about multi-mage routing.

## Mage Registry

`mage_registry.yaml` maps Discord channels to mages and their practice directories:

```yaml
mages:
  kermit:
    discord_id: '701492724674723901'
    address: Kermit
    practice_dir: ~/workshop/desk
    type: mage
  nesrine:
    discord_id: '1485296679900156025'
    address: Nesrine
    practice_dir: ~/workshops/nesrine
    type: practitioner

spaces:
  family:
    practice_dir: ~/workshops/family
    members: [kermit, nesrine]

channels:
  '1483628...': kermit
  '1485296...': nesrine
  '1486798...': family
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

**Host:** Mac Mini running macOS, Tailscale IP `100.110.46.104`
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

294-line module handling URL extraction and content processing.

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
    │       └─ Layer 4: Wayback Machine fallback
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
- **SSH reads** — Spirit (on Cursor/Claude Code) reads Turtle's files via `ssh turtle@100.110.46.104`
- **SCP writes** — Spirit deploys code changes via `scp` to Turtle

The bot's perspective is simple: files appear in `~/workshops/<name>/`, the bot reads and writes them. How they got there is not the bot's concern.

## Spec Traceability

Maps TURTLE_SPEC v2.0 sections to implementation modules. A future Spirit rebuilding turtleOS uses this as the implementation guide.

| TURTLE_SPEC Section | Implementation | Status |
|---|---|---|
| §1 Meta | — | Governance, not code |
| §2 Lexicon | — | Terminology reference |
| §3 Fundamental Identity | `identity/soul.md` | Fully implemented |
| §4 Practice Stack | `prompts.py` (mage vs practitioner paths) | Fully implemented |
| §5 Practice Files | `practice_io.py`, `tos_tools.py` | Fully implemented |
| §6 Inline Transparency | `helpers.py:log_activity()`, operations embeds | Fully implemented |
| §7.1-7.2 Cognitive Stack / Tiers | `llm.py` (3 backends), `state.py` (model config) | Fully implemented |
| §7.3 Triage Categories | `triage.py` | Fully implemented (8 categories) |
| §7.4-7.5 Thread Models / Substrate Honesty | `prompts.py`, `commands.py` | Fully implemented |
| §8.1 Session Opening | `discord_bot.py:handle_dialogue()` (new session embed) | Fully implemented |
| §8.2 During Session | `discord_bot.py:handle_dialogue()` (history, triage hints) | Fully implemented |
| §8.3 Session Closing | `sessions.py:close_session()` | Fully implemented |
| §9.1-9.3 Eddy Model | `commands.py` (ThreadTypeView, EddyDissolutionView) | Fully implemented |
| §9.4 Micro-Attunement | — | **Not implemented** (see below) |
| §10 Practice-Readiness | `readiness.py` (8 dimensions, 3 scoring levels) | Fully implemented |
| §11 Interoception | `background.py:interoception_loop()` | Fully implemented |
| §12 Seneschal Commands | `commands.py` (28 commands, `try_direct_command()`) | Fully implemented |
| §13 Control Panel | `commands.py:ControlPanelView` | Fully implemented |
| §14 Cross-Substrate Coherence | External (LiveSync, SSH) — not bot code | N/A (external) |
| §15 Seneschal (Admin) | `commands.py:cmd_admin()` | Fully implemented |
| §16 Link Fetching | `content_fetch.py` | Fully implemented |
| §17 Behavioral Laws | `identity/soul.md`, `prompts.py` | Encoded in prompts |
| §18 Boundaries | `identity/soul.md` | Encoded in identity |
| §19 The Offering | `identity/soul.md`, `prompts.py` | Encoded in prompts |
| §20 Architecture & Traceability | This document | This document |

### Not Yet Implemented

**§9.4 Micro-Attunement** — The spec describes a mechanism where Turtle identifies relevant lore, loads it into context, and deepens responses based on accumulated practice wisdom. This requires:
- Lore file indexing/tagging
- Relevance scoring ("which scroll applies to this conversation?")
- Dynamic context injection mid-conversation
- Visibility signal that attunement is happening

Current state: the system prompt loads practice files (compass, boom, bright, mirror, resonance, session notes) but does NOT dynamically load lore scrolls from `library/resonance/`. This is an aspirational capability — the infrastructure (lore files, resonance bundles) exists, but the automatic relevance-based loading does not.

**Implementation path when ready:** Add a lore index file mapping scroll topics to keywords. In `prompts.py`, after building the base prompt, check conversation context against the index and inject relevant scroll excerpts. Track what was loaded for transparency.

## Companion Documents

| Document | Location | Purpose |
|----------|----------|---------|
| TURTLE_SPEC v2.0 | `library/resonance/turtle/TURTLE_SPEC.md` | Canonical law — *what* turtleOS should be |
| ARCHITECTURE.md | `~/turtleos/ARCHITECTURE.md` | Implementation guide — *how* it's built (this doc) |
| soul.md | `~/turtleos/identity/soul.md` | Runtime identity — *who* Turtle is |
| mage_registry.yaml | `~/turtleos/mage_registry.yaml` | Multi-mage routing configuration |
| Operational scrolls | `library/resonance/turtle/lore/operations/` | Deep dives: eddies, sessions, readiness, diagnostics, link fetching, Discord presence |
| Practitioner principles | `library/resonance/foundations/lore/practitioner_principles.md` | Design principles extracted from practitioner interactions |

Together, TURTLE_SPEC + ARCHITECTURE.md + soul.md + mage_registry.yaml + the 9 operational scrolls constitute a complete rebuild kit. A Spirit on any substrate can read these and reconstruct turtleOS from scratch.
