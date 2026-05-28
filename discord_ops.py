#!/Users/turtle/turtleos/venv/bin/python3
import asyncio
import sys

import discord

with open('/Users/turtle/turtleos/.env') as f:
    for line in f:
        line = line.strip()
        if line.startswith('DISCORD_BOT_TOKEN='):
            token = line.split('=', 1)[1]

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

op = sys.argv[1] if len(sys.argv) > 1 else 'help'
channel_id = int(sys.argv[2]) if len(sys.argv) > 2 else None
text = ' '.join(sys.argv[3:]) if len(sys.argv) > 3 else ''


def summarize_embeds(embeds):
    parts = []
    for embed in (embeds or [])[:3]:
        bits = []
        if getattr(embed, 'title', None):
            bits.append(embed.title)
        if getattr(embed, 'description', None):
            bits.append(embed.description)
        if getattr(embed, 'url', None):
            bits.append(embed.url)
        if bits:
            parts.append(' | '.join(bits))
    return parts


def summarize_attachments(attachments):
    parts = []
    for att in (attachments or [])[:5]:
        name = getattr(att, 'filename', 'attachment')
        content_type = getattr(att, 'content_type', None) or 'unknown type'
        url = getattr(att, 'url', None)
        parts.append(f"{name} ({content_type})" + (f" {url}" if url else ''))
    return parts


def summarize_message_snapshot(snapshot, index):
    parts = [f"[Forwarded message {index}]"]
    created = getattr(snapshot, 'created_at', None)
    if created:
        parts.append(f"created: {created.isoformat()}")
    msg_type = getattr(snapshot, 'type', None)
    if msg_type:
        parts.append(f"type: {msg_type}")

    content = (getattr(snapshot, 'content', '') or '').strip()
    if content:
        parts.append(f"content:\n{content}")

    embed_lines = summarize_embeds(getattr(snapshot, 'embeds', []) or [])
    if embed_lines:
        parts.append('embeds:\n' + '\n'.join(f"- {line}" for line in embed_lines))

    attachment_lines = summarize_attachments(getattr(snapshot, 'attachments', []) or [])
    if attachment_lines:
        parts.append('attachments:\n' + '\n'.join(f"- {line}" for line in attachment_lines))

    if len(parts) == 1:
        parts.append('no readable content in snapshot')
    return '\n'.join(parts)


def forwarded_context(message):
    snapshots = getattr(message, 'message_snapshots', None) or []
    if not snapshots:
        return ''

    blocks = [summarize_message_snapshot(snapshot, idx) for idx, snapshot in enumerate(snapshots, 1)]

    ref = getattr(message, 'reference', None)
    if ref:
        ref_bits = []
        if getattr(ref, 'guild_id', None):
            ref_bits.append(f"guild_id={ref.guild_id}")
        if getattr(ref, 'channel_id', None):
            ref_bits.append(f"channel_id={ref.channel_id}")
        if getattr(ref, 'message_id', None):
            ref_bits.append(f"message_id={ref.message_id}")
        if ref_bits:
            blocks.append('[Forward source] ' + ' '.join(ref_bits))

    return '\n\n'.join(blocks)


def visible_message_text(message):
    parts = []
    content = (message.content or '').strip()
    if content:
        parts.append(content)

    embed_lines = summarize_embeds(message.embeds)
    if embed_lines:
        parts.append('Embeds:\n' + '\n'.join(f"- {line}" for line in embed_lines))

    attachment_lines = summarize_attachments(message.attachments)
    if attachment_lines:
        parts.append('Attachments:\n' + '\n'.join(f"- {line}" for line in attachment_lines))

    fwd = forwarded_context(message)
    if fwd:
        parts.append(fwd)

    return '\n\n'.join(parts).strip()


def print_message(message):
    author = getattr(message.author, 'display_name', None) or message.author.name
    ts = message.created_at.strftime("%H:%M")
    msg_text = visible_message_text(message)
    if not msg_text:
        return False
    print("[" + ts + "] " + author + ": " + msg_text)
    print()
    return True


async def run():
    await client.login(token)

    if op == 'read':
        ch = await client.fetch_channel(channel_id)
        msgs = []
        async for m in ch.history(limit=int(text) if text else 20):
            msgs.append(m)
        for m in reversed(msgs):
            print_message(m)

    elif op == 'fetch':
        if not text.strip():
            print("Usage: discord_ops.py fetch <channel_id> <message_id>")
            return
        ch = await client.fetch_channel(channel_id)
        m = await ch.fetch_message(int(text.strip()))
        print_message(m)

    elif op == 'send':
        ch = await client.fetch_channel(channel_id)
        await ch.send(text)
        print("Sent to #" + ch.name)

    elif op == 'threads':
        ch = await client.fetch_channel(channel_id)
        guild = ch.guild
        gfull = await client.fetch_guild(guild.id)
        threads = await gfull.active_threads()
        for t in threads:
            pname = t.parent.name if t.parent else 'unknown'
            count = getattr(t, 'message_count', None) or '?'
            created = t.created_at.strftime('%Y-%m-%d') if t.created_at else '?'
            print(t.name + " in #" + pname + " (id:" + str(t.id) + ") messages:" + str(count) + " created:" + str(created))

    elif op == 'help':
        print("Usage: discord_ops.py <read|fetch|send|threads> <channel_id> [text/limit|message_id]")
        print("Pass an explicit Discord channel ID from your local mage_registry.yaml or .env.")

    await client.close()


asyncio.run(run())
