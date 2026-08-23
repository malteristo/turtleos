"""Continuity Engine Slice 2 — plain-language theme confirm at checkpoint.

After an eddy note names proposed themes, offer Keep these before
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


def apply_keep_themes(
    practice_dir: str | Path,
    themes: list[str],
    *,
    confirmed_by: str | None = None,
) -> list[str]:
    """Promote confirmed themes into the alive layer. Returns labels kept.

    ``confirmed_by`` carries the practitioner address of whoever pressed Keep.
    In a shared space it is the difference between "the room is tracking this"
    and "Ana is tracking this" — the second is true, the first ventriloquizes.
    """
    kept: list[str] = []
    for label in themes_for_confirm(themes):
        thread = add_active_thread(
            practice_dir,
            label,
            tone="active",
            confirmed_by=confirmed_by,
            source="confirmed",
        )
        kept.append(str(thread.get("label") or label))
    return kept


def address_for_user(user) -> str | None:
    """Registry address for a Discord member, or ``None`` when unregistered.

    An unregistered confirmer is left unattributed rather than guessed at — a
    missing name is honest; an invented one lands in durable state (§6.1).
    """
    try:
        from mage import _MAGE_REGISTRY, _resolve_mage_from_author

        key, _pd = _resolve_mage_from_author(user)
        if not key:
            return None
        entry = (_MAGE_REGISTRY.get("mages") or {}).get(key) or {}
        return str(entry.get("address") or key.capitalize())
    except Exception as exc:
        print(f"Confirm attribution failed: {type(exc).__name__}: {exc}")
        return None


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
    """Keep these — timeout leaves the alive layer unchanged."""

    def __init__(self, channel_id: int, themes: list[str], practice_dir: str):
        super().__init__(timeout=CONFIRM_TIMEOUT_SECONDS)
        self._channel_id = channel_id
        self._themes = themes_for_confirm(themes)
        self._practice_dir = practice_dir
        self._resolved = False

        from runtime.offers import accept_action

        keep_btn = discord.ui.Button(
            label=accept_action("themes_keep").label,
            custom_id=f"ce:theme:keep:{channel_id}",
            style=discord.ButtonStyle.primary,
        )
        keep_btn.callback = self._on_keep
        self.add_item(keep_btn)

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
        kept = apply_keep_themes(
            self._practice_dir,
            self._themes,
            confirmed_by=address_for_user(interaction.user),
        )
        if len(kept) == 1:
            body = f"Kept: **{kept[0]}** — I'll remember this is in motion."
        else:
            joined = ", ".join(kept)
            body = f"Kept: **{joined}** — I'll remember these are in motion."
        from offer_ledger import record_for_channel

        record_for_channel(self._channel_id, kind="themes_keep", event="accepted")
        self.stop()
        await interaction.response.edit_message(content=body, view=None)


async def offer_theme_confirm(
    message,
    themes: list[str],
    *,
    practice_dir: str | None = None,
) -> bool:
    """Post the Keep-these surface. Returns True when a confirm was sent."""
    labels = themes_for_confirm(themes)
    if not labels:
        return False
    from mage import get_pd

    pd = practice_dir or get_pd()
    text = compose_theme_confirm_text(labels)
    view = ContinuityThemeConfirmView(message.channel.id, labels, str(pd))
    await message.reply(text, view=view, mention_author=False)
    from offer_ledger import record_for_channel

    record_for_channel(
        message.channel.id, kind="themes_keep", event="offered", detail=f"{len(labels)} themes"
    )
    return True


def alive_labels(practice_dir: str | Path) -> list[str]:
    """Test/helper — labels currently in motion."""
    return [
        str(t.get("label") or t.get("id") or "").strip()
        for t in list_active_threads(practice_dir)
        if (t.get("label") or t.get("id"))
    ]
