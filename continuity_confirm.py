"""Continuity Engine Slice 2 — plain-language theme confirm at checkpoint.

After an eddy note names proposed themes, offer Keep these / Not now before
anything enters the alive layer. Vocabulary firewall: never say alive.yaml,
knot, substrate, or Continuity Engine in practitioner-facing copy.
"""

from __future__ import annotations

from pathlib import Path

import discord

from continuity_engine import add_active_thread, list_active_threads

CONFIRM_TIMEOUT_SECONDS = 180
_MAX_THEMES = 3


def themes_for_confirm(proposed: list[str] | None) -> list[str]:
    """Sanitize proposal list for the confirm surface (already normalized upstream)."""
    kept: list[str] = []
    seen: set[str] = set()
    for raw in proposed or []:
        label = " ".join((raw or "").split())
        if not label:
            continue
        key = label.lower()
        if key in seen:
            continue
        seen.add(key)
        kept.append(label)
        if len(kept) >= _MAX_THEMES:
            break
    return kept


def apply_keep_themes(practice_dir: str | Path, themes: list[str]) -> list[str]:
    """Promote confirmed themes into the alive layer. Returns labels kept."""
    kept: list[str] = []
    for label in themes_for_confirm(themes):
        thread = add_active_thread(practice_dir, label, tone="active")
        kept.append(str(thread.get("label") or label))
    return kept


def compose_theme_confirm_text(themes: list[str]) -> str:
    labels = themes_for_confirm(themes)
    if not labels:
        return ""
    if len(labels) == 1:
        bullet = f"• {labels[0]}"
        lead = "Before you go — this feels live right now:"
    else:
        bullet = "\n".join(f"• {t}" for t in labels)
        lead = "Before you go — these feel live right now:"
    return (
        f"{lead}\n{bullet}\n\n"
        "Keep them in mind for next time?"
    )


class ContinuityThemeConfirmView(discord.ui.View):
    """Keep these / Not now — timeout leaves the alive layer unchanged."""

    def __init__(self, channel_id: int, themes: list[str], practice_dir: str):
        super().__init__(timeout=CONFIRM_TIMEOUT_SECONDS)
        self._channel_id = channel_id
        self._themes = themes_for_confirm(themes)
        self._practice_dir = practice_dir
        self._resolved = False

        keep_btn = discord.ui.Button(
            label="Keep these",
            custom_id=f"ce:theme:keep:{channel_id}",
            style=discord.ButtonStyle.primary,
        )
        keep_btn.callback = self._on_keep
        self.add_item(keep_btn)

        skip_btn = discord.ui.Button(
            label="Not now",
            custom_id=f"ce:theme:skip:{channel_id}",
            style=discord.ButtonStyle.secondary,
        )
        skip_btn.callback = self._on_skip
        self.add_item(skip_btn)

    async def on_timeout(self) -> None:
        self._resolved = True

    async def _on_keep(self, interaction: discord.Interaction) -> None:
        if self._resolved:
            await interaction.response.send_message(
                "Already answered.", ephemeral=True
            )
            return
        if interaction.channel and interaction.channel.id != self._channel_id:
            await interaction.response.send_message("Wrong thread.", ephemeral=True)
            return
        self._resolved = True
        kept = apply_keep_themes(self._practice_dir, self._themes)
        if len(kept) == 1:
            body = f"Kept: **{kept[0]}** — I'll remember this is in motion."
        else:
            joined = ", ".join(kept)
            body = f"Kept: **{joined}** — I'll remember these are in motion."
        self.stop()
        await interaction.response.edit_message(content=body, view=None)

    async def _on_skip(self, interaction: discord.Interaction) -> None:
        if self._resolved:
            await interaction.response.send_message(
                "Already answered.", ephemeral=True
            )
            return
        if interaction.channel and interaction.channel.id != self._channel_id:
            await interaction.response.send_message("Wrong thread.", ephemeral=True)
            return
        self._resolved = True
        self.stop()
        await interaction.response.edit_message(
            content="Okay — nothing carried forward from this checkpoint.",
            view=None,
        )


async def offer_theme_confirm(
    message,
    themes: list[str],
    *,
    practice_dir: str | None = None,
) -> bool:
    """Post the Keep these / Not now surface. Returns True when a confirm was sent."""
    labels = themes_for_confirm(themes)
    if not labels:
        return False
    from mage import get_pd

    pd = practice_dir or get_pd()
    text = compose_theme_confirm_text(labels)
    view = ContinuityThemeConfirmView(message.channel.id, labels, str(pd))
    await message.reply(text, view=view, mention_author=False)
    return True


def alive_labels(practice_dir: str | Path) -> list[str]:
    """Test/helper — labels currently in motion."""
    return [
        str(t.get("label") or t.get("id") or "").strip()
        for t in list_active_threads(practice_dir)
        if (t.get("label") or t.get("id"))
    ]
