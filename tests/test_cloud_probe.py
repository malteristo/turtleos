"""River lifts the cloud hold on its own once credit is back (09-27)."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
import unittest
from unittest.mock import patch

import cloud_fallback as cf


class ProbeHoldTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"TURTLEOS_HOUSE_DIR": self.tmp.name})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def _hold(self, last_try):
        (cf.house_dir() / "cloud_hold.json").write_text(
            json.dumps({"kind": "funds", "model": "claude-sonnet-4-6", "last_try": last_try})
        )

    def test_credit_back_lifts_the_hold_and_says_so(self):
        self._hold(0)

        async def ok(model):
            return None

        line = asyncio.run(cf.probe_hold(ok))
        self.assertIsNone(cf.read_hold())
        self.assertIn("Cloud is back", line)

    def test_still_out_keeps_the_hold_and_stays_quiet(self):
        self._hold(0)

        async def broke(model):
            raise RuntimeError("Your credit balance is too low")

        self.assertIsNone(asyncio.run(cf.probe_hold(broke)))
        self.assertGreater(cf.read_hold()["last_try"], time.time() - 5)

    def test_no_probe_inside_the_retry_interval(self):
        self._hold(time.time())
        called = []

        async def ask(model):
            called.append(model)

        asyncio.run(cf.probe_hold(ask))
        self.assertEqual(called, [])
        self.assertIsNotNone(cf.read_hold())

    def test_no_hold_no_call(self):
        called = []

        async def ask(model):
            called.append(model)

        self.assertIsNone(asyncio.run(cf.probe_hold(ask)))
        self.assertEqual(called, [])


if __name__ == "__main__":
    unittest.main()
