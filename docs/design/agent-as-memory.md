# Agent as memory — what a room keeps returning to

**Date:** 2026-09-03
**Spec reference:** TURTLE_SPEC §15.5 (boundaries), §3.2 (packet), §6.5 (source-claim honesty)
**Status:** Built; deploy pending a quiet window. Amends `what-a-shared-room-remembers.md` §9.
**Code:** `memory_agent.py`, `continuity_engine.render_substrate_packet`, `dialogue_turn.local_memory_tools`, `background.memory_loop`, `scripts/shake_memory.py`

---

## 1. The finding

A member of a shared room asked Turtle what it remembered about a topic the
room had returned to in 30 checkpoint notes over five weeks. Turtle answered
that there was no detailed archive.

Every note existed. Room memory (`what-a-shared-room-remembers.md` §4) reads
the last 7 days, 5 notes; the newest note on the topic was 7.5 days old. The
window did exactly what it was designed to do. It was the only reader.

The local model on that path had no tool loop, so it could not look — and it
said "I am checking the history" anyway.

Two defects, one class each: **a window where recurrence was meant**, and
**narration unbound from action**. Neither was a crash.

## 2. The stance: memory as a byproduct of practice

The room writes its memory already — every checkpoint leaves a dated,
attributed note. The **memory agent** is a curation role over those notes,
not a store beside them: it reads all of a room's notes, forms the topics
the room keeps returning to, and writes them as readable markdown under
`memory/`. Nothing there is ground truth; the notes are. Delete `memory/`
and rebuild it and you get the same answer:

```bash
python3 scripts/memory_rebuild.py ~/workshops/<room> --rebuild
```

No vector database. No embeddings. A turn reads markdown; a model that
cannot read what it cannot see is not helped by being smarter.

## 3. Formation

| Step | Who | Why |
|---|---|---|
| Collect every entry from `story/eddies/*.md` and kept `story/exogenous/**/*.md` (all time) | code | the corpus is the notes; Entwine writes the foreign ones; the window was the defect |
| **Name** the topics, with a one-line summary and 3–8 keywords | reflection model | 118 entries carried 281 distinct theme labels — the note-writer phrases every theme afresh, so label clustering is noise; naming needs a reader |
| **Assign** notes to topics by reading them for the keywords | code | the model listed 4 conversations for a topic the notes mention 30 times; recall must not depend on how many ids it felt like writing |
| Drop invented ids; drop topics from a single conversation unless recent | code | what the model says exists must exist |
| **Heat** = Σ 0.5^(age / 21 days) over a topic's entries | code | 40 conversations stay hot for a month after the last; one mention cools in three weeks — recurrence, not recency |
| Write `memory/topics.yaml` + `memory/topics.md` + `memory/topics/<id>.md` | code | machine view for the packet; readable pages for members and for the tools |

Formation names are read by **every member** of a shared room. The model is
told to name what a topic is about, never a verdict on a person. The first
run, before that instruction, named a topic after one member's failing; the
private eval scenarios are where this is checked, because it cannot be
checked with a regex.

A **keyword** formation path (salient words shared across conversations)
exists as the fallback when the model yields nothing and as the positive
control the model path is measured against. On real notes it is poor; on
the synthetic fixture it is what the tests run.

## 4. Retrieval

**Passive.** The substrate packet carries, every turn: the three hottest
topics, plus up to two the current message reaches for (keyword overlap
with label, summary, keywords, titles, excerpts), each with two dated,
attributed excerpts. The current eddy's own entries are excluded; an
excerpt is shown once even when its entry belongs to several topics.
Budget ~3.2 KB. The recency block stays as it was — *what has been said
lately* and *what this room keeps returning to* are different questions,
and each block says honestly when it has nothing.

**Active.** Where a room's memory has been built, the local model gets the
read-only pair — `search_practice_files`, `read_practice_file` — with a
**two-round cap**: one to look, one to answer. Rooms without a built memory
keep the plain call. `LOCAL_MEMORY_TOOLS=0` switches the loop off. The
packet's conduct line binds words to action: *do not say you checked or
searched unless you actually used a tool this turn.*

**Mediated** and **conversational** modes (the Hearth spec, 2026-09-03) are
deferred until active has a number.

## 5. Keeping it current

Currency is a state, drift is a rate. No checkpoint is asked to remember
to rebuild. `background.memory_loop` runs hourly and asks two questions per
registered root: are the notes newer than what the memory read
(`notes_newest_ts`), and is anyone talking (`dialogue/*.json` mtimes, the
deploy guard's own signal, 10 minutes). Yes and no → rebuild. A model-formed
rebuild holds the inference gate for minutes; a member waiting on a reply
must never pay for it.

## 6. Boundary — asymmetric by design

`memory_roots_for(root)` is the one place the rule lives:

| Root | Forms memory from |
|---|---|
| shared room | its own notes only |
| personal root | its own notes **and** the shared rooms whose member list names its practitioner, except spaces marked `memory: isolated` |
| isolated space | its own notes only — membership does not merge it into a personal root (health is the first) |
| any root | never another personal root |
| unregistered root | itself; registry failure fails closed |

A member remembers the rooms they are in. A room does not remember its
members' private conversations unless a member brings one in (link, share
eddy). Cross-root *active* reading is not built; passive carry of a shared
room's topics into a member's private memory is, and the excerpt says
which room it came from.

A **craft** surface reads that same personal index and must not remember
the shared rooms. That cut is render-time (`exclude_shared_rooms` on the
topic block), keyed by `uses_craft_surface`. `memory_roots_for` is not
the place: the merge is correct for the private river. Family space is
already `own_root` at build.

This amends `what-a-shared-room-remembers.md` §9 in two places: *not
permanent* becomes *derived* — standing, but unable to drift from its
source because it is rebuilt from it; *not cross-root* becomes *one
direction only*. "Nothing retrieved becomes state" still holds for turns:
the memory agent writes state, a turn only reads. TURTLE_SPEC §15.5 does not
yet say the asymmetry in so many words; that sentence is the operator's to
sanction.

## 7. Evaluation

`scripts/shake_memory.py` replays a scenario offline against a real root
with the room's own model and the packet a turn would build. Four checks:

- `packet_contains_any` — the passive layer carried the topic
- `reply_mentions_any` — the reply drew on it
- `reply_must_not` — none of the failure's own words
- `no_false_check` — no "I checked / looked / searched" unless a tool ran
- `no_native_we` — no "we discussed" / "I remember when we" on imported history
- `planted_native_we_fails` — the detector must fire on a planted lie (empty output is not coverage)

`--fixture` runs a synthetic room (a topic older than the recency window)
as the positive control; it passed with the live local model on the Mini
on 2026-09-03 with no tool used and the reply ending "that's what I hold
in my notes; I haven't looked further." Scenarios that name real people and
rooms live in the operator's private workshop, never here.

A PASS is necessary, not sufficient. Read the reply as the member would.

## 8. What would falsify this

- A topic with recurrence across weeks that never reaches the packet when
  asked about → heat or selection is wrong; the replay harness is where it
  shows.
- Turtle reciting topic headers unprompted in casual turns → the conduct
  line is not enough; narrow `TOPIC_BLOCK_TOP_N` or gate on message match.
- A member reading a topic name as a judgement of them → formation naming
  needs a mechanism, not an instruction.
- Reply latency on the local path rising by more than one model call →
  the cap is not holding or the tools are being called on casual turns.

## 9. What this does not do

- Does not read raw dialogue histories; the notes are the corpus. If the
  note-writer misses a conversation, the memory is thinner, not wrong.
- Does not synthesise topic summaries beyond one model sentence; the
  excerpts are the notes' own words.
- Does not retire `state/alive.yaml` — it keeps being written for the
  relation gate and the intention offer. Retire once topic memory has a
  month of numbers.
- Does not let a shared room grep a member's private root, ever.
- Does not parse a ChatGPT export. Entwine writes notes; this module
  reads notes. Imported excerpts are labelled as imported.
