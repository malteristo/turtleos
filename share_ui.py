"""Share eddy Discord UI — picker, preview, cmd_share (TURTLE_SPEC §15.6)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import discord

from helpers import reload_history
from mage import get_mage_key, get_registry, set_practice_context_for_channel
from share_delivery import (
    ShareContinueView,
    deliver_practitioner_share,
    deliver_space_share,
    maybe_post_share_rename_offer,
)
from share_policy import shared_eddy_source_for_thread
from share_storage import (
    clear_pending_draft,
    load_pending_draft,
    resolve_share_runtime_dir,
    write_pending_draft,
)
from share_targets import (
    ShareTarget,
    SpaceShareTarget,
    list_practitioner_targets,
    list_space_targets,
    mage_is_space_member,
    river_channel_for_mage,
    runtime_dir_for_mage,
)
from share_transcript import (
    build_export_bundle,
    build_export_bundle_from_draft,
    build_preview_embed,
    enrich_export_bundle,
    is_placeholder_eddy_title,
    share_label,
)

class ShareTargetSelect(discord.ui.Select):
    def __init__(
        self,
        *,
        thread_id: int,
        author_id: int,
        parent_channel_id: int,
        targets: list[ShareTarget],
    ):
        options = [
            discord.SelectOption(
                label=t.address[:100],
                value=t.mage_key,
                description=f"Share to {t.address}"[:100],
            )
            for t in targets[:25]
        ]
        super().__init__(
            placeholder="Choose a practitioner…",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"share:select:{thread_id}:{author_id}",
        )
        self._thread_id = thread_id
        self._author_id = author_id
        self._parent_channel_id = parent_channel_id
        self._targets = {t.mage_key: t for t in targets}

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self._author_id:
            await interaction.response.send_message(
                "Only the person who started Share can pick a recipient.",
                ephemeral=True,
            )
            return
        target = self._targets.get(self.values[0])
        if not target:
            await interaction.response.send_message("Unknown recipient.", ephemeral=True)
            return

        runtime_dir = resolve_share_runtime_dir(parent_channel_id=self._parent_channel_id)
        draft = load_pending_draft(runtime_dir, self._author_id, self._thread_id)
        if not draft:
            await interaction.response.send_message(
                "Share session expired — run `!share` again.",
                ephemeral=True,
            )
            return
        draft["target_mage_key"] = target.mage_key
        draft["target_address"] = target.address
        draft["target_discord_id"] = target.discord_id
        draft["target_channel_id"] = target.channel_id
        draft["target_kind"] = "practitioner"
        draft["parent_id"] = interaction.channel.parent_id
        write_pending_draft(runtime_dir, self._author_id, self._thread_id, draft)

        await interaction.response.defer()
        try:
            bundle = build_export_bundle(
                title=draft["title"],
                history=draft["history"],
                sharer_id=draft["sharer_id"],
                sharer_key=draft["sharer_key"],
                sharer_address=draft["sharer_address"],
                source_thread_id=draft["source_thread_id"],
                share_id=draft.get("share_id"),
            )
            bundle = await enrich_export_bundle(bundle)
        except Exception as exc:
            await interaction.followup.send(
                f"Could not summarize for share: {type(exc).__name__}: {exc}",
                ephemeral=True,
            )
            return

        draft["display_title"] = bundle["display_title"]
        draft["digest"] = bundle["digest"]
        write_pending_draft(runtime_dir, self._author_id, self._thread_id, draft)

        preview = SharePreviewView(
            self._thread_id, self._author_id, target, parent_channel_id=self._parent_channel_id
        )
        embed = build_preview_embed(draft, target)
        try:
            if interaction.message:
                await interaction.message.edit(embed=embed, view=preview)
            else:
                await interaction.edit_original_response(embed=embed, view=preview)
        except discord.HTTPException as exc:
            print(f"Share preview edit failed: {type(exc).__name__}: {exc}")
            await interaction.followup.send(
                f"Could not show share preview: {exc}",
                ephemeral=True,
            )
            return

        if isinstance(interaction.channel, discord.Thread) and is_placeholder_eddy_title(
            draft.get("title", "")
        ):
            await maybe_post_share_rename_offer(interaction.channel, draft, interaction.client)


class ShareSpaceSelect(discord.ui.Select):
    def __init__(
        self,
        *,
        thread_id: int,
        author_id: int,
        parent_channel_id: int,
        targets: list[SpaceShareTarget],
    ):
        options = [
            discord.SelectOption(
                label=t.address[:100],
                value=t.space_key,
                description=f"Share to {t.address}"[:100],
            )
            for t in targets[:25]
        ]
        super().__init__(
            placeholder="Choose a space…",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"share:space:{thread_id}:{author_id}",
        )
        self._thread_id = thread_id
        self._author_id = author_id
        self._parent_channel_id = parent_channel_id
        self._targets = {t.space_key: t for t in targets}

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self._author_id:
            await interaction.response.send_message(
                "Only the person who started Share can pick a space.",
                ephemeral=True,
            )
            return
        target = self._targets.get(self.values[0])
        if not target:
            await interaction.response.send_message("Unknown space.", ephemeral=True)
            return

        runtime_dir = resolve_share_runtime_dir(parent_channel_id=self._parent_channel_id)
        draft = load_pending_draft(runtime_dir, self._author_id, self._thread_id)
        if not draft:
            await interaction.response.send_message(
                "Share session expired — run `!share` again.",
                ephemeral=True,
            )
            return
        draft["target_space_key"] = target.space_key
        draft["target_address"] = target.address
        draft["target_channel_id"] = target.channel_id
        draft["target_kind"] = "space"
        draft["parent_id"] = interaction.channel.parent_id
        write_pending_draft(runtime_dir, self._author_id, self._thread_id, draft)

        await interaction.response.defer()
        try:
            bundle = build_export_bundle(
                title=draft["title"],
                history=draft["history"],
                sharer_id=draft["sharer_id"],
                sharer_key=draft["sharer_key"],
                sharer_address=draft["sharer_address"],
                source_thread_id=draft["source_thread_id"],
                share_id=draft.get("share_id"),
            )
            bundle = await enrich_export_bundle(bundle)
        except Exception as exc:
            await interaction.followup.send(
                f"Could not summarize for share: {type(exc).__name__}: {exc}",
                ephemeral=True,
            )
            return

        draft["display_title"] = bundle["display_title"]
        draft["digest"] = bundle["digest"]
        write_pending_draft(runtime_dir, self._author_id, self._thread_id, draft)

        preview = SharePreviewView(
            self._thread_id, self._author_id, target, parent_channel_id=self._parent_channel_id
        )
        embed = build_preview_embed(draft, target)
        try:
            if interaction.message:
                await interaction.message.edit(embed=embed, view=preview)
            else:
                await interaction.edit_original_response(embed=embed, view=preview)
        except discord.HTTPException as exc:
            print(f"Share preview edit failed: {type(exc).__name__}: {exc}")
            await interaction.followup.send(
                f"Could not show share preview: {exc}",
                ephemeral=True,
            )
            return

        if isinstance(interaction.channel, discord.Thread) and is_placeholder_eddy_title(
            draft.get("title", "")
        ):
            await maybe_post_share_rename_offer(interaction.channel, draft, interaction.client)


class ShareEditModal(discord.ui.Modal, title="Edit share preview"):
    """Edit title and digest — submit to confirm; dismiss modal to cancel."""

    def __init__(
        self,
        thread_id: int,
        author_id: int,
        target: ShareTarget | SpaceShareTarget,
        display_title: str,
        digest: str,
        *,
        parent_channel_id: int,
    ):
        super().__init__()
        self._thread_id = thread_id
        self._author_id = author_id
        self._target = target
        self._parent_channel_id = parent_channel_id
        self.title_input = discord.ui.TextInput(
            label="Title",
            default=display_title[:100],
            max_length=100,
            required=True,
        )
        self.digest_input = discord.ui.TextInput(
            label="Digest",
            style=discord.TextStyle.paragraph,
            default=digest[:500],
            max_length=500,
            required=True,
        )
        self.add_item(self.title_input)
        self.add_item(self.digest_input)

    async def on_submit(self, interaction: discord.Interaction):
        runtime_dir = resolve_share_runtime_dir(parent_channel_id=self._parent_channel_id)
        draft = load_pending_draft(runtime_dir, self._author_id, self._thread_id)
        if not draft:
            await interaction.response.send_message(
                "Share session expired — run `!share` again.",
                ephemeral=True,
            )
            return

        draft["display_title"] = self.title_input.value.strip()[:100]
        draft["digest"] = self.digest_input.value.strip()[:500]
        write_pending_draft(runtime_dir, self._author_id, self._thread_id, draft)

        preview = SharePreviewView(
            self._thread_id,
            self._author_id,
            self._target,
            parent_channel_id=self._parent_channel_id,
        )
        embed = build_preview_embed(draft, self._target)
        try:
            await interaction.response.edit_message(embed=embed, view=preview)
        except discord.HTTPException as exc:
            await interaction.response.send_message(
                f"Could not update preview: {exc}",
                ephemeral=True,
            )
            return

        if isinstance(interaction.channel, discord.Thread):
            await maybe_post_share_rename_offer(
                interaction.channel,
                draft,
                interaction.client,
                suggested=draft["display_title"],
            )


class SharePreviewView(discord.ui.View):
    """Preview synthesized title/digest before send."""

    def __init__(
        self,
        thread_id: int,
        author_id: int,
        target: ShareTarget | SpaceShareTarget,
        *,
        parent_channel_id: int,
    ):
        super().__init__(timeout=600)
        self._thread_id = thread_id
        self._author_id = author_id
        self._target = target
        self._parent_channel_id = parent_channel_id
        target_token = (
            f"s:{target.space_key}"
            if isinstance(target, SpaceShareTarget)
            else f"p:{target.mage_key}"
        )

        edit_btn = discord.ui.Button(
            label="Edit",
            style=discord.ButtonStyle.secondary,
            custom_id=f"share:edit:{thread_id}:{author_id}:{target_token}",
        )
        edit_btn.callback = self._on_edit
        cancel = discord.ui.Button(
            label="Cancel",
            style=discord.ButtonStyle.secondary,
            custom_id=f"share:cancel:{thread_id}:{author_id}",
        )
        cancel.callback = self._on_cancel
        share = discord.ui.Button(
            label="Share",
            style=discord.ButtonStyle.primary,
            emoji="📤",
            custom_id=f"share:send:{thread_id}:{author_id}:{target_token}",
        )
        share.callback = self._on_share
        self.add_item(edit_btn)
        self.add_item(cancel)
        self.add_item(share)

    async def _on_edit(self, interaction: discord.Interaction):
        if interaction.user.id != self._author_id:
            await interaction.response.send_message("Not your share.", ephemeral=True)
            return

        runtime_dir = resolve_share_runtime_dir(parent_channel_id=self._parent_channel_id)
        draft = load_pending_draft(runtime_dir, self._author_id, self._thread_id)
        if not draft:
            await interaction.response.send_message(
                "Share session expired — run `!share` again.",
                ephemeral=True,
            )
            return
        modal = ShareEditModal(
            self._thread_id,
            self._author_id,
            self._target,
            draft.get("display_title") or draft.get("title", ""),
            draft.get("digest") or "",
            parent_channel_id=self._parent_channel_id,
        )
        await interaction.response.send_modal(modal)

    async def _on_cancel(self, interaction: discord.Interaction):
        if interaction.user.id != self._author_id:
            await interaction.response.send_message("Not your share.", ephemeral=True)
            return

        runtime_dir = resolve_share_runtime_dir(parent_channel_id=self._parent_channel_id)
        clear_pending_draft(runtime_dir, self._author_id, self._thread_id)
        await interaction.response.edit_message(
            content="Share cancelled.",
            embed=None,
            view=None,
        )

    async def _on_share(self, interaction: discord.Interaction):
        if interaction.user.id != self._author_id:
            await interaction.response.send_message("Not your share.", ephemeral=True)
            return

        runtime_dir = resolve_share_runtime_dir(parent_channel_id=self._parent_channel_id)
        draft = load_pending_draft(runtime_dir, self._author_id, self._thread_id)
        if not draft:
            await interaction.response.send_message(
                "Share session expired — run `!share` again.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()
        bundle = build_export_bundle_from_draft(draft)
        try:
            if isinstance(self._target, SpaceShareTarget):
                await deliver_space_share(bundle, self._target, client=interaction.client)
            else:
                await deliver_practitioner_share(bundle, self._target, client=interaction.client)
        except Exception as exc:
            await interaction.followup.send(
                f"Share failed: {type(exc).__name__}: {exc}",
                ephemeral=True,
            )
            return

        clear_pending_draft(runtime_dir, self._author_id, self._thread_id)
        for child in self.children:
            child.disabled = True
        label = share_label(bundle)
        try:
            if interaction.message:
                await interaction.message.edit(
                    content=f"📤 Shared **“{label}”** with **{self._target.address}**.",
                    embed=None,
                    view=self,
                )
            else:
                await interaction.edit_original_response(
                    content=f"📤 Shared **“{label}”** with **{self._target.address}**.",
                    embed=None,
                    view=self,
                )
        except discord.HTTPException as exc:
            print(f"Share success edit failed: {type(exc).__name__}: {exc}")
            await interaction.followup.send(
                f"📤 Shared **“{label}”** with **{self._target.address}**.",
                ephemeral=True,
            )


class ShareConfirmView(SharePreviewView):
    """Backward-compatible alias for in-flight share messages."""


class SharePickerView(discord.ui.View):
    """Practitioners + Spaces sections (Slice 1 + 3a)."""

    def __init__(
        self,
        *,
        thread_id: int,
        author_id: int,
        parent_channel_id: int,
        targets: list[ShareTarget],
        space_targets: list[SpaceShareTarget] | None = None,
    ):
        super().__init__(timeout=600)
        if targets:
            self.add_item(
                ShareTargetSelect(
                    thread_id=thread_id,
                    author_id=author_id,
                    parent_channel_id=parent_channel_id,
                    targets=targets,
                )
            )
        if space_targets:
            self.add_item(
                ShareSpaceSelect(
                    thread_id=thread_id,
                    author_id=author_id,
                    parent_channel_id=parent_channel_id,
                    targets=space_targets,
                )
            )




def get_share_bot_client(message: discord.Message | None = None):
    """Discord client for share views — River bot in split mode, else guild client."""
    from mage import river_bot_enabled

    if river_bot_enabled():
        from river_state import river_client

        if getattr(river_client, "is_ready", lambda: False)():
            return river_client
    if message is not None:
        channel = message.channel
        guild = getattr(channel, "guild", None)
        if guild is not None:
            return guild._state._get_client()
    from state import client as turtle_client

    return turtle_client


def register_persistent_share_views(client: discord.Client) -> None:
    """Re-register Continue buttons after restart (inbox bundles on disk)."""
    for mage_key in get_registry().get("mages", {}):
        runtime = runtime_dir_for_mage(mage_key)
        inbox_dir = Path(runtime) / "share" / "inbox"
        if not inbox_dir.is_dir():
            continue
        ch_id = river_channel_for_mage(mage_key)
        if not ch_id:
            continue
        for path in inbox_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            share_id = data.get("share_id") or path.stem
            if not share_id:
                continue
            view = ShareContinueView(share_id, ch_id)
            client.add_view(view)


async def cmd_share(message: discord.Message, args: list[str]) -> None:
    """Start Share eddy flow — picker + confirm (practitioner and space targets)."""
    if not isinstance(message.channel, discord.Thread):
        await message.reply(
            "Use `!share` inside an eddy to send this conversation to another practitioner or space.",
            mention_author=False,
        )
        return

    parent_id = message.channel.parent_id
    if not parent_id:
        await message.reply("Could not resolve parent river.", mention_author=False)
        return

    set_practice_context_for_channel(parent_id)
    from mage import _resolve_mage_from_author, get_mage_address, get_runtime_dir

    author_key, _ = _resolve_mage_from_author(message.author)
    sender_key = author_key or get_mage_key()
    if author_key:
        mage = get_registry().get("mages", {}).get(author_key, {})
        sharer_address = mage.get("address", author_key.replace("_", " ").title())
    else:
        sharer_address = get_mage_address()

    history = reload_history(message.channel.id)
    if len(history) < 2:
        await message.reply(
            "Need a little conversation first — share works once you and Turtle have exchanged a few messages.",
            mention_author=False,
        )
        return

    from commands import thread_configs

    shared_source = shared_eddy_source_for_thread(
        message.channel.id,
        parent_id,
        thread_configs.get(message.channel.id),
    )
    transparency_space_key: str | None = None
    if shared_source:
        space_key = shared_source.get("space_key")
        if not author_key or not space_key or not mage_is_space_member(author_key, space_key):
            await message.reply(
                "Only space members can re-share from a shared family eddy.",
                mention_author=False,
            )
            return
        transparency_space_key = str(space_key)

    targets = list_practitioner_targets(sender_key, message.author.id)
    space_targets = [] if transparency_space_key else list_space_targets(sender_key)
    if not targets and not space_targets:
        await message.reply(
            "No practitioners or spaces are registered to share with yet.",
            mention_author=False,
        )
        return

    title = message.channel.name or "shared eddy"
    share_id = uuid.uuid4().hex[:12]
    draft = {
        "share_id": share_id,
        "title": title,
        "history": history,
        "source_thread_id": message.channel.id,
        "sharer_id": str(message.author.id),
        "sharer_key": sender_key,
        "sharer_address": sharer_address,
    }
    if transparency_space_key:
        draft["transparency_space_key"] = transparency_space_key
        draft["source_origin"] = "shared"
    write_pending_draft(get_runtime_dir(), message.author.id, message.channel.id, draft)

    try:
        from eddy_flow_library import dismiss_eddy_flow_library, dismiss_eddy_flow_library_bar

        await dismiss_eddy_flow_library_bar(message.channel)
        await dismiss_eddy_flow_library(message.channel, parent_id)
    except Exception as exc:
        print(f"Share flow bar dismiss failed: {type(exc).__name__}: {exc}")

    view = SharePickerView(
        thread_id=message.channel.id,
        author_id=message.author.id,
        parent_channel_id=parent_id,
        targets=targets,
        space_targets=space_targets,
    )
    sections: list[str] = []
    if targets:
        names = ", ".join(t.address for t in targets[:6])
        sections.append(f"**Practitioners**\n{names}")
    if space_targets:
        space_names = ", ".join(t.address for t in space_targets[:6])
        sections.append(f"**Spaces**\n{space_names}")
    body = (
        "\n\n".join(sections)
        + "\n\nPick who should receive a digest. Practitioners get a **received eddy**; "
        "spaces get a **shared eddy** in the parent river. Your thread here stays unchanged."
    )
    if transparency_space_key:
        space_label = transparency_space_key.replace("_", " ").title()
        body = (
            f"**Practitioners**\n{', '.join(t.address for t in targets[:6]) if targets else '(none)'}\n\n"
            f"Re-share from this **{space_label}** eddy to a practitioner's private river. "
            f"A transparency act will post in **{space_label}** when you confirm."
        )
    embed = discord.Embed(
        title="Share eddy",
        description=body,
        color=0x3498DB,
    )
    await message.reply(embed=embed, view=view, mention_author=False)
    return "Share eddy picker opened — choose target and confirm."
