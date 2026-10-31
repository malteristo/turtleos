# The curated command set, its surfaces, and the guidelines that grow with them

**Date:** 2026-10-14
**Status:** Slice 1 deployed 2026-10-14 (`6f30c78`); slices 2 and 3 deployed (`c424ba0`). Built after: the channel menu he keeps, and the retirement of `!fetch` and `!date` (below). Slice 4 is sanctioned and not built. Gate for slices 2 and 3: he types `!eddy` and `!live` and presses `...` in a channel, cold, in more than one channel.
**Spec:** TURTLE_SPEC §5.3 (the standing bar, amended on the `more` line), §5.5 (the `!` palette).
**Language:** [design-language.md](../ux/design-language.md), including the new §8 (modalities and cognitive ergonomics). Fourth surface on it, after [mcp-list-v2](mcp-list-v2.md) and [model-card-v2](model-card-v2.md).

## The gap it closes

The house had about 35 `!` commands and no way for a person to see which were worth reaching for. `!help` was an embed that listed models and a hand-kept inventory. The menu under "new eddy" offered `artifacts` and `help`, and the operator had never used either. A bare `!` did nothing. The two surfaces he does use (`!mcp`, `!model`) were reachable only by typing, and `!mcp` took two steps.

## Press release

You type `!` and one card tells you what you can type, in groups: what to do with an eddy, what to look at or keep, what the house itself offers. Each line says what the command is for. The menu under "new eddy" now opens your connections and this channel's model, each in one step, each only for you. The guidelines that make these cards look like one product now say what each way the house speaks (text, card, and later voice) is for, and what a head can hold.

## What he sees

```
## What you can type here
-# A command happens at once. The model is not asked.
▌ ### Eddies
▌ **!checkpoint**  Save where we are and keep going
▌ **!release**  Close the session: save, then start clean
▌ ...
▌ ### Look and keep
▌ **!context**  What Turtle read to answer you
▌ ...
▌ ### The house
▌ **!status**  How the house is doing
▌ **!model**  Choose who answers in this channel
▌ **!**  This list
-# A few older commands (like !threads) still work and are not listed.
```

Under "new eddy", `more…` offers `mcp` and `model`. Choosing one opens that card in the channel for you alone.

## Criteria (what makes it pass)

1. `!` and `!help` answer with the same card, in his language: three groups of at most seven lines, each saying what the command is for.
2. Every command on the card exists, and every command a member can run is either on the card or named as deliberately unlisted. A command that is neither fails a test.
3. The menu opens `!mcp` and `!model` privately in one press. A bar posted before this change, whose menu still offers `artifacts` and `help`, answers a press with one sentence instead of failing.
4. He does not have to ask what a line means.
5. The design language names who carries what (text, card, voice, visual companion), and a modality cannot be added or dropped without that section changing (a test says so).

Abandon line: if he never types `!` and the card is not what he opens when he forgets a command, the list is still the wrong shape and the dropdown is where help belongs.

## The board (what he sanctioned, in order)

| Slice | What | State |
|---|---|---|
| 1 | The curated list as a card (`!`, `!help`); the menu holds `mcp` and `model`; guidelines §8; the kit's heading, item-line and timestamp checks; the modality test | **Deployed 2026-10-14** |
| 2 | `!eddy`: his latest active eddies, each with a line saying what it is about and a link (replaces `!threads`, which is listed nowhere now). `...` in a channel becomes the same card (see below) | **Built 2026-10-14**; `!threads` and the spoken "show me threads" now draw the same card |
| 3 | `!live`: what Turtle has in mind in this channel, with the eddies behind each topic and what this practice adds (see "A command is a pattern, a practice implements it"). Read from topic memory, not from the older alive layer. `!focus` does not fold in; it is unlisted | **Built 2026-10-14** |
| 4 (after the menu) | The commands people do use, as cards in order of use: `!share`, `!checkpoint`, `!status`, `!context` (`!focus` dropped, see below) | Sanctioned, not built |
| 5 | The eddy's standing bar leaves; `?` shows its acts and the gestures (`.`, `...`, `!`) on request | Sanctioned, not built; see "What the survey changed" |

### What he said that changed the board

- **No separate home screen.** `...` in an eddy already does that job (Turtle names where the conversation is and one next move; River shows the acts; Memory shows related memory: [the `...` PR-FAQ](../pr-faq/instances/ellipsis-shows-what-this-eddy-can-do.md)). In a channel, `...` posts only plain text that lists the channel's eddies by creation order, not by activity. So the home screen is that gesture one level up: `...` in a channel becomes a card of recent active eddies (with links), what is still moving, and what waits on him. One gesture, at every level: *where am I*.
- **The continuity engine is not what `!live` reads.** It still runs: its alive layer feeds the relation gate and the intention offer, and `!focus` reads it. But retrieval moved to topic memory (`docs/design/agent-as-memory.md`, which left the alive file in place "until topic memory has a month of numbers"; that month has passed). `!live` reads the memory agent's topics. Retiring the alive layer is its own decision and is filed, not done here.
- **`!focus` is dropped, not folded.** In his words: focusing is something agents do naturally; he tells Turtle, attaches a file or an eddy link, or asks. An extra pointer is not needed. It is unlisted now (`LISTED_ELSEWHERE`, with that reason); its code and the continuity-engine scope go in the retirement chapter (issue 056). `!day` is unlisted for a smaller reason: it leaves one trace and the daily note refreshes itself.
- **`!live` is the same pattern in every channel and a different answer in each.** In craft it shows what Turtle has in mind there, the eddies those topics came from, and whose move each waiting eddy is. In the private river it adds the dates coming in two weeks. In a shared, partnership or team room it shows topics only. In health it shows the shape (a count, a time) and none of the words. The pattern is declared per kind of channel (`practice_views.LIVE_EXTRAS` and `NO_LIVE_EXTRAS`) and a test fails when a kind of channel has no decision.
- **Eva notes** were folded into the workshop design last session; nothing is owed here.

## The shape

- **Kit:** `Item(name, line)` for a list that has no state to show (a dot beside each command would say nothing), at most 80 characters of "what it is for". `build()` refuses a surface that does not say what it is before its first card.
- **`help_card.py`:** the curated set (`GROUPS`, `OPERATOR`) and the deliberately unlisted (`LISTED_ELSEWHERE`, each with a reason). A test compares them with `DIRECT_COMMANDS` and the member allowlist, both ways.
- **The menu:** `RiverEddyBarView` offers `mcp` and `model`. Both call the same functions the buttons and typed commands call (`outgoing_connect_ui.open_list`, `room_models.open_private`), so there is one card each, not a copy. The custom id of the menu is unchanged, so the bar already in a channel keeps working until the next time it is posted.
- **A bare `!`:** `try_direct_command` reads it as `!help`.
- **Removed:** `_river_help_body` and `_help_embed_fields` (the hand-kept inventory that listed models), the bar's `artifacts` and `help` paths.

## What the survey found that the sanction did not know

- **Retiring is entangled.** `prompts.py` tells Turtle to advertise `!artifacts`, `!read`, `!ls` and `!search`; `eddy_spawn.py` falls back to `!new`; several handlers are called from other modules. Unregistering a command and deleting it are different changes. Slice 1 therefore does **not** retire anything: it stops listing. The deletion list (measured: no trace of `!ls`, `!search`, `!export`, `!panel`, `!thread-type`, `!eddy-check`, `!absorb`, `!thread`, `!new` in the act digests on the Mini; `!artifacts` 3, `!read` 2) waits for the prompt and fallback edits that go with it. *Decided not to yet*, not *never got to*: the list is `LISTED_ELSEWHERE`, and the test fails when an entry's command is gone.
- **The `?` is not free.** `...` in an eddy already shows the bar's acts as buttons. A `?` that also shows them would be the same thing under another key. It is useful if it adds what `...` does not: the gestures and what each does here. Sliced last for that reason; he decides after using `!` and `...`.
- **An unknown command is silent.** A message that starts with `!` and is not a command is swallowed by River and ignored by Turtle. Not changed here: both bots can reach the dispatcher and a pointer reply from each would double. Filed as issue 055; the retirements and the alive layer as issue 056 (`issues/` is local).

## Built 2026-10-14: the menu he keeps, and the first two retirements

**The menu.** He will not memorise commands; he will type `!` a lot at first. The `!` list ends with a button, "Choose what's in the menu", that opens a private checklist of the commands a channel can keep (`!eddy`, `!live`, `!dates`, `!status`, `!readiness`): each is in or out, and one menu flips it. The channel bar's menu then offers `commands` (this list, only for you), what the channel keeps, `mcp` and `model`. Choosing a kept command runs it. The choice belongs to the channel (the bar is one message everyone there sees; a shared room is told so). Pins that follow a person across channels are not built: the bar cannot differ per person. Commands that act on an eddy or take words are not keepable, and a test says so.

**`!fetch` and `!date` are retired.** Typing either answers once, in his language, with where it went. What replaced them:
- *Links.* A pasted link is always read, with any amount of writing around it (the first three in a message; the rest get one offer). Saving to the library is an offer button after Turtle replies; the act behind it is unchanged.
- *Dates.* The regex capture was switched off (decided 2026-09-15), so `!date` was the only way a date was kept. Now Turtle reads the date in his words (any phrasing, any language), offers `keep_date` through the same channel it uses for checkpoint and save, and River draws the confirm button with weekday and month. Kept dates for the next year are in every turn, so "when is Anna's birthday?" is answered.
- Retirement means answered, not silent: the typed door answers; the act that a button runs stays.

Abandon line: if Turtle misses dates he says in words (he has to say it twice or reach for a command), the native path is still thin; the first fix is Turtle's reading, not a command.

## What a `!` command is for (his rule, 2026-10-14)

A command exists only for what the system does not do natively. He pastes links and asks about dates in words, so `!fetch <url>` and `!date <when> <what>` are off the card now and are to be retired once the native paths cover them (issue 056, "The rule"). The card's commands are acts (they change the structure of the house or an eddy: checkpoint, release, dissolve, share, model) or looks the model cannot be asked for (what Turtle read, what is live). The test for a new line on the card is the question: *could he just say this?*

## A command is a pattern, a practice implements it

His purpose for the `!` commands: a useful pattern, applied to different practices in the way each needs. So a command is not one function with one output.

- **The pattern** is the shape a person learns once (`!live`: *what is moving here*; `...`: *where am I*).
- **The practice** decides what that means in its channel. The table in `practice_views.py` holds one decision per kind of channel in `channel_primitives`: an extra card, or a stated reason for none. A test fails when a kind of channel is in neither table, in both, or gone.
- **The promise is checked.** The card that says "Turtle has these in mind" is the exact selection the passive per-turn block carries (`memory_agent.live_topics` returns it; a test compares it with `render_topic_memory_block`), so what he sees is what answers him. The second card ("Comes up when you mention it") is the rest.
- **Sensitive rooms show shape, not words.** Topics read "Topic 1" with a count and a time. Controls: show labels in a sensitive room, narrow the carried set, drop a kind of channel from the tables: each fails a named test.
- **Analytics are thin in v1:** eddy counts by state, who holds the next move (craft), dates (private). He says what he wants measured per practice; this is where it goes.

## Findings on the way

- The spoken "show me threads" already had its own embed; it and `!threads` now draw the card `!eddy` draws. About 150 lines of the old embed renderers (`eddy_five_state.group_lines_by_five_state` and the fitters, `river_display.compose_thread_glance_body`, `threads_title`) had no reader left and were removed with their tests.
- The layering ratchet (`tests/test_import_graph.py`) refused the first shape: a drawing module that imported `mage` grew the largest cycle from 50 to 51. So `practice_views.py` imports nothing from the runtime and `cmd_threads.py`, which already did, holds the glue.

## Built 2026-10-14 (third pass): ten more commands retired

His "yes" to retiring the commands that were already unlisted. Typing one answers once, in his language, with where it went; the handler is deleted (only `!fetch` keeps one, for the Save button).

| Typed | Where it went | Measured |
|-------|---------------|----------|
| `!thread`, `!new`, `!panel` | **new eddy** in the bar | no typed use since June |
| `!thread-type` | the type buttons on an eddy's opening message | none |
| `!eddy-check` | `!dissolve` (it had answered "retired" for months) | none |
| `!absorb`, `!absorbed`, `!forget` | memory agent; `!live` | none |
| `!day` | the daily note refreshes itself (scheduled evening plus morning catch-up) | 2 |
| `!focus` | tell Turtle, attach a file, share a link | 7, all in testing |

Kept, still unlisted: the browse family (`!artifacts`, `!export`, `!read`, `!ls`, `!search`: used 4-20 times a month, and the daily note's "Open note" button runs `!read`; Turtle has no native shelf view), `!keep`/`!ignore`, and the two aliases `!threads` and `!flow`.

Guards added: a table-wide test that every retired command answers once in both languages, a test that no retired command still has a handler (positive control: it sees one planted), and a prompt scan that no retired command is advertised (it spares `[Act: !fetch]`, the digest tag for an act that still runs).

The scan paid for itself on the way: the "Thread Orchestration (Appendix A)" paragraph in the prompt told Turtle to advertise `!thread`, `!absorb` and `!forget`; the "older commands" line of the card itself named `!thread`; two fallback messages said "use `!thread`" and "use `!new`". All rewritten.

Left standing on purpose, and filed (issue 056): `state.absorbed_contexts` and its reader in `dialogue_turn`, the `absorbed_threads` slot in `turn_packet`/`turn_trace`, and the continuity-engine scope that `!focus` wrote. Nothing writes them now. They go with the alive layer so the turn packet is changed once.

## Built 2026-10-14 (fourth pass): the browse family, keep and ignore, share

His reasoning: the browse commands are harness tools, not something a person should memorise. Nothing here is typed any more; the typed doors answer once.

| Typed | What replaced it | Handler |
|-------|------------------|---------|
| `!ls`, `!search` | Turtle's own file tools | deleted |
| `!read`, `!artifacts`, `!export` | Ask Turtle; Open, Browse and Download buttons | stays (the buttons run it) |
| `!keep`, `!ignore` | Say it; Turtle offers `keep` or `ignore` (`act_offer_signal`), River draws the button. `ignore` asks again on a second button before anything is removed | stays (the offers run it) |
| `!share` | The share button under `...` (a picker of members and shared rooms, one preview) | stays (the button runs it) |

- **Share is silent for the sender.** A share to a person leaves a note in their home channel; the sender is not told whether it was read or answered. A share to a shared room still tells the sharer once. (Correction to the earlier board: the recipient already saw a digest, with the full conversation loaded for Turtle; it was not the transcript.)
- **The text that told people to type was rewritten**: the shelf listing, the post-checkpoint hint, search results, the link failure embed, the share expiry messages. A source scan (`NoRetiredNameIsSpokenTests`) fails if prose names a retired command in backticks; button payloads and docstrings are exempt.
- **Found on the way:** `!artifacts --all` (the operator catalog) was only reachable by typing, so it is now unreachable. Its code stays until the next pass.
- **Not done, and why:** `!checkpoint`, `!status` and `!context` wait for his answer; `!export` to an external connection has no native path yet.

Two stance documents came with this pass, both drafts for him to react to: [names-audit](names-audit.md) and [procedures-and-doors](procedures-and-doors.md).

## Built 2026-10-14 (fifth pass): checkpoint, status, context

- **`!checkpoint`** is retired as a typed command. The checkpoint button under `...` and Turtle's own offer run the same handler, and the 15-minute idle checkpoint still runs on its own. A press stays a significance signal (TURTLE_SPEC §8.4), which is why it is not fired automatically on `.` or `...`: that would cost a model call each time someone says "go on", and a glance would start writing.
- **`!status` and `!context`** moved to the operator group of the `!` card and left the member list. `!status` is no longer pinnable in a channel's menu (a pin is for everyone in the channel). `!context` stays because it shows what the house injected from a file the turn wrote, not Turtle's own account of it.
- The card's footnote named `!artifacts` after that command was retired. A claim that decays: the card test now fails if the footnote names a retired command.
