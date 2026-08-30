# turtleOS

**A place for practices** — each a channel with its own Turtle and River. It runs on a machine you own, in a Discord server you own.

The house has two rooms: a **private** channel that is only yours, and a **community** channel that is everyone’s. When someone joins the server, they get their private channel and they are already in community. When they leave, they are gone from turtleOS.

Craft, a relationship practice, a game — those are **practices you add**. Each sits on the same two primitives, solo or shared. The private channel and the community channel are not practices. They are the rooms the house comes with.

A practice is work you return to. It has a goal that outlives a chat, a place that holds the week, and a way of working that gets better because you did it again. turtleOS is that place, running: rooms you can walk into, a partner that talks in conversation, a record that stays on your hardware.

*What a new install creates today is still one private river. Community at install is the remaining half of the house. Join already opens a private river and seats the person in a shared room if one exists. See the table below.*

**Care before operations** — the stance this household runs: [docs/design/family-care-operating-model.md](docs/design/family-care-operating-model.md)  
**The house:** [docs/design/practice-channels.md](docs/design/practice-channels.md)  
**Canonical law:** [TURTLE_SPEC.md](TURTLE_SPEC.md)

---

## The rooms

```
River (a channel)                    Eddy (a thread)
─────────────────────                ─────────────────
Drop something               →       A focused conversation
Acts only: buttons, embeds   →       Turtle talks here, and only here
Never chat                   →       One eddy = one conversation
Standing "new eddy" bar      →       Stays in your sidebar; return anytime
```

| Actor | Where | Speaks? |
|-------|-------|---------|
| **River** | A channel | No — acts only: buttons, embeds, reactions, the chronicle |
| **Turtle** | Eddies (threads) | Yes — the dialogue partner |

Each member has a private river. Community is the shared room. Turtle answers in both. A practice you add is another channel of the same kind.

---

## How Turtle holds a room

These are rules in the prompt layer or gates in the code, most of them added after the running house got them wrong and the failure was measured.

- **It reads the register before it offers anything.** A structured “shall I turn this into a plan?” belongs in logistics and not in a hard night. That judgement is a model call, made fresh, and it **fails closed** — when the check cannot run, nothing is offered.
- **It writes carefully, because the record outlives the conversation.** No clinical or characterological labels, in any language. One person’s account of another is recorded as *their account*, never as established fact. In a heavy moment the note gets **shorter and plainer, not deeper**.
- **It attributes.** In a shared room, notes name who said what and never merge two people into one voice. What Turtle said stays Turtle’s.
- **It carries its own age.** Anything remembered and brought forward says how old it is. “In motion since March” is the form.
- **It witnesses.** It does not adjudicate between members.

---

## The record

**turtleOS is a practice root that’s yours and readable, running on a shell you can verify.**

One practice root per member. Markdown is the contract; the Python shell is the engine. Notes, dates, and what a turn knew live on your machine. Local models (Ollama) are the default: a small model for intake, a larger one (~30B class) for conversation. Cloud APIs are opt-in.

Discord is the door. The messages themselves pass through Discord, like any other server you run. The practice root does not.

| Path | Purpose |
|------|---------|
| `character/` | Turtle's identity — soul, conduct |
| `flows/` | Optional guided conversations |
| `chronicle/` | Event log, offer ledger, record gaps |
| `state/` | Notes, artifacts, what is currently in motion |
| `story/` | Conversation and daily notes |

See [template/README.md](template/README.md). What must stay a file: [TURTLE_SPEC.md](TURTLE_SPEC.md) §3.2.

**Roster.** A human on the server is a turtleOS member. One without the other is an error. Among members, `household` or `kin` may say who can reach whom. They do not decide whether someone is a member.

---

## Members

The people in a practice are not a test population.

- **Even the administrator is a member** with additional rights.
- **Non-participation is a valid answer.** A member who does not want a feature has given design input.
- **Anything built *about* a member needs that member's voice**, not merely their data.

---

## What is live, and what is designed

| | |
|---|---|
| **Live** | One private river at install · optional shared rivers · join opens a private river and seats the person in an existing shared room · leave archives the river and drops the seat · `!admin doctor` reports Discord ≠ registry · eddies with a persistent lifecycle bar · optional guided **flows** · **dates and reminders** from ordinary conversation, in English and German · working plans · per-conversation and daily notes · relations and reach · announcements to shared rivers |
| **Designed, not built** | Community created at install — [practice-channels.md](docs/design/practice-channels.md) · **Topics** that stay alive until members resolve them · a read-only household surface (the "fridge") · a derived, zero-input **household barometer** · kin spaces |
| **Deliberately absent** | Engagement metrics · streaks · mood scoring · anything that ranks members against each other |

The measure is whether the practical business of a household gets lighter, and whether the people in it have a better time with each other.

---

## Quick start

### Requirements

- Python 3.11+
- [Ollama](https://ollama.ai) for local models
- A Discord bot token ([guide](https://discord.com/developers/applications))
- A private Discord server you own

No cloud API key needed for the default path.

### Recommended: agent-assisted install

If you use Claude Code, Codex, or similar, hand your agent the install skill:

**[docs/install/SKILL.md](docs/install/SKILL.md)** — clone → practice root → models → Discord bot → running river. A shared room is still a second pass. The destination is private + community at install ([practice-channels.md](docs/design/practice-channels.md)).

### Manual install

```bash
git clone https://github.com/malteristo/turtleos.git
cd turtleos

# 1. Practice root — one per member
mkdir -p ~/workshops/$(whoami)
cp -r template/character template/flows template/chronicle template/state ~/workshops/$(whoami)/

# 2. Shell config
cp .env.template .env
cp mage_registry.example.yaml mage_registry.yaml
# Edit .env (Discord token) and mage_registry.yaml (your Discord id, river channel id, practice path)

# 3. Python deps
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 4. Local models — sizes are examples; evaluate against your hardware
ollama pull qwen3.5:4b     # intake / action selection
ollama pull gemma3:27b     # conversation

# 5. Start
python discord_bot.py
```

### First success

1. The bot is online in your river channel
2. A standing **`new eddy`** bar sits at the bottom
3. Click it, send a message, and Turtle replies in the thread
4. The thread stays in your sidebar — come back to it whenever

Then, optionally: open the flow library inside an eddy and try **Navigator**. See [docs/ux/onboarding.md](docs/ux/onboarding.md).

### A household (shared practice — second pass today)

First success is still one member, one private river. A shared room on the same server is a second pass. The destination is that community exists at install, and a relationship practice is a channel you add:

1. Each adult who will practise needs their own Discord account. Discord’s age floor where you live applies — in Germany it is 16. Younger children are not members; a guest login is not a workaround.
2. In your river, `!admin` then `!admin invite <name> <emoji> --member @them` for each adult.
3. A shared room: `!admin space create family --members @you @them --context family --policy members_only`.

`!admin doctor` checks the house. Questions an administrator actually hits: [docs/ux/faq.md](docs/ux/faq.md).

Install law in full: [TURTLE_SPEC.md](TURTLE_SPEC.md) §13. Hosted rivers and shared rooms: §15.

---

## Project structure

```
turtleos/
├── TURTLE_SPEC.md          # Canonical platform law
├── ARCHITECTURE.md         # Implementation guide
├── docs/design/            # Product stances and design chapters
├── docs/install/SKILL.md   # Agent-assisted install
├── discord_bot.py          # Shell entry point
├── template/               # Practice root starter files
└── runtime/                # Native runtime modules
```

The shell is mid-migration from an earlier single-practitioner stack toward TURTLE_SPEC platform law. Current alignment, row by row: [docs/traceability-matrix.md](docs/traceability-matrix.md). Development standards: [docs/development.md](docs/development.md).

---

## Related

- **[FAQ](docs/ux/faq.md)** — household, Discord accounts, children, data
- **[Onboarding](docs/ux/onboarding.md)** — first success, then a household
- **[Magic](https://github.com/malteristo/magic)** — a practice framework that can author flows; not required to install
- **[About the author](https://github.com/malteristo/me)**

## License

MIT — see [LICENSE](LICENSE).
