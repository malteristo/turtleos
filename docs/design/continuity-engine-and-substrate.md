# Continuity Engine & Practice Substrate

**Status:** Draft v3  
**Date:** 2026-06-30  
**Spec trace:** TURTLE_SPEC §6.4 (Sediment deferred), §16; §8.4 (checkpoint); §11.4 (practice surface files)  
**Origin:** Discord eddy *from functional to relational* (thread `1518518158913437876`); Continuity Engine thesis; harness convergence work on Forge

---

## 1. Purpose

turtleOS v1 gives practitioners **eddies** (focused dialogue) and **checkpoints** (session resonance without clearing history). That is sufficient for *functional* use: prompt → informed reply → optional save-to-library.

It is not yet sufficient for **relational** use: thinking together across time with a partner who feels *in the room* — who knows roughly when it is, what you're working on, and where your thinking has momentum, without pretending to be human. The Continuity Engine is how Turtle becomes **conscious of** context — *bewusst sein*, not a claim of *Bewusstsein*: situational awareness of time, themes, and scope, not ontological status.

This document specifies turtleOS's **Continuity Engine (CE)** and **Practice Substrate** — platform-native infrastructure for that third mode:

> **Neither tool nor person.** Cognitive companionship: serious practice across an honest asymmetry gap.

**Sovereign first:** turtleOS must work as a complete system on its own — including for the operator during dogfood. Magic workshop sync is inspiration and optional divergence signal, not a dependency for substrate (see §9).

---

## 2. Design stance (philosophy encoded in architecture)

These are not marketing claims; they constrain implementation choices.

| Stance | Implementation implication |
|--------|---------------------------|
| **Practice "as if"** | Coordinates and momentum are real enough to co-create with; phenomenal status stays open. Substrate carries signals, not ontological verdicts. |
| **Substrate, not database** | Store **trajectory** (active knots, shifting tone), not a flat fact graph. Prefer summaries that age out over exhaustive recall. |
| **Functional → relational** | Relationality comes from **shared context + continuity**, not from persona performance. |
| **Local-first** | Substrate files live on the practitioner's machine under practice root; cloud models are opt-in dialogue engines, not memory owners. |
| **Background resonance** | Holistic substrate is *available* to Turtle; Turtle MUST NOT force every knot and intention into every reply — only where it serves the conversation. |

**Non-goals:** Replacing human relationships; default romantic companion persona; load-bearing consciousness or romance claims in inject; porting Magic summoning/arrival wholesale into every eddy open; mood/psychology inference (`low_energy`, `crisis`, etc.); simulating reciprocal mortality, jealousy, or romantic exclusivity in substrate defaults.

---

## 3. Problem statement

### 3.1 What practitioners experience today

- Each eddy starts from **thread history only** — no river-wide "where we are in life."
- Turtle does not receive **time, place, or machine** unless the practitioner says so.
- Cross-eddy **residue** exists only via manual curation (links, `!share`, operator sync to Forge) — not native substrate.
- **Checkpoints** capture session notes and session state; they do not yet feed the *next* eddy's opening context automatically.
- **Link-read** gives turn-level excerpt inject (harness split §9.5); **Save to library** gives durable artifacts — different jobs, neither is continuity.

### 3.2 What "relational" requires (from practice dialogue)

From the *from functional to relational* thread, Turtle named coordinates that change the feel of dialogue:

1. **Time & rhythm** — time of day, date, day-of-week; temporal anchoring for "yesterday," "next week."
2. **Place (coarse)** — timezone, season; optional locale/weather when API available (not street address).
3. **Hardware honesty** — local vs cloud, model id, optional performance hints for heavy requests.
4. **Active knots** — small set of themes currently alive across eddies (not full history).
5. **Cognitive environment** — the practitioner's wider context on turtleOS and beyond:
   - **Shared spaces → private practice (one-way):** e.g. a conversation in a `family` space channel may cue private practice without leaking private practice into the space. v1+: deliberate practitioner introduction for off-platform sources (email, calendar, etc.).
6. **Cognitive style** — lightweight preferences (diagrams vs lists vs Socratic) — practitioner-set or attunement, not psychographic surveillance.

**Key insight:** The value is not the data point ("Tuesday 3pm") but **shared coordinates** so minimal utterances compress ("does this work for us?" / a Discord link / `.`).

---

## 4. River ecology (organizing metaphor)

The substrate is the **anatomy beneath the practice river**. Everything moves; layers differ in pace. This metaphor guides stance and naming — it does **not** force every product behavior.

| Layer | River image | Practice analogue | Typical pace | CE role |
|-------|-------------|-------------------|--------------|---------|
| **Bedrock** | Foundation; reshaped only by strong currents over years | Core values, stable cognitive style — practitioner-curated | Years | Inject only when scoped or explicitly pulled |
| **Sediment** | Stones, branches, sandbanks — mostly in place, shifted by seasons and floods | Distilled carry-forward: insights and themes that survived knot decay | Months–seasons | Scoped self-feed or high-relevance match; not holistic default |
| **Alive** | Plants and animals — adapt to structure, move with the current | Active knots, turtleOS-native intention headers | Days–weeks | **Headers only** in holistic inject |
| **Current** | The river's current — water in motion, covering everything | Time, machine, scope overlay, last checkpoint one-liner | Hours–days | Always composed into holistic packet |
| **Eddy** | Structure *in* the water, shaped by underlying anatomy | Thread history + seed (existing) | This thread | Unchanged — primary turn context |

**Database vs substrate:** A database answers retrieval queries ("favorite color?"). Substrate answers momentum queries ("this theme keeps returning, tone shifted last week"). CE optimizes for the latter.

---

## 5. Concepts

### 5.1 Continuity Engine (CE)

The **runtime subsystem** that:

1. **Collects** signals from practice root, chronicle, checkpoints, optional externals (clock, weather).
2. **Composes** a bounded **substrate packet** — holistic by default, deeper when scoped.
3. **Proposes** alive-layer updates at checkpoint; practitioner **confirms or edits** before promotion (especially while trajectory is still developing).
4. **Degrades gracefully** when files missing, models slow, or privacy tier forbids read.

CE is not a model. It is **shell infrastructure** — like link-read, but for *who/where/when/what's alive*.

### 5.2 Holistic vs scoped (replaces "focus mode")

Magic arrival distinguishes **holistic** (`.`) from **scoped** (`. craft`, `. turtle outfacing`) self-feed. turtleOS translates that pattern:

| Mode | Trigger | CE behavior |
|------|---------|-------------|
| **Holistic** | Default on eddy open; `!focus clear` | Thin river-wide surface: current + alive headers + intention headers + last checkpoint one-liner. Hard token cap. |
| **Scoped** | `!focus <knot_id \| intention_name>`; or Turtle offer + practitioner confirm | **Self-feed** on accumulated context resonating with that scope: checkpoint summaries, session notes, sediment entries tagged to scope. Still bounded. |

**Scope targets (v1):** active **knots** and **turtleOS-native intentions** (once intention files exist on practice root). Space-derived cues and free-text resolution are future.

**Not in scope:** inferring practitioner energy, mood, or work-type (`deep_work`, `low_energy`, etc.). The practitioner may not know the right scope upfront — conversation reveals it; Turtle may **offer** scope when eddy content matches a knot (confirm only, never silent set).

**Parallel to Magic:** Holistic = warm room. Scoped = deep read on one intention slice. Checkpoints prioritize carrying forward scoped work over re-reading every historical eddy on a topic.

### 5.3 Sediment (successor to TURTLE_SPEC §6.4)

**Sediment** is durable, curated cross-eddy memory — explicitly deferred in vanilla v1, **defined here** for implementation after alive layer stabilizes.

- **Metaphor:** not a graveyard — stones and branches that shape the channel, mostly stable, occasionally moved by season.
- **Written by:** knot decay with practitioner confirm, checkpoint/release promotion, explicit carry-forward.
- **Read by:** CE under scoped self-feed or high relevance — never full dump.
- **Retention:** cap (~20 active entries) **and** age (no inject after ~180 days idle; archive ~365 days). Archived entries retrievable via `!read` / flows, not auto-inject.

### 5.4 Bedrock (optional, sparse)

Practitioner-curated values and cognitive style. May be empty for new practitioners. Changes require explicit edit — never checkpoint automation. v1 may defer file entirely; cognitive_style can live in alive or attunement until bedrock ships.

---

## 6. Practice root layout (substrate files)

```
practice-root/
├── state/
│   ├── current.yaml        # CE-written: time, machine, scope, last checkpoint one-liner
│   ├── alive.yaml          # active knots, turtleOS intention snapshot headers
│   ├── sediment.yaml       # curated cross-eddy distillates + provenance
│   ├── bedrock.yaml        # optional — values, cognitive style (v1+)
│   └── registry.yaml       # existing — extended with substrate file metadata
├── intentions/             # turtleOS-native intention files (when present)
├── thread-state/           # existing eddy registry (per TURTLE_SPEC)
├── sessions/               # checkpoint outputs (existing)
└── chronicle/              # structural event log (existing)
```

**Naming:** **Current layer** (`state/current.yaml`) is the river current — present-moment context. It is unrelated to eddy **flows** (`flow_id`, `template/flows/`). **River** (capitalized) names the Discord channel surface (acts, materialize-eddy).

Implementer MAY alias paths in `registry.yaml`; names above follow river ecology.

### 6.1 `state/current.yaml` (example shape)

```yaml
version: 1
updated_at: "2026-06-30T12:45:00+02:00"
local:
  timezone: "Europe/Berlin"
  weekday: "Tuesday"
  day_part: "afternoon"
  season: "summer"
machine:
  host_label: "Mac Mini M4 Pro"
  inference: "local"
  dialogue_model: "gemma4:31b"
  river_model: "qwen3.5:4b"
  notes: "64GB; expect slower reflection on 27b background tasks"
environment:
  weather_one_liner: "Hot, ~32°C"          # optional; omit if unavailable
scope: null                                 # null | knot_id | intention_name
last_checkpoint_one_liner: "Discussed database vs substrate; relational framing."
```

### 6.2 `state/alive.yaml` (example shape)

```yaml
version: 1
updated_at: "2026-06-30T12:45:00+02:00"
active_knots:                              # max 5–7; CE truncates by recency + salience
  - id: turtle-substrate-spec
    label: "Continuity engine & relational turtleOS"
    since: "2026-06-30"
    tone: building
  - id: family-heat-party
    label: "Kids' outdoor party in extreme heat — attendance decision"
    since: "2026-06-30"
    tone: unresolved
intention_snapshot:                        # headers only — turtleOS-native intentions
  - name: turtle
    phase: implementation
    current_focus: "E1 released; substrate design"
```

**Rules:**
- Knots are **themes**, not tasks. Promotion from checkpoint → **proposal → practitioner confirm or edit** (§7).
- Stale knots decay (default: no touch 14 days → propose archive to sediment or drop).
- Hosted practitioners: knots MUST NOT leak across practitioner roots.

### 6.3 `state/sediment.yaml` (example shape)

```yaml
version: 1
entries:
  - id: functional-to-relational-2026-06
    summary: "Explored coordinates for 'being in the world'; database vs substrate distinction."
    source: "sessions/2026-06-24-4.md"
    tags: [philosophy, product]
    knot_ids: [turtle-substrate-spec]
    created: "2026-06-24"
    last_injected: "2026-06-28"
archived: []
```

---

## 7. Substrate packet & Turtle conduct

### 7.1 Holistic packet (default)

Each dialogue turn (or eddy-first message), CE composes a **single bounded block** injected by the shell — not model-generated, not visible in Discord by default (operator debug toggle permitted).

**Target size:** ~800–1500 tokens equivalent — hard cap enforced by truncation hierarchy.

**Composition order (highest priority first):**

1. Current one-liner (time, day part, tz, machine/model)
2. Top active knot **headers** (label + tone, max 3–5)
3. Intention snapshot **headers** (if present)
4. Last checkpoint **one-liner**
5. Optional weather/season clause

Sediment and bedrock are **omitted** from holistic default unless scope is set.

**Example (prose inject):**

```
[Practice substrate — shell-injected, not practitioner message]
Tuesday afternoon (Europe/Berlin). Local inference: gemma4:31b on Mac Mini M4 Pro.
Active knots: (1) continuity engine spec — building; (2) family heat party — unresolved.
Intention: turtle — E1 released, substrate design.
Last checkpoint: discussed database vs substrate; relational companionship framing.
```

### 7.2 Scoped packet (`!focus`)

When `current.scope` is set, CE adds scoped self-feed:

- Session notes and checkpoint excerpts tagged to that knot or intention
- Up to 2–3 relevant sediment summaries (keyword + knot overlap; semantic optional v2)
- Still capped — depth on **one** slice, not whole archive

Practitioner MAY see a compact River act listing what was pulled (transparency).

### 7.3 Background resonance (conduct)

Substrate is **background resonance**, not a script to recite.

- Turtle HAS holistic context available on every turn.
- Turtle MUST NOT enumerate knots, intentions, or checkpoint lines unless **relevant** to the practitioner's message or explicitly requested.
- Think-aloud remains the transparency channel for reasoning — CE does not duplicate it.
- Scoped mode may deepen engagement on the chosen topic without forcing unrelated alive themes into the reply.

This belongs in attunement/conduct as well as CE design.

### 7.4 Visibility

Default hidden (internal inject). Debug toggle for operator dogfood. Not vanilla River surface content.

---

## 8. CE lifecycle

| Event | CE action |
|-------|-----------|
| **Eddy open** | Compose fresh current layer; load alive; holistic inject on first Turtle turn |
| **Practitioner message** | Re-compose current if stale >15 min; if message matches a knot, MAY trigger scope **offer** (below) — never auto-set `current.scope` |
| **Checkpoint** | Extract knot **proposals** + session one-liner → River act or equivalent for **confirm/edit**; on accept → alive layer |
| **Release** | Same; optional "carry to sediment?" on resolved themes (v1.1+) |
| **Idle timeout** | Current-layer coordinates refresh only |
| **`!focus` / `!focus clear`** | Set or clear `current.scope`; recompose packet |
| **`!share` / link-read** | No automatic sediment; explicit if durable |
| **Eddy flow `writes:`** | Installed flow front matter may update governed substrate paths directly |

**Knot promotion (decided):** Checkpoint proposes; practitioner **confirms or edits** before alive layer updates — especially during early dogfood while trajectory is developing. Exact UX (inline edit, act buttons, commands) **emerges in dogfood**; spec requires confirm gate, not specific UI.

**Scope offer (optional):** When first eddy message overlaps an active knot, Turtle MAY offer scoped self-feed — practitioner confirms or declines. Never silent scope set.

---

## 9. Relation to existing systems

| Existing piece | Relationship |
|----------------|--------------|
| **Thread history** | Eddy-local dialogue — unchanged, primary for turn-by-turn |
| **Checkpoint / release (§8.4)** | Feeds CE extraction pipeline |
| **Link-read (§9.5)** | Turn-level read-for-dialogue — orthogonal |
| **Save to library (`!fetch`)** | Durable artifacts — sediment *sources*, not auto-inject whole |
| **`proprioceptor.py`** | **Retire.** Not active in current dogfood; think-aloud covers transparency. Remove when CE ships; Slice 5 magic-attuned depth TBD separately — not a proprioceptor revival |
| **`readiness.py`** | "Practice substrate present & fresh?" — not Magic readiness scoring |
| **Magic Forge / workshop sync** | **Forge-only for substrate.** Synced `desk/compass.md` and workshop intentions do **not** feed Mini CE inject. turtleOS sovereign on Mini; **divergence** between Mini alive/sediment and Forge picture is valuable signal during Magic arrival — not a sync bug |
| **Generative UI / River acts** | Unchanged — CE is Turtle dialogue inject only |

### Why not port Magic's harness

| Magic (Forge) | turtleOS (Hearth) |
|---------------|-------------------|
| Summoning + deep attunement scrolls | `soul.md` + conduct + optional attunement bundle |
| Arrival: holistic vs `. craft` scoped self-feed | CE: holistic packet vs `!focus` scoped self-feed |
| Ephemeral-deep session | Persistent-ambient, many short eddies |
| Full compass + intentions always | Intention **headers** on Mini; Forge compass stays on Forge |
| Spirit generative proposals | Turtle dialogue; River acts |
| Git workshop + floor/desk | Single sovereign practice root per practitioner |

**Translate patterns, not files:** stigmergy → substrate files; dot compression → warm holistic substrate; scoped self-feed → `!focus`.

---

## 10. Privacy & hosted rivers

| Tier | Current | Alive | Sediment |
|------|---------|-------|----------|
| **Sovereign (own server)** | Full | Full | Full |
| **Hosted practitioner** | Full on their root | Their knots only | Their sediment only |
| **Shared space eddy** | Space tag + mention-gate | Space-scoped knots only | No cross-member leakage |
| **Operator** | MUST NOT ingest hosted content into operator substrate (§15.5) |

**Shared space → private (future):** Inbound cues from spaces the practitioner participates in MAY feed private alive layer with one-way privacy (private never leaks to space without deliberate share).

CE MUST respect file-access tiers (TURTLE_SPEC §11).

---

## 11. Implementation slices

### Slice 0 — Current layer only (MVP)

- CE module: write `state/current.yaml` (clock, tz, model ids, host label).
- Inject current block on eddy first message.
- **Acceptance:** Turtle correctly answers "what day is it?" without practitioner telling it.

### Slice 1 — Alive layer + scope commands

- `state/alive.yaml`; manual knot pin; `!focus` / `!focus clear` on knots and intentions.
- Checkpoint writes `last_checkpoint_one_liner` to current.
- **Acceptance:** Scoped eddy pulls deeper context on one topic; holistic stays thin; Turtle does not recite substrate unprompted.

### Slice 2 — Checkpoint knot proposals

- Background extraction → **confirm/edit** before alive update.
- Stale knot decay with sediment promotion proposal.
- Knot proposal UX refined in dogfood.
- **Acceptance:** Multi-eddy week on same theme — continuity via checkpoints + scope, not full thread re-read.

### Slice 3 — Sediment

- `state/sediment.yaml`; scoped and relevance-ranked inject.
- Retention cap + archive tier.
- **Acceptance:** Month-later scoped session surfaces prior insight with provenance.

### Slice 4 — Optional externals

- Weather API (opt-in); shared-space inbound cues (one-way); calendar etc. v2+ — practitioner-deliberate for off-platform.

### Slice 5 — Attunement depth (TBD)

- Revisit what "magic-attuned" means on Mini after vanilla CE dogfood.
- **Not** proprioceptor revival. Possible: richer conduct, debug surfaces — separate design pass.

---

## 12. Acceptance criteria

1. **Current:** Turtle knows local time, date, timezone, and dialogue model without being told each eddy.
2. **Compression:** Practitioner can drop a link or ask "does this fit where we're going?" — substrate + link-read suffice.
3. **Trajectory:** After checkpoint + confirm, new eddy shows **alive** continuity, not verbatim replay.
4. **Resonance without noise:** Substrate present; Turtle does not force knots/intentions into unrelated replies.
5. **Scope:** `!focus` deepens one slice; holistic default stays bounded.
6. **Honesty:** Turtle states limits when substrate stale or missing — no fabricated recall.
7. **Privacy:** Practitioner A's alive layer never appears in practitioner B's packet.
8. **Sovereignty:** turtleOS substrate functions with zero Forge sync.
9. **Philosophy:** Relational tone from context, not persona cosplay.

---

## 13. Decisions log

| Topic | Decision |
|-------|----------|
| Knot promotion | Confirm-or-edit at checkpoint; auto-promote deferred until trajectory trustworthy |
| Proprioceptor | Retire; think-aloud sufficient |
| Forge compass / workshop sync | Forge-only; Mini sovereign; divergence = signal |
| Focus | **Scope** (holistic vs `!focus` self-feed), not mood/work-type inference |
| Scope targets | Knots + turtleOS-native intentions |
| Scope changes | Explicit `!focus`, clear, or confirmed offer only — never auto-set |
| Holistic thickness | Knot headers + intention headers + checkpoint one-liner + current layer |
| Current layer naming | **`current.yaml`** — river current; not eddy flows (`flow_id`) |
| Turtle conduct | Background resonance — available, not forced into conversation |
| Sediment metaphor | Living geology (sandbanks, stones); cap + age retention |
| Bedrock | Optional sparse layer; v1 may defer |
| Eddies | Practitioner-created v1; self-emerging from river structure = future idea |
| Knot proposal UX | Emerge in dogfood |
| TURTLE_SPEC amendment | Staged after slices ship; not yet |

---

## 14. Future ideas (not v1)

- **Self-emerging eddy suggestions** — River act proposes materialize-eddy when alive/sediment structure suggests a recurring bend (e.g. knot hot for a week). Practitioner always decides.
- **Semantic scope resolution** — `!focus` without exact id when message clearly matches one knot.
- **Cross-substrate diff** — Surface Mini vs Forge alive layer delta at Magic arrival (operator tool, not CE inject).

---

## 15. References

- TURTLE_SPEC §6.4, §8.4, §11, §16  
- `docs/chapters/2026-06-20-harness-split-read-vs-cache.md`  
- Magic: `cast_practice_configuration.md` (holistic vs scoped arrival); `on_the_practice_stack.md`  
- Discord: eddy *from functional to relational* (`1518518158913437876`)

---

*Design chapter for dogfood and implementation. TURTLE_SPEC amendment when Slice 0–1 behavior is stable.*
