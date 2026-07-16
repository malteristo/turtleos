"""River act harness — TURTLE_SPEC §5, §12.

Turns inbound river messages into structured acts (never prose).
Gated by attunement profile `native` in mage_registry.yaml.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any

import discord

from llm import chat_ollama
from mage import get_pd
from practice_io import read_safe

RIVER_MODEL = None  # set from state on import


def _river_model() -> str:
    from state import RIVER_MODEL as model

    return model


DEFAULT_FLOW_NAMES = ["Navigator", "Thread", "Companion"]

RIVER_PROMPT_FALLBACK = """You classify river messages into structured acts only.
Output a single JSON object: {"acts": [...]} — no prose, no markdown fences.
A standing eddy bar at the channel bottom handles materialize — parent river messages get acknowledge/flow acts only.
Act types: acknowledge, offer_flow_menu, offer_flow, error.
Do NOT emit offer_eddy in the parent river channel.
"""


def load_river_prompt(practice_dir: str | None = None) -> str:
    base = practice_dir or get_pd()
    for rel in ("character/river_prompt.md", "template/character/river_prompt.md"):
        path = os.path.join(base, rel)
        content = read_safe(path)
        if content.strip():
            return content
    repo_template = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "template",
        "character",
        "river_prompt.md",
    )
    content = read_safe(repo_template)
    return content.strip() or RIVER_PROMPT_FALLBACK


def list_installed_flows(practice_dir: str | None = None) -> list[str]:
    base = practice_dir or get_pd()
    flows_dir = os.path.join(base, "flows")
    names: list[str] = []
    if os.path.isdir(flows_dir):
        for name in sorted(os.listdir(flows_dir)):
            if name.endswith(".md") and not name.startswith("_"):
                names.append(name[:-3].replace("_", " ").title())
    return names or list(DEFAULT_FLOW_NAMES)


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def parse_river_output(raw: str) -> tuple[list[dict[str, Any]], str | None]:
    """Parse model output into acts. Returns (acts, rejection_reason)."""
    if not raw or not raw.strip():
        return [], "empty output"

    cleaned = _strip_json_fences(raw)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\"acts\"[\s\S]*\}", cleaned)
        if not match:
            return [], "prose or non-JSON (rejected)"
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return [], "invalid JSON"

    if not isinstance(data, dict):
        return [], "root is not an object"

    acts = data.get("acts")
    if not isinstance(acts, list):
        return [], "missing acts array"

    normalized: list[dict[str, Any]] = []
    for item in acts:
        if isinstance(item, dict) and item.get("type"):
            normalized.append(item)

    if not normalized:
        return [], "no valid acts"

    return normalized, None


def finalize_parent_river_acts(acts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Strip model offer_eddy/acknowledge — standing eddy bar handles materialize."""
    return [a for a in acts if a.get("type") not in ("offer_eddy", "acknowledge", "revise_offer")]


def fallback_acts(reason: str = "River model unavailable") -> list[dict[str, Any]]:
    return finalize_parent_river_acts([
        {
            "type": "error",
            "embed": {
                "title": "River degraded",
                "description": reason,
            },
        },
    ])


async def classify_river_acts(content: str, practice_dir: str | None = None) -> list[dict[str, Any]]:
    """Call the River model and return normalized act list."""
    prompt = load_river_prompt(practice_dir)
    user = content.strip() or "(empty message)"
    try:
        raw = await chat_ollama(
            prompt,
            [{"role": "user", "content": user}],
            model=_river_model(),
            num_ctx=8192,
            think=False,
        )
    except Exception as exc:
        print(f"River model error: {type(exc).__name__}: {exc}")
        return fallback_acts(f"River model error: {type(exc).__name__}")

    acts, reason = parse_river_output(raw)
    if reason:
        print(f"River harness rejected output: {reason} — raw[:200]={raw[:200]!r}")
        return fallback_acts("Could not parse river acts; offering materialize only.")

    return finalize_parent_river_acts(acts)


def _append_chronicle(practice_dir: str, surface: str, deep: dict | None = None) -> None:
    chronicle_dir = os.path.join(practice_dir, "chronicle")
    os.makedirs(chronicle_dir, exist_ok=True)
    surface_path = os.path.join(chronicle_dir, "surface.md")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"- {ts} {surface}\n"
    with open(surface_path, "a", encoding="utf-8") as fh:
        fh.write(line)
    if deep is not None:
        deep_path = os.path.join(chronicle_dir, "deep.jsonl")
        with open(deep_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": ts, **deep}, ensure_ascii=False) + "\n")


def _flow_display_name(flow_id: str) -> str:
    return flow_id.replace("_", " ").title()


async def _spawn_eddy_from_anchor(
    channel: discord.abc.Messageable,
    *,
    flow_id: str | None = None,
    initiator: discord.abc.User | None = None,
) -> discord.Thread | None:
    """Spawn blank eddy via anchor message so Discord renders the thread list embed."""
    from eddy_spawn import spawn_river_eddy

    anchor = await channel.send("\u200b", silent=True)
    initiator_id = initiator.id if initiator else None
    return await spawn_river_eddy(anchor, flow_id=flow_id, initiator_id=initiator_id)


async def _materialize_from_bar(
    interaction: discord.Interaction,
    *,
    flow_id: str | None = None,
) -> None:
    """Delete bar, spawn eddy (Discord thread embed), repost bar at bottom."""
    channel = interaction.channel
    if not channel:
        await interaction.followup.send("Could not find river channel.", ephemeral=True)
        return
    client = interaction.client
    try:
        await interaction.message.delete()
    except discord.HTTPException as exc:
        print(f"Eddy bar delete failed: {exc}")
    try:
        thread = await _spawn_eddy_from_anchor(
            channel, flow_id=flow_id, initiator=interaction.user
        )
    except Exception as exc:
        print(f"Eddy bar spawn failed: {type(exc).__name__}: {exc}")
        await reconcile_river_bar_floor(channel, client)
        await interaction.followup.send(
            "Could not open eddy — try again or use `!thread`.",
            ephemeral=True,
        )
        return
    if not thread:
        await reconcile_river_bar_floor(channel, client)
        await interaction.followup.send("Could not open eddy.", ephemeral=True)
        return
    await reconcile_river_bar_floor(channel, client)


def _river_bar_custom_ids(channel_id: int) -> tuple[str, str]:
    return f"river:bar:new:{channel_id}", f"river:bar:more:{channel_id}"


def message_looks_like_river_bar(message, channel_id: int) -> bool:
    """True when a timeline message is (or was) a standing river bar."""
    content = (getattr(message, "content", None) or "").strip("\u200b").strip()
    if content:
        return False
    custom_ids: list[str] = []
    for row in getattr(message, "components", None) or []:
        children = getattr(row, "children", None) or getattr(row, "components", None) or []
        for child in children:
            cid = getattr(child, "custom_id", None)
            if cid:
                custom_ids.append(str(cid))
    if not custom_ids:
        return False
    new_id, more_id = _river_bar_custom_ids(channel_id)
    for cid in custom_ids:
        if cid == new_id or cid == more_id or cid.startswith("river:bar:"):
            return True
        if cid.startswith(f"river:act:{channel_id}:"):
            return True
    return False


class RiverEddyBarView(discord.ui.View):
    """Standing bottom bar — launch pad: new eddy + more (artifacts · help)."""

    def __init__(self, channel_id: int):
        super().__init__(timeout=None)
        self._channel_id = channel_id
        new_id, more_id = _river_bar_custom_ids(channel_id)
        new_btn = discord.ui.Button(
            label="new eddy",
            custom_id=new_id,
            style=discord.ButtonStyle.secondary,
            emoji="🌀",
        )
        new_btn.callback = self._on_new_eddy
        self.add_item(new_btn)

        more = discord.ui.Select(
            placeholder="more…",
            custom_id=more_id,
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label="artifacts",
                    value="artifacts",
                    emoji="📂",
                    description="Browse recent practice artifacts",
                ),
                discord.SelectOption(
                    label="help",
                    value="help",
                    emoji="❓",
                    description="Command summary (only you see this)",
                ),
            ],
        )
        more.callback = self._on_more
        self.add_item(more)

    async def _on_new_eddy(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await _materialize_from_bar(interaction)

    async def _on_more(self, interaction: discord.Interaction):
        if interaction.channel.id != self._channel_id:
            await interaction.response.send_message("Wrong channel.", ephemeral=True)
            return
        values = (interaction.data or {}).get("values") or []
        choice = values[0] if values else ""
        if choice == "help":
            from commands import _river_help_body

            body = _river_help_body()
            await interaction.response.send_message(
                f"📋 **Commands**\n{body}",
                ephemeral=True,
            )
            return
        if choice == "artifacts":
            from bar_anchor import hold_river_bar
            from eddy_lifecycle_bar import _run_river_act_command

            hold_river_bar(self._channel_id)
            await interaction.response.defer()
            await _run_river_act_command(interaction, "artifacts", [])
            return
        await interaction.response.send_message("Unknown option.", ephemeral=True)


class RiverEddyView(discord.ui.View):
    """Materialize-eddy button wired to native river spawn."""

    def __init__(
        self,
        source_message: discord.Message,
        label: str,
        flow_id: str | None = None,
    ):
        super().__init__(timeout=None)
        self._source = source_message
        self._flow_id = flow_id
        custom_id = f"river:eddy:{source_message.channel.id}:{source_message.id}"
        button = discord.ui.Button(
            label=label[:80],
            custom_id=custom_id,
            style=discord.ButtonStyle.secondary,
            emoji="🌀",
        )
        button.callback = self._on_press
        self.add_item(button)

    async def _on_press(self, interaction: discord.Interaction):
        from eddy_spawn import spawn_river_eddy

        await interaction.response.defer(ephemeral=True)
        try:
            thread = await spawn_river_eddy(self._source, flow_id=self._flow_id)
        except Exception as exc:
            print(f"River eddy button failed: {type(exc).__name__}: {exc}")
            await interaction.followup.send(
                "Could not materialize eddy — try again or use `!thread`.",
                ephemeral=True,
            )
            return
        if not thread:
            await interaction.followup.send("Could not materialize eddy.", ephemeral=True)
            return
        try:
            await interaction.message.delete()
        except discord.HTTPException as exc:
            print(f"River offer message delete failed: {exc}")
        await ensure_bar_at_bottom(interaction.channel, interaction.client)


class RiverFlowMenuView(discord.ui.View):
    """Contextual flow menu on a practitioner river message."""

    def __init__(self, flows: list[str], source_message: discord.Message):
        super().__init__(timeout=3600)
        self._source = source_message
        for flow in flows[:4]:
            flow_id = flow.strip().lower().replace(" ", "_")
            btn = discord.ui.Button(
                label=flow[:80],
                style=discord.ButtonStyle.primary,
                custom_id=f"river:flow:{source_message.id}:{flow_id[:20]}",
            )
            btn.callback = self._make_flow_callback(flow_id)
            self.add_item(btn)

    def _make_flow_callback(self, flow_id: str):
        async def callback(interaction: discord.Interaction):
            from eddy_spawn import spawn_river_eddy

            await interaction.response.defer(ephemeral=True)
            try:
                thread = await spawn_river_eddy(self._source, flow_id=flow_id)
            except Exception as exc:
                print(f"River flow button failed: {exc}")
                await interaction.followup.send("Could not open flow eddy.", ephemeral=True)
                return
            if not thread:
                await interaction.followup.send("Could not open flow eddy.", ephemeral=True)
                return
            try:
                await interaction.message.delete()
            except discord.HTTPException as exc:
                print(f"River flow menu delete failed: {exc}")
            client = interaction.client
            if interaction.channel:
                await ensure_bar_at_bottom(interaction.channel, client)

        return callback


async def _reply_with_view(message: discord.Message, view: discord.ui.View) -> None:
    """Reply to practitioner message with a button-only River post."""
    await message.reply("\u200b", view=view, mention_author=False)


async def render_acts(
    message: discord.Message,
    acts: list[dict[str, Any]],
    *,
    practice_dir: str | None = None,
) -> dict[str, Any]:
    """Render acts to Discord. Returns summary for logging."""
    practice_dir = practice_dir or get_pd()
    summary: dict[str, Any] = {"acts": [a.get("type") for a in acts], "views": 0}

    for act in acts:
        kind = act.get("type")
        if kind == "acknowledge":
            continue

        elif kind == "offer_flow_menu":
            flows = act.get("flows") or list_installed_flows(practice_dir)
            view = RiverFlowMenuView(flows, message)
            await message.reply("-# Choose a flow:", view=view, mention_author=False)
            summary["views"] += 1

        elif kind == "offer_flow":
            flow_id = (act.get("flow_id") or "navigator").strip()
            label = f"Open {flow_id.title()}"
            view = RiverEddyView(message, label=label, flow_id=flow_id)
            await _reply_with_view(message, view)
            summary["views"] += 1

        elif kind == "error":
            embed_data = act.get("embed") or {}
            embed = discord.Embed(
                title=embed_data.get("title", "Error"),
                description=embed_data.get("description", ""),
                color=0xED4245,
            )
            await message.channel.send(embed=embed, silent=True)

        elif kind == "chronicle":
            surface = act.get("surface", "")
            jump = act.get("jump_url")
            if jump and surface:
                surface = f"{surface} ({jump})"
            if surface:
                _append_chronicle(practice_dir, surface, act.get("deep"))

        elif kind == "present_artifacts":
            from artifact_presenter import ArtifactIntent, compose_artifact_surface, reply_artifact_surface
            from artifact_viewer import mark_artifacts_ui_unlocked
            from mage import get_mage_type

            mark_artifacts_ui_unlocked("river_act")
            intent_raw = (act.get("intent") or "browse_default").lower()
            intent_map = {
                "browse_default": ArtifactIntent.BROWSE_DEFAULT,
                "browse_shelf": ArtifactIntent.BROWSE_SHELF,
                "browse_all": ArtifactIntent.BROWSE_ALL,
            }
            intent = intent_map.get(intent_raw, ArtifactIntent.BROWSE_DEFAULT)
            surface = compose_artifact_surface(
                intent,
                mage_type=get_mage_type(),
                shelf_key=act.get("shelf"),
            )
            await reply_artifact_surface(message, surface)
            summary["views"] += 1

    _append_chronicle(
        practice_dir,
        f"river message {message.id}",
        {"message_id": message.id, "acts": summary["acts"]},
    )
    return summary


def _eddy_bar_state_path() -> str:
    from mage import _resolve_primary_runtime_dir

    river_dir = os.path.join(_resolve_primary_runtime_dir(), "thread-state", "river")
    os.makedirs(river_dir, exist_ok=True)
    return os.path.join(river_dir, "eddy_bar.json")


def _load_eddy_bar_state() -> dict[str, int]:
    from mage import workshop_runtime_roots

    merged: dict[str, int] = {}
    for runtime_dir in workshop_runtime_roots():
        path = os.path.join(runtime_dir, "thread-state", "river", "eddy_bar.json")
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            for key, val in data.items():
                sk = str(key)
                iv = int(val)
                if sk not in merged or iv > merged[sk]:
                    merged[sk] = iv
        except (json.JSONDecodeError, TypeError, ValueError, OSError):
            continue
    return merged


def _save_eddy_bar_message(channel_id: int, message_id: int) -> None:
    state = _load_eddy_bar_state()
    state[str(channel_id)] = message_id
    path = _eddy_bar_state_path()
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(state, fh)


async def _resolve_client_channel(client, channel_id: int):
    ch = client.get_channel(channel_id)
    if ch is not None:
        return ch
    try:
        return await client.fetch_channel(channel_id)
    except discord.HTTPException:
        return None


async def _iter_river_channels(client) -> list:
    """Resolve live Discord channels for every active practice parent.

    Includes shared-river / hosted-river — not only the operator dialogue channel.
    Skips archived and orphaned registry rows.
    """
    from mage import practice_parent_channel_ids

    channels = []
    for ch_id in practice_parent_channel_ids():
        ch = await _resolve_client_channel(client, ch_id)
        if ch is not None:
            channels.append(ch)
    return channels


async def _remove_legacy_eddy_door(channel) -> None:
    """Remove pinned Eddy Door messages from earlier river UX."""
    try:
        async for msg in channel.history(limit=50):
            if not msg.embeds:
                continue
            title = msg.embeds[0].title or ""
            if title.startswith("🌀 Eddy Door"):
                try:
                    await msg.unpin()
                except discord.HTTPException:
                    pass
                try:
                    await msg.delete()
                except discord.HTTPException:
                    pass
                print(f"Removed legacy eddy door in #{getattr(channel, 'name', channel.id)}")
    except discord.HTTPException:
        pass


_RIVER_BAR_HISTORY_SCAN = 40


async def post_river_eddy_bar(channel, client) -> discord.Message | None:
    """Post the standing new-eddy bar as the channel's last message."""
    from bar_anchor import channel_for_client

    ch = await channel_for_client(channel, client)
    view = RiverEddyBarView(ch.id)
    try:
        msg = await ch.send("\u200b", view=view, silent=True)
    except discord.HTTPException as exc:
        print(f"Eddy bar post failed for {ch.id}: {exc}")
        return None
    _save_eddy_bar_message(ch.id, msg.id)
    client.add_view(view)
    return msg


async def _delete_river_bar_orphans(channel, channel_id: int) -> int:
    """Delete standing-bar messages in recent history. Returns count deleted."""
    deleted = 0
    try:
        async for msg in channel.history(limit=_RIVER_BAR_HISTORY_SCAN):
            if not message_looks_like_river_bar(msg, channel_id):
                continue
            try:
                await msg.delete()
                deleted += 1
            except discord.HTTPException:
                pass
    except discord.HTTPException as exc:
        print(f"River bar orphan scan failed for {channel_id}: {exc}")
    return deleted


async def reconcile_river_bar_floor(channel, client) -> None:
    """Global floor invariant: at most one river bar, last in the channel."""
    from bar_anchor import channel_for_client, is_river_bar_held

    ch = await channel_for_client(channel, client)
    if is_river_bar_held(ch.id):
        return

    await _delete_river_bar_orphans(ch, ch.id)
    await post_river_eddy_bar(ch, client)


async def ensure_bar_at_bottom(
    channel,
    client,
    *,
    after_message_id: int | None = None,
) -> None:
    """Backward-compatible entry — schedules debounced reconcile (or immediate).

    ``after_message_id`` is ignored; reconcile always sweeps orphans. Callers that
    need an immediate settle should use ``reconcile_river_bar_floor``.
    """
    del after_message_id  # placement law is global reconcile, not message-relative
    from bar_anchor import schedule_river_bar_reconcile

    schedule_river_bar_reconcile(channel, client)


async def ensure_river_eddy_bar(client) -> None:
    """Deploy the standing eddy bar at the bottom of each river channel."""
    for channel in await _iter_river_channels(client):
        await _remove_legacy_eddy_door(channel)
        await reconcile_river_bar_floor(channel, client)
        print(f"Eddy bar ready in #{getattr(channel, 'name', channel.id)}")


async def sweep_river_bar_floors(client) -> None:
    """Periodic safety reconcile for all river channels."""
    for channel in await _iter_river_channels(client):
        try:
            await reconcile_river_bar_floor(channel, client)
        except Exception as exc:
            print(f"River bar sweep failed for {getattr(channel, 'id', '?')}: {exc}")


async def handle_eddy_first_message(message: discord.Message) -> bool:
    """Rename blank eddy from the practitioner's first message. Returns True if handled."""
    from eddy_spawn import (
        generate_topic,
        is_awaiting_flow_intake,
        pop_awaiting_title,
    )
    from thread_registry import update_thread_context_type, update_thread_name

    thread = message.channel
    if not isinstance(thread, discord.Thread):
        return False
    parent_id = thread.parent_id
    if not parent_id:
        return False
    if is_awaiting_flow_intake(thread.id, parent_id):
        return False

    awaiting = pop_awaiting_title(thread.id, parent_id)
    if not awaiting:
        return False

    flow_id = awaiting.get("flow_id")
    content = message.content.strip()
    if message.attachments and not content:
        content = f"(attachment: {message.attachments[0].filename})"

    from eddy_spawn import river_add_turtle_to_eddy

    await river_add_turtle_to_eddy(thread)

    title = await generate_topic(content or "check-in")
    try:
        await thread.edit(name=title[:100])
    except discord.HTTPException as exc:
        print(f"Eddy rename failed: {exc}")
        title = thread.name

    update_thread_name(thread.id, title)
    if flow_id:
        update_thread_context_type(thread.id, flow_id)

    try:
        from commands import thread_configs

        cfg = thread_configs.setdefault(thread.id, {})
        cfg["topic"] = title
        cfg["awaiting_title"] = False
        cfg["blank_eddy"] = False
        if flow_id and not cfg.get("context_type"):
            cfg["context_type"] = flow_id
    except Exception:
        pass

    practice_dir = get_pd()
    _append_chronicle(
        practice_dir,
        f"🌀 named: {title} ({thread.jump_url})",
        {"thread_id": str(thread.id), "message_id": message.id, "title": title},
    )
    print(f"Eddy renamed: {thread.id} → {title!r}")
    return True


def _river_client_for_channel(channel):
    from mage import river_bot_enabled

    if river_bot_enabled():
        from river_state import river_client

        return river_client
    return channel.guild._state._get_client() if channel.guild else None


async def handle_river_message(message: discord.Message) -> None:
    """Entry point for native river channel messages (acts only, no Turtle prose)."""
    content = message.content.strip()
    if message.attachments and not content:
        content = f"(attachment: {message.attachments[0].filename})"

    bar_client = _river_client_for_channel(message.channel)

    # Continuation breath — settle floor without River model round-trip.
    if content in {".", "..", "...", "go", "continue", "next"}:
        if bar_client:
            from bar_anchor import schedule_river_bar_reconcile

            schedule_river_bar_reconcile(message.channel, bar_client)
        return

    acts = await classify_river_acts(content)
    summary = await render_acts(message, acts)
    print(f"River [{message.author.display_name}]: {summary['acts']} views={summary['views']}")

    if bar_client:
        from bar_anchor import schedule_river_bar_reconcile

        schedule_river_bar_reconcile(message.channel, bar_client)
