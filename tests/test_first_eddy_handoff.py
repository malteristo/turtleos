"""First blank-eddy message must reach Turtle dialogue on the split-bot path."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from tests.discord_stub import install_discord_stub

install_discord_stub()

import dialogue_routing
import first_eddy_handoff as feh


class FirstEddyHandoffFileTests(unittest.TestCase):
    def test_write_then_pop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = feh.write_first_eddy_handoff(11, 22, 33, runtime_dir=tmp)
            self.assertTrue(path.exists())
            data = feh.pop_first_eddy_handoff(11, runtime_dir=tmp)
        self.assertEqual(data["thread_id"], 11)
        self.assertEqual(data["parent_id"], 22)
        self.assertEqual(data["message_id"], 33)
        self.assertFalse(path.exists())

    def test_request_writes_from_message(self) -> None:
        message = MagicMock()
        message.id = 77
        message.channel.id = 88
        message.channel.parent_id = 99
        with tempfile.TemporaryDirectory() as tmp:
            path = feh.request_first_eddy_dialogue(message, runtime_dir=tmp)
            data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["thread_id"], 88)
        self.assertEqual(data["message_id"], 77)

    def test_list_scans_every_given_runtime_dir(self) -> None:
        with tempfile.TemporaryDirectory() as primary, tempfile.TemporaryDirectory() as space:
            for runtime_dir, thread_id in ((primary, 111), (space, 333)):
                feh.write_first_eddy_handoff(
                    thread_id, 222, thread_id + 1, runtime_dir=runtime_dir
                )
            found = feh.list_first_eddy_handoffs([primary, space])
            thread_ids = {int(p["thread_id"]) for p in found}
            self.assertEqual(thread_ids, {111, 333})

    def test_rename_success_writes_handoff(self) -> None:
        message = MagicMock()
        message.id = 501
        message.channel.id = 601
        message.channel.parent_id = 701
        with tempfile.TemporaryDirectory() as tmp:
            path = feh.maybe_request_first_eddy_dialogue(
                message, renamed=True, runtime_dir=tmp
            )
            data = feh.pop_first_eddy_handoff(601, runtime_dir=tmp)
        self.assertIsNotNone(path)
        self.assertEqual(data["message_id"], 501)

    def test_rename_failure_writes_nothing(self) -> None:
        message = MagicMock()
        message.id = 502
        message.channel.id = 602
        message.channel.parent_id = 702
        with tempfile.TemporaryDirectory() as tmp:
            path = feh.maybe_request_first_eddy_dialogue(
                message, renamed=False, runtime_dir=tmp
            )
            leftover = feh.pop_first_eddy_handoff(602, runtime_dir=tmp)
        self.assertIsNone(path)
        self.assertIsNone(leftover)


class ProcessFirstEddyHandoffTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        dialogue_routing.reset_inbound_claims()

    def tearDown(self) -> None:
        dialogue_routing.reset_inbound_claims()

    def _payload(self, tmp: str) -> dict:
        feh.write_first_eddy_handoff(11, 22, 33, runtime_dir=tmp)
        return {
            "thread_id": 11,
            "parent_id": 22,
            "message_id": 33,
            "_runtime_dir": tmp,
        }

    async def test_routes_fetched_message(self) -> None:
        fetched = MagicMock()
        thread = MagicMock()
        thread.fetch_member = AsyncMock()
        thread.fetch_message = AsyncMock(return_value=fetched)
        client = MagicMock()
        client.user = MagicMock(id=9)
        client.get_channel.return_value = thread
        with tempfile.TemporaryDirectory() as tmp, patch(
            "mage.set_practice_context_for_channel"
        ), patch(
            "dialogue_routing.route_practice_dialogue", new_callable=AsyncMock
        ) as route:
            payload = self._payload(tmp)
            ok = await dialogue_routing.process_first_eddy_handoff(client, payload)
            leftover = feh.pop_first_eddy_handoff(11, runtime_dir=tmp)
        self.assertTrue(ok)
        route.assert_awaited_once_with(fetched)
        self.assertIsNone(leftover)

    async def test_retries_when_turtle_not_in_thread(self) -> None:
        thread = MagicMock()
        thread.fetch_member = AsyncMock(side_effect=Exception("missing"))
        thread.fetch_message = AsyncMock()
        client = MagicMock()
        client.user = MagicMock(id=9)
        client.get_channel.return_value = thread
        with tempfile.TemporaryDirectory() as tmp, patch(
            "mage.set_practice_context_for_channel"
        ), patch(
            "dialogue_routing.route_practice_dialogue", new_callable=AsyncMock
        ) as route:
            payload = self._payload(tmp)
            ok = await dialogue_routing.process_first_eddy_handoff(client, payload)
            leftover = feh.pop_first_eddy_handoff(11, runtime_dir=tmp)
        self.assertFalse(ok)
        route.assert_not_awaited()
        thread.fetch_message.assert_not_awaited()
        self.assertIsNotNone(leftover)

    async def test_drops_file_when_message_is_gone(self) -> None:
        thread = MagicMock()
        thread.fetch_member = AsyncMock()
        thread.fetch_message = AsyncMock(side_effect=Exception("unknown message"))
        client = MagicMock()
        client.user = MagicMock(id=9)
        client.get_channel.return_value = thread
        with tempfile.TemporaryDirectory() as tmp, patch(
            "mage.set_practice_context_for_channel"
        ), patch(
            "dialogue_routing.route_practice_dialogue", new_callable=AsyncMock
        ) as route:
            payload = self._payload(tmp)
            ok = await dialogue_routing.process_first_eddy_handoff(client, payload)
            leftover = feh.pop_first_eddy_handoff(11, runtime_dir=tmp)
        self.assertFalse(ok)
        route.assert_not_awaited()
        self.assertIsNone(leftover)

    async def test_handoff_skips_a_message_already_inbound(self) -> None:
        """Live 2026-09-13: inbound then handoff posted two replies."""
        self.assertTrue(dialogue_routing.claim_inbound(33))
        fetched = MagicMock()
        fetched.id = 33
        thread = MagicMock()
        thread.fetch_member = AsyncMock()
        thread.fetch_message = AsyncMock(return_value=fetched)
        client = MagicMock()
        client.user = MagicMock(id=9)
        client.get_channel.return_value = thread
        with tempfile.TemporaryDirectory() as tmp, patch(
            "mage.set_practice_context_for_channel"
        ), patch(
            "dialogue_routing.route_practice_dialogue", new_callable=AsyncMock
        ) as route:
            payload = self._payload(tmp)
            ok = await dialogue_routing.process_first_eddy_handoff(client, payload)
            leftover = feh.pop_first_eddy_handoff(11, runtime_dir=tmp)
        self.assertTrue(ok)
        route.assert_not_awaited()
        self.assertIsNone(leftover)

    async def test_same_message_is_not_enqueued_twice(self) -> None:
        message = MagicMock()
        message.id = 77
        message.channel = MagicMock()
        message.channel.id = 11
        message.channel.name = "eddy"
        message.content = "hello"
        with patch(
            "dialogue_queue.enqueue_dialogue", new_callable=AsyncMock
        ) as enqueue:
            first = await dialogue_routing.route_practice_dialogue(message)
            second = await dialogue_routing.route_practice_dialogue(message)
        self.assertTrue(first)
        self.assertFalse(second)
        enqueue.assert_awaited_once()

    def test_old_handoff_routed_without_checking_inbound(self) -> None:
        """Positive control: yesterday's process always called route after pop."""
        src = Path("dialogue_routing.py").read_text(encoding="utf-8")
        start = src.index("async def process_first_eddy_handoff")
        end = src.index("async def first_eddy_handoff_watcher")
        body = src[start:end]
        self.assertIn("already_inbound", body)
        self.assertLess(body.index("already_inbound"), body.index("route_practice_dialogue"))


class FirstEddyHandoffWiringTests(unittest.TestCase):
    def test_river_bot_writes_handoff_after_rename(self) -> None:
        src = Path("river_bot.py").read_text(encoding="utf-8")
        block = src.split("if is_awaiting_title")[1].split(
            "from eddy_lifecycle_bar"
        )[0]
        self.assertIn("handle_eddy_first_message", block)
        self.assertIn("maybe_request_first_eddy_dialogue", block)
        self.assertLess(
            block.index("handle_eddy_first_message"),
            block.index("maybe_request_first_eddy_dialogue"),
        )

    def test_turtle_starts_the_watcher(self) -> None:
        src = Path("discord_bot.py").read_text(encoding="utf-8")
        self.assertIn("start_first_eddy_handoff_watcher", src)

    def test_leaf_does_not_import_the_hub(self) -> None:
        src = Path("first_eddy_handoff.py").read_text(encoding="utf-8")
        self.assertNotIn("import mage", src)
        self.assertNotIn("from mage", src)

    def test_hosted_copy_does_not_teach_silence(self) -> None:
        text = Path("docs/ux/hosted-tester-program.md").read_text(encoding="utf-8")
        self.assertNotIn("no reply yet", text)
        self.assertNotIn("first message does not get a Turtle reply", text)
        self.assertNotIn("Message 1", text)


if __name__ == "__main__":
    unittest.main()
