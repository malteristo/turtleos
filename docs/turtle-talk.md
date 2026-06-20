# Turtle-Talk Command Inventory

**Status:** Operator doc (implementation inventory)  
**Spec anchor:** `TURTLE_SPEC.md` §5.5 — full palette lives here, not in the spec body  
**Last aligned:** 2026-06-19 (v1 platform-law refurbish)

---

## Three surfaces (read this first)

Turtle-talk is not one flat list. The v1 spec organizes invocation by **where** you are and **which attunement layer** applies:

| Surface | Where | Who executes | Spec |
|---------|-------|--------------|------|
| **River acts** | Parent channel (river) | River bot — buttons + minimal `!` | §5.4–5.5, §17 |
| **Eddy core** | Discord threads (eddies) | Harness — direct `!`, no LLM | §8.4, §9.2 |
| **Magic-attuned overlay** | Operator / Magic workshop | Same harness; not vanilla v1 | §11, Appendix A, §16 |

**Natural language → act buttons** is the default river path (§5.5). Turtle-talk `!` commands are the **power-user** path: instant, free, no interpret step.

**Accessible eddy lifecycle:** in-thread **lifecycle bar** (River-owned) — Checkpoint · Release · Dissolve — same handlers as eddy core `!` commands. See [docs/ux/eddy-lifecycle-bar.md](ux/eddy-lifecycle-bar.md).

Vanilla practitioners (`mage_type: practitioner`) receive a **minimal allowlist** in code (`commands.py` → `_PRACTITIONER_COMMANDS`). Everything else falls through to Turtle dialogue.

---

## River surface

### Primary UX (not `!` commands)

| Affordance | Behavior | Spec |
|------------|----------|------|
| **new eddy** (standing bar) | Materialize blank thread; practitioner speaks first; Turtle joins on first message | §5.4, §17 |
| **flow menu** (standing bar) | Select installed flow; orientation embed; flow-titled thread | §5.4, §10.2 |
| Contextual flow acts | `offer_flow_menu` / `offer_flow` on a river message when intent detected | §5.6 |

Implementation: `river_handler.py` (`StandingEddyBarView`).

### Turtle-talk palette (spec §5.5)

| Command | Status | Notes |
|---------|--------|-------|
| `!dissolve` | `cmd_dissolve` | §9.2 — archive eddy + `🍃 dissolved` chronicle (distinct from `!release`) |
| `!flows` | `cmd_flows` | §5.5 — flow picker (same as **flow menu** bar button) |
| `!pin` | `cmd_pin` | §6 — pin message (reply or message id) |

### River prohibitions

- Turtle MUST NOT speak in the river (native v1) — §7, §17  
- River MUST NOT use conversational prose — acts only (§12.3, Law of Acts Not Words)

---

## Eddy core (vanilla v1)

Commands every practitioner SHOULD know. Mapped to platform law.

| Command | Handler | Spec | Clears history? |
|---------|---------|------|-----------------|
| `!checkpoint` | `cmd_checkpoint` | §8.4 | No — saves flow state + session notes |
| `!release` | `cmd_release` | §8.4, §9.2 | Yes — after checkpoint |
| `!dissolve` | `cmd_dissolve` | §9.2 | Archives thread — does not clear history first |
| `!help` | `cmd_help` | — | Profile-aware inventory (this doc) |
| `!status` | `cmd_status` | Ops | No |
| `!readiness` | `cmd_readiness` | Ops (practitioner substrate check when hosted) | No |

**Idle checkpoint:** 15 min quiet → automatic checkpoint; does **not** release (§8.4, Law of Checkpoint Before Sweep).

### Link reading vs library distill (do not conflate)

| Mode | Trigger | Spec | Handler |
|------|---------|------|---------|
| Read for dialogue | URL in eddy chat (auto / opt-in) | §9.5 | `link_read.py` / `handle_dialogue` |
| Distill for library | `!fetch <url>` | §9.5 | `cmd_fetch` → `link-resonance/` |

### Eddy-scoped utilities (vanilla-safe)

| Command | Handler | Purpose |
|---------|---------|---------|
| `!read <path>` | `cmd_read` | View practice file |
| `!ls [dir]` | `cmd_ls` | Browse practice tree |
| `!search <query>` | `cmd_search` | Search practice files |
| `!fetch <url>` | `cmd_fetch` | Distill URL to library cache |
| `!rename <title>` | `cmd_rename` | Exact eddy title (in thread) |

---

## Magic-attuned overlay

Required for Magic workshop operators; **not** part of vanilla v1 install (§11.1). Appendix A / §16 marks several patterns as legacy or deferred.

### Session & practice state

| Command | Handler | Spec layer | Notes |
|---------|---------|------------|-------|
| `!recall` | `cmd_recall` | Magic overlay | **Deprecated habit** — hybrid runtime often pre-loads state; see `desk/notes/on_turtle_talk.md` |
| `!boom` | `cmd_boom` | Magic `desk/` | Show buffer |
| `!boom add <text>` | `cmd_boom` | Magic | Capture thought |
| `!boom convert` | `cmd_boom_convert` | Magic | Distill conversation → boom |
| `!boom thread` | `cmd_boom_thread` | Magic | Thread essence → boom |
| `!bright` | `cmd_bright` | Magic | Curated mind surface |
| `!compass` | `cmd_compass` | Magic | Life landscape |
| `!intentions` | `cmd_intentions` | Magic | Active intentions list |
| `!sweep` | `cmd_sweep` | Magic `@boom` analog | Triage boom → bright |
| `!sync` | `cmd_sync` | Magic | Workshop freshness |
| `!edit …` | `cmd_edit` | Magic | Direct writes (boom, bright, compass, intention) |
| `!load <context>` | `cmd_load` | Magic resonance | Workshop bundles — not the same as **flow menu** flows |
| `!attune` | `cmd_attune` | Magic | Self-attunement ritual (scroll digest) |
| `!propose` | `cmd_propose` | Magic | Capture proposal artifact |

### Thread / eddy legacy (Appendix A — deferred for vanilla)

| Command | Handler | Status vs v1 |
|---------|---------|--------------|
| `!thread "topic" [flags]` | `cmd_thread` | **Legacy spawn** — bar is default (§5.4); still used by Magic-attuned orchestration |
| `!new [topic]` | `cmd_new` | AI-named thread spawn — legacy |
| `!threads` | `cmd_threads` | List threads + eddy metadata |
| `!thread-type <type>` | `cmd_thread_type` | Standing/slow/fast types — §9.3 deferred |
| `!eddy-check` | `cmd_eddy_check` | Magic-attuned only — metabolic sweep (§16 deferred; gated when `attunement: native`) |
| `!absorb` / `!absorbed` / `!forget` | absorb cmds | Cross-thread context in main channel — Magic-era pattern |
| `!panel` | `cmd_panel` | Control panel UI |

### Operator / infrastructure

| Command | Handler | Audience |
|---------|---------|----------|
| `!diagnose` | `cmd_diagnose` | Operator — canary view |
| `!admin …` | `cmd_admin` | Operator — incl. `river-key` (§15.4) |
| `!signals …` | `cmd_signals` | Magic outfacing — §16 optional |
| `!drip …` | `cmd_drip` | Magic outfacing |
| `!new` | `cmd_new` | Legacy thread spawn |

---

## Release vs dissolve (mental model)

| Operation | Command / act | History in eddy | Thread archive | Chronicle |
|-----------|---------------|-----------------|----------------|-----------|
| **Checkpoint** | idle / `!checkpoint` | Retained | Open | `💾 checkpoint …` |
| **Release** | `!release` | Cleared after checkpoint | May dissolve manual threads | checkpoint + release |
| **Dissolve** | `!dissolve` / eddy-check UI (Magic) | Cleared by handler | Archived in Discord (still readable) | `🍃 dissolved …` (§6.2) |

Do not conflate **release** (session resonance capture + clear dialogue) with **dissolve** (structural eddy lifecycle).

**What “archived” means:** Discord `thread.edit(archived=True)` — the eddy moves to archived threads, stays readable, and is **not deleted**. A file copy lands in `thread-archive/`; optional essence in boom; parent river gets a `🍃 dissolved` act.

---

## Profile matrix (`!help` behavior)

| Profile | `get_mage_type()` | Help sections shown |
|---------|-------------------|---------------------|
| Hosted practitioner | `practitioner` | River bar + Eddy core |
| Native operator | `mage` + `attunement: native` | River + Eddy core + files/fetch |
| Magic-attuned operator | `mage` + `attunement: magic` | All layers (labeled) |

Code: `commands.cmd_help`, `commands._PRACTITIONER_COMMANDS`, `mage.get_attunement_profile()`.

---

## Seneschal / prompt guidance

Turtle dialogue prompts (`prompts.py`) SHOULD recommend commands matching the active layer:

- **Practitioner:** natural language only; no boom/compass vocabulary unless they use it first  
- **Native eddy:** `!checkpoint`, `!release`; link read visible in embeds — not `!fetch` unless distill wanted  
- **Magic-attuned:** full overlay; prefer **flow menu** / eddy bar for new work; `!thread` is legacy fallback

Magic `@` flows (`@release`, `@boom`, …) are **Forge/Anvil invocations** — not turtle-talk. Flows in `practice_root/flows/` are **platform programs** loaded via flow menu or flow spawn tag.

---

## Planned alignment (documentation-first chapter)

1. ✅ This inventory (`docs/turtle-talk.md`)  
2. ✅ Profile-split `!help` + seneschal prompt layers  
3. ✅ Implement `!dissolve`, `!flows`, `!pin` river aliases  
4. ✅ Gate `!eddy-check` metabolic sweep behind Magic attunement  
5. ⬜ Trim Magic-attuned main-channel orchestration when `attunement: native`

---

## Source of truth in code

| Artifact | Location |
|----------|----------|
| Handler registry | `commands.py` → `DIRECT_COMMANDS` |
| Practitioner gate | `commands.py` → `_PRACTITIONER_COMMANDS` |
| Contextual action buttons | `commands.py` → `CONTEXTUAL_ACTION_COMMANDS` |
| Platform law | `TURTLE_SPEC.md` |
| Deployed topology | `docs/architecture.md` |

When adding or renaming a command: update this file, `cmd_help`, and the seneschal block in `prompts.py` in the same chapter.
