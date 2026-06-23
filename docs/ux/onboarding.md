# First install and onboarding

**Status:** Target copy and structure (2026-06-20)  
**Audience:** Anyone installing turtleOS — not Magic practitioners, not flow authors  
**Related:** [journeys.md](journeys.md) · [flow-library-journeys.md](flow-library-journeys.md) · [eddy-entry.md](eddy-entry.md)

---

## Product layers (hold both)

turtleOS is **two things at once**, without forcing either:

| Layer | What it is | Who it's for |
|-------|------------|--------------|
| **Personal AI (default)** | Sovereign, local-first **ChatGPT-style** use on Discord — open an eddy, talk, paste links, daily LLM work | Everyone after install |
| **Guided flows (optional)** | Structured conversations — expert process encoded; **guided emergence** without prompt engineering | People who want more structure, or who are exploring what flows can do |

**Install succeeds when Layer 1 feels good.** Layer 2 is discoverable in the eddy; never required for daily use.

For operators who also live with **intentions** (clarity on what you want, plans, checkpoints): that depth is available on demand — Turtle attunes when you ask, not by nagging.

---

## What you get after install

1. A **Discord server** (yours) with a **river** channel  
2. **turtleOS** running on your machine — local models by default, API opt-in if you choose  
3. **Turtle** as dialogue partner in **eddies** (threads)  
4. **River** in the main channel — structural acts only, not a chatbot  
5. A **flow library** installed under your practice root — optional programs you load inside an eddy when you want them  

No cloud API key is required for the default path. Your hardware picks the best local models it can run during install.

---

## Onboarding embed (generic — target copy)

Use this shape for first-run river embed, install skill success message, and hosted-river welcome (locale variants in `template/practitioner/`). **Longer and generic** — flows are a short optional section at the end, not the headline.

---

### Welcome to turtleOS

You now have a **personal AI** on Discord — running on **your** machine, with **your** models.

**The river** is where you drop things. The river doesn't chat in paragraphs; it acknowledges and offers buttons. That's normal.

**Eddies** are where you actually talk. At the bottom of the river you'll see **`new eddy`** — click it to open a thread. Send a message. Turtle joins and replies. That's the whole daily loop.

It works like the familiar pattern: open a chat, start typing, follow up, paste a link when you need to discuss something on the web. Threads stay in your sidebar — come back anytime.

**A few things that help:**

- **One eddy, one conversation** — start a new eddy when the topic shifts  
- **Paste URLs in the eddy** — Turtle can read many pages and talk about them with you  
- **Your data stays local** — practice files and flow checkpoints live on your machine under your practice root  

**Optional — flows:** Inside an eddy you can open the **flow library** and load a guided conversation (structured programs for specific jobs — clarity, reflection, a recurring dynamic, and more). You don't need flows for regular use. If you're curious what a flow feels like, try **Navigator** once — it walks through finding one concrete next step toward something you care about.

No homework. No framework vocabulary. Open an eddy and talk.

---

## First success checklist (install verification)

| Step | Pass |
|------|------|
| 1 | Bot online; river channel receives a test message |
| 2 | Standing bar at bottom: **`new eddy`** |
| 3 | Click → thread opens → practitioner sends first message |
| 4 | `river added turtle` (system line) → Turtle replies |
| 5 | Thread appears in Discord sidebar — re-enter works |

**Not required for first success:** loading a flow, checkpoint, `!fetch`, intentions files, compass/boom.

---

## Operator vs hosted practitioner

| Surface | Tone |
|---------|------|
| **Self-install (Pop 2)** | Generic personal AI first; flows optional; sovereignty/local models mentioned briefly |
| **Hosted river (claim room)** | Same core loop; privacy boundary (your channel is yours); locale from `onboarding_de.md` / `onboarding_en.md` |
| **Magic-attuned operator** | Same generic onboarding for product; Magic overlay is not the install story |

---

## What onboarding must not do

- Lead with Navigator or any single flow as **the** product  
- Use **Turtle Practice** or internal jargon in user-facing copy  
- Imply flows, intentions, or checkpoint/release are required Day 1  
- Proactively push flow suggestions after install  
- Conflate river acts with Turtle dialogue (“talk to the river”)  

---

## Template files

| File | Use |
|------|-----|
| `template/practitioner/onboarding_en.md` | Hosted claim embed (EN) — keep aligned with this doc |
| `template/practitioner/onboarding_de.md` | Hosted claim embed (DE) |
| `docs/install/SKILL.md` | Agent-assisted install — first-success = J1, not flow shake |

---

*Generic onboarding is Layer 1. Flow journeys live in [flow-library-journeys.md](flow-library-journeys.md).*
