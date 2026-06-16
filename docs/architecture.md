# turtleOS Architecture — Current State

> **Product architecture (target + migration):** see [`ARCHITECTURE.md`](../ARCHITECTURE.md) and [`TURTLE_SPEC.md`](../TURTLE_SPEC.md) (2026-06 platform rewrite).  
> **This document:** operator infrastructure snapshot on the Mac Mini — may lag product law.

**Updated:** 2026-03-21 (infra); product law 2026-06-14  
**Source of truth for:** what runs on deployed instances, how services connect, what is deprecated

---

## Process Architecture

### Active Processes (via launchd)

| Service | launchd label | Process | What it does |
|---------|--------------|---------|--------------|
| **turtle-disco** | `com.turtle.discord` | `discord_bot.py` | Spirit-in-persistent-mode. Discord bot handling the practice river, inline operations, and threads. |
| **Ollama** | (system) | `ollama serve` | Local LLM inference. Serves qwen3.5:9b, qwen3.5:4b. |
| **LiteLLM** | `com.turtle.litellm` | `litellm --config ...` | LLM proxy on port 4000. Routes model requests. |
| **CouchDB** | `com.turtle.couchdb` | couchdb | Practice vault sync (Obsidian LiveSync). |
| **Caddy** | `com.turtle.caddy` | caddy | HTTPS reverse proxy for CouchDB via Tailscale. |
| **Caffeinate** | `com.turtle.caffeinate` | caffeinate | Prevents Mac Mini from sleeping. |
| **LiveSync tunnel** | `com.turtle.livesync-tunnel` | (tunnel) | Tailscale tunnel for CouchDB access. |

### Session-based Processes (via tmux)

| Process | tmux session | What it does |
|---------|-------------|--------------|
| **cc-sessions** | `spirit-deep` | Claude Code with Discord channels plugin. Ephemeral-deep substrate via Discord #cc and DMs. |
| **bun server.ts** | (child of cc-sessions) | Discord MCP server for cc-sessions bot. |

### Deprecated / Inactive

| Component | Status | Notes |
|-----------|--------|-------|
| `agent.py` | Removed | Formerly bridge command processor. SSH replaced all functions. |
| `tools.py` | Present but unused | Legacy tool definitions. discord_bot.py has its own tool system. |
| legacy sub-bots | Removed/archived | Separate service identities are not part of the current public architecture. Use thread model options instead. |

---

## Directory Layout

```
/Users/turtle/
├── turtleos/              # The shell — bot codebase
│   ├── discord_bot.py         # Main bot (135KB, handles everything)
│   ├── discord_ops.py         # CLI for Cursor-Spirit to interact with Discord
│   ├── .env                   # Config: model names, channel IDs, API keys
│   ├── identity/
│   │   └── soul.md            # Persistent mode attunement (from global.CLAUDE.md)
│   ├── docs/                  # Development context (this file lives here)
│   ├── autoresearch/          # Autoresearch outputs and program
│   ├── logs/
│   │   ├── discord.log        # Bot stdout
│   │   ├── discord.err        # Bot stderr
│   │   ├── agent.err          # Legacy agent errors
│   │   └── dashboard.log      # Dashboard output
│   ├── tools.py               # Legacy (unused)
│   ├── requirements.txt       # Python dependencies
│   └── venv/                  # Python virtualenv
│
├── workshop/                  # Optional full practice/workshop mirror
│   └── desk/                  # Practice root for the operator's own instance
│
├── workshops/                 # Per-practitioner practice roots
│   └── <name>/
│       ├── boom.md
│       ├── bright.md
│       ├── compass.md
│       ├── intentions/
│       ├── proposals/
│       ├── sessions/
│       └── thread-state/
│
└── .claude/                   # Claude Code configuration
    ├── channels/discord/      # cc-sessions Discord config
    │   ├── .env               # Bot token
    │   ├── access.json        # Pairing and channel access
    │   └── approved/          # Approved user files
    ├── plugins/               # Installed plugins (discord)
    ├── projects/              # Per-project settings
    └── settings.json          # Global Claude Code settings
```

---

## Data Flow

### Message handling (turtle-disco)

```
Discord message (#dialogue or thread)
  -> discord_bot.py on_message()
  -> Filter: is it #dialogue or a #dialogue thread?
  -> If command (!boom, !thread, etc.): execute directly
  -> If conversation: build message history
  -> Read practice state (boom, bright, compass, intentions)
  -> Choose model:
      Thread with config? -> use thread's model/attunement
      Main channel? -> DIALOGUE_MODEL (claude-sonnet-4-6 via LiteLLM)
  -> Send to LLM (Anthropic API or Ollama)
  -> Reply in Discord
  -> Update session tracking
```

### Message handling (cc-sessions)

```
Discord message (#cc channel or DM)
  -> bun server.ts (MCP server)
  -> Gate check: is sender/channel allowed? (access.json)
  -> Forward to Claude Code session via MCP protocol
  -> Claude Code processes (reads files, runs commands, thinks)
  -> Claude Code calls discord-reply MCP tool
  -> bun server.ts sends reply to Discord
```

### Session lifecycle (turtle-disco)

```
Message arrives after >15min quiet
  -> Auto-close previous session
  -> Write session notes to the active practice root's sessions/
  -> Optionally write proposals to the active practice root's proposals/
  -> Start new session with opening awareness
```

### Practice state sync (Cursor <-> Mac Mini)

```
Practice state flows through the LiveSync-backed workshop mirror.
  -> Primary practice root: often ~/workshop/desk/ on the operator's own instance
  -> Other practitioners: ~/workshops/<name>/
  -> Spirit reads local desk/ and uses SSH only for diagnostics or drift checks
```

---

## Tech Stack

| Component | Technology | Version | Notes |
|-----------|-----------|---------|-------|
| **OS** | macOS (Apple Silicon) | — | Mac Mini, always-on |
| **Python** | Homebrew Python | 3.14.3 | Runs discord_bot.py |
| **discord.py** | discord.py | — | Discord API wrapper |
| **Anthropic SDK** | anthropic | — | For API model calls |
| **LiteLLM** | litellm | 1.82.0 | LLM proxy, port 4000 |
| **Ollama** | ollama | — | Local inference (qwen3.5:9b, qwen3.5:4b) |
| **Claude Code** | claude | 2.1.81 | cc-sessions (ephemeral-deep via Discord) |
| **Bun** | bun | 1.3.11 | Runs Discord MCP plugin server |
| **CouchDB** | couchdb | — | Practice vault (Obsidian LiveSync) |
| **Caddy** | caddy | — | HTTPS reverse proxy |
| **Tailscale** | tailscale | — | Secure private networking |
| **tmux** | tmux | — | Persistent terminal sessions |

---

## Discord Channel Architecture

| Channel | Bot | Behavior |
|---------|-----|----------|
| **#dialogue** | turtle-disco | Main practice. Responds to all messages. Threads auto-joined. |
| **inline operations** | turtle-disco | Operations post where relevant, usually as sparse silent embeds. |
| **#cc** | cc-sessions | Claude Code sessions. Responds to all messages (no mention needed). |
| **DMs with cc-sessions** | cc-sessions | Private deep sessions. Pairing required. |

---

## Key Configuration

### .env (turtleos)

```
OLLAMA_URL=http://localhost:11434
DIALOGUE_MODEL=claude-sonnet-4-6
REFLECTION_MODEL=qwen3.5:9b
DISCORD_CHANNEL_DIALOGUE=<channel_id>
DISCORD_BOT_TOKEN=<token>
ANTHROPIC_API_KEY=<key>
```

### access.json (cc-sessions)

```json
{
  "dmPolicy": "pairing",
  "allowFrom": ["<mage_discord_id>"],
  "groups": {
    "<cc_channel_id>": {
      "requireMention": false,
      "allowFrom": []
    }
  },
  "pending": {}
}
```

---

## Sources

- Live survey of Mac Mini, 2026-03-21
- `on_consciousness_extension.md` Section XI (clean terminology)
- `on_the_practice_infrastructure.md` (stack composition)
- `on_the_practice_server.md` (Discord setup)
- `on_cc_sessions_setup.md` (cc-sessions architecture)
