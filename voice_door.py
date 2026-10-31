"""The door the house speaker calls.

It listens only on the virtual-machine bridge, 192.168.64.1. The guest can
reach that address. The house LAN and Tailscale cannot. A sentence comes in,
the home channel answers, and the body that goes back is only what may be spoken.
"""

from __future__ import annotations

import asyncio
import json

from house_speaker import chat_response, loads_body, sentence_of

BIND_HOST = "192.168.64.1"
BIND_PORT = 8766

_runner = None


async def chat_result(body: dict, turn) -> tuple[dict, bool]:
    """Run one chat body. The bool is whether the caller asked for a stream."""
    from voice_home import note_messages

    stream = bool(body.get("stream"))
    note_messages(body.get("messages") if isinstance(body, dict) else None)
    sentence = sentence_of(body)
    if not sentence:
        return chat_response("", None), stream
    try:
        reply = await turn(sentence)
    except Exception as exc:
        print(f"Voice turn failed: {type(exc).__name__}: {exc}")
        return chat_response(sentence, None, failed=True), stream
    return chat_response(sentence, reply), stream


def tags_body() -> dict:
    return {"models": [{"name": "home", "model": "home"}]}


async def start_voice_door(client) -> None:
    """Listen for the speaker. A second call does nothing. A failed bind does not stop Turtle."""
    global _runner
    if _runner is not None:
        return
    from aiohttp import web

    from voice_home import answer_in_home, name_stored_placeholder, note_press

    app = web.Application()

    async def tags(_request):
        return web.json_response(tags_body())

    async def version(_request):
        return web.json_response({"version": "home"})

    async def show(_request):
        return web.json_response({"model": "home", "details": {"family": "home"}})

    async def chat(request):
        try:
            raw = await request.read()
            body = loads_body(raw)
        except Exception:
            body = {}
        result, stream = await chat_result(
            body, lambda sentence: answer_in_home(client, sentence)
        )
        if stream:
            return web.Response(
                text=json.dumps(result) + "\n",
                content_type="application/x-ndjson",
            )
        return web.json_response(result)

    async def press(request):
        try:
            body = loads_body(await request.read())
        except Exception:
            body = {}
        return web.json_response({"ok": True, "new_eddy": note_press(body)})

    app.router.add_get("/api/tags", tags)
    app.router.add_get("/api/version", version)
    app.router.add_post("/api/show", show)
    app.router.add_post("/api/chat", chat)
    app.router.add_post("/press", press)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, BIND_HOST, BIND_PORT)
    try:
        await site.start()
    except OSError as exc:
        print(f"Voice door did not bind {BIND_HOST}:{BIND_PORT}: {exc}")
        await runner.cleanup()
        return
    _runner = runner
    print(f"Voice door listening on http://{BIND_HOST}:{BIND_PORT}")
    try:
        await name_stored_placeholder(client)
    except Exception as exc:
        print(f"Voice eddy rename failed: {type(exc).__name__}: {exc}")
    asyncio.create_task(_watch_day(client))


async def _watch_day(client) -> None:
    """At each local midnight, close yesterday's voice eddy and open today's."""
    from voice_home import ensure_day_eddy, seconds_until_next_day

    while True:
        await asyncio.sleep(seconds_until_next_day())
        try:
            await ensure_day_eddy(client)
        except Exception as exc:
            print(f"Voice day roll failed: {type(exc).__name__}: {exc}")
