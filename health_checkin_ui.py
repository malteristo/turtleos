"""Buttons on the state check-in. A tap stores the same record as the sentence.

The message is sent by River's token from the Turtle process. The view that
answers the tap lives on the running River client, registered once at startup
with stable custom ids. A view that existed only on the short-lived sender
would draw buttons that do nothing.
"""

from __future__ import annotations

from datetime import date

import discord

YES_ID = "hchk:yes"
NO_ID = "hchk:no"
SKIP_ID = "hchk:skip"
STATE_ID = "hchk:state"

_registry_loader = None


def state_checkin_buttons(
    *, locale: str, has_draft: bool, register_all: bool = False
) -> list[tuple[str, str]]:
    """``(label, custom_id)`` for one post. Registration passes ``register_all``."""
    locale = "en" if locale == "en" else "de"
    rows: list[tuple[str, str]] = []
    if has_draft or register_all:
        rows.append(("Yes" if locale == "en" else "Ja", YES_ID))
        rows.append(("No, rather …" if locale == "en" else "Nein, eher …", NO_ID))
    if (not has_draft) or register_all:
        rows.append(("Answer" if locale == "en" else "Antworten", STATE_ID))
    rows.append(("Skip", SKIP_ID))
    return rows


def state_checkin_view(*, locale: str, has_draft: bool) -> discord.ui.View:
    """The buttons for one post. Registration uses the full set, separately."""
    return StateCheckinView(locale=locale, has_draft=has_draft, register_all=False)


def register_state_checkin_view(client, registry_loader) -> None:
    """``registry_loader`` comes from a module that already reads the registry.

    This module does not import that reader. A new importer of it grows the
    hub the layer rule refuses to raise.
    """
    global _registry_loader
    _registry_loader = registry_loader
    client.add_view(StateCheckinView(locale="de", has_draft=True, register_all=True))


class _WordingModal(discord.ui.Modal):
    def __init__(self, *, locale: str, kind: str, target: dict, day: date):
        title = "Eher so" if locale != "en" else "Rather this"
        if kind == "stated":
            title = "Dein Stand" if locale != "en" else "Your state"
        super().__init__(title=title[:45])
        self._kind = kind
        self._target = target
        self._day = day
        label = "Dein Stand" if locale != "en" else "Your state"
        self.wording = discord.ui.TextInput(
            label=label[:45],
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=500,
        )
        self.add_item(self.wording)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        from health_checkin import StateCapture

        text = str(self.wording.value or "").strip()
        kind = "correct" if self._kind == "correct" else "stated"
        await _finish(interaction, self._target, self._day, StateCapture(kind, text))


class StateCheckinView(discord.ui.View):
    def __init__(self, *, locale: str, has_draft: bool, register_all: bool):
        super().__init__(timeout=None)
        for label, custom_id in state_checkin_buttons(
            locale=locale, has_draft=has_draft, register_all=register_all
        ):
            style = (
                discord.ButtonStyle.primary
                if custom_id in {YES_ID, STATE_ID}
                else discord.ButtonStyle.secondary
            )
            callback = {
                YES_ID: self._yes,
                NO_ID: self._no,
                STATE_ID: self._state,
                SKIP_ID: self._skip,
            }[custom_id]
            self._button(label, style, custom_id, callback)

    def _button(self, label: str, style, custom_id: str, callback) -> None:
        button = discord.ui.Button(label=label, style=style, custom_id=custom_id)
        button.callback = callback
        self.add_item(button)

    async def _yes(self, interaction: discord.Interaction) -> None:
        from health_checkin import StateCapture

        found = _open_for(interaction)
        if found is None:
            await _refuse_closed(interaction)
            return
        target, day = found
        if not await _actor_is_subject(interaction, target):
            return
        await _finish(interaction, target, day, StateCapture("confirm"))

    async def _skip(self, interaction: discord.Interaction) -> None:
        from health_checkin import StateCapture

        found = _open_for(interaction)
        if found is None:
            await _refuse_closed(interaction)
            return
        target, day = found
        if not await _actor_is_subject(interaction, target):
            return
        await _finish(interaction, target, day, StateCapture("skip"))

    async def _no(self, interaction: discord.Interaction) -> None:
        found = _open_for(interaction)
        if found is None:
            await _refuse_closed(interaction)
            return
        target, day = found
        if not await _actor_is_subject(interaction, target):
            return
        locale = target["config"].locale
        await interaction.response.send_modal(
            _WordingModal(locale=locale, kind="correct", target=target, day=day)
        )

    async def _state(self, interaction: discord.Interaction) -> None:
        found = _open_for(interaction)
        if found is None:
            await _refuse_closed(interaction)
            return
        target, day = found
        if not await _actor_is_subject(interaction, target):
            return
        locale = target["config"].locale
        await interaction.response.send_modal(
            _WordingModal(locale=locale, kind="stated", target=target, day=day)
        )


def _registry():
    if _registry_loader is None:
        return None
    return _registry_loader()


def _open_for(interaction: discord.Interaction):
    from channel_primitives import resolve_primitive
    from health_checkin import health_channel_targets, open_checkin_for_message

    message = interaction.message
    registry = _registry()
    if message is None or not registry:
        return None
    for target in health_channel_targets(registry):
        day = open_checkin_for_message(target["practice_dir"], message.id)
        if day is None:
            continue
        primitive = resolve_primitive(registry, target["channel_id"])
        if primitive is None:
            continue
        return {**target, "primitive": primitive}, day
    return None


async def _actor_is_subject(interaction: discord.Interaction, target: dict) -> bool:
    from health_record_ui import _member_key

    registry = _registry()
    actor = _member_key(registry or {}, interaction.user.id)
    if actor == target["subject"]:
        target["actor"] = actor
        return True
    locale = target["config"].locale
    text = (
        "Only you can answer this."
        if locale == "en"
        else "Nur du kannst das beantworten."
    )
    if not interaction.response.is_done():
        await interaction.response.send_message(text, ephemeral=True)
    return False


async def _refuse_closed(interaction: discord.Interaction) -> None:
    await interaction.response.send_message(
        "Das ist schon beantwortet.", ephemeral=True
    )


async def _finish(interaction, target: dict, day: date, capture) -> None:
    from health_checkin import posted_draft
    from health_record_ui import apply_state_capture

    if "actor" not in target and not await _actor_is_subject(interaction, target):
        return
    ack = apply_state_capture(
        root=target["practice_dir"],
        primitive=target["primitive"],
        actor=target["actor"],
        today=day,
        locale=target["config"].locale,
        capture=capture,
        draft=posted_draft(target["practice_dir"], day),
    )
    if ack is None:
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "Konnte ich nicht halten.", ephemeral=True
            )
        return
    if interaction.response.is_done():
        await interaction.followup.send(ack)
    else:
        await interaction.response.send_message(ack)
    message = interaction.message
    if message is not None:
        try:
            await message.edit(view=None)
        except Exception:
            pass
