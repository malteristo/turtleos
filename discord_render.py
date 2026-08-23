"""Render an ``OutgoingMessage`` onto Discord.

The outbound half of the transport seam. `runtime/` decides what to say and what to
offer; this module decides that an offer looks like an embed with buttons, that a
button's `custom_id` has a particular shape, and that clicking one defers before it
works. None of those are practice decisions, and all of them used to be written
inline in whichever module happened to be posting.

Why this exists as its own module rather than a method on the value object: the
value objects live in `runtime/`, which may not import a transport library — a rule
`tests/test_transport_boundary.py` enforces. So rendering has to live outside, and
having exactly one place for it is what makes a second transport a new file rather
than a search for every `discord.ui.View` in the tree.

**Guard note, load-bearing.** Moving labels out of `Button(label="…")` literals and
into `Action.label` blinds `tests/test_no_decline_buttons.py`, which reads label
literals from the AST. That guard now also scans `Action(...)` constructions in
`runtime/`, because after this module exists that is where offer labels are
written. A guard that keeps passing because the thing it watches moved is the
failure mode this codebase is trying to stop having.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Iterable

import discord

from runtime.messages import Action, IncomingMessage, OutgoingMessage

ActionHandler = Callable[[discord.Interaction, Action], Awaitable[None]]

# Discord's own limit; a longer label is rejected at post time, which reads as the
# whole offer failing rather than as one string being too long.
MAX_LABEL_CHARS = 80


def default_custom_id(prefix: str, action: Action) -> str:
    return f"{prefix}:{action.key}"


class OutgoingView(discord.ui.View):
    """The actions of an ``OutgoingMessage``, as Discord buttons.

    Persistent by default (`timeout=None`) because offer buttons have to survive a
    restart, which means their `custom_id` must be stable and the view must be
    re-registered with `Client.add_view` on boot.
    """

    def __init__(
        self,
        outgoing: OutgoingMessage,
        incoming: IncomingMessage,
        *,
        prefix: str,
        handlers: dict[str, ActionHandler],
        custom_id_for: Callable[[str, Action], str] = default_custom_id,
        style: discord.ButtonStyle = discord.ButtonStyle.primary,
    ) -> None:
        super().__init__(timeout=None)
        self._handlers = handlers
        self.rendered: tuple[Action, ...] = outgoing.renderable_actions(incoming)

        for action in self.rendered:
            button = discord.ui.Button(
                label=action.label[:MAX_LABEL_CHARS],
                style=style,
                custom_id=custom_id_for(prefix, action),
            )
            button.callback = self._callback_for(action)
            self.add_item(button)

    def _callback_for(self, action: Action) -> Callable[[discord.Interaction], Awaitable[None]]:
        async def callback(interaction: discord.Interaction) -> None:
            handler = self._handlers.get(action.key)
            if handler is None:
                # An action the runtime offered and the transport cannot service is
                # a wiring bug, and the practitioner should not be the one who
                # discovers it as a silent button.
                print(f"discord_render: no handler for action {action.key!r}")
                await interaction.response.send_message(
                    "That button isn't wired up — this is a bug, not you.",
                    ephemeral=True,
                )
                return
            await handler(interaction, action)

        return callback


def _fold_actions_into_text(text: str, actions: Iterable[Action]) -> str:
    """What a surface without buttons says instead.

    Not currently reachable from Discord — kept because dropping the actions
    silently is the behaviour this seam exists to prevent, and a transport that
    lands later should find the fold already written rather than reinvent it.
    """
    names = [a.label for a in actions]
    if not names:
        return text
    if len(names) == 1:
        return f"{text}\n\nSay **{names[0]}** if you want it."
    joined = ", ".join(f"**{n}**" for n in names[:-1])
    return f"{text}\n\nSay {joined} or **{names[-1]}**."


async def send_outgoing(
    channel: Any,
    outgoing: OutgoingMessage,
    incoming: IncomingMessage,
    *,
    prefix: str,
    handlers: dict[str, ActionHandler] | None = None,
    bot_client: discord.Client | None = None,
    title: str | None = None,
    color: int | None = None,
    footer: str | None = None,
    custom_id_for: Callable[[str, Action], str] = default_custom_id,
    silent: bool = True,
) -> discord.Message | None:
    """Post the reply. Returns the sent message, or None when the send failed.

    None rather than a raise, because every caller's next step is the same: an
    offer that did not post is not an offer, so nothing downstream (least of all
    the ledger) should record it as one.

    `title`, `color` and `footer` are Discord chrome and are the caller's, not the
    runtime's. When no `title` is given the text is sent as plain content, which is
    the right shape for a conversational reply.
    """
    handlers = handlers or {}
    view: OutgoingView | None = None
    if outgoing.renderable_actions(incoming):
        view = OutgoingView(
            outgoing,
            incoming,
            prefix=prefix,
            handlers=handlers,
            custom_id_for=custom_id_for,
        )
        if bot_client is not None:
            bot_client.add_view(view)

    text = outgoing.text
    if not incoming.can("buttons"):
        text = _fold_actions_into_text(text, outgoing.actions)

    kwargs: dict[str, Any] = {"silent": silent}
    if view is not None:
        kwargs["view"] = view
    if title is not None:
        embed = discord.Embed(title=title, description=text, color=color)
        if footer:
            embed.set_footer(text=footer)
        kwargs["embed"] = embed
    else:
        kwargs["content"] = text

    try:
        return await channel.send(**kwargs)
    except discord.HTTPException as exc:
        print(f"send_outgoing failed ({prefix}): {exc}")
        return None
