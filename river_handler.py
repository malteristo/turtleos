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
Do NOT emit offer_eddy in the parent channel.
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
    from river_house import attach_house_to_prompt, gather_house_facts, withhold_offers

    facts = gather_house_facts()
    prompt = attach_house_to_prompt(load_river_prompt(practice_dir), facts)
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

    return withhold_offers(finalize_parent_river_acts(acts), facts)


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
    """Delete bar, spawn eddy (Discord thread embed), repost bar at bottom.

    In a magic room, Summon always opens a new session. Other unreleased
    spirits are named in the greeting. They do not stop the summon.
    """
    channel = interaction.channel
    if not channel:
        await interaction.followup.send("Could not find this channel.", ephemeral=True)
        return
    company = await _workshop_company(channel)
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
            "Could not open eddy — try again.",
            ephemeral=True,
        )
        return
    if not thread:
        await reconcile_river_bar_floor(channel, client)
        await interaction.followup.send("Could not open eddy.", ephemeral=True)
        return
    await reconcile_river_bar_floor(channel, client)
    await _greet_summon(thread, channel, interaction.user, company=company)


def _owner_checkout(channel_id):
    """The owner's workshop checkout, when they have one.

    A home room does not grant the workshop. The checkout is the person's.
    Another member, with none, gets None, and their session stays in the channel.
    """
    from pathlib import Path

    from mage import get_registry
    from room_connections import owner_of
    from workshop_tools import checkout_for

    try:
        registry = get_registry()
    except Exception:
        return None
    owner = owner_of(registry, channel_id) if registry else None
    if not owner:
        return None
    root = checkout_for(registry, owner)
    return root if isinstance(root, Path) else None


async def _open_home_session(interaction: discord.Interaction) -> None:
    """A piece of work in this home channel. Not a summon.

    The owner's session can work on the platform when they have a workshop.
    Another member's session stays in the channel.
    """
    channel = interaction.channel
    if channel is None or not offers_session(getattr(channel, "id", None)):
        await interaction.followup.send("A session starts from home.", ephemeral=True)
        return
    client = interaction.client
    try:
        await interaction.message.delete()
    except discord.HTTPException as exc:
        print(f"Session bar delete failed: {exc}")
    try:
        thread = await _spawn_eddy_from_anchor(channel, initiator=interaction.user)
    except Exception as exc:
        print(f"Session open failed: {type(exc).__name__}: {exc}")
        await reconcile_river_bar_floor(channel, client)
        await interaction.followup.send("Could not open the session.", ephemeral=True)
        return
    if not thread:
        await reconcile_river_bar_floor(channel, client)
        await interaction.followup.send("Could not open the session.", ephemeral=True)
        return
    root = _owner_checkout(channel.id)
    if root is not None:
        try:
            from boom_takeup import mark_platform_session
            from mage import get_runtime_dir

            mark_platform_session(get_runtime_dir(), thread.id)
        except Exception as exc:
            print(f"Platform session mark failed: {type(exc).__name__}: {exc}")
        await _name_session(thread, channel, root)
        await thread.send(HOME_SESSION_PLATFORM)
    else:
        try:
            from eddy_spawn import pop_awaiting_title
            from thread_registry import update_thread_name

            await thread.edit(name="session")
            update_thread_name(thread.id, "session")
            pop_awaiting_title(thread.id, channel.id)
        except Exception as exc:
            print(f"Session naming failed: {type(exc).__name__}: {exc}")
        await thread.send(HOME_SESSION)
    await reconcile_river_bar_floor(channel, client)


async def _active_parent_threads(channel) -> list:
    """Threads of this channel the guild currently has open."""
    guild = getattr(channel, "guild", None)
    if guild is None:
        return list(getattr(channel, "threads", []) or [])
    try:
        return list(await guild.active_threads())
    except Exception as exc:
        print(f"Summon active threads failed: {type(exc).__name__}: {exc}")
        return list(getattr(channel, "threads", []) or [])


async def _workshop_company(channel) -> str:
    """Names of unreleased spirits in this room. Empty when the room has no workshop.

    This never refuses a summon. The caller opens the session either way.
    """
    from mage import channel_has_capability, get_pd, set_practice_context_for_channel

    if not channel_has_capability(channel.id, "workshop"):
        return ""
    set_practice_context_for_channel(channel.id)
    from magic_session import pick_session
    from session_record import is_released

    practice = get_pd()
    rows = []
    for thread in await _active_parent_threads(channel):
        if getattr(thread, "parent_id", None) != channel.id:
            continue
        rows.append({
            "id": thread.id,
            "name": getattr(thread, "name", "") or str(thread.id),
            "archived": bool(getattr(thread, "archived", False)),
            "released": is_released(practice, thread.id),
        })
    return pick_session(rows)["text"]


async def _greet_summon(thread, channel, user, company: str = "") -> None:
    """In a room with a workshop, the new thread opens on the pair, naming the release."""
    from mage import channel_has_capability

    if not channel_has_capability(channel.id, "workshop"):
        return
    try:
        from eddy_spawn import river_add_spirit_to_eddy, river_add_turtle_to_eddy
        from mage import get_pd
        from magic_prompt import greeting
        from magic_session import BRIEFING, apply_stand, briefing_digest
        from session_record import append_event
        from workshop_tools import room_checkout

        try:
            await river_add_turtle_to_eddy(thread)
            await river_add_spirit_to_eddy(thread)
        except Exception as exc:
            print(f"Summon join failed: {type(exc).__name__}: {exc}")
        root = room_checkout(channel.id, getattr(user, "id", None))
        stood = apply_stand(root) if root is not None else ""
        note = "\n".join(part for part in (company, stood) if part)
        text = greeting(root, stand=note)
        await thread.send(text)
    except Exception as exc:
        print(f"Summon greeting failed: {type(exc).__name__}: {exc}")
        return
    try:
        digest = briefing_digest(root / BRIEFING) if root is not None else "missing"
        append_event(get_pd(), thread.id, kind="greeting", actor="river", text=text, briefing=digest)
    except Exception as exc:
        print(f"Summon greeting record failed: {type(exc).__name__}: {exc}")
    await _name_session(thread, channel, root)


async def _name_session(thread, channel, root) -> None:
    """A session in a workshop room is named at Summon and never retitled from its first words.

    `...` and `.` are River gestures that return before the title step, so a session that opens
    with either stayed "new eddy" for good. The name is the number, the release and the day.
    """
    if root is None:
        return
    try:
        from commands import thread_configs
        from eddy_spawn import pop_awaiting_title
        from magic_prompt import session_name
        from thread_registry import load_registry, update_thread_name

        name = session_name(root, load_registry().get("threads") or {}, channel.id, thread.id)
        await thread.edit(name=name[:100])
        update_thread_name(thread.id, name)
        pop_awaiting_title(thread.id, channel.id)
        cfg = thread_configs.setdefault(thread.id, {})
        cfg["topic"] = name
        cfg["awaiting_title"] = False
        cfg["blank_eddy"] = False
    except Exception as exc:
        print(f"Session naming failed: {type(exc).__name__}: {exc}")


async def open_drop_thread(anchor, *, title: str, kind: str, preface: str = "") -> bool:
    """Open the eddy on his message and ask the room's voice to answer it.

    False when Discord would not open the thread. The caller says so.
    """
    from eddy_spawn import (
        patch_pending_native_eddy,
        pop_awaiting_title,
        river_add_spirit_to_eddy,
        river_add_turtle_to_eddy,
        spawn_river_eddy,
    )
    from first_eddy_handoff import write_first_eddy_handoff
    from mage import get_runtime_dir
    from parent_intake import SESSION_OPENED
    from thread_registry import update_thread_name

    thread = await spawn_river_eddy(anchor)
    if thread is None:
        return False
    parent_id = anchor.channel.id
    named = False
    if kind == "session":
        from workshop_tools import room_checkout

        author = getattr(anchor, "author", None)
        root = room_checkout(parent_id, getattr(author, "id", None))
        if root is not None:
            await _name_session(thread, anchor.channel, root)
            named = True
    if not named:
        await thread.edit(name=title[:100])
        update_thread_name(thread.id, title)
        pop_awaiting_title(thread.id, parent_id)
    try:
        from commands import thread_configs

        cfg = thread_configs.get(thread.id)
        if isinstance(cfg, dict):
            cfg["awaiting_title"] = False
            cfg["blank_eddy"] = False
            cfg["topic"] = title
    except Exception:
        pass
    patch_pending_native_eddy(
        thread.id,
        parent_id,
        {"awaiting_title": False, "blank_eddy": False, "topic": title},
    )
    if preface:
        await thread.send(preface[:1800])
    if kind == "session":
        await thread.send(SESSION_OPENED)
    await river_add_turtle_to_eddy(thread)
    if kind == "session":
        await river_add_spirit_to_eddy(thread)
    write_first_eddy_handoff(
        thread.id, parent_id, anchor.id, runtime_dir=get_runtime_dir()
    )
    if kind == "boom":
        from boom_takeup import post_takeup_button

        try:
            await post_takeup_button(thread)
        except Exception as exc:
            print(f"Take this up button failed: {type(exc).__name__}: {exc}")
    return True


async def open_taken_up(interaction) -> None:
    """The press of Take this up. Bound into the button so the button stays a leaf."""
    import boom_takeup
    from channel_primitives import resolve_primitive
    from mage import get_pd, get_registry, get_runtime_dir, set_practice_context_for_channel
    from pathlib import Path
    from room_connections import owner_of

    thread = interaction.channel
    parent = getattr(thread, "parent", None)
    if parent is None:
        await interaction.followup.send("This button belongs on a Boom eddy.", ephemeral=True)
        return
    registry = get_registry()
    primitive = resolve_primitive(registry, parent.id)
    if primitive is None or primitive.name != "craft":
        await interaction.followup.send("This button belongs on a Boom eddy.", ephemeral=True)
        return
    client = interaction.client
    runtime_dir = get_runtime_dir()
    set_practice_context_for_channel(parent.id)
    try:
        practice = Path(get_pd())
    except Exception:
        practice = None
    existing = boom_takeup.load_session(runtime_dir, thread.id)
    if existing is not None:
        session = await boom_takeup._fetch(client, existing)
        released = False
        if practice is not None and session is not None:
            from session_record import is_released

            released = is_released(practice, existing)
        if boom_takeup.still_open(
            found=session is not None,
            archived=bool(getattr(session, "archived", False)),
            released=released,
        ):
            await thread.send(boom_takeup.eddy_line(boom_takeup._url(session), already=True))
            return
    owner = owner_of(registry, parent.id)
    home_id = boom_takeup.home_channel_id(registry, owner) if owner else None
    if not home_id:
        await thread.send(boom_takeup.COULD_NOT)
        return
    home = await boom_takeup._fetch(client, int(home_id))
    if home is None:
        await thread.send(boom_takeup.COULD_NOT)
        return
    river = getattr(client, "user", None)
    words, reply, note = await boom_takeup.gather_packet(
        thread,
        river_id=getattr(river, "id", None),
        practice_dir=practice,
    )
    opened = await _open_taken_session(
        home,
        text=boom_takeup.carry_text(words=words, reply=reply, note=note),
        user_id=getattr(interaction.user, "id", None),
        runtime_dir=runtime_dir,
    )
    if opened is None:
        await thread.send(boom_takeup.COULD_NOT)
        return
    boom_takeup.save_session(runtime_dir, thread.id, opened.id)
    await thread.send(boom_takeup.eddy_line(boom_takeup._url(opened), already=False))


async def _open_taken_session(home, *, text: str, user_id: int | None, runtime_dir: str):
    from eddy_spawn import river_add_spirit_to_eddy, river_add_turtle_to_eddy, spawn_river_eddy
    from first_eddy_handoff import write_first_eddy_handoff

    anchor = await home.send(text)
    thread = await spawn_river_eddy(anchor, initiator_id=user_id)
    if thread is None:
        return None
    root = _owner_checkout(home.id)
    if root is not None:
        from boom_takeup import mark_platform_session

        mark_platform_session(runtime_dir, thread.id)
        await _name_session(thread, home, root)
    else:
        try:
            from eddy_spawn import pop_awaiting_title
            from thread_registry import update_thread_name

            await thread.edit(name="session")
            update_thread_name(thread.id, "session")
            pop_awaiting_title(thread.id, home.id)
        except Exception as exc:
            print(f"Session naming failed: {type(exc).__name__}: {exc}")
    await river_add_turtle_to_eddy(thread)
    await river_add_spirit_to_eddy(thread)
    write_first_eddy_handoff(thread.id, home.id, anchor.id, runtime_dir=runtime_dir)
    return thread


def install_takeup() -> None:
    from boom_takeup import bind_house

    bind_house(open_taken_up)


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


HOME_SESSION = "This is a session. A piece of work, in this channel."
HOME_SESSION_PLATFORM = "This is a session. It can work on turtleOS, and the workshop keeps it."


def offers_session(channel_id: int) -> bool:
    """A home feed can start a piece of work. Every other room cannot."""
    from mage import get_channel_primitive

    primitive = get_channel_primitive(channel_id)
    return bool(primitive and primitive.name == "private")


def _bar_face(channel_id: int) -> tuple[str, bool, str]:
    """(label, is_primary, emoji) of the standing button: Summon where a workshop is, else new eddy."""
    from mage import channel_has_capability

    if channel_has_capability(channel_id, "workshop"):
        return "Summon", True, "✨"
    return "new eddy", False, "🌀"


class RiverEddyBarView(discord.ui.View):
    """Standing bottom bar — launch pad: new eddy + more (commands, the ones this channel keeps, mcp, model)."""

    def __init__(self, channel_id: int):
        super().__init__(timeout=None)
        self._channel_id = channel_id
        new_id, more_id = _river_bar_custom_ids(channel_id)
        label, primary, emoji = _bar_face(channel_id)
        new_btn = discord.ui.Button(
            label=label,
            custom_id=new_id,
            style=discord.ButtonStyle.primary if primary else discord.ButtonStyle.secondary,
            emoji=emoji,
        )
        new_btn.callback = self._on_new_eddy
        self.add_item(new_btn)

        if offers_session(channel_id):
            session_btn = discord.ui.Button(
                label="session",
                custom_id=f"river:bar:session:{channel_id}",
                style=discord.ButtonStyle.secondary,
            )
            session_btn.callback = self._on_session
            self.add_item(session_btn)

        from bar_menu import menu_options, pins
        from cloud_fallback import house_dir

        more = discord.ui.Select(
            placeholder="more…",
            custom_id=more_id,
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label=label, value=value, description=description)
                for value, label, description in menu_options(pins(house_dir(), channel_id))
            ],
        )
        more.callback = self._on_more
        self.add_item(more)

    async def _on_new_eddy(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await _materialize_from_bar(interaction)

    async def _on_session(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await _open_home_session(interaction)

    async def _on_more(self, interaction: discord.Interaction):
        if interaction.channel.id != self._channel_id:
            await interaction.response.send_message("Wrong channel.", ephemeral=True)
            return
        values = (interaction.data or {}).get("values") or []
        choice = values[0] if values else ""
        if choice == "commands":
            from mage import get_mage_type
            from room_models import open_commands_private

            await open_commands_private(interaction, operator=get_mage_type() != "practitioner")
            return
        from bar_menu import pins
        from cloud_fallback import house_dir

        if choice in pins(house_dir(), self._channel_id):
            from eddy_lifecycle_bar import _run_river_act_command

            await interaction.response.defer()
            await _run_river_act_command(interaction, choice, [])
            return
        if choice == "mcp":
            from outgoing_connect_ui import open_list

            await open_list(interaction)
            return
        if choice == "model":
            from core.models import conversation_model
            from room_models import open_private

            await open_private(interaction, default=conversation_model())
            return
        # A bar posted before this menu changed may still offer a choice that is gone.
        await interaction.response.send_message(
            "That menu has changed. Open it again to see what is there now.", ephemeral=True
        )


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
                "Could not materialize eddy — try again.",
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


class ThreadDisplayView(discord.ui.View):
    """One Open link per named eddy. No prose."""

    def __init__(self, specs: list[dict[str, str]]):
        super().__init__(timeout=86400)
        for spec in specs:
            self.add_item(
                discord.ui.Button(
                    style=discord.ButtonStyle.link,
                    label=spec["label"],
                    url=spec["url"],
                )
            )


class ChannelMenuView(discord.ui.View):
    """Controls the channel primitive named. Same tools as the standing bar."""

    def __init__(self, specs: list[dict[str, str]], source: discord.Message):
        super().__init__(timeout=86400)
        self._source = source
        self._channel_id = source.channel.id
        for spec in specs:
            button = discord.ui.Button(
                label=spec["label"],
                custom_id=f"river:menu:{spec['id']}:{self._channel_id}",
                style=discord.ButtonStyle.secondary,
            )
            button.callback = self._callback_for(spec["id"])
            self.add_item(button)

    def _callback_for(self, key: str):
        async def callback(interaction: discord.Interaction):
            if key in ("new_eddy", "summon"):
                await interaction.response.defer()
                await _materialize_from_bar(interaction)
                return
            if key == "threads":
                await interaction.response.defer()
                await _reply_thread_display(self._source, days=None)
                return
            if key == "artifacts":
                from bar_anchor import hold_river_bar
                from eddy_lifecycle_bar import _run_river_act_command

                hold_river_bar(self._channel_id)
                await interaction.response.defer()
                await _run_river_act_command(interaction, "artifacts", [])
                return
            await interaction.response.send_message("Unknown control.", ephemeral=True)

        return callback


async def _reply_thread_display(message: discord.Message, *, days: int | None) -> None:
    """The same card as `!eddy`; a spoken window is a filter, not a new list."""
    from cmd_threads import post_eddies

    await post_eddies(message, days=days)


async def _reply_waiting_display(message: discord.Message) -> None:
    """Only rows waiting for a session or a word. Not another inventory."""
    from core.craft_readiness import waiting_glance_rows
    from mage import get_runtime_dir
    from river_display import (
        BUTTON_ROW,
        compose_waiting_body,
        thread_button_specs,
        waiting_title,
    )
    from state import EMBED_COLORS
    from thread_registry import load_registry

    source = message.channel
    if isinstance(source, discord.Thread):
        source = source.parent
    records = waiting_glance_rows(
        get_runtime_dir(),
        load_registry().get("threads", {}),
        parent_name=getattr(source, "name", None),
        parent_id=getattr(source, "id", None),
    )
    embed = discord.Embed(
        title=waiting_title(records),
        description=compose_waiting_body(records) or None,
        color=EMBED_COLORS["help"],
    )
    guild_id = getattr(getattr(message, "guild", None), "id", None)
    specs = thread_button_specs(records, guild_id=guild_id)
    view = ThreadDisplayView(specs) if specs else None
    if len(records) > BUTTON_ROW:
        embed.set_footer(text="Session first, then you")
    await message.reply(embed=embed, view=view, mention_author=False)


async def _reply_channel_menu(message: discord.Message) -> None:
    from mage import get_channel_primitive
    from river_display import channel_menu_specs
    from state import EMBED_COLORS

    primitive = get_channel_primitive(message.channel.id)
    name = primitive.name if primitive else "channel"
    controls = primitive.parent_controls if primitive else ("new_eddy",)
    embed = discord.Embed(title=f"{name} channel", color=EMBED_COLORS["help"])
    view = ChannelMenuView(channel_menu_specs(controls), message)
    await message.reply(embed=embed, view=view, mention_author=False)


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

        elif kind == "show_threads":
            days = act.get("days")
            try:
                days = int(days) if days is not None else None
            except (TypeError, ValueError):
                days = None
            await _reply_thread_display(message, days=days)
            summary["views"] += 1

        elif kind == "show_waiting":
            await _reply_waiting_display(message)
            summary["views"] += 1

        elif kind == "show_channel_menu":
            await _reply_channel_menu(message)
            summary["views"] += 1

        elif kind == "file_intake":
            from craft_intake import schedule_craft_intake

            client = _river_client_for_channel(message.channel)
            if client is None:
                from state import client as fallback_client

                client = fallback_client
            if client:
                await schedule_craft_intake(message, client)
                summary["filed"] = True

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


def _eddy_bar_state_path_for_channel(channel_id: int) -> str:
    """INT-050: bar state lives under the channel's own runtime root, not primary."""
    from mage import _normalized_dir, _resolve_runtime_dir_for_channel

    runtime_dir = _normalized_dir(_resolve_runtime_dir_for_channel(channel_id))
    river_dir = os.path.join(runtime_dir, "thread-state", "river")
    os.makedirs(river_dir, exist_ok=True)
    return os.path.join(river_dir, "eddy_bar.json")


def _load_eddy_bar_file(path: str) -> dict[str, int]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        out: dict[str, int] = {}
        for key, val in data.items():
            out[str(key)] = int(val)
        return out
    except (json.JSONDecodeError, TypeError, ValueError, OSError):
        return {}


def _load_eddy_bar_state() -> dict[str, int]:
    """Merge bar anchors across roots for read-side lookup (legacy callers)."""
    from mage import workshop_runtime_roots

    merged: dict[str, int] = {}
    for runtime_dir in workshop_runtime_roots():
        path = os.path.join(runtime_dir, "thread-state", "river", "eddy_bar.json")
        for key, val in _load_eddy_bar_file(path).items():
            if key not in merged or val > merged[key]:
                merged[key] = val
    return merged


def _channels_for_runtime(runtime_dir: str) -> set[str]:
    """Channel ids whose registry runtime resolves to ``runtime_dir``."""
    from mage import (
        _normalized_dir,
        _resolve_runtime_dir_for_channel,
        practice_parent_channel_ids,
    )

    target = _normalized_dir(runtime_dir)
    owned: set[str] = set()
    for ch_id in practice_parent_channel_ids():
        if _normalized_dir(_resolve_runtime_dir_for_channel(ch_id)) == target:
            owned.add(str(ch_id))
    return owned


def _save_eddy_bar_message(channel_id: int, message_id: int) -> None:
    """Persist one channel's bar id into *that channel's* runtime root only.

    INT-050 / Cluster A: the 2026-07-10 merge-to-primary save put every river's
    anchor into the operator's ``eddy_bar.json``. Write owning-root only, and
    drop foreign channel keys left by that contamination when rewriting a file.
    """
    from mage import _normalized_dir, _resolve_runtime_dir_for_channel

    runtime_dir = _normalized_dir(_resolve_runtime_dir_for_channel(channel_id))
    path = _eddy_bar_state_path_for_channel(channel_id)
    state = _load_eddy_bar_file(path)
    state[str(channel_id)] = message_id
    owned = _channels_for_runtime(runtime_dir)
    owned.add(str(channel_id))
    cleaned = {k: v for k, v in state.items() if k in owned}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(cleaned, fh)


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


async def refresh_river_bar(client, channel_id) -> None:
    """Redraw the standing bar after its menu changed.

    A posted menu cannot change its options, so the bar is replaced by a new one at the
    bottom, as `reconcile_river_bar_floor` would. A channel with no bar gets none made.
    """
    if str(channel_id) not in _load_eddy_bar_state():
        return
    channel = client.get_channel(int(channel_id)) or await client.fetch_channel(int(channel_id))
    await _delete_river_bar_orphans(channel, channel.id)
    await post_river_eddy_bar(channel, client)


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
        from flow_intake_handler import practitioner_message_ends_intake_wait

        if not practitioner_message_ends_intake_wait(thread.id, parent_id):
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

    # Charter §3.3 cardinality branch. This is the eddy bar's normal route —
    # blank eddy, first message names it — and it was the largest hole in the
    # 07-29 neutral-titling deploy: the branch was wired into the two spawn
    # paths and not into the one most eddies actually take, so one member's
    # opening line about another kept becoming a permanent shared label.
    from mage import channel_is_shared_space

    title = await generate_topic(
        content or "check-in", neutral=channel_is_shared_space(parent_id)
    )
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


async def post_parent_river_glance(channel, *, toward: str = "", user_id=None) -> None:
    """Parent `...` — the same card as `!live`: where am I, here."""
    from cmd_threads import post_channel_glance

    await post_channel_glance(channel, toward=toward, user_id=user_id)


async def handle_river_message(message: discord.Message) -> None:
    """Entry point for native river channel messages (acts only, no Turtle prose)."""
    content = message.content.strip()
    if message.attachments and not content:
        content = f"(attachment: {message.attachments[0].filename})"

    bar_client = _river_client_for_channel(message.channel)

    # Continuation breath — settle floor without River model round-trip.
    # `...` glances this river (or says it is not a conversation). Not go-on.
    from practice_gestures import glance_toward, is_ellipsis_glance, is_go_breath

    if is_ellipsis_glance(content):
        await post_parent_river_glance(
            message.channel,
            toward=glance_toward(content),
            user_id=getattr(getattr(message, "author", None), "id", None),
        )
        return
    if is_go_breath(content) or content in {"..", "go", "continue", "next"}:
        if bar_client:
            from bar_anchor import schedule_river_bar_reconcile

            schedule_river_bar_reconcile(message.channel, bar_client)
        return

    from craft_intake import is_craft_intake_channel
    from river_display import parse_display_request, settle_parent_acts

    craft = is_craft_intake_channel(message)
    display = parse_display_request(content)
    channel_id = getattr(message.channel, "id", None)
    if isinstance(channel_id, int) and not display and not craft:
        from mage import get_channel_primitive
        from parent_intake import drop_kind, eddy_title

        primitive = get_channel_primitive(channel_id)
        if drop_kind(getattr(primitive, "name", None), display=False) == "session":
            opened = await open_drop_thread(
                message,
                title=eddy_title(content),
                kind="session",
            )
            if not opened:
                await message.channel.send("Could not open the session.")
            return
    if display:
        acts = [display]
    elif craft:
        acts = []
    else:
        acts = await classify_river_acts(content)
    acts = settle_parent_acts(acts, craft=craft)
    summary = await render_acts(message, acts)
    print(f"River [{message.author.display_name}]: {summary['acts']} views={summary['views']}")

    if bar_client:
        from bar_anchor import schedule_river_bar_reconcile

        schedule_river_bar_reconcile(message.channel, bar_client)


install_takeup()
