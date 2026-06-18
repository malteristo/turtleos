"""River flow intake — structured prepare step before Turtle joins (Navigator v1)."""

from __future__ import annotations

import discord

from flow_runner import (
    FlowIntakeField,
    flow_orientation_description,
    format_intake_summary,
    load_flow_spec,
    read_flow_intake_values,
    write_flow_intake,
)
from mage import get_pd, set_practice_context_for_channel

# discord.py 2.7+ — TextStyle.paragraph (not TextInputStyle)
_TEXT_PARAGRAPH = discord.TextStyle.paragraph


def _parse_intake_custom_id(custom_id: str, prefix: str) -> tuple[int, int, str] | None:
    """Parse river:flow:intake:{action}:{thread_id}:{parent_id}:{flow_id}."""
    parts = custom_id.split(":")
    if len(parts) < 7 or parts[0] != "river" or parts[1] != "flow" or parts[2] != "intake":
        return None
    if parts[3] != prefix:
        return None
    try:
        thread_id = int(parts[4])
        parent_id = int(parts[5])
    except ValueError:
        return None
    flow_id = ":".join(parts[6:])
    return thread_id, parent_id, flow_id


class FlowIntakeModal(discord.ui.Modal):
    """Collect intake fields declared in flow front matter."""

    def __init__(
        self,
        *,
        thread_id: int,
        parent_id: int,
        flow_id: str,
        title: str,
        fields: list[FlowIntakeField],
        prefill: dict[str, str] | None = None,
    ):
        super().__init__(title=title[:45])
        self._thread_id = thread_id
        self._parent_id = parent_id
        self._flow_id = flow_id
        self._field_ids: list[str] = []
        defaults = prefill or {}
        for field in fields[:5]:
            field_id = field.id.strip()
            if not field_id:
                continue
            label = (field.label or field_id).strip()[:45]
            placeholder = field.placeholder[:100] if field.placeholder else None
            prior = (defaults.get(field_id) or "").strip()
            text_input = discord.ui.TextInput(
                label=label,
                custom_id=field_id[:100],
                style=_TEXT_PARAGRAPH,
                required=field.required,
                max_length=1000,
                placeholder=placeholder,
                default=prior[:1000] if prior else None,
            )
            self._field_ids.append(field_id)
            self.add_item(text_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        from eddy_spawn import patch_awaiting_title

        spec = load_flow_spec(self._flow_id)
        if not spec or not spec.intake:
            await interaction.response.send_message(
                "This flow no longer supports intake.", ephemeral=True
            )
            return

        values: dict[str, str] = {}
        for item in self.children:
            if isinstance(item, discord.ui.TextInput):
                values[item.custom_id] = (item.value or "").strip()

        set_practice_context_for_channel(self._parent_id)
        write_flow_intake(spec, values, get_pd())
        patch_awaiting_title(
            self._thread_id,
            self._parent_id,
            intake_ready=True,
        )

        thread = interaction.channel
        if not isinstance(thread, discord.Thread):
            await interaction.response.send_message(
                "Could not find the eddy thread.", ephemeral=True
            )
            return

        summary_embed = discord.Embed(
            title=f"Prepared for {spec.title}",
            description=format_intake_summary(spec, values),
            color=0x57F287,
        )
        summary_embed.set_footer(text="When this looks right, begin with Turtle.")
        view = FlowIntakeSummaryView(self._thread_id, self._parent_id, self._flow_id)
        interaction.client.add_view(view)
        await interaction.response.send_message(embed=summary_embed, view=view, silent=True)


class FlowIntakeSummaryView(discord.ui.View):
    """Explicit handoff — Turtle joins only after Begin."""

    def __init__(self, thread_id: int, parent_id: int, flow_id: str):
        super().__init__(timeout=None)
        self._thread_id = thread_id
        self._parent_id = parent_id
        self._flow_id = flow_id
        begin_btn = discord.ui.Button(
            label="Begin with Turtle",
            style=discord.ButtonStyle.primary,
            custom_id=f"river:flow:intake:begin:{thread_id}:{parent_id}:{flow_id}",
        )
        begin_btn.callback = self._on_begin
        self.add_item(begin_btn)

    async def _on_begin(self, interaction: discord.Interaction) -> None:
        custom_id = interaction.custom_id or (interaction.data or {}).get("custom_id", "")
        parsed = _parse_intake_custom_id(custom_id, "begin")
        if not parsed:
            await interaction.response.send_message("Invalid intake handoff.", ephemeral=True)
            return
        thread_id, parent_id, flow_id = parsed
        thread = interaction.channel
        if not isinstance(thread, discord.Thread) or thread.id != thread_id:
            await interaction.response.send_message(
                "Open this from the flow eddy thread.", ephemeral=True
            )
            return
        await interaction.response.defer()
        await complete_flow_intake_handoff(thread, parent_id, flow_id, skipped=False)
        try:
            await interaction.message.edit(view=None)
        except discord.HTTPException:
            pass


class FlowIntakeOrientationView(discord.ui.View):
    """Prepare (modal) or Skip — shown on flow eddy materialize when intake is configured."""

    def __init__(self, thread_id: int, parent_id: int, flow_id: str, skippable: bool = True):
        super().__init__(timeout=None)
        self._thread_id = thread_id
        self._parent_id = parent_id
        self._flow_id = flow_id
        prepare_btn = discord.ui.Button(
            label="Prepare",
            style=discord.ButtonStyle.primary,
            custom_id=f"river:flow:intake:prepare:{thread_id}:{parent_id}:{flow_id}",
        )
        prepare_btn.callback = self._on_prepare
        self.add_item(prepare_btn)
        if skippable:
            skip_btn = discord.ui.Button(
                label="Skip — I'll talk",
                style=discord.ButtonStyle.secondary,
                custom_id=f"river:flow:intake:skip:{thread_id}:{parent_id}:{flow_id}",
            )
            skip_btn.callback = self._on_skip
            self.add_item(skip_btn)

    async def _on_prepare(self, interaction: discord.Interaction) -> None:
        spec = load_flow_spec(self._flow_id)
        if not spec or not spec.intake or not spec.intake.fields:
            await interaction.response.send_message(
                "Intake is not configured for this flow.", ephemeral=True
            )
            return
        set_practice_context_for_channel(self._parent_id)
        prefill = read_flow_intake_values(spec, get_pd())
        modal = FlowIntakeModal(
            thread_id=self._thread_id,
            parent_id=self._parent_id,
            flow_id=self._flow_id,
            title=f"{spec.title} — prepare",
            fields=spec.intake.fields,
            prefill=prefill,
        )
        await interaction.response.send_modal(modal)

    async def _on_skip(self, interaction: discord.Interaction) -> None:
        from eddy_spawn import patch_awaiting_title

        patch_awaiting_title(
            self._thread_id,
            self._parent_id,
            awaiting_intake=False,
            intake_skipped=True,
        )
        embed = discord.Embed(
            description="Skipped prepare — your first message will bring Turtle in.",
            color=0x5865F2,
        )
        await interaction.response.send_message(embed=embed, silent=True)
        try:
            await interaction.message.edit(view=None)
        except discord.HTTPException:
            pass


async def complete_flow_intake_handoff(
    thread: discord.Thread,
    parent_id: int,
    flow_id: str,
    *,
    skipped: bool,
) -> None:
    """Add Turtle after explicit Begin (or mark skip path for first-message join)."""
    from eddy_spawn import pop_awaiting_title, river_add_turtle_to_eddy
    from flow_intake_opening import write_intake_handoff_request

    set_practice_context_for_channel(parent_id)
    pop_awaiting_title(thread.id, parent_id)

    await river_add_turtle_to_eddy(thread)

    if not skipped:
        write_intake_handoff_request(thread.id, parent_id, flow_id)


async def post_flow_intake_orientation(
    thread: discord.Thread,
    flow_id: str,
    bot_client: discord.Client,
) -> None:
    """Orientation embed with Prepare / Skip for flows that declare intake."""
    from mage import get_pd

    spec = load_flow_spec(flow_id, get_pd())
    if not spec or not spec.intake:
        return

    parent_id = thread.parent_id
    if not parent_id:
        return

    embed = discord.Embed(
        title=f"{spec.title} eddy",
        description=flow_orientation_description(spec, get_pd()),
        color=0x5865F2,
    )
    embed.set_footer(text="Prepare recommended — or skip and talk freely.")
    skippable = spec.intake.skippable
    view = FlowIntakeOrientationView(thread.id, parent_id, flow_id, skippable=skippable)
    bot_client.add_view(view)
    await thread.send(embed=embed, view=view, silent=True)
