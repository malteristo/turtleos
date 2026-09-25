"""Streamable-HTTP MCP endpoint (JSON responses, no server stream).

Listens on loopback only. ``tailscale serve`` terminates HTTPS in front of it
and is the only way in; it deletes client-supplied ``Tailscale-User-*`` and
``X-Forwarded-For`` headers and sets verified ones, which is why loopback is a
requirement and not a preference.
"""

from __future__ import annotations

import argparse
import json
import os

from aiohttp import web

from mcp_access.grants import ACTIVE, GrantStore
from mcp_access.protocol import INVALID_REQUEST, Session, _error
from mcp_access.registry import load_registry, resolve_sources

LOOPBACK = frozenset({"127.0.0.1", "::1", "localhost"})
DEFAULT_PORT = 3141
LOGIN_HEADER = "Tailscale-User-Login"
ADDR_HEADER = "X-Forwarded-For"


class NotLoopback(ValueError):
    pass


def assert_loopback(host: str) -> None:
    if host not in LOOPBACK:
        raise NotLoopback(f"refusing to listen on {host!r}: loopback only")


def _require_identity() -> bool:
    return os.environ.get("TURTLE_MCP_REQUIRE_TAILNET_IDENTITY", "1") != "0"


def _unauthorized(text: str = "unauthorized") -> web.Response:
    return web.Response(status=401, text=text, headers={"WWW-Authenticate": "Bearer"})


def build_app(store: GrantStore | None = None, registry_loader=load_registry) -> web.Application:
    store = store or GrantStore()

    async def mcp_post(request: web.Request) -> web.Response:
        if request.headers.get("Origin"):
            return web.Response(status=403, text="origin not allowed")
        auth = request.headers.get("Authorization", "")
        token = auth[7:].strip() if auth.startswith("Bearer ") else ""
        grant = store.find_by_token(token)
        if grant is None or grant.status != ACTIVE or grant.expired():
            return _unauthorized()

        login = request.headers.get(LOGIN_HEADER, "").strip()
        addr = request.headers.get(ADDR_HEADER, "").strip()
        if _require_identity():
            if not login or not addr:
                store.count(grant.id, refused=True)
                return web.Response(status=403, text="tailnet identity required")
            if grant.bound_login is None:
                grant = store.update(grant.id, bound_login=login, bound_addr=addr) or grant
            elif grant.bound_login != login or grant.bound_addr != addr:
                store.count(grant.id, refused=True)
                return web.Response(status=403, text="credential used from another identity")

        try:
            message = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            return web.json_response(_error(None, INVALID_REQUEST, "invalid json"), status=400)
        if isinstance(message, list):
            return web.json_response(_error(None, INVALID_REQUEST, "batch not supported"), status=400)

        sources = resolve_sources(grant.owner, grant.sources, registry_loader())
        session = Session(grant=grant, sources=sources, store=store)
        reply = session.handle(message)
        store.count(grant.id, refused=session.refused)
        if reply is None:
            return web.Response(status=202)
        return web.json_response(reply)

    async def mcp_other(_request: web.Request) -> web.Response:
        return web.Response(status=405, headers={"Allow": "POST"})

    async def health(_request: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    app = web.Application(client_max_size=256 * 1024)
    app.router.add_post("/mcp", mcp_post)
    app.router.add_get("/mcp", mcp_other)
    app.router.add_delete("/mcp", mcp_other)
    app.router.add_get("/health", health)
    return app


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="turtleOS MCP access point")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    assert_loopback(args.host)
    web.run_app(build_app(), host=args.host, port=args.port, print=None)
