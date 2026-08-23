#!/usr/bin/env python3
"""Open a *prepared* eddy — one Spirit spun off for the Mage to work at his own time.

Why this exists
---------------
The bright layer accumulates ideas that never develop, and the reason is a shape
mismatch rather than a discipline failure: entries sit there as open questions,
and the Mage adjudicates candidates rather than generating them. A prepared eddy
is the same material handed over in the form he can act on — context gathered,
question named, candidates drawn, recommendation stated — on the substrate where
he actually has time.

The eddy is the workspace; a **surface file** under the practice root carries the
prepared context. The opener stays short on purpose: long sends chunk, and a
chunked handoff has already caused Turtle to answer parts 1 and 4 before the rest
arrived. An opener over the limit is a design error here, so it fails loudly
rather than chunking quietly.

The surface is a **living workspace**, not a staged document. Turtle updates it as
the interview resolves things, and the Mage reads it between sessions — so the
file is the shared object and the eddy is where it is worked.

That is why rendering into chat is **opt-in** (`--render`). Rendering is the right
answer for reading a *fixed* document on a phone, and it was added for exactly
that. But a rendered copy is a snapshot, and the moment the workspace can change
underneath it, those messages become a confident stale version of a file that has
moved on — scrolled above the conversation that changed it. Wrong-and-convincing
beats missing, so the default is the file plus a short note, and the rendering is
requested when the Mage wants to read rather than work.

When it is requested, rendered messages go out as **acts from the river bot**:
`helpers.reload_history` drops non-Turtle bot messages, so the delivery costs
Turtle no context and cannot be mistaken for the Mage speaking.

Special status
--------------
A prepared eddy is not one the Mage opened, and the harvest has to tell them
apart — his own eddies are thinking he started, these are surfaces Spirit staged.

**Lifecycle (sanctioned 2026-08-10):** prepared eddies appear and disappear on
their own once they have served their purpose. The Mage works them in his own
time, writing into the workspace as he goes. When the surface's target
condition is met (the "good outcome" / determination the file named at open),
Turtle **recommends** close — it does not silently dissolve. He confirms
(``!dissolve`` / the one-liner path); disposition goes ``ready``; Spirit
harvests at ``. craft``. Craft-turtle stays clear of Spirit-opened residue:
only Mage-started eddies linger by default.

The status lives in a **sidecar** file, not in the thread registry, and that is not
a style choice. The running bot keeps the registry in a module-level cache and
persists the whole document from memory on a debounce, so a write from any other
process is erased the next time a message arrives anywhere in the space. Marking
the registry from here appeared to work and was gone inside three minutes. The
registry is the bot's exclusive writable surface; anything Spirit-side owns must
live beside it. The eddy's own name is not durable either — a blank eddy gets
auto-renamed from its first exchange — so the sidecar keeps the topic Spirit
opened it under.

Usage (on the host, where the bot tokens live):
    python3 open_prepared_eddy.py --topic "ux research as offering" \
        --surface craft/surface-ux-research.md --opener /tmp/opener-ux.md
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(os.environ.get("TURTLEOS_REPO", Path.home() / "turtleos"))
sys.path.insert(0, str(REPO))

ENV_PATH = REPO / ".env"
CRAFT_TYPES = ("craft",)


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if not ENV_PATH.is_file():
        return values
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        values[key.strip()] = val.strip()
    for key, val in values.items():
        os.environ.setdefault(key, val)
    return values


def resolve_craft_channel_id() -> int:
    """The craft surface, from the registry — never a literal.

    A hardcoded channel id in product-adjacent code is a tracked defect class in
    this repo (three product sites, ten fixtures). Resolve by ``type``.
    """
    import yaml

    registry_path = REPO / "mage_registry.yaml"
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    for ch_id, entry in (registry.get("channels") or {}).items():
        if not str(ch_id).isdigit() or not isinstance(entry, dict):
            continue
        if entry.get("type") in CRAFT_TYPES:
            return int(ch_id)
    raise RuntimeError("No channel of type 'craft' in mage_registry.yaml")


def bind_channel(channel_id: int) -> None:
    """Bind practice + runtime roots to the channel's own space.

    ``get_pd()`` / ``get_runtime_dir()`` fall back to the *primary* mage when no
    context is set, which is the Cluster A shape: correct for the operator and
    silently wrong for everyone else. Bind explicitly so this works for a hosted
    space the day one gets a craft surface.
    """
    from mage import set_practice_context_for_channel

    set_practice_context_for_channel(channel_id)


def sidecar_path() -> Path:
    from mage import get_runtime_dir

    return Path(get_runtime_dir()) / "thread-state" / "prepared_eddies.yaml"


def resolve_surface(rel_path: str) -> Path:
    """Practice-root-relative surface path → an absolute file that exists."""
    from mage import get_pd

    path = Path(get_pd()) / rel_path
    if not path.is_file():
        raise RuntimeError(f"Surface file not found: {path}")
    return path


def surface_footer(rel_path: str) -> str:
    """Where the workspace lives, appended to the opener."""
    return f"\n\n-# 📄 shared workspace: `{rel_path}` — ask me to render it to read it here"


def workspace_note(rel_path: str) -> str:
    """Default delivery: the file, and what it is for."""
    name = rel_path.replace("\\", "/").rstrip("/").split("/")[-1]
    return (
        f"**{name}** — the shared workspace for this eddy, attached.\n"
        f"Turtle keeps it current as things resolve here, so the file is the "
        f"state of the thinking rather than a record of it.\n"
        f"-# workshop path `{rel_path}` · ask to have it rendered here to read it on a phone"
    )


async def deliver_surface(
    client, thread_id: int, surface_abs: Path, rel: str, *, render: bool
) -> int:
    """Put the workspace in the eddy — as a file, or rendered for reading.

    Sequential awaits when rendering, because order is the whole point of a split
    document and gather() would race it.
    """
    import discord

    from core.prepared_surface import render_surface_messages

    thread = await client.fetch_channel(thread_id)

    def attachment():
        return discord.File(str(surface_abs), filename=surface_abs.name)

    if not render:
        await thread.send(workspace_note(rel), file=attachment())
        return 1

    messages = render_surface_messages(surface_abs.read_text(encoding="utf-8"), rel)
    for i, body in enumerate(messages, start=1):
        extra = {"file": attachment()} if i == len(messages) else {}
        await thread.send(body, **extra)
    return len(messages)


def mark_prepared(thread_id: int, surface: str, topic: str) -> None:
    """Record the special status where the bot will not overwrite it."""
    import yaml

    path = sidecar_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if path.is_file():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = data.setdefault("prepared", {})
    entries[str(thread_id)] = {
        "surface": surface,
        "prepared_topic": topic,
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "prepared_by": "spirit",
        "disposition": "open",
    }
    path.write_text(yaml.dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"marked prepared in {path}")


DISCORD_LIMIT = 2000


def river_token(env: dict) -> str:
    token = env.get("RIVER_BOT_TOKEN") or env.get("DISCORD_BOT_TOKEN")
    if not token:
        raise RuntimeError("RIVER_BOT_TOKEN or DISCORD_BOT_TOKEN not found in .env")
    return token


async def river_client(env: dict):
    import discord

    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)
    await client.login(river_token(env))
    return client


async def post_opener(env: dict, thread_id: int, body: str, rel: str) -> None:
    """The ask, signed by Spirit so it becomes a turn.

    Which bot signs a message decides whether Turtle answers: ``is_practitioner_input``
    counts only Spirit among bots. The opener must be Spirit or Turtle never engages;
    the surface delivery must not be, or a document arriving spends a turn and talks
    over a question the eddy is holding for the Mage.
    """
    import discord

    token = env.get("SPIRIT_BOT_TOKEN")
    if not token:
        raise RuntimeError("SPIRIT_BOT_TOKEN not found in .env")

    content = body.rstrip() + surface_footer(rel)
    if len(content) > DISCORD_LIMIT:
        raise RuntimeError(
            f"Opener is {len(content)} chars, over Discord's {DISCORD_LIMIT}. "
            "Shorten it — the surface carries the detail, the opener carries the ask. "
            "Chunking here has previously made Turtle answer part 1 before part 4 arrived."
        )

    client = discord.Client(intents=discord.Intents.default())
    await client.login(token)
    try:
        thread = await client.fetch_channel(thread_id)
        await thread.send(content)
    finally:
        await client.close()


async def main_async(args: argparse.Namespace) -> dict:
    env = load_env()
    from eddy_spawn import spawn_blank_river_eddy

    channel_id = args.channel or resolve_craft_channel_id()
    bind_channel(channel_id)
    surface_abs = resolve_surface(args.surface)
    body = Path(args.opener).read_text(encoding="utf-8") if args.opener else None

    if args.resend_surface:
        client = await river_client(env)
        try:
            sent = await deliver_surface(
                client, args.resend_surface, surface_abs, args.surface, render=args.render
            )
        finally:
            await client.close()
        return {
            "status": "ok",
            "action": "resend-surface",
            "surface": args.surface,
            "messages": sent,
            "thread_id": str(args.resend_surface),
        }

    if not args.topic or not args.opener:
        raise RuntimeError("--topic and --opener are required when opening a new eddy")

    # One act: spawn, deliver the surface, then ask. A prepared eddy missing its
    # surface is the half-completed write this repo keeps rediscovering, so the
    # steps stay in one command rather than one command per step.
    client = await river_client(env)
    try:
        channel = await client.fetch_channel(channel_id)
        thread = await spawn_blank_river_eddy(
            channel,
            flow_id=None,
            eddy_type=args.eddy_type,
            topic=args.topic,
        )
        if thread is None:
            raise RuntimeError("spawn_blank_river_eddy returned None")
        # Surface before opener, so the document sits above the conversation it
        # is about rather than under it.
        sent = await deliver_surface(
            client, thread.id, surface_abs, args.surface, render=args.render
        )
    finally:
        await client.close()

    await post_opener(env, thread.id, body, args.surface)
    mark_prepared(thread.id, args.surface, args.topic)
    return {
        "status": "ok",
        "topic": args.topic,
        "surface": args.surface,
        "messages": sent,
        "thread_id": str(thread.id),
        "parent_channel_id": str(channel_id),
        "jump_url": getattr(thread, "jump_url", None),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Open a Spirit-prepared eddy")
    parser.add_argument("--topic", default=None, help="Eddy name")
    parser.add_argument(
        "--surface",
        required=True,
        help="Practice-root-relative path to the prepared surface file",
    )
    parser.add_argument("--opener", default=None, help="Path to the opener message body")
    parser.add_argument(
        "--resend-surface",
        type=int,
        default=None,
        metavar="THREAD_ID",
        help="Post the surface into an existing eddy instead of opening a new one",
    )
    parser.add_argument(
        "--render",
        action="store_true",
        help="Also render the workspace as readable messages (snapshot — it can go stale)",
    )
    parser.add_argument("--channel", type=int, default=None, help="Override channel id")
    parser.add_argument("--eddy-type", default="standard", dest="eddy_type")
    args = parser.parse_args()
    try:
        report = asyncio.run(main_async(args))
        print(json.dumps(report, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "fail", "error": f"{type(exc).__name__}: {exc}"}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
