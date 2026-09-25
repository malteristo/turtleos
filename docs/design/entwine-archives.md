# Entwine — exogenous chat archives

**Date:** 2026-09-08
**Spec:** TURTLE_SPEC §6.5 (source-claim honesty), §15.5 (memory boundaries), §3.2.1 (provenance)
**Status:** Design + slices 1–3 (inventory, packet read, distill job). Amends the July Entwine sketch. First instance is a private workshop note, not this file.
**Does not:** name a practitioner, a household, or an export.

---

## What this is

A practitioner may bring a large chat archive from another platform
(ChatGPT export today; others later). turtleOS may form **memory** from
it. Turtle did not have those conversations. The archive is **exogenous
history**, not native dialogue.

This is not a memory-agent skill that learns zip layouts at turn time.
Two jobs stay two jobs.

| Job | Who | Corpus |
|---|---|---|
| **Entwine** | code + an offline capable-model job | the archive |
| **Memory** | existing `memory_agent` / `memory_rebuild.py` | notes the room may read |

`docs/design/agent-as-memory.md` §9 already says the memory agent does
not read raw dialogue. If a note-writer misses a conversation, memory is
thinner, not wrong. Entwine is that note-writer for a foreign archive.

## Why not dump the archive into the prompt

A current OpenAI export is sharded JSON (`conversations-NNN.json`), a
huge `chat.html`, and thousands of binary assets. Conversation count is
in the thousands; messages in the tens of thousands. The local dialogue
heart cannot read that, and should not pretend to.

The July sketch was right about provenance and wrong about the gate:
per-theme confirm does not survive a tired practitioner. Distill, write,
correct later. Delete the derived notes and rebuild — the zip is still
there.

## Shape of a ChatGPT export (mechanism)

Code must parse this, not a prompt.

- Zip. Immutable once hashed into a practice store.
- `conversations-*.json` — list of conversations. Each has `title`,
  `create_time`, `update_time`, `mapping` (node graph), `is_archived`,
  `is_do_not_remember`.
- A mapping node has `message.author.role` (`user` / `assistant`) and
  `message.content.parts`.
- `shared_conversations.json` is a title list, not the corpus.
- `chat.html` and `*.dat` are not the memory corpus.

Inventory is titles, ids, timestamps, message counts, roles. Not bodies
in git. Not bodies in a public design.

## Derived notes, not native eddies

Write one markdown note per **kept** conversation (or per split of a
mixed conversation) under the **destination root**:

```
story/exogenous/chatgpt/<conversation_id>.md
```

Frontmatter must make a lie fail:

- `source: exogenous/chatgpt`
- `conversation_id`, `title`, `created`, `updated`
- `origin_platform`, `origin_agent` (not Turtle)
- `route: health | personal | skip`
- `entwined: YYYY-MM-DD`

Body: the practitioner's words and durable facts, compressed. The other
agent's differentials stay labelled inference or are dropped. This is
not a transcript.

`collect_entries` grows by one directory. Packet excerpts must say the
room did not have this talk: *from an earlier ChatGPT conversation you
imported*, never *we discussed* / *I remember when*.

Native `story/eddies/` stay Discord. Mixing the two would teach the
memory agent that Turtle was in the room.

## Routing is a write, not a retrieve

Memory roots do not search across archives. Entwine **writes** into the
root that may remember.

**Default:** exogenous *personal* history writes only into that
practitioner's **personal** channel. Talk that happens to be about
family, a shared room, or another person still lands in the personal
root. If they want it in a shared room, they query their own river and
share a Discord post or thread link. Entwine never writes family,
partnership, craft, or another person's river.

**Exception — health.** A health channel is one person's isolated health
practice. Body/course/clinician material from *that owner's* archive may
write into *that owner's* health root (and the health board, same bar as
a family-source harvest). This is not a shared-family write. A second
person's health is a second health instance.

| Class | Destination root | Also |
|---|---|---|
| Health (body, course, clinicians, sick leave, meds) | the archive owner's isolated health practice | health board Observed |
| Everything kept that is not health | that practitioner's personal river | memory topics only |
| Skip | nowhere | empty, one-shot toys, export junk, `is_do_not_remember` |

`assert_entwine_route` is the mechanism: `family` / `shared` / `craft`
fail closed. Isolated health stays isolated — health notes are not
merged into the personal index. A mixed conversation is **split**, not
copied whole to both.

Classification is an offline job. The live local model does not open
the zip.

## Dialogue contract (already named in July)

Allowed: "From what you imported from earlier chats…" · "One ChatGPT
thread mentioned…"

Forbidden: implying the conversation happened with Turtle · native
checkpoint voice on exogenous material · "I remember when we…"

A shake must include a false-native-memory case. Empty output is not
evidence it cannot happen.

## What we decided not to do

- Teach the memory agent to parse exports. That is Entwine. Memory
  names topics from notes.
- Load `conversations.json` as a turn tool. Capable tier offline;
  local heart reads notes.
- Per-thread greenlight. Correction after write. The zip remains.
- Living-key rewrite of the archive (one fluent story). That mints an
  unopposed account.
- Vector store beside `memory/`. Delete derived notes + rebuild.

## First slices (platform)

1. **Parser + inventory** — **done 2026-09-09.** `entwine_chatgpt.py` +
   `scripts/entwine_inventory.py`. Hash zip, list conversations, write
   `inventory.json` / `inventory.md`. No note writes. Fixture zip in
   `test_entwine_chatgpt` (bodies cannot leak; shared list is not
   corpus; live modules do not import the parser; git does not track
   an export). Live export stays off git.
2. **`collect_entries` reads `story/exogenous/`** — **done 2026-09-10.**
   Packet labels imported origin. `has_native_we_voice` fails a planted
   "I remember when we" / "we discussed" about a ChatGPT day. Shake
   fixture `fixture-exogenous-chatgpt` carries the same check.
3. **Classifier + distill job** — **done 2026-09-10.**
   `extract_conversation` + `entwine_conversation` +
   `scripts/entwine_distill.py`. Writes `story/exogenous/chatgpt/`.
   Family / shared routes fail. Assistant-only tokens cannot enter the
   note or Observed harvest. `do_not_remember` writes nothing. Mixed
   conversations split. Health Observed harvest is a file under the
   health root (`record/entwine_observed.md`), not a silent board edit.
   v0 is operator-run; `--dry-run` / `--classify-json` / `--limit`.
   The live path still does not open the zip.
4. **Command later** — `!entwine` after the job has a number. v0 is
   operator-run on the Mini.

## Falsifiers

- Turtle answers a health question from labs only while health
  exogenous notes exist and were not on the compact board.
- Turtle says "we talked about this last year" for a ChatGPT day.
- A family or craft packet carries an exogenous note from a personal
  or health root.
- Entwine writes a personal archive into family, partnership, or
  another person's river.
- The live path opens the zip.
