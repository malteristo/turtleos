# turtleOS

**Sovereign practice infrastructure for human-AI partnership.**

turtleOS turns any computer into a personal cognitive infrastructure node — a persistent AI practice partner that lives on hardware you own. Not a chatbot. Not a task assistant. A thinking partner that knows you and gets better at knowing you over time.

turtleOS is a **markdown practice core plus a reference shell**. The practice core is portable meaning: prompts, files, folders, and habits. The reference shell is the Python runtime that makes the practice ambient, conversational, and self-maintaining on owned hardware.

> **Don't want to install anything?** You can start practicing right now with any AI you already use.
> **[Read the Portable Practice Guide →](PRACTICE.md)**

## How to Read This Repo

turtleOS has three layers:

1. **Practice core** — markdown files and prompts that define the practice.
2. **Reference shell** — Python services that make the practice persistent on owned hardware.
3. **Your instance** — local configuration, model choices, Discord channels, and private practice state.

The core is the product's soul. The shell is the current open-source body. Your instance is yours. Setup starts by creating a practice root, then installing the shell that serves it.

## What It Does

You talk to your practice partner on Discord. It reads your practice files, notices patterns, asks questions, and pushes back when something doesn't add up. Between sessions, you dump raw thoughts into a capture buffer. Next session, the partner reads them, helps you process, and routes what matters to the right place.

Over time, the files accumulate. The partner knows you better. You get clearer about what you want and where your energy should go.

**The practice layer is what makes this different** from a chat interface or an agent framework:

- **Compass** — a map of what matters in your life (domains, directions, seeds)
- **Boom/Bright** — a cognitive buffer (capture anything) and curated surface (what's alive)
- **Intentions** — active goals with dependency topology
- **Sessions** — accumulated relational memory, auto-generated after each conversation
- **Proposals** — autonomous suggestions from the AI, generated during reflection

The closest historical analog is not another AI project — it is the practice of journaling, meditation, or therapy. turtleOS is infrastructure for an ongoing reflective practice that uses AI as the mirror.

## Architecture

```
Discord message
    │
    ├─ triage (0.8B local model) ─── classify depth: greeting/casual/practice/deep
    │
    ├─ proprioceptor (9B local) ──── scan practice state in parallel
    │
    ├─ conversation (cloud API) ──── deep dialogue with full practice context
    │
    └─ session reflection (27B local) ── after 15min silence:
        ├─ write session note
        ├─ generate proposals (if patterns noticed)
        └─ update practice state (compass, boom, mirror)
```

**Three-tier local LLM pipeline** (via Ollama):
- **Triage** (0.8B) — sub-second message classification. Runs on every message.
- **Proprioceptor** (9B) — context preparation, parallel with triage.
- **Reflection** (27B) — session notes, proposals, health assessment. Runs autonomously.

Cloud API (Anthropic Claude) handles deep conversation. The explicit design: cloud dependency shrinks as local models improve.

**34 Python files, approximately 14,000 lines of Python code.** See [ARCHITECTURE.md](ARCHITECTURE.md) for the full module map, data flow, and design decisions.

## Quick Start

### Requirements
- Python 3.11+ recommended; currently tested on the deployed Python 3.14 runtime
- [Ollama](https://ollama.ai) (for local models)
- A Discord bot token ([guide](https://discord.com/developers/applications))
- An Anthropic API key (for conversation model)

### Setup

```bash
git clone https://github.com/malteristo/turtleos.git
cd turtleos

# 1. Create your practice root: the files that belong to you
mkdir -p ~/workshops/$(whoami)
cp -r template/* ~/workshops/$(whoami)/

# 2. Configure the reference shell that will serve that practice
cp .env.template .env
cp mage_registry.example.yaml mage_registry.yaml
# Edit .env and mage_registry.yaml with your API keys, Discord token, channel IDs, and practice path

# 3. Install runtime dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Install local model components
ollama pull qwen3.5:0.8b
ollama pull qwen3.5:9b
ollama pull qwen3.5:27b

# 5. Start the shell
python discord_bot.py
```

### First Session

Once the bot is running and connected to your Discord server:
1. Send a message in the configured dialogue channel
2. The first session builds your **compass** — a map of what matters in your life
3. Confirm a session note can be written and your practice files can be read back
4. Everything else grows from there

The first success metric is not "bot online." It is first meaningful practice interaction plus continuity: your practice root was read, the conversation was situated, and the next session has something real to inherit.

## Practice Template

The `template/` directory contains the starter files for a new practitioner:

| File | Purpose |
|------|---------|
| `system.md` | Practice partner instructions (the "give this to any AI" file) |
| `compass.md` | Life landscape — empty, first session creates this |
| `boom.md` | Capture buffer — dump raw thoughts here any time |
| `bright.md` | Curated mind surface — actions, ideas, waiting |
| `intentions/` | Active goals and projects |
| `sessions/` | Conversation notes (auto-generated) |

## Multi-Practitioner Support

turtleOS supports multiple practitioners on one node. Each practitioner gets:
- Their own Discord channel (private)
- Their own practice directory (`~/workshops/<name>/`)
- Their own practice context (compass, boom, sessions, etc.)

Practitioners are registered in `mage_registry.yaml`, created locally from `mage_registry.example.yaml`. The real registry contains Discord IDs, channel IDs, and local paths, so it stays untracked. The system routes messages to the correct practice directory automatically.

## Project Structure

```
turtleos/
├── TURTLE_SPEC.md      # Canonical specification (23 sections)
├── ARCHITECTURE.md     # Implementation guide — module map, data flow, design decisions
├── identity/soul.md    # AI identity / system prompt
├── discord_bot.py      # Entry point
├── triage.py           # Message classification (local 0.8B model)
├── proprioceptor.py    # Practice state scanning (local 9B model)
├── prompts.py          # System prompt construction
├── llm.py              # LLM backend abstraction (Anthropic, Gemini, Ollama)
├── commands.py         # 28 Discord commands
├── sessions.py         # Session lifecycle + reflection (local 27B model)
├── tos_tools.py        # 9 practice file tools exposed to LLMs
├── mage.py             # Multi-practitioner routing
├── practice_io.py      # Practice file I/O
├── readiness.py        # 8-dimension practice health assessment
├── background.py       # Autonomous background tasks
├── ...                 # Additional modules (see ARCHITECTURE.md)
├── template/           # Practice starter files for new practitioners
└── identity/           # Identity files and attunement history
```

## Status

**Production.** Running 24/7 on a Mac Mini M4 Pro since January 2026. Serving multiple practitioners daily. 50+ autonomously generated session notes, 26+ self-generated proposals, 35+ active conversation threads.

The specification ([TURTLE_SPEC.md](TURTLE_SPEC.md)) governs the system. The architecture document ([ARCHITECTURE.md](ARCHITECTURE.md)) traces every spec section to its implementation.

## Related

- **[Magic](https://github.com/malteristo/magic)** — the practice framework that turtleOS implements. Theory, lore, and practice design.
- **[About the author](https://github.com/malteristo/me)** — public identity and research background.

## License

MIT — see [LICENSE](LICENSE).
