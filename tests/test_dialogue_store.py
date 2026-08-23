"""Tests for shared dialogue persistence (split-bot lifecycle)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.modules.setdefault("discord", __import__("unittest.mock").mock.MagicMock())
sys.modules.setdefault("discord.ext", sys.modules["discord"])
sys.modules.setdefault("discord.ext.tasks", sys.modules["discord"])

import dialogue_store as ds


class TestDialogueStore(unittest.TestCase):
    def test_write_read_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch("mage.get_runtime_dir", return_value=tmp):
                ds.write_shared(42, [{"role": "user", "content": "hello"}])
                loaded = ds.read_shared(42)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded[0]["content"], "hello")

    def test_clear_removes_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch("mage.get_runtime_dir", return_value=tmp):
                ds.write_shared(7, [{"role": "assistant", "content": "hi"}])
                self.assertTrue(Path(tmp, "dialogue", "7.json").exists())
                ds.clear_shared(7)
                self.assertFalse(Path(tmp, "dialogue", "7.json").exists())

    def test_trim_respects_max_history(self) -> None:
        from state import MAX_DIALOGUE_HISTORY

        with tempfile.TemporaryDirectory() as tmp:
            with patch("mage.get_runtime_dir", return_value=tmp):
                long = [{"role": "user", "content": str(i)} for i in range(MAX_DIALOGUE_HISTORY + 5)]
                ds.write_shared(9, long)
                loaded = ds.read_shared(9)
            assert loaded is not None
            self.assertEqual(len(loaded), MAX_DIALOGUE_HISTORY)
            self.assertEqual(loaded[0]["content"], "5")


class TestHelpersSharedHistory(unittest.TestCase):
    def test_reload_history_reads_disk(self) -> None:
        from helpers import dialogue_histories, reload_history

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dialogue"
            path.mkdir()
            payload = [{"role": "user", "content": "from disk"}]
            (path / "99.json").write_text(json.dumps(payload), encoding="utf-8")
            with patch("dialogue_store.shared_dialogue_enabled", return_value=True), patch(
                "mage.get_runtime_dir", return_value=tmp
            ):
                dialogue_histories.clear()
                history = reload_history(99)
            self.assertEqual(history[0]["content"], "from disk")


if __name__ == "__main__":
    unittest.main()
