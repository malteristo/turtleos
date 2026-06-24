# Eddy entry and presence

How practitioners enter eddies and what they see before Turtle speaks.

**See also:** [flows-and-intake.md](flows-and-intake.md) · [journeys.md](journeys.md)

---

## Blank eddy entry (default from bar)

**Principle:** Opening an eddy should feel like walking into an empty room — no seed, no Turtle monologue, no config UI.

| Step | What the practitioner sees |
|------|----------------------------|
| Materialize | Thread titled **`new eddy`**; Discord thread card in river |
| First message | They speak first — that message **is** the opening |
| Rename | River harness retitles thread from first message content (`generate_topic`); **`!rename Exact title`** anytime in-eddy for manual override |
| First Turtle reply | `river added turtle` system line, then dialogue |
| **Resume** (return after days) | Same thread — history reloads from disk or Discord; Turtle continues without recap disclaimer |

**Implementation:** `spawn_river_eddy`, `handle_eddy_first_message`, `write_awaiting_title` / `pop_awaiting_title` in `eddy_spawn.py` + `river_handler.py`; `load_thread_history`, `dialogue_store`, `_build_native_runtime_env` in `discord_bot.py`.

**Lifecycle bar (planned):** After first practitioner message, River posts checkpoint/release/dissolve bar at thread bottom — not on empty materialize. See [eddy-lifecycle-bar.md](eddy-lifecycle-bar.md).

---

## Seeded eddy (contextual / legacy)

When materializing **from a practitioner’s river message** (contextual flow button), the thread still opens as `new eddy` until first in-eddy message renames it. Legacy intake/vortex paths may post a seed embed — not the default bar path.

---

## Deferred presence

`Turtle joined` posts **once**, immediately before Turtle’s **first reply** — not at thread creation.

- **Split-bot:** River adds the practitioner at materialize (`river added you`). On first in-eddy message, River adds Turtle (`river added turtle`) — same native Discord system line, no green embed.
- Turtle does not join at thread create; entry is deferred until the practitioner speaks.
- Flow context loads in the Turtle prompt. On first reply in a flow eddy, the shell posts a compact `-#` presence line (e.g. `Navigator · continuing from last time`) — practitioner-facing outcome, not filenames or tool trace. The model must not emit `-# flow:` / `-# read` lines or echo the presence line.

**Implementation:** `ensure_native_presence`, `post_flow_presence_if_needed` in `eddy_spawn.py`; `flow_runner.flow_presence_line`; `conduct.md`.

---

## Discord-native system lines (inventory)

We **prefer Discord’s system lines** over custom “joined” embeds. The shell cannot author arbitrary system-line text — only trigger API actions that Discord renders.

| Event | System line (approx.) | Who triggers |
|-------|----------------------|--------------|
| Materialize eddy | `river added {practitioner}` | River `thread.add_user` at spawn |
| First in-eddy message | `river added turtle` | River `thread.add_user` before Turtle’s first reply |
| First message / flow rename | `river changed the channel name: {title}` | River `thread.edit(name=…)` |
| Practitioner @mention | Orange highlight on left | **Discord client** — not turtleOS |

**Rejected:** green “Turtle joined” embed; fake system-line prose from bots. See [rejected.md](rejected.md).

**Implementation:** `eddy_spawn.py` (`river_add_turtle_to_eddy`, `prepare_flow_eddy_entry`); `river_handler.py` `handle_eddy_first_message`.

**Link-read naming:** River owns eddy titles in split-bot mode — link-read must not rename practitioner- or flow-chosen names. See [link-reading.md](link-reading.md).
