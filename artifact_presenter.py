"""Generative UI E1 — compose artifact browse surfaces (controlled presentation rules)."""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field

import discord

from artifact_viewer import (
    SHELF_DEFS,
    format_shelf_menu,
    list_recent_artifacts,
    list_shelf_artifacts,
    list_shelves,
    shelf_title_for_path,
)
from practice_io import artifact_display_name


class ArtifactIntent(enum.Enum):
    BROWSE_DEFAULT = "browse_default"
    BROWSE_SHELF = "browse_shelf"
    BROWSE_ALL = "browse_all"
    POST_CHECKPOINT = "post_checkpoint"


@dataclass
class ArtifactSurface:
    template_id: str
    embed: discord.Embed | None = None
    content: str | None = None
    open_actions: list[tuple[str, str]] = field(default_factory=list)
    """(button label, turtle-talk command) pairs — typically !read <path>."""
    export_paths: list[str] = field(default_factory=list)
    """Paths for a second action row of Export buttons (≤3, when Open row uses link buttons)."""


def checkpoint_open_path(
    *,
    session_note: str | None,
    flow_write: str | None,
) -> str | None:
    """Primary artifact path to offer Open after checkpoint."""
    if session_note:
        name = session_note.strip()
        if not name.endswith(".md"):
            name += ".md"
        if name.startswith("sessions/"):
            return name
        return f"sessions/{name}"
    if flow_write:
        path = flow_write.strip()
        if not path.endswith(".md"):
            path += ".md"
        return path
    return None


def _practitioner_footer() -> str:
    return "Search: !search · All shelves: !artifacts --all"


def _open_label(path: str) -> str:
    name = artifact_display_name(path)
    label = f"Open: {name}"
    return label[:80]


def _open_actions_for_paths(paths: list[str]) -> list[tuple[str, str]]:
    actions: list[tuple[str, str]] = []
    for path in paths[:8]:
        actions.append((_open_label(path), f"!read {path}"))
    return actions


def compose_artifact_surface(
    intent: ArtifactIntent,
    *,
    mage_type: str | None = None,
    shelf_key: str | None = None,
    session_note: str | None = None,
    flow_write: str | None = None,
) -> ArtifactSurface:
    if intent == ArtifactIntent.BROWSE_ALL:
        text = format_shelf_menu(mage_type=mage_type, include_empty=True, operator_hints=True)
        embed = discord.Embed(
            title="Practice artifacts",
            description=text[:4096],
            color=0x5865F2,
        )
        return ArtifactSurface(template_id="operator_catalog", embed=embed)

    if intent == ArtifactIntent.POST_CHECKPOINT:
        path = checkpoint_open_path(session_note=session_note, flow_write=flow_write)
        if not path:
            return ArtifactSurface(template_id="post_checkpoint_none")
        display = artifact_display_name(path)
        shelf = shelf_title_for_path(path)
        embed = discord.Embed(
            title="Checkpoint saved",
            description=f"Saved to **{shelf}** · {display}",
            color=0x5865F2,
        )
        embed.set_footer(text="History kept — continue when ready, or !release to close.")
        return ArtifactSurface(
            template_id="post_checkpoint_open",
            embed=embed,
            open_actions=[("Open", f"!read {path}")],
        )

    if intent == ArtifactIntent.BROWSE_SHELF:
        key = (shelf_key or "").lower().strip()
        artifacts = list_shelf_artifacts(key, mage_type=mage_type)
        title = next((s.title for s in SHELF_DEFS if s.key == key), key.title())
        if not artifacts:
            embed = discord.Embed(
                title=title,
                description=f"No artifacts in **{title}** yet.",
                color=0x5865F2,
            )
            embed.set_footer(text=_practitioner_footer())
            return ArtifactSurface(template_id="shelf_empty", embed=embed)

        lines = [artifact_display_name(p) for p in artifacts[:40]]
        body = "\n".join(f"• {line}" for line in lines)
        if len(artifacts) > 40:
            body += f"\n\n*…and {len(artifacts) - 40} more. Use `!search`.*"
        embed = discord.Embed(
            title=f"{title} ({len(artifacts)})",
            description=body[:4096],
            color=0x5865F2,
        )
        embed.set_footer(text=_practitioner_footer())
        open_paths = artifacts[:8]
        export_paths = artifacts[:3] if len(open_paths) <= 3 else []
        return ArtifactSurface(
            template_id="shelf_listing",
            embed=embed,
            open_actions=_open_actions_for_paths(open_paths),
            export_paths=export_paths,
        )

    # browse_default
    recent = list_recent_artifacts(limit=8, mage_type=mage_type)
    if recent:
        lines = [f"• **{r.display_name}** · {r.shelf_title}" for r in recent]
        embed = discord.Embed(
            title="Recent",
            description="\n".join(lines)[:4096],
            color=0x5865F2,
        )
        embed.set_footer(text=_practitioner_footer())
        paths = [r.path for r in recent]
        print(
            f"artifact_presenter intent=browse_default template=recent_cross_shelf items={len(paths)}"
        )
        return ArtifactSurface(
            template_id="recent_cross_shelf",
            embed=embed,
            open_actions=_open_actions_for_paths(paths),
        )

    nonempty = [(s, c) for s, c in list_shelves(mage_type=mage_type) if c > 0]
    if not nonempty:
        embed = discord.Embed(
            title="Your practice library",
            description=(
                "Nothing saved yet. Checkpoint an eddy or paste something into intake — "
                "it will show up here."
            ),
            color=0x5865F2,
        )
        embed.set_footer(text=_practitioner_footer())
        return ArtifactSurface(template_id="corpus_empty", embed=embed)

    lines = [f"**{shelf.title}** — {count} · {shelf.blurb}" for shelf, count in nonempty]
    embed = discord.Embed(
        title="Your practice library",
        description="\n".join(lines)[:4096],
        color=0x5865F2,
    )
    embed.set_footer(text=_practitioner_footer())
    browse_actions: list[tuple[str, str]] = []
    for shelf, _count in nonempty[:3]:
        browse_actions.append((f"Browse {shelf.title}", f"!artifacts {shelf.key}"))
    print(f"artifact_presenter intent=browse_default template=nonempty_shelves shelves={len(nonempty)}")
    return ArtifactSurface(
        template_id="nonempty_shelves",
        embed=embed,
        open_actions=browse_actions,
    )


def _apply_practice_context(interaction: discord.Interaction) -> None:
    """Restore mage/practice context for button/select callbacks (split-bot eddies)."""
    from mage import set_practice_context_for_channel

    channel = interaction.channel
    if isinstance(channel, discord.Thread) and channel.parent_id:
        set_practice_context_for_channel(channel.parent_id)
    elif channel:
        set_practice_context_for_channel(channel.id)


def _artifact_read_url(path: str) -> str | None:
    """Browser URL for artifact when web read is configured."""
    from practice_io import artifact_read_url, is_readable

    rel = path.strip()
    if not is_readable(rel):
        return None
    return artifact_read_url(rel)


class _ArtifactOpenSelect(discord.ui.Select):
    """Select menu — option values store pre-resolved browser URLs when available."""

    def __init__(
        self,
        channel_id: int,
        options: list[tuple[str, str, str | None]],
        *,
        select_id: str,
    ):
        select_options = []
        for label, path, url in options[:25]:
            # Embed resolved URL at compose time (practice context is correct then).
            value = (url or path)[:100]
            select_options.append(
                discord.SelectOption(
                    label=label[:100],
                    value=value,
                    description=shelf_title_for_path(path)[:100],
                )
            )
        super().__init__(
            placeholder="Choose artifact to open…",
            min_values=1,
            max_values=1,
            options=select_options,
            custom_id=f"artifact:open_select:{channel_id}:{select_id}",
        )
        self._channel_id = channel_id
        self._path_for_value = {
            (url or path)[:100]: path for _label, path, url in options[:25]
        }

    async def callback(self, interaction: discord.Interaction):
        if interaction.channel.id != self._channel_id:
            await interaction.response.send_message("Wrong channel.", ephemeral=True)
            return
        selected = self.values[0]
        path_hint = self._path_for_value.get(selected, selected)
        if selected.startswith("http://") or selected.startswith("https://"):
            url = selected
        else:
            _apply_practice_context(interaction)
            url = _artifact_read_url(path_hint)
        if url:
            view = discord.ui.View()
            view.add_item(
                discord.ui.Button(
                    label="Open in browser",
                    style=discord.ButtonStyle.link,
                    url=url,
                )
            )
            export_path = path_hint
            if export_path and not export_path.endswith(".md"):
                export_path += ".md"
            from cmd_dispatch import CONTEXTUAL_ACTION_COMMANDS
            from eddy_lifecycle_bar import _encode_act_custom_id, _run_river_act_command

            if export_path:
                export_cmd = f"!export {export_path}"
                custom_id = _encode_act_custom_id(self._channel_id, export_cmd)
                if custom_id and "export" in CONTEXTUAL_ACTION_COMMANDS:

                    async def _on_export(interaction: discord.Interaction):
                        if interaction.channel.id != self._channel_id:
                            await interaction.response.send_message("Wrong channel.", ephemeral=True)
                            return
                        _apply_practice_context(interaction)
                        await interaction.response.defer()
                        await _run_river_act_command(interaction, "export", [export_path])

                    export_btn = discord.ui.Button(
                        label="Export .md",
                        custom_id=custom_id,
                        style=discord.ButtonStyle.secondary,
                    )
                    export_btn.callback = _on_export
                    view.add_item(export_btn)
            display = artifact_display_name(path_hint)
            embed = interaction.message.embeds[0] if interaction.message and interaction.message.embeds else None
            await interaction.response.edit_message(
                content=f"**{display}** — tap below to open.",
                embed=embed,
                view=view,
            )
            from bar_anchor import ensure_channel_bars

            await ensure_channel_bars(interaction.channel, interaction.client)
            return
        from eddy_lifecycle_bar import _run_river_act_command

        await interaction.response.defer()
        await _run_river_act_command(interaction, "read", [path_hint])


class ArtifactPresenterView(discord.ui.View):
    """Open / browse buttons for artifact presenter surfaces."""

    def __init__(
        self,
        channel_id: int,
        actions: list[tuple[str, str]],
        *,
        export_paths: list[str] | None = None,
    ):
        super().__init__(timeout=3600)
        self._channel_id = channel_id
        from cmd_dispatch import CONTEXTUAL_ACTION_COMMANDS
        from eddy_lifecycle_bar import _encode_act_custom_id, _parse_act_command, _run_river_act_command

        read_actions: list[tuple[str, str]] = []
        other_actions: list[tuple[str, str]] = []
        for label, command in actions:
            cmd, _ = _parse_act_command(command)
            if cmd == "read":
                read_actions.append((label, command))
            else:
                other_actions.append((label, command))

        if len(read_actions) > 3:
            options: list[tuple[str, str, str | None]] = []
            for _label, command in read_actions[:25]:
                _cmd, args = _parse_act_command(command)
                path = args[0] if args else ""
                if path:
                    options.append(
                        (
                            artifact_display_name(path),
                            path,
                            _artifact_read_url(path),
                        )
                    )
            if options:
                self.add_item(
                    _ArtifactOpenSelect(channel_id, options, select_id=uuid.uuid4().hex[:8])
                )
        else:
            for label, command in read_actions[:3]:
                _cmd, args = _parse_act_command(command)
                path = args[0] if args else ""
                url = _artifact_read_url(path) if path else None
                if url:
                    self.add_item(
                        discord.ui.Button(
                            label=label[:80],
                            style=discord.ButtonStyle.link,
                            url=url,
                        )
                    )
                    continue
                if _cmd not in CONTEXTUAL_ACTION_COMMANDS:
                    continue
                custom_id = _encode_act_custom_id(channel_id, command)
                if not custom_id:
                    continue
                button = discord.ui.Button(
                    label=label[:80],
                    custom_id=custom_id,
                    style=discord.ButtonStyle.secondary,
                )
                button.callback = self._make_read_callback(
                    custom_id, _run_river_act_command, _parse_act_command
                )
                self.add_item(button)

        for label, command in other_actions[:3]:
            cmd, _ = _parse_act_command(command)
            if cmd not in CONTEXTUAL_ACTION_COMMANDS:
                continue
            custom_id = _encode_act_custom_id(channel_id, command)
            if not custom_id:
                continue
            button = discord.ui.Button(
                label=label[:80],
                custom_id=custom_id,
                style=discord.ButtonStyle.primary,
            )
            button.callback = self._make_read_callback(custom_id, _run_river_act_command, _parse_act_command)
            self.add_item(button)

        if export_paths and len(read_actions) <= 3 and "export" in CONTEXTUAL_ACTION_COMMANDS:
            for path in export_paths[:3]:
                command = f"!export {path}"
                label = f"Export: {artifact_display_name(path)}"[:80]
                custom_id = _encode_act_custom_id(channel_id, command)
                if not custom_id:
                    continue
                button = discord.ui.Button(
                    label=label,
                    custom_id=custom_id,
                    style=discord.ButtonStyle.secondary,
                )
                button.callback = self._make_read_callback(
                    custom_id, _run_river_act_command, _parse_act_command
                )
                self.add_item(button)

    def _make_read_callback(self, custom_id: str, run_act, parse_cmd):
        async def callback(interaction: discord.Interaction):
            if interaction.channel.id != self._channel_id:
                await interaction.response.send_message("Wrong channel.", ephemeral=True)
                return
            _apply_practice_context(interaction)
            from eddy_lifecycle_bar import _decode_act_custom_id

            try:
                _, decoded = _decode_act_custom_id(custom_id)
            except ValueError:
                await interaction.response.send_message("This action expired.", ephemeral=True)
                return
            cmd, args = parse_cmd(decoded)
            await interaction.response.defer()
            await run_act(interaction, cmd, args)
            for child in self.children:
                child.disabled = True
            try:
                if interaction.message:
                    await interaction.message.edit(view=self)
            except discord.HTTPException:
                pass

        return callback


async def reply_artifact_surface(message, surface: ArtifactSurface) -> None:
    """Send composed artifact surface as a Discord reply."""
    kwargs: dict = {"mention_author": False}
    if surface.embed is not None:
        kwargs["embed"] = surface.embed
    if surface.content:
        kwargs["content"] = surface.content
    if not surface.embed and not surface.content:
        kwargs["content"] = "\u200b"

    view = None
    if surface.open_actions or surface.export_paths:
        view = ArtifactPresenterView(
            message.channel.id,
            surface.open_actions,
            export_paths=surface.export_paths,
        )
        if view.children:
            kwargs["view"] = view
        else:
            view = None

    await message.reply(**kwargs)
