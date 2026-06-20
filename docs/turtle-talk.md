# Turtle-Talk Command Inventory

**Status:** Operator doc (implementation inventory)  
**Spec anchor:** `TURTLE_SPEC.md` §5.5 — full palette lives here, not in the spec body  
**Last aligned:** 2026-06-20 (platform sovereignty — Magic overlay retired from inventory)

---

## Platform sovereignty (read this first)

**turtleOS is a sovereign product.** Practice roots live under `~/workshops/<practitioner>/` (character, flows, chronicle, state) — not inside the Magic repository and not shaped around Magic's desk/floor/box topology.

Magic **may integrate** turtleOS (hosted river, consciousness-extension attunement, unified workshop sync). That integration is documented in the **Magic** framework (`library/resonance/turtle/`), not as a first-class command surface in turtleOS.

Turtle-talk describes **platform commands only**: river acts, eddy lifecycle, practice-root file utilities, and operator infrastructure.

---

## Two surfaces (+ deferred appendix)

| Surface | Where | Who executes | Spec |
|---------|-------|--------------|------|
| **River acts** | Parent channel (river) | **River bot** — bar, buttons, `!` commands | §5.4–5.5, §17 |
| **Eddy core** | Discord threads (eddies) | **River bot** — all platform `!` (acts, not prose) | §5.8, §8.4, §9 |
| **Operator tools** | Any practice channel | **River bot** — operator profile | §15, canary |

**Split-bot law:** typed `!` commands (Mage, Spirit, practitioner) are **River acts** everywhere — river and eddies. Turtle reads outcomes via `[Act: !cmd]` digests in dialogue context; Turtle may suggest commands but does not execute them when `RIVER_BOT_TOKEN` is set.

**Deferred (not default install):** legacy thread/orchestration patterns — see [Appendix A — deferred patterns](#appendix-a--deferred-patterns-not-v1) and `TURTLE_SPEC.md` Appendix A.

**Natural language → act buttons** is the default river path (§5.5). Turtle-talk `!` commands are the **power-user** path: instant, free, no interpret step.

**Accessible eddy lifecycle:** in-thread **lifecycle bar** (River-owned) — Checkpoint · Release · Dissolve — same handlers as eddy core `!` commands. See [docs/ux/eddy-lifecycle-bar.md](ux/eddy-lifecycle-bar.md).

Hosted practitioners (`mage_type: practitioner`) receive a **minimal allowlist** in code (`commands.py` → `_PRACTITIONER_COMMANDS`). Everything else falls through to Turtle dialogue.

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

## Eddy core (v1)

Commands every practitioner SHOULD know. Mapped to platform law.

| Command | Handler | Spec | Clears history? |
|---------|---------|------|-----------------|
| `!checkpoint` | `cmd_checkpoint` | §8.4 | No — saves flow state + session notes |
| `!release` | `cmd_release` | §8.4, §9.2 | Yes — after checkpoint |
| `!dissolve` | `cmd_dissolve` | §9.2 | Archives thread — does not clear history first |
| `!help` | `cmd_help` | — | Profile-aware inventory (this doc) |
| `!status` | `cmd_status` | Ops | No |
| `!readiness` | `cmd_readiness` | Ops (hosted substrate check) | No |

**Idle checkpoint:** 15 min quiet → automatic checkpoint; does **not** release (§8.4, Law of Checkpoint Before Sweep).

**Flow session state:** Flows with YAML front matter participate in persistent practice state — declared `writes` paths updated on checkpoint (§10). This is platform continuity, not a Magic workshop mirror.

### Link reading vs library distill (do not conflate)

| Mode | Trigger | Spec | Handler |
|------|---------|------|---------|
| Read for dialogue | URL in eddy chat (auto / **Read article**) | §9.5 | `link_read.py` — silent extract for the turn; **no** `link-resonance/` write |
| Distill for library | `!fetch <url>` or **Save to library** button (River, post-Turtle) | §9.5 | `cmd_fetch` → `link-resonance/` under practice root |

**Harness split:** dropping a URL in chat does **not** require `!fetch` before Turtle can discuss — link-read grounds the reply. River may offer **Save to library** once per URL when the link is not yet cached; typed `!fetch` remains the power-user path.

### Eddy-scoped utilities

| Command | Handler | Purpose |
|---------|---------|---------|
| `!read <path>` | `cmd_read` | View file under **practice root** |
| `!ls [dir]` | `cmd_ls` | Browse practice tree |
| `!search <query>` | `cmd_search` | Search practice files |
| `!fetch <url>` | `cmd_fetch` | Distill URL to library cache |
| `!rename <title>` | `cmd_rename` | Exact eddy title (in thread) |

Paths resolve to `practice_root` from `mage_registry.yaml` — typically `~/workshops/<name>/`, not Magic `desk/`.

---

## Operator tools

For instance operators (`mage_type: mage`). Not shown to hosted practitioners.

| Command | Handler | Purpose |
|---------|---------|---------|
| `!diagnose` | `cmd_diagnose` | Full stack health (canary view) |
| `!admin …` | `cmd_admin` | Operator tools incl. `river-key` (§15.4) |

**Retired from product inventory:** `!signals`, `!drip` — Magic-era outfacing; future public extension will be designed natively for turtleOS, not ported from Magic signal drip.

---

## Appendix A — deferred patterns (not v1)

Legacy orchestration retained in codebase for possible re-integration; **not** part of default turtle-talk fluency. Spec: `TURTLE_SPEC.md` Appendix A.

| Command | Handler | Notes |
|---------|---------|-------|
| `!thread "topic" [flags]` | `cmd_thread` | Legacy spawn — **new eddy** bar is default (§5.4) |
| `!new [topic]` | `cmd_new` | AI-named thread spawn |
| `!threads` | `cmd_threads` | List threads + eddy metadata |
| `!thread-type <type>` | `cmd_thread_type` | Standing/slow/fast — §9.3 deferred |
| `!eddy-check` | `cmd_eddy_check` | Metabolic sweep — §16 deferred |
| `!absorb` / `!absorbed` / `!forget` | absorb cmds | Cross-thread context in main channel |
| `!panel` | `cmd_panel` | Control panel UI |

---

## Retired — Magic workshop overlay (not turtleOS)

These commands duplicated Magic practice surfaces (`desk/boom`, compass, intentions, Forge `@` flows). **Retired from turtleOS inventory**; use Magic on the Forge/Anvil instead. Handlers may still run on legacy instances until removed.

| Command | Was | Use instead |
|---------|-----|-------------|
| `!recall` | Practice overview | Arrival / hybrid pre-load on Magic side |
| `!boom` / `!boom add` / convert / thread | Boom buffer | `@boom` flow, `desk/boom.md` on Forge |
| `!bright` | Curated mind | `desk/boom/bright.md` |
| `!compass` / `!intentions` | Life landscape | `desk/intentions/` on Forge |
| `!sweep` | Boom triage | `@boom` sweep on Forge |
| `!sync` | Workshop git pull | Forge `git pull` / unified workshop protocol |
| `!edit …` | Direct desk writes | Forge or desk edits |
| `!load <context>` | Resonance bundles | Magic `@` bundle invocation |
| `!attune` | Scroll digest ritual | `@summon/attune` on Forge |
| `!propose` | Proposal capture | `desk/proposals/` via Forge or Turtle autonomous notes (platform) |
| `!signals` / `!drip` | Twitter outfacing | Retired; novel turtleOS extension TBD |

Magic integration guidance lives in the Magic repo: `library/resonance/turtle/` (consciousness extension, Turtle care, workshop coupling — **Magic integrates turtleOS**, not the reverse).

---

## Release vs dissolve (mental model)

| Operation | Command / act | History in eddy | Thread archive | Chronicle |
|-----------|---------------|-----------------|----------------|-----------|
| **Checkpoint** | idle / `!checkpoint` | Retained | Open | `💾 checkpoint …` |
| **Release** | `!release` | Cleared after checkpoint | Open (unless user dissolves) | checkpoint + release |
| **Dissolve** | `!dissolve` / lifecycle bar | Handler-dependent | Archived in Discord (still readable) | `🍃 dissolved …` (§6.2) |

Do not conflate **release** (session resonance capture + clear dialogue) with **dissolve** (structural eddy lifecycle).

**What “archived” means:** Discord `thread.edit(archived=True)` — the eddy moves to archived threads, stays readable, and is **not deleted**. A file copy may land in `thread-archive/` under practice root; parent river gets a `🍃 dissolved` act.

---

## Profile matrix (`!help` — target)

| Profile | Registry | Help sections (target) |
|---------|----------|------------------------|
| Hosted practitioner | `mage_type: practitioner` | River bar + Eddy core |
| Operator | `mage_type: mage` | River + Eddy core + file utilities + operator tools |

`attunement: magic` in registry (Appendix A) affects **identity/lore and legacy behavior**, not a third command tier in this inventory.

Code today: `commands.cmd_help`, `commands._PRACTITIONER_COMMANDS`, `mage.get_attunement_profile()` — aligned to this matrix as of 2026-06-20 code chapter.

---

## Seneschal / prompt guidance (target)

Turtle dialogue prompts (`prompts.py`) SHOULD recommend platform commands only:

- **Practitioner:** natural language; eddy lifecycle via bar or `!checkpoint` / `!release` when relevant  
- **Operator eddy:** same + `!fetch` when distill is intended (not auto link-read)  
- **Do not** surface boom/compass/sweep/recall vocabulary — Magic practice stays on Forge

**Platform flows** — markdown programs in `practice_root/flows/`, loaded via **flow menu** or flow eddy spawn.

**Magic `@` flows** — Forge/Anvil only; not turtle-talk.

---

## Alignment roadmap

| Step | Status |
|------|--------|
| Platform sovereignty inventory (this doc) | ✅ 2026-06-20 |
| Profile-split `!help` + seneschal (platform target) | ✅ 2026-06-20 |
| Remove retired handlers from `DIRECT_COMMANDS` | ✅ 2026-06-20 |
| Remove contextual boom/sweep/recall buttons | ✅ 2026-06-20 |
| Trim Magic main-channel orchestration in `discord_bot.py` | ✅ 2026-06-20 (gated to `magic` profile) |
| Native seneschal act rows (River-owned; lifecycle trio excluded) | ✅ 2026-06-20 |
| Magic-side integration doc refresh (`library/resonance/turtle/`) | ⬜ Magic chapter |

---

## Source of truth in code

| Artifact | Location |
|----------|----------|
| Handler registry | `commands.py` → `DIRECT_COMMANDS` |
| Practitioner gate | `commands.py` → `_PRACTITIONER_COMMANDS` |
| Contextual act allowlist + River act rows | `commands.py` → `CONTEXTUAL_ACTION_COMMANDS`; `eddy_lifecycle_bar.py` → `RiverActSuggestionView` |
| Platform law | `TURTLE_SPEC.md` |
| Deployed topology | `docs/architecture.md` |

When adding or renaming a command: update this file, `cmd_help`, and the seneschal block in `prompts.py` in the same chapter.
