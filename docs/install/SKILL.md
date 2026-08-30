# Install turtleOS (Agent Skill)

Use this skill when the practitioner wants to install turtleOS on local hardware with Discord + Ollama. Walk them through each step; execute shell commands when you have filesystem access; stop and ask when credentials or Discord UI steps are required.

**Canonical law:** `TURTLE_SPEC.md` §13  
**Target practitioner:** Tech-curious early adopter; comfortable with Discord; wants local open-weight models.

---

## Outcome

The house is a **private** river and a **community** river, Turtle in both. **Today this skill leaves them in the private river.** Community at install is the remaining half ([practice-channels.md](../design/practice-channels.md)). Do not tell them they already have two rooms.

A running bot where:

1. Practitioner has a **private Discord server** with a **river** channel (their private room)
2. **Ollama** serves a small River model and a capable Turtle model
3. **Practice root** exists with `character/`, `flows/`, `chronicle/`, `state/`
4. Dropping text in the river yields acts (ack + Materialize eddy button)
5. Pressing the button opens an eddy; Turtle responds in the thread

Cloud API keys are **not** required for the default path.

---

## Prerequisites Check

Confirm with the practitioner:

- [ ] macOS or Linux machine with enough RAM/VRAM for ~30B class model (or agreed smaller Turtle model)
- [ ] Python 3.11+
- [ ] Discord account
- [ ] Git installed
- [ ] Ollama installed ([ollama.ai](https://ollama.ai)) or willingness to install

---

## Step 1 — Clone

```bash
git clone https://github.com/malteristo/turtleos.git
cd turtleos
echo "cloned turtleos"
```

---

## Step 2 — Practice root

```bash
PRACTICE_ROOT="$HOME/workshops/$(whoami)"
mkdir -p "$PRACTICE_ROOT"
cp -r template/character template/flows template/chronicle template/state "$PRACTICE_ROOT/"
echo "practice root at $PRACTICE_ROOT"
```

Native install seeds `state/current.yaml` only — legacy portable files (`compass.md`, `boom.md`, etc.) are retired.

---

## Step 3 — Python environment

```bash
cd turtleos
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
echo "venv ready"
```

---

## Step 4 — Ollama models

Pull models appropriate to hardware. Example defaults (adjust per machine):

```bash
ollama pull qwen3.5:4b
ollama pull gemma3:27b
echo "models pulled"
```

Record chosen model names for `.env` / config. River: 4B–9B class. Turtle: ~30B class target.

Verify:

```bash
ollama list
```

---

## Step 5 — Discord application

Guide the practitioner through (cannot fully automate):

1. [Discord Developer Portal](https://discord.com/developers/applications) → New Application
2. Bot → Add Bot → copy **token**
3. Enable intents: **Message Content Intent**, **Server Members Intent**
4. OAuth2 → URL Generator → scopes: `bot` → permissions: **Administrator** on a private server they own. Narrower channel permissions are not enough to create rivers.
5. Invite bot to the practitioner's **private server**
6. Create a text channel named e.g. `river` — this is their private room

Collect:

- Bot token (→ `.env`)
- Practitioner's Discord ID (Developer Mode → copy ID)
- River channel ID (right-click channel → Copy Channel ID)

---

## Step 6 — Configure shell

```bash
cd turtleos
cp .env.template .env
cp mage_registry.example.yaml mage_registry.yaml
```

The bot reads `mage_registry.yaml` **in this clone**, not `~/turtleos/`. Edit the file you just copied.

Edit `.env` — at minimum set Discord bot token and model names per current shell expectations.

Edit `mage_registry.yaml`:

- Replace `YOUR_DISCORD_USER_ID`
- Replace `YOUR_DIALOGUE_CHANNEL_ID` with river channel id
- Set `practice_dir` and `runtime_dir` to `$PRACTICE_ROOT`
- Confirm channel `type: river`

**Do not commit** `.env` or `mage_registry.yaml`.

---

## Step 7 — Start shell

```bash
cd turtleos
source venv/bin/activate
python discord_bot.py
```

Bot should connect. Practitioner sends a test message in the river channel.

---

## Step 8 — Verify (acceptance)

| Check | Expected |
|-------|----------|
| River message | Acts only — no conversational prose from River |
| Eddy button | Materialize eddy affordance present |
| Button press | New thread; seed message; Turtle reply in thread |
| Chronicle | River records eddy open with thread link (when implemented) |

**Note:** Default install uses `attunement: native` — identity from `practice_root/character/`, not legacy `identity/soul.md` (Appendix A magic-attuned only).

---

## Troubleshooting

| Issue | Action |
|-------|--------|
| Bot offline | Check token, intents, invite URL |
| No response | Check channel id in `mage_registry.yaml` matches river channel |
| Ollama errors | `ollama serve` running; model names match config |
| Permission errors | Bot role can read/send in river channel; create threads |

---

## Optional — Cloud model opt-in

Only if the practitioner explicitly wants API models: add Anthropic (or other) key to `.env`. Not part of default narrative.

---

## Done

Confirm with the practitioner:

- Practice root path
- River channel name
- Models in use
- How to restart bot

Point to `TURTLE_SPEC.md`, `README.md`, and `docs/ux/faq.md` for the house and the dest.

---

## Optional — a shared room (second pass today)

First success is one private river. The destination is that **community** exists at install. Until that ships, a shared room on this server is a second pass.

A second adult needs their own Discord account and joins **this** server. That join is membership: they get a private river, and if a shared room already exists they are seated in it. Discord’s age floor where they live applies (16 in Germany / the EU). Do not use a guest or unclaimed session.

`!admin invite` is only if you want a claim room before they arrive:

```
!admin
!admin invite <name> <emoji> en --member @them
```

To create the shared room today:

```
!admin space create family --members @you @them --context family --policy members_only
```

`!admin rivers` lists rivers. `!admin doctor` checks the house. FAQ: `docs/ux/faq.md`.
