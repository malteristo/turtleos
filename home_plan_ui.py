"""River pin card + offer views for pinned home eddies.

Honesty: Continue / Open / Stop pinning — river pin tray discovery only.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import discord

from home_plans import (
    HomePlanError,
    bind_home,
    clear_plan,
    get_by_eddy,
    get_by_id,
    set_pin_message,
    touch_plan,
)

PIN_CARD_COLOR = 0x57F287  # Discord green — distinct from ops grey
OFFER_TIMEOUT = 300
STOP_CONFIRM_TIMEOUT = 60
PIN_CARD_BUTTON_LABELS = ("Continue", "Open", "Stop pinning")


def compose_pin_card_embed(plan: dict[str, Any]) -> discord.Embed:
    title = str(plan.get("title") or "Working plan")
    updated = plan.get("updated_at") or plan.get("created_at") or ""
    desc_parts = ["Home eddy · Continue anytime from this pin."]
    if updated:
        try:
            # Show date portion only
            day = str(updated)[:10]
            desc_parts.insert(0, f"Updated {day}")
        except Exception:
            pass
    embed = discord.Embed(
        title=f"📌 {title}",
        description="\n".join(desc_parts),
        color=PIN_CARD_COLOR,
    )
    path = plan.get("artifact_path") or ""
    if path:
        embed.set_footer(text=f"File · {path}")
    return embed


def build_pin_card_view(
    plan: dict[str, Any],
    *,
    continue_url: str | None,
    open_url: str | None,
) -> discord.ui.View:
    """Continue (link) + Open (link or disabled) + Stop pinning."""
    view = HomePlanPinView(str(plan.get("id") or ""), timeout=None)
    if continue_url:
        view.add_item(
            discord.ui.Button(
                label="Continue",
                style=discord.ButtonStyle.link,
                url=continue_url,
            )
        )
    else:
        # Fallback ack button when jump URL unavailable
        cont = discord.ui.Button(
            label="Continue",
            style=discord.ButtonStyle.primary,
            custom_id=f"homeplan:continue:{plan.get('id')}",
        )
        cont.callback = view._on_continue_ack
        view.add_item(cont)

    if open_url:
        view.add_item(
            discord.ui.Button(
                label="Open",
                style=discord.ButtonStyle.link,
                url=open_url,
            )
        )
    else:
        open_btn = discord.ui.Button(
            label="Open",
            style=discord.ButtonStyle.secondary,
            custom_id=f"homeplan:open:{plan.get('id')}",
        )
        open_btn.callback = view._on_open_path
        view.add_item(open_btn)

    stop = discord.ui.Button(
        label="Stop pinning",
        style=discord.ButtonStyle.danger,
        custom_id=f"homeplan:stop:{plan.get('id')}",
    )
    stop.callback = view._on_stop
    view.add_item(stop)
    return view


def pin_card_payload_labels(view: discord.ui.View) -> list[str]:
    """Test helper — button labels on a pin card view."""
    labels: list[str] = []
    for item in view.children:
        label = getattr(item, "label", None)
        if label:
            labels.append(str(label))
    return labels


class HomePlanPinView(discord.ui.View):
    def __init__(self, plan_id: str, *, timeout: float | None = None):
        super().__init__(timeout=timeout)
        self._plan_id = plan_id

    async def _on_continue_ack(self, interaction: discord.Interaction) -> None:
        from mage import get_pd

        plan = get_by_id(get_pd(), self._plan_id)
        if not plan:
            await interaction.response.send_message(
                "That working plan is no longer pinned.", ephemeral=True
            )
            return
        eddy_id = plan.get("home_eddy_id")
        await interaction.response.send_message(
            f"Open the home eddy for **{plan.get('title')}** "
            f"(thread id `{eddy_id}`) from your river pin tray.",
            ephemeral=True,
        )

    async def _on_open_path(self, interaction: discord.Interaction) -> None:
        from mage import get_pd
        from practice_io import artifact_read_url

        plan = get_by_id(get_pd(), self._plan_id)
        if not plan:
            await interaction.response.send_message(
                "That working plan is no longer pinned.", ephemeral=True
            )
            return
        path = str(plan.get("artifact_path") or "")
        url = artifact_read_url(path) if path else None
        if url:
            await interaction.response.send_message(
                f"Open: {url}", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"Read with `!read {path}` in an eddy.", ephemeral=True
            )

    async def _on_stop(self, interaction: discord.Interaction) -> None:
        confirm = HomePlanStopConfirmView(self._plan_id)
        await interaction.response.send_message(
            "Stop pinning this working plan? The file stays; the river card goes away.",
            view=confirm,
            ephemeral=True,
        )


class HomePlanStopConfirmView(discord.ui.View):
    def __init__(self, plan_id: str):
        super().__init__(timeout=STOP_CONFIRM_TIMEOUT)
        self._plan_id = plan_id
        yes = discord.ui.Button(
            label="Stop pinning",
            style=discord.ButtonStyle.danger,
            custom_id=f"homeplan:stopconfirm:{plan_id}",
        )
        yes.callback = self._confirm
        no = discord.ui.Button(
            label="Keep pin",
            style=discord.ButtonStyle.secondary,
            custom_id=f"homeplan:stopcancel:{plan_id}",
        )
        no.callback = self._cancel
        self.add_item(yes)
        self.add_item(no)

    async def _confirm(self, interaction: discord.Interaction) -> None:
        from mage import get_pd
        from state import client

        pd = get_pd()
        plan = clear_plan(pd, self._plan_id)
        if not plan:
            await interaction.response.edit_message(
                content="Already unpinned.", view=None
            )
            return
        msg_id = plan.get("river_pin_message_id")
        ch_id = plan.get("river_channel_id")
        if msg_id and ch_id and client:
            try:
                ch = client.get_channel(int(ch_id)) or await client.fetch_channel(
                    int(ch_id)
                )
                msg = await ch.fetch_message(int(msg_id))
                try:
                    await msg.unpin(reason="Stop pinning working plan")
                except Exception:
                    pass
                try:
                    await msg.edit(
                        content=f"Unpinned: **{plan.get('title')}** (file kept).",
                        embed=None,
                        view=None,
                    )
                except Exception:
                    pass
            except Exception as exc:
                print(f"home_plan stop unpin failed: {exc}")
        await interaction.response.edit_message(
            content=f"Stopped pinning **{plan.get('title')}**. File kept.",
            view=None,
        )

    async def _cancel(self, interaction: discord.Interaction) -> None:
        await interaction.response.edit_message(
            content="Pin kept.", view=None
        )


class HomePlanOfferView(discord.ui.View):
    """Keep as working plan — same bind path as !pin in eddy."""

    def __init__(
        self,
        *,
        channel_id: int,
        river_channel_id: int,
        title: str,
        body: str | None,
        practice_dir: str,
    ):
        super().__init__(timeout=OFFER_TIMEOUT)
        self._channel_id = channel_id
        self._river_channel_id = river_channel_id
        self._title = title
        self._body = body
        self._practice_dir = practice_dir
        self._resolved = False
        keep = discord.ui.Button(
            label="Keep as working plan",
            style=discord.ButtonStyle.primary,
            custom_id=f"homeplan:offer:{channel_id}",
        )
        keep.callback = self._on_keep
        self.add_item(keep)
        skip = discord.ui.Button(
            label="Not now",
            style=discord.ButtonStyle.secondary,
            custom_id=f"homeplan:offer_skip:{channel_id}",
        )
        skip.callback = self._on_skip
        self.add_item(skip)

    async def _on_keep(self, interaction: discord.Interaction) -> None:
        if self._resolved:
            await interaction.response.send_message("Already answered.", ephemeral=True)
            return
        self._resolved = True
        try:
            plan = await bind_and_post_pin(
                practice_dir=self._practice_dir,
                title=self._title,
                home_eddy_id=self._channel_id,
                river_channel_id=self._river_channel_id,
                body=self._body,
                discord_client=interaction.client,
            )
        except HomePlanError as exc:
            await interaction.response.edit_message(content=str(exc), view=None)
            return
        except Exception as exc:
            await interaction.response.edit_message(
                content=f"Could not pin working plan: {exc}", view=None
            )
            return
        await interaction.response.edit_message(
            content=(
                f"Pinned **{plan.get('title')}** on your river — "
                "Continue anytime from the pin tray."
            ),
            view=None,
        )

    async def _on_skip(self, interaction: discord.Interaction) -> None:
        if self._resolved:
            await interaction.response.send_message("Already answered.", ephemeral=True)
            return
        self._resolved = True
        await interaction.response.edit_message(content="Okay — not pinned.", view=None)


def resolve_pin_client(message=None, discord_client=None):
    """Client that must post/pin the river card — River when split, else message client.

    Never use the Turtle ``state.client`` from the River process: it is not
    logged-in there and Discord awaits land on ``_MissingSentinel`` (no ``is_set``).
    """
    if discord_client is not None:
        return discord_client
    try:
        from mage import river_bot_enabled
        from river_state import river_client

        if river_bot_enabled() and river_client is not None:
            ready = getattr(river_client, "is_ready", None)
            if callable(ready) and ready():
                return river_client
            # River process: prefer river_client even before is_ready races settle
            if getattr(river_client, "user", None) is not None:
                return river_client
    except Exception:
        pass
    if message is not None:
        getter = getattr(getattr(message, "_state", None), "_get_client", None)
        if callable(getter):
            live = getter()
            if live is not None:
                return live
    from state import client as global_client

    return global_client


async def bind_and_post_pin(
    *,
    practice_dir: str,
    title: str,
    home_eddy_id: int,
    river_channel_id: int,
    body: str | None = None,
    artifact_path: str | None = None,
    discord_client=None,
    message=None,
    refresh_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Bind (unless refresh) + post/pin river card. Returns plan dict."""
    import discord as discord_mod
    from practice_io import artifact_read_url

    dc = resolve_pin_client(message=message, discord_client=discord_client)
    if dc is None:
        raise HomePlanError("No Discord client available to post the river pin.")
    if refresh_plan:
        plan = dict(refresh_plan)
        touch_plan(practice_dir, str(plan["id"]))
        plan = get_by_id(practice_dir, str(plan["id"])) or plan
        # First-attempt bind may have left a skeleton before pin post failed —
        # fill from eddy body when the file is still a placeholder.
        if body and body.strip() and plan.get("artifact_path"):
            from pathlib import Path

            abs_path = Path(practice_dir) / str(plan["artifact_path"])
            try:
                current = abs_path.read_text(encoding="utf-8") if abs_path.is_file() else ""
            except OSError:
                current = ""
            if (
                not current.strip()
                or "Working plan — edit with Turtle" in current
                or len(current) < 80
            ):
                clean = body.strip()
                if not clean.lstrip().startswith("#"):
                    clean = f"# {plan.get('title') or title}\n\n{clean}"
                if not clean.endswith("\n"):
                    clean += "\n"
                from atomic_io import atomic_write_text

                atomic_write_text(abs_path, clean)
    else:
        plan = bind_home(
            practice_dir,
            title=title,
            home_eddy_id=home_eddy_id,
            river_channel_id=river_channel_id,
            artifact_path=artifact_path,
            body=body,
        )

    river = dc.get_channel(int(river_channel_id))
    if river is None:
        river = await dc.fetch_channel(int(river_channel_id))

    # Resolve home thread for Continue URL; unarchive if needed.
    continue_url = None
    try:
        thread = dc.get_channel(int(home_eddy_id))
        if thread is None:
            thread = await dc.fetch_channel(int(home_eddy_id))
        if isinstance(thread, discord_mod.Thread):
            if thread.archived:
                try:
                    await thread.edit(archived=False, reason="Home plan Continue")
                except Exception as exc:
                    print(f"home_plan unarchive: {exc}")
            continue_url = getattr(thread, "jump_url", None)
    except Exception as exc:
        print(f"home_plan continue url: {exc}")

    open_url = artifact_read_url(str(plan.get("artifact_path") or ""))
    embed = compose_pin_card_embed(plan)
    view = build_pin_card_view(plan, continue_url=continue_url, open_url=open_url)

    # Idempotent refresh: edit existing pin message if present.
    msg = None
    old_id = plan.get("river_pin_message_id")
    if old_id:
        try:
            msg = await river.fetch_message(int(old_id))
            await msg.edit(embed=embed, view=view)
        except Exception:
            msg = None

    if msg is None:
        msg = await river.send(embed=embed, view=view, silent=True)
        try:
            await msg.pin(reason=f"Working plan: {plan.get('title')}")
        except discord_mod.Forbidden as exc:
            raise HomePlanError(
                "Cannot pin on the river — bot needs **Manage Messages** / pin permission."
            ) from exc
        except discord_mod.HTTPException as exc:
            raise HomePlanError(f"Pin failed: {exc}") from exc

    set_pin_message(practice_dir, str(plan["id"]), msg.id)
    plan = get_by_id(practice_dir, str(plan["id"])) or plan

    try:
        dc.add_view(HomePlanPinView(str(plan["id"]), timeout=None))
    except Exception as exc:
        print(f"home_plan add_view: {exc}")

    return plan


async def offer_home_plan(
    message,
    *,
    title: str,
    body: str | None = None,
    practice_dir: str | None = None,
) -> bool:
    """Post Keep as working plan offer in an eddy. Returns True if offered."""
    import discord as discord_mod
    from mage import get_pd

    if not isinstance(message.channel, discord_mod.Thread):
        return False
    pd = practice_dir or get_pd()
    if get_by_eddy(pd, message.channel.id):
        return False
    parent_id = message.channel.parent_id
    if not parent_id:
        return False
    view = HomePlanOfferView(
        channel_id=message.channel.id,
        river_channel_id=parent_id,
        title=title,
        body=body,
        practice_dir=pd,
    )
    await message.reply(
        f"Keep **{title}** as a working plan? "
        "Pins a card on your river — Continue opens this home eddy.",
        view=view,
        mention_author=False,
    )
    return True


def format_updated_subtitle(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        return f"Updated {dt.date().isoformat()}"
    except Exception:
        return f"Updated {str(iso)[:10]}"
