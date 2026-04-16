"""turtleOS eddy spawn — auto-create focused threads from rich content.

Two modes:
  !new        — explicit command, always spawns a thread from the message
  Auto-detect — when main-channel content looks thread-worthy, offer a button

Both use the same spawn_eddy() pipeline:
  1. Analyze content (URLs, text, attachments)
  2. Generate a thread topic via LLM
  3. Create a Discord thread from the source message
  4. Post a substantive opening response in the thread
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

URL_PATTERN = re.compile(r'https?://\S+')
LONG_TEXT_THRESHOLD = 250
MULTI_PARAGRAPH_THRESHOLD = 3

TOPIC_PROMPT = (
    "Generate a short, specific thread title (2-5 words) for a conversation "
    "about the following content. Be concrete, not generic. No quotes, no "
    "punctuation, lowercase preferred.\n\nContent:\n{content}"
)


def should_offer_eddy(message) -> bool:
    """Detect whether a main-channel message is a thread seed.

    Signals: external URLs, long text, multi-paragraph, pasted content.
    Excludes: commands, short reactions, greetings, messages in threads.
    """
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


async def spawn_eddy(message, topic: str | None = None, eddy_type: str = "standard"):
    """Create a focused thread from a message with a substantive opening.

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


def make_eddy_spawn_view(source_message) -> discord.ui.View:
    """Create a view with a thread-spawn button. Encodes source IDs in custom_id."""
    view = discord.ui.View(timeout=None)
    custom_id = f"eddy:spawn:{source_message.channel.id}:{source_message.id}"
    button = discord.ui.Button(
        label="Start thread",
        custom_id=custom_id,
        style=discord.ButtonStyle.secondary,
        emoji="\U0001f9f5",
    )
    view.add_item(button)
    return view


async def handle_eddy_spawn_interaction(interaction: discord.Interaction):
    """Handle eddy:spawn button clicks. Called from on_interaction in the bot."""
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
