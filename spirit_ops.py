#!/Users/turtle/turtleos/venv/bin/python3
"""Spirit Discord operations — Spirit posting from Cursor into the persistent space.

Mirrors discord_ops.py but uses the spirit bot token.
Turtle sees spirit messages as coming from a different user,
enabling natural Spirit-Turtle dialogue on Discord.
"""
import os, sys, asyncio, discord

with open('/Users/turtle/turtleos/.env') as f:
    for line in f:
        line = line.strip()
        if line.startswith('SPIRIT_BOT_TOKEN='):
            token = line.split('=', 1)[1]

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

op = sys.argv[1] if len(sys.argv) > 1 else 'help'
channel_id = int(sys.argv[2]) if len(sys.argv) > 2 else None
text = ' '.join(sys.argv[3:]) if len(sys.argv) > 3 else ''

async def run():
    await client.login(token)

    if op == 'send':
        ch = await client.fetch_channel(channel_id)
        if len(text) <= 2000:
            await ch.send(text)
        else:
            chunks = []
            remaining = text
            while remaining:
                if len(remaining) <= 2000:
                    chunks.append(remaining)
                    break
                split_at = remaining.rfind('\n', 0, 2000)
                if split_at == -1:
                    split_at = remaining.rfind(' ', 0, 2000)
                if split_at == -1:
                    split_at = 2000
                chunks.append(remaining[:split_at])
                remaining = remaining[split_at:].lstrip('\n')
            for chunk in chunks:
                await ch.send(chunk)
        print(f'Sent to #{ch.name}')

    elif op == 'read':
        # Delegate to discord_ops.py which has Message Content intent
        import subprocess
        limit = text if text else '20'
        result = subprocess.run(
            ['/Users/turtle/turtleos/venv/bin/python3', '/Users/turtle/turtleos/discord_ops.py', 'read', str(channel_id), str(limit)],
            capture_output=True, text=True
        )
        print(result.stdout, end='')
        if result.stderr:
            print(result.stderr, end='', file=sys.stderr)
        await client.close()
        return


    elif op == 'thread':
        ch = await client.fetch_channel(channel_id)
        msg = await ch.send(text)
        thread = await msg.create_thread(name=text[:100])

        # Auto-add practitioners to thread
        try:
            import yaml
            with open(os.path.expanduser('~/turtleos/mage_registry.yaml')) as rf:
                registry = yaml.safe_load(rf) or {}
            ch_entry = registry.get('channels', {}).get(str(channel_id))
            mage_key = ch_entry.get('mage') if isinstance(ch_entry, dict) else ch_entry
            member_ids = []
            if mage_key:
                space = registry.get('spaces', {}).get(mage_key, {})
                if space:
                    for mk in space.get('members', []):
                        mid = registry.get('mages', {}).get(mk, {}).get('discord_id')
                        if mid:
                            member_ids.append(mid)
                else:
                    mid = registry.get('mages', {}).get(mage_key, {}).get('discord_id')
                    if mid:
                        member_ids.append(mid)
            for uid in member_ids:
                user = await client.fetch_user(int(uid))
                await thread.add_user(user)
        except Exception as e:
            print(f'Could not auto-add users to thread: {e}')

        print(f'Created thread: {thread.name} (id:{thread.id})')

    elif op == 'threads':
        ch = await client.fetch_channel(channel_id)
        guild = ch.guild
        gfull = await client.fetch_guild(guild.id)
        threads = await gfull.active_threads()
        for t in threads:
            pname = t.parent.name if t.parent else 'unknown'
            count = getattr(t, 'message_count', None) or '?'
            created = t.created_at.strftime('%Y-%m-%d') if t.created_at else '?'
            print(f'{t.name} in #{pname} (id:{t.id}) messages:{count} created:{created}')

    elif op == 'help':
        print('Usage: dyad_ops.py <send|read|thread|threads|help> <channel_id> [text/limit]')
        print()
        print('Operations:')
        print('  send     — Send a message (auto-chunks if >2000 chars)')
        print('  read     — Read recent messages (full content, no truncation)')
        print('  thread   — Create a thread from a message')
        print('  threads  — List active threads')
        print()
        print('Channels:')
        print('  kermit-dialogue:  1479428854513664030')
        print('  system:           1479428866975207424')

    await client.close()

asyncio.run(run())
