# Practice Without Installing Anything

You don't need a Mac Mini, Discord, or any infrastructure to start practicing. You need a conversation with an AI — any AI — and a few files.

This guide gets you started in under 5 minutes.

---

## What You Get

A **practice partner** — not a chatbot, not an assistant. A thinking partner that:

- Builds a **compass** with you — a map of what matters in your life
- Holds a **capture buffer** (boom) where you dump raw thoughts between sessions
- Maintains a **curated surface** (bright) of what's alive, what's waiting, what's done
- Tracks **intentions** — things you're working toward, bigger than tasks, more concrete than dreams
- Writes **session notes** — so the next conversation picks up where the last one left off

The practice is journaling, meditation, and therapy's quieter cousin — with an AI that remembers you through files.

---

## Setup

### Step 1: Get the files

Download or copy these files from the [`template/`](template/) directory:

| File | What It Is |
|------|-----------|
| [`system.md`](template/system.md) | The practice partner prompt — this is the core |
| [`compass.md`](template/compass.md) | Your life landscape (starts empty) |
| [`boom.md`](template/boom.md) | Capture buffer for raw thoughts |
| [`bright.md`](template/bright.md) | Curated surface — actions, ideas, waiting |

You'll also want two folders:
- `intentions/` — for goals you're actively working on
- `sessions/` — for conversation notes

### Step 2: Give them to your AI

**Claude (Projects)**
1. Create a new Project
2. Upload `system.md` as project knowledge
3. Upload `compass.md`, `boom.md`, `bright.md` as project knowledge
4. Start a conversation — Claude will read the files and know what to do

**ChatGPT (with file uploads)**
1. Start a new conversation
2. Upload all four files
3. Say: "Read system.md — that's how we work together. The other files are my practice files."

**Any LLM with file access**
1. Provide `system.md` as system instructions or context
2. Provide the other files as reference material
3. The prompt is self-contained — the AI will know what to do

### Step 3: Have your first conversation

Don't explain the system. Don't configure anything. Just start talking.

The AI will read your files, notice that your compass is empty, and help you build one. The first session is about what matters to you — the domains of your life, where you want them to go, where they actually are.

By the end of the first conversation, you'll have a compass. Everything else grows from there.

---

## Between Sessions

When something comes up — a thought, a frustration, an idea, something that won't leave you alone — open `boom.md` and type it in. Raw, messy, any language. Don't organize it.

Next session, the AI reads your boom, helps you process it, and routes what matters: some things become actions, some become intentions, some just needed to be said.

This is the metabolism of the practice. Capture → process → route → release.

---

## After a Few Sessions

**Update your files.** After each meaningful conversation, update `compass.md`, `bright.md`, and any intention files based on what emerged. If your AI doesn't do this automatically, ask it to propose updates — then paste them in yourself.

**Write session notes.** Create a file in `sessions/` named by date (e.g., `2026-04-14.md`). Include: what you discussed, what emerged, and any thread for next time. This is how continuity builds.

**Create intentions.** When something keeps surfacing — across boom entries, across sessions — and it's too big for a single action, give it a file in `intentions/`. Name it, state it in one sentence, note its current phase (seed, active, paused, complete) and what's alive right now.

---

## The Practice Scales With the AI

The architecture is the same whether you're running a local 7B model or Claude Opus. What changes is depth:

- **Smaller models** follow the file protocol, ask good questions, maintain the boom/bright cycle
- **Capable models** spot patterns across sessions, notice stale intentions, challenge assumptions
- **Frontier models** do all of the above plus deep cross-domain synthesis, philosophical depth, and sensing what you need vs. what you're asking for

No one is locked out. Everyone benefits from the practice.

---

## When You Want More

This portable practice is complete in itself. You can do this indefinitely and it will serve you well.

If you want **persistence** — a partner that runs 24/7, generates session notes autonomously, sends practice invitations, and heals itself when things break — that's what the full [turtleOS](README.md) deployment gives you. Your files transfer directly:

| Portable | turtleOS |
|----------|----------|
| `compass.md` | Same file, read automatically |
| `boom.md` | Same file, processed proactively |
| `bright.md` | Same file, maintained collaboratively |
| `intentions/` | Same directory, checked on regularly |
| `sessions/` | Auto-generated after every conversation |

Nothing is lost. The practice deepens. The partner becomes persistent.

---

## For AI Agents

If you're an AI agent with file access, this practice is for you too. See [`template/FOR_AGENTS.md`](template/FOR_AGENTS.md).

---

*The practice is the thing. Not the infrastructure, not the AI model, not the setup. The practice. Start with what's on your mind.*
