"""The Google card on `!mcp`: connect, switch a room, disconnect.

docs/design/channel-connections.md, criteria 1, 2, 4, 6. Each guard sits beside a control
that must say yes.
"""

from __future__ import annotations

import json
import os
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

try:
    import discord  # noqa: F401
except ImportError:
    raise unittest.SkipTest("needs discord.py")

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import google_connection as gc  # noqa: E402
import room_connections as rc  # noqa: E402
import ui_kit  # noqa: E402
from tests.test_google_connection import ACCESS, CODE, REFRESH, FakeHttp, granted  # noqa: E402
from tests.test_mcp_list import ListFixture, _interaction, alltext, button, buttons, row_for  # noqa: E402

REDIRECT = "https://house.example/connect/google/callback"


class GoogleFixture(ListFixture):
    def setUp(self):
        super().setUp()
        self.house = self.shop.base / "house"
        self.house.mkdir()
        self.registry = self.shop.registry
        self.registry["channels"] = {
            "10": {"type": "river", "mage": "alice", "name": "home-alice", "discord_name": "home-alice"},
            "11": {"type": "craft", "mage": "alice", "name": "craft-turtle", "discord_name": "craft"},
            "12": {"type": "health", "mage": "alice", "name": "my-health", "discord_name": "my-health"},
            "13": {"type": "shared-river", "mage": "alice", "name": "family", "discord_name": "family"},
            "14": {"type": "hosted-river", "mage": "bob", "name": "home-bob", "discord_name": "home-bob"},
        }
        self.env2 = mock.patch.dict(
            os.environ,
            {
                "GOOGLE_CLIENT_ID": "cid",
                "GOOGLE_CLIENT_SECRET": "csecret",
                "GOOGLE_REDIRECT_URI": REDIRECT,
                "TURTLEOS_HOUSE_DIR": str(self.house),
            },
        )
        self.env2.start()

    def tearDown(self):
        self.env2.stop()
        super().tearDown()

    def sign_in(self):
        now = time.time()
        gc.begin(person="alice", root=self.shop.root, house=self.house, channel_id=10, services=["calendar"], now=now)
        state = list(json.loads(gc.pending_path(self.house).read_text()))[-1]
        gc.complete(self.house, state, CODE, FakeHttp([granted()]), now=now + 1)

    def level(self, channel: str) -> str:
        return rc.level("calendar", registry=self.registry, channel_id=channel, person="alice", root=self.shop.root)


class StateOfTheCardTests(GoogleFixture):
    async def test_a_house_without_the_app_says_so_and_offers_nothing(self):
        with mock.patch.dict(os.environ, {"GOOGLE_CLIENT_ID": ""}):
            view = self.view()
            self.assertIn("not set up", alltext(view))
            self.assertNotIn("Connect Google", [b.label for b in buttons(view)])
        self.assertIn("Connect Google", [b.label for b in buttons(self.view())], "positive control")

    async def test_the_card_stays_inside_the_design_language(self):
        forbidden = (REFRESH, ACCESS, CODE, "csecret", "cid", "oauth", "scope", "token")
        self.assertEqual(ui_kit.violations(self.view(), forbidden=forbidden), [])
        self.sign_in()
        self.assertEqual(ui_kit.violations(self.view(), forbidden=forbidden), [])

    async def test_signed_in_lists_only_this_persons_rooms_the_house_allows(self):
        self.sign_in()
        view = self.view()
        text = alltext(view)
        self.assertIn("Calendar · home-alice", text)
        self.assertIn("Calendar · craft", text)
        for never in ("my-health", "family", "home-bob"):
            self.assertNotIn(never, text, never)
        self.assertEqual(button(view, "Turn off").label, "Turn off")  # home: on by default
        self.assertIn("ada@example.com", text)
        for secret in (REFRESH, ACCESS, CODE):
            self.assertNotIn(secret, text)

    async def test_a_room_that_is_off_says_so_beside_its_own_button(self):
        self.sign_in()
        home = row_for(self.view(), "Calendar · home-alice")
        craft = row_for(self.view(), "Calendar · craft")
        self.assertIn("on", home["components"][0]["content"])
        self.assertEqual(home["accessory"]["label"], "Turn off")
        self.assertIn("off", craft["components"][0]["content"])
        self.assertEqual(craft["accessory"]["label"], "Turn on")


class ConnectTests(GoogleFixture):
    async def test_connect_sends_one_private_link_and_keeps_the_record(self):
        press = _interaction(111)
        press.channel_id = 10
        await button(self.view(), "Connect Google").callback(press)
        send = press.response.send_message
        send.assert_awaited_once()
        self.assertTrue(send.await_args.kwargs.get("ephemeral"), "the link is only for the one who pressed")
        text = send.await_args.args[0]
        self.assertIn("https://accounts.google.com/", text)
        self.assertNotIn("csecret", text)
        pending = json.loads(gc.pending_path(self.house).read_text())
        record = next(iter(pending.values()))
        self.assertEqual((record["person"], record["root"], record["channel"]), ("alice", str(self.shop.root), "10"))

    async def test_a_stranger_gets_no_link(self):
        press = _interaction(999)
        press.channel_id = 10
        await button(self.view(), "Connect Google").callback(press)
        self.assertFalse(gc.pending_path(self.house).exists())
        self.assertTrue(press.response.send_message.await_args.kwargs.get("ephemeral"))


class SwitchTests(GoogleFixture):
    async def test_a_press_switches_one_room_and_the_card_follows(self):
        self.sign_in()
        self.assertEqual(self.level("11"), "off", "craft is not on until he says so")
        press = _interaction(111)
        await row_for_button(self.view(), "Calendar · craft").callback(press)
        self.assertEqual(self.level("11"), "look")
        self.assertEqual(self.level("10"), "look", "the other room is untouched")
        press.response.edit_message.assert_awaited_once()
        press = _interaction(111)
        await row_for_button(self.view(), "Calendar · craft").callback(press)
        self.assertEqual(self.level("11"), "off")

    async def test_a_room_the_house_forbids_cannot_be_switched_on_by_a_forged_press(self):
        import mcp_list_ui

        self.sign_in()
        press = _interaction(111)
        for room in ("12", "13", "14"):  # health, shared, and another person's home
            await mcp_list_ui._google_room(press, "calendar", room)
            self.assertEqual(self.level(room), "off", room)
        self.assertEqual(press.response.send_message.await_count, 3, "each was refused out loud")
        data = rc.choices_path(self.shop.root)
        self.assertFalse(data.exists() and any(r in data.read_text() for r in ("12", "13", "14")))
        await mcp_list_ui._google_room(_interaction(111), "calendar", "11")  # positive control
        self.assertEqual(self.level("11"), "look")

    async def test_another_member_cannot_switch_a_room_that_is_not_theirs(self):
        self.sign_in()
        import mcp_list_ui

        press = _interaction(222)  # bob
        await mcp_list_ui._google_room(press, "calendar", "11")  # alice's craft
        self.assertEqual(self.level("11"), "off")
        self.assertTrue(press.response.send_message.await_args.kwargs.get("ephemeral"))


class DisconnectTests(GoogleFixture):
    async def test_disconnect_asks_first_then_removes_every_room_at_once(self):
        self.sign_in()
        with mock.patch.object(gc, "UrlHttp", lambda: FakeHttp([{}])):
            asked = _interaction(111)
            await button(self.view(), "Disconnect Google").callback(asked)
            self.assertTrue(gc.token_path(self.shop.root).exists(), "asking removes nothing")
            asked_view = asked.response.edit_message.await_args.kwargs["view"]
            sure = _interaction(111)
            await button(asked_view, "Disconnect").callback(sure)
        self.assertFalse(gc.token_path(self.shop.root).exists())
        self.assertIsNone(gc.signed_in("alice", self.shop.root))
        text = alltext(self.view())
        self.assertNotIn("Calendar · home-alice", text)
        self.assertIn("Connect Google", [b.label for b in buttons(self.view())])

    async def test_keep_leaves_it_connected(self):
        self.sign_in()
        asked = _interaction(111)
        await button(self.view(), "Disconnect Google").callback(asked)
        await button(asked.response.edit_message.await_args.kwargs["view"], "Keep").callback(_interaction(111))
        self.assertIsNotNone(gc.signed_in("alice", self.shop.root))


def row_for_button(view, name: str):
    section = row_for(view, name)
    label = section["accessory"]["label"]
    return next(b for b in buttons(view) if b.custom_id == section["accessory"]["custom_id"] and b.label == label)


if __name__ == "__main__":
    unittest.main()
