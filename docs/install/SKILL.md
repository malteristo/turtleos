# Install turtleOS (Agent Skill)

Use this skill when the user wants to install turtleOS on local hardware with Discord + Ollama. Walk the user through each step; execute shell commands when you have filesystem access; stop and ask when credentials or Discord UI steps are required.

**Canonical law:** `TURTLE_SPEC.md` §13  
**Target user:** Tech-curious early adopter; comfortable with Discord; wants local open-weight models.

---

## Outcome

A running bot where:

1. User has a **private Discord server** with a **river** channel
2. **Ollama** serves a small River model and a capable Turtle model
3. **Practice root** exists with `character/`, `flows/`, `chronicle/`, `state/`
4. Dropping text in the river yields acts (ack + Materialize eddy button)
5. Pressing the button opens an eddy; Turtle responds in the thread

Cloud API keys are **not** required for the default path.

---

## Prerequisites Check

Confirm with the user:

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

Guide the user through (cannot fully automate):

1. [Discord Developer Portal](https://discord.com/developers/applications) → New Application
2. Bot → Add Bot → copy **token**
3. Enable intents: **Message Content Intent**, **Server Members Intent**
4. OAuth2 → URL Generator → scopes: `bot` → permissions: Send Messages, Read Message History, Create Public Threads, Send Messages in Threads, Embed Links, Add Reactions (or Administrator for private server)
5. Invite bot to user's **private server**
6. Create a text channel named e.g. `river` — this is the practice surface

Collect:

- Bot token (→ `.env`)
- User's Discord user ID (Developer Mode → copy ID)
- River channel ID (right-click channel → Copy Channel ID)

---

## Step 6 — Configure shell

```bash
cd turtleos
cp .env.template .env
cp mage_registry.example.yaml mage_registry.yaml
```

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

Bot should connect. User sends a test message in the river channel.

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

Only if user explicitly wants API models: add Anthropic (or other) key to `.env`. Not part of default narrative.

---

## Done

Confirm with user:

- Practice root path
- River channel name
- Models in use
- How to restart bot

Point to `TURTLE_SPEC.md` and `README.md` for product law and architecture.
