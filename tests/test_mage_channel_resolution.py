import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.modules.setdefault("discord", MagicMock())

import mage


class MageChannelResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._path = os.path.join(self._tmpdir.name, "mage_registry.yaml")
        self._orig_path = mage.REGISTRY_PATH
        mage.REGISTRY_PATH = self._path
        self._runtime_root = os.path.join(self._tmpdir.name, "runtime")
        os.makedirs(self._runtime_root, exist_ok=True)

    def tearDown(self) -> None:
        mage.REGISTRY_PATH = self._orig_path
        mage.reload_mage_registry()
        self._tmpdir.cleanup()

    def _write_registry(self, channels: dict, mages: dict | None = None) -> None:
        lines = ["channels:"]
        for ch_id, entry in channels.items():
            lines.append(f"  '{ch_id}':")
            for key, val in entry.items():
                lines.append(f"    {key}: {val}")
        if mages:
            lines.append("mages:")
            for key, entry in mages.items():
                lines.append(f"  {key}:")
                for k, v in entry.items():
                    lines.append(f"    {k}: {v}")
        with open(self._path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        time.sleep(0.01)
        mage.reload_mage_registry()

    def test_resolve_registry_channel_id_parent_channel(self) -> None:
        self._write_registry(
            {
                "100": {"type": "shared-river", "mage": "lukas_play"},
                "200": {"type": "shared-river", "mage": "kermit"},
            },
            mages={
                "lukas_play": {"practice_dir": "/tmp/lukas", "runtime_dir": self._runtime_root},
                "kermit": {"practice_dir": "/tmp/kermit", "runtime_dir": "/tmp/kermit_rt"},
            },
        )
        self.assertEqual(mage.resolve_registry_channel_id(100), 100)

    def test_resolve_registry_channel_id_from_awaiting_title(self) -> None:
        self._write_registry(
            {"1522210357622341766": {"type": "shared-river", "mage": "lukas_play"}},
            mages={
                "lukas_play": {
                    "practice_dir": "/tmp/lukas",
                    "runtime_dir": self._runtime_root,
                },
            },
        )
        thread_id = 1522648705360990469
        parent_id = 1522210357622341766
        awaiting_dir = Path(self._runtime_root) / "thread-state" / "awaiting-title"
        awaiting_dir.mkdir(parents=True, exist_ok=True)
        awaiting_dir.joinpath(f"{thread_id}.json").write_text(
            json.dumps({"thread_id": thread_id, "parent_channel_id": parent_id}),
            encoding="utf-8",
        )
        self.assertEqual(mage.resolve_registry_channel_id(thread_id), parent_id)

    def test_set_practice_context_for_thread_uses_parent_workshop(self) -> None:
        lukas_pd = os.path.join(self._tmpdir.name, "lukas")
        os.makedirs(lukas_pd, exist_ok=True)
        parent_id = 1522210357622341766
        thread_id = 1522648705360990469
        self._write_registry(
            {str(parent_id): {"type": "shared-river", "mage": "lukas_play"}},
            mages={
                "lukas_play": {
                    "practice_dir": lukas_pd,
                    "runtime_dir": self._runtime_root,
                },
            },
        )
        awaiting_dir = Path(self._runtime_root) / "thread-state" / "awaiting-title"
        awaiting_dir.mkdir(parents=True, exist_ok=True)
        awaiting_dir.joinpath(f"{thread_id}.json").write_text(
            json.dumps({"thread_id": thread_id, "parent_channel_id": parent_id}),
            encoding="utf-8",
        )
        pd = mage.set_practice_context_for_channel(thread_id)
        self.assertEqual(pd, lukas_pd)


if __name__ == "__main__":
    unittest.main()
