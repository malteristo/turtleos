# turtleOS

**Family friendly AI.** It runs on a machine you own, and it is built to be in a room with people who love each other.

turtleOS runs on a machine you own and lives in a Discord server you own. Everyone in the household is a **member** — the person who installed it included. It holds the things a family keeps losing: the date nobody wrote down, the thing that was never resolved, the plan that lived in one person's head. And it is built, first, to know when to stay out of the way.

Most assistants are designed for one person getting things done. This one is designed for several people who have to keep living with each other afterwards. That changes almost every decision in it.

**Care before operations.** The stance in full: [docs/design/family-care-operating-model.md](docs/design/family-care-operating-model.md)
**Canonical law:** [TURTLE_SPEC.md](TURTLE_SPEC.md)

---

## Why restraint is the feature

An assistant that is wrong about a task wastes a minute. An assistant that is wrong about a *moment* — that offers to organise your week while you are describing a hard night — teaches a family that the thing in the corner does not understand them, and they stop bringing it anything real.

So the interesting engineering here is mostly refusal:

- **It reads the register before it offers anything.** A structured "shall I turn this into a plan?" is welcome when you are sorting out logistics and unwelcome when you are not. That judgement is a model call, made fresh, and it **fails closed** — when the check cannot run, nothing is offered. The rule was added after measuring the alternative: across eight weeks of one real household, offers that misread the moment outnumbered the useful ones by a wide margin, and the take rate looked like disinterest when it was actually a register problem.
- **It writes carefully, because the record outlives the conversation.** Notes are the durable part. So: no clinical or characterological labels, anywhere, in any language. One person's account of another is recorded as *their account*, never as established fact. In a heavy moment the note gets **shorter and plainer, not deeper** — it records what was said and what was left open, and does not diagnose anyone.
- **It attributes.** In a shared room, notes name who said what and never merge two people into one voice. What the AI said stays the AI's, never retold as your realization.
- **It carries its own age.** The standing rule for anything the system remembers and brings forward: say how old it is. "In motion since March" is honest; the same thing asserted in the present tense, six weeks stale, is not. This one is a standard the project is still finishing bringing every surface into line with — the most recent correction landed the week this was written.
- **It is not a referee.** turtleOS witnesses; it does not adjudicate between members, and it is not built to. If you are looking for something to settle arguments, this is the wrong tool.

None of this is aspirational copy. Each line above corresponds to a rule in the prompt layer or a gate in the code, most of them added *after* the running system got it wrong and the failure was measured.

---

## How it works

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

Each member gets their own private river. A household can also have a **shared** river that several members are in at once — which is where the attribution and record rules above stop being theoretical.

**Local models by default** (via Ollama): a small model for intake and action selection, a larger one (~30B class) for conversation. Cloud APIs are opt-in, per instance.

**What "private" does and does not mean here.** Your practice root — every note, every date, everything remembered — lives on your machine, and with local models the inference does too: no conversation is sent to a model provider unless you deliberately configure one. But **Discord is the transport**, so the messages themselves pass through and are stored by Discord like any other server you run. That is a real limit, and it is the honest trade for the thing that makes this usable at all: a family will actually open an app they already have. If Discord's involvement is unacceptable for your household, this is not the tool for you yet.

**Relations, not roles.** Members are `household`, `kin`, or `guest`, and who can reach whom follows from that. A guest is the default; widening it is a deliberate act.

---

## What is live, and what is designed

Honest status, because a family adopting this deserves to know which is which.

| | |
|---|---|
| **Live** | Private and shared rivers · eddies with a persistent lifecycle bar · optional guided **flows** · **dates and reminders** captured from ordinary conversation, in English and German · working plans you can keep · per-conversation and daily notes · relations and reach · announcements to shared rivers |
| **Designed, not built** | **Topics** — member-made threads that stay alive until members resolve them · a read-only **family surface** (the "fridge") · a derived, zero-input **household barometer**, symmetric by construction · kin spaces |
| **Deliberately absent** | Engagement metrics · streaks · mood scoring · anything that ranks members against each other |

The measure this project holds itself to is not usage. It is whether the practical business of a household gets lighter, and whether the people in it have a better time with each other. Those are hard to measure, which is a reason to be careful about the claim, not a reason to substitute an easy metric for it.

---

## Members, not users

The people in a household are not a test population.

- **Even the administrator is a member** with additional rights, not a different species.
- **Non-participation is a valid answer.** A member who doesn't want a feature has given design input, not a problem to be solved.
- **Anything built *about* a member needs that member's voice**, not merely their data.

This is written down because it is easy to agree with and easy to violate the first time a feature would be more convenient without it.

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

**[docs/install/SKILL.md](docs/install/SKILL.md)** — clone → practice root → models → Discord bot → running river → (optional) household.

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

### A household

First success is one member, one river. A household is a second pass, on the same server:

1. Each adult who will practise needs their own Discord account. Discord’s age floor where you live applies — in Germany it is 16. Younger children are not members; a guest login is not a workaround.
2. In your river, `!admin` then `!admin invite <name> <emoji> --member @them` for each adult.
3. A shared room: `!admin space create family --members @you @them --context family --policy members_only`.

`!admin doctor` checks the house. Questions an administrator actually hits: [docs/ux/faq.md](docs/ux/faq.md).

Install law in full: [TURTLE_SPEC.md](TURTLE_SPEC.md) §13. Hosted rivers and shared rooms: §15.

---

## Practice root

**turtleOS is a practice root that's yours and readable, running on a shell you can verify.**

One per member. The practice root is the readable part you own; the repo is the shell that runs it. What must stay a file vs what may stay ephemeral is the readability contract in [TURTLE_SPEC.md](TURTLE_SPEC.md) §3.2 — its first test is persisting the context packet a turn used.

| Path | Purpose |
|------|---------|
| `character/` | Turtle's identity — soul, conduct |
| `flows/` | Optional guided conversations |
| `chronicle/` | Event log, offer ledger, record gaps |
| `state/` | Notes, artifacts, what is currently in motion |
| `story/` | Conversation and daily notes |

See [template/README.md](template/README.md).

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
