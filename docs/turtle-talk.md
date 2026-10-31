# Turtle-Talk Command Inventory

**Status:** Operator doc (implementation inventory)  
**Spec anchor:** `TURTLE_SPEC.md` §5.5 — full palette lives here, not in the spec body  
**Last aligned:** 2026-06-25 (Share eddy `!share`; flow library on-demand via `!flows` / `!flow`)

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

**Split-bot law:** typed `!` commands (Mage, Spirit, practitioner) are **River acts** everywhere — river and eddies. Turtle reads outcomes via `[Act: !cmd]` digests in dialogue context; Turtle may suggest commands but does not execute them when `RIVER_BOT_TOKEN` is set. Structured contextual offers: Turtle proposes via `offer_river_act` / `[[act-offer:…]]` → River posts the button (`act_offer_signal.py`); never via prose backtick parsing.

**Deferred (not default install):** legacy thread/orchestration patterns — see [Appendix A — deferred patterns](#appendix-a--deferred-patterns-not-v1) and `TURTLE_SPEC.md` Appendix A.

**Natural language → act buttons** is the default river path (§5.5). Turtle-talk `!` commands are the **power-practitioner** path: instant, free, no interpret step.

**Accessible eddy lifecycle:** in-thread **lifecycle bar** (River-owned) — Checkpoint · Release · Dissolve — same handlers as eddy core `!` commands. See [docs/ux/eddy-lifecycle-bar.md](ux/eddy-lifecycle-bar.md).

Hosted practitioners (`mage_type: practitioner`) receive a **minimal allowlist** in code (`commands.py` → `_PRACTITIONER_COMMANDS`). Everything else falls through to Turtle dialogue.

---

## River surface

### Primary UX (not `!` commands)

| Affordance | Behavior | Spec |
|------------|----------|------|
| **new eddy** (standing bar) | Materialize blank thread; practitioner speaks first; Turtle joins on first message | §5.4, §17 |
| **more** (standing bar select) | The house's own surfaces, answered privately: mcp · model | §5.3 |
| **flow library** (in-eddy) | **`!flows`** or **`!flow`** in eddy posts inline picker; load → Turtle bootstrap | §5.4, §5.6, §10.2 |
| Contextual flow acts | `offer_flow_menu` / `offer_flow` on a river message when intent detected | §5.6 |

Implementation: `river_handler.py` (`StandingEddyBarView`).

### Turtle-talk palette (spec §5.5)

| Command | Status | Notes |
|---------|--------|-------|
| `!dissolve` | `cmd_dissolve` | §9.2 / §9.6 — archive eddy + `🍃 dissolved` chronicle (distinct from `!release`); native **Close Thread** uses same pipeline (policy C) |
| `!flows` | `cmd_flows` | §5.6 — in-eddy flow picker (`!flow` alias); in parent river, redirects to open an eddy |
| `!flow` | `cmd_flows` | Alias for `!flows` |
| `!pin` | `cmd_pin` | §5.3 — **eddy:** bind working plan (home eddy + river pin card); **river:** legacy message pin (reply / id) |

### River prohibitions

- Turtle MUST NOT speak in the river (native v1) — §7, §17  
- River MUST NOT use conversational prose — acts only (§12.3, Law of Acts Not Words)

---

## Eddy core (v1)

Commands every practitioner SHOULD know. Mapped to platform law.

| Command | Handler | Spec | Clears history? |
|---------|---------|------|-----------------|
| *(retired)* `!checkpoint` | `cmd_checkpoint` (the checkpoint button under `...` and Turtle's offer run it) | §8.4 | No — saves flow state + session notes. Typing it answers once; the idle checkpoint (15 min) runs on its own |
| `!release` | `cmd_release` | §8.4, §9.2 | Yes — after checkpoint |
| `!context` (operator) | `cmd_context` | §3.2 | No — renders the packet this eddy's last turn injected. Operator group of the `!` card; not a member command |
| `!dissolve` | `cmd_dissolve` | §9.2 | Archives thread — does not clear history first |
| `!help` (and a bare `!`) | `cmd_help`, `help_card.py` | — | The curated commands as one card in three groups, plus an operator group for the operator. What is deliberately unlisted is `help_card.LISTED_ELSEWHERE` (a test compares both lists with the registry). Design: [curated-surfaces-v1](design/curated-surfaces-v1.md) |
| `!status` (operator) | `cmd_status` | Ops | No. Operator group of the `!` card; not a member command, not pinnable |
| `!readiness` | `cmd_readiness` | Ops (hosted substrate check) | No |
| `!model` | `room_models.cmd_model` | §8.1, [own-channel-model](design/own-channel-model.md) | No — shows this channel's model, plus River and Memory (system models, not picked here), and a menu of local and API models the house can route to. `!model sonnet-5.5` / `opus` / `local` picks this channel — in your own channels (and your health channel, as its owner), and in any shared room you are a member of (the room is told who changed it). The conversation default is the local Gemma model |
| `!feed` | `backlog_feed_ui.cmd_feed` | [magic-channel](design/magic-channel.md) | No — craft only, the channel owner only. Posts every backlog pitch not posted yet, each with Build, Drop and Talk it through. River also posts new ones on its own when the channel has `push: true` (never at night). `!feed queue` lists what Spirit was asked to build; `!feed status` counts |
| `!mcp` | `cmd_mcp` | [mcp-connections](design/mcp-connections.md), [connection-chooser](design/connection-chooser.md) | No — posts a button. The reply only the person who pressed can see is built in the [design language](ux/design-language.md): *Who can read your context* (a card per program, a row per thing — notes, health picture, practice — with its state and its own Open or Close, and End connection, which asks once) and *What your house uses for you* (X, its state, the room it answers in, Pause and Remove X). A press changes the reply in place. Your own connections only; the card in your home channel follows what you change here |

**Idle checkpoint:** 15 min quiet → automatic checkpoint; does **not** release (§8.4, Law of Checkpoint Before Sweep).

**`!context` (readability contract):** shows, for this eddy's last turn, the shell-injected blocks by name, the tools called, the files loaded, which injection slots were empty, and — when the room had notes to choose from — every note the window offered with a mark for whether it was carried. The source of truth is `state/packets/<eddy-id>.md` — a file the turn wrote, not Turtle self-report. It does not name the alive layer.

**`!focus` is retired (2026-10-14).** Focusing is something Turtle does when told, shown a file, or given an eddy link. Typing it answers once with that pointer (`help_card.RETIRED`). The continuity-engine scope it wrote (`state/scopes.yaml`) is still read; nothing writes it now (issue 056).

**Flow session state:** Flows with YAML front matter participate in persistent practice state — declared `writes` paths updated on checkpoint (§10). This is platform continuity, not a Magic workshop mirror.

### Link reading vs library distill (do not conflate)

| Mode | Trigger | Spec | Handler |
|------|---------|------|---------|
| Read for dialogue | URL in eddy chat (auto / **Read article**) | §9.5 | `link_read.py` — silent extract for the turn; **no** `link-resonance/` write |
| Distill for library | **Save to library** button (River, post-Turtle); the typed `!fetch` is retired and answers with a pointer | §9.5 | `cmd_fetch` → `link-resonance/` under practice root |

**Discord links** (message, eddy, or whole channel) are read on the poster's behalf: only what they can see; a heads-up when it lands in a room where some people couldn't see it; frontier-model rooms read more before summarising ([own-channel-model](design/own-channel-model.md)).

**Harness split:** dropping a URL in chat does **not** require `!fetch` before Turtle can discuss — link-read grounds the reply. River may offer **Save to library** once per URL when the link is not yet cached; typed `!fetch` remains the power-practitioner path.

### Eddy-scoped utilities

| Command | Handler | Purpose |
|---------|---------|---------|
| *(retired)* `!export`, `!artifacts`, `!read` | `cmd_export`, `cmd_artifacts`, `cmd_read` (the Open, Browse and Download buttons run them) | Typing one answers once: ask Turtle; saved notes come with an Open button |
| *(retired)* `!ls`, `!search` | none | Turtle finds and reads files with its own tools (`search_practice_files`, `list_practice_files`, `read_practice_file`) |
| *(retired)* `!keep`, `!ignore` | `cmd_keep`, `cmd_ignore` (Turtle's offers run them) | Say it: Turtle offers `keep` or `ignore`. `ignore` takes a second press before anything is removed |
| *(retired)* `!fetch` | `cmd_fetch` (the offer button still runs it) | Typing it answers once: paste the link instead |
| *(retired)* `!date` | none | Typing it answers once: tell Turtle the date; Turtle offers `keep_date`, River draws the confirm |
| `!rename <title>` | `cmd_rename` | Exact eddy title (in thread) |
| *(retired)* `!share` | `cmd_share` (the share button under `...` runs it) | §15.6 — send eddy to another practitioner (digest + received eddy). Typing it answers once. To a person, the sender is not told whether it was read; to a shared room, the sharer is told once |

Paths resolve to `practice_root` from `mage_registry.yaml` — typically `~/workshops/<name>/`, not Magic `desk/`.

---

## Operator tools

For instance operators (`mage_type: mage`). Not shown to hosted practitioners.

| Command | Handler | Purpose |
|---------|---------|---------|
| `!diagnose` | `cmd_diagnose` | Full stack health (canary view) |
| `!admin …` | `cmd_admin` | Host tools — `invite`, `rivers`, `space`, `doctor` (§15.4) |

**Retired from product inventory:** `!signals`, `!drip` — Magic-era outfacing; future public extension will be designed natively for turtleOS, not ported from Magic signal drip.

---

## Appendix A — deferred patterns (not v1)

Old orchestration commands. **Retired 2026-10-14**: typing one answers once with where it went (`help_card.RETIRED`), and the handlers are deleted. The test `test_a_shut_door_has_no_room_behind_it` fails if one comes back.

| Typed | Where it went |
|-------|---------------|
| `!thread`, `!new`, `!panel` | **new eddy** in the channel bar |
| `!thread-type` | The type buttons on an eddy's opening message |
| `!eddy-check` | `!dissolve` in an eddy |
| `!absorb`, `!absorbed`, `!forget` | Turtle carries what matters across eddies (memory agent); `!live` shows what it has in mind |
| `!day` | The daily note refreshes itself |
| `!focus` | Tell Turtle, attach a file, or share an eddy link |
| `!fetch`, `!date` | Paste a link; say a date in words |

Still live and not listed: `!eddy` (alias `!threads`) and `!live`, below.

| Command | Handler | Notes |
|---------|---------|-------|
| `!eddy` (alias `!threads`) | `cmd_eddy` | Open eddies as a card: link, what each last held, when. `!eddy all` adds parked ones |
| `!live` | `cmd_live` | What Turtle has in mind in this channel, with related eddies and what this practice adds. `...` in a channel shows the same card |

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
| **Release** | `!release` | Cleared after checkpoint | Open (unless practitioner dissolves) | checkpoint + release |
| **Dissolve** | `!dissolve` / lifecycle bar | Handler-dependent | Archived in Discord (still readable) | `🍃 dissolved …` (§6.2) |

Do not conflate **release** (session resonance capture + clear dialogue) with **dissolve** (structural eddy lifecycle).

**What “archived” means:** Discord `thread.edit(archived=True)` — the eddy moves to archived threads, stays readable, and is **not deleted**. A file copy may land in `thread-archive/` under practice root; parent river gets a `🍃 dissolved` act. **Close Thread** in Discord's UI triggers the same path (§9.6) — see [docs/ux/discord-native-ui.md](ux/discord-native-ui.md).

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

**Platform flows** — markdown programs in `practice_root/flows/`, loaded via **`!flows`** / **`!flow`** in an eddy (not required for daily use).

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
| Deployed topology | `docs/live-runtime.md` |

When adding or renaming a command: update this file, `cmd_help`, and the seneschal block in `prompts.py` in the same chapter.
