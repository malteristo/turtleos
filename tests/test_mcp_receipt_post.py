"""River delivers receipts. A second pass does not send them again."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from mcp_access import receipts  # noqa: E402
from mcp_receipt_post import health_channel_id, post_pending  # noqa: E402


class _Msg:
    def __init__(self, mid: int):
        self.id = mid


class _Channel:
    def __init__(self):
        self.sent: list[tuple[str, bool]] = []

    async def send(self, text: str, silent: bool = False):
        self.sent.append((text, silent))
        return _Msg(len(self.sent))


class _Client:
    def __init__(self, channels: dict[int, _Channel]):
        self.channels = channels

    def get_channel(self, channel_id: int):
        return self.channels.get(int(channel_id))

    async def fetch_channel(self, channel_id: int):
        return self.channels.get(int(channel_id))


class DeliveryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "alice"
        (self.root / "story").mkdir(parents=True)
        self.private = _Channel()
        self.health = _Channel()
        self.thread = _Channel()
        self.client = _Client({11: self.private, 801: self.health, 123456789012345: self.thread})
        self.registry = {
            "mages": {"alice": {"practice_dir": str(self.root), "locale": "de"}},
            "spaces": {
                "health": {
                    "subject": "alice",
                    "members": ["alice"],
                    "memory": "isolated",
                    "practice_dir": str(self.tmp.name),
                }
            },
            "channels": {
                "11": {"mage": "alice", "type": "hosted-river"},
                "801": {"primitive": "health", "type": "health", "mage": "health", "subject": "alice"},
            },
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_health_channel_resolves_to_the_subject(self):
        self.assertEqual(health_channel_id(self.registry, "alice"), 801)
        self.assertIsNone(health_channel_id(self.registry, "bob"))

    async def test_a_receipt_is_posted_once_and_the_thread_stays_silent(self):
        self.assertTrue(
            receipts.for_note(
                self.root,
                note_id="123456789012345-morning",
                title="Spaziergang",
                locale="de",
                principal="Laptop Cursor",
                client_name="Cursor",
                client_version="1.2.3",
            )
        )
        self.assertTrue(receipts.for_health(self.root, locale="de", principal="Laptop Cursor", client_name="Cursor"))
        n = await post_pending(self.client, lambda: self.registry)
        self.assertEqual(n, 4)
        self.assertEqual(len(self.thread.sent), 1)
        self.assertTrue(self.thread.sent[0][1])
        self.assertIn("dieses Gespräch", self.thread.sent[0][0])
        self.assertIn("Cursor", self.thread.sent[0][0])
        self.assertNotIn("1.2.3", self.thread.sent[0][0])
        self.assertIn("Laptop Cursor", self.thread.sent[0][0])
        self.assertFalse(self.private.sent[0][1], "the private channel is where she hears it")
        self.assertIn("Spaziergang", self.private.sent[0][0])
        self.assertTrue(self.health.sent[0][1])
        self.assertIn("Gesundheitsbild", self.health.sent[0][0])
        again = await post_pending(self.client, lambda: self.registry)
        self.assertEqual(again, 0)
        self.assertEqual(len(self.thread.sent), 1)

    async def test_a_missing_channel_is_skipped_and_not_retried_forever(self):
        bare = {"mages": {"alice": {"practice_dir": str(self.root)}}, "channels": {}}
        receipts.enqueue_private_line(self.root, "Dein Computer hat dein Gesundheitsbild bereits gelesen.")
        n = await post_pending(self.client, lambda: bare)
        self.assertEqual(n, 0)
        row = json.loads((self.root / receipts.RECEIPTS_REL).read_text().splitlines()[0])
        self.assertEqual(row["posts"][0]["sent"], "skipped:no-channel")


if __name__ == "__main__":
    unittest.main()
