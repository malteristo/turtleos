"""Visible confirmation acts for pending health-record proposals."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import discord

from core.atomic_io import atomic_write_json
from governed_record import pending_proposals
from health_record import confirm_proposal, reject_proposal


class HealthProposalView(discord.ui.View):
    def __init__(self, practice_dir: str, proposal_id: str, *, subject: str, registry: dict):
        super().__init__(timeout=None)
        self.practice_dir = practice_dir
        self.proposal_id = proposal_id
        self.subject = subject
        self.registry = registry
        confirm = discord.ui.Button(
            label="Confirm",
            style=discord.ButtonStyle.success,
            custom_id=f"health:confirm:{proposal_id}",
        )
        reject = discord.ui.Button(
            label="Reject",
            style=discord.ButtonStyle.secondary,
            custom_id=f"health:reject:{proposal_id}",
        )
        confirm.callback = self._confirm
        reject.callback = self._reject
        self.add_item(confirm)
        self.add_item(reject)

    async def _confirm(self, interaction: discord.Interaction) -> None:
        actor = _member_key(self.registry, interaction.user.id)
        if actor != self.subject:
            await interaction.response.send_message(
                "Only the record owner can confirm this change.", ephemeral=True
            )
            return
        result = confirm_proposal(self.practice_dir, self.proposal_id, actor=actor)
        await interaction.response.edit_message(
            content=f"**Applied** · {result.get('reason', 'record update')}", view=None
        )

    async def _reject(self, interaction: discord.Interaction) -> None:
        actor = _member_key(self.registry, interaction.user.id)
        if actor != self.subject:
            await interaction.response.send_message(
                "Only the record owner can reject this change.", ephemeral=True
            )
            return
        result = reject_proposal(self.practice_dir, self.proposal_id, actor=actor)
        await interaction.response.edit_message(
            content=f"**Rejected** · {result.get('reason', 'record update')}", view=None
        )


async def post_pending_health_proposals(
    channel, practice_dir: str, *, subject: str, registry: dict
) -> list[int]:
    posted = []
    for proposal in pending_proposals(practice_dir):
        if proposal.get("presented_at"):
            continue
        message = await channel.send(
            content=_proposal_summary(proposal),
            view=HealthProposalView(
                practice_dir,
                proposal["proposal_id"],
                subject=subject,
                registry=registry,
            ),
        )
        _mark_presented(practice_dir, proposal["proposal_id"], getattr(message, "id", None))
        posted.append(getattr(message, "id", 0))
    return posted


def register_pending_health_views(client, registry: dict) -> int:
    """Rehydrate governed-record buttons selected by primitive capability."""
    from channel_primitives import resolve_primitive

    count = 0
    seen_roots: set[str] = set()
    for channel_id, entry in (registry.get("channels") or {}).items():
        if not isinstance(entry, dict):
            continue
        primitive = resolve_primitive(registry, channel_id)
        if (
            primitive is None
            or not primitive.has("governed_record")
            or not primitive.subject
        ):
            continue
        key = str(entry.get("mage") or "")
        owner = (
            (registry.get("spaces") or {}).get(key)
            if primitive.base == "shared"
            else (registry.get("mages") or {}).get(key)
        )
        if not isinstance(owner, dict):
            continue
        configured_root = str(owner.get("practice_dir") or "").strip()
        if not configured_root:
            continue
        root = str(Path(configured_root).expanduser())
        if root in seen_roots:
            continue
        seen_roots.add(root)
        for proposal in pending_proposals(root):
            client.add_view(
                HealthProposalView(
                    root,
                    proposal["proposal_id"],
                    subject=primitive.subject,
                    registry=registry,
                )
            )
            count += 1
    return count


def _proposal_summary(proposal: dict) -> str:
    operations = proposal.get("operations") or []
    lines = ["**Review a health-record change**", proposal.get("reason") or "Proposed update"]
    for operation in operations[:8]:
        value = operation.get("claim") or operation.get("event") or operation
        text = str(value.get("text") or value.get("correction") or "")
        if text:
            evidence = value.get("evidence") or []
            suffix = f" — {evidence[0]}" if evidence else ""
            lines.append(f"- {text[:350]}{suffix}")
    return "\n".join(lines)


def _mark_presented(practice_dir: str, proposal_id: str, message_id) -> None:
    path = Path(practice_dir) / "record" / "proposals" / f"{proposal_id}.json"
    proposal = json.loads(path.read_text(encoding="utf-8"))
    proposal["presented_at"] = datetime.now(timezone.utc).isoformat()
    proposal["presented_message_id"] = str(message_id or "")
    atomic_write_json(path, proposal, indent=2, lock=True)


def _member_key(registry: dict, discord_id) -> str | None:
    for key, entry in (registry.get("mages") or {}).items():
        if str((entry or {}).get("discord_id") or "") == str(discord_id):
            return str(key)
    return None


async def maybe_capture_checkin(
    message, primitive, *, practice_dir: str, actor: str | None, today
) -> bool:
    """True when this message was the day's check-in and must not start a dialogue turn."""
    if primitive is None or primitive.name != "health" or not primitive.subject:
        return False
    from health_checkin import (
        MODE_STATE,
        ack_text,
        format_observation,
        hint_text,
        is_skip,
        load_config,
        mark_logged,
        message_in_parent,
        parse_reply,
        posted_message_id,
    )
    from health_record import save_observation

    root = practice_dir
    config = load_config(root)
    if not root or not config.enabled:
        return False
    if not message_in_parent(message):
        return False
    if actor != primitive.subject:
        return False
    text = (getattr(message, "content", None) or "").strip()
    if config.mode == MODE_STATE:
        return await _capture_state_reply(
            message,
            primitive,
            root=root,
            actor=actor,
            today=today,
            locale=config.locale,
            text=text,
        )
    locale = config.locale
    if is_skip(text):
        mark_logged(root, today)
        await message.channel.send("Heute ausgesetzt." if locale == "de" else "Skipped today.")
        return True
    entry = parse_reply(text, questions=config.questions, flags=config.flags)
    prompt_id = posted_message_id(root, today)
    ref = getattr(getattr(message, "reference", None), "message_id", None)
    answering_prompt = bool(prompt_id and ref and str(ref) == str(prompt_id))
    if entry is None:
        if answering_prompt:
            await message.channel.send(
                hint_text(
                    locale=locale,
                    questions=config.questions,
                    flags=config.flags,
                )
            )
            return True
        return False
    result = save_observation(
        root,
        primitive=primitive,
        actor=actor,
        text=format_observation(entry, today, questions=config.questions),
    )
    if result.get("decision") != "applied":
        return False
    mark_logged(root, today)
    await message.channel.send(ack_text(entry, locale=locale))
    return True


async def _capture_state_reply(
    message,
    primitive,
    *,
    root: str,
    actor: str,
    today,
    locale: str,
    text: str,
) -> bool:
    from health_checkin import (
        already_logged,
        classify_state_capture,
        mark_logged,
        posted_draft,
        posted_message_id,
        state_ack,
    )
    from health_record import save_observation

    prompt_id = posted_message_id(root, today)
    ref = getattr(getattr(message, "reference", None), "message_id", None)
    draft = posted_draft(root, today)
    capture = classify_state_capture(
        text,
        in_parent=True,
        already_logged=already_logged(root, today),
        references_prompt=bool(prompt_id and ref and str(ref) == str(prompt_id)),
        has_draft=bool(draft),
    )
    if capture is None:
        return False
    if capture.kind == "skip":
        mark_logged(root, today)
        await message.channel.send("Heute ausgesetzt." if locale == "de" else "Skipped today.")
        return True
    if capture.kind == "confirm":
        saved = draft
        verdict = "confirmed"
        turtle_draft = None
    elif capture.kind == "correct":
        saved = capture.text
        verdict = "corrected"
        turtle_draft = draft
    else:
        saved = capture.text
        verdict = None
        turtle_draft = None
    if not saved:
        return False
    result = save_observation(
        root,
        primitive=primitive,
        actor=actor,
        text=saved,
        verdict=verdict,
        turtle_draft=turtle_draft,
    )
    if result.get("decision") != "applied":
        return False
    mark_logged(root, today)
    await message.channel.send(state_ack(capture.kind, locale=locale))
    return True
