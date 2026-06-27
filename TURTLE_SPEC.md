# TURTLE_SPEC: Law of the Platform

> **Canonical version:** This file in the `malteristo/turtleos` repository is the sole canonical TURTLE_SPEC.  
> The Magic practice bundle links here; it does not mirror this document.

**Version:** 2026-06-25 (Share eddy Slice 1; flow library on-demand via `!flows`)  
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
| **Flow library** | In-eddy affordance to load an installed flow mid-conversation — intentional, user-initiated (§5.6). User-facing term; internal code may say *flows*. |
| **Turtle Practice** | Internal name for the shipped flow library plus platform state conventions. User-facing copy SHOULD say **flows** or **flow library**, not "Turtle Practice." Shipped programs: Navigator, Thread, Companion (Shelter archived — practitioners may install custom flows). |
| **turtle practice** | Lowercase: the activity of practicing on turtleOS — using the river, eddies, and flows. |
| **Practice root** | Local directory holding character files, flows, chronicle, state, and optional practice artifacts. |
| **Attunement** | Identity and conduct layer on the platform: native (default), craft, or magic-attuned. |
| **Sediment** | Cross-eddy curated memory. **Deferred** — design chapter, not vanilla v1 (§16). |
| **Chronicle** | Event log of structural actions (eddies opened, dissolved, checkpoints, etc.). Dual layer: surface + deep (§6). |
| **Checkpoint** | Automatic or manual capture of session resonance — flow state and/or session notes — **without** clearing eddy history (§8.4). |
| **Release** | Practitioner-initiated session close — checkpoint first, then clear history (§8.4). |

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

**Standing eddy bar:** The river channel maintains a **persistent bottom affordance** — always the last message in the timeline:

```text
[ 🌀 new eddy ]
```

This satisfies **always offer eddy** globally (§17). Practitioners materialize blank eddies by click — not from river prose. **Flow choice is in-eddy** (§5.6), not on the standing bar.

**Per-message act bundle** (parent channel only — not inside eddies):

```text
optional (as warranted):
  acknowledge(emoji)          # low-key recognition; often suppressed when alone
  offer_flow_menu()           # when user signals flows on a specific river message
  offer_flow(flow_id)         # when one flow is clearly named on that message
  error(...)                  # degraded / parse failure
not emitted in parent channel:
  offer_eddy                  # superseded by standing bar
  revise_offer                # bar path uses generic open + rename in eddy
```

After each practitioner river message, the harness MUST ensure the eddy bar remains the **last message** in the channel.

**v1 routing policy:** No semantic routing to existing eddies. Each materialize is a **new thread**. Semantic merge is deferred (§16).

**UX resonance surface:** [docs/ux/README.md](docs/ux/README.md) — living collection for practitioner-facing patterns; amend together with this spec when UX law changes.

### 5.4. Eddy Materialize (Bar Path)

**Blank eddy (`new eddy`) — Layer 1 default:**

1. Practitioner clicks **`new eddy`** on the standing bar.
2. Bar message deletes; River creates a thread anchor; Discord renders the native **thread-list embed**.
3. Thread opens as **`new eddy`** — no seed, no Turtle monologue.
4. Fresh bar posts below the new thread card.
5. Thread is an **empty room** until the practitioner speaks — no orientation embed at materialize.
6. On first in-eddy message: River retitles the thread from content; River adds Turtle (split-bot: Discord system line); Turtle replies. Flow library is **not** auto-posted — practitioner loads via **`!flows`** / **`!flow`** when wanted (§5.6).

**Load flow in eddy (Layer 2 — intentional):**

1. Practitioner opens **`new eddy`** (or continues in an existing eddy) and chooses a flow from the in-eddy library or **`!flows`**.
2. River provisional-renames the thread; River adds Turtle if not present.
3. **Turtle bootstrap** — conversational opening (intake interview when declared; no River modal).
4. Dialogue proceeds in flow voice; checkpoint on release/idle when front matter declares `writes`.

**Mid-eddy lens load:** Loading a flow after dialogue has started MUST bootstrap from thread history; MUST NOT auto-rename unless the practitioner accepts an explicit rename offer.

**Contextual offers (optional):** When the River model detects flow-browse intent on a **specific parent-channel message**, it MAY attach a contextual flow button to that message. This does not replace the in-eddy library.

**Legacy (retired):** River-bar **`flow menu`**, flow-titled spawn from bar, River modal intake (Prepare/Begin). See [docs/ux/flow-library-journeys.md](docs/ux/flow-library-journeys.md).

### 5.5. River Commands

Two paths, layered:

| Path | Audience | Behavior |
|------|----------|----------|
| **Natural language → acts** | Default | River model interprets intent → act buttons (consent before execution) |
| **Turtle-talk commands** | Power users | `!dissolve`, `!flows`, `!pin`, etc. — direct execution, no interpret step |

The turtle-talk palette SHOULD expose a river-relevant subset for v1 (dissolve, pin). Full command inventory: [docs/turtle-talk.md](docs/turtle-talk.md) — platform surfaces (river acts, eddy core, operator tools); Magic workshop commands retired from turtleOS (integrate via Magic on Forge).

The River executes; it does not discuss.

### 5.6. Flow Discovery

**Primary (in-eddy):** Practitioner-initiated only. **`!flows`** or **`!flow`** inside an eddy posts an inline flow library embed with picker; load → Turtle bootstrap (§10). **`!flows`** in the parent river redirects practitioners to open an eddy first.

**Secondary (parent channel):** When a river message signals intent to browse programs, the River MAY emit **`offer_flow_menu`** or **`offer_flow`** on **that message** — contextual, not proactive spam.

**Not shipped:** standing bottom flow library bar (retired 2026-06-25 after dogfood); standing-bar flow picker; proactive flow offers in dialogue (same policy as intentions — discoverable, user-initiated).

No prose catalog in the river.

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
| **River bot** | Acts only — bar, buttons, embeds, chronicle, **turtle-talk `!` commands** | Creates thread; adds practitioner at materialize; adds Turtle before first reply; renames thread; **executes all platform `!` in eddies** |
| **Turtle bot** | Silent (no user-message replies) | Dialogue, tools, flow-loaded prompts; reads `[Act: !cmd]` digests; may suggest commands in prose |

Practitioners MUST be able to distinguish River acts from Turtle dialogue by bot name and avatar. Single-bot mode MAY remain as a migration fallback when `RIVER_BOT_TOKEN` is unset.

**Harness split (split-bot eddies):** Turtle harness owns **read-for-dialogue** (silent link-read, excerpt inject — no `link-resonance/` write). River harness owns **distill-for-library** (`!fetch`, post-Turtle **Save to library** act row when URL is not yet cached). River MUST NOT require `!fetch` before Turtle can discuss a URL. See §9.5.

---

## 6. Chronicle

### 6.1. Purpose

The River accumulates **events**, not conversation. The chronicle is how the system remembers what happened structurally — and how users navigate **upstream** through their eddy history when Discord's sidebar loses inactive threads.

### 6.2. Event Types (v1)

| Event | Surface chronicle | Deep chronicle |
|-------|-------------------|----------------|
| Message received in river | Optional minimal line | Full payload + classification |
| Eddy offered | Button act | Offer record + inferred title |
| Eddy materialized | `🌀 opened: [title]` + **thread jump link** | Thread id, guild id, jump URL, flow_id if any, timestamp |
| Resonance checkpoint | `💾 checkpoint (idle\|manual\|release): …` | Paths written, channel id, trigger |
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

1. **Blank eddy (bar — default):** no seed at materialize — the practitioner's **first message** is the opening. Thread title starts as **`new eddy`**; River retitles from first message content. Bottom flow library bar appears after first message (§5.6).
2. **Flow active (in-eddy load):** Turtle bootstrap opening; conversational intake when declared; flow prompt sections loaded; presence tag before first flow reply (§7.6).
3. **Seeded eddy (contextual / legacy):** practitioner's river input MAY be posted as a seed embed.
4. **Deferred Turtle join:** Turtle does not join at thread create. On first in-eddy practitioner message, River adds Turtle, then Turtle replies (§7.7).
5. Turtle reads thread history (plus flow prompt sections when `flow_id` is set) and responds.

No Turtle speech in the river. No model/attunement config chrome in vanilla v1 eddies. No arrival monologue.

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

Transparency is **mostly conversational** — Turtle explains gaps, active flows, and uncertainty in dialogue.

The shell harness MAY inject **compact presence tags** for active flows (e.g. `Navigator · continuing from last time` when a checkpoint exists, or `Navigator` on a fresh start) — practitioner-facing outcomes, not filenames. In native attunement, operational `-#` lines MUST NOT be emitted by the model; the shell owns load visibility.

**Link reading:** URL fetch progress and outcomes MUST appear as **silent embeds** on the eddy timeline (Reading → Read, or failure/opt-in offers). Turtle MUST NOT narrate fetch mechanics in conversational voice; the practitioner sees trace in embeds only (§9.5).

Magic-attuned instances MAY retain model-emitted operational lines where attunement requires them.

### 7.7. Presence Indicators

Join and handoff MUST be visible in the eddy thread.

**Native split-bot (preferred):** Use **Discord-native system lines** where the API provides them — e.g. `river added [practitioner]`, `river added turtle`, `river changed the channel name: [title]`. The shell triggers these via API actions; it cannot author arbitrary system-line text.

**Single-bot fallback:** Compact join embed or equivalent MAY be used when split-bot is unavailable.

**Rejected for native v1:** Custom green "Turtle joined" embeds when Discord system lines suffice; Turtle speaking in the river; join before the practitioner speaks in a blank eddy.

| Event | Native presentation |
|-------|---------------------|
| **Materialize** | `river added [practitioner]` |
| **First in-eddy message** | `river added turtle` → Turtle reply |
| **Rename from first message** | `river changed the channel name: …` |
| **Exit (idle unload)** | Compact system embed — `Turtle stepped out` (when implemented) |

Optional exit note on idle departure remains v1.1 (§8.1, §16). The thread persists; history is retained until **release** (§8.4).

---

## 8. Cognitive Architecture

### 8.1. v1 Stack (Replaces Proprioception)

Vanilla turtleOS uses **two local models**, not the legacy proprioceptive stack:

| Component | Model | Env var | Trigger |
|-----------|-------|---------|---------|
| **River** | Small local (Qwen class) | `RIVER_MODEL` | Every river message |
| **Turtle** | Capable local (Gemma class) | `TURTLE_MODEL` | Every eddy message |

Background work (triage, reflection, delegate edits) uses the Qwen stack — see `models.py` and `.env.template`.

**Retired from vanilla:** proprioceptor, reflex lines, CR routing, triage→proprio→cloud pipeline, reflection tier as separate pre-dialogue path.

**Session resonance (v1):** After idle timeout or manual checkpoint, the platform captures flow state and session notes without clearing history (§8.4). This replaces the deferred "idle exit reflection" as the v1 continuity mechanism for flow eddies and practice sessions.

**Idle exit note (v1.1):** When Turtle steps out after extended pause, an optional short exit note MAY be written to `state/notes/` to aid re-entry — additive to checkpoint, not a substitute.

### 8.2. Think-Aloud Generation

**v1:** One Turtle model call structured as:

```text
[think-aloud — italicized when rendered]
[answer — normal prose]
```

Split think/answer across two model calls is permitted later for latency tuning; the user-facing shape stays the same.

### 8.3. Cloud Opt-In

Power users MAY configure cloud API models for Turtle (or River). This is **explicit opt-in**, not install-default. Documentation MUST NOT imply cloud dependency for the core narrative.

### 8.4. Session Resonance — Checkpoint and Release

Practitioners leave sessions without announcing closure. The platform MUST capture resonance so nothing is swept away — without simulating an explicit "session ended" unless the practitioner chooses release.

**Two operations — do not conflate:**

| Operation | Trigger | Clears eddy history? |
|-----------|---------|----------------------|
| **Checkpoint** | 15 min idle (automatic) or `!checkpoint` (manual) | **No** |
| **Release** | `!release` (practitioner explicit only) | **Yes** (after checkpoint) |

**Checkpoint (`checkpoint_session`) writes:**

| Target | Threshold | Notes |
|--------|-----------|-------|
| Flow `writes` paths (e.g. `state/notes/navigator-last.md`) | ≥2 exchanges | Mechanical tail capture; flow resolved from thread registry `context_type`, thread config, thread name, or flow signals |
| Session notes (`sessions/YYYY-MM-DD.md`) | ≥4 exchanges | LLM reflection; cooldown applies |
| Proposals / practice extraction | Per attunement | Magic-attuned and practitioner profiles as implemented |

Idle checkpoint marks the session **paused** so the monitor does not re-fire; the next practitioner message reopens it. Manual `!checkpoint` does **not** pause — the practitioner continues.

Successful checkpoints append a **chronicle** line (`💾 checkpoint …`) — River-side structural memory, not eddy dialogue.

**Release** runs checkpoint first, then clears in-memory dialogue history and confirms to the practitioner. **Never** auto-release on idle.

**Regular eddies (no flow):** session notes only at checkpoint thresholds today. **Sediment** (cross-eddy curated memory) remains deferred (§16).

**Magic-attuned:** `sessions/`, `proposals/`, and extended practice files remain expected; checkpoint law applies equally.

**In-thread lifecycle bar (v1):** Checkpoint, Release, and Dissolve SHOULD be accessible via a persistent River-owned button bar at the bottom of native eddies — same handlers as `!checkpoint`, `!release`, `!dissolve`. Dissolve uses in-place confirm (Cancel + 15s timeout revert). See [docs/ux/eddy-lifecycle-bar.md](docs/ux/eddy-lifecycle-bar.md).

---

## 9. The Eddy Model

### 9.1. Definition

An eddy is a Discord thread — a **bounded conversation** with its own history. Analogous to starting a new chat in mainstream AI apps.

### 9.2. Vanilla v1 Lifecycle

| Phase | Behavior |
|-------|----------|
| **Offer** | Standing eddy bar always visible at bottom; optional contextual flow acts |
| **Materialize** | Thread created via bar click; chronicle link; practitioner added; Turtle deferred |
| **Spin** | User and Turtle converse; think-aloud when warranted; thread may rename on first message |
| **Checkpoint** | Idle or `!checkpoint` saves resonance; history retained |
| **Persist** | Thread remains until user dissolves/archives — **no auto-dissolve** |
| **Release** | User `!release` — checkpoint + clear history |
| **Dissolve** | User-initiated archive; chronicle records event |

**No standing eddies at install:** No vortex thread, no boom thread, no pre-created system eddies.

### 9.3. Eddy Types (Deferred)

Standing wave, manual-release, metabolic Sunday sweep, and harvest/calcification pipelines are **legacy Magic-attuned patterns** — not vanilla v1 requirements. See Appendix A.

### 9.4. Attachments

**v1:** Text in the river → eddy offer → text seed in eddy.

**Later:** Images, image+text seeds, attachment-aware title inference.

### 9.5 Link Reading (Eddy Dialogue)

Practitioners expect modern-agent behavior: drop a URL, Turtle reads it and responds with awareness of the page. turtleOS MUST make fetch **progress and outcomes visible on the eddy timeline** — embed-only trace, not prose in Turtle's voice (§7.6).

**Two modes (do not conflate):**

| Mode | Trigger | Output | Cache |
|------|---------|--------|-------|
| **Read for dialogue** | URL in eddy chat (auto or opt-in) | Extract injected into turn context | No `link-resonance/` write |
| **Distill for library** | `!fetch <url>` | Distilled summary embed | Yes — `link-resonance/` |

**Auto-read (URL-primary):** External URL only; ≤120 characters of non-URL commentary; or explicit read/summarize cues.

**Discord permalinks (read-for-dialogue):** Message links (`…/channels/{guild}/{channel}/{message}`) and thread links (`…/channels/{guild}/{thread}`) in eddy chat MUST be read via the Discord bot API — visible embed trace, inject into turn context, **no** `link-resonance/` write, **no** River-side fetch before Turtle speaks. Message links inside multi-message threads MAY expand to thread history (40-message cap). Long transcripts MAY be summarized with `RIVER_MODEL` before inject (see external long-page excerpt policy). Failures use the same honest ladder (permission, paste hint).

**Incidental links:** Long messages with buried **external** URLs MUST NOT auto-fetch on the first turn. Shell posts a **Read article / Skip** opt-in; Read triggers a follow-up turn with fetch.

**Visible trace:** Silent embed lifecycle — **Reading…** → **Read** (host, char counts, **N/M in context**, spill path when applicable, LITL flag, paste/`!fetch` hints on failure). Fetch runs during typing indicator.

**Long pages:** Full extract MAY spill to `box/intake/{timestamp}-{slug}.md`; prompt receives an excerpt (default 8k chars) plus file pointer.

**Thread naming:** In split-bot mode, **River owns eddy titles** — link-read MUST NOT rename practitioner- or flow-chosen thread names. Single-bot fallback MAY rename only blank eddies (`new eddy`, `blank eddy`) or bare host slugs.

**Failure ladder:** retry, `/paste` endpoint, screenshot, paste in chat, `!fetch` for distill-only.

**Implementation:** `link_read.py`, `content_fetch.py`, `discord_ref_read.py`, `discord_bot.handle_dialogue`.

**Split-bot harness (§5.8):** Auto-read and incidental Read/Skip run in the **Turtle process** before the informed reply. **Save to library** (`!fetch` button or typed command) runs in the **River process** after Turtle replies — optional persistence, not a dialogue prerequisite. River polls thread history for Turtle prose when scheduling save offers; skip reasons (cached in `link-resonance/`, already offered, recent `!fetch` act) MUST be logged distinctly for operator debug.

---

## 10. Flows and the Execution Layer

### 10.1. Principle

turtleOS is an **execution layer for prompt programs**. Flows are markdown files — optionally with YAML front matter — that the platform loads, runs, and surfaces.

### 10.2. Shipped Flows (Flow Library)

The repository ships a **flow library** — optional prompt programs (Navigator, Thread, Companion). They are not identity defaults and not required for Layer 1 (blank eddy + Turtle). Flows MUST ship with front matter + state hooks before release. **Shelter** is archived (`template/flows/_archive/`); blank eddy + Turtle identity holds presence without a dedicated flow.

Users run a flow by:

- **`!flows`** or **`!flow`** inside an eddy (inline picker — primary discoverability),
- Contextual **`offer_flow_menu`** / **`offer_flow`** on a parent river message, or
- Custom install under `practice_root/flows/`

**Intake:** Flows with `intake` front matter use **Turtle conversational bootstrap** — not River modals. Captured values write to declared paths and load into Turtle's prompt; Turtle MUST NOT re-ask captured fields.

### 10.3. Front Matter Contract (Extensible)

Flows with front matter participate in **persistent practice state** across sessions. On session **checkpoint**, declared `writes` paths MUST be updated from conversation tail. Plain prompts without front matter run in-eddy only and do not read or write platform state.

```yaml
---
title: Navigator
reads: [state/notes/navigator-last.md]
writes: [state/notes/navigator-last.md]
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
    { "type": "offer_flow_menu", "flows": ["Navigator", "Thread", "Companion"] },
    { "type": "offer_flow", "flow_id": "navigator" },
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
| `offer_eddy` | **Retired in parent channel** | Superseded by standing **`new eddy`** bar (§5.3) |
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

### 15.1 Channel types

| Type | Purpose |
|------|---------|
| `river` | Operator/practitioner main practice surface on their own server or as primary mage |
| `hosted-river` | Sovereign practitioner's private river on an operator's server — same River harness as `river` |
| `unclaimed-river` | Private claim room before first bind; becomes `hosted-river` on river key drop |
| `shared` | Legacy multi-practitioner dialogue — migrate to `shared-river` |
| `shared-river` | Multi-member practice spaces (family, etc.) — River harness in parent; shared eddies with space `members` auto-join |

### 15.2 Practitioner profile

Hosted practitioners SHOULD be registered with `type: practitioner` in `mage_registry.yaml`. Their practice root (`~/workshops/<name>/`) MUST be isolated from the operator's and from other hosted practitioners.

Eddies in hosted rivers use practitioner character files (`character/soul.md`, `character/conduct.md`) and optional `resonance.md` — not the operator's Magic practice stack.

### 15.3 Onboarding

Each bound hosted river MUST receive one-time onboarding (pinned embed) explaining:

- Parent channel is acts-only (River); Turtle speaks in eddies only
- Standing eddy bar at the bottom opens threads
- Language and tone matched to practitioner locale (`de`, `en`, …)

Onboarding MUST NOT use Magic framework vocabulary unless the practitioner introduces it first.

Legacy binds MAY grandfather existing onboarding; new guests use the river-key claim path (§15.4).

### 15.4 River keys (invite-to-claim)

An operator MAY provision a hosted river for a guest:

1. Guest chooses an emoji out of band; operator registers it as the **river key** (practice token, not authentication).
2. Operator creates an **unclaimed-river** claim room (private: operator + bots + invitee via channel-specific invite).
3. Guest drops the emoji in the claim room → platform binds `discord_id`, renames channel, locks permissions, posts onboarding, deploys eddy bar.

Wrong keys MUST receive a clear rejection. Already-claimed rivers MUST NOT accept a second bind.

Provisioning command surface: `!admin river-key` (operator implementation).

### 15.5 Cross-practitioner boundaries

Cross-practitioner content boundaries: pattern observations in operator proposals are allowed; quoting another practitioner's conversation is not.

The operator MUST NOT surface hosted-river message content in the operator's river, proposals, or session notes. Hosted practitioners MUST NOT receive operator-style practice-readiness scoring on empty substrate — a fresh space is not "practice-ready," it is **new**.

Full seneschal, permission, and multi-server law from prior spec remains valid for operators; see implementation `docs/architecture.md` and `docs/operations/hosted-river-boundaries.md`.

### 15.6 Share eddy (thinking together)

A node MAY implement **Share eddy** — sender-initiated export of an eddy conversation to another practitioner or to a registered **space**. Share is explicit practitioner action; it satisfies §15.5 when content crosses sovereign boundaries. Design chapter: `docs/chapters/design-share-eddy.md`.

#### 15.6.1 Primitive

- **Share** creates on confirm: export bundle (digest + full transcript for Turtle context), destination digest River act, and destination eddy (received or shared). The source eddy MUST remain unchanged.
- **One primitive, two targets:** `practitioner` (1:1 fork) or `space` (shared invitation). Same confirm flow; routing differs.
- **Digest first:** Parent channel shows digest only. Full transcript MUST load into Turtle dialogue context on continue; replaying the full transcript into the Discord timeline MUST NOT be the default.

#### 15.6.2 Practitioner target

- Recipient MUST receive digest River act in their parent channel and a **received eddy** distinct from self-spawned eddies (`origin: received`, sharer attribution).
- Recipient MUST be notified at creation via **`@` mention and River act** — not DM (v1).
- Sender MUST receive chronicle-style feedback in their own parent river.

#### 15.6.3 Space target

- Requires channel `type: shared-river` (or successor) and space registry entry with `members` and `share_policy`.
- On confirm: digest River act in space parent channel and **shared eddy** created immediately (space-tagged, space default context).
- Space **members** MUST be notified at creation (`@` + River act). Sharer MUST NOT be auto-joined to the shared eddy.
- When any space member sends the **first human message** in that shared eddy, the original sharer MUST be notified (`@` + River act in sharer's river). Turtle-only opening content MUST NOT trigger this notification.
- In shared eddies, Turtle MUST use **mention-gated** response policy (default): reply only when `@`-mentioned, replied to, or explicitly invoked; peer-to-peer messages (e.g. thanks to sharer, `@` another member) MUST be recorded as witness history without a Turtle reply.

#### 15.6.4 Picker and confirmation

- Share entry point MUST offer targets from registry policy, **not** Discord channel membership alone.
- Picker MUST visually separate **Practitioners** and **Spaces**.
- A practitioner who is not a Discord member of a space channel MAY appear in the Spaces picker when `share_policy` allows (e.g. `all_practitioners`).
- A confirmation step MUST precede send, naming target and source title.

#### 15.6.5 Re-share and transparency

- Any **space member** MAY share from a **space-tagged** shared eddy to a **practitioner** target (with confirmation).
- That outbound share MUST post a **transparency River act** in the space parent channel naming who shared, with whom, and digest/title. Recipient private continuation MUST NOT appear in the space act.
- Share from a private (non-space) eddy to a practitioner MUST NOT post to unrelated spaces.

#### 15.6.6 Dissolve authority

- Only the practitioner who created the share (`share_creator`) MAY dissolve the shared or received eddy created by that share (v1).

#### 15.6.7 Operator boundaries

- Share satisfies explicit-action rules in §15.5. Operator prompts and proposals MUST still forbid quoting hosted content without such action.
- Server norm: practitioners who decline cross-share boundaries SHOULD resolve with the operator privately; product v1 MAY omit per-practitioner share deny lists.

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
| **Idle exit reflection** — exit note on Turtle step-out | v1.1 (checkpoint is v1 — §8.4) |
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

The river channel MUST always expose a materialize-eddy affordance — via the **standing eddy bar** at the bottom of the timeline. The user always has a path into focused dialogue without hunting pins or side panels.

### The Law of Checkpoint Before Sweep

Idle timeout MUST checkpoint session resonance (flow state and/or session notes per thresholds). History MUST NOT be cleared on idle. Only explicit **release** clears history.

### The Law of Eddy Focus (Turtle)

Turtle speaks only in eddies. One eddy, one conversational context.

### The Law of User Consent

The River offers; the user decides. No automatic eddy spawn without button press.

### The Law of Local-First

Default install uses local open weights. Cloud is opt-in.

### The Law of Visible Thinking

When think-aloud fires, the user sees it — italicized, in the eddy, before the answer.

### The Law of Visible Operations (Eddies)

Flow and state loads MUST be visible to the practitioner — via shell-injected presence tags in native attunement, or compact operational lines where attunement requires them (§7.6).

### The Law of Substrate Honesty (Eddies)

Turtle admits uncertainty and context limits inside eddies. No fabricated recall.

### The Law of Visible Link Read (Eddies)

When Turtle reads a URL or Discord permalink for dialogue, the practitioner MUST see progress and outcome on the timeline — via embeds, not fetch prose in Turtle's voice. Read-for-dialogue and distill-for-library (`!fetch`) remain distinct operations. Discord permalinks are never distilled to `link-resonance/`.

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
2. `docs/ux/README.md` — practitioner UX resonance (patterns, journeys, rejected UX, review checklist)
3. `README.md`, `ARCHITECTURE.md`, `PRACTICE.md` — scope alignment
4. `template/` — skeleton practice root (`character/`, `flows/`, `chronicle/`, `state/`)
5. Installation skill — agent-assisted install (§13.4)
6. Shell code — River act harness, eddy bar, checkpoint/release, think-aloud rendering
7. Magic bundle — stub pointer only (no mirror body)
8. Live instances last — attunement profiles, not default rewrite

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
| 2026-06-18 | Native eddy bar (replaces per-message offer_eddy / Eddy Door); split-bot system lines; flow eddy orientation; checkpoint vs release (§8.4); chronicle checkpoint events |
| 2026-06-18 | Eddy link reading (§9.5) — visible embed trace, read vs `!fetch`, spill, Read/Skip for incidental URLs; Law of Visible Link Read |
| 2026-06-18 | UX doc split — `docs/ux/` topic collection replaces monolithic `docs/ux-principles.md` |
| 2026-06-19 | §15 — hosted-river, unclaimed-river, practitioner onboarding, river keys (invite-to-claim), sovereignty boundaries |
| 2026-06-20 | §5.5 — turtle-talk inventory cross-ref; §8.4 — in-thread lifecycle bar law (Checkpoint · Release · Dissolve) |
| 2026-06-20 | §5.5 — turtle-talk inventory: platform sovereignty; Magic workshop overlay retired from product inventory; signals/drip retired |
| 2026-06-20 | §5.8 — River bot owns all turtle-talk `!` execution (split-bot); Turtle reads `[Act: !cmd]` digests; bar posts use River client identity |
| 2026-06-20 | §5.8 / §9.5 — harness split: Turtle silent link-read vs River post-Turtle Save to library (`!fetch`); distinct skip logging |
| 2026-06-23 | In-eddy flow library — bar = `new eddy` only; Turtle bootstrap intake; Shelter archived; user-facing **flows** / **flow library** |
| 2026-06-25 | §15.6 Share eddy Slice 1 (practitioner target, `!share`); flow library on-demand (`!flows` / `!flow`); standing bottom flow bar retired — see `docs/chapters/2026-06-25-share-eddy-slice1-dogfood.md` |
| 2026-06-20 | §9.5 — Discord permalink read-for-dialogue (`discord_ref_read.py`): visible trace, thread history, long-thread summary; distinct from external URL read and `!fetch` |

---

*End of TURTLE_SPEC*
