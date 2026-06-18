# turtleOS

**Local open-weight AI, made accessible.**

turtleOS turns capable local hardware into a personal AI practice space on Discord: a **river** that receives what you drop and responds through actions (never conversation), and **eddies** where **Turtle** thinks aloud and talks with you. Prompt programs — **Turtle Practice** flows — run on the platform; you can author and share your own.

turtleOS is a **practice core plus a reference shell**. The practice core is portable: character, flows, chronicle, and state files. The shell is the Python runtime that connects Discord, local models, and your practice root.

**Canonical law:** [TURTLE_SPEC.md](TURTLE_SPEC.md)  
**Applied UX (dogfood / review):** [docs/ux/README.md](docs/ux/README.md)

---

## How It Works

```
River (main channel)                Eddy (thread)
─────────────────────               ─────────────────
Drop text                    →      Focused conversation
River understands            →      Turtle dialogue + think-aloud
Acts only (buttons, emoji)   →      No chat in the river
Always: new eddy bar (bottom)  →      One eddy = one chat
Chronicle with thread links  →      Persist until you remove
```

| Actor | Where | Speaks? |
|-------|--------|---------|
| **River** | Main Discord channel | No — acts only (buttons, embeds, reactions, chronicle) |
| **Turtle** | Eddies (threads) only | Yes — dialogue partner |

**Two local models** (Ollama): a small **River** model for intake and action selection; a capable **Turtle** model (~30B class) for eddy conversation. Cloud APIs are opt-in for power users.

---

## Three Layers

1. **Practice core** — `character/`, `flows/`, `chronicle/`, `state/` in your practice root
2. **Reference shell** — this repo (`discord_bot.py` and supporting modules)
3. **Your instance** — models, Discord server, `.env`, `mage_registry.yaml`

---

## Quick Start

### Requirements

- Python 3.11+ (3.14 tested on deployed instances)
- [Ollama](https://ollama.ai) for local models
- A Discord bot token ([guide](https://discord.com/developers/applications))
- A private Discord server (you own it)

No cloud API key required for the default path.

### Recommended: agent-assisted install

If you use Claude Code, Codex, or similar, hand your agent the install skill:

**[docs/install/SKILL.md](docs/install/SKILL.md)**

The skill walks through clone → practice root → Ollama models → Discord bot → running river.

### Manual install

```bash
git clone https://github.com/malteristo/turtleos.git
cd turtleos

# 1. Practice root
mkdir -p ~/workshops/$(whoami)
cp -r template/character template/flows template/chronicle template/state ~/workshops/$(whoami)/
# Or copy full template/ if you want optional legacy portable files too

# 2. Shell config
cp .env.template .env
cp mage_registry.example.yaml mage_registry.yaml
# Edit .env (Discord token) and mage_registry.yaml (your user id, river channel id, practice path)

# 3. Python deps
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Local models (example — pin your instance config)
ollama pull qwen3.5:4b      # River model class
ollama pull gemma3:27b      # Turtle model class (evaluate on your hardware)

# 5. Start
python discord_bot.py
```

### First success

1. Message appears in your **river** channel
2. River responds with acts (ack + **Materialize eddy** button)
3. Press button → eddy opens → Turtle responds in the thread
4. Chronicle line in river includes a link back to the eddy

See [TURTLE_SPEC.md](TURTLE_SPEC.md) §13 for the full install law.

---

## Practice Root (Vanilla)

| Path | Purpose |
|------|---------|
| `character/` | Turtle identity — soul, conduct (authored after spec) |
| `flows/` | Turtle Practice programs (Shelter, Navigator, …) |
| `chronicle/` | Deep event log (`deep.jsonl`) |
| `state/notes/` | Flow outcomes and practice artifacts |

Compass, boom, bright, and intentions are **not** required at install — flows load them via front matter when needed.

See [template/README.md](template/README.md).

---

## Portable Practice (Paused)

A zero-install markdown practice path (`PRACTICE.md`) is **paused** while practice-state design settles. **Install is the primary onboarding story** for vanilla v1.

---

## Project Structure

```
turtleos/
├── TURTLE_SPEC.md          # Canonical platform law
├── ARCHITECTURE.md         # Implementation guide (+ migration status)
├── docs/install/SKILL.md   # Agent-assisted install
├── discord_bot.py          # Shell entry point
├── template/               # Practice root starter files
├── identity/               # Runtime attunement (instance-specific)
└── runtime/                # Native runtime modules (evolving)
```

The shell is mid-migration from a legacy magic-attuned stack (proprioception, cloud-default dialogue, river conversation) toward [TURTLE_SPEC](TURTLE_SPEC.md) platform law. See ARCHITECTURE.md **Migration Status**.

---

## Multi-Practitioner

Optional: multiple practitioners on one node, each with isolated practice root and river channel. Configure in `mage_registry.example.yaml` → `mage_registry.yaml`.

---

## Status

**Reference shell:** production on operator instances; **platform rewrite** in progress (2026-06).

| Layer | Status |
|-------|--------|
| TURTLE_SPEC (platform law) | Active — 2026-06-14 |
| Docs + template ripple | Active |
| Shell migration (River acts, eddy-only Turtle) | Planned |

Development standards: [docs/development.md](docs/development.md)

---

## Related

- **[Magic](https://github.com/malteristo/magic)** — optional practice framework; can author flows for turtleOS
- **[About the author](https://github.com/malteristo/me)**

## License

MIT — see [LICENSE](LICENSE).
