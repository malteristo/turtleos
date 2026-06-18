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


DEFAULT_FLOW_NAMES = ["Shelter", "Navigator", "Thread", "Companion"]

RIVER_PROMPT_FALLBACK = """You classify river messages into structured acts only.
Output a single JSON object: {"acts": [...]} — no prose, no markdown fences.
A pinned Eddy Door handles materialize — parent river messages get acknowledge/flow acts only.
Act types: acknowledge, revise_offer, offer_flow_menu, offer_flow, error.
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


def ensure_offer_eddy(acts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if any(a.get("type") == "offer_eddy" for a in acts):
        return acts
    return [
        *acts,
        {
            "type": "offer_eddy",
            "button_label": "Materialize eddy",
        },
    ]


def finalize_parent_river_acts(acts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Strip model offer_eddy/acknowledge — shell posts offer_eddy reply only."""
    return [a for a in acts if a.get("type") not in ("offer_eddy", "acknowledge")]


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

    # Model must not emit offer_eddy (standing door + prompt). Shell re-adds per-message
    # materialize button so practitioners get a contextual button on every river post.
    return ensure_offer_eddy(finalize_parent_river_acts(acts))


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


class RiverEddyDoorView(discord.ui.View):
    """Persistent standing door — materialize blank eddy without a river message."""

    def __init__(self, channel_id: int):
        super().__init__(timeout=None)
        self._channel_id = channel_id
        button = discord.ui.Button(
            label="Materialize eddy",
            custom_id=f"river:door:{channel_id}",
            style=discord.ButtonStyle.secondary,
            emoji="🌀",
        )
        button.callback = self._on_press
        self.add_item(button)

    async def _on_press(self, interaction: discord.Interaction):
        from eddy_spawn import spawn_blank_river_eddy

        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        if not channel:
            await interaction.followup.send("Could not find river channel.", ephemeral=True)
            return
        try:
            thread = await spawn_blank_river_eddy(channel)
        except Exception as exc:
            print(f"Eddy door failed: {type(exc).__name__}: {exc}")
            await interaction.followup.send(
                "Could not materialize eddy — try again or use `!thread`.",
                ephemeral=True,
            )
            return
        if not thread:
            await interaction.followup.send("Could not materialize eddy.", ephemeral=True)
            return
        # Success: thread appears in sidebar — no ephemeral followup.


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


class RiverFlowMenuView(discord.ui.View):
    def __init__(self, flows: list[str], source_message: discord.Message):
        super().__init__(timeout=3600)
        self._source = source_message
        for flow in flows[:4]:
            btn = discord.ui.Button(
                label=flow[:80],
                style=discord.ButtonStyle.primary,
                custom_id=f"river:flow:{flow[:20]}",
            )
            btn.callback = self._make_flow_callback(flow)
            self.add_item(btn)

    def _make_flow_callback(self, flow_name: str):
        async def callback(interaction: discord.Interaction):
            from eddy_spawn import spawn_blank_river_eddy

            await interaction.response.defer(ephemeral=True)
            channel = interaction.channel
            if not channel:
                await interaction.followup.send("Could not find river channel.", ephemeral=True)
                return
            try:
                thread = await spawn_blank_river_eddy(
                    channel,
                    flow_id=flow_name.lower(),
                )
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

        elif kind == "offer_eddy":
            label = act.get("button_label") or "Materialize eddy"
            view = RiverEddyView(message, label=label)
            await _reply_with_view(message, view)
            summary["views"] += 1

        elif kind == "revise_offer":
            label = act.get("button_label") or "Materialize eddy"
            view = RiverEddyView(message, label=label[:80])
            await _reply_with_view(message, view)
            summary["views"] += 1

        elif kind == "offer_flow_menu":
            flows = act.get("flows") or list_installed_flows(practice_dir)
            view = RiverFlowMenuView(flows, message)
            await message.reply("-# Choose a flow:", view=view, mention_author=False)
            summary["views"] += 1

        elif kind == "offer_flow":
            flow_id = (act.get("flow_id") or "shelter").strip()
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

    _append_chronicle(
        practice_dir,
        f"river message {message.id}",
        {"message_id": message.id, "acts": summary["acts"]},
    )
    return summary


def _eddy_door_state_path(practice_dir: str | None = None) -> str:
    from mage import get_runtime_dir

    river_dir = os.path.join(get_runtime_dir(), "thread-state", "river")
    os.makedirs(river_dir, exist_ok=True)
    return os.path.join(river_dir, "eddy_door.json")


def _load_eddy_door_state() -> dict[str, int]:
    path = _eddy_door_state_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return {str(k): int(v) for k, v in data.items()}
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


def _save_eddy_door_message(channel_id: int, message_id: int) -> None:
    state = _load_eddy_door_state()
    state[str(channel_id)] = message_id
    path = _eddy_door_state_path()
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(state, fh)


def _iter_river_channels(client) -> list:
    from mage import get_registry, get_channel, get_attunement_profile

    channels = []
    seen: set[int] = set()
    reg = get_registry()
    for ch_id_str, entry in reg.get("channels", {}).items():
        ch_type = entry.get("type") if isinstance(entry, dict) else None
        if ch_type in ("river", "hosted-river"):
            try:
                ch_id = int(ch_id_str)
            except (ValueError, TypeError):
                continue
            ch = client.get_channel(ch_id)
            if ch and ch_id not in seen:
                channels.append(ch)
                seen.add(ch_id)
    dialogue = get_channel("dialogue")
    if dialogue and get_attunement_profile() == "native" and dialogue.id not in seen:
        channels.append(dialogue)
    return channels


async def _channel_has_eddy_door(channel) -> bool:
    state = _load_eddy_door_state()
    msg_id = state.get(str(channel.id))
    if msg_id:
        try:
            msg = await channel.fetch_message(msg_id)
            return bool(msg)
        except discord.HTTPException:
            pass
    try:
        async for msg in channel.pins():
            for embed in msg.embeds or []:
                if embed.title and embed.title.startswith("🌀 Eddy Door"):
                    _save_eddy_door_message(channel.id, msg.id)
                    return True
    except discord.HTTPException:
        pass
    return False


async def ensure_eddy_door(client) -> None:
    """Deploy and pin the standing Materialize eddy door in each river channel."""
    for channel in _iter_river_channels(client):
        if await _channel_has_eddy_door(channel):
            client.add_view(RiverEddyDoorView(channel.id))
            print(f"Eddy door already present in #{getattr(channel, 'name', channel.id)}")
            continue
        embed = discord.Embed(
            title="🌀 Eddy Door",
            description="Open a focused conversation with Turtle.",
            color=0x5865F2,
        )
        view = RiverEddyDoorView(channel.id)
        try:
            msg = await channel.send(embed=embed, view=view)
            _save_eddy_door_message(channel.id, msg.id)
            client.add_view(view)
            try:
                await msg.pin()
                print(f"Eddy door deployed and pinned in #{getattr(channel, 'name', channel.id)}")
            except discord.HTTPException as exc:
                print(f"Eddy door deployed (pin failed: {exc})")
        except discord.HTTPException as exc:
            print(f"Eddy door deploy failed for {channel.id}: {exc}")


async def handle_eddy_first_message(message: discord.Message) -> bool:
    """Rename blank eddy from the practitioner's first message. Returns True if handled."""
    from eddy_spawn import generate_topic, pop_awaiting_title
    from thread_registry import update_thread_name

    thread = message.channel
    if not isinstance(thread, discord.Thread):
        return False
    parent_id = thread.parent_id
    if not parent_id:
        return False
    if not pop_awaiting_title(thread.id, parent_id):
        return False

    content = message.content.strip()
    if message.attachments and not content:
        content = f"(attachment: {message.attachments[0].filename})"

    title = await generate_topic(content or "check-in")
    try:
        await thread.edit(name=title[:100])
    except discord.HTTPException as exc:
        print(f"Eddy rename failed: {exc}")
        title = thread.name

    update_thread_name(thread.id, title)
    try:
        from commands import thread_configs

        if thread.id in thread_configs:
            thread_configs[thread.id]["topic"] = title
            thread_configs[thread.id]["awaiting_title"] = False
            thread_configs[thread.id]["blank_eddy"] = False
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


async def handle_river_message(message: discord.Message) -> None:
    """Entry point for native river channel messages (acts only, no Turtle prose)."""
    content = message.content.strip()
    if message.attachments and not content:
        content = f"(attachment: {message.attachments[0].filename})"

    acts = await classify_river_acts(content)
    summary = await render_acts(message, acts)
    print(f"River [{message.author.display_name}]: {summary['acts']} views={summary['views']}")
