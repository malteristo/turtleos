"""One room's eddy titles never reach another room (2026-09-28).

The thread registry kept one cache for every practice root: each save wrote
every room's threads into the saving root's file, and the related-thread block
put other members' private titles into prompts.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.modules.setdefault("discord", MagicMock())

import yaml

import thread_registry as tr


class PerRootRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.a = Path(self.tmp.name) / "a"
        self.b = Path(self.tmp.name) / "b"
        tr.clear_registry_cache_for_tests()

    def tearDown(self):
        tr.clear_registry_cache_for_tests()
        self.tmp.cleanup()

    def _in(self, root):
        return patch("thread_registry.get_runtime_dir", return_value=str(root))

    def test_a_save_in_one_root_does_not_carry_another_roots_threads(self):
        with self._in(self.a):
            tr.register_thread(1, "private to a", parent_channel_id=10)
        with self._in(self.b):
            tr.register_thread(2, "private to b", parent_channel_id=20)
        on_disk = yaml.safe_load((self.b / "thread-state" / "registry.yaml").read_text())
        self.assertEqual(set(on_disk["threads"]), {"2"})


class RoomScopedAwarenessTests(unittest.TestCase):
    def setUp(self):
        registry = {"threads": {
            "1": {"name": "garden plans spring", "parent_channel_id": 10},
            "2": {"name": "garden worries", "parent_channel_id": 20},
            "3": {"name": "garden old", "parent_channel": "unknown"},
        }}
        self.p = patch("thread_registry.load_registry", return_value=registry)
        self.p.start()

    def tearDown(self):
        self.p.stop()

    def test_related_threads_come_only_from_this_room(self):
        text = tr.get_related_thread_awareness("garden today", current_thread_id=9, parent_channel_id=10)
        self.assertIn("garden plans spring", text)
        self.assertNotIn("garden worries", text)
        self.assertNotIn("garden old", text)

    def test_no_room_no_threads(self):
        self.assertEqual(tr.get_related_thread_awareness("garden today", current_thread_id=9), "")
        self.assertEqual(tr.build_live_thread_summary(), "")

    def test_live_summary_is_one_room(self):
        text = tr.build_live_thread_summary(parent_channel_id=20)
        self.assertIn("garden worries", text)
        self.assertNotIn("garden plans spring", text)


class PromptWiringTests(unittest.TestCase):
    def test_eddy_prompt_passes_its_room(self):
        src = (Path(__file__).resolve().parents[1] / "dialogue_runtime.py").read_text()
        call = src.split("get_related_thread_awareness(", 1)[1].split(")\n", 1)[0]
        self.assertIn("parent_channel_id=", call)


if __name__ == "__main__":
    unittest.main()
