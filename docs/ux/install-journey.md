# Install journey (draft for UX review)

**Status:** Draft — for Mage feel-review and notes (2026-06-24)  
**Persona:** Tech-curious early adopter, **no Magic** — comfortable with Discord and copy-paste; may use Claude Code or Cursor but is not a daily developer  
**Hardware example:** Mac with **32 GB RAM** (Standard tier)  
**Success definition:** [First success checklist](onboarding.md#first-success-checklist-install-verification) — J1 only; no flow required

**Related:** [onboarding.md](onboarding.md) · [docs/install/SKILL.md](../install/SKILL.md) · TURTLE_SPEC §13

---

## What we are designing

One coherent first-run story from “I heard about turtleOS” to “I just had a real conversation with Turtle in Discord.”

**Hybrid install (target architecture):**

| Layer | Who runs it | This journey shows |
|-------|-------------|-------------------|
| **CLI** `turtle install` | Deterministic script | Local setup, model tier, verify |
| **Browser checklist** | Human (cannot automate) | Discord apps, server, invites |
| **Agent skill** (optional) | AI assistant | Same steps; pauses at browser gates |
| **In-product welcome** | River bot on first connect | Layer 1 onboarding embed |

---

## Journey at a glance

```
[0] Expectations (2 min read)
      ↓
[1] Local bootstrap — turtle install (10–40 min, mostly model download)
      ↓
[2] Discord setup — browser checklist (15–25 min, human)
      ↓
[3] Connect — paste tokens, turtle install verify (5 min)
      ↓
[4] First conversation — new eddy → speak → Turtle replies (2 min)
      ↓
[5] Welcome embed — pinned in #river (automatic)
```

**Total time (first install):** ~45–90 minutes, dominated by Ollama model download and Discord portal clicks.

---

## [0] Before you start — expectations screen

*Surface: README intro, install landing, or first CLI banner*

### Headline

**Personal AI on Discord — on your machine.**

### Body (short)

You will:

1. Install **turtleOS** on your Mac (local models, your files).
2. Create a **private Discord server** with a channel called **river**.
3. Talk to **Turtle** in **eddies** (threads) — like opening a chat, not chatting in the main channel.

You will **not** need a cloud API key for the default path.

### What “good” looks like when you’re done

> Click **`new eddy`** at the bottom of the river → send a message → Turtle replies in the thread. That’s it.

### What you need ready

- [ ] Discord account  
- [ ] ~25 GB free disk (models + repo)  
- [ ] This Mac plugged in (first model download takes a while)  
- [ ] 45–90 minutes uninterrupted (or pause after step 1 and resume later)

### Open UX note

*Should this be a web page, terminal banner only, or PDF?*

---

## [1] Local bootstrap — `turtle install`

*Surface: Terminal. User may have an agent running these commands; copy below is what **they** should see.*

### Step 1.1 — Welcome

```
turtleOS install
────────────────
We'll set up local AI + your practice folder on this Mac.
Discord setup comes next (in the browser).

Continue? [Y/n]
```

### Step 1.2 — Hardware probe → model tier

```
Checking this Mac…
  RAM: 32 GB
  GPU: Apple Silicon (unified memory)

Recommended: Standard
  River (fast):  qwen3.5:4b   (~2.5 GB)
  Turtle (chat): gemma3:27b  (~16 GB)

This matches a daily ChatGPT-style loop on your hardware.

[1] Use recommended (Standard)
[2] Lighter models (less RAM, shorter replies)
[3] I'll choose manually (advanced)

Choice [1]:
```

**If they pick Lighter**, show one line why (“Fine for trying turtleOS; long eddies may feel thinner”) and different model names — no catalog wall.

### Step 1.3 — Practice root

```
Practice files will live at:
  ~/workshops/alex/

  character/   — Turtle's voice
  flows/       — optional guided programs (not required Day 1)
  state/       — your checkpoints when you use flows later
  chronicle/   — event log

Create practice root? [Y/n]
```

### Step 1.4 — Python + repo

*(Mostly silent progress; only show errors.)*

```
✓ Repository ready
✓ Python environment ready
```

### Step 1.5 — Ollama

```
Ollama is running.

Pulling models (this may take 20–40 minutes)…
  [████████░░░░] qwen3.5:4b
  [██░░░░░░░░░░] gemma3:27b

✓ Models ready
```

**Quick sanity check** (optional but high-trust UX):

```
Running a 5-word Turtle test…
✓ Turtle responded in 4.2s

Local AI is working. Next: Discord.
```

### Step 1.6 — Pause gate (browser handoff)

```
────────────────────────────────────────
Next: Discord (browser, ~15 minutes)

You'll create:
  • A private server
  • A #river channel
  • Two bot applications (River + Turtle)

Open the checklist:
  docs/install/discord-checklist.md
  (or: turtle install discord-guide)

When you have tokens and channel ID, run:
  turtle install connect
────────────────────────────────────────
```

**Open UX note:** *Single URL / `turtle install discord-guide` that opens checklist in browser vs inline terminal wizard?*

---

## [2] Discord setup — browser checklist

*Surface: Static checklist page (markdown or simple HTML). User keeps terminal open; works in browser tabs.*

### Checklist header

**Connect turtleOS to Discord**

You need **two bots** so the product feels right: **River** handles structure in the main channel; **Turtle** talks in threads. Both are yours; both run on your Mac.

Estimated time: 15–25 minutes.

---

### Part A — Your server (5 min)

1. **Discord → Add a Server → Create My Own → For me and my friends**
2. Name it something you'll recognize (e.g. `Alex turtleOS`)
3. Create a text channel named **`river`**
4. Delete or ignore extra channels if you want a clean surface — only `#river` matters for now

**You should see:** an empty `#river` channel that's yours.

---

### Part B — River bot (7 min)

1. [Discord Developer Portal](https://discord.com/developers/applications) → **New Application** → name: `River`
2. **Bot** → Add Bot → copy **token** (save as `RIVER_BOT_TOKEN` — you'll paste soon)
3. **Privileged Gateway Intents:** enable **Message Content Intent**, **Server Members Intent**
4. **OAuth2 → URL Generator:**
   - Scopes: `bot`
   - Bot permissions: Send Messages, Read Message History, Create Public Threads, Send Messages in Threads, Embed Links, Add Reactions, Manage Threads *(or Administrator on a private test server)*
5. Open the generated URL → invite **River** to your server

**You should see:** River appear in the member list (offline until you start turtleOS).

---

### Part C — Turtle bot (7 min)

Repeat Part B with a **second** application named **`Turtle`**.

- Same intents  
- Same invite flow  
- Copy token as `TURTLE_BOT_TOKEN` (stored in `.env` as `DISCORD_BOT_TOKEN` for the Turtle process)

**You should see:** Turtle and River both in the member list.

---

### Part D — IDs you need (3 min)

Enable **Developer Mode**: Discord Settings → Advanced → Developer Mode **On**.

| What | How | Label for paste |
|------|-----|-----------------|
| Your user ID | Right-click your name → Copy User ID | `DISCORD_USER_ID` |
| River channel ID | Right-click `#river` → Copy Channel ID | `RIVER_CHANNEL_ID` |

Keep these in a notes app until the next step.

---

### Checklist footer

When both bots are invited and you have both tokens + channel ID:

```bash
turtle install connect
```

**Open UX note:** *Could one bot suffice for “try in 20 min” with a migration path to split-bot? Product tension — see review questions below.*

---

## [3] Connect — `turtle install connect`

*Surface: Terminal prompts; no raw YAML editing for default path.*

### Step 3.1 — Paste secrets

```
turtle install connect
──────────────────────

Paste River bot token (input hidden):
Paste Turtle bot token (input hidden):
Paste your Discord user ID:
Paste #river channel ID:

Writing config to ~/turtleos/.env and mage_registry.yaml …
✓ Saved (not committed to git)
```

### Step 3.2 — Start services

```
Start turtleOS now? [Y/n]

Starting River…  ✓
Starting Turtle… ✓

Both bots should show online in Discord.
```

*(LaunchAgent install optional sub-step: “Start automatically when Mac is on? [Y/n]”)*

### Step 3.3 — Verify — `turtle install verify`

```
turtle install verify
─────────────────────

Ollama          ✓ models loaded
River bot       ✓ online in #river
Turtle bot      ✓ can reach Discord
Channel map     ✓ #river → your practice root
Standing bar    ✓ new eddy visible

Install complete. Do the first conversation check:

  1. Open #river in Discord
  2. Click  new eddy  at the bottom
  3. Send any message in the thread
  4. Wait for Turtle to reply

First success? [y/N]
```

If **N**, show one troubleshooting link block (token, intents, channel ID mismatch) — not a wiki.

---

## [4] First conversation — the product moment

*Surface: Discord. No install UI.*

### What the user sees (sequence)

| Order | What appears | User interpretation |
|-------|----------------|---------------------|
| 1 | Thread titled **`new eddy`** | “Empty chat room” |
| 2 | User types: *“Hey — testing my install.”* | Normal Discord |
| 3 | System line: **`river added turtle`** | “Something joined” — not a green embed |
| 4 | Thread may rename (e.g. `install test`) | Optional; fine if it stays odd |
| 5 | **Bottom bar** appears: flow library (compact) | “Optional extras — I can ignore this” |
| 6 | **Turtle reply** in thread | **Success** — personal AI works |

### What must NOT happen (negative UX)

- Turtle prose in `#river` parent channel  
- Orientation essay before user speaks in a new eddy  
- “Create a flow first” or Navigator pushed  
- Fetch button required before discussing a URL (that's later, in-eddy)

---

## [5] In-product welcome — pinned embed

*Surface: `#river`, posted once by River on first successful connect.*

### Embed title

**Welcome to turtleOS**

### Embed body (target copy — aligned with [onboarding.md](onboarding.md))

> You now have **personal AI on Discord** — running on **your Mac**, with **your** models.
>
> **The river** doesn't chat in paragraphs. Short acknowledgements and buttons are normal.
>
> **Eddies** are where you talk. At the bottom of this channel you'll see **`new eddy`** — click it, send a message, Turtle joins and replies. Open a chat, follow up, paste a link when you want to discuss something on the web. Threads stay in your sidebar — come back anytime.
>
> **Optional — flows:** Inside an eddy you can open the **flow library** for guided conversations. You don't need flows for regular use. Curious? Try **Navigator** once.
>
> No homework. Open an eddy and talk.

### Pin behavior

- Pin once; don't repost on every restart  
- Same module as hosted-river onboarding (`hosted_river_onboarding.py`), generalized for self-install

---

## Optional paths (same journey, branches)

### API model opt-in

Only after J1 success:

> Want faster or deeper replies sometimes? You can add an API key later. Local-first stays the default.

No key prompt during install.

### Agent-assisted install

User in Cursor/Claude Code:

> “Install turtleOS using the install skill.”

Agent runs `turtle install` → pauses at **Discord checklist** → user pastes tokens → agent runs `turtle install connect` + verify.

Skill text stays thin; CLI is source of truth.

### Resume after pause

```
turtle install status

  Practice root   ✓ ~/workshops/alex
  Models          ✓ Standard tier
  Discord config  ✗ not connected

Next: turtle install connect
```

---

## Failure & recovery (user-facing)

| Symptom | User message | One action |
|---------|--------------|------------|
| Bot offline in Discord | “River/Turtle shows offline” | `turtle install verify` → check tokens |
| No `new eddy` bar | “Nothing at bottom of #river” | Confirm River bot running; channel ID |
| Turtle never replies | “I'm alone in the thread” | Confirm Turtle bot running; check intents |
| Ollama error | “Model not found” | `turtle install` → re-pull tier |
| Wrong channel | “Bot works elsewhere” | Re-run `turtle install connect` with correct channel ID |

Tone: **one primary action**, not logs.

---

## Review questions (for your notes)

1. **Split-bot on day one** — Is two Developer Portal apps acceptable for early adopters, or do we need a simplified single-bot first-run with a later “upgrade to split-bot” chapter?

2. **CLI vs agent prominence** — README leads with agent skill today; should the journey lead with `turtle install` and mention agent as optional?

3. **Model tier copy** — Is “Standard / Lighter / manual” the right granularity, or too technical even with probes?

4. **Discord checklist format** — Markdown in repo, `turtle install discord-guide` (opens browser), or embedded terminal (harder to follow)?

5. **Welcome embed timing** — Pin on first verify success, or only after user's first successful J1 self-report?

6. **LaunchAgent default** — Opt-in “start on login” during connect, or separate `turtle install service` step?

7. **Naming** — Application names `River` / `Turtle` vs user-branded names (confusing in member list)?

8. **Hosted path** — Should this doc explicitly say “if someone hosts for you, skip sections 1–3 and use claim room”?

---

## Copy deck (quick reference)

| Moment | Key phrase |
|--------|------------|
| Product promise | Personal AI on Discord — on your machine |
| River behavior | Acts, not paragraphs |
| Daily loop | `new eddy` → speak → Turtle replies |
| Flows | Optional; try Navigator once if curious |
| Success | Thread in sidebar; come back anytime |
| Not required Day 1 | Flows, checkpoint, `!fetch`, API keys |

---

*Draft for Mage review. After notes: align SKILL.md, implement `turtle install` slices, add `discord-checklist.md` if checklist stays separate from this file.*
