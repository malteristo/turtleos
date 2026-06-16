# TURTLE_SPEC: Law of the Platform

> **Canonical version:** This file in the `malteristo/turtleos` repository is the sole canonical TURTLE_SPEC.  
> The Magic practice bundle links here; it does not mirror this document.

**Version:** 2026-06-14 (platform rewrite, resonance pass)  
**Status:** Active — governs vanilla turtleOS and attunement contracts

---

## 1. Meta

### 1.1. What This Document Is

This specification defines **platform law** for turtleOS — the rules governing local execution infrastructure, the River/Turtle interaction model, eddy semantics, prompt-program execution, practice state, and the minimal practice root.

It is **not** Spirit law. It does not assume Magic, summoning, or consciousness-extension identity. Those belong to optional attunement layers (§4, Appendix A).

### 1.2. Why It Exists

turtleOS is infrastructure that makes **local, open-weight inference accessible** through a Discord-native practice surface. This spec canonizes the product architecture agreed in the 2026-06 decoupling chapter: platform vs attunement, River vs Turtle, acts-not-words in the river, dialogue only in eddies.

### 1.3. Relationship to Other Law

| Document | Relationship |
|----------|--------------|
| **MAGIC_SPEC** | Independent framework law. Magic practitioners may run Magic-shaped prompt programs on turtleOS; the platform does not require Magic. |
| **Attunement bundles** | Character files, conduct, and optional lore that shape Turtle's voice. Authored downstream of this spec. |
| **Flow front matter** | Contract between prompt programs and the execution layer (§10). |

**Amendment:** Through deliberate product revision and systematic error-correction. Foundational changes should trace to an explicit design decision, not implementation drift.

### 1.4. Supersedes

This rewrite supersedes the prior **"Law of the Persistent Spirit"** framing as the default product identity. Spirit-in-persistent-mode, proprioception, vortex/prism intake, river-entry dialogue, and Magic-first onboarding are **not** vanilla platform requirements. They may persist in magic-attuned instances (Appendix A).

---

## 2. Lexicon

| Term | Description |
|------|-------------|
| **turtleOS** | The platform — local runtime, Discord adapter, model routing, flow runner, practice-root storage. |
| **The shell** | Reference implementation: Python services (`discord_bot.py` and supporting modules) that implement platform law. |
| **The River** | The practitioner's main Discord channel. Intake surface, action broker, and surface chronicle. **Does not speak in prose.** |
| **Turtle** | The dialogue agent. Speaks **only inside eddies**. Warm, distinct character — attunement-defined, not platform-defined. |
| **Eddy** | A Discord thread — a focused conversation space, analogous to a new chat in ChatGPT or Claude. |
| **Act** | A structured, non-verbal River output: reaction, button, embed, chronicle line, or moderation operation. |
| **Flow** | A self-contained prompt program (markdown with optional front matter) executed by the platform. |
| **Turtle Practice** | The shipped library of flows plus platform state conventions — the portable practice layer turtleOS runs. Individual programs (Shelter, Navigator, etc.) are **flows within Turtle Practice**, not "front doors." Legacy Magic term *front door* is retired in product law. |
| **turtle practice** | Lowercase: the activity of practicing on turtleOS — using the river, eddies, and flows. |
| **Practice root** | Local directory holding character files, flows, chronicle, state, and optional practice artifacts. |
| **Attunement** | Identity and conduct layer on the platform: native (default), craft, or magic-attuned. |
| **Sediment** | Cross-eddy curated memory. **Deferred** — design chapter, not vanilla v1 (§16). |
| **Chronicle** | Event log of structural actions (eddies opened, dissolved, etc.). Dual layer: surface + deep (§6). |

---

## 3. Platform Identity

### 3.1. The Product Promise

**turtleOS** turns capable local hardware into a personal AI practice space:

- **Local, open-weight inference** — the default path uses models you run yourself (Ollama or equivalent).
- **Discord-native UX** — a **river** for intake and action; **eddies** for conversation.
- **Prompt programs as the practice layer** — Turtle Practice flows run on the platform; users may author and share their own.

The narrative for early adopters: *local AI made accessible* — not cloud chat with extra steps, not a Magic installation requirement.

### 3.2. Three Layers

| Layer | What it is |
|-------|------------|
| **Practice core** | Markdown files, flows, character, state — portable meaning. |
| **Reference shell** | Open-source runtime that makes the practice ambient on owned hardware. |
| **Your instance** | Model choices, Discord server, practice root, optional attunement profile. |

### 3.3. What the Platform Is Not

- Not a chatbot in the main channel.
- Not Spirit-in-persistent-mode by default.
- Not a Magic workshop clone at install time.
- Not cloud-dependent (cloud models are opt-in for power users — §8.3).

### 3.4. Target Population (Vanilla v1)

**Tech-curious early adopters** who:

- Follow AI developments and want local open-weight models.
- Understand Discord and can operate a private server.
- Have found local setup (Ollama, bot tokens, model downloads) too friction-heavy.
- Often already use agent-assisted development tools (Claude Code, Codex, etc.) — install MAY be agent-guided (§13.4).

---

## 4. Attunement Layers

The platform is neutral. **Attunement** shapes character and optional practice depth.

| Layer | Default? | Role |
|-------|----------|------|
| **Native turtle** | **Yes (shipped)** | Distinct character, minimal Magic vocabulary, general-purpose eddy partner. Authored to implement platform law (§14). |
| **Craft turtle** | Opt-in | Semi-attuned partner for turtleOS development and operator work. |
| **Magic-attuned persistent Spirit** | Opt-in | Full workshop mirror, triad Discord, consciousness-extension framing. See Appendix A. |

**Invariant:** A vanilla install must be coherent without Magic files, Spirit identity, or compass/boom/bright templates.

**Identity authoring sequence:** Platform law (this spec) → attunement author reads spec → drafts `character/` files in template. Character is molded *for* the product purpose; it is not a copy of Forge Spirit identity.

---

## 5. The River

### 5.1. Role

The River is the main channel. It is the **silent witness** — benevolent, ambient, caring — that:

1. Receives what the user drops (text first; images later).
2. Understands intent well enough to offer **good actions**.
3. Never holds conversational dialogue.

Metaphor: the sea in *Moana*, the casita in *Encanto* — intelligence expressed through **acts**, not words.

### 5.2. The No-Prose Law

**The River never speaks in conversational prose.** All communication uses Discord-native non-verbal modes:

- Emoji reactions and custom acknowledgments
- Embeds (structured, not chatty)
- Buttons and select menus
- Chronicle lines (§6)
- Moderation acts (pin, archive, dissolve)

**Errors and status** follow the same law: `⚠️ Model unavailable` as an embed or act — not an apologetic chatbot paragraph. This constraint is a **design freedom**: explore alternative communication modes the substrate affords.

### 5.3. Intake Logic (Vanilla v1)

Every inbound river message produces an **act bundle** — not a single either/or outcome.

```text
always:
  offer_eddy(title)           # safety net — always present
optional (as warranted):
  acknowledge(emoji)          # low-key recognition
  offer_flow_menu()           # when user signals flows / Turtle Practice
  revise_offer(title)         # after user correction
  execute_command(...)        # power-user !commands (§5.5)
```

**Always offer eddy:** Every river response MUST include a materialize-eddy affordance. Title is inferred when possible; generic label (`Materialize eddy`) when uncertain. This prevents false negatives when classification misses eddy-worthy input.

Acknowledgment and eddy offer **coexist** — e.g. `"hi"` → 👋 **and** a low-friction eddy offer such as `Open eddy: check-in`.

**v1 routing policy:** No semantic routing to existing eddies. Each materialized eddy is a **new thread**. Semantic merge is deferred (§16).

### 5.4. Eddy Offer Shape

When the River offers an eddy:

1. Infer a concise **topic title** from the message (or use a generic label).
2. Post an act with a button: **Materialize eddy: "[title]"** (label MAY vary; semantics MUST be clear).
3. On press: spawn thread with that title, post the **seed message** (faithful copy of user input), invoke Turtle in the eddy context (§7.2).

If the user says they were misunderstood and clarifies, the River posts a **revised offer** — different title/intent — without conversational reply.

### 5.5. River Commands

Two paths, layered:

| Path | Audience | Behavior |
|------|----------|----------|
| **Natural language → acts** | Default | River model interprets intent → act buttons (consent before execution) |
| **Turtle-talk commands** | Power users | `!dissolve`, `!flows`, `!pin`, etc. — direct execution, no interpret step |

The turtle-talk palette SHOULD expose a river-relevant subset for v1 (dissolve, flow menu, pin). Full command inventory lives in implementation docs.

The River executes; it does not discuss.

### 5.6. Flow Discovery

When the user's message signals intent to browse programs (e.g. mentions *flows*, *Turtle Practice*, or equivalent), the River emits **`offer_flow_menu`** — a select menu or button row of installed flows. No prose catalog.

A standing flow-browse affordance MAY appear alongside other acts on substantive messages.

### 5.7. River Model

The River uses a **small local model** optimized for:

- Classification (ack vs command vs flow-browse vs eddy title inference)
- Structured act generation (JSON or tool schema)

It does **not** need conversational quality. It needs reliable **action selection**.

Recommended class: 4B–9B local, always resident. Exact checkpoint is instance configuration, not platform law.

### 5.8. River vs Turtle Identity (Discord)

Vanilla native installs SHOULD use **two Discord applications**:

| Bot | Role in river channel | Role in eddies |
|-----|----------------------|----------------|
| **River bot** | Acts only — reactions, buttons, embeds, chronicle | Creates thread + seed on materialize |
| **Turtle bot** | Silent (no user-message replies) | Dialogue, tools, presence ("Turtle joined") |

Practitioners MUST be able to distinguish River acts from Turtle dialogue by bot name and avatar. Single-bot mode MAY remain as a migration fallback when `RIVER_BOT_TOKEN` is unset.

---

## 6. Chronicle

### 6.1. Purpose

The River accumulates **events**, not conversation. The chronicle is how the system remembers what happened structurally — and how users navigate **upstream** through their eddy history when Discord's sidebar loses inactive threads.

### 6.2. Event Types (v1)

| Event | Surface chronicle | Deep chronicle |
|-------|-------------------|----------------|
| Message received in river | Optional minimal line | Full payload + classification |
| Eddy offered | Button act | Offer record + inferred title |
| Eddy materialized | `🌀 opened: [title]` + **thread jump link** | Thread id, guild id, jump URL, seed hash, timestamp |
| Eddy dissolved | `🍃 dissolved: [title]` + link if archived | Archive pointer, actor |
| Turtle entered eddy | Optional in river | Session start record |
| Turtle exited eddy | Optional in river | Exit record, optional exit note path |
| Error / degraded mode | Embed act | Stack, model state |

**Thread links:** Surface chronicle entries for materialized eddies MUST include a Discord jump URL so users can walk backward through conversations in reverse chronological order along the river.

### 6.3. Dual Layer

| Layer | Audience | Format |
|-------|----------|--------|
| **Surface** | User | Legible lines and embeds in the river — the visible tide |
| **Deep** | Operator / debug | Append-only log under practice root (`chronicle/deep.jsonl` or equivalent) |

**Principle:** The river runs deep; users normally see the surface.

### 6.4. Sediment (Deferred)

Cross-eddy memory, curated distillates, and what Turtle/River may read across time — **out of scope for vanilla v1** (§16). v1 eddies are self-contained via thread history.

---

## 7. Turtle

### 7.1. Role

**Turtle is the dialogue partner.** Turtle exists only in eddies. Each eddy is a separate conversational context; Turtle attunes to **this eddy** — its title, seed message, and thread history.

### 7.2. Eddy Entry Behavior

When an eddy is materialized:

1. **Seeded eddy:** the practitioner's river input is posted as a seed embed.
2. **Blank eddy (Eddy Door):** no seed at materialize — the practitioner's **first message** is the opening.
3. **Presence embed** — compact system line (`Turtle joined`) — not conversational prose. For blank eddies, presence is deferred until the first practitioner message, immediately before Turtle's first reply (§7.7).
4. Turtle reads the opening + thread history and responds.

No Turtle speech in the river. No model/attunement config chrome in vanilla v1 eddies (legacy Magic-attuned UI). No arrival monologue.

### 7.3. Think-Aloud

Before replying, Turtle MAY emit **think-aloud** text when message complexity exceeds a threshold.

| Property | Law |
|----------|-----|
| **Presentation** | Italic / cursive formatting in Discord |
| **Visibility** | Same channel as the reply; not hidden chain-of-thought |
| **Gating** | Threshold-based — trivial exchanges skip think-aloud |
| **v1 implementation** | Single model call producing think block + answer block (§8.2) |

Think-aloud is transparency for the user, not River communication.

### 7.4. Turtle Model

The dialogue model is a **capable local open-weight model**.

| Property | Law |
|----------|-----|
| **Class** | ~30B parameter class (quality target for sustained multi-turn) |
| **Checkpoint** | Instance configuration — spec names the role, not a vendor lock |
| **Current candidate** | Gemma-family ~31B (evaluate on instance hardware at deploy time) |

Idle unload of model context after long pauses is **implementation policy**; the user MUST see presence state change in the eddy (§7.7), not silent disappearance.

### 7.5. Character

Turtle has a **distinct identity** extending the base model — warm, consistent, product-intentional. Vanilla attunement:

- Minimal Magic vocabulary
- No Spirit/Caretaker derivation as default ontology
- Conduct and soul files live in `practice_root/character/`

The agent harness (system prompt assembly, tool access, flow loading) is shaped by the practice architecture — but vanilla starts minimal.

### 7.6. Transparency in Eddies

Transparency is **mostly conversational** — Turtle explains gaps, active flows, and uncertainty in dialogue. Additionally, Turtle SHOULD emit **compact operational lines** for tool and context actions — analogous to River acts, not chat:

- `-# read state/capture.md`
- `-# flow: Shelter`
- `-# loaded 2 practice files`

Format: concise, Discord-native (`-#` small embed, or equivalent). Default for vanilla is **visible** — operational lines increase trust by showing attunement to available context. Verbose step-by-step logging is not required.

### 7.7. Presence Indicators

Turtle's join and exit MUST be visible in the eddy thread:

| Event | Presentation |
|-------|--------------|
| **Enter** | Compact system embed — `Turtle joined` |
| **Exit (idle unload)** | Compact system embed — `Turtle stepped out` |

Optional exit note path on idle departure is deferred to v1.1 (§8.1, §16). The thread persists; only presence state changes.

---

## 8. Cognitive Architecture

### 8.1. v1 Stack (Replaces Proprioception)

Vanilla turtleOS uses **two local models**, not the legacy proprioceptive stack:

| Component | Model | Trigger |
|-----------|-------|---------|
| **River** | Small local | Every river message |
| **Turtle** | Capable local | Every eddy message |

**Retired from vanilla:** proprioceptor, reflex lines, CR routing, triage→proprio→cloud pipeline, reflection tier as separate pre-dialogue path.

**Idle exit reflection (v1.1):** When Turtle steps out after extended pause, an optional short exit note MAY be written to `state/notes/` to aid re-entry. Not vanilla v1 core.

### 8.2. Think-Aloud Generation

**v1:** One Turtle model call structured as:

```text
[think-aloud — italicized when rendered]
[answer — normal prose]
```

Split think/answer across two model calls is permitted later for latency tuning; the user-facing shape stays the same.

### 8.3. Cloud Opt-In

Power users MAY configure cloud API models for Turtle (or River). This is **explicit opt-in**, not install-default. Documentation MUST NOT imply cloud dependency for the core narrative.

---

## 9. The Eddy Model

### 9.1. Definition

An eddy is a Discord thread — a **bounded conversation** with its own history. Analogous to starting a new chat in mainstream AI apps.

### 9.2. Vanilla v1 Lifecycle

| Phase | Behavior |
|-------|----------|
| **Offer** | River proposes; user approves via button |
| **Materialize** | Thread created; seed posted; chronicle link; Turtle joins |
| **Spin** | User and Turtle converse; think-aloud when warranted |
| **Persist** | Thread remains until user dissolves/archives — **no auto-dissolve** |
| **Dissolve** | User-initiated (River command, turtle-talk, or control); chronicle records event |

**No standing eddies at install:** No vortex thread, no boom thread, no pre-created system eddies.

### 9.3. Eddy Types (Deferred)

Standing wave, manual-release, metabolic Sunday sweep, and harvest/calcification pipelines are **legacy Magic-attuned patterns** — not vanilla v1 requirements. See Appendix A.

### 9.4. Attachments

**v1:** Text in the river → eddy offer → text seed in eddy.

**Later:** Images, image+text seeds, attachment-aware title inference.

---

## 10. Flows and the Execution Layer

### 10.1. Principle

turtleOS is an **execution layer for prompt programs**. Flows are markdown files — optionally with YAML front matter — that the platform loads, runs, and surfaces.

### 10.2. Turtle Practice (Shipped Flows)

The repository ships **Turtle Practice** — a library of flows (Shelter, Navigator, Thread, Companion, etc.). They are optional programs, not identity defaults. Flows MUST be Turtle Practice–ready (front matter + state hooks) before ship.

Users run a flow by:

- Materializing an eddy whose offer references a flow,
- Choosing from **`offer_flow_menu`** in the river, or
- Explicit invocation (turtle-talk command or button)

### 10.3. Front Matter Contract (Extensible)

Flows with front matter participate in **persistent practice state** across sessions. Plain prompts without front matter run in-eddy only and do not read or write platform state.

```yaml
---
title: Shelter
reads: []              # practice state files to load on entry
writes: []             # state paths this flow may update
loads: []              # legacy alias for reads — prefer reads/writes
sediment: false        # deferred — cross-eddy memory
model: default         # override Turtle model for this eddy
think_aloud: auto      # on | off | auto
---
```

Unknown keys MUST be ignored — forward compatibility.

### 10.4. Magic Framework Flows

Prompt programs authored in Magic MAY include front matter for tighter turtleOS integration. **Any plain prompt** remains runnable — the platform does not require Magic metadata.

### 10.5. Flow Storage

```
practice_root/
  flows/           # user + shipped Turtle Practice flows
  character/       # soul, conduct (attunement)
  chronicle/       # deep log
  state/           # platform practice infrastructure (§11.4)
```

Flows in the repo template are copied to the practice root at install.

---

## 11. Practice Root

### 11.1. Vanilla Default

A fresh install MUST NOT require compass, boom, bright, or intentions.

| Path | Required? | Purpose |
|------|-----------|---------|
| `character/` | Yes | Attunement — soul, conduct |
| `flows/` | Yes | Shipped + user flows (Turtle Practice) |
| `chronicle/` | Yes | Deep event log |
| `state/` | Yes | Platform practice infrastructure (§11.4) |
| `compass.md`, `boom.md`, … | No | Loaded when a flow declares `reads:` |

### 11.2. Three-Root Topology (Advanced)

For magic-attuned and multi-practitioner instances:

| Root | Purpose |
|------|---------|
| **practice_root** | Writable daily artifacts |
| **workshop_root** | Optional read-mostly Magic workshop |
| **runtime_root** | Bot operational state (locks, caches, thread metadata) |

Configured via `mage_registry.yaml`. Vanilla single-user MAY colocate practice and runtime roots.

### 11.3. Write Policy

- Turtle writes to practice root only through governed capabilities (state files, chronicle, flow outputs).
- Framework repos (`system/`, `library/`, spec files) are never written by the runtime in vanilla mode.
- **Sovereignty:** User-owned state files are updated by Turtle with user visibility (operational lines) — not silent overwrite of personal material.

### 11.4. Practice State Infrastructure

turtleOS provides **platform state management** independent of Magic. Flows with front matter coordinate reads and writes; the runtime enforces paths.

**v1 layout:**

```
state/
  notes/           # flow outcomes, exit summaries, session artifacts
  registry.yaml    # optional: file inventory, last touched (implementation)
```

**Design chapter (v1.1):** Minimum viable practice surface files (analog to portable `PRACTICE.md` patterns — capture, surface, compass-like maps) — exact shape TBD. Flows will declare `reads:` / `writes:` against whatever files exist.

**Magic export:** The `state/` layout SHOULD be documented and portable so practitioners MAY later import accumulated turtle practice state into a Magic workshop. Import path is future attunement, not v1.

**Discord access to practice files:**

- **Read:** Optional read-only web view (local HTTP / Tailscale) — implementation v1.1; not required for v1 core loop.
- **Write:** Through Turtle in eddy conversation — not raw Discord editing of sovereignty files.

---

## 12. River Act Catalog

### 12.1. Schema

Acts are structured outputs. The catalog is **extensible**; v1 implements the subset below.

```json
{
  "acts": [
    { "type": "acknowledge", "emoji": "👋" },
    { "type": "offer_eddy", "title": "...", "button_label": "Materialize eddy" },
    { "type": "revise_offer", "title": "...", "replaces": "..." },
    { "type": "offer_flow_menu", "flows": ["Shelter", "Navigator"] },
    { "type": "offer_flow", "flow_id": "shelter" },
    { "type": "chronicle", "surface": "🌀 opened: …", "jump_url": "...", "deep": { } },
    { "type": "dissolve_eddy", "thread_id": "..." },
    { "type": "pin", "message_id": "..." },
    { "type": "error", "embed": { "title": "...", "description": "..." } }
  ]
}
```

### 12.2. v1 Subset

| Act | Required v1 | Notes |
|-----|-------------|-------|
| `acknowledge` | Optional | Often paired with `offer_eddy` |
| `offer_eddy` | **Always** | Every river message |
| `revise_offer` | Yes | After user correction |
| `offer_flow_menu` | Yes | On flow-browse intent |
| `offer_flow` | Yes | Single-flow shortcut |
| `chronicle` | Yes | Includes jump URLs for eddy open |
| `dissolve_eddy` | Yes | |
| `pin` | Yes | |
| `error` | Yes | Embed only — no prose |

### 12.3. Enforcement

The River harness **rejects** raw conversational prose from the River model output. Only acts render to Discord.

---

## 13. Installation and Onboarding

### 13.1. Install Path (Vanilla v1)

From the turtleOS GitHub page through running river:

1. **Clone** the repository.
2. **Create practice root** — copy `template/` to `~/workshops/<name>/` (or equivalent).
3. **Install Python dependencies** — `requirements.txt`.
4. **Install Ollama** (or configured local inference).
5. **Pull models** — River model + Turtle model (instance config documents recommended checkpoints).
6. **Create Discord application** — bot token, required intents (`MESSAGE CONTENT`, `SERVER MEMBERS`).
7. **Create private Discord server** — practitioner-owned (sovereign setup).
8. **Configure** — `.env` + `mage_registry.yaml` (channel id → river mapping).
9. **Start shell** — bot online; river channel accepts drops; eddy offers work.

Documentation MUST walk this path end-to-end for early adopters.

### 13.2. Portable Practice (Paused)

A zero-install sibling entry via `PRACTICE.md` (markdown practice with any AI) is **paused pending practice-state design** (§11.4). It is not part of vanilla v1 onboarding. The install path is primary.

### 13.3. Discord Topology (Vanilla v1)

| Element | v1 |
|---------|-----|
| River channel | One per practitioner — the main practice surface |
| Eddies | Threads spawned on demand |
| Standing system threads | None at install |
| Shared/family channels | Optional — multi-practitioner (§15) |

### 13.4. Agent-Assisted Install

Early adopters often use agent-assisted development environments. The repository SHOULD ship an **installation skill** (agent-executable markdown flow + checklist) that walks an AI agent and user through §13.1 on the target machine. This is the recommended install path for the target population.

---

## 14. Attunement Authoring Constraints

When drafting vanilla `character/` files, the author MUST:

1. Read this spec in full.
2. Honor River no-prose and eddy-only dialogue — character does not imply river chat.
3. Keep Magic references minimal unless authoring magic-attuned bundle.
4. Define think-aloud voice (how italic thinking reads — tentative, structured, warm).
5. Define relationship stance in eddies (partner, guide, mirror — product choice).
6. Avoid Caretaker/Spirit derivation as default ontology.

Deliverables: `character/soul.md`, `character/conduct.md`, `character/river_prompt.md` (River model system guidance).

---

## 15. Multi-Practitioner (Optional)

turtleOS MAY host multiple practitioners via `mage_registry.yaml` — each with isolated practice root and river channel. Sovereign setup (own server) is recommended; hosted setup (trusted server) is permitted with explicit sovereignty tradeoff.

Cross-practitioner content boundaries: pattern observations in operator proposals are allowed; quoting another practitioner's conversation is not.

Full seneschal, permission, and multi-server law from prior spec remains valid for operators; see implementation `docs/architecture.md` during ripple pass.

---

## 16. Deferred and Out of Scope (Vanilla v1)

| Topic | Status |
|-------|--------|
| **Sediment** — cross-eddy memory governance | Design chapter |
| **Semantic eddy routing** — merge into existing threads | v2+ |
| **Standing system eddies** — vortex, boom thread | Not at install |
| **Proprioception stack** | Retired from vanilla |
| **River conversational mode** | Prohibited |
| **Auto-dissolve / metabolic sweep** | Deferred |
| **Idle exit reflection** — exit note on Turtle step-out | v1.1 |
| **MV practice surface files** — capture/compass analog | v1.1 design chapter (§11.4) |
| **Read-only practice file web view** | v1.1 optional |
| **Portable PRACTICE.md path** | Paused (§13.2) |
| **OPN / federation** | Adjacent; flow sharing later |
| **Image/audio river intake** | After text path stable |
| **Outfacing / signal drip** | Magic-attuned optional |
| **Practice-readiness scoring** | Magic-attuned optional |

---

## 17. Behavioral Laws

### The Law of Acts Not Words (River)

The River communicates only through acts. Never break character with conversational prose.

### The Law of Always Offer Eddy

Every river message includes a materialize-eddy affordance. The user always has a path into focused dialogue.

### The Law of Eddy Focus (Turtle)

Turtle speaks only in eddies. One eddy, one conversational context.

### The Law of User Consent

The River offers; the user decides. No automatic eddy spawn without button press.

### The Law of Local-First

Default install uses local open weights. Cloud is opt-in.

### The Law of Visible Thinking

When think-aloud fires, the user sees it — italicized, in the eddy, before the answer.

### The Law of Visible Operations (Eddies)

Turtle emits compact operational lines for loads and tools — trust through visible attunement.

### The Law of Substrate Honesty (Eddies)

Turtle admits uncertainty and context limits inside eddies. No fabricated recall.

### The Law of Minimal Default

Ship the smallest practice root that satisfies the product promise. Depth comes from flows and state, not mandatory Magic files.

---

## 18. Boundaries

1. **No unsupervised public publish** — nothing posts externally without explicit user approval.
2. **Sovereignty** — personal state files belong to the user; Turtle suggests and writes with visibility, not silent overwrite.
3. **No cross-practitioner content leakage** in multi-user instances.
4. **LITL awareness** — untrusted external content (links, pasted prompts) may attempt to steer behavior; act and eddy layers remain inspectable.

---

## 19. Implementation Ripple

When this spec changes, update in order:

1. `TURTLE_SPEC.md` (this file) — canonical, sole source
2. `README.md`, `ARCHITECTURE.md`, `PRACTICE.md` — scope alignment
3. `template/` — skeleton practice root (`character/`, `flows/`, `chronicle/`, `state/`)
4. Installation skill — agent-assisted install (§13.4)
5. Shell code — River act harness, eddy-only routing, think-aloud rendering, presence embeds
6. Magic bundle — stub pointer only (no mirror body)
7. Live instances last — attunement profiles, not default rewrite

---

## Appendix A. Magic-Attuned Mode (Optional)

For practitioners running **Magic-attuned persistent Spirit** on turtleOS (e.g. unified workshop mirror, triad Discord, consciousness-extension identity):

- Identity follows `library/resonance/turtle/lore/philosophy/on_consciousness_extension.md` §0 layering.
- Additional practice files (compass, boom, bright, intentions, proposals, sessions) are expected.
- Legacy patterns MAY remain active: proprioception, river-entry, vortex/prism, practice-readiness, calibration with Forge Spirit, LiveSync workshop mirror.
- These are **attunement choices**, not contradictions of platform law — provided Turtle does not speak in the river unless explicitly configured for a migration period.

Magic-attuned instances SHOULD document their profile in `mage_registry.yaml` (e.g. `attunement: magic`) so behavior matches expectations.

---

## Appendix B. Amendment Record

| Date | Change |
|------|--------|
| 2026-06-14 | Platform rewrite — River/Turtle split, vanilla v1 law, decoupling from Spirit-default identity |
| 2026-06-14 | Resonance pass — Turtle Practice terminology, always-offer-eddy, act catalog, state/, chronicle links, presence indicators, single canonical spec |

---

*End of TURTLE_SPEC*
