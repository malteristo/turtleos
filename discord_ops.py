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
            content = m.content if m.content else '[embed/system]'
            print("[" + ts + "] " + author + ": " + content)
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
            count = 0
            async for _ in t.history(limit=100):
                count += 1
            print(t.name + " in #" + pname + " (id:" + str(t.id) + ") messages:" + str(count))
    
    elif op == 'help':
        print("Usage: discord_ops.py <read|send|threads> <channel_id> [text/limit]")
        print("Channels:")
        print("  kermit:       1479428854513664030")
        print("  nesrine:      1484973995823599757")
        print("  family:       1484973622471692543  (forum — use 'threads' first)")
        print("  heartbeat:    1479428858133479466")
        print("  efferent:     1479428862776442942")
        print("  afferent:     1479428866975207424")
        print("  precognition: 1479428870401691731")
        print("  care:         1479428874382213121")
        print("  distress:     1479428878199033987")
    
    await client.close()

asyncio.run(run())
