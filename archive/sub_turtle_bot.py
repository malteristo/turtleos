#!/usr/bin/env python3
"""Sub-Turtle Bot — Lightweight Discord agent for Consul and Scout.

Runs as a facet of the Turtle's awareness. Each instance loads its own
role card, connects with its own bot token, and uses its own Ollama model.

Architecture principle: the Mage always talks to ONE entity (Turtle).
Sub-turtles contribute through #precognition (observations) and
#afferent (signals), never through #dialogue. Coordination happens
through behavioral traces in Discord (stigmergy), not conversation.
"""

import os
import sys
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import discord
from discord.ext import tasks


def load_env(env_path=None):
    path = env_path or os.environ.get("DOTENV_PATH", ".env")
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


load_env()

BOT_NAME = os.environ.get("BOT_NAME", "SubTurtle")
MODEL = os.environ.get("CONSUL_MODEL") or os.environ.get("SCOUT_MODEL") or "qwen3.5:4b"
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
ROLE_CARD_PATH = os.environ.get("ROLE_CARD_PATH", "")

CHANNELS = {
    "heartbeat": os.environ.get("DISCORD_CHANNEL_HEARTBEAT"),
    "efferent": os.environ.get("DISCORD_CHANNEL_EFFERENT"),
    "afferent": os.environ.get("DISCORD_CHANNEL_AFFERENT"),
    "dialogue": os.environ.get("DISCORD_CHANNEL_DIALOGUE"),
    "precognition": os.environ.get("DISCORD_CHANNEL_PRECOGNITION"),
    "distress": os.environ.get("DISCORD_CHANNEL_DISTRESS"),
}

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


def load_role_card():
    if ROLE_CARD_PATH and os.path.exists(ROLE_CARD_PATH):
        with open(ROLE_CARD_PATH) as f:
            return f.read()
    return f"You are {BOT_NAME}, a sub-turtle in the Turtle nervous system."


def get_channel(name):
    ch_id = CHANNELS.get(name)
    if ch_id:
        return client.get_channel(int(ch_id))
    return None


def _split_message(text, limit=1900):
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


async def chat_ollama(system_prompt, messages):
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            *messages,
        ],
        "stream": True,
        "options": {"num_ctx": 8192},
    }

    reply_chunks = []
    async with httpx.AsyncClient(timeout=httpx.Timeout(
        connect=10.0, read=300.0, write=10.0, pool=10.0
    )) as http:
        async with http.stream(
            "POST", f"{OLLAMA_URL}/api/chat", json=payload
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                try:
                    chunk = json.loads(line)
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        reply_chunks.append(token)
                    if chunk.get("done"):
                        break
                except json.JSONDecodeError:
                    continue

    return "".join(reply_chunks).strip()


@client.event
async def on_ready():
    print(f"{BOT_NAME} online: {client.user} (model: {MODEL})")
    await client.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="the nervous system"
        )
    )

    afferent = get_channel("afferent")
    if afferent:
        await afferent.send(f"{BOT_NAME} online. Model: {MODEL}.")



@client.event
async def on_message(message):
    if message.author == client.user:
        return

    efferent = get_channel("efferent")
    if efferent and message.channel.id == efferent.id:
        await handle_command(message)
        return

    # Sub-turtles do NOT participate in #dialogue.
    # The Mage talks to Turtle. Turtle integrates.
    # Consul and Scout contribute via #precognition and #afferent.


async def handle_command(message):
    """Process commands from #efferent."""
    await message.add_reaction("\U0001F4E1")

    precognition = get_channel("precognition")
    if precognition:
        system_prompt = load_role_card()
        try:
            result = await chat_ollama(
                system_prompt,
                [{"role": "user", "content": f"Command received: {message.content}\n\nProcess this and report your observations."}],
            )
            if result:
                for chunk in _split_message(result):
                    await precognition.send(f"**{BOT_NAME}:** {chunk}")
        except Exception as e:
            print(f"{BOT_NAME} command processing error: {type(e).__name__}: {e}")

    afferent = get_channel("afferent")
    if afferent:
        embed = discord.Embed(
            title=f"{BOT_NAME}: Command received",
            description=f"Processing: {message.content[:200]}",
            color=0x3498DB,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Source", value=f"turtle/{BOT_NAME.lower()}", inline=True)
        await afferent.send(embed=embed)


def main():
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        print(f"Error: DISCORD_BOT_TOKEN not set for {BOT_NAME}", file=sys.stderr)
        sys.exit(1)

    if "--test" in sys.argv:
        print(f"Bot: {BOT_NAME}")
        print(f"Token: ...{token[-8:]}")
        print(f"Model: {MODEL}")
        print(f"Role card: {ROLE_CARD_PATH}")
        role = load_role_card()
        print(f"Role card loaded: {len(role)} chars")
        print(f"Channels configured: {sum(1 for v in CHANNELS.values() if v)}/{len(CHANNELS)}")
        print("Configuration OK.")
        return

    client.run(token)


if __name__ == "__main__":
    main()
