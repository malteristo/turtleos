# Procedures and doors — flows, skills, `!` and `.`

**Date:** 2026-10-14
**Status:** Stance, for him to react to. Nothing here is built.
**Spec:** TURTLE_SPEC §10 (Flows and the Execution Layer), §12 (River act catalog).
**Companions:** [curated-surfaces-v1](curated-surfaces-v1.md), [names-audit](names-audit.md).

## 1. What exists today

- **A flow** is one markdown file, optionally with front matter (`title`, `reads`, `writes`, `intake`, `think_aloud`, `model`). It is loaded into Turtle's prompt. It is not three prompts: River has its own single prompt and runs no flows, and so does the memory agent. Flows live in `practice_root/flows/`; the shipped ones are copied there at install. Someone writes the file; the product has no authoring surface. Unknown front-matter keys are ignored (TURTLE_SPEC §10.3).
- **A skill or procedure** is a markdown file in the repo's `skills/` and `procedures/`, with `summary` and `when` front matter. Turtle lists and reads them with `list_turtle_capabilities`. This is already close to the agent-skill convention (`name`, `description`).
- **A person starts a flow** with `!flows`, a picker. There is no `!<flowname>`.
- **A `!` command** is either an act the system does (`!release`, `!dissolve`, `!model`) or a convenience that duplicates something Turtle can do. The rule since 2026-10-14: a command exists only for what the system does not do natively.

## 2. Position

Flows and skills are one thing in two folders. The difference is who reaches for it, not what it is.

**One library, one format, three doors:**

| Door | Who | How | Example |
|------|-----|-----|---------|
| `.` and `. <toward>` | Turtle, from shared context | Turtle reads the library and picks | "Go on" in an eddy about a plan reaches the planning procedure |
| `!<name>` | The person, when the same procedure is wanted every time | Typed, or a button | `!navigator`, `!fresh-eyes` |
| A button | River, when a moment calls for an act | River offers | Checkpoint, Share, Keep this eddy |

- **`.` is the product.** It means: do the right thing from a demonstrated understanding of what we share. A command is the fallback for when exactness matters more than inference. Anything a person has to restate every time is a gap in `.`, not a feature.
- **`!<name>` is a ritual door.** Some procedures are ritual: repeated, named, wanted the same each time. Those earn a `!name`. The `!` card then has two kinds of rows: system acts and library rituals.
- **Compatibility.** Adopt the agent-skill format for the library: `name` and `description` required, our existing keys (`reads`, `writes`, `intake`, `think_aloud`, `model`) as extensions, plus one new key, `invoke: person | turtle | both`. A flow is a skill with `invoke: person` or `both`. A skill Turtle keeps for itself is `invoke: turtle`. Existing flows keep working because unknown keys are ignored.
- **River does not run procedures.** River executes acts with buttons. It would not carry a prompt per procedure; the small model stays a classifier and executor.
- **Who creates them.** The practitioner or Spirit writes a file under `practice_root/flows/`. Turtle may propose one after a pattern recurs, but a proposal is a draft a person accepts; nothing writes into the library unasked.
- **Base attunement stays small.** What belongs in the base prompt is what is true in every eddy: honesty, presence, the acts Turtle can offer. What is a procedure (a sequence with a purpose) belongs in the library, not the base.

## 3. What this does not decide

- Whether `!flows` goes. Probably yes once `!<name>` exists, but a picker is how a person discovers what is there, so it moves into the `!` card first.
- Whether every system act (`!release`) is also a library entry. Acts need handlers; procedures do not. They stay two kinds behind one door.
- Anything about the Magic workshop's own skills; those are authored there.

## 4. Enforcement owed if built

- A test that every shipped procedure has `name`, `description` and a valid `invoke`.
- A test that `!<name>` resolves only to an `invoke: person|both` entry, never to a Turtle-only one (positive control: a Turtle-only entry is refused).
- A scan that the `!` card lists exactly the ritual entries and the system acts, so the card cannot drift from the library.
