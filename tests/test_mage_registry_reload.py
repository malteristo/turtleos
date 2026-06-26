import os
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock

sys.modules.setdefault("discord", MagicMock())

import mage


class MageRegistryReloadTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._path = os.path.join(self._tmpdir.name, "mage_registry.yaml")
        self._orig_path = mage.REGISTRY_PATH
        mage.REGISTRY_PATH = self._path

    def tearDown(self) -> None:
        mage.REGISTRY_PATH = self._orig_path
        mage.reload_mage_registry()
        self._tmpdir.cleanup()

    def _write_registry(self, channels: dict) -> None:
        with open(self._path, "w", encoding="utf-8") as fh:
            fh.write("channels:\n")
            for ch_id, entry in channels.items():
                fh.write(f"  '{ch_id}':\n")
                for key, val in entry.items():
                    fh.write(f"    {key}: {val}\n")
        time.sleep(0.01)

    def test_maybe_reload_skips_when_unchanged(self) -> None:
        self._write_registry({"111": {"type": "hosted-river", "mage": "guest"}})
        mage.reload_mage_registry()
        self.assertFalse(mage.maybe_reload_mage_registry())

    def test_maybe_reload_picks_up_new_channel(self) -> None:
        self._write_registry({"111": {"type": "hosted-river", "mage": "guest"}})
        mage.reload_mage_registry()
        self._write_registry(
            {
                "111": {"type": "hosted-river", "mage": "guest"},
                "222": {"type": "hosted-river", "mage": "other"},
            }
        )
        self.assertTrue(mage.maybe_reload_mage_registry())
        self.assertIn("222", mage.get_registry().get("channels", {}))


if __name__ == "__main__":
    unittest.main()
