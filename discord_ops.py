#!/Users/turtle/turtle-shell/venv/bin/python3
import os, asyncio, discord

with open('/Users/turtle/turtle-shell/.env') as f:
    for line in f:
        line = line.strip()
        if line.startswith('DISCORD_BOT_TOKEN='):
            token = line.split('=', 1)[1]

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

import sys
op = sys.argv[1] if len(sys.argv) > 1 else 'help'
channel_id = int(sys.argv[2]) if len(sys.argv) > 2 else None
text = ' '.join(sys.argv[3:]) if len(sys.argv) > 3 else ''

async def run():
    await client.login(token)
    
    if op == 'read':
        ch = await client.fetch_channel(channel_id)
        msgs = []
        async for m in ch.history(limit=int(text) if text else 20):
            msgs.append(m)
        for m in reversed(msgs):
            author = m.author.display_name or m.author.name
            ts = m.created_at.strftime("%H:%M")
            if m.content:
                msg_text = m.content
            elif m.embeds:
                parts = []
                for e in m.embeds:
                    if e.title:
                        parts.append(e.title)
                    if e.description:
                        parts.append(e.description)
                if parts:
                    msg_text = ' | '.join(parts)
                else:
                    continue
            else:
                continue
            print("[" + ts + "] " + author + ": " + msg_text)
            print()
    
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
        print("Usage: discord_ops.py <read|send|threads> <channel_id> [text/limit]")
        print("Channels:")
        print("  kermit:       1479428854513664030")
        print("  nesrine:      1484973995823599757")
        print("  family:       1491163697278881836  (text channel — river model)")
        print("  heartbeat:    1479428858133479466")
        print("  efferent:     1479428862776442942")
        print("  afferent:     1479428866975207424")
        print("  precognition: 1479428870401691731")
        print("  care:         1479428874382213121")
        print("  distress:     1479428878199033987")
    
    await client.close()

asyncio.run(run())
