#!/Users/turtle/turtleos/venv/bin/python3
"""Spirit Discord operations — Spirit posting from Cursor into the persistent space.

Mirrors discord_ops.py but uses the spirit bot token.
Turtle sees spirit messages as coming from a different user,
enabling natural Spirit-Turtle dialogue on Discord.
"""
import os, sys, asyncio, discord

ENV_PATH = '/Users/turtle/turtleos/.env'
VENV_PY = '/Users/turtle/turtleos/venv/bin/python3'
DISCORD_OPS = '/Users/turtle/turtleos/discord_ops.py'


def load_token():
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line.startswith('SPIRIT_BOT_TOKEN='):
                return line.split('=', 1)[1]
    raise RuntimeError('SPIRIT_BOT_TOKEN not found in .env')


def parse_args(argv):
    op = argv[1] if len(argv) > 1 else 'help'
    channel_id = int(argv[2]) if len(argv) > 2 and argv[2].isdigit() else None
    args = argv[3:] if len(argv) > 3 else []

    input_path = None
    read_stdin = False
    remaining = []
    i = 0
    while i < len(args):
        if args[i] == '--file' and i + 1 < len(args):
            input_path = args[i + 1]
            i += 2
        elif args[i] == '--stdin':
            read_stdin = True
            i += 1
        else:
            remaining.append(args[i])
            i += 1

    if input_path:
        with open(os.path.expanduser(input_path), encoding='utf-8') as f:
            text = f.read()
    elif read_stdin:
        text = sys.stdin.read()
    else:
        text = ' '.join(remaining)

    return op, channel_id, text


def chunk_message(text, limit=2000):
    if len(text) <= limit:
        return [text]

    # Leave room for headers that tell Turtle not to respond mid-handoff.
    body_limit = 1850
    chunks = []
    remaining = text
    while remaining:
        if len(remaining) <= body_limit:
            chunks.append(remaining)
            break
        split_at = remaining.rfind('\n', 0, body_limit)
        if split_at == -1:
            split_at = remaining.rfind(' ', 0, body_limit)
        if split_at == -1:
            split_at = body_limit
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:].lstrip('\n')

    total = len(chunks)
    return [
        f"[Spirit handoff {i}/{total} — wait for final part before responding]\n\n{chunk}"
        for i, chunk in enumerate(chunks, start=1)
    ]


def print_help():
    print('Usage: spirit_ops.py <send|read|fetch|thread|threads|help> <channel_id> [text/limit|message_id]')
    print('       spirit_ops.py send <channel_id> --file <path>')
    print('       command | spirit_ops.py send <channel_id> --stdin')
    print()
    print('Operations:')
    print('  send     — Send a message (auto-chunks if >2000 chars)')
    print('  read     — Read recent messages (full content, no truncation)')
    print('  fetch    — Fetch one message by channel_id and message_id')
    print('  thread   — Create a thread from a message')
    print('  threads  — List active threads')
    print()
    print('Channels:')
    print('  river:            1479428854513664030')


async def run(op, channel_id, text, client):
    if op == 'help':
        print_help()
        return

    if op in ('read', 'fetch'):
        # Delegate to discord_ops.py which has Message Content intent.
        import subprocess
        if not channel_id:
            print_help()
            return
        arg = text if text else ('20' if op == 'read' else '')
        if op == 'fetch' and not arg:
            print_help()
            return
        result = subprocess.run(
            [VENV_PY, DISCORD_OPS, op, str(channel_id), str(arg)],
            capture_output=True, text=True
        )
        print(result.stdout, end='')
        if result.stderr:
            print(result.stderr, end='', file=sys.stderr)
        return

    if op in ('send', 'thread') and (not channel_id or not text):
        print_help()
        return
    if op == 'threads' and not channel_id:
        print_help()
        return

    await client.login(token)
    try:
        if op == 'send':
            ch = await client.fetch_channel(channel_id)
            chunks = chunk_message(text)
            for chunk in chunks:
                await ch.send(chunk)
            print(f'Sent to #{ch.name}')

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

        else:
            print_help()
    finally:
        await client.close()

if __name__ == '__main__':
    token = load_token()
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)
    op, channel_id, text = parse_args(sys.argv)
    asyncio.run(run(op, channel_id, text, client))
