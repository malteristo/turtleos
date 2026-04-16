"""turtleOS eddy spawn — auto-create focused threads from rich content.

Core pattern: a standing intake thread acts as a thread launcher.
Anything posted into the intake thread auto-spawns a new thread
in the parent channel, seeded with the content. The intake thread
is the front door — drop content, get a focused conversation.

Also supports:
  !new [topic]  — explicit command from main channel
  Auto-detect   — URL/long-text messages in main channel get a button
"""

import asyncio
import os
import re
from datetime import datetime, timezone

import discord

from llm import chat_ollama
from mage import get_pd
from practice_io import read_safe
from state import EDDY_TYPES, EDDY_DEFAULT, REFLECTION_MODEL
from helpers import local_now

TOPIC_MODEL = "qwen3.5:9b"
TOPIC_CTX = 2048
TOPIC_TIMEOUT = 15

INTAKE_THREAD_NAMES = {"new", "new thread", "intake"}

URL_PATTERN = re.compile(r'https?://\S+')
LONG_TEXT_THRESHOLD = 250
MULTI_PARAGRAPH_THRESHOLD = 3

TOPIC_PROMPT = (
    "Generate a short, specific thread title (2-5 words) for a conversation "
    "about the following content. Be concrete, not generic. No quotes, no "
    "punctuation, lowercase preferred.\n\nContent:\n{content}"
)


def is_intake_thread(channel) -> bool:
    """Check if a channel is the standing intake thread."""
    if not isinstance(channel, discord.Thread):
        return False
    return channel.name.lower().strip() in INTAKE_THREAD_NAMES


def should_offer_eddy(message) -> bool:
    """Detect whether a main-channel message is a thread seed."""
    if isinstance(message.channel, discord.Thread):
        return False

    text = message.content.strip()

    if not text and not message.attachments:
        return False
    if text.startswith("!"):
        return False

    has_urls = bool(URL_PATTERN.search(text))
    is_long = len(text) > LONG_TEXT_THRESHOLD
    is_multi = text.count("\n\n") >= MULTI_PARAGRAPH_THRESHOLD
    has_attachments = bool(message.attachments)
    has_code = "```" in text

    if has_urls:
        return True
    if is_long and (is_multi or has_code):
        return True
    if has_attachments:
        return True

    return False


async def generate_topic(content: str) -> str:
    """Generate a thread topic from content using a fast local model."""
    snippet = content[:1500]
    try:
        result = await asyncio.wait_for(
            chat_ollama(
                "You generate short thread titles. Respond with ONLY the title, nothing else.",
                [{"role": "user", "content": TOPIC_PROMPT.format(content=snippet)}],
                model=TOPIC_MODEL,
                num_ctx=TOPIC_CTX,
                think=False,
            ),
            timeout=TOPIC_TIMEOUT,
        )
        if result:
            topic = result.strip().strip('"\'').strip()
            topic = topic.split("\n")[0][:80]
            if topic:
                return topic
    except (asyncio.TimeoutError, Exception) as e:
        print(f"Topic generation failed: {type(e).__name__}: {e}")

    urls = URL_PATTERN.findall(content)
    if urls:
        from urllib.parse import urlparse
        domain = urlparse(urls[0]).netloc.replace("www.", "")
        return f"shared from {domain}"

    first_line = content.strip().split("\n")[0][:60]
    return first_line if first_line else "new thread"


async def spawn_eddy_in_channel(channel, content: str, topic: str | None = None,
                                 eddy_type: str = "standard"):
    """Create a thread in a channel (not from a message). Used by the intake pattern.

    Returns the created thread, or None on failure.
    """
    from commands import thread_configs, _build_config_line, ThreadConfigView
    from llm import resolve_model
    from mage import get_thread_member_ids
    from thread_registry import register_thread
    from state import client

    if not topic:
        topic = await generate_topic(content)

    model_id, use_api = resolve_model("local")
    attunement = "semi"
    eddy_archive = EDDY_TYPES.get(eddy_type, {}).get("archive_minutes", 10080)

    try:
        thread = await channel.create_thread(
            name=topic,
            auto_archive_duration=eddy_archive,
            type=discord.ChannelType.public_thread,
        )
    except discord.HTTPException as e:
        print(f"Eddy spawn in channel failed: {e}")
        return None

    thread_configs[thread.id] = {
        "model": model_id,
        "use_api": use_api,
        "attunement": attunement,
        "model_label": "local",
        "eddy_type": eddy_type,
        "context_type": None,
        "created": datetime.now(timezone.utc),
    }

    config_line = _build_config_line(thread.id)
    view = ThreadConfigView(current_type=eddy_type)
    await thread.send(config_line, view=view)

    for uid in get_thread_member_ids(channel.id):
        try:
            user = await client.fetch_user(int(uid))
            await thread.add_user(user)
        except Exception:
            pass

    register_thread(
        thread.id, topic,
        parent_channel=channel.name if hasattr(channel, "name") else "unknown",
        model="local", attunement=attunement, eddy_type=eddy_type,
    )

    print(f"Eddy spawned in channel: {topic} (id: {thread.id})")
    return thread


async def spawn_eddy(message, topic: str | None = None, eddy_type: str = "standard"):
    """Create a thread from a message (used by !new and button spawn).

    Returns the created thread, or None on failure.
    """
    from commands import thread_configs, _build_config_line, ThreadConfigView
    from llm import resolve_model
    from mage import get_thread_member_ids
    from thread_registry import register_thread
    from state import client

    text = message.content.strip()

    if not topic:
        topic = await generate_topic(text)

    model_id, use_api = resolve_model("local")
    attunement = "semi"
    eddy_archive = EDDY_TYPES.get(eddy_type, {}).get("archive_minutes", 10080)

    try:
        thread = await message.create_thread(
            name=topic,
            auto_archive_duration=eddy_archive,
        )
    except discord.HTTPException as e:
        if e.code == 160004:
            return None
        print(f"Eddy spawn failed: {e}")
        return None

    thread_configs[thread.id] = {
        "model": model_id,
        "use_api": use_api,
        "attunement": attunement,
        "model_label": "local",
        "eddy_type": eddy_type,
        "context_type": None,
        "created": datetime.now(timezone.utc),
    }

    config_line = _build_config_line(thread.id)
    view = ThreadConfigView(current_type=eddy_type)
    await thread.send(config_line, view=view)

    parent_id = message.channel.id
    for uid in get_thread_member_ids(parent_id):
        try:
            user = await client.fetch_user(int(uid))
            await thread.add_user(user)
        except Exception:
            pass

    register_thread(
        thread.id, topic,
        parent_channel=message.channel.name if hasattr(message.channel, "name") else "unknown",
        model="local", attunement=attunement, eddy_type=eddy_type,
    )

    print(f"Eddy spawned: {topic} (id: {thread.id}) from message {message.id}")
    return thread


async def handle_intake_message(message):
    """Handle a message posted in the intake thread.

    Spawns a new thread in the parent channel, seeds it with the content,
    and gets Turtle to respond there. The intake thread gets a brief
    confirmation; the new thread gets Turtle's substantive opening.
    """
    from state import dialogue_histories
    from helpers import split_message
    from prompts import get_thread_prompt

    parent = message.channel.parent
    if not parent:
        print("Intake: no parent channel found")
        return None

    content = message.content.strip()
    if not content and not message.attachments:
        return None
    if content.startswith("!"):
        return None

    thread = await spawn_eddy_in_channel(parent, content)
    if not thread:
        await message.reply("Couldn't create thread.", mention_author=False)
        return None

    # Confirmation in intake thread
    await message.reply(
        f"\U0001f9f5 \u2192 **{thread.name}**",
        mention_author=False,
    )

    # Generate Turtle's opening response in the new thread
    user_entry = f"[{message.author.display_name}]: {content}"

    # Fetch URLs if present
    url_content = ""
    urls = URL_PATTERN.findall(content)
    if urls:
        try:
            from content_fetch import process_urls
            url_content = await process_urls(urls)
            if url_content:
                user_entry += f"\n\n[Fetched content]:\n{url_content[:6000]}"
        except Exception as e:
            print(f"Intake URL fetch failed: {e}")

    history = [{"role": "user", "content": user_entry}]
    dialogue_histories[thread.id] = list(history)

    system_prompt = get_thread_prompt("semi", False)

    try:
        async with thread.typing():
            from llm import chat_ollama_with_tools
            from tos_tools import TOS_TOOLS, execute_tos_tool
            reply, _ = await chat_ollama_with_tools(
                system_prompt, history,
                tos_tools=TOS_TOOLS, execute_tool=execute_tos_tool,
            )
            if not reply:
                reply = "*listening*"
    except Exception as e:
        print(f"Intake opening response failed: {e}")
        reply = "*listening*"

    dialogue_histories[thread.id].append({"role": "assistant", "content": reply})
    for chunk in split_message(reply):
        await thread.send(chunk)

    print(f"Intake: spawned {thread.name} (id: {thread.id}) with opening response")
    return thread


def make_eddy_spawn_view(source_message) -> discord.ui.View:
    """Create a view with a thread-spawn button. Encodes source IDs in custom_id."""
    channel_id = source_message.channel.id
    message_id = source_message.id

    view = discord.ui.View(timeout=None)
    custom_id = f"eddy:spawn:{channel_id}:{message_id}"
    button = discord.ui.Button(
        label="Start thread",
        custom_id=custom_id,
        style=discord.ButtonStyle.secondary,
        emoji="\U0001f9f5",
    )

    async def button_callback(interaction: discord.Interaction):
        await handle_eddy_spawn_interaction(interaction)

    button.callback = button_callback
    view.add_item(button)
    return view


async def handle_eddy_spawn_interaction(interaction: discord.Interaction):
    """Handle eddy:spawn button clicks."""
    custom_id = interaction.data.get("custom_id", "")
    parts = custom_id.split(":")
    if len(parts) < 4:
        await interaction.response.send_message(
            "Button data missing. Use `!new` instead.", ephemeral=True
        )
        return

    channel_id = int(parts[2])
    message_id = int(parts[3])

    await interaction.response.defer(thinking=True)
    try:
        channel = interaction.client.get_channel(channel_id)
        if not channel:
            await interaction.followup.send("Channel not found.", ephemeral=True)
            return

        source = await channel.fetch_message(message_id)
        thread = await spawn_eddy(source)

        if thread:
            view = discord.ui.View(timeout=None)
            done_button = discord.ui.Button(
                label=f"\u2192 {thread.name}",
                custom_id=f"eddy:done:{thread.id}",
                style=discord.ButtonStyle.success,
                emoji="\U0001f9f5",
                disabled=True,
            )
            view.add_item(done_button)
            await interaction.message.edit(view=view)
            await interaction.followup.send(
                f"\U0001f9f5 Thread created: **{thread.name}**",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                "Couldn't create thread \u2014 this message may already have one.",
                ephemeral=True,
            )
    except Exception as e:
        await interaction.followup.send(
            f"Spawn failed: {type(e).__name__}: {e}",
            ephemeral=True,
        )
