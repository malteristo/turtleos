"""One connection, and the card that opens what it shows. docs/design/connection-chooser.md."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from aiohttp.test_utils import TestClient, TestServer

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from mcp_access.protocol import Session  # noqa: E402
from mcp_access.registry import private_root, resolve_sources  # noqa: E402
from mcp_access.reveal import RevealError, set_open  # noqa: E402
from mcp_access.server import build_app, connection_name  # noqa: E402
from tests.test_mcp_workshop import (  # noqa: E402
    ROOM_CANARY,
    SHOP_CANARY,
    Shop,
    call,
    file_ref,
    read,
    text_of,
    tool,
    tool_text,
)


def _instructions(shop: Shop, grant) -> str:
    session = shop.session(grant)
    return call(session, "initialize", {"protocolVersion": "2025-06-18"})["result"]["instructions"]


class RevealTests(unittest.TestCase):
    def setUp(self):
        self.shop = Shop()
        health = self.shop.base / "health"
        health.mkdir()
        self.shop.registry["spaces"] = {"health-alice": {"subject": "alice", "practice_dir": str(health)}}
        self.grant = self.shop.store.create(principal="laptop", owner="alice", sources=[], profile="house")[0]

    def tearDown(self):
        self.shop.close()

    def _open(self, source_id: str, *, opened: bool = True, grant=None):
        return set_open(
            self.shop.store,
            (grant or self.grant).id,
            source_id,
            opened=opened,
            registry=self.shop.registry,
        )

    def test_nothing_is_visible_until_it_is_opened_and_closing_hides_it_again(self):
        self.assertEqual(json.loads(tool_text(tool(self.shop.session(self.grant), "search", query=ROOM_CANARY))), [])
        self._open("alice")
        found = tool_text(tool(self.shop.session(self.grant), "search", query=ROOM_CANARY))
        self.assertIn(ROOM_CANARY, found, "positive control: an opened source is readable on the next request")
        self._open("alice", opened=False)
        self.assertEqual(json.loads(tool_text(tool(self.shop.session(self.grant), "search", query=ROOM_CANARY))), [])

    def test_the_practice_opens_and_closes_on_the_same_connection(self):
        self._open("alice-workshop")
        self.assertIn("THE-PRACTICES-OWN-WORDS", text_of(read(self.shop.session(self.grant), file_ref("system/bootstrap.md"))))
        found = tool_text(tool(self.shop.session(self.grant), "search", query=SHOP_CANARY))
        self.assertIn(SHOP_CANARY, found)
        self._open("alice-workshop", opened=False)
        self.assertIn("error", read(self.shop.session(self.grant), file_ref("system/bootstrap.md")))
        self.assertEqual(
            json.loads(tool_text(tool(self.shop.session(self.grant), "search", query=SHOP_CANARY))), []
        )

    def test_a_rooms_connection_cannot_open_the_practice(self):
        rooms = self.shop.store.create(principal="laptop", owner="alice", sources=["alice"], profile="reader")[0]
        with self.assertRaises(RevealError) as caught:
            self._open("alice-workshop", grant=rooms)
        self.assertEqual(caught.exception.code, "unreachable")
        # Positive control: the same open on the combined connection is allowed.
        self._open("alice-workshop")
        self.assertIn("alice-workshop", self.shop.store.get(self.grant.id).sources)

    def test_the_house_profile_starts_closed_and_the_reader_still_plans_rooms(self):
        import mcp_grant

        self.assertEqual(mcp_grant.plan("alice", "house", [], self.shop.registry), [])
        self.assertEqual(mcp_grant.plan("alice", "reader", [], self.shop.registry), ["alice", "health-alice"])
        self.assertEqual(mcp_grant.plan("alice", "house", ["alice-workshop"], self.shop.registry), ["alice-workshop"])
        with self.assertRaises(SystemExit):
            mcp_grant.plan("alice", "reader", ["alice-workshop"], self.shop.registry)

    def test_the_client_is_told_only_what_is_open(self):
        self._open("alice")
        text = _instructions(self.shop, self.grant)
        self.assertIn("Open on this connection: your notes.", text)
        self.assertNotIn("your practice", text)
        self._open("alice-workshop")
        text = _instructions(self.shop, self.grant)
        self.assertIn("your practice", text)
        self.assertIn("bootstrap", text)

    def test_a_combined_grant_is_the_one_entry_and_a_workshop_grant_keeps_its_name(self):
        self.assertEqual(connection_name(["read_note", "workshop_read"]), ("turtleos", ["turtleos-workshop"]))
        self.assertEqual(connection_name(["workshop_read"]), ("turtleos-workshop", []))
        self.assertEqual(connection_name(["read_note"]), ("turtleos", []))


class HttpRevealTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.shop = Shop()
        self.grant, self.token = self.shop.store.create(
            principal="laptop", owner="alice", sources=["alice"], profile="house"
        )
        self.client = TestClient(TestServer(build_app(self.shop.store, lambda: self.shop.registry)))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()
        self.shop.close()

    async def _search(self, query: str) -> str:
        body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "search", "arguments": {"query": query}}}
        response = await self.client.post(
            "/mcp",
            json=body,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Tailscale-User-Login": "alice@example.com",
                "X-Forwarded-For": "203.0.113.7",
            },
        )
        self.assertEqual(response.status, 200)
        return (await response.json())["result"]["content"][0]["text"]

    async def test_closing_is_what_the_next_request_sees(self):
        self.assertIn(ROOM_CANARY, await self._search(ROOM_CANARY))
        set_open(self.shop.store, self.grant.id, "alice", opened=False, registry=self.shop.registry)
        self.assertNotIn(ROOM_CANARY, await self._search(ROOM_CANARY))

    async def test_the_connect_reply_names_the_one_entry_and_what_it_replaces(self):
        from mcp_access import offers

        self.shop.registry["mages"]["alice"]["tailscale_login"] = "alice@example.com"
        headers = {
            "Tailscale-User-Login": "alice@example.com",
            "X-Forwarded-For": "203.0.113.9",
            "X-Turtleos-Client": "connect-tool",
        }
        offer = offers.create(
            self.shop.root, owner="alice", principal="laptop", sources=[], profile="house", url="https://host:8443/mcp"
        )
        offers.mark_ready(self.shop.root, offer.id)
        response = await self.client.post("/connect", headers=headers)
        self.assertEqual(response.status, 200)
        body = await response.json()
        self.assertEqual(body["name"], "turtleos")
        self.assertEqual(body["replaces"], ["turtleos-workshop"])
        self.assertEqual(body["reaches"], [])
        described = " ".join(offers.describe(offer))
        self.assertIn("nothing yet", described)
        self.assertNotIn("alice-workshop", described)


class SessionRereadTests(unittest.TestCase):
    """The server builds a session from a fresh grant read. This pins that the helper does too."""

    def test_session_helper_reads_the_grant_again(self):
        shop = Shop()
        try:
            grant = shop.store.create(principal="laptop", owner="alice", sources=["alice"], profile="house")[0]
            set_open(shop.store, grant.id, "alice", opened=False, registry=shop.registry)
            session = Session(
                shop.store.get(grant.id),
                resolve_sources("alice", shop.store.get(grant.id).sources, shop.registry),
                shop.store,
                owner_root=private_root("alice", shop.registry),
            )
            self.assertEqual(session.sources, [])
        finally:
            shop.close()
