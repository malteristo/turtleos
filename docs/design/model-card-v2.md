# `!model` and the home-channel card, in the turtleOS design language

**Date:** 2026-10-13
**Status:** Built in the checkout 2026-10-13. Sanctioned with `.` ("yes and I also want the `!model` interface to get that makeover"). Not yet deployed. Gate: he opens `!model` and the new card cold.
**Spec:** TURTLE_SPEC §3.1, §15.5 (the model a room reads on).
**Language:** [design-language.md](../ux/design-language.md). Second and third surfaces on it, after [mcp-list-v2.md](mcp-list-v2.md).
**Companions:** [own-channel-model.md](own-channel-model.md).

## The gap it closes

`!model` answered with a block of text (This channel / House / a missing-provider line / how to pick / a cloud note) and a menu below it. The facts were right and the order was the machine's: what the house uses came before what the menu does, the privacy sentence sat apart from the model it was about, and a pick posted a second message instead of changing the first. The home-channel connection card was text and a row of buttons whose state was said twice.

## Press release

You type `!model` and one card answers: who answers in this channel, in a line, with what that means for you ("Runs on the house machine. Nothing leaves the house." or "Reads what you say here on the provider's servers. The community account pays."). The menu to change it is on that card. Pick another and the card changes in place and says so, and it now describes the new model. In a shared room the card also says who changed it. The connection card in your home channel reads the same way as `!mcp`: a line per thing the program can see, its state, and its own button.

## What he sees (`!model`, `[ ]` is the menu)

```
## Who answers here
-# The model that reads and replies in this channel. Change it with the menu, or type !model and a name.
▌ **Gemma 4 31B (local)**  🟢 answering here
▌ -# Runs on the house machine. Nothing leaves the house. Good for: conversation, ...
▌ [ Change this channel's model            v ]
-# The house itself runs River on ... and Memory on .... Those are not chosen here.
-# A cloud model is paid from the community account and reads what you say here on the provider's servers. ...
```

After a pick the card is green, opens with "**Claude Opus 5.5 answers here from now on.**" and the cloud warning has moved onto the row, where it belongs. A health room says what the provider would read (the health board, document text, what is said) before the pick and after it.

## Criteria (what makes it pass)

1. The room's model, what it means, and the way to change it are on one card, in that order.
2. A pick changes the card in place. A menu posted before this change cannot become a card, so a press on one answers with a new card instead of failing.
3. The consequence for a cloud model is said on its own row; a local room is warned once, below, what a cloud pick would mean. A health room names what the provider would read, before and after.
4. Who may pick is unchanged (`set_pick`). A refused press is a private sentence to the presser and writes nothing.
5. Every string exists in English and German; the card keeps the grammar in every state (local, cloud, health, shared, no owner, over 25 choices).
6. He reads it cold and does not have to ask what answering here means.

Abandon line: if he still asks what "answering here" does, or the card is longer than the old text was, the wording is wrong and the layout is not.

## The shape

- **Kit:** a `Pick` block (a menu with a sentence for a placeholder, up to 25 choices, one current) and `Choice`. A card holds at most one, after its rows and before its acts. The language test reads into menus: an id or an emoji outside the vocabulary in a choice fails it.
- **One listener, many menus:** the menu keeps its custom id, so one registered listener answers every card, before and after a restart. A test says the card's menu and the listener share the id.
- **The home card:** `kind_rows` is shared with `!mcp`. `Offer.card_message_id` records the card; `show_card` posts it once (an in-process lock decides "not yet posted") and then lets the connect message say "Connected". A change from `!mcp` edits the card. An ended connection leaves a line and no buttons.
- **Dead code removed:** `picker_text`, `describe`, the first-version select and view classes, `card_text`, `announcement_for`, `RevealView`, `button_label`.
- **Not in this slice:** `/model` or `/mcp` as private one-step commands (needs slash registration on the live bot); paging for more than two connections; a model composing a card.
