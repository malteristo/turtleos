# `!mcp`, in the turtleOS design language

**Date:** 2026-10-13
**Status:** Live 2026-10-13 (`!mcp`, seen and approved: "It looks very good"). The home-channel card and `!model` follow it the same day, see [model-card-v2.md](model-card-v2.md).
**Spec:** TURTLE_SPEC §3.1, §15.5.
**Language:** [design-language.md](../ux/design-language.md). This is its first application.
**Companions:** [mcp-connections.md](mcp-connections.md), [connection-chooser.md](connection-chooser.md).

Practitioner-visible change. Four artifacts first (`docs/development.md` §12).

## The gap it closes

The first version of the list works and does not explain itself. Seen live on 2026-10-13:

- State is said twice and in opposite voices: the line says *open*, the button below says *Close*. The eye has to join each line to a button in a row under the text.
- The buttons do not say which program they act on. With a second connection they would be ambiguous.
- *End*, a destructive act, sits in the same row as the safe ones.
- The services table is a code block. On a phone its last column wraps into a broken second table.
- *no use recorded yet*, *ready, 17m ago* and *cursor-vscode* are the machine's words, not his.
- Nothing says what open or closed does. He had to be told.

## 1. Press release

You ask your house who can read your context, and the answer fits on one screen. Each program that can read it is a card. Inside the card, each thing it can see is a line: your notes, your health picture, your practice. Each line says in plain words whether the program can read it right now, and the button for it is on the same line. Press it and the line changes. The one red button, at the bottom of the card, ends the connection after asking you once. Below, the services your house uses for you are a card too, with the same shape.

## 2. Happy path

What he sees (a private reply). `▌` is the card's accent bar; `[ ]` is a button on the right of its line.

```
▌ Who can read your context
▌ -# Open what a program may see. Close it and it stops seeing it.
▌
▌ **laptop cursor** · Cursor
▌ -# last asked <t:…:R> (3 hours ago)
▌ ───────────────────────────────────────────
▌ 📝 **Notes**  🟢 open                    [ Close ]
▌ -# Cursor can read them
▌ 🩺 **Health picture**  ⚪ closed          [ Open ]
▌ -# Hidden from Cursor
▌ 🧭 **Practice**  🟢 open                 [ Close ]
▌ -# Cursor can read it
▌ ───────────────────────────────────────────
▌ [ End connection ]                    (red)

▌ What your house uses for you
▌ **X**  🟢 ready · checked <t:…:R> (17 minutes ago)    [ ⏸ Pause X ]
▌ -# Posts, bookmarks and search, on your sign-in. In craft only.
▌ [ Remove X ]                          (red)

```

He presses **Close** on the practice. The line becomes `🧭 Practice  ⚪ closed [ Open ]` with `-# Hidden from Cursor`, in place. The card in his home channel changes too. He presses **End connection**:

```
▌ End laptop cursor?
▌ It stops reading at once and has to be connected again.
▌ [ Keep ]   [ End it ] (red, last)
```

*Invisible: the grant id, the source ids, the profile, `cursor-vscode`.*

When nothing is connected the card says `Nothing is connected. To connect a program, ask your Spirit to connect you to turtleOS.` and offers nothing to press.

## 3. Success criteria

| # | Experience | Can fail in week three | Re-run |
|---|------------|------------------------|--------|
| 1 | Each line has its state and its button together; no state list sits apart from a button strip. | A second connection leaves buttons that name no program, or the buttons return to a separate row. | Automated: each source line is a row whose act is its own; two connections give two cards, each act inside its own card. |
| 2 | The words are his: kinds by name, programs by what he calls them, time as relative time. | An id, a profile name or `cursor-vscode` shows. A time is a frozen string. | Automated: planted ids and client names absent; a known client maps to its name; a time is a relative-time token. Positive control: an unknown client still shows something. |
| 3 | Red is only for what cannot be undone from here, once per group, last, and asks. | Red on a safe act, red not last, or End acts on one press. | Automated: every danger button is last in its group and has an Ask; mutation: move one, the test fails. |
| 4 | It reads on a phone. | A table in a code block wraps. | Automated: no code-block table in the reply. |
| 5 | A press changes the line in place and nothing else posts. | A press posts a second message, or the line stays stale. | Automated: a press edits the message; the grant and the home card agree. |
| 6 | He understands what open and closed do without being told. | He asks what open means. | Live, once: he opens `!mcp` cold. Not automatable. This is the criterion that matters. |
| 7 | Nothing else's list or controls change. | Another member's connection appears or can be pressed. | Unchanged from the first version's owner guards (kept, mutation-checked). |

Mechanism-blind: another transport still has to give "state and its control together, in his words".

## 4. Abandon line

Stop if he still has to be told what open means, or if the card needs more than a screen for the connections he actually has.

## The shape (for implementers)

- The kit (`ui_kit.py`) and its test (`tests/test_ui_language.py`) were built with this, not after. This is the first surface on the layout parts; nothing else moved. Pause and Remove moved from separate replies onto the card, in place.
- The first-version buttons, owner checks, audit lines, End confirmation and card refresh are behaviour that stays. This changes how it is laid out and worded.
- No footer: Discord already prints "Only you can see this" under a private reply, and saying it twice is noise.
- Discord allows 40 parts in a layout reply, which fits two connection cards beside the services card. More than two are counted in a quiet line (*N more are not shown*), ordered by most recently asked, and never dropped silently. Paging is not built; it waits until someone has three live connections.
- The program-name table is small, and an unknown name is shown as it is rather than hidden.
- **The card in the home channel** (`mcp_reveal_ui.py`) is the same card, one program, posted under the connect message. It shares `kind_rows` with the list, so the two cannot disagree about a row. A press changes it in place and it survives a restart. The connect message was born as text and a button, which Discord cannot turn into a layout message, so the card is its own message (`Offer.card_message_id`) and the connect message keeps the receipt ("Connected, until ..., nobody saw the key"). The one card that already existed was moved once at startup (`restore_reveal_cards`); after that a restart only re-arms it.
- Not in this slice: `/mcp` as a one-step private command (touches how the live bot is registered); converting any other surface; a model composing a surface.
