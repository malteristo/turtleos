"""One-time onboarding embed for hosted-river practitioner channels (native v1)."""

from __future__ import annotations

import json
import os

import discord

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))


def _onboarding_state_path(channel_id: int) -> str:
    from mage import set_practice_context_for_channel, _resolve_runtime_dir_for_channel

    set_practice_context_for_channel(channel_id)
    runtime = _resolve_runtime_dir_for_channel(channel_id)
    river_dir = os.path.join(runtime, "thread-state", "river")
    os.makedirs(river_dir, exist_ok=True)
    return os.path.join(river_dir, "onboarding.json")


def is_onboarding_posted(channel_id: int) -> bool:
    path = _onboarding_state_path(channel_id)
    if not os.path.exists(path):
        return False
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return bool(data.get("posted"))
    except (json.JSONDecodeError, TypeError):
        return False


def mark_onboarding_posted(channel_id: int, message_id: int | None = None) -> None:
    path = _onboarding_state_path(channel_id)
    payload = {"posted": True, "channel_id": channel_id}
    if message_id is not None:
        payload["message_id"] = message_id
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)


def _practitioner_locale(channel_id: int) -> str:
    from mage import set_practice_context_for_channel, get_registry, _get_channel_mage

    set_practice_context_for_channel(channel_id)
    mage_key = _get_channel_mage(channel_id)
    if not mage_key:
        return "en"
    mage = get_registry().get("mages", {}).get(mage_key, {})
    locale = (mage.get("locale") or "en").strip().lower()
    return locale if locale in ("de", "en") else "en"


def load_onboarding_markdown(channel_id: int) -> str:
    from mage import set_practice_context_for_channel, get_pd

    set_practice_context_for_channel(channel_id)
    pd = get_pd()
    custom = os.path.join(pd, "onboarding.md")
    if os.path.isfile(custom):
        with open(custom, encoding="utf-8") as fh:
            body = fh.read().strip()
        if body:
            return body

    locale = _practitioner_locale(channel_id)
    template_name = f"onboarding_{locale}.md"
    template_path = os.path.join(REPO_ROOT, "template", "practitioner", template_name)
    if os.path.isfile(template_path):
        with open(template_path, encoding="utf-8") as fh:
            return fh.read().strip()

    fallback = os.path.join(REPO_ROOT, "template", "practitioner", "onboarding_en.md")
    with open(fallback, encoding="utf-8") as fh:
        return fh.read().strip()


def _parse_onboarding_markdown(body: str) -> tuple[str, str]:
    lines = body.splitlines()
    title = ""
    description_lines: list[str] = []
    for line in lines:
        if not title and line.startswith("# "):
            title = line[2:].strip()
            continue
        description_lines.append(line)
    description = "\n".join(description_lines).strip()
    if len(description) > 4000:
        description = description[:3997] + "..."
    return title, description


def _markdown_to_embed(body: str, *, locale: str) -> discord.Embed:
    title, description = _parse_onboarding_markdown(body)
    if not title:
        title = "Willkommen" if locale == "de" else "Welcome"
    color = discord.Color.from_rgb(86, 156, 214)
    embed = discord.Embed(title=title, description=description, color=color)
    return embed


def _iter_hosted_river_channels(client) -> list:
    from mage import get_registry

    channels = []
    for ch_id_str, entry in get_registry().get("channels", {}).items():
        if not isinstance(entry, dict):
            continue
        if entry.get("type") != "hosted-river":
            continue
        try:
            ch_id = int(ch_id_str)
        except (ValueError, TypeError):
            continue
        ch = client.get_channel(ch_id)
        if ch:
            channels.append(ch)
    return channels


async def post_hosted_river_onboarding(channel, client) -> discord.Message | None:
    from mage import set_practice_context_for_channel, get_mage_type, get_pd
    from river_handler import _append_chronicle, ensure_bar_at_bottom

    channel_id = channel.id
    if is_onboarding_posted(channel_id):
        return None

    set_practice_context_for_channel(channel_id)
    if get_mage_type() != "practitioner":
        return None

    locale = _practitioner_locale(channel_id)
    body = load_onboarding_markdown(channel_id)
    embed = _markdown_to_embed(body, locale=locale)

    try:
        msg = await channel.send(embed=embed, silent=True)
    except discord.HTTPException as exc:
        print(f"Hosted river onboarding failed for {channel_id}: {exc}")
        return None

    try:
        await msg.pin()
    except discord.HTTPException:
        pass

    mark_onboarding_posted(channel_id, msg.id)
    practice_dir = get_pd()
    _append_chronicle(
        practice_dir,
        f"hosted river onboarding posted (channel {channel_id})",
        {"event": "hosted_river_onboarding", "channel_id": channel_id, "message_id": msg.id},
    )
    await ensure_bar_at_bottom(channel, client)
    print(f"Hosted river onboarding posted in #{getattr(channel, 'name', channel_id)}")
    return msg


async def ensure_hosted_river_onboarding(client) -> None:
    """Post one-time practitioner onboarding in each hosted-river channel."""
    from mage import get_attunement_profile

    if get_attunement_profile() != "native":
        return
    for channel in _iter_hosted_river_channels(client):
        await post_hosted_river_onboarding(channel, client)


def seed_practitioner_workshop(mage_key: str, *, locale: str = "en") -> str:
    """Initialize practitioner workshop dirs and copy v1 character + onboarding template."""
    import shutil

    workshop = os.path.expanduser(f"~/workshops/{mage_key}")
    os.makedirs(os.path.join(workshop, "sessions"), exist_ok=True)
    os.makedirs(os.path.join(workshop, "state", "notes"), exist_ok=True)
    os.makedirs(os.path.join(workshop, "proposals"), exist_ok=True)
    os.makedirs(os.path.join(workshop, "thread-state"), exist_ok=True)
    os.makedirs(os.path.join(workshop, "character"), exist_ok=True)
    os.makedirs(os.path.join(workshop, "chronicle"), exist_ok=True)
    os.makedirs(os.path.join(workshop, "thread-archive"), exist_ok=True)
    os.makedirs(os.path.join(workshop, "box", "intake"), exist_ok=True)

    current_path = os.path.join(workshop, "state", "current.yaml")
    if not os.path.exists(current_path):
        with open(current_path, "w") as f:
            f.write("version: 1\n")

    char_src = os.path.join(REPO_ROOT, "template", "practitioner", "character")
    for name in ("soul.md", "conduct.md"):
        src = os.path.join(char_src, name)
        dest = os.path.join(workshop, "character", name)
        if os.path.isfile(src) and not os.path.exists(dest):
            shutil.copy2(src, dest)

    onboard_src = os.path.join(REPO_ROOT, "template", "practitioner", f"onboarding_{locale}.md")
    onboard_dest = os.path.join(workshop, "onboarding.md")
    if os.path.isfile(onboard_src) and not os.path.exists(onboard_dest):
        shutil.copy2(onboard_src, onboard_dest)

    template = os.path.expanduser(os.environ.get("PRACTITIONER_SYSTEM_TEMPLATE", ""))
    dest = os.path.join(workshop, "system.md")
    if template and os.path.exists(template) and not os.path.exists(dest):
        shutil.copy2(template, dest)

    return workshop
