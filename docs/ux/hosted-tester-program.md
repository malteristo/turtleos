# Hosted tester program (draft)

**Status:** Draft — friends & family beta (2026-06-24)  
**Cohort language:** English only (product copy, onboarding, flows).  
**Strategy:** Learn **Layer 1 UX** (River + eddies + Turtle) without sovereign install friction.  
**Related:** [onboarding.md](onboarding.md) · [install-journey.md](install-journey.md) · TURTLE_SPEC §15 · [design-hosted-river.md](../chapters/design-hosted-river.md)

---

## Why hosted first

Sovereign install (Ollama, Discord apps, drivers, config) is a **parallel chapter**. Testers should experience **how turtleOS is meant to work** — including **River** in the parent channel — not wrestle substrate.

| They experience | They skip |
|-----------------|-----------|
| `#river` acts, standing **`new eddy`** bar | Clone repo, models, `.env` |
| Eddies, Turtle dialogue, link-read | GPU/driver tuning |
| Optional **flow library** (incl. **Feedback**) | Agent-assisted terminal |

---

## Operator checklist (you)

### Provision

1. Create **unclaimed-river** claim room (or assign hosted-river channel).  
2. Register **river key** with **`locale=en`** (default) → guest drops emoji → bind.  
3. Confirm **`hosted_river_onboarding`** embed pins once (see [onboarding.md](onboarding.md)).  
4. **Feedback** flow ships in `template/flows/` — appears in the library automatically (no copy step unless you add custom flows under `~/workshops/<guest>/flows/`).  
5. Optional: guest `resonance.md` (language, boundaries, “feedback goes to host only”).

### Invite message (send to guest)

> I set up a private **river** channel for you on Discord — personal AI that runs on my machine, but **your channel is yours**.
>
> **River** (main channel) doesn’t chat like ChatGPT — you’ll see buttons and short acts. That’s normal.  
> **Eddies** are threads: click **`new eddy`** at the bottom, send a message, **Turtle** replies there.
>
> Use it like any chat app — follow up, paste links, come back to threads later.
>
> **Optional:** inside an eddy, open the **flow library** and pick **Feedback** anytime you want to tell me what worked or what didn’t.
>
> No homework. Just talk when you want.

Use **`onboarding_en.md`** / **`template/flows/feedback.md`** as shipped — no localization work for this cohort.

### Language

| Layer | Current cohort |
|-------|----------------|
| **Product copy** | English — onboarding embed, flows, invite message |
| **Conversation** | Practitioners may switch languages in dialogue; Turtle follows (no special setup) |
| **Localized templates** | **`onboarding_de.md`** and claim-room DE strings remain in repo for a future pass — **not** used when provisioning testers now |

Do not provision hosted rivers with `locale=de` until a deliberate localization pass for non-English cohorts.

### What you watch

| Signal | Where |
|--------|--------|
| First J1 success | Guest eddy: `new eddy` → speak → Turtle reply |
| River confusion | “Why doesn’t it talk here?” → onboarding copy gap |
| Feedback submitted | Eddy thread + `~/workshops/<guest>/state/notes/feedback-*.md` on Mini |
| Your feel | Discord digests — not only files |

---

## Feedback flow (tester-facing)

**Invoke:** In any eddy → **flow library** → **Feedback** (works mid-conversation — lens load).

**They decide when** — no prompts from you to fill surveys.

**Flow collects:**

- Kind (praise / confusion / bug / idea)  
- What they were doing (River, eddy, link, etc.)  
- What worked / didn’t  
- Quote permission (optional)  
- **Thread context** from conversation (bootstrap excerpt — they shouldn’t re-narrate everything)

**Template:** `template/flows/feedback.md`

**Close:** Turtle summarizes → they say **done** → optional **`!checkpoint`** to persist files.

---

## Operator: reading feedback

1. **Discord** — read the Feedback eddy thread (primary human context).  
2. **Practice root** on Mini — `~/workshops/<guest>/state/notes/`:
   - `feedback-intake.md` — structured fields (when intake capture lands)  
   - `feedback-last.md` — checkpoint tail on `!checkpoint`  
3. **Do not** surface guest content in your own river or proposals without consent (`quote_ok` field).

---

## Acceptance (hosted beta)

| ID | Scenario | Pass |
|----|----------|------|
| H1 | Guest completes claim + reads onboarding | Understands River ≠ chatbot; eddies = talk |
| H2 | Guest J1 without your help | `new eddy` → Turtle reply |
| H3 | Guest submits Feedback unprompted | Lens load → structured summary in thread |
| H4 | You receive actionable note | Can name one UX fix from their report |

---

## Open slices (later)

| Slice | What |
|-------|------|
| **Feedback intake persist** | `write_flow_intake` on Feedback close / `!checkpoint` (today: thread + checkpoint tail) |
| **Operator digest** | Weekly `!admin` or script: list new feedback files across hosted guests |
| **Self-install track** | [install-journey.md](install-journey.md) when sovereign path is ready |
| **Localization** | Full pass when non-English speakers join the cohort (`onboarding_de.md`, claim embeds, flows) |

---

*Hosted testing validates product feel; install journey validates sovereignty. Sequence, don’t conflate.*
