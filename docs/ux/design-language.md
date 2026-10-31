# The turtleOS design language

**Status:** v0, 2026-10-13. Sanctioned and built with its first application, [mcp-list-v2](../design/mcp-list-v2.md). Applied the same day to the home-channel connection card and `!model` ([model-card-v2](../design/model-card-v2.md)). 2026-10-14: `!` and `!help` ([curated-surfaces-v1](../design/curated-surfaces-v1.md)), and §8 (modalities and cognitive ergonomics), written with him after he asked that the guidelines grow with every modality the house adds. Same day: **trace** (the live action list in a magic session). Code: `ui_kit.py`, `turn_trace.py`. Checks: `tests/test_ui_language.py`, `tests/test_workshop_tools.py`, `tests/test_magic_room.py`.
**Extends:** [principles.md](principles.md) (why), [system-state.md](system-state.md) (glance), [generative-ui-e1-experience.md](generative-ui-e1-experience.md) (what dogfood taught).
**Law:** unchanged. This is how the surfaces should feel, not a spec amendment.

The interface of turtleOS is what Discord can render: text, cards, rows, buttons, menus, emoji, colour. Every surface the house composes for a person is generative UI, even when a rule and not a model chose it. That will only grow. A language is what keeps ten surfaces feeling like one product, and what lets a model compose a surface later without being trusted with layout.

---

## 1. The parts Discord gives us

| Part | What it is good for | Limits that shape design |
|------|--------------------|--------------------------|
| **Text** (markdown) | Headings `#`/`##`/`###`, quiet line `-#`, bold, quotes, lists, links. | No columns. Code-block tables do not wrap (a wide row breaks on a phone). |
| **Relative time** `<t:unix:R>` | "3 hours ago", localised, and still true an hour later. | Needs a timestamp, not a computed string. |
| **Embed** (legacy card) | Colour bar, title, fields, footer. Fine for a single read-only card. | Fields are not rows. A button cannot sit beside a field. |
| **Layout card** (Container, Section, Separator, TextDisplay) | A card with an accent colour, and rows of **text on the left, one button on the right**. This is the only part that puts a control on the thing it controls. | A message is either layout or text/embeds, never both. About 40 parts in all. New to this codebase. |
| **Buttons** | One act each. Five styles (blurple, grey, green, red, link). Label up to 80 characters, one emoji. | Five to a row, five rows. Buttons on a private reply stop working after a restart. |
| **Select** | Choosing one of 5-25. | One per row. |
| **Modal** | Typing. It is not channel history, so it is where text a person types could live. | Not for secrets here: a key is still never typed into Discord. |
| **Private reply** | Personal state that the room should not see. | Cannot be a typed `!` command's direct reply; it comes from a button or a slash command. |
| **Thread card, reaction** | Discord renders them. We use them as they are ([principles](principles.md#prefer-discord-native-surfaces)). | Do not rebuild. |

## 2. Grammar: what makes a surface explain itself

A person should be able to use a surface cold, once, with nobody telling them how. Eight rules.

1. **Say what you are looking at, in their words, then what they can do.** A heading, then one quiet line. "Who can read your context" with "Open what a program may see. Close it and it stops seeing it." The heading is never an internal noun (grant, profile, source, connection).
2. **State is shown once, on the thing it belongs to.** One row per thing: name, state, and the control that changes it, on the same line. Never a state list above and a button strip below that the eye has to join.
3. **A button says what will happen.** A verb and the thing, in a few words: *Close*, *Pause X*, *End connection*. Never *Toggle*, never an id, never the state it is already in.
4. **The press is its own receipt.** The message changes in place to show the new state. A new message is only for something that left the house (a receipt).
5. **Red means it cannot be undone from here.** It is the only red. It sits alone, last in its group. It asks once, in a sentence that names the consequence, and the safe choice is a named button (*Keep*), not a cancel.
6. **Consequences, not mechanisms.** "Cursor can read these notes" and not "open". "It stops reading at once and has to be connected again" and not "revoked".
7. **An empty state says how it fills.** Not "nothing". "Nothing is connected. To connect a program, ..."
8. **Explain once, near the thing.** Short quiet lines on the row. Longer help sits behind a *What is this?* button that answers privately. A tutorial is never repeated after the second use (E1 dogfood, rule 5).

Two more are inherited and still hold: **a glance, not an inventory** (about seven rows, empties collapsed, counts complete) and **private by default** for anything personal.

## 3. Vocabulary

**Colour is meaning, one per card.** Neutral blue: information. Green: done. Amber: waits on you. Red: broken or destructive. Never decoration.

**Emoji are interface, not decoration.** They are a closed set, always beside a word (colour and glyph alone fail some readers), at most one at the start of a row, and the same glyph means the same thing everywhere.

| Glyph | Means | Used for |
|-------|-------|----------|
| 🟢 | on, ready, open | a thing that is working or visible |
| ⚪ | off, closed, paused by you | a thing that is deliberately not on |
| 🟡 | needs you | waits on a choice or a check |
| 🔴 | broken | not answering |
| 📝 🩺 🧭 | notes, health picture, practice | **kind**, only where rows differ by kind |
| ⏸ ▶ | pause, resume | the act |

`system-state.md` rejects type emoji on `!threads`. That is consistent: there the rows differ by state, so state is the glyph. Here the rows differ by kind, so kind is the glyph and state is the dot. A surface uses at most one of the two as the row's first glyph.

**Words.** The person's words: *notes*, *health picture*, *practice*, *program*, *service*. The Mage's own names for their things, never ours. Programs are named as a person says them (*Cursor*), not by what the client calls itself (`cursor-vscode`). Every string is a locale entry, English and German, and layout does not change by language.

## 4. The kit, and why it is also the safety layer

A surface is built from a few blocks, not from raw Discord calls:

**Header** (what you are looking at) · **Card** (rows, a menu, safe acts, one red act last, an accent) · **Row** (name, state, one act) · **Item** (a name and what it is for, on one line, where there is no state to show) · **Pick** (one menu with its choices, that changes the thing the card is about) · **Note** · **Act** (a button that says what happens; red ones must ask or confirm). The in-place change is the receipt, and the Ask is a card whose last act is the red one, with the safe choice (*Keep*) before it.

This is the one structural bet. When a model composes a surface, it emits blocks from this set with their fields, and the kit, which already knows the grammar, refuses what breaks it. The model never picks a colour, writes a label past the limit, or places red anywhere but last. Controlled generative UI stays controlled as it grows: **the kit is the schema, the grammar is the validator.**

## 5. What enforces it (so it is not only prose)

A rule here that nothing checks is a declaration, and it will stop being true silently. `tests/test_ui_language.py` checks all of these, and each has a surface that breaks the rule on purpose, which the check must catch (and a mutation that removes the guard and must fail the suite):

- **At construction** (`ui_kit.py` refuses): a menu with no sentence, no choices, more than 25, a duplicate value or two current ones; a red act that does not ask, red on a row or not last, a label past a few words, a state glyph without its word or outside the vocabulary, an unknown accent or kind, more than seven rows in a card, more parts than Discord allows.
- **On what was rendered** (`ui_kit.violations`): an id-shaped string or a named internal thing in anything readable, an emoji outside the vocabulary or standing without a word, a code block in something a person reads, red that is not last in its card, the part budget. The kit's count of parts equals the library's own.
- **Also at construction and on what was rendered (2026-10-14):** an item's line past 80 characters; a raw clock reading (`2026-10-14 09:28`) where relative time (`<t:…:R>`) belongs.
- **Across the house:** every modality has a section in §8, and every section is a modality (`ui_kit.MODALITIES`, `PLANNED_MODALITIES`); only `ui_kit.py` touches the layout parts; every string exists in English and German; every glyph in the table above is in the kit and the other way round; a new embed surface fails until it is built with the kit or added to `LEGACY_EMBED_SURFACES` with its reason.
- **Real surfaces:** the `!mcp` list, the home-channel card and `!model` are rendered in every state they can be in, in both languages, and must come back clean (`tests/test_ui_language.py`, `tests/test_mcp_list.py`, `tests/test_model_card.py`). The checks read into menus as well as text and buttons.

`LEGACY_EMBED_SURFACES` is the exemption list, in the shape of `tests/test_transport_boundary.py` (`ADAPTER_EXEMPT`): *decided not to yet*, not *never got to*. The 28 surfaces on it predate the language. A file leaves the list when it is next changed for another reason, and the test fails if one stays on it after it stops building an embed.

What it does not check, on purpose: whether the words are good. That is the one criterion only he can run, once, cold.

## 6. What this is not

- **Not LLM-chosen layout.** Rules pick the blocks today. Later a model may choose among blocks; it never chooses pixels.
- **Not a rebuild of what Discord already renders** ([rejected.md](rejected.md): custom thread cards).
- **Not a reason to touch working surfaces.** Embeds stay until a surface is next changed for another reason.
- **Not decoration.** If a glyph or colour could be removed with no loss of meaning, remove it.

## 7. Review

Add to [review-checklist.md](review-checklist.md): *15. Language: does this surface follow design-language.md, or is it on the exemption list with a reason?*

## 8. Modalities and cognitive ergonomics

turtleOS speaks to a person in more than one way, and will speak in more. Each way carries something the others cannot. The language is written for the person's head, not for the screen: what they can hold, what they can scan, what they have to remember. A new modality is not shippable until it has a section here with its first surface named (`ui_kit.MODALITIES` and the headings below must agree, and the test fails both ways). Each rule in a section has a mechanism, or a named reason it does not have one yet. Nothing here is advice.

**Who carries what.**

| Modality | Carries well | Does not carry |
|----------|-------------|----------------|
| **Text** (the conversation) | Reasoning, nuance, drafts. The record. | State, choices, anything to act on later: it scrolls away. |
| **Card** (layout) | State at a glance, choices, a few things to compare, whatever the person will return to or act on. | Argument. Long prose. More than a glance. |
| **Trace** (one edited message) | What the turn is doing, as it happens: which file, which search, which check. The handle for a file without a browser. | The file's contents. The model's chain of thought. An inventory of the workshop. |
| **Voice** (planned) | The summary, the next move, warmth, anything while eyes and hands are busy. | A list of more than three. Anything to compare or keep: speech is gone as it is said. |
| **Visual companion** (planned) | What is being talked about, shown while it is said: the picture, the link, the list the voice summarised. | The only copy of anything the voice said. |

Where this comes from: conversation-design practice for assistants (a short spoken answer, the detail in the visual, a visual that never stands alone: [Google](https://developers.google.com/assistant/conversation-design/visual-components-overview)); voice-first design (speech is linear and fleeting, the screen is a glanceable companion, the voice-only path is complete: [Alexa](https://developer.amazon.com/en-US/alexa/alexa-haus/voice-fundamentals)); chat-widget design (colour never alone, one primary act, red sparingly, label what a button does: [Slack](https://docs.slack.dev/concepts/designing-with-block-kit.md)); and typed component catalogs for generated interfaces (the model may only use what the catalog allows: [A2UI](https://a2ui.org/concepts/catalogs/), [json-render](https://github.com/vercel-labs/json-render)). The last is the bet in §4. The first three are what §2 and this section take from it.

### Modality: text

First surface: every reply Turtle writes. The conversation is the record and the place for reasoning. It is not where state or choices live.

- **The answer comes first, then the reason.** *Judgment.* Reviewed, not checked.
- **A command's answer is a card, not a paragraph.** A direct `!` command answers in blocks (`!mcp`, `!model`, `!`). *Checked:* a new embed surface fails until it is built with the kit or listed with its reason (`LEGACY_EMBED_SURFACES`).

### Modality: card

First surface: `!mcp`. What the person scans and acts on. Eight rules in §2 plus these, which are about what a head can hold.

1. **One question per surface, in its heading.** A person should be able to say what a card answers ("Who answers here", "What you can type here"). *Checked:* `build()` refuses a surface that does not open with a Header or a titled card. Whether the heading names a question a person would ask is *judgment*.
2. **Seven rows and a screen.** About seven things are scanned, more are searched. *Checked:* `ROWS_MAX`, `PART_BUDGET`, and `fit()` names what it left out.
3. **A line says what a thing is for, in one breath.** *Checked:* an item's line is at most 80 characters (`ITEM_LINE_MAX`).
4. **Colour and glyph never carry meaning alone.** *Checked:* a glyph without its word fails; the accent is one of four and means one thing.
5. **Time is relative and stays true.** "3 hours ago" is a timestamp Discord renders and keeps right. *Checked:* a raw clock reading in readable text fails.
6. **The person is not asked to remember what the surface can show.** A choice carries its consequence beside it. *Judgment.* The first test is the cold read (§5): does he have to ask what it means?
7. **The same thing is in the same place.** The channel bar's menu is where the house's own surfaces open (`mcp`, `model`, and what joins them); `!` lists everything that can be typed. *Judgment*, reviewed when the bar or the list changes.
8. **Order by what the person needs next**, not by how the machine stores it: what waits on them above what is merely true; recent activity above creation order. *Held until the first list that has dates* (`!eddy`): the test sorts a planted list and a mutation that sorts by creation must fail it. *Decided not to build earlier: no list with activity dates exists to check.*

### Modality: trace

First surface: a magic session, posted by Spirit. Discord has no token stream and no disclosure row. A sentence the model wrote is a message. The call the model made is a message: its name and its arguments, created once. The practitioner is not in an IDE: there is no file tree beside the chat. The trace is how they see what the model did, without leaving the thread.

This is not Turtle's process log. In a magic room the room's own voice posts it and edits it. A Turtle animal or a typing indicator on Turtle's account is the defect.

1. **The line names the act and the object.** `read desk/bearings.md`. `searched for "stale dates"`. `ran rot_radar`. A status, a diff, and a log are `looked`. Add, commit, push, and a new branch are `kept · commit`. Never "read the workshop". *Checked:* `describe_tool` for a workshop read, write, search and run includes the path, the query or the check (`tests/test_workshop_tools.py`). A status line does not carry the porcelain (`tests/test_turn_trace.py`).
2. **The line never carries the content.** Not the file, not a key, not a tool result stump beyond a count (`→ 4 matches`). *Checked:* a planted body in a write or a read is absent from the step text.
3. **The provider's chain of thought is not a facet we show.** It is not requested and not stored (`session_record`). What the model wrote is, and so is the call it made. In a personal room, a craft room, and a magic room, the sentence is posted as the model wrote it. The call is one quiet line: the tool, then each argument as its key and its value (`workshop_read · path desk/state.md`). A value that is a file stays a count. Those messages are created once, and they are not edited. A status line may show the name while the tool runs, and it is removed when the call itself is in the thread. The model loop does not wait on Discord. The tokens are not posted. The tool's result is not the call. A shared room still ends as one line. *Checked:* a magic turn posts that quiet line, a file body stays a count, and the message is not edited (`tests/test_dialogue_turn_trunk.py`). Naming a call reaches the loop before the tool runs, and a text delta is not posted as its own line (`tests/test_llm_tool_empty_reply.py`). The loop returns while a post is still waiting (`tests/test_dialogue_turn_trunk.py`).
4. **The sentences are messages. Each call is its own message. The room's voice posts them.** The compact card, used by a shared room, still names an act in one line: `read desk/bearings.md`, `ran rot_radar`, `kept · commit`. That paraphrase is not what a personal, craft, or magic room posts. The window that inspects a call still exists and is not attached to these messages yet. *Checked:* a personal room posts the tool name and the arguments, not the paraphrase and not the result (`tests/test_dialogue_turn_trunk.py`). The compact card and the window keep their own checks (`tests/test_turn_trace.py`, `tests/test_trace_reveal.py`). Turtle does not type (`_NoTyping`).
5. **MCP and house tools use the same grammar.** Verb plus object: `searched notes for "Kate"`, `read the calendar 15.10 for "Kate"`. A blocked call says why in their words, not a status code. *Checked:* a calendar list with a planted event title shows the day and the query, and not the title (`tests/test_service_tools.py`).
6. **A named path is the handle for a file.** Press-to-open in the thread is the next slice (the artifact viewer opens the practice root, not the workshop checkout). *Decided not to yet: no workshop-open button. Reason: the viewer does not resolve `~/workshop`.* Until then the path in the line is what they have, and they ask Spirit for a passage rather than opening a browser.
7. **The pair is the session.** `...` arrives, `.` goes on. The trace is how the work is visible between those. A file browser is not a step.

The 🐢 on craft traces stays: that room is Turtle's. A magic trace has no animal.

### Modality: voice (planned)

No voice code exists in turtleOS. The rules are written first so that the first voice surface cannot be built without them. Not sanctioned for build.

1. **Voice carries the summary and the next move; the visual carries the detail.** A voice answer is a sentence or two and, if there is more, an offer to show it.
2. **Never read more than three things aloud.** The rest is shown, and the voice says so.
3. **A complete voice-only path.** Every act that can be pressed can be said, and nothing important is only on the screen. Someone who cannot look still gets the whole of it.
4. **A voice conversation has an eddy of its own, the visual companion.** What is spoken about is shown there as it is spoken: the picture, the link, the list. The eddy is also the record.
5. **A visual never stands alone, and never repeats the speech word for word.** It shows what speech cannot hold.

*Mechanism, when voice ships:* a voice surface declares what is **said** (at most three items) and what is **shown** (blocks); the kit refuses a surface whose shown acts have no spoken equivalent, or whose spoken summary is empty. That is built with the first voice surface, not before: nothing exists to check yet, and a check with no surface is a declaration. *Decided not to build; reason: no voice surface.*

### Modality: visual companion (planned)

Ships with voice. Its rules are rules 4 and 5 above.

### How this section grows

A new modality (a screen on a device, a notification, a widget) arrives with: (1) its row in the table above; (2) its section, with first surface named; (3) each rule with a mechanism or a named reason it has none yet. `ui_kit.MODALITIES` lists what exists; `PLANNED_MODALITIES` lists what is only written. The test fails if the two and the headings disagree, so a modality cannot ship, or be dropped, without this document knowing.

## 9. Practice patterns

A `!` command is a pattern a person learns once (`!live`: what is moving here), and each practice implements it in the way it needs: craft shows whose move each eddy waits on, the private river shows dates, a health room shows shape and no words. The decision is declared per kind of channel (`practice_views.LIVE_EXTRAS` / `NO_LIVE_EXTRAS`), and `tests/test_practice_views.py` fails when a kind of channel has no decision. A new pattern ships with its table, not with branches inside the command. A card that promises something about Turtle ("Turtle has these in mind") must be built from the same selection Turtle uses, and a test says so.

## Open

- **One step, not two.** `!mcp` posts a button and the list comes from pressing it, because a typed command cannot reply privately. A slash command (`/mcp`) can reply privately in one step. The house registers no slash commands today, so that is a change to how the live bot is set up, not a styling change.
- **Do rows that differ by kind need the kind glyph at all** once the word is there? The draft says yes for scanning speed. Dogfood decides.
