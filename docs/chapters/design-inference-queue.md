# A conversation waits, it never fails

**2026-08-07** · reliability · shipped, deploy pending

## The report

> *"I am getting a lot of these messages currently. Too much load on the server?"*

Forwarded from a river eddy, attached to a Turtle reply that read
`[dialogue error: ReadTimeout: ]`. The Mage's hypothesis was right. The
mechanism was more specific than load.

## What was actually happening

`llama-server` runs with **one slot** — `-np 1`, because `OLLAMA_NUM_PARALLEL`
is unset in the launchd plist. Every request to every local model serializes
there.

A gemma4:31b turn, measured on the Mini's own log:

| | |
|---|---|
| prompt eval | 80.4s / 8,740 tokens (109 tok/s) |
| generation | 92.1s / 1,071 tokens (11.6 tok/s) |
| **one turn** | **~172s** |

The client's read timeout was **300s**. And in a *streaming* httpx request,
`read` measures **the gap between bytes** — not the length of the call. A
request parked in Ollama's queue emits no bytes at all.

So the deadline was a budget on **waiting in line**. Two concurrent
conversations already exceeded it. The family river had five.

Evidence, 2026-08-06 18:00–24:00 — 99 `/api/chat` calls:

- **21** sat at ~5min, the timeout wall
- **9** ran 6–15min
- only **9** finished under a minute
- 19 HTTP 500s in `ollama.log`; 73 `ReadTimeout` lines in `discord.log`

## Two things that were not the problem

**Per-channel serialization already existed.** `dialogue_queue` has serialized
turns per channel since the decomposition, and it worked. The contention was
one level up: four *different* eddies, each correctly serialized on its own,
all arriving at the single slot together. The first version of this fix added a
second per-channel lock — redundant, and it would have deadlocked every eddy
turn, because `continue_dialogue_turn` calls `ensure_channel_bars` from inside
itself and `asyncio.Lock` is not reentrant.

*Check which axis the concurrency is on before adding a queue.*

**The fallback was an amplifier.** On timeout the handler retried with
`REFLECTION_MODEL` — a *different* 17GB model. A congestion failure therefore
bought an eviction and a reload, queued behind the same congested slot. When
that timed out too, the second exception's string went to the practitioner.

## The design

**One gate, at the inference layer.** `llm._InferenceGate` — a semaphore
sized to the server's real slot count (`OLLAMA_MAX_INFLIGHT`, default 1).
The line exists whether or not we form it; forming it makes waits ordered
instead of racing, makes depth visible in the log, and means a queued turn
cannot be timed out for waiting. **Raise it only in step with
`OLLAMA_NUM_PARALLEL`, never ahead of it.**

**No byte-gap deadline on local inference.** `read=None`. Two guards replace
it, and both measure faults rather than load:

- `OLLAMA_STALL_SECONDS` (180) — silence *after* the first token. Once
  generation starts tokens arrive steadily; a long gap mid-sentence is a
  wedged runner.
- `OLLAMA_TURN_CEILING_SECONDS` (1800) — whole-call ceiling, so a wedge
  cannot hold the gate forever. At ~172s/turn that is roughly ten deep: past
  any real conversation, short of never.

**Coalescing in the queue that already exists.** The Mage's ask was exact —
*"deal with them one after the other, while trying to keep the latest state of
the conversation in mind while working off the queue."* The drain now looks
ahead: when more messages are queued for the channel, the handler runs with
`reply=False`. The message is still absorbed in order — history, attachments,
links, activity — and only the generation defers. The last arrival answers,
seeing all of them.

Nothing is dropped. **The replies collapse, not the record.**

**No traceback in a conversation.** The failure path retries the model that is
already resident, once, and otherwise posts Turtle's own line. A practitioner
in the middle of a hard conversation should never be handed an exception class
as an answer.

## The part that mattered more than speed

`sessions.py` caught the same timeout on the **eddy-note write**, printed one
line, and continued — no retry, no surface. Two 2026-08-06 river eddies have
no note on disk. And because `_promote_proposed_themes` is reached *through*
`write_eddy_note`, one timeout lost the room's memory and its alive layer
together — silently, on precisely the densest conversations of the day.

A degraded reply is visible. A dropped record is not.

**Open:** eddy-note retry, and a dropped note counted in the ops report rather
than printed. Not in this slice.

## Ops levers, not code

Independent of the above, and needing an Ollama restart:

1. `OLLAMA_NUM_PARALLEL=2` + raise `OLLAMA_CONTEXT_LENGTH` so slots do not
   starve at 8,192 (prompts run 15–22K chars).
2. `OLLAMA_MAX_LOADED_MODELS=2` — gemma4:31b (19GB) + qwen3.5:4b (3.4GB)
   resident together on a 64GB box kills the reload tax. Three models are in
   rotation; `desk/turtle_env.md` lists only two and names one that is not
   installed.

## Verification

933 unit tests green. **Living verify owed after deploy:** three messages sent
into one eddy during a reply produce one answer carrying all three, and four
concurrent eddies produce no `ReadTimeout`.
